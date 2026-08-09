"""Tests de endpoints de comprobantes."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BloqueoPreautorizacionArca, settings
from app.models.certificado import Certificado
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.elegibilidad_rece import (
    PuntoVentaElegibilidadReceActual,
    PuntoVentaElegibilidadReceRevision,
    PuntoVentaGuardaEmisionRece,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import (
    EmitirComprobanteRequest,
    EmitirComprobanteResponse,
)
from app.services.facturacion_service import FacturacionService
from app.services.elegibilidad_rece_service import ElegibilidadReceService
from app.services.idempotencia_fiscal_service import (
    CreacionOperacionAmbiguaError,
    IdempotenciaFiscalService,
)


FECHA_FISCAL_PRUEBA = date(2026, 8, 9)
AHORA_FISCAL_PRUEBA = datetime(2026, 8, 9, 12, 0, 0)


@pytest.fixture(autouse=True)
def _configurar_ambiente_rece_productivo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fija el ambiente RECE requerido sin depender del entorno del runner."""
    monkeypatch.setattr(settings, "arca_env", "produccion")


def _crear_error_db_temporal(
    error_type: type[Exception],
) -> SQLAlchemyTimeoutError | OperationalError:
    """Construye un error transitorio sin depender de una base real."""
    if error_type is SQLAlchemyTimeoutError:
        return SQLAlchemyTimeoutError()
    return OperationalError(
        "SELECT dato_fiscal FROM comprobantes",
        {"empresa_id": 1},
        RuntimeError("base temporalmente no disponible"),
    )


def _idempotency_header(key: str = "idem-test-emitir") -> dict[str, str]:
    """Construye header de idempotencia para tests fiscales."""
    return {"X-Idempotency-Key": key}


def _request_emitir_base(test_empresa) -> dict:
    """Construye un request mínimo de emisión confirmada."""
    return {
        "empresa_id": test_empresa.id,
        "punto_venta_id": 1,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": FECHA_FISCAL_PRUEBA.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 99,
        "numero_documento": "0",
        "razon_social": "A CONSUMIDOR FINAL",
        "condicion_iva": "Consumidor Final",
        "items": [
            {
                "descripcion": "Servicio",
                "cantidad": 1,
                "unidad": "unidad",
                "precio_unitario": 1000,
                "iva_porcentaje": 0,
            }
        ],
    }


async def _crear_punto_rece_verificado_para_api(
    db: AsyncSession,
    *,
    empresa,
    usuario_id: int,
    numero: int = 1,
) -> PuntoVenta:
    """Crea punto, cabeza RECE vigente y certificado sintéticos para API feliz."""
    hoy = FECHA_FISCAL_PRUEBA
    ahora = AHORA_FISCAL_PRUEBA
    punto = PuntoVenta(
        numero=numero,
        nombre="Punto RECE API sintético",
        sistema="Web Services",
        activo=True,
        es_webservice=True,
        bloqueado=False,
        revision_fiscal=1,
        empresa_id=empresa.id,
    )
    certificado = Certificado(
        nombre="Certificado RECE API sintético",
        cuit=empresa.cuit,
        fecha_emision=hoy - timedelta(days=1),
        fecha_vencimiento=hoy + timedelta(days=30),
        archivo_crt="certificado-api-test.crt",
        archivo_key="certificado-api-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=empresa.id,
    )
    db.add_all([punto, certificado])
    await db.flush()
    revision = PuntoVentaElegibilidadReceRevision(
        empresa_id=empresa.id,
        punto_venta_id=punto.id,
        ambiente=settings.arca_env,
        revision=1,
        estado="verificado_rece",
        fuente="constancia_arca_atestada",
        evidencia_tipo="rece_aplicativo_web_services_v1",
        evidencia_sha256="a" * 64,
        clasificador_version="rece-v1-api-test",
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
    db.add(revision)
    await db.flush()
    db.add(
        PuntoVentaElegibilidadReceActual(
            empresa_id=empresa.id,
            punto_venta_id=punto.id,
            ambiente=settings.arca_env,
            revision_actual_id=revision.id,
        )
    )
    await db.commit()
    return punto


async def _request_emitir_rece(
    db: AsyncSession,
    *,
    empresa,
    usuario_id: int,
    numero: int = 1,
) -> tuple[dict, PuntoVenta]:
    """Construye un request individual con autoridad RECE moderna explícita."""
    punto = await _crear_punto_rece_verificado_para_api(
        db,
        empresa=empresa,
        usuario_id=usuario_id,
        numero=numero,
    )
    payload = _request_emitir_base(empresa)
    payload["punto_venta_id"] = punto.id
    return payload, punto


@pytest.mark.asyncio
async def test_pf19_bloquea_antes_de_operacion_y_sin_regla_exige_rece(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los gates PF-19/RECE fallan antes de crear ownership fiscal."""
    punto = PuntoVenta(
        numero=7,
        nombre="Web Services PF-19 sintético",
        sistema="Web Services",
        es_webservice=True,
        bloqueado=False,
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto)
    await db_session.commit()
    await db_session.refresh(punto)

    monkeypatch.setattr(settings, "arca_env", "produccion")
    monkeypatch.setattr(
        settings,
        "arca_bloqueos_preautorizacion",
        [
            BloqueoPreautorizacionArca(
                ambiente="produccion",
                empresa_id=test_empresa.id,
                punto_venta_id=punto.id,
                punto_venta=punto.numero,
                tipo_comprobante=6,
                motivo="elegibilidad_no_verificada",
            )
        ],
    )

    def arca_no_debe_inicializarse(*_args, **_kwargs):
        raise AssertionError("El aborto PF-19 no debe inicializar WSAA ni WSFE")

    monkeypatch.setattr(
        "app.services.facturacion_service.WSAAClient",
        arca_no_debe_inicializarse,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        arca_no_debe_inicializarse,
    )
    payload = _request_emitir_base(test_empresa)
    payload["punto_venta_id"] = punto.id
    headers = {
        **auth_headers,
        **_idempotency_header("idem-pf19-aborto-durable"),
    }

    primera = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )
    monkeypatch.setattr(settings, "arca_bloqueos_preautorizacion", [])
    replay = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )

    assert primera.status_code == 409, primera.text
    assert replay.status_code == 409, replay.text
    assert primera.json()["detail"]["categoria_error"] == (
        "punto_venta_bloqueado_preautorizacion"
    )
    assert replay.json()["detail"]["categoria_error"] == (
        "elegibilidad_rece_no_verificada"
    )
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-pf19-aborto-durable"
        )
    )
    assert operacion is None
    assert (
        await db_session.execute(select(IntentoEmisionFiscal))
    ).scalars().all() == []
    assert (await db_session.execute(select(Comprobante))).scalars().all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("campo_correcto", "campo_erroneo", "valor"),
    [
        ("moneda", "monedaa", "USD"),
        ("cotizacion", "cotizaccion", 2),
        ("guardar_cliente", "guardar_clientee", False),
        (
            "confirmacion_fecha_fiscal",
            "confirmacion_fecha_fiscaal",
            True,
        ),
    ],
)
async def test_emitir_comprobante_rechaza_claves_superiores_desconocidas(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    campo_correcto: str,
    campo_erroneo: str,
    valor: object,
) -> None:
    """Una errata fiscal debe fallar antes de idempotencia y del servicio."""
    llamadas_servicio = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas_servicio
        llamadas_servicio += 1
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=701,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=71,
            fecha=request.fecha_emision,
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    payload = _request_emitir_base(test_empresa)
    payload.pop(campo_correcto, None)
    payload[campo_erroneo] = valor
    idempotency_key = f"idem-extra-{campo_erroneo}"
    headers = {
        **auth_headers,
        **_idempotency_header(idempotency_key),
    }

    response = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 422, response.text
    assert llamadas_servicio == 0
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == idempotency_key
        )
    )
    assert operacion is None
    assert any(
        error["type"] == "extra_forbidden" and error["loc"] == ["body", campo_erroneo]
        for error in response.json()["detail"]
    )


def test_emitir_request_preserva_compatibilidad_transitoria_del_item_ui() -> None:
    """PF-03A no hace estricto el ítem que la UI aún envía con subtotal."""
    payload = _request_emitir_base(SimpleNamespace(id=1))
    payload["items"][0]["subtotal"] = 1000

    request = EmitirComprobanteRequest.model_validate(payload)

    assert request.items[0].descripcion == "Servicio"
    assert "subtotal" not in request.items[0].model_dump()


@pytest.mark.asyncio
async def test_emitir_comprobante_rechaza_concepto_faltante(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    """No debe completar Productos por defecto si falta concepto."""
    response = await client.post(
        "/api/comprobantes/emitir",
        headers=auth_headers,
        json={
            "empresa_id": test_empresa.id,
            "punto_venta_id": 1,
            "tipo_comprobante": 6,
            "fecha_emision": FECHA_FISCAL_PRUEBA.isoformat(),
            "tipo_documento": 96,
            "numero_documento": "12345678",
            "razon_social": "Cliente sin concepto",
            "condicion_iva": "Consumidor Final",
            "items": [
                {
                    "descripcion": "Servicio",
                    "cantidad": 1,
                    "unidad": "unidad",
                    "precio_unitario": 100,
                    "iva_porcentaje": 0,
                }
            ],
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_emitir_comprobante_exige_confirmacion_fecha_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    """No debe emitir por API si no se confirmó la fecha fiscal en la UI."""
    response = await client.post(
        "/api/comprobantes/emitir",
        headers=auth_headers,
        json={
            "empresa_id": test_empresa.id,
            "punto_venta_id": 1,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": FECHA_FISCAL_PRUEBA.isoformat(),
            "tipo_documento": 96,
            "numero_documento": "12345678",
            "razon_social": "Cliente sin confirmacion",
            "condicion_iva": "Consumidor Final",
            "items": [
                {
                    "descripcion": "Servicio",
                    "cantidad": 1,
                    "unidad": "unidad",
                    "precio_unitario": 100,
                    "iva_porcentaje": 0,
                }
            ],
        },
    )

    assert response.status_code == 400
    assert "confirmar la fecha fiscal" in response.json()["detail"]


@pytest.mark.asyncio
async def test_emitir_comprobante_reconciliacion_devuelve_409(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """La API debe exponer datos fiscales si ARCA autorizó y falló persistencia."""

    async def fake_emitir(self, request, **kwargs):
        await self.db.execute(
            update(OperacionIdempotente)
            .where(
                OperacionIdempotente.id == kwargs["operacion_id"],
                OperacionIdempotente.estado == "en_proceso",
                OperacionIdempotente.response_json.is_(None),
            )
            .values(estado="requiere_reconciliacion")
        )
        await self.db.commit()
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=12,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            total=Decimal("1000.00"),
            mensaje="ARCA autorizó el comprobante, pero FactuFlow no pudo guardarlo",
            errores=["No reintentes esta emisión"],
            requiere_reconciliacion=True,
            categoria_error="post_arca_persistencia",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
        numero=6,
    )

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header()},
        json=payload,
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["requiere_reconciliacion"] is True
    assert detail["categoria_error"] == "post_arca_persistencia"
    assert detail["cae"] == "12345678901234"
    assert detail["numero"] == 12


@pytest.mark.asyncio
async def test_emitir_comprobante_cambio_pre_arca_devuelve_fallo_terminal(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """El aborto anterior a FECAE conserva categoría y cierra la operación."""
    await _crear_punto_rece_verificado_para_api(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=78,
            fecha=request.fecha_emision,
            total=Decimal("1000.00"),
            mensaje="La numeración de ARCA cambió antes de solicitar el CAE",
            errores=["No se envió ninguna solicitud de CAE."],
            requiere_reconciliacion=False,
            categoria_error="numeracion_arca_cambio_pre_arca",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    key = "idem-preflight-numeracion"

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header(key)},
        json=_request_emitir_base(test_empresa),
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["requiere_reconciliacion"] is False
    assert detail["categoria_error"] == "numeracion_arca_cambio_pre_arca"
    assert "No se envió ninguna solicitud de CAE." in detail["errores"]

    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(OperacionIdempotente.idempotency_key == key)
    )
    assert operacion is not None
    assert operacion.estado == "fallido"
    assert operacion.response_json["categoria_error"] == (
        "numeracion_arca_cambio_pre_arca"
    )


@pytest.mark.asyncio
async def test_emitir_recupera_fallo_durable_al_cerrar_pre_arca(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un cierre fallido no publica respuesta ni deja guarda pre-ARCA activa."""
    punto = await _crear_punto_rece_verificado_para_api(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )
    consultas_numeracion = 0
    llamadas_fecae = 0
    cierres = 0

    class FakeWSFEClient:
        """Cambia la numeración después de reservar sin recibir FECAE."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva sin abrir red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Fuerza el aborto demostrablemente anterior a FECAE."""
            nonlocal consultas_numeracion
            consultas_numeracion += 1
            return 0 if consultas_numeracion == 1 else 1

        async def fe_cae_solicitar(self, arca_request):
            """Hace observable cualquier cruce indebido de la frontera."""
            nonlocal llamadas_fecae
            llamadas_fecae += 1
            raise AssertionError("No debe solicitar FECAE en este escenario")

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    cierre_original = ElegibilidadReceService.cerrar_pre_arca

    async def fallar_primer_cierre(self, guarda, **kwargs):
        nonlocal cierres
        cierres += 1
        if cierres == 1:
            raise RuntimeError("fallo sintético al confirmar cierre")
        return await cierre_original(self, guarda, **kwargs)

    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        FakeWSFEClient,
    )
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    monkeypatch.setattr(
        ElegibilidadReceService,
        "cerrar_pre_arca",
        fallar_primer_cierre,
    )
    payload = _request_emitir_base(test_empresa)
    payload["punto_venta_id"] = punto.id
    key = "idem-fallo-cierre-pre-arca-individual"

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header(key)},
        json=payload,
    )

    assert response.status_code == 503, response.text
    assert consultas_numeracion == 2
    assert llamadas_fecae == 0
    assert cierres == 1
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        operacion = await observador.scalar(
            select(OperacionIdempotente).where(
                OperacionIdempotente.idempotency_key == key
            )
        )
        assert operacion is not None
        guarda = await observador.scalar(
            select(PuntoVentaGuardaEmisionRece).where(
                PuntoVentaGuardaEmisionRece.operacion_id == operacion.id
            )
        )
        intento = await observador.scalar(
            select(IntentoEmisionFiscal).where(
                IntentoEmisionFiscal.operacion_id == operacion.id
            )
        )
        assert guarda is not None
        assert intento is not None
        assert guarda.fase == "cerrada_pre_arca"
        assert guarda.arca_iniciada_en is None
        assert intento.estado == "fallido_verificado"
        assert operacion.estado == "interrumpida_pre_arca"
        assert operacion.response_json is None


@pytest.mark.asyncio
async def test_emitir_comprobante_exige_idempotency_key(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    """No debe solicitar CAE si falta X-Idempotency-Key."""
    response = await client.post(
        "/api/comprobantes/emitir",
        headers=auth_headers,
        json=_request_emitir_base(test_empresa),
    )

    assert response.status_code == 400
    assert "X-Idempotency-Key" in response.json()["detail"]["mensaje"]


@pytest.mark.asyncio
async def test_emitir_comprobante_rechaza_emisor_ajeno_antes_de_servicio(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Un usuario común no debe solicitar CAE bajo un emisor ajeno."""
    segunda = test_empresa.__class__(
        razon_social="Empresa Ajena Emision S.A.",
        cuit="30444444446",
        condicion_iva="RI",
        domicilio="Av. Ajena 456",
        localidad="CABA",
        provincia="Buenos Aires",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(segunda)
    await db_session.commit()
    await db_session.refresh(segunda)
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=999,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=1,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={
            **auth_headers,
            **_idempotency_header("idem-emisor-ajeno"),
            "X-Empresa-Id": str(segunda.id),
        },
        json=_request_emitir_base(test_empresa),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "No tenés permiso para operar el emisor seleccionado"
    )
    assert llamadas == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyTimeoutError, OperationalError],
    ids=["timeout", "operational"],
)
async def test_emitir_comprobante_db_temporal_devuelve_503_sanitizado(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    error_type: type[Exception],
) -> None:
    """La API indica reintento sin filtrar statement, parámetros ni causa DB."""

    async def fake_emitir(self, request, **kwargs):
        raise _crear_error_db_temporal(error_type)

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header("idem-db-temporal")},
        json=payload,
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
    assert response.json() == {
        "detail": (
            "La base de datos está temporalmente no disponible. "
            "Intentá nuevamente en unos segundos."
        )
    }
    assert "SELECT dato_fiscal" not in response.text
    assert "empresa_id" not in response.text
    assert "base temporalmente no disponible" not in response.text
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-db-temporal"
        )
    )
    assert operacion is not None
    assert operacion.estado == "interrumpida_pre_arca"
    assert operacion.response_json is None
    intentos = (
        (
            await db_session.execute(
                select(IntentoEmisionFiscal).where(
                    IntentoEmisionFiscal.operacion_id == operacion.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert intentos == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyTimeoutError, OperationalError],
    ids=["timeout", "operational"],
)
async def test_replay_individual_pre_arca_reclama_y_continua_una_sola_vez(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    """La misma clave reanuda de inmediato tras una caída DB inequívoca pre-ARCA."""
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        if llamadas == 1:
            assert kwargs["fase_solicitud_arca"].iniciada is False
            raise _crear_error_db_temporal(error_type)
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=700,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=70,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 7, 21),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    headers = {**auth_headers, **_idempotency_header("idem-replay-pre-arca")}
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )

    primera = await client.post(
        "/api/comprobantes/emitir", headers=headers, json=payload
    )
    segunda = await client.post(
        "/api/comprobantes/emitir", headers=headers, json=payload
    )

    assert primera.status_code == 503, primera.text
    assert segunda.status_code == 200, segunda.text
    assert llamadas == 2
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-replay-pre-arca"
        )
    )
    assert operacion is not None
    assert operacion.estado == "finalizado"
    assert operacion.response_json["comprobante_id"] == 700


@pytest.mark.asyncio
async def test_replay_individual_pre_arca_cas_db_ambiguo_devuelve_409_sanitizado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un CAS ambiguo conserva el bloqueo y nunca se presenta como 503 reintentable."""
    llamadas = 0

    async def fail_primera(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        raise SQLAlchemyTimeoutError()

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fail_primera)
    headers = {**auth_headers, **_idempotency_header("idem-replay-cas-ambiguo")}
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )
    primera = await client.post(
        "/api/comprobantes/emitir", headers=headers, json=payload
    )
    assert primera.status_code == 503, primera.text

    async def fail_claim(self, operacion):
        raise OperationalError("COMMIT", {}, RuntimeError("resultado ambiguo"))

    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "reclamar_operacion_interrumpida_pre_arca",
        fail_claim,
    )
    replay = await client.post(
        "/api/comprobantes/emitir", headers=headers, json=payload
    )

    assert replay.status_code == 409
    assert "Retry-After" not in replay.headers
    assert replay.json()["detail"]["categoria_error"] == ("pre_arca_estado_bloqueado")
    assert "COMMIT" not in replay.text
    assert "resultado ambiguo" not in replay.text
    assert llamadas == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("stage_ambiguo", ["commit", "refresh"])
async def test_emitir_resuelve_creacion_ambigua_y_replay_reclama_misma_operacion(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    stage_ambiguo: str,
) -> None:
    """Commit o refresh ambiguo propio abre replay con la misma clave."""
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )
    fallo_inyectado = False
    if stage_ambiguo == "commit":
        original_commit = db_session.commit

        async def commit_ambiguo():
            nonlocal fallo_inyectado
            await original_commit()
            if not fallo_inyectado:
                fallo_inyectado = True
                raise SQLAlchemyTimeoutError()

        monkeypatch.setattr(db_session, "commit", commit_ambiguo)
    else:
        original_refresh = db_session.refresh

        async def refresh_ambiguo(instance, *args, **kwargs):
            nonlocal fallo_inyectado
            await original_refresh(instance, *args, **kwargs)
            if isinstance(instance, OperacionIdempotente) and not fallo_inyectado:
                fallo_inyectado = True
                raise SQLAlchemyTimeoutError()

        monkeypatch.setattr(db_session, "refresh", refresh_ambiguo)

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=701,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=71,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 7, 21),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    headers = {**auth_headers, **_idempotency_header("idem-create-ambiguo")}

    primera = await client.post(
        "/api/comprobantes/emitir", headers=headers, json=payload
    )
    segunda = await client.post(
        "/api/comprobantes/emitir", headers=headers, json=payload
    )

    assert primera.status_code == 503, primera.text
    assert segunda.status_code == 200, segunda.text
    assert fallo_inyectado is True
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-create-ambiguo"
        )
    )
    assert operacion is not None
    assert operacion.estado == "finalizado"


@pytest.mark.asyncio
async def test_emitir_lookup_temporal_no_interrumpe_operacion_viva(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una caída del lookup no reclama una operación viva de otra request."""
    payload = _request_emitir_base(test_empresa)
    request = EmitirComprobanteRequest.model_validate(payload)
    idempotencia = IdempotenciaFiscalService(db_session)
    payload_hash = idempotencia.calcular_payload_hash(
        idempotencia.payload_sin_confirmacion_duplicado(request.model_dump(mode="json"))
    )
    operacion = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=None,
        idempotency_key="idem-lookup-vivo",
        tipo_operacion="emitir_comprobante",
        payload_hash=payload_hash,
        lote_id=None,
        estado="en_proceso",
    )
    db_session.add(operacion)
    await db_session.commit()
    await db_session.refresh(operacion)
    original_lookup = IdempotenciaFiscalService._obtener_operacion
    llamadas_arca = 0

    async def fail_lookup(self, empresa_id, idempotency_key):
        raise SQLAlchemyTimeoutError()

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas_arca
        llamadas_arca += 1
        raise AssertionError("No debe emitir desde una operación viva")

    monkeypatch.setattr(IdempotenciaFiscalService, "_obtener_operacion", fail_lookup)
    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    headers = {**auth_headers, **_idempotency_header("idem-lookup-vivo")}

    primera = await client.post(
        "/api/comprobantes/emitir", headers=headers, json=payload
    )
    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "_obtener_operacion",
        original_lookup,
    )
    segunda = await client.post(
        "/api/comprobantes/emitir", headers=headers, json=payload
    )

    assert primera.status_code == 503, primera.text
    assert segunda.status_code == 409, segunda.text
    assert segunda.json()["detail"]["categoria_error"] == "idempotencia_en_proceso"
    await db_session.refresh(operacion)
    assert operacion.estado == "en_proceso"
    assert operacion.response_json is None
    assert llamadas_arca == 0


@pytest.mark.asyncio
async def test_replay_individual_no_sobrescribe_terminal_concurrente(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El CAS del replay conserva un resultado terminal publicado en carrera."""
    punto = await _crear_punto_rece_verificado_para_api(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )
    payload = _request_emitir_base(test_empresa)
    payload.update(
        {
            "punto_venta_id": punto.id,
            "fecha_emision": "2026-08-09",
        }
    )
    request = EmitirComprobanteRequest.model_validate(payload)
    elegibilidad = ElegibilidadReceService(db_session)
    contexto = await elegibilidad.exigir_contexto_preautorizacion(
        empresa_id=test_empresa.id,
        punto_venta_id=punto.id,
        ambiente=settings.arca_env,
        tipo_comprobante=request.tipo_comprobante,
        bloquear=True,
    )
    idempotencia = IdempotenciaFiscalService(db_session)
    payload_hash = idempotencia.calcular_payload_hash(
        idempotencia.payload_sin_confirmacion_duplicado(request.model_dump(mode="json"))
    )
    operacion, creada = await idempotencia.obtener_o_crear_operacion(
        empresa_id=test_empresa.id,
        usuario_id=test_user.id,
        idempotency_key="idem-replay-terminal-concurrente",
        tipo_operacion="emitir_comprobante",
        payload_hash=payload_hash,
        contextos_rece=[contexto],
    )
    assert creada is True
    operacion_id = int(operacion.id)
    terminal = EmitirComprobanteResponse(
        exito=True,
        comprobante_id=810,
        tipo_comprobante=request.tipo_comprobante,
        punto_venta=punto.numero,
        numero=81,
        fecha=request.fecha_emision,
        cae="12345678901234",
        cae_vencimiento=date(2026, 8, 31),
        total=Decimal("1000.00"),
        mensaje="Resultado terminal concurrente",
    )
    reconstruida = terminal.model_copy(
        update={
            "comprobante_id": 820,
            "numero": 82,
            "mensaje": "Resultado reconstruido obsoleto",
        }
    )
    llamadas_emision = 0

    async def resolver_y_publicar_terminal(self, operacion_id_argumento):
        assert operacion_id_argumento == operacion_id
        await self.db.execute(
            update(OperacionIdempotente)
            .where(
                OperacionIdempotente.id == operacion_id,
                OperacionIdempotente.estado == "en_proceso",
                OperacionIdempotente.response_json.is_(None),
            )
            .values(
                estado="finalizado",
                response_json=terminal.model_dump(mode="json"),
            )
        )
        await self.db.commit()
        return reconstruida

    async def no_emitir(self, request, **kwargs):
        nonlocal llamadas_emision
        llamadas_emision += 1
        raise AssertionError("El replay no debe volver a solicitar CAE")

    monkeypatch.setattr(
        FacturacionService,
        "resolver_operacion_idempotente_incompleta",
        resolver_y_publicar_terminal,
    )
    monkeypatch.setattr(FacturacionService, "emitir_comprobante", no_emitir)

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={
            **auth_headers,
            **_idempotency_header("idem-replay-terminal-concurrente"),
        },
        json=payload,
    )

    assert response.status_code == 503, response.text
    assert llamadas_emision == 0
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        durable = await observador.get(OperacionIdempotente, operacion_id)
        assert durable is not None
        assert durable.estado == "finalizado"
        assert durable.response_json == terminal.model_dump(mode="json")


@pytest.mark.asyncio
async def test_emitir_creacion_ambigua_mismatch_no_muta_operacion(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La recuperación ambigua rechaza otro payload y no muta su operación."""
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )

    async def crear_otro_payload(self, **kwargs):
        operacion = OperacionIdempotente(
            empresa_id=kwargs["empresa_id"],
            usuario_id=kwargs["usuario_id"],
            idempotency_key=kwargs["idempotency_key"],
            tipo_operacion=kwargs["tipo_operacion"],
            payload_hash="hash-de-otro-payload",
            lote_id=None,
            estado="en_proceso",
        )
        self.db.add(operacion)
        await self.db.commit()
        raise CreacionOperacionAmbiguaError(SQLAlchemyTimeoutError())

    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "obtener_o_crear_operacion",
        crear_otro_payload,
    )
    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header("idem-create-mismatch")},
        json=payload,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["categoria_error"] == ("pre_arca_estado_bloqueado")
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-create-mismatch"
        )
    )
    assert operacion is not None
    assert operacion.estado == "en_proceso"
    assert operacion.payload_hash == "hash-de-otro-payload"


@pytest.mark.asyncio
async def test_emitir_comprobante_integrity_error_conserva_500(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un conflicto de integridad no se clasifica como indisponibilidad temporal."""

    async def fake_emitir(self, request, **kwargs):
        raise IntegrityError(
            "INSERT INTO comprobantes",
            {"cae": "dato-interno"},
            RuntimeError("conflicto interno"),
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header("idem-integrity")},
        json=payload,
    )

    assert response.status_code == 500
    assert "Retry-After" not in response.headers
    assert response.json()["detail"]["mensaje"] == (
        "Error interno al emitir comprobante"
    )
    assert "INSERT INTO" not in response.text
    assert "dato-interno" not in response.text
    assert "conflicto interno" not in response.text


@pytest.mark.asyncio
async def test_emitir_comprobante_sanitiza_errores_inesperados(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """Un error inesperado se registra sin exponer detalles internos por HTTP."""

    async def fake_emitir(self, request, **kwargs):
        raise RuntimeError("detalle interno secreto; ruta C:\\certs\\privada.key")

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header("idem-error-sanitizado")},
        json=payload,
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["mensaje"] == "Error interno al emitir comprobante"
    assert "secreto" not in response.text
    assert "privada.key" not in response.text


@pytest.mark.asyncio
async def test_emitir_comprobante_excepcion_post_arca_persiste_replay_409(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una excepción inesperada post-ARCA se guarda y no vuelve a emitir."""
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        """Cruza la frontera ARCA y simula un fallo interno posterior."""
        nonlocal llamadas
        llamadas += 1
        kwargs["fase_solicitud_arca"].marcar_iniciada()
        raise RuntimeError("detalle interno secreto; ruta C:\\certs\\privada.key")

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    headers = {
        **auth_headers,
        **_idempotency_header("idem-excepcion-post-arca"),
    }
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
    )

    primera = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )
    segunda = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )

    assert primera.status_code == 409
    assert segunda.status_code == 409
    assert llamadas == 1
    for response in (primera, segunda):
        detail = response.json()["detail"]
        assert detail["requiere_reconciliacion"] is True
        assert detail["categoria_error"] == "arca_respuesta_incierta"
        assert "otra clave" in detail["errores"][0]
        assert "secreto" not in response.text
        assert "privada.key" not in response.text

    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-excepcion-post-arca"
        )
    )
    assert operacion is not None
    assert operacion.estado == "requiere_reconciliacion"
    assert operacion.response_json["categoria_error"] == "arca_respuesta_incierta"


@pytest.mark.asyncio
async def test_emitir_comprobante_fallo_guardando_respuesta_post_arca_persiste_409(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un fallo idempotente post-CAE conserva CAE y bloquea el replay."""
    llamadas_emision = 0
    llamadas_guardado = 0
    guardar_original = IdempotenciaFiscalService.guardar_respuesta_operacion_cas

    async def fake_emitir(self, request, **kwargs):
        """Devuelve una autorización después de marcar la frontera ARCA."""
        nonlocal llamadas_emision
        llamadas_emision += 1
        kwargs["fase_solicitud_arca"].marcar_iniciada()
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=101,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=22,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 7, 23),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    async def fallar_primer_guardado(self, **kwargs):
        """Falla una vez y permite persistir el fallback incierto."""
        nonlocal llamadas_guardado
        llamadas_guardado += 1
        if llamadas_guardado == 1:
            raise RuntimeError("secreto privada.key")
        return await guardar_original(self, **kwargs)

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "guardar_respuesta_operacion_cas",
        fallar_primer_guardado,
    )
    headers = {
        **auth_headers,
        **_idempotency_header("idem-fallo-respuesta-post-arca"),
    }
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
        numero=6,
    )

    primera = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )
    segunda = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )

    assert primera.status_code == 409
    assert segunda.status_code == 409
    assert llamadas_emision == 1
    assert llamadas_guardado == 2
    for response in (primera, segunda):
        detail = response.json()["detail"]
        assert detail["requiere_reconciliacion"] is True
        assert detail["categoria_error"] == "post_arca_persistencia"
        assert detail["cae"] == "12345678901234"
        assert detail["numero"] == 22
        assert "secreto" not in response.text
        assert "privada.key" not in response.text

    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-fallo-respuesta-post-arca"
        )
    )
    assert operacion is not None
    assert operacion.estado == "requiere_reconciliacion"
    assert operacion.response_json["cae"] == "12345678901234"


@pytest.mark.asyncio
async def test_emitir_comprobante_replay_misma_clave_no_reemite(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """La misma clave y payload debe devolver la respuesta persistida."""
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=100 + llamadas,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=20 + llamadas,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    headers = {**auth_headers, **_idempotency_header("idem-replay")}
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
        numero=6,
    )

    primera = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )
    segunda = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert llamadas == 1
    assert segunda.json()["numero"] == primera.json()["numero"]
    assert segunda.json()["comprobante_id"] == primera.json()["comprobante_id"]


@pytest.mark.asyncio
async def test_emitir_comprobante_misma_clave_payload_distinto_devuelve_409(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
):
    """Una clave reutilizada con otro payload debe fallar antes de emitir."""

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=101,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=21,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    headers = {**auth_headers, **_idempotency_header("idem-conflicto")}
    payload, _ = await _request_emitir_rece(
        db_session,
        empresa=test_empresa,
        usuario_id=test_user.id,
        numero=6,
    )

    primera = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )
    payload_distinto = {**payload, "observaciones": "Otro dato fiscal"}
    segunda = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload_distinto,
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 409
    assert "otros datos" in segunda.json()["detail"]["mensaje"]


@pytest.mark.asyncio
async def test_get_comprobante_detalle_con_items(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """Debe devolver el detalle de un comprobante con items sin error 500."""
    cliente = Cliente(
        razon_social="Cliente API Test",
        tipo_documento="DNI",
        numero_documento="12345678",
        condicion_iva="CF",
        empresa_id=test_empresa.id,
    )
    punto_venta = PuntoVenta(
        numero=5,
        nombre="PV Test",
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([cliente, punto_venta])
    await db_session.flush()

    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=1,
        fecha_emision=date(2026, 3, 9),
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae="12345678901234",
        cae_vencimiento=date(2026, 3, 19),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1.000000"),
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        cliente_id=cliente.id,
    )
    db_session.add(comprobante)
    await db_session.flush()

    item = ComprobanteItem(
        codigo="ITEM-1",
        descripcion="Producto API Test",
        cantidad=Decimal("1.00"),
        unidad="unidades",
        precio_unitario=Decimal("1000.00"),
        descuento_porcentaje=Decimal("0.00"),
        iva_porcentaje=Decimal("21.00"),
        subtotal=Decimal("1000.00"),
        orden=1,
        comprobante_id=comprobante.id,
    )
    db_session.add(item)
    await db_session.commit()

    response = await client.get(
        f"/api/comprobantes/{comprobante.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == comprobante.id
    assert data["cliente_nombre"] == "Cliente API Test"
    assert data["punto_venta_numero"] == 5
    assert len(data["items"]) == 1
    assert data["items"][0]["descripcion"] == "Producto API Test"


@pytest.mark.asyncio
async def test_proximo_numero_rechaza_punto_no_usable(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """No debe consultar ARCA para puntos que no son usables por FactuFlow."""
    punto_venta = PuntoVenta(
        numero=998,
        nombre="Factuweb",
        sistema="Factuweb (Imprenta) - Monotributo",
        es_webservice=False,
        bloqueado=False,
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.commit()

    response = await client.get(
        "/api/comprobantes/proximo-numero/998/6",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "no está habilitado" in response.json()["detail"]


@pytest.mark.asyncio
async def test_proximo_numero_expone_historia_externa_sin_bloquear_emision(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """El endpoint distingue historia externa de un intento propio incierto."""
    punto_venta = PuntoVenta(
        numero=5,
        nombre="Web Services",
        es_webservice=True,
        bloqueado=False,
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.commit()

    async def fake_diagnostico(self, empresa_id, punto_venta_id, tipo):
        """Devuelve un desfase legítimo sin conectarse con ARCA."""
        assert empresa_id == test_empresa.id
        assert punto_venta_id == punto_venta.id
        assert tipo == 6
        return SimpleNamespace(
            ultimo_local=76,
            ultimo_arca=77,
            proximo_local=77,
            proximo_arca=78,
            proximo_numero=78,
            estado="arca_adelantada",
            emision_habilitada=True,
        )

    monkeypatch.setattr(
        FacturacionService,
        "obtener_diagnostico_numeracion",
        fake_diagnostico,
    )

    response = await client.get(
        "/api/comprobantes/proximo-numero/5/6",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "punto_venta": 5,
        "tipo_comprobante": 6,
        "ultimo_local": 76,
        "ultimo_arca": 77,
        "proximo_local": 77,
        "proximo_arca": 78,
        "proximo_numero": 78,
        "estado": "arca_adelantada",
        "emision_habilitada": True,
        "advertencia": (
            "ARCA registra comprobantes anteriores que todavía no están en "
            "FactuFlow. La emisión continuará con el siguiente número de ARCA; "
            "la reconstrucción histórica es opcional y se realizará en un paso "
            "posterior."
        ),
    }
