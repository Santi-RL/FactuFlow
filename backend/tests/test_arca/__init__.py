"""Fixtures para tests de ARCA."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from app.arca.models import TicketAcceso


@pytest.fixture
def mock_ticket():
    """Fixture que devuelve un ticket de acceso mock."""
    return TicketAcceso(
        token="mock_token_12345",
        sign="mock_sign_67890",
        expiracion=datetime.utcnow() + timedelta(hours=12),
        servicio="wsfe",
    )


@pytest.fixture
def mock_cuit():
    """Fixture con CUIT de prueba de ARCA."""
    return "20409378472"  # CUIT de homologación de ARCA


@pytest.fixture
def mock_cert_paths(tmp_path):
    """Fixture que crea archivos de certificado y clave mock."""
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()

    cert_file = cert_dir / "test.crt"
    key_file = cert_dir / "test.key"

    # Crear archivos vacíos para testing
    cert_file.write_text("mock certificate")
    key_file.write_text("mock private key")

    return {"cert_path": str(cert_file), "key_path": str(key_file)}
