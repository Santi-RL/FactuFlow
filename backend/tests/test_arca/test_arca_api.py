"""Tests para endpoints de API de ARCA."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.api.arca import get_wsfe_client
from app.arca.config import ArcaAmbiente
from app.arca.models import TicketAcceso, TipoComprobante, TipoDocumento, TipoIva
from app.core.config import settings
from app.models.certificado import Certificado
from app.models.usuario import Usuario


@pytest.mark.asyncio
class TestArcaAPIEndpoints:
    """Tests para endpoints de ARCA."""

    async def test_test_conexion_sin_autenticacion(self, client: AsyncClient):
        """Debe requerir autenticación."""
        response = await client.get("/api/arca/test-conexion")
        # Sin autenticación debería retornar 403 Forbidden
        assert response.status_code == 403

    @patch("app.api.arca.get_wsfe_client")
    async def test_test_conexion_exitoso(
        self, mock_get_client, client: AsyncClient, auth_headers: dict
    ):
        """Debe probar conexión exitosamente."""
        # Mock del cliente WSFEv1
        mock_wsfe = AsyncMock()
        mock_wsfe.fe_dummy.return_value = {
            "app_server": "OK",
            "db_server": "OK",
            "auth_server": "OK",
        }
        mock_get_client.return_value = mock_wsfe

        response = await client.get("/api/arca/test-conexion", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "servidor" in data

    @patch("app.api.arca.get_wsfe_client")
    async def test_get_tipos_comprobante(
        self, mock_get_client, client: AsyncClient, auth_headers: dict
    ):
        """Debe obtener tipos de comprobante."""
        # Mock del cliente WSFEv1
        mock_wsfe = AsyncMock()
        mock_wsfe.fe_param_get_tipos_cbte.return_value = [
            TipoComprobante(
                id=1, descripcion="Factura A", fecha_desde="20100101", fecha_hasta=None
            ),
            TipoComprobante(
                id=6, descripcion="Factura B", fecha_desde="20100101", fecha_hasta=None
            ),
        ]
        mock_get_client.return_value = mock_wsfe

        response = await client.get("/api/arca/tipos-comprobante", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        # Check if key exists before asserting value
        if "descripcion" in data[0]:
            assert data[0]["descripcion"] == "Factura A"
        elif "Desc" in data[0]:
            assert data[0]["Desc"] == "Factura A"
        else:
            # Print actual keys for debugging
            print(f"Available keys: {data[0].keys()}")
            raise AssertionError(
                f"Neither 'descripcion' nor 'Desc' found in response. Keys: {data[0].keys()}"
            )

    @patch("app.api.arca.get_wsfe_client")
    async def test_get_tipos_documento(
        self, mock_get_client, client: AsyncClient, auth_headers: dict
    ):
        """Debe obtener tipos de documento."""
        # Mock del cliente WSFEv1
        mock_wsfe = AsyncMock()
        mock_wsfe.fe_param_get_tipos_doc.return_value = [
            TipoDocumento(
                id=80, descripcion="CUIT", fecha_desde="20100101", fecha_hasta=None
            ),
            TipoDocumento(
                id=96, descripcion="DNI", fecha_desde="20100101", fecha_hasta=None
            ),
        ]
        mock_get_client.return_value = mock_wsfe

        response = await client.get("/api/arca/tipos-documento", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 80
        # Check either key name
        assert data[0].get("descripcion", data[0].get("Desc")) == "CUIT"

    @patch("app.api.arca.get_wsfe_client")
    async def test_get_tipos_iva(
        self, mock_get_client, client: AsyncClient, auth_headers: dict
    ):
        """Debe obtener tipos de IVA."""
        # Mock del cliente WSFEv1
        mock_wsfe = AsyncMock()
        mock_wsfe.fe_param_get_tipos_iva.return_value = [
            TipoIva(id=5, descripcion="21%", fecha_desde="20100101", fecha_hasta=None),
            TipoIva(
                id=4, descripcion="10.5%", fecha_desde="20100101", fecha_hasta=None
            ),
        ]
        mock_get_client.return_value = mock_wsfe

        response = await client.get("/api/arca/tipos-iva", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 5
        # Check either key name
        assert data[0].get("descripcion", data[0].get("Desc")) == "21%"

    @patch("app.api.arca.get_wsfe_client")
    async def test_get_ultimo_comprobante(
        self, mock_get_client, client: AsyncClient, auth_headers: dict
    ):
        """Debe obtener último comprobante autorizado."""
        # Mock del cliente WSFEv1
        mock_wsfe = AsyncMock()
        mock_wsfe.fe_comp_ultimo_autorizado.return_value = 100
        mock_get_client.return_value = mock_wsfe

        response = await client.get(
            "/api/arca/ultimo-comprobante/1/1", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ultimo_comprobante"] == 100
        assert data["proximo_comprobante"] == 101
        assert data["punto_venta"] == 1
        assert data["tipo_cbte"] == 1


@pytest.mark.asyncio
@patch("app.api.arca.WSFEv1Client")
@patch("app.api.arca.WSAAClient")
async def test_get_wsfe_client_usa_cuit_empresa_activa(
    mock_wsaa_class,
    mock_wsfe_class,
    db_session,
    test_empresa,
    test_user: Usuario,
    tmp_path,
    monkeypatch,
):
    """Debe autenticar y operar WSFE con el CUIT de la empresa activa."""
    monkeypatch.setattr(settings, "arca_env", ArcaAmbiente.HOMOLOGACION.value)

    cert_path = tmp_path / "certificado.crt"
    key_path = tmp_path / "certificado.key"
    cert_path.write_text("CRT", encoding="ascii")
    key_path.write_text("KEY", encoding="ascii")

    certificado = Certificado(
        nombre="Certificado QA",
        cuit="23318277559",
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2028, 1, 1),
        archivo_crt=str(cert_path),
        archivo_key=str(key_path),
        activo=True,
        ambiente=ArcaAmbiente.HOMOLOGACION.value,
        empresa_id=test_empresa.id,
    )
    db_session.add(certificado)
    await db_session.commit()

    ticket = TicketAcceso(
        token="token",
        sign="sign",
        expiracion=datetime.now(timezone.utc) + timedelta(hours=1),
        servicio="wsfe",
    )
    mock_wsaa = AsyncMock()
    mock_wsaa.login.return_value = ticket
    mock_wsaa_class.return_value = mock_wsaa

    wsfe_mock = AsyncMock()
    mock_wsfe_class.return_value = wsfe_mock

    client = await get_wsfe_client(db_session, test_user, test_empresa.id)

    assert client is wsfe_mock
    mock_wsaa.login.assert_awaited_once_with(
        cert_path=str(cert_path),
        key_path=str(key_path),
        cuit=test_empresa.cuit,
        servicio="wsfe",
    )
    mock_wsfe_class.assert_called_once_with(
        ambiente=ArcaAmbiente.HOMOLOGACION,
        ticket=ticket,
        cuit=test_empresa.cuit,
    )
