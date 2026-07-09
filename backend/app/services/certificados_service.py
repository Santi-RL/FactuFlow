"""Servicio para manejo de certificados ARCA."""

import os
import logging
import re
from uuid import uuid4
from datetime import date, datetime
from pathlib import Path
from typing import Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID

from app.core.config import settings
from app.arca.crypto import (
    get_default_private_key_password,
    load_certificate,
    load_private_key,
    verify_certificate_validity,
)
from app.arca.exceptions import ArcaCertificateError

logger = logging.getLogger(__name__)


MANAGED_CERT_FILENAME_RE = re.compile(
    r"^(?P<cuit>\d{11})_"
    r"(?P<ambiente>homologacion|produccion)_"
    r"(?P<fecha>\d{8})_"
    r"(?P<hora>\d{6})"
    r"(?:_(?P<nonce>[0-9a-f]{32}))?"
    r"\.(?P<extension>key|crt|cer|pem)$"
)


def _formatear_limite_upload(max_bytes: int) -> str:
    """Formatea un límite de bytes para mensajes de error de upload."""
    if max_bytes >= 1024 * 1024 and max_bytes % (1024 * 1024) == 0:
        return f"{max_bytes // (1024 * 1024)} MB"
    if max_bytes >= 1024 and max_bytes % 1024 == 0:
        return f"{max_bytes // 1024} KB"
    return f"{max_bytes} bytes"


def _certs_base_path() -> Path:
    """Resuelve el directorio administrado de certificados."""
    return Path(settings.certs_path).resolve()


def _write_private_key_file(path: Path, contenido: bytes) -> None:
    """Crea una clave privada con permisos restrictivos desde la apertura."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    fd = os.open(path, flags, 0o400)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(contenido)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise

    # Defensa en profundidad para plataformas que no honren el modo inicial.
    os.chmod(path, 0o400)


def _ensure_path_inside_certs_base(path: Path) -> Path:
    """Verifica que un path resuelto pertenezca al directorio de certificados."""
    base = _certs_base_path()
    resolved = path.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ArcaCertificateError(
            "El archivo de certificado debe estar dentro del directorio administrado"
        ) from exc
    return resolved


def resolve_cert_storage_path(path_value: str) -> str:
    """Resuelve paths absolutos o relativos de certificados guardados en BD."""
    path = Path(path_value)
    if path.is_absolute():
        return str(_ensure_path_inside_certs_base(path))

    normalized_parts = list(path.parts)
    certs_base = _certs_base_path()
    if normalized_parts and normalized_parts[0] == certs_base.name:
        path = Path(*normalized_parts[1:])

    return str(_ensure_path_inside_certs_base(certs_base / path))


def resolve_managed_cert_filename(
    filename: str, cuit: str, ambiente: str, extension: str
) -> Path:
    """Resuelve un archivo administrado generado por FactuFlow."""
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ArcaCertificateError("Nombre de archivo de certificado inválido")

    match = MANAGED_CERT_FILENAME_RE.fullmatch(filename)
    if not match:
        raise ArcaCertificateError("Nombre de archivo de certificado inválido")

    if match.group("cuit") != cuit or match.group("ambiente") != ambiente:
        raise ArcaCertificateError(
            "La clave privada no coincide con el CUIT y ambiente indicados"
        )

    if match.group("extension") != extension:
        raise ArcaCertificateError("Tipo de archivo de certificado inválido")

    return _ensure_path_inside_certs_base(_certs_base_path() / filename)


class CertificadoInfo:
    """Información extraída de un certificado."""

    def __init__(
        self,
        cuit: str,
        fecha_emision: date,
        fecha_vencimiento: date,
        subject: dict,
        issuer: dict,
        serial_number: str,
    ):
        self.cuit = cuit
        self.fecha_emision = fecha_emision
        self.fecha_vencimiento = fecha_vencimiento
        self.subject = subject
        self.issuer = issuer
        self.serial_number = serial_number

    @property
    def dias_restantes(self) -> int:
        """Calcula días restantes hasta el vencimiento."""
        delta = self.fecha_vencimiento - date.today()
        return delta.days

    @property
    def estado(self) -> str:
        """Calcula el estado del certificado basado en días restantes."""
        dias = self.dias_restantes
        if dias <= 0:
            return "vencido"
        elif dias <= 30:
            return "por_vencer"
        return "valido"


class CertificadosService:
    """Servicio para gestión de certificados ARCA."""

    def __init__(self):
        """Inicializa el servicio de certificados."""
        self.certs_path = _certs_base_path()
        self.certs_path.mkdir(parents=True, exist_ok=True)

    async def generar_clave_y_csr(
        self, cuit: str, nombre_empresa: str, ambiente: str
    ) -> Tuple[str, str, str]:
        """
        Genera clave privada RSA 2048 y CSR.

        Args:
            cuit: CUIT de la empresa (11 dígitos sin guiones)
            nombre_empresa: Nombre de la empresa/persona
            ambiente: "homologacion" o "produccion"

        Returns:
            Tupla con (key_path, csr_content, key_filename)

        Raises:
            ArcaCertificateError: Si hay error en la generación
        """
        try:
            logger.info(f"Generando clave privada y CSR para CUIT: {cuit}")

            # Generar clave privada RSA 2048 bits
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=2048, backend=default_backend()
            )

            # Construir subject del certificado
            subject = x509.Name(
                [
                    x509.NameAttribute(NameOID.COUNTRY_NAME, "AR"),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, nombre_empresa),
                    x509.NameAttribute(NameOID.COMMON_NAME, cuit),
                    x509.NameAttribute(NameOID.SERIAL_NUMBER, f"CUIT {cuit}"),
                ]
            )

            # Crear CSR
            csr = (
                x509.CertificateSigningRequestBuilder()
                .subject_name(subject)
                .sign(private_key, hashes.SHA256(), backend=default_backend())
            )

            # Generar nombres de archivo únicos
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            key_filename = f"{cuit}_{ambiente}_{timestamp}_{uuid4().hex}.key"
            key_path = self.certs_path / key_filename

            # Guardar clave privada con permisos restrictivos
            key_password = get_default_private_key_password()
            key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=(
                    serialization.BestAvailableEncryption(key_password)
                    if key_password
                    else serialization.NoEncryption()
                ),
            )

            _write_private_key_file(key_path, key_pem)

            # Convertir CSR a PEM string
            csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode("utf-8")

            logger.info(f"Clave y CSR generados exitosamente para CUIT: {cuit}")

            return str(key_path), csr_pem, key_filename

        except Exception as e:
            logger.error(f"Error generando clave y CSR: {str(e)}")
            raise ArcaCertificateError(f"Error al generar clave y CSR: {str(e)}")

    async def validar_certificado(
        self, cert_path: str, key_path: str, cuit_esperado: str
    ) -> CertificadoInfo:
        """
        Valida un certificado y verifica que coincida con la clave privada.

        Args:
            cert_path: Path al archivo del certificado
            key_path: Path al archivo de la clave privada
            cuit_esperado: CUIT que se espera en el certificado

        Returns:
            CertificadoInfo con la información extraída

        Raises:
            ArcaCertificateError: Si el certificado es inválido
        """
        try:
            logger.info(f"Validando certificado: {cert_path}")

            # Cargar certificado
            cert = load_certificate(cert_path)

            # Verificar validez temporal
            verify_certificate_validity(cert)

            # Cargar clave privada
            private_key = load_private_key(key_path)

            # Verificar que el certificado y la clave coincidan
            # Comparamos las claves públicas
            cert_public_key = cert.public_key()
            private_public_key = private_key.public_key()

            cert_public_numbers = cert_public_key.public_numbers()
            private_public_numbers = private_public_key.public_numbers()

            if (
                cert_public_numbers.n != private_public_numbers.n
                or cert_public_numbers.e != private_public_numbers.e
            ):
                raise ArcaCertificateError(
                    "El certificado no coincide con la clave privada"
                )

            # Extraer información del certificado
            subject_dict = {}
            for attr in cert.subject:
                subject_dict[attr.oid._name] = attr.value

            issuer_dict = {}
            for attr in cert.issuer:
                issuer_dict[attr.oid._name] = attr.value

            def extraer_cuit(valor: str) -> str:
                """Extrae dígitos del CUIT desde un string."""
                if not valor:
                    return ""
                digitos = "".join(ch for ch in valor if ch.isdigit())
                return digitos if len(digitos) == 11 else ""

            # Extraer CUIT del CN o del SERIALNUMBER (ARCA usa alias en CN)
            cn_attr = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            serial_attr = cert.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)
            cn_valor = cn_attr[0].value if cn_attr else ""
            serial_valor = serial_attr[0].value if serial_attr else ""

            cuit_cert = extraer_cuit(cn_valor)
            if not cuit_cert:
                cuit_cert = extraer_cuit(serial_valor)

            # Verificar que el CUIT coincida
            if cuit_cert != cuit_esperado:
                raise ArcaCertificateError(
                    "El CUIT del certificado no coincide con el esperado "
                    f"(CN={cn_valor}, SERIALNUMBER={serial_valor}, esperado={cuit_esperado})"
                )

            info = CertificadoInfo(
                cuit=cuit_cert,
                fecha_emision=cert.not_valid_before_utc.date(),
                fecha_vencimiento=cert.not_valid_after_utc.date(),
                subject=subject_dict,
                issuer=issuer_dict,
                serial_number=str(cert.serial_number),
            )

            logger.info(
                f"Certificado validado exitosamente. Vence: {info.fecha_vencimiento}"
            )

            return info

        except ArcaCertificateError:
            raise
        except Exception as e:
            logger.error(f"Error validando certificado: {str(e)}")
            raise ArcaCertificateError(f"Error al validar certificado: {str(e)}")

    def calcular_estado(self, dias_restantes: int) -> str:
        """
        Calcula el estado del certificado basado en días restantes.

        Args:
            dias_restantes: Días hasta el vencimiento

        Returns:
            Estado: "valido", "por_vencer" o "vencido"
        """
        if dias_restantes <= 0:
            return "vencido"
        elif dias_restantes <= 30:
            return "por_vencer"
        return "valido"

    def get_tipo_alerta(self, dias_restantes: int) -> str:
        """
        Determina el tipo de alerta basado en días restantes.

        Args:
            dias_restantes: Días hasta el vencimiento

        Returns:
            Tipo de alerta: "danger", "warning" o "info"
        """
        if dias_restantes <= 0:
            return "danger"
        elif dias_restantes <= 7:
            return "danger"
        elif dias_restantes <= 30:
            return "warning"
        return "info"

    async def guardar_certificado(
        self, contenido: bytes, cuit: str, ambiente: str
    ) -> str:
        """
        Guarda un certificado en el sistema de archivos.

        Args:
            contenido: Contenido del certificado en bytes
            cuit: CUIT asociado
            ambiente: "homologacion" o "produccion"

        Returns:
            Path del archivo guardado

        Raises:
            ArcaCertificateError: Si hay error al guardar
        """
        max_bytes = settings.certificate_max_upload_bytes
        if len(contenido) > max_bytes:
            raise ArcaCertificateError(
                "El certificado supera el tamaño máximo permitido "
                f"de {_formatear_limite_upload(max_bytes)}"
            )

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cert_filename = f"{cuit}_{ambiente}_{timestamp}_{uuid4().hex}.crt"
            cert_path = self.certs_path / cert_filename

            with open(cert_path, "xb") as f:
                f.write(contenido)

            # Establecer permisos restrictivos
            os.chmod(cert_path, 0o400)

            logger.info(f"Certificado guardado: {cert_path}")

            return str(cert_path)

        except Exception as e:
            logger.error(f"Error guardando certificado: {str(e)}")
            raise ArcaCertificateError(f"Error al guardar certificado: {str(e)}")
