"""Tests de endpoints de comprobantes."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import (
    EmitirComprobanteRequest,
    EmitirComprobanteResponse,
)
from app.services.facturacion_service import FacturacionService
from app.services.idempotencia_fiscal_service import (
    CreacionOperacionAmbiguaError,
    IdempotenciaFiscalService,
)


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
        "fecha_emision": date.today().isoformat(),
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
            "fecha_emision": date.today().isoformat(),
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
            "fecha_emision": date.today().isoformat(),
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
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """La API debe exponer datos fiscales si ARCA autorizó y falló persistencia."""

    async def fake_emitir(self, request, **kwargs):
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

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header()},
        json=_request_emitir_base(test_empresa),
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["requiere_reconciliacion"] is True
    assert detail["categoria_error"] == "post_arca_persistencia"
    assert detail["cae"] == "12345678901234"
    assert detail["numero"] == 12


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
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    error_type: type[Exception],
) -> None:
    """La API indica reintento sin filtrar statement, parámetros ni causa DB."""

    async def fake_emitir(self, request, **kwargs):
        raise _crear_error_db_temporal(error_type)

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header("idem-db-temporal")},
        json=_request_emitir_base(test_empresa),
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
    payload = _request_emitir_base(test_empresa)

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
    test_empresa,
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
    payload = _request_emitir_base(test_empresa)
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
    monkeypatch: pytest.MonkeyPatch,
    stage_ambiguo: str,
) -> None:
    """Commit o refresh ambiguo propio abre replay con la misma clave."""
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
    payload = _request_emitir_base(test_empresa)

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
async def test_emitir_creacion_ambigua_mismatch_no_muta_operacion(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La recuperación ambigua rechaza otro payload y no muta su operación."""

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
        json=_request_emitir_base(test_empresa),
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
    test_empresa,
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

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header("idem-integrity")},
        json=_request_emitir_base(test_empresa),
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
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Un error inesperado se registra sin exponer detalles internos por HTTP."""

    async def fake_emitir(self, request, **kwargs):
        raise RuntimeError(
            "postgresql://usuario:secreto@db/factuflow C:\\certs\\privada.key"
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header("idem-error-sanitizado")},
        json=_request_emitir_base(test_empresa),
    )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["mensaje"] == "Error interno al emitir comprobante"
    assert "secreto" not in response.text
    assert "privada.key" not in response.text


@pytest.mark.asyncio
async def test_emitir_comprobante_replay_misma_clave_no_reemite(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
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
    payload = _request_emitir_base(test_empresa)

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
    test_empresa,
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
    payload = _request_emitir_base(test_empresa)

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
