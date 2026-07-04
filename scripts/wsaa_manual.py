"""Cliente simple de WSAA (ARCA) para pruebas de homologacion.

Replica el flujo oficial:
1) Generar TRA
2) Firmar CMS
3) Enviar loginCms
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from zeep import Client
from zeep.exceptions import Fault, TransportError

# Permitir importar app.* desde backend/
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.arca.crypto import sign_tra  # noqa: E402


_LAST_UNIQUE_ID = 0


def build_unique_id() -> str:
    """Genera un identificador numérico monotónico con resolución alta para el TRA."""
    global _LAST_UNIQUE_ID

    candidate = int(time.time())
    if candidate <= _LAST_UNIQUE_ID:
        candidate = _LAST_UNIQUE_ID + 1
    _LAST_UNIQUE_ID = candidate
    return str(candidate)


def write_sensitive_response(
    out_path: Path, response: str, *, overwrite: bool = False
) -> None:
    """Guarda Token/Sign con permisos restrictivos y sin pisar por defecto."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if overwrite else os.O_EXCL
    fd = os.open(out_path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(response)
    try:
        os.chmod(out_path, 0o600)
    except OSError:
        pass


def build_tra_xml(servicio: str) -> str:
    """Genera TRA con ventana corta (-10/+10 min) como en el ejemplo oficial."""
    now = datetime.now()
    gen_time = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    exp_time = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S")
    unique_id = build_unique_id()

    request = ET.Element("loginTicketRequest", {"version": "1.0"})
    header = ET.SubElement(request, "header")
    ET.SubElement(header, "uniqueId").text = unique_id
    ET.SubElement(header, "generationTime").text = gen_time
    ET.SubElement(header, "expirationTime").text = exp_time
    ET.SubElement(request, "service").text = servicio
    return ET.tostring(request, encoding="unicode", xml_declaration=True)


def main(argv: list[str] | None = None) -> int:
    """Ejecuta una prueba manual de loginCms sin exponer credenciales por defecto."""
    parser = argparse.ArgumentParser(description="Prueba de loginCms con WSAA (ARCA)")
    parser.add_argument("--cert", required=True, help="Ruta al .crt")
    parser.add_argument("--key", required=True, help="Ruta al .key")
    parser.add_argument("--service", default="wsfe", help="Servicio (default: wsfe)")
    parser.add_argument(
        "--wsaa-wsdl",
        default="https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL",
        help="WSDL de WSAA (default: homologacion)",
    )
    parser.add_argument(
        "--out", help="Archivo para guardar la respuesta XML con Token y Sign"
    )
    parser.add_argument(
        "--overwrite-output",
        action="store_true",
        help="Permite sobrescribir el archivo indicado por --out.",
    )
    parser.add_argument(
        "--print-response",
        action="store_true",
        help=(
            "Imprime la respuesta completa de WSAA. Puede contener Token y Sign; "
            "usar solo en entornos controlados."
        ),
    )

    args = parser.parse_args(argv)

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
        out_path = Path(args.out)
        try:
            write_sensitive_response(
                out_path, response, overwrite=args.overwrite_output
            )
        except FileExistsError:
            print(
                "El archivo de salida ya existe; use --overwrite-output para reemplazarlo.",
                file=sys.stderr,
            )
            return 7
        print(
            "ATENCIÓN: la respuesta WSAA guardada contiene Token y Sign; "
            "consérvela fuera de Git y de carpetas compartidas.",
            file=sys.stderr,
        )

    if args.print_response:
        print(response)
    elif args.out:
        print(f"LoginCms OK. Respuesta guardada en: {args.out}")
    else:
        print("LoginCms OK. Respuesta recibida; use --out para guardarla.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
