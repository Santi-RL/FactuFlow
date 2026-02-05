"""Cliente simple de WSAA (ARCA) para pruebas de homologacion.

Replica el flujo oficial:
1) Generar TRA
2) Firmar CMS
3) Enviar loginCms
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from zeep import Client
from zeep.exceptions import Fault, TransportError

# Permitir importar app.* desde backend/
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.arca.crypto import sign_tra  # noqa: E402


def build_tra_xml(servicio: str) -> str:
    """Genera TRA con ventana corta (-10/+10 min) como en el ejemplo oficial."""
    now = datetime.now()
    gen_time = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    exp_time = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    unique_id = now.strftime("%y%m%d%H%M")

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<loginTicketRequest version=\"1.0\">\n"
        "<header>\n"
        f"    <uniqueId>{unique_id}</uniqueId>\n"
        f"    <generationTime>{gen_time}</generationTime>\n"
        f"    <expirationTime>{exp_time}</expirationTime>\n"
        "</header>\n"
        f"<service>{servicio}</service>\n"
        "</loginTicketRequest>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prueba de loginCms con WSAA (ARCA)"
    )
    parser.add_argument("--cert", required=True, help="Ruta al .crt")
    parser.add_argument("--key", required=True, help="Ruta al .key")
    parser.add_argument("--service", default="wsfe", help="Servicio (default: wsfe)")
    parser.add_argument(
        "--wsaa-wsdl",
        default="https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL",
        help="WSDL de WSAA (default: homologacion)",
    )
    parser.add_argument("--out", help="Archivo para guardar la respuesta XML")

    args = parser.parse_args()

    cert_path = Path(args.cert)
    key_path = Path(args.key)

    if not cert_path.exists():
        print(f"Certificado no encontrado: {cert_path}")
        return 2
    if not key_path.exists():
        print(f"Clave privada no encontrada: {key_path}")
        return 2

    tra_xml = build_tra_xml(args.service)

    try:
        cms_b64 = sign_tra(tra_xml, str(cert_path), str(key_path))
    except Exception as exc:
        print(f"Error firmando TRA: {exc}")
        return 3

    try:
        client = Client(args.wsaa_wsdl)
        response = client.service.loginCms(cms_b64)
    except Fault as exc:
        print(f"Error SOAP en WSAA: {exc.message}")
        return 4
    except TransportError as exc:
        print(f"Error de transporte en WSAA: {exc}")
        return 5
    except Exception as exc:
        print(f"Error inesperado en WSAA: {exc}")
        return 6

    if args.out:
        Path(args.out).write_text(response, encoding="utf-8")

    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
