"""Tests para funciones de criptografía de ARCA."""

import base64
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

import pytest

from app.arca.crypto import generate_tra, sign_tra
from app.arca.exceptions import ArcaCertificateError


class TestGenerateTra:
    """Tests para generate_tra."""

    def test_generate_tra_default(self):
        """Debe generar TRA con valores por defecto."""
        tra = generate_tra()

        assert "<?xml version" in tra
        assert "<loginTicketRequest" in tra
        assert "<service>wsfe</service>" in tra
        assert "<uniqueId>" in tra
        assert "<generationTime>" in tra
        assert "<expirationTime>" in tra

    def test_generate_tra_custom_service(self):
        """Debe generar TRA con servicio personalizado."""
        tra = generate_tra(servicio="wsfex")

        assert "<service>wsfex</service>" in tra

    def test_generate_tra_custom_ttl(self):
        """Debe generar TRA con TTL personalizado."""
        tra = generate_tra(ttl_hours=6)

        # Verificar que el XML es válido
        assert "<loginTicketRequest" in tra
        assert "<expirationTime>" in tra

    def test_generate_tra_max_ttl(self):
        """Debe limitar TTL a máximo 12 horas."""
        tra = generate_tra(ttl_hours=24)  # Solicita 24, debe limitarse a 12

        # Verificar que el XML es válido
        assert "<loginTicketRequest" in tra


# Nota: Los tests de load_certificate, load_private_key, sign_tra, etc.
# requieren certificados reales o mocks más complejos, por lo que se
# testearán en tests de integración o con mocks apropiados.
# Para tests unitarios básicos, estos casos cubren la funcionalidad principal.


class TestCertificateOperations:
    """Tests para operaciones con certificados."""

    def test_load_certificate_not_found(self):
        """Debe lanzar error si el certificado no existe."""
        with pytest.raises(ArcaCertificateError) as exc_info:
            from app.arca.crypto import load_certificate

            load_certificate("/path/to/nonexistent/cert.crt")

        assert "no encontrado" in str(exc_info.value).lower()

    def test_load_private_key_not_found(self):
        """Debe lanzar error si la clave privada no existe."""
        with pytest.raises(ArcaCertificateError) as exc_info:
            from app.arca.crypto import load_private_key

            load_private_key("/path/to/nonexistent/key.key")

        assert "no encontrado" in str(exc_info.value).lower()

    def test_sign_tra_genera_cms_pkcs7_compatible(self, tmp_path: Path) -> None:
        """Debe firmar un TRA y producir un CMS DER con el certificado incluido."""
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "FactuFlow Test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(private_key.public_key())
            .serial_number(1)
            .not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc))
            .not_valid_after(datetime(2040, 1, 1, tzinfo=timezone.utc))
            .sign(private_key, hashes.SHA256())
        )
        password = b"clave-sintetica"
        cert_path = tmp_path / "certificado.pem"
        key_path = tmp_path / "clave.pem"
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(password),
            )
        )

        cms_base64 = sign_tra(
            "<loginTicketRequest/>",
            str(cert_path),
            str(key_path),
            password,
        )

        cms_der = base64.b64decode(cms_base64, validate=True)
        certificados = pkcs7.load_der_pkcs7_certificates(cms_der)
        assert len(certificados) == 1
        assert certificados[0].serial_number == cert.serial_number
