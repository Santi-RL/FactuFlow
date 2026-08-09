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
from app.models.empresa import Empresa
from app.models.elegibilidad_rece import (
    PuntoVentaElegibilidadReceActual,
    PuntoVentaElegibilidadReceRevision,
)
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario


async def _crear_punto_rece_verificado_arca(
    db_session,
    *,
    empresa: Empresa,
    usuario_id: int,
    numero: int = 1,
) -> PuntoVenta:
    """Crea un punto con acreditación RECE positiva solo para pruebas API."""
    hoy = date.today()
    ahora = datetime.utcnow()
    punto = PuntoVenta(
        numero=numero,
        nombre="Punto RECE ARCA sintético",
        sistema="Web Services",
        activo=True,
        es_webservice=True,
        bloqueado=False,
        revision_fiscal=1,
        empresa_id=empresa.id,
    )
    db_session.add(punto)
    await db_session.flush()
    revision = PuntoVentaElegibilidadReceRevision(
        empresa_id=empresa.id,
        punto_venta_id=punto.id,
        ambiente=settings.arca_env,
        revision=1,
        estado="verificado_rece",
        fuente="constancia_arca_atestada",
        evidencia_tipo="rece_aplicativo_web_services_v1",
        evidencia_sha256="a" * 64,
        clasificador_version="rece-v1-arca-api-test",
        empresa_cuit_snapshot=empresa.cuit,
        punto_venta_numero_snapshot=numero,
        punto_revision_fiscal=1,
        documento_emitido_en=hoy,
        vigente_hasta=hoy + timedelta(days=7),
        observado_en=ahora,
        verificado_en=ahora,
        creado_por_usuario_id=usuario_id,
        actor_usuario_id_snapshot=usuario_id,
        created_at=ahora,
    )
    db_session.add(revision)
    await db_session.flush()
    db_session.add(
        PuntoVentaElegibilidadReceActual(
            empresa_id=empresa.id,
            punto_venta_id=punto.id,
            ambiente=settings.arca_env,
            revision_actual_id=revision.id,
        )
    )
    await db_session.commit()
    return punto


@pytest.mark.asyncio
class TestArcaAPIEndpoints:
    """Tests para endpoints de ARCA."""

    async def test_test_conexion_sin_autenticacion(self, client: AsyncClient):
        """Debe requerir autenticación."""
        response = await client.get("/api/arca/test-conexion")
        # Sin autenticación debería retornar 403 Forbidden
        assert response.status_code == 403

    async def test_solicitar_cae_legacy_sin_autenticacion(self, client: AsyncClient):
        """Debe rechazar solicitudes CAE legacy sin autenticación."""
        response = await client.post("/api/arca/solicitar-cae", json={})

        assert response.status_code == 403

    @patch("app.api.arca.get_wsfe_client")
    async def test_solicitar_cae_legacy_deshabilitado_no_invoca_arca(
        self, mock_get_client, client: AsyncClient, auth_headers: dict
    ):
        """Debe bloquear el CAE directo sin construir un cliente WSFE."""
        response = await client.post(
            "/api/arca/solicitar-cae", json={}, headers=auth_headers
        )

        assert response.status_code == 410
        detail = response.json()["detail"]
        assert "Endpoint legacy deshabilitado" in detail
        assert "X-Idempotency-Key" in detail
        mock_get_client.assert_not_called()

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

    async def test_status_informa_certificado_del_ambiente_actual(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session,
        test_empresa,
        tmp_path,
        monkeypatch,
    ):
        """El estado ARCA debe mirar certificados del ambiente configurado."""
        monkeypatch.setattr(settings, "arca_env", ArcaAmbiente.PRODUCCION.value)
        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        certificado_homologacion = Certificado(
            nombre="Certificado homologacion",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2028, 1, 1),
            archivo_crt="homo.crt",
            archivo_key="homo.key",
            activo=True,
            ambiente=ArcaAmbiente.HOMOLOGACION.value,
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado_homologacion)
        await db_session.commit()

        response = await client.get("/api/arca/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["ambiente"] == "produccion"
        assert data["certificado_activo"] is False
        assert data["certificado_disponible"] is False

        (tmp_path / "prod.crt").write_text("CRT", encoding="ascii")
        (tmp_path / "prod.key").write_text("KEY", encoding="ascii")
        certificado_produccion = Certificado(
            nombre="Certificado produccion",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2028, 1, 1),
            archivo_crt="prod.crt",
            archivo_key="prod.key",
            activo=True,
            ambiente=ArcaAmbiente.PRODUCCION.value,
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado_produccion)
        await db_session.commit()

        response = await client.get("/api/arca/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["ambiente"] == "produccion"
        assert data["certificado_activo"] is True
        assert data["certificado_disponible"] is True
        assert data["certificado_nombre"] == "Certificado produccion"

    async def test_certificado_activo_sin_clave_no_habilita_arca_ni_expone_paths(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session,
        test_empresa,
        tmp_path,
        monkeypatch,
    ):
        """Debe fallar antes de WSAA sin exponer la ubicación de la clave."""
        monkeypatch.setattr(settings, "arca_env", ArcaAmbiente.PRODUCCION.value)
        monkeypatch.setattr(settings, "certs_path", str(tmp_path))
        (tmp_path / "presente.crt").write_text("CRT", encoding="ascii")
        certificado = Certificado(
            nombre="Certificado incompleto",
            cuit=test_empresa.cuit,
            fecha_emision=date(2026, 1, 1),
            fecha_vencimiento=date(2028, 1, 1),
            archivo_crt="presente.crt",
            archivo_key="faltante.key",
            activo=True,
            ambiente=ArcaAmbiente.PRODUCCION.value,
            empresa_id=test_empresa.id,
        )
        db_session.add(certificado)
        await db_session.commit()

        status_response = await client.get("/api/arca/status", headers=auth_headers)

        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["certificado_activo"] is True
        assert status_data["certificado_disponible"] is False

        with patch("app.api.arca.WSAAClient") as mock_wsaa_class:
            connection_response = await client.get(
                "/api/arca/test-conexion", headers=auth_headers
            )

        assert connection_response.status_code == 500
        detail = connection_response.json()["detail"]
        assert detail == (
            "El certificado activo no tiene disponibles sus archivos locales. "
            "Revisá la configuración de certificados."
        )
        assert str(tmp_path) not in detail
        assert "faltante.key" not in detail
        mock_wsaa_class.assert_not_called()

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
        self,
        mock_get_client,
        client: AsyncClient,
        auth_headers: dict,
        db_session,
        test_empresa,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Debe obtener último comprobante autorizado."""
        monkeypatch.setattr(settings, "arca_env", ArcaAmbiente.PRODUCCION.value)
        punto = await _crear_punto_rece_verificado_arca(
            db_session,
            empresa=test_empresa,
            usuario_id=test_user.id,
        )
        # Mock del cliente WSFEv1
        mock_wsfe = AsyncMock()
        mock_wsfe.fe_comp_ultimo_autorizado.return_value = 100
        mock_get_client.return_value = mock_wsfe

        response = await client.get(
            f"/api/arca/ultimo-comprobante/{punto.numero}/1", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ultimo_comprobante"] == 100
        assert data["proximo_comprobante"] == 101
        assert data["punto_venta"] == 1
        assert data["tipo_cbte"] == 1

    @pytest.mark.parametrize(
        "caso",
        ["no_verificado", "cruzado", "inexistente"],
    )
    async def test_ultimo_comprobante_falla_cerrado_antes_de_wsaa(
        self,
        caso: str,
        client: AsyncClient,
        auth_headers: dict,
        db_session,
        test_empresa,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PV inválido o sin RECE corta antes de WSAA/FEComp/FECAE."""
        monkeypatch.setattr(settings, "arca_env", ArcaAmbiente.PRODUCCION.value)
        llamadas = {"wsaa": 0, "fecomp": 0, "fecae": 0}
        numero = {
            "no_verificado": 51,
            "cruzado": 52,
            "inexistente": 53,
        }[caso]
        if caso == "no_verificado":
            db_session.add(
                PuntoVenta(
                    numero=numero,
                    nombre="Punto sin RECE",
                    sistema="Web Services",
                    activo=True,
                    es_webservice=True,
                    empresa_id=test_empresa.id,
                )
            )
        elif caso == "cruzado":
            otra_empresa = Empresa(
                razon_social="Empresa cruzada sintética",
                cuit="20304050607",
                condicion_iva="RI",
                domicilio="Domicilio sintético 456",
                localidad="Ciudad de prueba",
                provincia="Buenos Aires",
                codigo_postal="1000",
                inicio_actividades=date(2020, 1, 1),
            )
            db_session.add(otra_empresa)
            await db_session.flush()
            db_session.add(
                PuntoVenta(
                    numero=numero,
                    nombre="Punto de otro emisor",
                    sistema="Web Services",
                    activo=True,
                    es_webservice=True,
                    empresa_id=otra_empresa.id,
                )
            )
        await db_session.commit()

        class FakeWSFEClient:
            """Registra cualquier cruce indebido de la frontera ARCA."""

            async def fe_comp_ultimo_autorizado(self, punto_venta, tipo_cbte):
                """Registra una lectura FEComp indebida."""
                llamadas["fecomp"] += 1
                return 0

            async def fe_cae_solicitar(self, request):
                """Registra una solicitud FECAE indebida."""
                llamadas["fecae"] += 1
                raise AssertionError("El endpoint de lectura nunca solicita CAE")

        async def fake_get_wsfe_client(*args, **kwargs):
            """Representa la autenticación WSAA que debe quedar en cero."""
            llamadas["wsaa"] += 1
            return FakeWSFEClient()

        monkeypatch.setattr(
            "app.api.arca.get_wsfe_client",
            fake_get_wsfe_client,
        )

        response = await client.get(
            f"/api/arca/ultimo-comprobante/{numero}/6",
            headers=auth_headers,
        )

        assert response.status_code == 409, response.text
        assert response.json()["detail"]["categoria_error"] == (
            "elegibilidad_rece_no_verificada"
        )
        assert llamadas == {"wsaa": 0, "fecomp": 0, "fecae": 0}


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
    monkeypatch.setattr(settings, "certs_path", str(tmp_path))

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
