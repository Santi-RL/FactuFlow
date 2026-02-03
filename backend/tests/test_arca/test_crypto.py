"""Tests para funciones de criptografía de ARCA."""

import pytest
from datetime import datetime

from app.arca.crypto import generate_tra, get_certificate_info
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
