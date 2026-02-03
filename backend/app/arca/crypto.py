"""Funciones de criptografía para firma de TRA con certificados X.509."""

import base64
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.hazmat.backends import default_backend

from app.arca.exceptions import ArcaCertificateError


def load_certificate(cert_path: str) -> x509.Certificate:
    """
    Carga un certificado X.509 desde un archivo.

    Args:
        cert_path: Ruta al archivo del certificado (.crt o .pem)

    Returns:
        Objeto Certificate

    Raises:
        ArcaCertificateError: Si el archivo no existe o no se puede leer
    """
    cert_file = Path(cert_path)

    if not cert_file.exists():
        raise ArcaCertificateError(f"Archivo de certificado no encontrado: {cert_path}")

    try:
        with open(cert_file, "rb") as f:
            cert_data = f.read()

        # Intentar cargar como PEM
        try:
            return x509.load_pem_x509_certificate(cert_data, default_backend())
        except Exception:
            # Intentar cargar como DER
            return x509.load_der_x509_certificate(cert_data, default_backend())

    except Exception as e:
        raise ArcaCertificateError(f"Error al cargar certificado: {str(e)}")


def load_private_key(key_path: str, password: bytes | None = None):
    """
    Carga una clave privada desde un archivo.

    Args:
        key_path: Ruta al archivo de la clave privada (.key o .pem)
        password: Contraseña de la clave privada (opcional)

    Returns:
        Objeto de clave privada

    Raises:
        ArcaCertificateError: Si el archivo no existe o no se puede leer
    """
    key_file = Path(key_path)

    if not key_file.exists():
        raise ArcaCertificateError(
            f"Archivo de clave privada no encontrado: {key_path}"
        )

    try:
        with open(key_file, "rb") as f:
            key_data = f.read()

        # Intentar cargar como PEM
        try:
            return serialization.load_pem_private_key(
                key_data, password=password, backend=default_backend()
            )
        except Exception:
            # Intentar cargar como DER
            return serialization.load_der_private_key(
                key_data, password=password, backend=default_backend()
            )

    except Exception as e:
        raise ArcaCertificateError(f"Error al cargar clave privada: {str(e)}")


def verify_certificate_validity(cert: x509.Certificate) -> None:
    """
    Verifica que el certificado esté vigente.

    Args:
        cert: Certificado a verificar

    Raises:
        ArcaCertificateError: Si el certificado está vencido o no es válido aún
    """
    now = datetime.utcnow()

    if now < cert.not_valid_before_utc:
        raise ArcaCertificateError(
            f"El certificado aún no es válido. Válido desde: {cert.not_valid_before_utc}"
        )

    if now > cert.not_valid_after_utc:
        raise ArcaCertificateError(
            f"El certificado está vencido. Venció el: {cert.not_valid_after_utc}"
        )


def generate_tra(servicio: str = "wsfe", ttl_hours: int = 12) -> str:
    """
    Genera un Ticket de Requerimiento de Acceso (TRA) en formato XML.

    Args:
        servicio: Servicio al que se solicita acceso (ej: "wsfe", "wsfex")
        ttl_hours: Tiempo de vida del TRA en horas (máximo 12)

    Returns:
        XML del TRA como string
    """
    if ttl_hours > 12:
        ttl_hours = 12

    now = datetime.utcnow()
    generation_time = now.strftime("%Y-%m-%dT%H:%M:%S")
    expiration_time = (now + timedelta(hours=ttl_hours)).strftime("%Y-%m-%dT%H:%M:%S")
    unique_id = int(now.timestamp())

    tra_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
<header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{generation_time}</generationTime>
    <expirationTime>{expiration_time}</expirationTime>
</header>
<service>{servicio}</service>
</loginTicketRequest>"""

    return tra_xml


def sign_tra(
    tra: str, cert_path: str, key_path: str, key_password: bytes | None = None
) -> str:
    """
    Firma un TRA con el certificado X.509 usando CMS (PKCS#7).

    Args:
        tra: TRA en formato XML
        cert_path: Ruta al certificado
        key_path: Ruta a la clave privada
        key_password: Contraseña de la clave privada (opcional)

    Returns:
        CMS firmado y codificado en Base64

    Raises:
        ArcaCertificateError: Si hay errores en el proceso de firma
    """
    try:
        # Cargar certificado y clave privada
        cert = load_certificate(cert_path)
        private_key = load_private_key(key_path, key_password)

        # Verificar validez del certificado
        verify_certificate_validity(cert)

        # Convertir TRA a bytes
        tra_bytes = tra.encode("utf-8")

        # Crear firma CMS (PKCS#7)
        # Usando SignedData sin atributos adicionales
        options = [pkcs7.PKCS7Options.DetachedSignature]

        cms = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(tra_bytes)
            .add_signer(cert, private_key, hashes.SHA256())
            .sign(serialization.Encoding.DER, options)
        )

        # Codificar en Base64
        cms_base64 = base64.b64encode(cms).decode("ascii")

        return cms_base64

    except ArcaCertificateError:
        raise
    except Exception as e:
        raise ArcaCertificateError(f"Error al firmar TRA: {str(e)}")


def create_signed_tra(
    cert_path: str,
    key_path: str,
    servicio: str = "wsfe",
    ttl_hours: int = 12,
    key_password: bytes | None = None,
) -> str:
    """
    Crea y firma un TRA en un solo paso.

    Args:
        cert_path: Ruta al certificado
        key_path: Ruta a la clave privada
        servicio: Servicio al que se solicita acceso
        ttl_hours: Tiempo de vida del TRA en horas
        key_password: Contraseña de la clave privada (opcional)

    Returns:
        CMS firmado y codificado en Base64

    Raises:
        ArcaCertificateError: Si hay errores en el proceso
    """
    # Generar TRA
    tra = generate_tra(servicio, ttl_hours)

    # Firmar TRA
    cms = sign_tra(tra, cert_path, key_path, key_password)

    return cms


def get_certificate_info(cert_path: str) -> dict:
    """
    Obtiene información de un certificado.

    Args:
        cert_path: Ruta al certificado

    Returns:
        Diccionario con información del certificado
    """
    cert = load_certificate(cert_path)

    # Extraer información del subject
    subject = cert.subject
    subject_dict = {}
    for attr in subject:
        subject_dict[attr.oid._name] = attr.value

    return {
        "subject": subject_dict,
        "issuer": {attr.oid._name: attr.value for attr in cert.issuer},
        "serial_number": str(cert.serial_number),
        "not_valid_before": cert.not_valid_before_utc.isoformat(),
        "not_valid_after": cert.not_valid_after_utc.isoformat(),
        "version": cert.version.name,
    }
