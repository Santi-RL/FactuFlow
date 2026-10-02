"""Tests para emision masiva de comprobantes."""

import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from io import BytesIO
import json
from zipfile import ZipFile
from xml.etree import ElementTree
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from openpyxl import Workbook, load_workbook
from openpyxl.utils.datetime import to_excel
from sqlalchemy import JSON, delete, event, func, inspect, null, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.arca.exceptions import (
    ArcaErrorGlobalEstructurado,
    ArcaServiceError,
    CabeceraRespuestaFecae,
    MensajeArcaEstructurado,
)
from app.arca.models import CAEResponse
from app.arca.models import ComprobanteResponse as ArcaComprobanteResponse
from app.core.config import settings
from app.models.certificado import Certificado
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.empresa import Empresa
from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceActual,
    PuntoVentaElegibilidadReceRevision,
    PuntoVentaGuardaEmisionRece,
)
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteEvento,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.idempotencia_fiscal import (
    IntentoEmisionFiscal,
    LoteDuplicadoCoincidencia,
    LoteDuplicadoCoincidenciaMiembro,
    LoteDuplicadoEvidencia,
    OperacionIdempotente,
)
from app.models.punto_venta import PuntoVenta
from app.models.usuario_emisor_acceso import UsuarioEmisorAcceso
from app.schemas.comprobante import EmitirComprobanteRequest, EmitirComprobanteResponse
from app.schemas.lote_comprobante import (
    LoteComprobanteResponse,
    LoteComprobanteSeguimientoResponse,
    LoteProcesamientoResponse,
    LoteReconciliacionExternaItem,
)
from app.services import duplicados_lotes_service as duplicados_lotes_module
from app.services.facturacion_service import FacturacionService
from app.services.lote_comprobantes_service import (
    LoteComprobanteConflictoError,
    LoteComprobanteError,
    LoteComprobantesService,
    LoteDuplicadosEvidenciaCambioError,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.duplicados_lotes_service import (
    DuplicadosLoteError,
    DuplicadosLotePreflightCambioError,
    DuplicadosLotesService,
    canonicalizar_payload_fiscal_v2,
    identidad_entrada_v2,
    material_grupo_v2,
)
from app.services.elegibilidad_rece_service import (
    ContextoElegibilidadRece,
    ElegibilidadReceService,
)
from app.services.lote_worker import LoteWorker, get_lote_worker_status
from app.services.puntos_venta_arca_service import PuntosVentaArcaService


@pytest.mark.parametrize(
    ("tipo", "numero", "nombre", "tiene_nombre", "tiene_documento"),
    [
        (99, "0", "Consumidor Final", False, False),
        (99, "000", " A   CONSUMIDOR FINAL ", False, False),
        (96, "", "  María   Pérez ", True, False),
        (96, "30.000.001", "Otro nombre", True, True),
        (80, "00000000000", "Empresa sintética", True, False),
        (80, "20123456789", "Empresa sintética", True, False),
        (80, "20-40937847-2", "Empresa sintética", True, True),
        (777, "30000001", "", False, False),
    ],
)
def test_identidad_entrada_v2_distingue_anonimos_y_receptores_definidos(
    tipo,
    numero,
    nombre,
    tiene_nombre,
    tiene_documento,
):
    identidad = identidad_entrada_v2(
        tipo_documento=tipo,
        numero_documento=numero,
        razon_social=nombre,
    )

    assert bool(identidad["nombre_hash"]) is tiene_nombre
    assert bool(identidad["documento_hash"]) is tiene_documento
    assert identidad["nombre_original"] == (nombre.strip() or None)


def _request_duplicados_v2(**updates) -> EmitirComprobanteRequest:
    payload = {
        "empresa_id": 1,
        "punto_venta_id": 1,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": "2026-08-09",
        "confirmacion_fecha_fiscal": True,
        "confirmacion_duplicado_logico": False,
        "tipo_documento": 96,
        "numero_documento": "30000001",
        "razon_social": "Persona Sintética",
        "condicion_iva": "CF",
        "domicilio": "Calle de prueba 123",
        "moneda": "PES",
        "cotizacion": "1",
        "observaciones": "Operación sintética",
        "guardar_cliente": False,
        "items": [
            {
                "codigo": "A",
                "descripcion": "Servicio A",
                "cantidad": "1.00",
                "unidad": "unidad",
                "precio_unitario": "100.0000",
                "descuento_porcentaje": "0",
                "iva_porcentaje": "21.0",
                "orden": 9,
            },
            {
                "codigo": "B",
                "descripcion": "Servicio B",
                "cantidad": "2",
                "unidad": "unidad",
                "precio_unitario": "50",
                "descuento_porcentaje": "0",
                "iva_porcentaje": "21",
                "orden": 1,
            },
        ],
        "comprobantes_asociados": [],
    }
    payload.update(updates)
    return EmitirComprobanteRequest.model_validate(payload)


def test_contenido_fiscal_v2_ignora_orden_pero_preserva_multiplicidad_y_campos():
    request = _request_duplicados_v2()
    reversed_request = request.model_copy(
        update={
            "items": list(reversed(request.items)),
            "confirmacion_duplicado_logico": True,
        }
    )
    base = canonicalizar_payload_fiscal_v2(request, punto_venta_numero=1)
    reordered = canonicalizar_payload_fiscal_v2(reversed_request, punto_venta_numero=1)

    assert base == reordered
    duplicated = request.model_copy(
        update={"items": [*request.items, request.items[0]]}
    )
    assert canonicalizar_payload_fiscal_v2(duplicated, punto_venta_numero=1) != base
    assert canonicalizar_payload_fiscal_v2(
        request.model_copy(
            update={"moneda": "USD", "cotizacion": Decimal("1.000000001")}
        ),
        punto_venta_numero=1,
    ) != canonicalizar_payload_fiscal_v2(
        request.model_copy(
            update={"moneda": "USD", "cotizacion": Decimal("1.000000002")}
        ),
        punto_venta_numero=1,
    )
    assert canonicalizar_payload_fiscal_v2(request, punto_venta_numero=1) != (
        canonicalizar_payload_fiscal_v2(request, punto_venta_numero=2)
    )


def test_material_grupo_v2_no_desborda_importes_admitidos_ni_redondea_cotizacion():
    request = _request_duplicados_v2(
        moneda="USD",
        cotizacion=Decimal("123456789.123456789123"),
    )
    identity = identidad_entrada_v2(
        tipo_documento=96,
        numero_documento="30000001",
        razon_social="Persona Sintética",
    )

    material = material_grupo_v2(
        payload=request.model_dump(mode="json"),
        punto_venta_numero=1,
        total=Decimal("9999999999.99"),
        identidad=identity,
    )

    assert material["total_centavos"] == 999999999999
    assert material["cotizacion_duplicados"] == "123456789.123456789123"


@pytest.mark.asyncio
@pytest.mark.parametrize("core_update", [False, True])
async def test_coordinador_v2_rechaza_transaccion_ajena_incluso_flushed(
    db_session: AsyncSession,
    test_empresa,
    core_update: bool,
):
    nombre_original = test_empresa.razon_social
    if core_update:
        await db_session.execute(
            update(Empresa)
            .where(Empresa.id == test_empresa.id)
            .values(razon_social="Cambio ajeno por Core")
        )
    else:
        test_empresa.razon_social = "Cambio ajeno por ORM"
        await db_session.flush()

    with pytest.raises(DuplicadosLoteError, match="frontera transaccional limpia"):
        await DuplicadosLotesService(db_session).evaluar_y_reservar(
            operacion_id=999,
            lote_id=999,
            empresa_id=test_empresa.id,
            estados={"validado"},
            grupo_ids=None,
            aceptacion_recibida=None,
            solicitante_nombre="Operador sintético",
            reservar=True,
            ambiente="homologacion",
        )

    assert db_session.in_transaction()
    await db_session.rollback()
    await db_session.refresh(test_empresa)
    assert test_empresa.razon_social == nombre_original


def _modificar_receptores_excel_multi(
    excel: bytes,
    *,
    tipo: str,
    numeros: list[str],
    nombres: list[str],
    condicion: str,
) -> bytes:
    workbook = load_workbook(BytesIO(excel))
    sheet = workbook["Comprobantes"]
    for index, (numero, nombre) in enumerate(zip(numeros, nombres), start=2):
        sheet.cell(row=index, column=7).value = tipo
        sheet.cell(row=index, column=8).value = numero
        sheet.cell(row=index, column=9).value = nombre
        sheet.cell(row=index, column=10).value = condicion
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


@pytest.mark.asyncio
async def test_control_v2_silencia_anonimos_internos_y_tipifica_receptor_identificado(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    anonymous_excel = _modificar_receptores_excel_multi(
        _build_lote_excel_multi_grupo(test_empresa.cuit),
        tipo="CI",
        numeros=["", ""],
        nombres=["Consumidor Final", "A consumidor final"],
        condicion="Consumidor Final",
    )
    anonymous = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "anonimos.xlsx",
                anonymous_excel,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert anonymous.status_code == 200, anonymous.text
    summary = await client.get(
        f"/api/lotes-comprobantes/{anonymous.json()['lote']['id']}/resumen",
        headers=auth_headers,
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["control_duplicados"]["estado"] == "sin_coincidencias"
    assert summary.json()["control_duplicados"]["tipos_coincidencia"] == []

    identified_excel = _modificar_receptores_excel_multi(
        _build_lote_excel_multi_grupo(test_empresa.cuit),
        tipo="DNI",
        numeros=["30000011", "30000011"],
        nombres=["Persona Uno", "Persona Dos"],
        condicion="Consumidor Final",
    )
    identified = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "identificados.xlsx",
                identified_excel,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert identified.status_code == 200, identified.text
    summary = await client.get(
        f"/api/lotes-comprobantes/{identified.json()['lote']['id']}/resumen",
        headers=auth_headers,
    )
    control = summary.json()["control_duplicados"]
    assert control["estado"] == "requiere_confirmacion"
    assert control["tipos_coincidencia"] == ["interna_receptor"]
    detail = await client.get(
        f"/api/lotes-comprobantes/{identified.json()['lote']['id']}/coincidencias",
        params={"evidencia_id": control["evidencia_id"]},
        headers=auth_headers,
    )
    assert detail.status_code == 200, detail.text
    detail_items = detail.json()["items"]
    assert {item["tipo_coincidencia"] for item in detail_items} == {"interna_receptor"}
    assert all(item["lote_anterior_id"] is None for item in detail_items)
    assert all(item["comprobante_actual_ref"] for item in detail_items)


@pytest.mark.asyncio
async def test_aceptacion_v2_es_aleatoria_reexpedible_y_ligada_a_misma_operacion(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    excel = _modificar_receptores_excel_multi(
        _build_lote_excel_multi_grupo(test_empresa.cuit),
        tipo="DNI",
        numeros=["30000021", "30000021"],
        nombres=["Persona Sintética", "Persona Sintética"],
        condicion="Consumidor Final",
    )
    validation = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "aceptacion-v2.xlsx",
                excel,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validation.status_code == 200, validation.text
    lote_id = validation.json()["lote"]["id"]
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="pf13-aceptacion-v2",
    )

    first = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )
    assert first.status_code == 409, first.text
    first_detail = first.json()["detail"]
    acceptance_id = first_detail["aceptacion_id"]
    evidence_id = first_detail["control_duplicados"]["evidencia_id"]
    assert acceptance_id.startswith("v2.")
    assert acceptance_id != evidence_id
    page = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/coincidencias",
        params={"evidencia_id": evidence_id, "page": 2, "per_page": 1},
        headers=auth_headers,
    )
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 4
    assert page.json()["total_pages"] == 4
    assert len(page.json()["items"]) == 1

    repeated = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )
    assert repeated.status_code == 409, repeated.text
    assert repeated.json()["detail"]["aceptacion_id"] == acceptance_id

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=None,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=100,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 8, 20),
            total=self._calcular_totales(request.items)["total"],
            mensaje="Autorizado por doble sintético",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    accepted = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={
            **auth_headers,
            **headers,
            "X-Confirmacion-Duplicado-Logico": acceptance_id,
        },
    )
    assert accepted.status_code == 200, accepted.text
    operation = (
        await db_session.execute(
            select(OperacionIdempotente).where(
                OperacionIdempotente.idempotency_key == "pf13-aceptacion-v2"
            )
        )
    ).scalar_one()
    assert operation.control_duplicados_json["evidencia_id"] == evidence_id
    assert operation.control_duplicados_json["aceptacion_id"] == acceptance_id
    assert operation.control_duplicados_json["estado"] == "aceptada"
    durable_page = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/coincidencias",
        params={"evidencia_id": evidence_id, "page": 1, "per_page": 1},
        headers=auth_headers,
    )
    assert durable_page.status_code == 200, durable_page.text
    assert durable_page.json()["total"] == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("accion", ["procesar", "reintentar-fallidos"])
@pytest.mark.parametrize("reusar_clave", [True, False])
async def test_remanente_v1_aceptado_no_admite_reconfirmacion_ni_nueva_operacion(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    accion: str,
    reusar_clave: bool,
) -> None:
    """Una aceptación v1 no comprobable no se reconstruye como aceptación v2."""
    empresa_id = int(test_empresa.id)
    cantidad = 3 if accion == "reintentar-fallidos" and not reusar_clave else 2
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre=f"legacy-{accion}.xlsx",
        cantidad=cantidad,
    )
    estados = {"validado"}
    body = None
    if accion == "reintentar-fallidos":
        grupos_preparados = await _marcar_grupos_lote(
            db_session, lote_id, ["fallido"] * cantidad
        )
        estados = {"fallido"}
        body = {}
    else:
        grupos_preparados = list(
            (
                await db_session.scalars(
                    select(LoteComprobanteGrupo)
                    .where(LoteComprobanteGrupo.lote_id == lote_id)
                    .order_by(LoteComprobanteGrupo.orden)
                )
            ).all()
        )
    assert len(grupos_preparados) == cantidad
    for grupo in grupos_preparados[:2]:
        grupo.identidad_nombre_hash = "a" * 64
        grupo.identidad_documento_hash = "b" * 64
    await db_session.commit()

    clave_legacy = f"pf13-legacy-{accion}"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados=estados,
        idempotency_key=clave_legacy,
    )
    endpoint = f"/api/lotes-comprobantes/{lote_id}/{accion}"
    primera = await client.post(
        endpoint,
        headers={**auth_headers, **headers},
        json=body,
    )
    assert primera.status_code == 409, primera.text
    assert primera.json()["detail"]["categoria_error"] == "duplicado_logico_lote"

    operacion_legacy = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == clave_legacy
        )
    )
    assert operacion_legacy is not None
    legacy_id = int(operacion_legacy.id)
    material_rece = await LoteComprobantesService(
        db_session
    ).calcular_material_idempotente_grupos(
        lote_id=lote_id,
        empresa_id=empresa_id,
        estados=estados,
    )
    await db_session.execute(
        update(OperacionIdempotente)
        .where(OperacionIdempotente.id == legacy_id)
        .values(
            duplicados_generacion_id=None,
            duplicados_version=None,
            control_duplicados_json=None,
            estado="interrumpida_pre_arca",
            response_json=null(),
        )
    )
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    metadata = dict(lote.metadata_json or {})
    metadata["operacion_idempotente_id"] = legacy_id
    metadata["confirmacion_duplicado_logico"] = True
    metadata["pf19b_rece_material"] = material_rece
    lote.metadata_json = metadata
    if accion == "procesar" and not reusar_clave:
        lote.estado = "en_cola"
        lote.modo_procesamiento = "background"
        lote.procesamiento_async = True
        operacion_legacy.estado = "en_proceso"
        operacion_legacy.response_json = {
            "lote": LoteComprobanteResponse.model_validate(lote).model_dump(
                mode="json"
            ),
            "mensaje": "El lote legacy permanece en cola.",
            "en_progreso": True,
            "errores_arca": [],
        }
    await db_session.flush()
    await db_session.execute(
        delete(LoteDuplicadoEvidencia).where(
            LoteDuplicadoEvidencia.operacion_id == operacion_legacy.id
        )
    )
    await db_session.commit()

    estado_legacy = operacion_legacy.estado
    payload_hash_legacy = operacion_legacy.payload_hash
    response_legacy = deepcopy(operacion_legacy.response_json)
    metadata_legacy = deepcopy(lote.metadata_json)
    operaciones_antes = int(
        await db_session.scalar(
            select(func.count(OperacionIdempotente.id)).where(
                OperacionIdempotente.lote_id == lote_id
            )
        )
        or 0
    )
    headers_intento = {
        **auth_headers,
        **headers,
        "X-Idempotency-Key": (
            clave_legacy if reusar_clave else f"{clave_legacy}-nueva"
        ),
        "X-Confirmacion-Duplicado-Logico": primera.json()["detail"]["aceptacion_id"],
    }
    body_intento = body
    if accion == "reintentar-fallidos" and not reusar_clave:
        body_intento = {"grupo_ids": [int(grupos_preparados[-1].id)]}

    bloqueado = await client.post(endpoint, headers=headers_intento, json=body_intento)

    assert bloqueado.status_code == 409, bloqueado.text
    assert (
        bloqueado.json()["detail"]["categoria_error"]
        == "duplicado_legacy_no_reconfirmable"
    )
    db_session.expire_all()
    operacion_legacy = await db_session.get(OperacionIdempotente, legacy_id)
    assert operacion_legacy is not None
    assert operacion_legacy.estado == estado_legacy
    assert operacion_legacy.payload_hash == payload_hash_legacy
    assert operacion_legacy.response_json == response_legacy
    assert operacion_legacy.duplicados_version is None
    assert operacion_legacy.control_duplicados_json is None
    assert operacion_legacy.duplicados_generacion_id is None
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    assert lote.metadata_json == metadata_legacy
    assert (
        int(
            await db_session.scalar(
                select(func.count(OperacionIdempotente.id)).where(
                    OperacionIdempotente.lote_id == lote_id
                )
            )
            or 0
        )
        == operaciones_antes
    )
    assert (
        int(
            await db_session.scalar(
                select(func.count(LoteDuplicadoEvidencia.id)).where(
                    LoteDuplicadoEvidencia.operacion_id == operacion_legacy.id
                )
            )
            or 0
        )
        == 0
    )
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id
                )
            )
        ).all()
    )
    assert all(grupo.duplicados_reserva_operacion_id is None for grupo in grupos)
    assert (
        int(
            await db_session.scalar(
                select(func.count(IntentoEmisionFiscal.id)).where(
                    IntentoEmisionFiscal.lote_id == lote_id
                )
            )
            or 0
        )
        == 0
    )
    assert (
        int(
            await db_session.scalar(
                select(func.count(PuntoVentaGuardaEmisionRece.id)).where(
                    PuntoVentaGuardaEmisionRece.operacion_id == operacion_legacy.id
                )
            )
            or 0
        )
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("aceptacion_historica", "cantidad"),
    [
        pytest.param(False, 2, id="sin-aceptacion-historica"),
        pytest.param(True, 1, id="sin-coincidencias-actuales"),
    ],
)
async def test_bloqueo_legacy_no_amplia_remanentes_convertibles(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    aceptacion_historica: bool,
    cantidad: int,
) -> None:
    """Un v1 pendiente o sin coincidencias actuales conserva la conversión pre-ARCA."""
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="legacy-convertible.xlsx",
        cantidad=cantidad,
    )
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    for grupo in grupos:
        grupo.identidad_nombre_hash = "c" * 64
        grupo.identidad_documento_hash = "d" * 64
    owner = OperacionIdempotente(
        empresa_id=int(test_empresa.id),
        idempotency_key=f"pf13-legacy-convertible-{aceptacion_historica}-{cantidad}",
        tipo_operacion="procesar_lote",
        payload_hash="e" * 64,
        estado="interrumpida_pre_arca",
        lote_id=lote_id,
    )
    db_session.add(owner)
    await db_session.flush()
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    metadata = dict(lote.metadata_json or {})
    metadata["operacion_idempotente_id"] = int(owner.id)
    metadata["confirmacion_duplicado_logico"] = aceptacion_historica
    lote.metadata_json = metadata
    await db_session.commit()

    bloqueo = await DuplicadosLotesService(
        db_session
    ).obtener_bloqueo_legacy_no_reconfirmable(
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado"},
    )

    assert bloqueo is None


@pytest.mark.asyncio
async def test_reintentar_fallidos_replay_terminal_precede_owner_legacy_posterior(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Una clave terminal conserva su replay aunque el lote cambie luego de owner."""
    empresa_id = int(test_empresa.id)
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="replay-terminal-con-owner-legacy.xlsx",
        cantidad=2,
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido", "fallido"])
    for grupo in grupos:
        grupo.identidad_nombre_hash = "f" * 64
        grupo.identidad_documento_hash = "1" * 64
    await db_session.commit()
    clave_terminal = "pf13-retry-terminal-antes-de-legacy"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        idempotency_key=clave_terminal,
    )
    material = await LoteComprobantesService(
        db_session
    ).calcular_material_idempotente_grupos(
        lote_id=lote_id,
        empresa_id=empresa_id,
        estados={"fallido", "reintentando", "autorizado", "requiere_reconciliacion"},
    )
    payload = {
        "lote_id": lote_id,
        "grupo_ids": [],
        "confirmacion_fecha_fiscal": headers["X-Confirmacion-Fecha-Fiscal"],
        "grupo_ids_resueltos": material["grupo_ids"],
        "grupos_hash": material["grupos_hash"],
    }
    idempotencia = IdempotenciaFiscalService(db_session)
    terminal = OperacionIdempotente(
        empresa_id=empresa_id,
        idempotency_key=clave_terminal,
        tipo_operacion="reintentar_fallidos_lote",
        payload_hash=idempotencia.calcular_payload_hash(payload),
        estado="finalizado",
        lote_id=lote_id,
    )
    db_session.add(terminal)
    await db_session.flush()
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    terminal.response_json = {
        "lote": LoteComprobanteResponse.model_validate(lote).model_dump(mode="json"),
        "mensaje": "Resultado terminal durable previo.",
        "errores_arca": [],
    }
    owner_legacy = OperacionIdempotente(
        empresa_id=empresa_id,
        idempotency_key="pf13-owner-legacy-posterior",
        tipo_operacion="reintentar_fallidos_lote",
        payload_hash="2" * 64,
        estado="interrumpida_pre_arca",
        lote_id=lote_id,
    )
    db_session.add(owner_legacy)
    await db_session.flush()
    metadata = dict(lote.metadata_json or {})
    metadata["operacion_idempotente_id"] = int(owner_legacy.id)
    metadata["confirmacion_duplicado_logico"] = True
    lote.metadata_json = metadata
    await db_session.commit()
    bloqueo = await DuplicadosLotesService(
        db_session
    ).obtener_bloqueo_legacy_no_reconfirmable(
        lote_id=lote_id,
        empresa_id=empresa_id,
        estados={"fallido"},
    )
    assert bloqueo is not None
    conteo_antes = int(
        await db_session.scalar(
            select(func.count(OperacionIdempotente.id)).where(
                OperacionIdempotente.lote_id == lote_id
            )
        )
        or 0
    )

    replay = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers},
        json={},
    )

    assert replay.status_code == 200, replay.text
    assert replay.json() == terminal.response_json
    assert (
        int(
            await db_session.scalar(
                select(func.count(OperacionIdempotente.id)).where(
                    OperacionIdempotente.lote_id == lote_id
                )
            )
            or 0
        )
        == conteo_antes
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("accion", ["procesar", "reintentar-fallidos"])
@pytest.mark.parametrize("reusar_clave", [True, False])
async def test_admision_legacy_revierte_create_o_claim_si_falla_antes_de_reservar(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    accion: str,
    reusar_clave: bool,
) -> None:
    """Create/claim y reserva v2 pertenecen a una única raíz reversible."""
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre=f"legacy-rollback-{accion}.xlsx",
        cantidad=2,
    )
    estados = {"validado"}
    body = None
    if accion == "reintentar-fallidos":
        grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido", "fallido"])
        estados = {"fallido"}
        body = {}
    else:
        grupos = list(
            (
                await db_session.scalars(
                    select(LoteComprobanteGrupo)
                    .where(LoteComprobanteGrupo.lote_id == lote_id)
                    .order_by(LoteComprobanteGrupo.orden)
                )
            ).all()
        )
    for grupo in grupos:
        grupo.identidad_nombre_hash = "3" * 64
        grupo.identidad_documento_hash = "4" * 64
    await db_session.commit()
    clave_legacy = f"pf13-legacy-rollback-{accion}-{reusar_clave}"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados=estados,
        idempotency_key=clave_legacy,
    )
    endpoint = f"/api/lotes-comprobantes/{lote_id}/{accion}"
    advertencia = await client.post(
        endpoint,
        headers={**auth_headers, **headers},
        json=body,
    )
    assert advertencia.status_code == 409, advertencia.text
    operacion_legacy = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == clave_legacy
        )
    )
    assert operacion_legacy is not None
    legacy_id = int(operacion_legacy.id)
    await db_session.execute(
        update(OperacionIdempotente)
        .where(OperacionIdempotente.id == legacy_id)
        .values(
            duplicados_generacion_id=None,
            duplicados_version=None,
            control_duplicados_json=None,
            estado="interrumpida_pre_arca",
            response_json=null(),
        )
    )
    await db_session.execute(
        delete(LoteDuplicadoEvidencia).where(
            LoteDuplicadoEvidencia.operacion_id == legacy_id
        )
    )
    grupos[1].identidad_nombre_hash = "5" * 64
    grupos[1].identidad_documento_hash = "6" * 64
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    metadata = dict(lote.metadata_json or {})
    metadata["operacion_idempotente_id"] = legacy_id
    metadata["confirmacion_duplicado_logico"] = True
    lote.metadata_json = metadata
    await db_session.commit()
    db_session.expire_all()
    operacion_legacy = await db_session.get(OperacionIdempotente, legacy_id)
    lote = await db_session.get(LoteComprobante, lote_id)
    assert operacion_legacy is not None
    assert lote is not None
    estado_antes = operacion_legacy.estado
    hash_antes = operacion_legacy.payload_hash
    respuesta_antes = deepcopy(operacion_legacy.response_json)
    metadata_antes = deepcopy(lote.metadata_json)
    operaciones_antes = int(
        await db_session.scalar(
            select(func.count(OperacionIdempotente.id)).where(
                OperacionIdempotente.lote_id == lote_id
            )
        )
        or 0
    )

    async def fallar_antes_de_reservar(self, **kwargs):
        raise DuplicadosLoteError(
            "Fallo sintético antes de reservar.",
            "duplicados_fallo_sintetico",
        )

    resultados_claim = []
    reclamar_original = (
        IdempotenciaFiscalService.reclamar_operacion_interrumpida_pre_arca
    )

    async def registrar_claim(self, operacion, *, commit=True):
        resultado = await reclamar_original(self, operacion, commit=commit)
        resultados_claim.append((commit, resultado[1], resultado[0].estado))
        return resultado

    monkeypatch.setattr(
        DuplicadosLotesService,
        "evaluar_y_reservar_bajo_coordinacion",
        fallar_antes_de_reservar,
    )
    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "reclamar_operacion_interrumpida_pre_arca",
        registrar_claim,
    )
    headers_intento = {
        **auth_headers,
        **headers,
        "X-Idempotency-Key": (
            clave_legacy if reusar_clave else f"{clave_legacy}-nueva"
        ),
    }

    fallida = await client.post(endpoint, headers=headers_intento, json=body)

    assert fallida.status_code == 409, fallida.text
    assert (
        fallida.json()["detail"]["categoria_error"] == "duplicados_fallo_sintetico"
    ), (
        fallida.json(),
        resultados_claim,
    )
    db_session.expire_all()
    operacion_legacy = await db_session.get(OperacionIdempotente, legacy_id)
    lote = await db_session.get(LoteComprobante, lote_id)
    assert operacion_legacy is not None
    assert lote is not None
    assert operacion_legacy.estado == estado_antes
    assert operacion_legacy.payload_hash == hash_antes
    assert operacion_legacy.response_json == respuesta_antes
    assert operacion_legacy.duplicados_version is None
    assert operacion_legacy.control_duplicados_json is None
    assert operacion_legacy.duplicados_generacion_id is None
    assert lote.metadata_json == metadata_antes
    assert (
        int(
            await db_session.scalar(
                select(func.count(OperacionIdempotente.id)).where(
                    OperacionIdempotente.lote_id == lote_id
                )
            )
            or 0
        )
        == operaciones_antes
    )
    grupos_recargados = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id
                )
            )
        ).all()
    )
    assert all(
        grupo.duplicados_reserva_operacion_id is None for grupo in grupos_recargados
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("token_fiscal_valido", [True, False])
async def test_admision_legacy_rechaza_dml_ajeno_antes_de_preparar_rece(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    token_fiscal_valido: bool,
) -> None:
    """La lectura legacy contaminada no puede confirmar DML ni alcanzar RECE."""
    empresa_id = int(test_empresa.id)
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre=f"legacy-frontera-{token_fiscal_valido}.xlsx",
        cantidad=2,
    )
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    for grupo in grupos:
        grupo.identidad_nombre_hash = "a" * 64
        grupo.identidad_documento_hash = "b" * 64
    await db_session.commit()
    clave_legacy = f"pf13-legacy-frontera-{token_fiscal_valido}"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=clave_legacy,
    )
    endpoint = f"/api/lotes-comprobantes/{lote_id}/procesar"
    advertencia = await client.post(endpoint, headers={**auth_headers, **headers})
    assert advertencia.status_code == 409, advertencia.text
    owner = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == clave_legacy
        )
    )
    assert owner is not None
    owner_id = int(owner.id)
    await db_session.execute(
        update(OperacionIdempotente)
        .where(OperacionIdempotente.id == owner_id)
        .values(
            duplicados_generacion_id=None,
            duplicados_version=None,
            control_duplicados_json=None,
            estado="interrumpida_pre_arca",
            response_json=null(),
        )
    )
    await db_session.execute(
        delete(LoteDuplicadoEvidencia).where(
            LoteDuplicadoEvidencia.operacion_id == owner_id
        )
    )
    grupos[1].identidad_nombre_hash = "c" * 64
    grupos[1].identidad_documento_hash = "d" * 64
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    metadata = dict(lote.metadata_json or {})
    metadata["operacion_idempotente_id"] = owner_id
    metadata["confirmacion_duplicado_logico"] = True
    lote.metadata_json = metadata
    await db_session.commit()
    metadata_antes = deepcopy(lote.metadata_json)
    operaciones_antes = int(
        await db_session.scalar(
            select(func.count(OperacionIdempotente.id)).where(
                OperacionIdempotente.lote_id == lote_id
            )
        )
        or 0
    )
    resumen_original = LoteComprobantesService.obtener_resumen_operativo_lote

    async def contaminar_resumen(self, *args, **kwargs):
        resultado = await resumen_original(self, *args, **kwargs)
        await self.db.execute(
            update(Empresa)
            .where(Empresa.id == empresa_id)
            .values(razon_social="Cambio legacy no autorizado")
        )
        return resultado

    preparaciones_rece = 0

    async def no_preparar_rece(*_args, **_kwargs):
        nonlocal preparaciones_rece
        preparaciones_rece += 1
        raise AssertionError("No debe alcanzarse la preparación RECE")

    monkeypatch.setattr(
        LoteComprobantesService,
        "obtener_resumen_operativo_lote",
        contaminar_resumen,
    )
    monkeypatch.setattr(
        PuntosVentaArcaService,
        "asegurar_comprobacion_reciente",
        no_preparar_rece,
    )
    headers_intento = {
        **auth_headers,
        "X-Idempotency-Key": (
            clave_legacy if token_fiscal_valido else f"{clave_legacy}-sin-token"
        ),
    }
    if token_fiscal_valido:
        headers_intento["X-Confirmacion-Fecha-Fiscal"] = headers[
            "X-Confirmacion-Fecha-Fiscal"
        ]

    bloqueada = await client.post(endpoint, headers=headers_intento)

    assert bloqueada.status_code == 409, bloqueada.text
    assert (
        bloqueada.json()["detail"]["categoria_error"]
        == "duplicado_coordinacion_transaccional"
    )
    assert preparaciones_rece == 0
    await db_session.rollback()
    db_session.expire_all()
    empresa = await db_session.get(Empresa, empresa_id)
    owner = await db_session.get(OperacionIdempotente, owner_id)
    lote = await db_session.get(LoteComprobante, lote_id)
    assert empresa is not None
    assert empresa.razon_social == "Empresa Test S.A."
    assert owner is not None
    assert owner.estado == "interrumpida_pre_arca"
    assert owner.duplicados_version is None
    assert owner.control_duplicados_json is None
    assert owner.duplicados_generacion_id is None
    assert owner.response_json is None
    assert lote is not None
    assert lote.metadata_json == metadata_antes
    assert (
        int(
            await db_session.scalar(
                select(func.count(OperacionIdempotente.id)).where(
                    OperacionIdempotente.lote_id == lote_id
                )
            )
            or 0
        )
        == operaciones_antes
    )
    grupos_actuales = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id
                )
            )
        ).all()
    )
    assert all(
        grupo.duplicados_reserva_operacion_id is None for grupo in grupos_actuales
    )


@pytest.mark.asyncio
async def test_admision_legacy_revalida_coincidencia_aparecida_antes_del_coordinador(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """La clasificación se repite bajo coordinación antes de crear otra operación."""
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="legacy-intercalado-antes-coordinador.xlsx",
        cantidad=2,
    )
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    for grupo in grupos:
        grupo.identidad_nombre_hash = "7" * 64
        grupo.identidad_documento_hash = "8" * 64
    await db_session.commit()
    clave_legacy = "pf13-legacy-intercalado-owner"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=clave_legacy,
    )
    endpoint = f"/api/lotes-comprobantes/{lote_id}/procesar"
    advertencia = await client.post(
        endpoint,
        headers={**auth_headers, **headers},
    )
    assert advertencia.status_code == 409, advertencia.text
    owner = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == clave_legacy
        )
    )
    assert owner is not None
    owner_id = int(owner.id)
    await db_session.execute(
        update(OperacionIdempotente)
        .where(OperacionIdempotente.id == owner_id)
        .values(
            duplicados_generacion_id=None,
            duplicados_version=None,
            control_duplicados_json=None,
            estado="interrumpida_pre_arca",
            response_json=null(),
        )
    )
    await db_session.execute(
        delete(LoteDuplicadoEvidencia).where(
            LoteDuplicadoEvidencia.operacion_id == owner_id
        )
    )
    grupos[1].identidad_nombre_hash = "9" * 64
    grupos[1].identidad_documento_hash = "a" * 64
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    metadata = dict(lote.metadata_json or {})
    metadata["operacion_idempotente_id"] = owner_id
    metadata["confirmacion_duplicado_logico"] = True
    lote.metadata_json = metadata
    await db_session.commit()
    metadata_antes = deepcopy(lote.metadata_json)
    grupo_intercalado_id = int(grupos[1].id)
    operaciones_antes = int(
        await db_session.scalar(
            select(func.count(OperacionIdempotente.id)).where(
                OperacionIdempotente.lote_id == lote_id
            )
        )
        or 0
    )
    adquirir_original = DuplicadosLotesService.adquirir_coordinacion
    intercalada = False

    async def adquirir_despues_de_publicacion(self, **kwargs):
        nonlocal intercalada
        if not intercalada:
            intercalada = True
            await self.db.execute(
                update(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.id == grupo_intercalado_id)
                .values(
                    identidad_nombre_hash="7" * 64,
                    identidad_documento_hash="8" * 64,
                )
            )
            await self.db.commit()
        return await adquirir_original(self, **kwargs)

    monkeypatch.setattr(
        DuplicadosLotesService,
        "adquirir_coordinacion",
        adquirir_despues_de_publicacion,
    )

    bloqueada = await client.post(
        endpoint,
        headers={
            **auth_headers,
            **headers,
            "X-Idempotency-Key": "pf13-legacy-intercalado-nueva",
        },
    )

    assert intercalada is True
    assert bloqueada.status_code == 409, bloqueada.text
    assert (
        bloqueada.json()["detail"]["categoria_error"]
        == "duplicado_legacy_no_reconfirmable"
    )
    db_session.expire_all()
    owner = await db_session.get(OperacionIdempotente, owner_id)
    lote = await db_session.get(LoteComprobante, lote_id)
    assert owner is not None
    assert lote is not None
    assert owner.estado == "interrumpida_pre_arca"
    assert owner.response_json is None
    assert owner.duplicados_version is None
    assert owner.control_duplicados_json is None
    assert owner.duplicados_generacion_id is None
    assert lote.metadata_json == metadata_antes
    assert (
        int(
            await db_session.scalar(
                select(func.count(OperacionIdempotente.id)).where(
                    OperacionIdempotente.lote_id == lote_id
                )
            )
            or 0
        )
        == operaciones_antes
    )


@pytest.mark.asyncio
async def test_coordinacion_sqlite_serializa_sesiones_reales(tmp_path) -> None:
    """La segunda sesión espera el commit de la raíz coordinadora en SQLite."""
    database_path = tmp_path / "pf13-coordinacion.sqlite3"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
        connect_args={"timeout": 2},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE lotes_duplicados_coordinacion ("
                "empresa_id INTEGER NOT NULL, ambiente VARCHAR(20) NOT NULL, "
                "revision INTEGER NOT NULL, updated_at DATETIME NOT NULL, "
                "PRIMARY KEY (empresa_id, ambiente))"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO lotes_duplicados_coordinacion "
                "(empresa_id, ambiente, revision, updated_at) "
                "VALUES (1, 'homologacion', 0, CURRENT_TIMESTAMP)"
            )
        )
    try:
        async with sessions() as sesion_a, sessions() as sesion_b:
            await DuplicadosLotesService(sesion_a).adquirir_coordinacion(
                empresa_id=1,
                ambiente="homologacion",
            )
            tarea_b = asyncio.create_task(
                DuplicadosLotesService(sesion_b).adquirir_coordinacion(
                    empresa_id=1,
                    ambiente="homologacion",
                )
            )
            await asyncio.sleep(0.05)
            assert not tarea_b.done()
            await sesion_a.commit()
            await tarea_b
            revision_b = await sesion_b.scalar(
                text(
                    "SELECT revision FROM lotes_duplicados_coordinacion "
                    "WHERE empresa_id = 1 AND ambiente = 'homologacion'"
                )
            )
            assert revision_b == 2
            await sesion_b.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_detalle_v2_rechaza_evidencia_obsoleta_sin_exponer_aceptacion(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    excel = _modificar_receptores_excel_multi(
        _build_lote_excel_multi_grupo(test_empresa.cuit),
        tipo="DNI",
        numeros=["30000031", "30000031"],
        nombres=["Persona Sintética", "Persona Sintética"],
        condicion="Consumidor Final",
    )
    validation = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "evidencia-obsoleta.xlsx",
                excel,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    lote_id = validation.json()["lote"]["id"]
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="pf13-evidencia-obsoleta",
    )
    warning = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )
    assert warning.status_code == 409, warning.text
    old_evidence = warning.json()["detail"]["control_duplicados"]["evidencia_id"]
    group = await db_session.scalar(
        select(LoteComprobanteGrupo)
        .where(LoteComprobanteGrupo.lote_id == lote_id)
        .order_by(LoteComprobanteGrupo.orden)
    )
    group.huella_fiscal_completa = "f" * 64
    await db_session.commit()

    detail = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/coincidencias",
        params={"evidencia_id": old_evidence},
        headers=auth_headers,
    )

    assert detail.status_code == 409, detail.text
    payload = detail.json()["detail"]
    assert payload["control_duplicados"]["evidencia_id"] != old_evidence
    assert "aceptacion_id" not in payload
    assert "aceptacion_id" not in payload["control_duplicados"]


@pytest.mark.asyncio
async def test_detalle_retry_v2_conserva_seleccion_original_parcial(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="retry-seleccion-parcial.xlsx",
        cantidad=3,
    )
    grupos = await _marcar_grupos_lote(
        db_session,
        lote_id,
        ["fallido", "fallido", "fallido"],
    )
    for grupo in grupos:
        grupo.identidad_nombre_hash = "a" * 64
        grupo.identidad_documento_hash = "b" * 64
    await db_session.commit()
    seleccion = [int(grupos[0].id), int(grupos[1].id)]
    excluido_id = int(grupos[2].id)
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=seleccion,
        idempotency_key="pf13-retry-parcial",
    )
    warning = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers},
        json={"grupo_ids": seleccion},
    )
    assert warning.status_code == 409, warning.text
    evidence = warning.json()["detail"]["control_duplicados"]["evidencia_id"]

    detail = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/coincidencias",
        params={"evidencia_id": evidence, "page": 1, "per_page": 100},
        headers=auth_headers,
    )

    assert detail.status_code == 200, detail.text
    assert {item["grupo_actual_id"] for item in detail.json()["items"]} == set(
        seleccion
    )
    assert excluido_id not in {
        item["grupo_actual_id"] for item in detail.json()["items"]
    }


async def _publicar_generacion_real_de_prueba(
    db_session: AsyncSession,
    *,
    empresa_id: int,
    lote_id: int,
    grupos: list[LoteComprobanteGrupo],
    idempotency_key: str,
    aceptar: bool,
) -> tuple[OperacionIdempotente, LoteDuplicadoEvidencia, dict, str | None,]:
    usuario_id = await db_session.scalar(
        select(UsuarioEmisorAcceso.usuario_id).where(
            UsuarioEmisorAcceso.empresa_id == empresa_id
        )
    )
    operation = OperacionIdempotente(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        idempotency_key=idempotency_key,
        tipo_operacion="procesar_lote",
        payload_hash=hashlib.sha256(idempotency_key.encode()).hexdigest(),
        estado="en_proceso",
        lote_id=lote_id,
    )
    db_session.add(operation)
    await db_session.commit()
    service = DuplicadosLotesService(db_session)
    control, token, accepted = await service.evaluar_y_reservar(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=empresa_id,
        estados={"validado", "autorizado", "fallido"},
        grupo_ids=[int(group.id) for group in grupos],
        aceptacion_recibida=None,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    if aceptar:
        assert token is not None
        control, same_token, accepted = await service.evaluar_y_reservar(
            operacion_id=int(operation.id),
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados={"validado", "autorizado", "fallido"},
            grupo_ids=[int(group.id) for group in grupos],
            aceptacion_recibida=token,
            solicitante_nombre="Operador sintético",
            reservar=False,
            ambiente=settings.arca_env,
        )
        assert same_token == token
        assert accepted is True
    else:
        assert accepted is False
    operation = await db_session.get(OperacionIdempotente, int(operation.id))
    generation = await db_session.get(
        LoteDuplicadoEvidencia, int(operation.duplicados_generacion_id)
    )
    assert generation is not None
    return operation, generation, control, token


async def _crear_intento_sintetico_con_generacion(
    db_session: AsyncSession,
    *,
    operation: OperacionIdempotente,
    group: LoteComprobanteGrupo,
    generation_id: int,
    punto_venta: PuntoVenta,
) -> IntentoEmisionFiscal:
    contexto = ContextoElegibilidadRece(
        empresa_id=int(group.empresa_id),
        punto_venta_id=int(group.punto_venta_id),
        punto_venta_numero=int(group.punto_venta_numero),
        ambiente=str(group.ambiente),
        elegibilidad_revision_id=int(group.punto_venta_elegibilidad_revision_id),
        punto_venta_revision_fiscal=int(group.punto_venta_revision_fiscal),
    )
    operation.rece_snapshot_hash = ElegibilidadReceService.calcular_digest_contextos(
        [contexto]
    )
    db_session.add(
        OperacionIdempotenteElegibilidadRece(
            operacion_id=int(operation.id),
            empresa_id=int(group.empresa_id),
            punto_venta_id=int(group.punto_venta_id),
            ambiente=str(group.ambiente),
            elegibilidad_revision_id=int(group.punto_venta_elegibilidad_revision_id),
            punto_venta_revision_fiscal=int(group.punto_venta_revision_fiscal),
        )
    )
    await db_session.commit()
    guard = PuntoVentaGuardaEmisionRece(
        token=hashlib.sha256(
            f"guarda-{operation.id}-{generation_id}".encode()
        ).hexdigest(),
        fase="pre_arca",
        operacion_id=int(operation.id),
        empresa_id=int(group.empresa_id),
        punto_venta_id=int(group.punto_venta_id),
        ambiente=str(group.ambiente),
        elegibilidad_revision_id=int(group.punto_venta_elegibilidad_revision_id),
        punto_venta_revision_fiscal=int(group.punto_venta_revision_fiscal),
    )
    db_session.add(guard)
    await db_session.flush()
    request = EmitirComprobanteRequest.model_validate(group.payload_json or {})
    intento = await IdempotenciaFiscalService(db_session).crear_intento_emision(
        request=request,
        punto_venta=punto_venta,
        numero_planificado=1000 + int(group.id),
        total=FacturacionService(db_session)._calcular_totales(request.items)["total"],
        operacion_id=int(operation.id),
        usuario_id=operation.usuario_id,
        lote_id=int(group.lote_id),
        grupo_id=int(group.id),
        duplicados_generacion_id=generation_id,
        contexto_rece=contexto,
        guarda_rece_id=int(guard.id),
        commit=False,
    )
    await db_session.commit()
    return intento


@pytest.mark.asyncio
async def test_retry_reutiliza_xy_solo_para_y_y_no_extiende_aceptacion_a_z(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="seleccion-original-xyz.xlsx",
        cantidad=3,
    )
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    x, y, z = grupos
    x.identidad_documento_hash = "a" * 64
    y.identidad_documento_hash = "a" * 64
    await db_session.flush()
    empresa_id = int(test_empresa.id)
    service = DuplicadosLotesService(db_session)
    usuario_id = await db_session.scalar(
        select(UsuarioEmisorAcceso.usuario_id).where(
            UsuarioEmisorAcceso.empresa_id == empresa_id
        )
    )
    root = OperacionIdempotente(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        idempotency_key="pf13-raiz-xy",
        tipo_operacion="procesar_lote",
        payload_hash="e" * 64,
        estado="en_proceso",
        lote_id=lote_id,
    )
    db_session.add(root)
    await db_session.commit()
    root_id = int(inspect(root).identity[0])
    baseline, token_xy, accepted = await service.evaluar_y_reservar(
        operacion_id=root_id,
        lote_id=lote_id,
        empresa_id=empresa_id,
        estados={"validado"},
        grupo_ids=[int(x.id), int(y.id)],
        aceptacion_recibida=None,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    assert token_xy is not None
    assert accepted is False
    baseline, same_token, accepted = await service.evaluar_y_reservar(
        operacion_id=root_id,
        lote_id=lote_id,
        empresa_id=empresa_id,
        estados={"validado"},
        grupo_ids=[int(x.id), int(y.id)],
        aceptacion_recibida=token_xy,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    assert same_token == token_xy
    assert accepted is True
    root = await db_session.get(OperacionIdempotente, root_id)
    root.estado = "finalizado"
    retry_y = OperacionIdempotente(
        empresa_id=empresa_id,
        idempotency_key="pf13-retry-y",
        tipo_operacion="reintentar_fallidos_lote",
        payload_hash="f" * 64,
        estado="en_proceso",
        lote_id=lote_id,
        operacion_raiz_id=int(root.id),
    )
    retry_z = OperacionIdempotente(
        empresa_id=empresa_id,
        idempotency_key="pf13-retry-z",
        tipo_operacion="reintentar_fallidos_lote",
        payload_hash="1" * 64,
        estado="en_proceso",
        lote_id=lote_id,
        operacion_raiz_id=int(root.id),
    )
    db_session.add_all([retry_y, retry_z])
    x.estado = "autorizado"
    y.estado = "fallido"
    z.estado = "fallido"
    await db_session.commit()
    retry_y_id = int(inspect(retry_y).identity[0])
    retry_z_id = int(inspect(retry_z).identity[0])
    y_id = int(inspect(y).identity[0])
    z_id = int(inspect(z).identity[0])

    control, acceptance_id, accepted = await service.evaluar_y_reservar(
        operacion_id=retry_y_id,
        lote_id=lote_id,
        empresa_id=empresa_id,
        estados={"fallido"},
        grupo_ids=[y_id],
        aceptacion_recibida=token_xy,
        solicitante_nombre="Operador sintético",
        reservar=True,
        ambiente=settings.arca_env,
    )
    assert accepted is True
    assert acceptance_id == token_xy
    assert control["evidencia_id"] == baseline["evidencia_id"]
    y_actual = await db_session.get(LoteComprobanteGrupo, y_id)
    z_actual = await db_session.get(LoteComprobanteGrupo, z_id)
    assert y_actual.duplicados_reserva_operacion_id == retry_y_id
    assert z_actual.duplicados_reserva_operacion_id is None
    await db_session.rollback()

    with pytest.raises(
        DuplicadosLoteError,
        match="no pertenecen a la selección original",
    ):
        await service.evaluar_y_reservar(
            operacion_id=retry_z_id,
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados={"fallido"},
            grupo_ids=[z_id],
            aceptacion_recibida=token_xy,
            solicitante_nombre="Operador sintético",
            reservar=True,
            ambiente=settings.arca_env,
        )
    await db_session.rollback()
    root_actual = await db_session.get(OperacionIdempotente, root_id)
    assert root_actual.operacion_raiz_id == root_id
    assert (
        await db_session.get(LoteComprobanteGrupo, z_id)
    ).duplicados_reserva_operacion_id is None


@pytest.mark.asyncio
async def test_generaciones_conservan_token_aceptacion_y_progreso_propio(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="generaciones-snapshot.xlsx",
        cantidad=2,
    )
    grupos = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo)
            .where(LoteComprobanteGrupo.lote_id == lote_id)
            .order_by(LoteComprobanteGrupo.id)
        )
    )
    for group in grupos:
        group.identidad_documento_hash = "9" * 64
    await db_session.commit()
    operation, generation_1, control, token = await _publicar_generacion_real_de_prueba(
        db_session,
        empresa_id=int(test_empresa.id),
        lote_id=lote_id,
        grupos=grupos,
        idempotency_key="pf13-generaciones-snapshot",
        aceptar=False,
    )
    assert control["estado"] == "requiere_confirmacion"
    assert token is not None
    assert generation_1.aceptada_at is None

    grupos[0].comprobante_ref += "-descriptivo"
    await db_session.commit()
    _, same_token, accepted = await DuplicadosLotesService(
        db_session
    ).evaluar_y_reservar(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado", "autorizado"},
        grupo_ids=[int(group.id) for group in grupos],
        aceptacion_recibida=None,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    await db_session.refresh(operation)
    generation_2 = await db_session.get(
        LoteDuplicadoEvidencia, int(operation.duplicados_generacion_id)
    )
    assert generation_2.id != generation_1.id
    assert same_token == token
    assert accepted is False
    assert generation_2.aceptada_at is None
    assert generation_2.aceptacion_origen_generacion_id is None
    await db_session.commit()

    _, same_token, accepted = await DuplicadosLotesService(
        db_session
    ).evaluar_y_reservar(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado", "autorizado"},
        grupo_ids=[int(group.id) for group in grupos],
        aceptacion_recibida=token,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    assert same_token == token
    assert accepted is True
    await db_session.refresh(generation_2)
    accepted_audit = (
        generation_2.aceptacion_id,
        generation_2.aceptada_por_usuario_id,
        generation_2.aceptada_por_nombre,
        generation_2.aceptada_at,
    )

    grupos[1].comprobante_ref += "-otro-contexto"
    await db_session.commit()
    _, inherited_token, inherited = await DuplicadosLotesService(
        db_session
    ).evaluar_y_reservar(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado", "autorizado"},
        grupo_ids=[int(group.id) for group in grupos],
        aceptacion_recibida=None,
        solicitante_nombre="Otro operador",
        reservar=False,
        ambiente=settings.arca_env,
    )
    await db_session.refresh(operation)
    generation_3 = await db_session.get(
        LoteDuplicadoEvidencia, int(operation.duplicados_generacion_id)
    )
    assert generation_3.id not in {generation_1.id, generation_2.id}
    assert inherited_token == token
    assert inherited is True
    assert (
        generation_3.aceptacion_id,
        generation_3.aceptada_por_usuario_id,
        generation_3.aceptada_por_nombre,
        generation_3.aceptada_at,
    ) == accepted_audit
    assert generation_3.aceptacion_origen_generacion_id == generation_2.id

    preflight = await DuplicadosLotesService(db_session).revalidar_operacion_lote(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
    )
    assert preflight["_duplicados_generacion_id"] == generation_3.id
    grupos[0].comprobante_ref += "-posterior-al-preflight"
    await db_session.commit()
    still_valid = await DuplicadosLotesService(db_session).revalidar_operacion_lote(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
    )
    assert still_valid["_duplicados_generacion_id"] == generation_3.id
    await db_session.commit()
    _, _, accepted = await DuplicadosLotesService(db_session).evaluar_y_reservar(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado", "autorizado"},
        grupo_ids=[int(group.id) for group in grupos],
        aceptacion_recibida=None,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    await db_session.refresh(operation)
    generation_4_id = int(operation.duplicados_generacion_id)
    assert generation_4_id != generation_3.id
    assert accepted is True

    grupos[0].estado = "autorizado"
    await db_session.commit()
    _, _, accepted = await DuplicadosLotesService(db_session).evaluar_y_reservar(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado", "autorizado"},
        grupo_ids=[int(group.id) for group in grupos],
        aceptacion_recibida=None,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    await db_session.refresh(operation)
    assert accepted is True
    assert operation.duplicados_generacion_id == generation_4_id


@pytest.mark.asyncio
@pytest.mark.parametrize("tampering", ["ambiente", "formato", "relacion", "origen"])
async def test_preflight_generacional_falla_cerrado_ante_manipulacion(
    tampering: str,
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre=f"generacion-alterada-{tampering}.xlsx",
        cantidad=2,
    )
    grupos = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == lote_id)
        )
    )
    for group in grupos:
        group.identidad_documento_hash = "8" * 64
    await db_session.commit()
    operation, generation, _, _ = await _publicar_generacion_real_de_prueba(
        db_session,
        empresa_id=int(test_empresa.id),
        lote_id=lote_id,
        grupos=grupos,
        idempotency_key=f"pf13-alterada-{tampering}",
        aceptar=True,
    )
    if tampering == "ambiente":
        generation.ambiente = (
            "produccion" if generation.ambiente == "homologacion" else "homologacion"
        )
    elif tampering == "formato":
        generation.formato = "duplicados_relacion/desconocido"
    elif tampering == "origen":
        generation.aceptacion_origen_generacion_id = 999999
    else:
        member = await db_session.scalar(
            select(LoteDuplicadoCoincidenciaMiembro)
            .join(LoteDuplicadoCoincidencia)
            .where(LoteDuplicadoCoincidencia.generacion_id == generation.id)
            .limit(1)
        )
        assert member is not None
        member.snapshot_json = {
            **member.snapshot_json,
            "detalle": {"alterado": True},
        }
    with pytest.raises(DuplicadosLotePreflightCambioError):
        await DuplicadosLotesService(db_session).revalidar_operacion_lote(
            operacion_id=int(operation.id),
            lote_id=lote_id,
            empresa_id=int(test_empresa.id),
        )
    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("tampering", ["bloque", "miembro"])
async def test_get_detalle_valida_integridad_durable_antes_de_paginar(
    tampering: str,
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre=f"detalle-integridad-{tampering}.xlsx",
        cantidad=2,
    )
    grupos = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == lote_id)
        )
    )
    for group in grupos:
        group.identidad_documento_hash = "6" * 64
    await db_session.commit()
    _operation, generation, _, _ = await _publicar_generacion_real_de_prueba(
        db_session,
        empresa_id=int(test_empresa.id),
        lote_id=lote_id,
        grupos=grupos,
        idempotency_key=f"pf13-detalle-integridad-{tampering}",
        aceptar=True,
    )
    url = f"/api/lotes-comprobantes/{lote_id}/coincidencias"
    healthy = await client.get(
        url,
        params={"evidencia_id": generation.evidencia_id, "per_page": 10},
        headers=auth_headers,
    )
    assert healthy.status_code == 200, healthy.text

    block = await db_session.scalar(
        select(LoteDuplicadoCoincidencia)
        .where(LoteDuplicadoCoincidencia.generacion_id == generation.id)
        .limit(1)
    )
    assert block is not None
    if tampering == "bloque":
        block.snapshot_json = {**block.snapshot_json, "alterado": True}
    else:
        member = await db_session.scalar(
            select(LoteDuplicadoCoincidenciaMiembro)
            .where(LoteDuplicadoCoincidenciaMiembro.bloque_id == block.id)
            .limit(1)
        )
        assert member is not None
        member.snapshot_json = {**member.snapshot_json, "alterado": True}
    await db_session.commit()
    page_calls = 0

    async def prohibit_page(*_args, **_kwargs):
        nonlocal page_calls
        page_calls += 1
        raise AssertionError("la página no debe leerse antes de validar integridad")

    monkeypatch.setattr(
        DuplicadosLotesService,
        "_pagina_generacion",
        prohibit_page,
    )
    corrupted = await client.get(
        url,
        params={"evidencia_id": generation.evidencia_id, "per_page": 10},
        headers=auth_headers,
    )
    assert corrupted.status_code == 409, corrupted.text
    assert corrupted.json()["detail"]["categoria_error"] == (
        "duplicados_coordinacion_error"
    )
    assert page_calls == 0


@pytest.mark.asyncio
async def test_herencia_aceptacion_rechaza_origen_de_otra_raiz(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="generaciones-raices.xlsx",
        cantidad=2,
    )
    grupos = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == lote_id)
        )
    )
    for group in grupos:
        group.identidad_documento_hash = "7" * 64
    await db_session.commit()
    _, generation_1, _, _ = await _publicar_generacion_real_de_prueba(
        db_session,
        empresa_id=int(test_empresa.id),
        lote_id=lote_id,
        grupos=grupos,
        idempotency_key="pf13-raiz-aceptada-1",
        aceptar=True,
    )
    operation_2, generation_2, _, _ = await _publicar_generacion_real_de_prueba(
        db_session,
        empresa_id=int(test_empresa.id),
        lote_id=lote_id,
        grupos=grupos,
        idempotency_key="pf13-raiz-aceptada-2",
        aceptar=True,
    )
    generation_2.aceptacion_id = generation_1.aceptacion_id
    generation_2.aceptada_por_usuario_id = generation_1.aceptada_por_usuario_id
    generation_2.aceptada_por_nombre = generation_1.aceptada_por_nombre
    generation_2.aceptada_at = generation_1.aceptada_at
    generation_2.aceptacion_origen_generacion_id = generation_1.id
    with pytest.raises(DuplicadosLotePreflightCambioError):
        await DuplicadosLotesService(db_session).revalidar_operacion_lote(
            operacion_id=int(operation_2.id),
            lote_id=lote_id,
            empresa_id=int(test_empresa.id),
        )
    await db_session.rollback()


@pytest.mark.asyncio
async def test_g1_intento_x_y_evidencia_nueva_publica_g2_sin_habilitar_y(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="generaciones-g1-g2.xlsx",
        cantidad=2,
    )
    grupos = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo)
            .where(LoteComprobanteGrupo.lote_id == lote_id)
            .order_by(LoteComprobanteGrupo.id)
        )
    )
    x, y = grupos
    for group in grupos:
        group.identidad_documento_hash = "6" * 64
    await db_session.commit()
    (
        operation,
        generation_1,
        control_1,
        token_1,
    ) = await _publicar_generacion_real_de_prueba(
        db_session,
        empresa_id=int(test_empresa.id),
        lote_id=lote_id,
        grupos=grupos,
        idempotency_key="pf13-g1-x-g2-y",
        aceptar=True,
    )
    assert token_1 is not None
    assert control_1["estado"] == "aceptada"
    accepted_audit = (
        generation_1.aceptacion_id,
        generation_1.aceptada_por_usuario_id,
        generation_1.aceptada_por_nombre,
        generation_1.aceptada_at,
    )
    preflight = await DuplicadosLotesService(db_session).revalidar_operacion_lote(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
    )
    generation_validated_id = int(preflight["_duplicados_generacion_id"])
    assert generation_validated_id == generation_1.id
    await db_session.commit()
    intento_x = await _crear_intento_sintetico_con_generacion(
        db_session,
        operation=operation,
        group=x,
        generation_id=generation_validated_id,
        punto_venta=test_punto_venta,
    )
    intento_x_id = int(intento_x.id)
    guarda_x = await db_session.get(
        PuntoVentaGuardaEmisionRece, int(intento_x.guarda_rece_id)
    )
    assert guarda_x is not None
    guarda_x.fase = "arca_iniciada"
    guarda_x.arca_iniciada_en = datetime.utcnow()
    await db_session.commit()
    respuesta_x = EmitirComprobanteResponse(
        exito=True,
        tipo_comprobante=int(x.tipo_comprobante),
        punto_venta=int(x.punto_venta_numero),
        numero=int(intento_x.numero_planificado),
        fecha=EmitirComprobanteRequest.model_validate(
            x.payload_json or {}
        ).fecha_emision,
        cae="12345678901234",
        cae_vencimiento=date(2099, 12, 31),
        total=Decimal(str(intento_x.total)),
        mensaje="Autorización ARCA sintética; no se realizó ninguna llamada real.",
    )
    x.estado = "autorizado"
    x.cae = respuesta_x.cae
    x.numero_asignado = respuesta_x.numero
    await FacturacionService(db_session)._persistir_intento_y_guarda_rece(
        idempotencia=IdempotenciaFiscalService(db_session),
        intento=intento_x,
        respuesta=respuesta_x,
        guarda=guarda_x,
        fase="cerrada_terminal",
        commit=True,
        contexto="prueba_g1_x_autorizado",
    )
    intento_x = await db_session.get(IntentoEmisionFiscal, intento_x_id)
    guarda_x = await db_session.get(
        PuntoVentaGuardaEmisionRece, int(intento_x.guarda_rece_id)
    )
    assert intento_x.estado == "autorizado"
    assert intento_x.duplicados_generacion_id == generation_1.id
    assert guarda_x is not None and guarda_x.fase == "cerrada_terminal"

    _, same_token, accepted_after_x = await DuplicadosLotesService(
        db_session
    ).evaluar_y_reservar(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado", "autorizado"},
        grupo_ids=[int(x.id), int(y.id)],
        aceptacion_recibida=None,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    await db_session.refresh(operation)
    assert operation.duplicados_generacion_id == generation_1.id
    assert same_token == token_1
    assert accepted_after_x is True

    previous_lot = LoteComprobante(
        empresa_id=int(test_empresa.id),
        nombre_archivo="antecedente-nuevo-y.xlsx",
        archivo_hash="5" * 64,
        estado="procesado",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
    )
    db_session.add(previous_lot)
    await db_session.flush()
    previous_group = LoteComprobanteGrupo(
        lote_id=int(previous_lot.id),
        empresa_id=int(y.empresa_id),
        comprobante_ref="ANTERIOR-Y",
        orden=1,
        estado="autorizado",
        tipo_comprobante=y.tipo_comprobante,
        punto_venta_numero=y.punto_venta_numero,
        cliente_documento=y.cliente_documento,
        cliente_razon_social=y.cliente_razon_social,
        total_estimado=y.total_estimado,
        payload_json=deepcopy(y.payload_json),
        duplicados_version=y.duplicados_version,
        duplicados_cobertura=y.duplicados_cobertura,
        huella_fiscal_completa=y.huella_fiscal_completa,
        identidad_nombre_hash=y.identidad_nombre_hash,
        identidad_documento_hash=y.identidad_documento_hash,
        identidad_nombre_original=y.identidad_nombre_original,
        identidad_tipo_documento_original=y.identidad_tipo_documento_original,
        identidad_numero_documento_original=y.identidad_numero_documento_original,
        fecha_emision_normalizada=y.fecha_emision_normalizada,
        moneda_duplicados=y.moneda_duplicados,
        cotizacion_duplicados=y.cotizacion_duplicados,
        total_centavos=y.total_centavos,
        punto_venta_id=y.punto_venta_id,
        ambiente=y.ambiente,
        punto_venta_elegibilidad_revision_id=y.punto_venta_elegibilidad_revision_id,
        punto_venta_revision_fiscal=y.punto_venta_revision_fiscal,
    )
    db_session.add(previous_group)
    await db_session.commit()

    with pytest.raises(DuplicadosLotePreflightCambioError):
        await DuplicadosLotesService(db_session).revalidar_operacion_lote(
            operacion_id=int(operation.id),
            lote_id=lote_id,
            empresa_id=int(test_empresa.id),
        )
    await db_session.commit()
    control_2, token_2, accepted_2 = await DuplicadosLotesService(
        db_session
    ).evaluar_y_reservar(
        operacion_id=int(operation.id),
        lote_id=lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado", "autorizado"},
        grupo_ids=[int(x.id), int(y.id)],
        aceptacion_recibida=None,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    await db_session.refresh(operation)
    generation_2 = await db_session.get(
        LoteDuplicadoEvidencia, int(operation.duplicados_generacion_id)
    )
    assert generation_2.id != generation_1.id
    assert control_2["evidencia_id"] != control_1["evidencia_id"]
    assert token_2 not in {None, token_1}
    assert accepted_2 is False
    assert (
        generation_1.aceptacion_id,
        generation_1.aceptada_por_usuario_id,
        generation_1.aceptada_por_nombre,
        generation_1.aceptada_at,
    ) == accepted_audit
    intento_x = await db_session.get(IntentoEmisionFiscal, intento_x_id)
    assert intento_x.duplicados_generacion_id == generation_1.id
    assert (
        await db_session.scalar(
            select(func.count(IntentoEmisionFiscal.id)).where(
                IntentoEmisionFiscal.grupo_id == y.id
            )
        )
        == 0
    )


def test_modelo_declara_fks_generacionales_con_clausura_fiscal() -> None:
    pointer_fks = {
        fk.constraint.name: fk
        for fk in OperacionIdempotente.__table__.foreign_keys
        if fk.parent.name == "duplicados_generacion_id"
    }
    pointer = pointer_fks["fk_operaciones_idempotentes_duplicados_generacion"]
    assert pointer.target_fullname == "lotes_duplicados_evidencias.id"
    assert pointer.ondelete == "SET NULL"
    attempt_fk = next(
        constraint
        for constraint in IntentoEmisionFiscal.__table__.foreign_key_constraints
        if constraint.name == "fk_intento_duplicados_generacion_scope"
    )
    assert attempt_fk.ondelete == "RESTRICT"
    assert {element.parent.name for element in attempt_fk.elements} == {
        "duplicados_generacion_id",
        "operacion_id",
        "empresa_id",
        "lote_id",
        "ambiente",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "contaminacion",
    [
        "orm_flush",
        "core_update",
        "orm_pendiente",
        "sql_desconocido",
        "driver_sql_dml",
    ],
)
async def test_frontera_http_duplicados_falla_cerrada_ante_transaccion_no_lectora(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    contaminacion: str,
):
    """La API no descarta ni confirma DML ajeno para abrir su sección crítica."""
    empresa_id = int(test_empresa.id)
    validation = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "frontera-transaccional.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validation.status_code == 200, validation.text
    lote_id = validation.json()["lote"]["id"]
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=f"pf13-frontera-{contaminacion}",
    )
    original = LoteComprobantesService.obtener_resumen_operativo_lote

    async def contaminar(self, *args, **kwargs):
        result = await original(self, *args, **kwargs)
        if contaminacion == "core_update":
            await self.db.execute(
                update(Empresa)
                .where(Empresa.id == empresa_id)
                .values(razon_social="Cambio Core no autorizado")
            )
        elif contaminacion == "sql_desconocido":
            await self.db.execute(text("SELECT 1"))
        elif contaminacion == "driver_sql_dml":
            connection = await self.db.connection()
            await connection.exec_driver_sql(
                "UPDATE empresas SET razon_social = ? WHERE id = ?",
                ("Cambio driver SQL no autorizado", empresa_id),
            )
        else:
            empresa = await self.db.get(Empresa, empresa_id)
            empresa.razon_social = "Cambio ORM no autorizado"
            if contaminacion == "orm_flush":
                await self.db.flush()
        return result

    llamadas_fiscales = 0

    async def no_emitir(*_args, **_kwargs):
        nonlocal llamadas_fiscales
        llamadas_fiscales += 1
        raise AssertionError("No debe alcanzarse la emisión fiscal")

    monkeypatch.setattr(
        LoteComprobantesService,
        "obtener_resumen_operativo_lote",
        contaminar,
    )
    monkeypatch.setattr(FacturacionService, "emitir_comprobante", no_emitir)

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )

    assert response.status_code == 409, response.text
    assert (
        response.json()["detail"]["categoria_error"]
        == "duplicado_coordinacion_transaccional"
    )
    assert llamadas_fiscales == 0
    await db_session.rollback()
    empresa = await db_session.get(Empresa, empresa_id, populate_existing=True)
    assert empresa.razon_social == "Empresa Test S.A."


async def _validar_multi_para_duplicados(
    client: AsyncClient,
    auth_headers: dict,
    empresa_cuit: str,
    *,
    nombre: str,
    cantidad: int,
    anonimo: bool = False,
) -> int:
    workbook = load_workbook(
        BytesIO(_build_lote_excel_multi_grupo(empresa_cuit, cantidad))
    )
    sheet = workbook["Comprobantes"]
    for row in range(2, cantidad + 2):
        sheet.cell(
            row=row, column=1
        ).value = f"{sheet.cell(row=row, column=1).value}-{nombre}"
        if anonimo:
            sheet.cell(row=row, column=7).value = "CI"
            sheet.cell(row=row, column=8).value = ""
            sheet.cell(row=row, column=9).value = "Consumidor Final"
            sheet.cell(row=row, column=10).value = "Consumidor Final"
    stream = BytesIO()
    workbook.save(stream)
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                nombre,
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    return int(response.json()["lote"]["id"])


@pytest.mark.asyncio
async def test_lote_anonimo_uno_contra_cien_no_es_igualdad_completa(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un único ítem coincidente no convierte un lote previo de cien en duplicado."""
    previo_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="anonimo-previo-cien.xlsx",
        cantidad=100,
        anonimo=True,
    )
    actual_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="anonimo-actual-uno.xlsx",
        cantidad=1,
        anonimo=True,
    )
    grupos_previos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == previo_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    for grupo in grupos_previos:
        grupo.estado = "autorizado"
    operacion = OperacionIdempotente(
        empresa_id=test_empresa.id,
        idempotency_key="pf13-anonimo-seleccion-cien",
        tipo_operacion="procesar_lote",
        payload_hash="9" * 64,
        estado="finalizado",
        lote_id=previo_id,
        duplicados_version="duplicados_lotes/v2",
        control_duplicados_json={
            "evidencia_id": "v2.cien",
            "seleccion_original": [
                {
                    "grupo_id": int(grupo.id),
                    "huella": grupo.huella_fiscal_completa,
                    "nombre_hash": grupo.identidad_nombre_hash,
                    "documento_hash": grupo.identidad_documento_hash,
                }
                for grupo in grupos_previos
            ],
        },
    )
    db_session.add(operacion)
    await db_session.flush()
    linked_comprobante_id = await _persistir_comprobante_autorizado(
        db_session,
        test_empresa,
        test_punto_venta,
        tipo_comprobante=6,
        numero=801,
        fecha_emision=FECHA_FISCAL_CONTROLADA_PF19B,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 8, 20),
        total=Decimal("1210.00"),
    )
    individual_comprobante_id = await _persistir_comprobante_autorizado(
        db_session,
        test_empresa,
        test_punto_venta,
        tipo_comprobante=6,
        numero=802,
        fecha_emision=FECHA_FISCAL_CONTROLADA_PF19B,
        cae=CAE_TEST_NO_REAL_ALT,
        cae_vencimiento=date(2026, 8, 20),
        total=Decimal("1210.00"),
    )
    testigo_grupo = grupos_previos[0]
    db_session.add(
        IntentoEmisionFiscal(
            operacion_id=int(operacion.id),
            empresa_id=int(test_empresa.id),
            usuario_id=None,
            punto_venta_id=int(test_punto_venta.id),
            punto_venta_numero=int(test_punto_venta.numero),
            tipo_comprobante=int(testigo_grupo.tipo_comprobante),
            numero_planificado=801,
            fecha_emision=testigo_grupo.fecha_emision_normalizada,
            total=Decimal("1210.00"),
            receptor_tipo_documento=99,
            receptor_numero_documento="0",
            receptor_razon_social="A CONSUMIDOR FINAL",
            payload_hash="c" * 64,
            huella_logica="d" * 64,
            estado="autorizado",
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 8, 20),
            comprobante_id=linked_comprobante_id,
            lote_id=previo_id,
            grupo_id=int(testigo_grupo.id),
        )
    )
    await db_session.commit()
    linked = await db_session.get(Comprobante, linked_comprobante_id)
    individual = await db_session.get(Comprobante, individual_comprobante_id)
    assert linked is not None
    assert individual is not None
    matches = [linked]

    async def buscar_matches(*_args, **_kwargs):
        return list(matches)

    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "buscar_duplicados_logicos_lote",
        buscar_matches,
    )

    control = await DuplicadosLotesService(db_session).calcular_control(
        lote_id=actual_id,
        empresa_id=int(inspect(test_empresa).identity[0]),
        estados={"validado"},
    )

    assert control["estado"] == "sin_coincidencias"
    assert control["tipos_coincidencia"] == []
    assert control["cantidad_afectada"] == 0

    matches.append(individual)
    control = await DuplicadosLotesService(db_session).calcular_control(
        lote_id=actual_id,
        empresa_id=int(inspect(test_empresa).identity[0]),
        estados={"validado"},
    )
    assert control["estado"] == "requiere_confirmacion"
    assert control["cantidad_afectada"] == 1
    assert {
        antecedente["comprobante_ref"]
        for antecedente in control["antecedentes_resumen"]
        if antecedente["origen"] == "comprobante_individual"
    } == {f"comprobante-{individual_comprobante_id}"}


@pytest.mark.asyncio
async def test_resumen_y_revalidacion_usan_relacion_sin_construir_dtos(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    previo_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="relacion-previa-cuatro.xlsx",
        cantidad=4,
    )
    actual_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="relacion-actual-tres.xlsx",
        cantidad=3,
    )
    previos = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo)
            .where(LoteComprobanteGrupo.lote_id == previo_id)
            .order_by(LoteComprobanteGrupo.id)
        )
    )
    actuales = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo)
            .where(LoteComprobanteGrupo.lote_id == actual_id)
            .order_by(LoteComprobanteGrupo.id)
        )
    )
    for indice, grupo in enumerate(previos):
        grupo.estado = "autorizado"
        grupo.identidad_documento_hash = "d" * 64
        grupo.identidad_nombre_hash = hashlib.sha256(
            f"previo-{indice}".encode()
        ).hexdigest()
    for indice, grupo in enumerate(actuales):
        grupo.identidad_documento_hash = "d" * 64
        grupo.identidad_nombre_hash = hashlib.sha256(
            f"actual-{indice}".encode()
        ).hexdigest()
    await db_session.commit()

    def prohibir_dto(**_kwargs):
        raise AssertionError("Resumen/revalidación no deben construir DTOs de detalle")

    monkeypatch.setattr(
        DuplicadosLotesService,
        "_armar_detalle_compacto",
        prohibir_dto,
    )
    service = DuplicadosLotesService(db_session)
    resumen = await service.calcular_control(
        lote_id=actual_id,
        empresa_id=int(test_empresa.id),
        estados={"validado"},
        incluir_interno=True,
    )
    assert resumen["cantidad_actual"] == 3
    assert resumen["cantidad_afectada"] == 3
    assert resumen["evidencia_id"] is not None
    assert "_coincidencias" not in resumen
    assert "_detalle_total" not in resumen
    bloque_historico = next(
        bloque
        for bloque in resumen["_bloques"].values()
        if bloque["clase"] == "parcial_documento"
    )
    miembros = list(bloque_historico["miembros"].values())
    assert sum(item["lado"] == "actual" for item in miembros) == 3
    assert sum(item["lado"] == "anterior" for item in miembros) == 4
    antecedente = next(
        item for item in resumen["antecedentes_resumen"] if item["lote_id"] == previo_id
    )
    assert antecedente["cantidad_coincidente"] == 3
    assert antecedente["cantidad_autorizada"] == 4

    operation, generation, _, _ = await _publicar_generacion_real_de_prueba(
        db_session,
        empresa_id=int(test_empresa.id),
        lote_id=actual_id,
        grupos=actuales,
        idempotency_key="pf13-h2-relacion-sin-dto",
        aceptar=True,
    )
    revalidated = await service.revalidar_operacion_lote(
        operacion_id=int(operation.id),
        lote_id=actual_id,
        empresa_id=int(test_empresa.id),
    )
    assert revalidated["evidencia_id"] == generation.evidencia_id


@pytest.mark.asyncio
async def test_detalle_parcial_no_retiene_expansion_en_resumen_ni_pagina_profunda(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_count = 42
    current_count = 41
    previo_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="recursos-previo-cuarenta-y-dos.xlsx",
        cantidad=previous_count,
    )
    actual_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="recursos-actual-cuarenta-y-uno.xlsx",
        cantidad=current_count,
    )
    empresa_id = int(inspect(test_empresa).identity[0])
    await db_session.execute(
        update(LoteComprobanteGrupo)
        .where(LoteComprobanteGrupo.lote_id == previo_id)
        .values(estado="autorizado", identidad_documento_hash="b" * 64)
    )
    await db_session.execute(
        update(LoteComprobanteGrupo)
        .where(LoteComprobanteGrupo.lote_id == actual_id)
        .values(identidad_documento_hash="b" * 64)
    )
    await db_session.commit()

    service = DuplicadosLotesService(db_session)
    resumen = await service.calcular_control(
        lote_id=actual_id,
        empresa_id=empresa_id,
        estados={"validado"},
        incluir_interno=True,
    )

    assert "_detalle_total" not in resumen
    assert "_coincidencias" not in resumen
    total_agregado = sum(
        service._total_bloque_compacto(block) for block in resumen["_bloques"].values()
    )
    parcial = next(
        block
        for block in resumen["_bloques"].values()
        if block["clase"] == "parcial_documento"
    )
    assert (
        service._total_bloque_compacto(parcial)
        == (current_count * previous_count) - current_count
    )
    assert total_agregado == ((current_count * previous_count) - current_count) + (
        2 * current_count
    )
    construidos = 0
    maximo_heap = 0
    cursores = []
    opciones_stream = []
    binds_por_consulta = []
    activos = 0
    maximo_activos = 0
    original = service._armar_detalle_compacto
    original_heappush = duplicados_lotes_module.heapq.heappush
    original_heapreplace = duplicados_lotes_module.heapq.heapreplace
    original_stream = db_session.stream

    class CursorObservado:
        def __init__(self, cursor):
            nonlocal activos, maximo_activos
            self.cursor = cursor
            self.closed = False
            activos += 1
            maximo_activos = max(maximo_activos, activos)

        def mappings(self):
            return self.cursor.mappings()

        async def close(self):
            nonlocal activos
            if not self.closed:
                await self.cursor.close()
                self.closed = True
                activos -= 1

    def contar_dto(**kwargs):
        nonlocal construidos
        construidos += 1
        return original(**kwargs)

    def observar_heap(heap, item):
        nonlocal maximo_heap
        original_heappush(heap, item)
        maximo_heap = max(maximo_heap, len(heap))

    def observar_reemplazo(heap, item):
        nonlocal maximo_heap
        result = original_heapreplace(heap, item)
        maximo_heap = max(maximo_heap, len(heap))
        return result

    async def observar_stream(statement, *args, **kwargs):
        opciones_stream.append(statement.get_execution_options())
        compiled = statement.compile(dialect=db_session.bind.sync_engine.dialect)
        binds_por_consulta.append(
            len(compiled.positiontup)
            if compiled.positiontup is not None
            else len(compiled.params)
        )
        result = await original_stream(statement, *args, **kwargs)
        observado = CursorObservado(result)
        cursores.append(observado)
        return observado

    monkeypatch.setattr(service, "_armar_detalle_compacto", contar_dto)
    monkeypatch.setattr(duplicados_lotes_module.heapq, "heappush", observar_heap)
    monkeypatch.setattr(
        duplicados_lotes_module.heapq, "heapreplace", observar_reemplazo
    )
    monkeypatch.setattr(db_session, "stream", observar_stream)
    _, items, total = await service.obtener_detalle(
        lote_id=actual_id,
        empresa_id=empresa_id,
        evidencia_id=resumen["evidencia_id"],
        page=total_agregado,
        per_page=1,
    )
    assert total == total_agregado
    assert len(items) == 1
    assert construidos == 1
    particiones = sum(
        1
        for block in resumen["_bloques"].values()
        for _ in service._consultas_bloque_vivo(block)
    )
    assert particiones > len(resumen["_bloques"])
    assert len(cursores) > particiones
    assert maximo_activos == 1
    assert activos == 0
    assert maximo_heap <= service._live_member_buffer()
    assert max(binds_por_consulta) <= duplicados_lotes_module.READ_PARAMETER_BUFFER
    assert all(option["yield_per"] == 1 for option in opciones_stream)
    assert all(option["max_row_buffer"] == 1 for option in opciones_stream)
    assert all(cursor.closed for cursor in cursores)


@pytest.mark.asyncio
async def test_pagina_viva_cierra_cursor_si_falla_el_consumo(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = DuplicadosLotesService(db_session)
    member = {
        "lado": "actual",
        "miembro_clave": "g-1",
        "grupo_id": 1,
        "comprobante_id": None,
        "nombre_hash": "a" * 64,
        "documento_hash": None,
        "ordinal": None,
        "relevancia": "actual",
        "snapshot": {},
    }
    block = {
        "bloque_clave": "cierre-excepcion",
        "clase": "interna_nombre",
        "antecedente_clave": None,
        "snapshot": {
            "origen": "lote",
            "tipo_coincidencia": "interna_receptor",
            "campos_coincidentes": ["nombre"],
        },
        "miembros": {("actual", "g-1"): member},
    }
    original_stream = db_session.stream
    active = 0

    class CursorObservado:
        def __init__(self, cursor):
            nonlocal active
            self.cursor = cursor
            self.closed = False
            active += 1

        def mappings(self):
            return self.cursor.mappings()

        async def close(self):
            nonlocal active
            if not self.closed:
                await self.cursor.close()
                self.closed = True
                active -= 1

    async def observe_stream(statement, *args, **kwargs):
        return CursorObservado(await original_stream(statement, *args, **kwargs))

    def fail_key(_row):
        raise RuntimeError("fallo sintético durante el consumo")

    monkeypatch.setattr(db_session, "stream", observe_stream)
    monkeypatch.setattr(service, "_clave_orden_publico", fail_key)
    with pytest.raises(RuntimeError, match="fallo sintético"):
        await service._pagina_relacion_viva(
            {"_bloques": {block["bloque_clave"]: block}},
            offset=0,
            limit=1,
        )
    assert active == 0


@pytest.mark.asyncio
async def test_comparacion_historica_usa_seleccion_original_y_no_lote_fisico_completo(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una operación previa X+Y no se mezcla con Z sólo por compartir lote físico."""
    previo_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="previo-xyz.xlsx",
        cantidad=3,
    )
    actual_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="actual-xy.xlsx",
        cantidad=2,
    )
    empresa_id = int(inspect(test_empresa).identity[0])
    previos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == previo_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    for grupo in previos:
        grupo.estado = "autorizado"
    operacion_previa = OperacionIdempotente(
        empresa_id=empresa_id,
        idempotency_key="pf13-seleccion-previa-xy",
        tipo_operacion="procesar_lote",
        payload_hash="a" * 64,
        estado="finalizado",
        lote_id=previo_id,
        duplicados_version="duplicados_lotes/v2",
        control_duplicados_json={
            "evidencia_id": "v2.previa",
            "seleccion_original": [
                {
                    "grupo_id": int(grupo.id),
                    "huella": grupo.huella_fiscal_completa,
                    "nombre_hash": grupo.identidad_nombre_hash,
                    "documento_hash": grupo.identidad_documento_hash,
                }
                for grupo in previos[:2]
            ],
        },
        solicitante_nombre_snapshot="Solicitante histórico",
        solicitud_emision_at=datetime(2026, 8, 9, 14, 0, tzinfo=timezone.utc),
    )
    db_session.add(operacion_previa)
    await db_session.flush()
    for indice, grupo in enumerate(previos[:2], start=1):
        db_session.add(
            IntentoEmisionFiscal(
                operacion_id=operacion_previa.id,
                empresa_id=empresa_id,
                usuario_id=None,
                punto_venta_id=grupo.punto_venta_id,
                punto_venta_numero=grupo.punto_venta_numero,
                tipo_comprobante=grupo.tipo_comprobante,
                numero_planificado=indice,
                fecha_emision=grupo.fecha_emision_normalizada,
                total=grupo.total_estimado,
                receptor_tipo_documento=96,
                receptor_numero_documento=str(30000000 + indice),
                receptor_razon_social=f"Cliente Lote {indice}",
                payload_hash=grupo.huella_fiscal_completa,
                huella_logica=grupo.huella_fiscal_completa,
                estado="autorizado",
                solicitante_nombre_snapshot="Solicitante histórico",
                solicitud_arca_at=datetime(2026, 8, 9, 14, indice, tzinfo=timezone.utc),
                resultado_fiscal_at=datetime(
                    2026, 8, 9, 14, indice, 30, tzinfo=timezone.utc
                ),
                lote_id=previo_id,
                grupo_id=grupo.id,
            )
        )
    await db_session.commit()
    db_session.expire_all()

    control = await DuplicadosLotesService(db_session).calcular_control(
        lote_id=actual_id,
        empresa_id=empresa_id,
        estados={"validado"},
    )

    antecedentes = [
        item for item in control["antecedentes_resumen"] if item["lote_id"] == previo_id
    ]
    assert len(antecedentes) == 1
    assert antecedentes[0]["tipo_coincidencia"] == "historica_completa"
    assert antecedentes[0]["cantidad_lote_anterior"] == 2
    assert antecedentes[0]["cantidad_coincidente"] == 2
    assert antecedentes[0]["hora_confiable"] is True
    assert antecedentes[0]["emitido_desde"].isoformat() == ("2026-08-09T14:01:30+00:00")
    assert antecedentes[0]["solicitantes"] == [
        {
            "usuario_id": None,
            "nombre": "Solicitante histórico",
            "estado": "registrado",
        }
    ]
    detalle = await client.get(
        f"/api/lotes-comprobantes/{actual_id}/coincidencias",
        params={"evidencia_id": control["evidencia_id"]},
        headers=auth_headers,
    )
    assert detalle.status_code == 200, detalle.text
    marca = datetime.fromisoformat(
        detalle.json()["items"][0]["resultado_fiscal_at"].replace("Z", "+00:00")
    )
    assert marca.utcoffset() == timedelta(0)
    assert detalle.json()["items"][0]["hora_confiable"] is True

    intentos_antes = int(
        await db_session.scalar(select(func.count(IntentoEmisionFiscal.id))) or 0
    )
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=actual_id,
        estados={"validado"},
        idempotency_key="pf13-conflicto-historico-con-fechas",
    )
    conflicto = await client.post(
        f"/api/lotes-comprobantes/{actual_id}/procesar",
        headers={**auth_headers, **headers},
    )

    assert conflicto.status_code == 409, conflicto.text
    conflicto_json = conflicto.json()["detail"]
    assert conflicto_json["categoria_error"] == "duplicado_logico_lote"
    assert conflicto_json["aceptacion_id"].startswith("v2.")
    antecedente_http = next(
        item
        for item in conflicto_json["control_duplicados"]["antecedentes_resumen"]
        if item["lote_id"] == previo_id
    )
    assert datetime.fromisoformat(antecedente_http["emitido_desde"]) == datetime(
        2026, 8, 9, 14, 1, 30, tzinfo=timezone.utc
    )
    assert datetime.fromisoformat(antecedente_http["emitido_hasta"]) == datetime(
        2026, 8, 9, 14, 2, 30, tzinfo=timezone.utc
    )
    operacion_conflicto = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key
            == "pf13-conflicto-historico-con-fechas"
        )
    )
    assert operacion_conflicto is not None
    assert operacion_conflicto.response_json == conflicto_json
    intentos_despues = int(
        await db_session.scalar(select(func.count(IntentoEmisionFiscal.id))) or 0
    )
    assert intentos_despues == intentos_antes


@pytest.mark.asyncio
async def test_selecciones_parciales_conservan_raices_y_colapsan_continuaciones(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="raices-previo-abc.xlsx",
        cantidad=3,
    )
    current_lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="raices-actual-a.xlsx",
        cantidad=1,
    )
    previous_groups = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == previous_lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    current_group = await db_session.scalar(
        select(LoteComprobanteGrupo).where(
            LoteComprobanteGrupo.lote_id == current_lote_id
        )
    )
    for group in previous_groups:
        group.estado = "autorizado"

    def selection(*indexes: int) -> list[dict]:
        return DuplicadosLotesService._seleccion_material(
            [previous_groups[index] for index in indexes]
        )

    root_one = OperacionIdempotente(
        empresa_id=int(test_empresa.id),
        idempotency_key="pf13-h2-raiz-uno",
        tipo_operacion="procesar_lote",
        payload_hash="1" * 64,
        estado="finalizado",
        lote_id=previous_lote_id,
        duplicados_version="duplicados_lotes/v2",
        control_duplicados_json={"seleccion_original": selection(0, 1)},
    )
    root_two = OperacionIdempotente(
        empresa_id=int(test_empresa.id),
        idempotency_key="pf13-h2-raiz-dos",
        tipo_operacion="procesar_lote",
        payload_hash="2" * 64,
        estado="finalizado",
        lote_id=previous_lote_id,
        duplicados_version="duplicados_lotes/v2",
        control_duplicados_json={"seleccion_original": selection(0, 2)},
    )
    db_session.add_all([root_one, root_two])
    await db_session.flush()
    continuation = OperacionIdempotente(
        empresa_id=int(test_empresa.id),
        idempotency_key="pf13-h2-raiz-uno-continuacion",
        tipo_operacion="procesar_lote",
        payload_hash="3" * 64,
        estado="finalizado",
        lote_id=previous_lote_id,
        operacion_raiz_id=int(root_one.id),
        duplicados_version="duplicados_lotes/v2",
        control_duplicados_json={"seleccion_original": selection(0, 1)},
    )
    invalid_cross_lote = OperacionIdempotente(
        empresa_id=int(test_empresa.id),
        idempotency_key="pf13-h2-seleccion-cruzada-lote",
        tipo_operacion="procesar_lote",
        payload_hash="4" * 64,
        estado="finalizado",
        lote_id=previous_lote_id,
        duplicados_version="duplicados_lotes/v2",
        control_duplicados_json={
            "seleccion_original": DuplicadosLotesService._seleccion_material(
                [current_group]
            )
        },
    )
    db_session.add_all([continuation, invalid_cross_lote])
    await db_session.commit()

    service = DuplicadosLotesService(db_session)
    baseline = await service.calcular_control(
        lote_id=current_lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado"},
        incluir_interno=True,
    )
    selected_query_counts = []
    operation_windows = 0
    orm_peaks = {
        LoteComprobanteGrupo: 0,
        OperacionIdempotente: 0,
        IntentoEmisionFiscal: 0,
    }

    def observe_selected_members(
        _connection, _cursor, statement, parameters, _context, _many
    ):
        nonlocal operation_windows
        if (
            "lotes_comprobantes_grupos.id IN" in statement
            and "lotes_comprobantes_grupos.lote_id IN" not in statement
        ):
            selected_query_counts.append(len(parameters))
        if (
            "FROM operaciones_idempotentes" in statement
            and "control_duplicados_json" in statement
            and "LIMIT" in statement
        ):
            operation_windows += 1

    def observe_orm_load(session, _instance):
        for model in orm_peaks:
            orm_peaks[model] = max(
                orm_peaks[model],
                sum(isinstance(item, model) for item in session.identity_map.values()),
            )

    monkeypatch.setattr(duplicados_lotes_module, "READ_PARAMETER_BUFFER", 2)
    monkeypatch.setattr(duplicados_lotes_module, "HISTORICAL_READ_WINDOW", 1)
    db_session.expunge_all()
    sync_engine = db_session.bind.sync_engine
    event.listen(sync_engine, "before_cursor_execute", observe_selected_members)
    event.listen(db_session.sync_session, "loaded_as_persistent", observe_orm_load)
    try:
        control = await service.calcular_control(
            lote_id=current_lote_id,
            empresa_id=int(test_empresa.id),
            estados={"validado"},
            incluir_interno=True,
        )
    finally:
        event.remove(sync_engine, "before_cursor_execute", observe_selected_members)
        event.remove(db_session.sync_session, "loaded_as_persistent", observe_orm_load)

    assert service._publicable(control) == service._publicable(baseline)
    assert service._relacion_canonica(control, snapshot=True) == (
        service._relacion_canonica(baseline, snapshot=True)
    )
    baseline_page, baseline_total = await service._pagina_relacion_viva(
        baseline, offset=0, limit=100
    )
    partitioned_page, partitioned_total = await service._pagina_relacion_viva(
        control, offset=0, limit=100
    )
    assert partitioned_total == baseline_total
    assert partitioned_page == baseline_page
    assert len(selected_query_counts) >= 2
    assert max(selected_query_counts) <= 5
    assert operation_windows >= 4
    assert orm_peaks[OperacionIdempotente] == 0
    assert orm_peaks[IntentoEmisionFiscal] == 0
    assert orm_peaks[LoteComprobanteGrupo] <= 4

    antecedents = [
        item
        for item in control["antecedentes_resumen"]
        if item["lote_id"] == previous_lote_id
    ]
    assert len(antecedents) == 2
    assert {item["cantidad_lote_anterior"] for item in antecedents} == {2}
    assert {item["cantidad_coincidente"] for item in antecedents} == {1}
    root_keys = {
        block["antecedente_clave"]
        for block in control["_bloques"].values()
        if block["antecedente_clave"] is not None
    }
    assert len(root_keys) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("historical_lote_count", [8, 16])
async def test_historia_fisica_mantiene_pico_orm_por_frontera(
    historical_lote_count: int,
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre=f"volumen-actual-{historical_lote_count}.xlsx",
        cantidad=1,
    )
    current = await db_session.scalar(
        select(LoteComprobanteGrupo).where(
            LoteComprobanteGrupo.lote_id == current_lote_id
        )
    )
    assert current is not None
    expected_antecedent_keys = set()
    for index in range(historical_lote_count):
        lote = LoteComprobante(
            empresa_id=int(test_empresa.id),
            nombre_archivo=f"volumen-previo-{historical_lote_count}-{index}.xlsx",
            archivo_hash=hashlib.sha256(
                f"volumen-{historical_lote_count}-{index}".encode()
            ).hexdigest(),
            estado="completado",
            total_grupos=2,
            grupos_emitidos=1,
            grupos_fallidos=1,
        )
        db_session.add(lote)
        await db_session.flush()
        common = {
            "lote_id": int(lote.id),
            "empresa_id": int(test_empresa.id),
            "tipo_comprobante": current.tipo_comprobante,
            "punto_venta_id": current.punto_venta_id,
            "punto_venta_numero": current.punto_venta_numero,
            "ambiente": current.ambiente,
            "punto_venta_elegibilidad_revision_id": (
                current.punto_venta_elegibilidad_revision_id
            ),
            "punto_venta_revision_fiscal": current.punto_venta_revision_fiscal,
            "fecha_emision_normalizada": current.fecha_emision_normalizada,
            "moneda_duplicados": current.moneda_duplicados,
            "cotizacion_duplicados": current.cotizacion_duplicados,
            "total_estimado": current.total_estimado,
            "total_centavos": current.total_centavos,
            "duplicados_version": current.duplicados_version,
            "duplicados_cobertura": current.duplicados_cobertura,
        }
        matching_group = LoteComprobanteGrupo(
            **common,
            comprobante_ref=f"MATCH-{index}",
            orden=0,
            estado="autorizado",
            huella_fiscal_completa=current.huella_fiscal_completa,
            identidad_nombre_hash=current.identidad_nombre_hash,
            identidad_documento_hash=current.identidad_documento_hash,
        )
        db_session.add_all(
            [
                matching_group,
                LoteComprobanteGrupo(
                    **common,
                    comprobante_ref=f"AJENO-{index}",
                    orden=1,
                    estado="fallido",
                    huella_fiscal_completa=hashlib.sha256(
                        f"ajeno-{historical_lote_count}-{index}".encode()
                    ).hexdigest(),
                    identidad_nombre_hash=hashlib.sha256(
                        f"nombre-ajeno-{historical_lote_count}-{index}".encode()
                    ).hexdigest(),
                    identidad_documento_hash=hashlib.sha256(
                        f"documento-ajeno-{historical_lote_count}-{index}".encode()
                    ).hexdigest(),
                ),
            ]
        )
        await db_session.flush()
        expected_antecedent_keys.add(
            duplicados_lotes_module._sha256(
                {
                    "lote_id": int(lote.id),
                    "operacion_raiz_id": None,
                    "seleccion": [int(matching_group.id)],
                }
            )
        )
    await db_session.commit()
    service = DuplicadosLotesService(db_session)
    baseline = await service.calcular_control(
        lote_id=current_lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado"},
        incluir_interno=True,
    )
    db_session.expunge_all()
    peaks = {LoteComprobante: 0, LoteComprobanteGrupo: 0}

    def observe_load(session, _instance):
        for model in peaks:
            peaks[model] = max(
                peaks[model],
                sum(isinstance(item, model) for item in session.identity_map.values()),
            )

    monkeypatch.setattr(duplicados_lotes_module, "HISTORICAL_READ_WINDOW", 2)
    event.listen(db_session.sync_session, "loaded_as_persistent", observe_load)
    try:
        windowed = await service.calcular_control(
            lote_id=current_lote_id,
            empresa_id=int(test_empresa.id),
            estados={"validado"},
            incluir_interno=True,
        )
    finally:
        event.remove(db_session.sync_session, "loaded_as_persistent", observe_load)
    assert service._publicable(windowed) == service._publicable(baseline)
    assert service._relacion_canonica(windowed, snapshot=True) == (
        service._relacion_canonica(baseline, snapshot=True)
    )
    assert windowed["evidencia_id"] == baseline["evidencia_id"]
    baseline_page = await service._pagina_relacion_viva(baseline, offset=0, limit=100)
    windowed_page = await service._pagina_relacion_viva(windowed, offset=0, limit=100)
    assert windowed_page == baseline_page
    assert len(windowed["antecedentes_resumen"]) == historical_lote_count
    assert all(
        item["cantidad_lote_anterior"] == 2 and item["cantidad_coincidente"] == 1
        for item in windowed["antecedentes_resumen"]
    )
    assert {
        block["antecedente_clave"]
        for block in windowed["_bloques"].values()
        if block["antecedente_clave"] is not None
    } == expected_antecedent_keys
    assert peaks[LoteComprobante] <= 2
    assert peaks[LoteComprobanteGrupo] <= 3


@pytest.mark.asyncio
async def test_reserva_solo_publica_propietario_con_scope_acreditado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="scope-reserva.xlsx",
        cantidad=1,
    )
    group = await db_session.scalar(
        select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == lote_id)
    )
    other_lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="scope-reserva-otro-lote.xlsx",
        cantidad=1,
    )
    other_company = Empresa(
        razon_social="Empresa ajena sintética",
        cuit="20999999991",
        condicion_iva="RI",
        domicilio="Calle sintética 456",
        localidad="Ciudad de prueba",
        provincia="Buenos Aires",
        codigo_postal="1000",
        email="ajena@example.invalid",
        telefono="00000001",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(other_company)
    await db_session.flush()
    other_company_lote = LoteComprobante(
        empresa_id=int(other_company.id),
        nombre_archivo="scope-ajeno.xlsx",
        archivo_hash="9" * 64,
        estado="validado",
    )
    db_session.add(other_company_lote)
    await db_session.flush()

    async def owner(
        key: str,
        *,
        empresa_id: int,
        owner_lote_id: int,
        ambiente: str,
        nombre: str,
    ) -> OperacionIdempotente:
        operation = OperacionIdempotente(
            empresa_id=empresa_id,
            idempotency_key=key,
            tipo_operacion="procesar_lote",
            payload_hash=hashlib.sha256(key.encode()).hexdigest(),
            estado="en_proceso",
            lote_id=owner_lote_id,
            duplicados_version="duplicados_lotes/v2",
            solicitante_nombre_snapshot=nombre,
        )
        db_session.add(operation)
        await db_session.flush()
        generation = LoteDuplicadoEvidencia(
            operacion_id=int(operation.id),
            empresa_id=empresa_id,
            lote_id=owner_lote_id,
            ambiente=ambiente,
            generacion=1,
            formato="duplicados_relacion/1",
            evidencia_id=f"v2.{key}",
            snapshot_hash=hashlib.sha256(f"snapshot-{key}".encode()).hexdigest(),
            control_snapshot_json={"manifiesto": {"bloques": 0, "miembros": 0}},
        )
        db_session.add(generation)
        await db_session.flush()
        operation.duplicados_generacion_id = int(generation.id)
        await db_session.flush()
        return operation

    valid = await owner(
        "scope-valido",
        empresa_id=int(test_empresa.id),
        owner_lote_id=lote_id,
        ambiente=group.ambiente,
        nombre="Propietario válido",
    )
    wrong_lote = await owner(
        "scope-lote-ajeno",
        empresa_id=int(test_empresa.id),
        owner_lote_id=other_lote_id,
        ambiente=group.ambiente,
        nombre="No divulgar lote",
    )
    wrong_company = await owner(
        "scope-empresa-ajena",
        empresa_id=int(other_company.id),
        owner_lote_id=int(other_company_lote.id),
        ambiente=group.ambiente,
        nombre="No divulgar empresa",
    )
    wrong_environment = await owner(
        "scope-ambiente-ajeno",
        empresa_id=int(test_empresa.id),
        owner_lote_id=lote_id,
        ambiente=("produccion" if group.ambiente == "homologacion" else "homologacion"),
        nombre="No divulgar ambiente",
    )
    await db_session.commit()
    service = DuplicadosLotesService(db_session)

    group.duplicados_reserva_operacion_id = int(valid.id)
    valid_evidence = (await service._evidencia_por_grupo([group]))[int(group.id)]
    assert valid_evidence["operacion_id"] == int(valid.id)
    assert valid_evidence["nombre"] == "Propietario válido"
    assert valid_evidence["procedencia"] == "reserva_operacion_propietaria"

    for invalid in (wrong_lote, wrong_company, wrong_environment):
        group.duplicados_reserva_operacion_id = int(invalid.id)
        evidence = (await service._evidencia_por_grupo([group]))[int(group.id)]
        assert evidence == {
            "operacion_id": None,
            "usuario_id": None,
            "nombre": None,
            "solicitud_emision_at": None,
            "solicitud_arca_at": None,
            "resultado_fiscal_at": None,
            "procedencia": "reserva_no_acreditada",
        }

    group.duplicados_reserva_operacion_id = int(valid.id)
    synthetic = [
        SimpleNamespace(
            id=100000 + index,
            duplicados_reserva_operacion_id=None,
            estado="fallido",
        )
        for index in range(2100)
    ]
    parameter_counts = []

    def observe_parameters(
        _connection, _cursor, _statement, parameters, _context, _many
    ):
        parameter_counts.append(len(parameters))

    sync_engine = db_session.bind.sync_engine
    event.listen(sync_engine, "before_cursor_execute", observe_parameters)
    try:
        expanded_evidence = await service._evidencia_por_grupo([group, *synthetic])
    finally:
        event.remove(sync_engine, "before_cursor_execute", observe_parameters)
    assert expanded_evidence == {int(group.id): valid_evidence}
    assert max(parameter_counts) <= duplicados_lotes_module.READ_PARAMETER_BUFFER
    assert parameter_counts == [1]


@pytest.mark.asyncio
async def test_completa_cien_conserva_ordinales_antes_de_filtrar_relevancia(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    previous_lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="completa-previa-cien.xlsx",
        cantidad=100,
    )
    current_lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="completa-actual-cien.xlsx",
        cantidad=100,
    )
    previous_groups = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == previous_lote_id)
                .order_by(LoteComprobanteGrupo.id)
            )
        ).all()
    )
    current_groups = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == current_lote_id)
                .order_by(LoteComprobanteGrupo.id)
            )
        ).all()
    )
    authorized_ordinals = set(range(0, 100, 5))
    relevant_ordinals = authorized_ordinals | {1, 3}
    for ordinal, group in enumerate(previous_groups):
        group.huella_fiscal_completa = "8" * 64
        group.estado = (
            "autorizado"
            if ordinal in authorized_ordinals
            else "requiere_reconciliacion"
            if ordinal == 3
            else "fallido"
        )
        if ordinal == 1:
            group.duplicados_reserva_operacion_id = 999999
    for group in current_groups:
        group.huella_fiscal_completa = "8" * 64
    await db_session.commit()
    service = DuplicadosLotesService(db_session)

    control = await service.calcular_control(
        lote_id=current_lote_id,
        empresa_id=int(test_empresa.id),
        estados={"validado"},
        incluir_interno=True,
    )

    antecedent = next(
        item
        for item in control["antecedentes_resumen"]
        if item["lote_id"] == previous_lote_id
    )
    assert antecedent["cantidad_lote_anterior"] == 100
    assert antecedent["cantidad_coincidente"] == 100
    assert antecedent["cantidad_autorizada"] == 20
    assert antecedent["cantidad_reservada_en_curso"] == 1
    assert antecedent["cantidad_incierta"] == 1
    assert control["cantidad_afectada"] == 20
    complete = next(
        block for block in control["_bloques"].values() if block["clase"] == "completa"
    )
    assert complete["snapshot"]["multiplicidad_total"] == 100
    current_ordinals = {
        member["ordinal"]
        for member in complete["miembros"].values()
        if member["lado"] == "actual"
    }
    previous_ordinals = {
        member["ordinal"]
        for member in complete["miembros"].values()
        if member["lado"] == "anterior"
    }
    assert current_ordinals == previous_ordinals == relevant_ordinals
    assert len(current_ordinals) == 22
    assert 2 not in current_ordinals
    _, items, total = await service.obtener_detalle(
        lote_id=current_lote_id,
        empresa_id=int(test_empresa.id),
        evidencia_id=control["evidencia_id"],
        page=1,
        per_page=100,
    )
    assert total == 22
    assert len(items) == 22


@pytest.mark.asyncio
async def test_relacion_seis_clases_iguala_paginas_vivas_durables_y_buffer_core(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = DuplicadosLotesService(db_session)

    def current(group_id: int, *, name: str | None, document: str | None) -> dict:
        return {
            "lado": "actual",
            "miembro_clave": f"g-{group_id}",
            "grupo_id": group_id,
            "comprobante_id": None,
            "nombre_hash": name,
            "documento_hash": document,
            "ordinal": None,
            "relevancia": "actual",
            "snapshot": {
                "decision": {"grupo_id": group_id},
                "presentacion": {
                    "grupo_id": group_id,
                    "comprobante_ref": f"ACT-{group_id}",
                    "importe": "1.00",
                    "moneda": "PES",
                    "cotizacion": "1",
                },
            },
        }

    def previous(
        entity_id: int,
        *,
        name: str | None,
        document: str | None,
        receipt: bool = False,
    ) -> dict:
        return {
            "lado": "anterior",
            "miembro_clave": f"{'c' if receipt else 'g'}-{entity_id}",
            "grupo_id": None if receipt else entity_id,
            "comprobante_id": entity_id if receipt else None,
            "nombre_hash": name,
            "documento_hash": document,
            "ordinal": None,
            "relevancia": "autorizado",
            "snapshot": {
                "decision": {"comprobante_id" if receipt else "grupo_id": entity_id},
                "presentacion": {
                    "lote_anterior_id": None if receipt else 900,
                    "grupo_anterior_id": None if receipt else entity_id,
                    "comprobante_anterior_ref": f"ANT-{entity_id}",
                    "estado_grupo_anterior": None if receipt else "autorizado",
                    "operacion_anterior_ref": "op-90",
                    "solicitantes": [],
                    "solicitud_emision_at": None,
                    "solicitud_arca_at": None,
                    "resultado_fiscal_at": None,
                    "hora_confiable": False,
                },
            },
        }

    def block(
        key: str,
        clase: str,
        members: list[dict],
        *,
        fields: list[str],
    ) -> dict:
        return {
            "bloque_clave": key,
            "clase": clase,
            "antecedente_clave": None if clase.startswith("interna_") else "raiz-90",
            "snapshot": {
                "origen": (
                    "comprobante_individual" if clase == "individual_legacy" else "lote"
                ),
                "tipo_coincidencia": (
                    "interna_receptor"
                    if clase.startswith("interna_")
                    else "historica_completa"
                    if clase == "completa"
                    else "historica_individual_legacy"
                    if clase == "individual_legacy"
                    else "historica_parcial_receptor"
                ),
                "campos_coincidentes": fields,
                "lote_anterior_id": (
                    900
                    if not clase.startswith("interna_") and clase != "individual_legacy"
                    else None
                ),
                "multiplicidad_total": 1 if clase == "completa" else None,
            },
            "miembros": {
                (member["lado"], member["miembro_clave"]): member for member in members
            },
        }

    complete_current = current(3, name="n3", document="d3")
    complete_current["ordinal"] = 0
    complete_previous = previous(30, name="n3", document="d3")
    complete_previous["ordinal"] = 0
    overlap_current = current(5, name="igual", document="doc")
    overlap_previous = previous(50, name="igual", document="doc")
    blocks = {
        item["bloque_clave"]: item
        for item in [
            block(
                "i-nombre",
                "interna_nombre",
                [
                    current(10, name="interno", document="x"),
                    current(2, name="interno", document="y"),
                ],
                fields=["nombre"],
            ),
            block(
                "i-documento",
                "interna_documento",
                [
                    current(10, name="x", document="interno"),
                    current(2, name="y", document="interno"),
                ],
                fields=["documento"],
            ),
            block(
                "completa",
                "completa",
                [complete_current, complete_previous],
                fields=["contenido_completo"],
            ),
            block(
                "p-nombre",
                "parcial_nombre",
                [overlap_current, overlap_previous],
                fields=["nombre"],
            ),
            block(
                "p-documento",
                "parcial_documento",
                [
                    overlap_current,
                    current(6, name=None, document="doc"),
                    overlap_previous,
                    previous(51, name="otro", document="doc"),
                ],
                fields=["documento"],
            ),
            block(
                "individual",
                "individual_legacy",
                [
                    current(7, name="legacy", document="legacy"),
                    previous(70, name=None, document=None, receipt=True),
                ],
                fields=["predicado_individual_vigente"],
            ),
        ]
    }
    control = {"_bloques": blocks}

    reference_rows = []
    for compact_block in blocks.values():
        actual = [
            member
            for member in compact_block["miembros"].values()
            if member["lado"] == "actual"
        ]
        prior = [
            member
            for member in compact_block["miembros"].values()
            if member["lado"] == "anterior"
        ]
        pairs = []
        if compact_block["clase"].startswith("interna_"):
            pairs = [(member, None) for member in actual]
        elif compact_block["clase"] == "completa":
            pairs = [
                (
                    member,
                    next(
                        item for item in prior if item["ordinal"] == member["ordinal"]
                    ),
                )
                for member in actual
            ]
        else:
            pairs = [
                (member, antecedent)
                for member in actual
                for antecedent in prior
                if compact_block["clase"] != "parcial_documento"
                or member["nombre_hash"] is None
                or antecedent["nombre_hash"] is None
                or member["nombre_hash"] != antecedent["nombre_hash"]
            ]
        for actual_member, prior_member in pairs:
            reference_rows.append(
                (
                    {
                        "grupo_actual_id": actual_member["grupo_id"],
                        "lote_anterior_id": compact_block["snapshot"].get(
                            "lote_anterior_id"
                        ),
                        "grupo_anterior_id": (
                            prior_member["grupo_id"] if prior_member else None
                        ),
                        "tipo_orden": duplicados_lotes_module.TIPO_ORDEN_PUBLICO[
                            compact_block["clase"]
                        ],
                        "comprobante_anterior_id": (
                            prior_member["comprobante_id"] if prior_member else None
                        ),
                        "antecedente_clave": compact_block["antecedente_clave"],
                        "bloque_clave": compact_block["bloque_clave"],
                    },
                    service._armar_detalle_compacto(
                        clase=compact_block["clase"],
                        block_snapshot=compact_block["snapshot"],
                        current_snapshot=actual_member["snapshot"],
                        previous_snapshot=(
                            prior_member["snapshot"] if prior_member else None
                        ),
                        current_document_hash=actual_member["documento_hash"],
                        previous_document_hash=(
                            prior_member["documento_hash"] if prior_member else None
                        ),
                    ),
                )
            )
    expected = [
        item[1]
        for item in sorted(
            reference_rows,
            key=lambda item: service._clave_orden_publico(item[0]),
        )
    ]
    assert len(expected) == 10

    lote = LoteComprobante(
        empresa_id=int(test_empresa.id),
        nombre_archivo="relacion-seis-clases.xlsx",
        archivo_hash="7" * 64,
        estado="validado",
    )
    db_session.add(lote)
    await db_session.flush()
    operation = OperacionIdempotente(
        empresa_id=int(test_empresa.id),
        idempotency_key="pf13-h2-seis-clases",
        tipo_operacion="procesar_lote",
        payload_hash="6" * 64,
        estado="en_proceso",
        lote_id=int(lote.id),
    )
    db_session.add(operation)
    await db_session.flush()
    generation = LoteDuplicadoEvidencia(
        operacion_id=int(operation.id),
        empresa_id=int(test_empresa.id),
        ambiente="homologacion",
        lote_id=int(lote.id),
        generacion=1,
        formato="duplicados_relacion/1",
        evidencia_id="v2.seis-clases",
        snapshot_hash="6" * 64,
        control_snapshot_json={
            "manifiesto": {
                "bloques": len(blocks),
                "miembros": sum(len(item["miembros"]) for item in blocks.values()),
            }
        },
    )
    db_session.add(generation)
    await db_session.flush()
    await service._insertar_relacion(generation=generation, control=control)

    for page, offset in enumerate(range(0, len(expected), 3), start=1):
        live_items, live_total = await service._pagina_relacion_viva(
            control, offset=offset, limit=3
        )
        durable_items, durable_total = await service._pagina_generacion(
            generation, offset=offset, limit=3
        )
        assert live_total == durable_total == len(expected)
        assert live_items == durable_items == expected[offset : offset + 3]
        assert len(live_items) <= 3
        assert page <= 4

    permuted_blocks = {}
    for key, compact_block in reversed(list(blocks.items())):
        copy_block = deepcopy(compact_block)
        copy_block["miembros"] = dict(reversed(list(copy_block["miembros"].items())))
        permuted_blocks[key] = copy_block
    permuted = {"_bloques": permuted_blocks}
    canonical = service._relacion_canonica(control, snapshot=False)
    permuted_canonical = service._relacion_canonica(permuted, snapshot=False)
    assert canonical == permuted_canonical
    assert duplicados_lotes_module._sha256(canonical) == (
        duplicados_lotes_module._sha256(permuted_canonical)
    )
    permuted_items, permuted_total = await service._pagina_relacion_viva(
        permuted, offset=0, limit=100
    )
    assert permuted_total == len(expected)
    assert permuted_items == expected

    large_members = [
        current(1000 + index, name="buffer", document=str(index))
        for index in range(601)
    ]
    large_block = block(
        "buffer-601",
        "interna_nombre",
        large_members,
        fields=["nombre"],
    )
    second_generation = LoteDuplicadoEvidencia(
        operacion_id=int(operation.id),
        empresa_id=int(test_empresa.id),
        ambiente="homologacion",
        lote_id=int(lote.id),
        generacion=2,
        formato="duplicados_relacion/1",
        evidencia_id="v2.buffer-601",
        snapshot_hash="5" * 64,
        control_snapshot_json={
            "manifiesto": {"bloques": 1, "miembros": len(large_members)}
        },
    )
    db_session.add(second_generation)
    await db_session.flush()
    batches = []
    original_execute = db_session.execute

    async def observe_execute(statement, params=None, *args, **kwargs):
        if getattr(
            getattr(statement, "table", None), "name", None
        ) == LoteDuplicadoCoincidenciaMiembro.__tablename__ and isinstance(
            params, list
        ):
            batches.append(len(params))
        return await original_execute(statement, params, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", observe_execute)
    await service._insertar_relacion(
        generation=second_generation,
        control={"_bloques": {large_block["bloque_clave"]: large_block}},
    )
    assert batches == [250, 250, 101]


@pytest.mark.asyncio
async def test_generacion_y_get_sobreviven_compactacion_sqlite(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    previous_lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="integracion-previo.xlsx",
        cantidad=1,
    )
    current_lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="integracion-actual.xlsx",
        cantidad=1,
    )
    await _marcar_grupos_lote(db_session, previous_lote_id, ["autorizado"])
    current_groups = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo).where(
                LoteComprobanteGrupo.lote_id == current_lote_id
            )
        )
    )
    operation, generation, _, _ = await _publicar_generacion_real_de_prueba(
        db_session,
        empresa_id=int(test_empresa.id),
        lote_id=current_lote_id,
        grupos=current_groups,
        idempotency_key="pf13-h3-integracion-compacta",
        aceptar=True,
    )
    before = await client.get(
        f"/api/lotes-comprobantes/{current_lote_id}/coincidencias",
        params={"evidencia_id": generation.evidencia_id, "per_page": 10},
        headers=auth_headers,
    )
    assert before.status_code == 200, before.text

    await _marcar_grupos_lote(db_session, current_lote_id, ["autorizado"])
    compact = await client.post(
        f"/api/lotes-comprobantes/{current_lote_id}/compactar",
        headers=auth_headers,
    )
    assert compact.status_code == 200, compact.text
    after = await client.get(
        f"/api/lotes-comprobantes/{current_lote_id}/coincidencias",
        params={"evidencia_id": generation.evidencia_id, "per_page": 10},
        headers=auth_headers,
    )
    assert after.status_code == 200, after.text
    assert after.json() == before.json()
    assert (
        await db_session.scalar(
            select(func.count(LoteComprobanteFila.id)).where(
                LoteComprobanteFila.lote_id == current_lote_id
            )
        )
        == 0
    )
    await db_session.refresh(operation)
    assert operation.duplicados_generacion_id == generation.id
    assert len(operation.control_duplicados_json["seleccion_original"]) == 1
    assert await db_session.get(LoteDuplicadoEvidencia, generation.id) is not None


@pytest.mark.asyncio
async def test_metricas_historicas_deduplican_actual_afectado_por_varios_lotes(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El mismo comprobante actual cuenta una vez aunque tenga dos antecedentes."""
    previos_ids = []
    for indice in (1, 2):
        previos_ids.append(
            await _validar_multi_para_duplicados(
                client,
                auth_headers,
                test_empresa.cuit,
                nombre=f"previo-repetido-{indice}.xlsx",
                cantidad=1,
            )
        )
    actual_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="actual-repetido.xlsx",
        cantidad=1,
    )
    await db_session.execute(
        update(LoteComprobanteGrupo)
        .where(LoteComprobanteGrupo.lote_id.in_(previos_ids))
        .values(estado="autorizado")
    )
    await db_session.commit()

    control = await DuplicadosLotesService(db_session).calcular_control(
        lote_id=actual_id,
        empresa_id=test_empresa.id,
        estados={"validado"},
    )

    assert control["cantidad_afectada"] == 1
    assert control["importe_afectado"] == "1210.00"
    assert len(control["antecedentes_resumen"]) == 2
    assert (
        sum(item["cantidad_autorizada"] for item in control["antecedentes_resumen"])
        == 2
    )


@pytest.mark.asyncio
async def test_importes_v2_no_suman_monedas_distintas_ni_unidad_desconocida(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    lote_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="importes-multimoneda.xlsx",
        cantidad=2,
    )
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    grupos[0].moneda_duplicados = "PES"
    grupos[0].total_estimado = Decimal("100.00")
    grupos[1].moneda_duplicados = "USD"
    grupos[1].total_estimado = Decimal("7.50")
    await db_session.commit()

    service = DuplicadosLotesService(db_session)
    control = await service.calcular_control(
        lote_id=lote_id,
        empresa_id=int(inspect(test_empresa).identity[0]),
        estados={"validado"},
    )

    assert control["importe_actual"] is None
    assert control["importes_actuales"] == {
        "por_moneda": [
            {"moneda": "PES", "importe": "100.00", "cantidad": 1},
            {"moneda": "USD", "importe": "7.50", "cantidad": 1},
        ],
        "cantidad_sin_moneda_acreditada": 0,
    }

    grupo_sin_moneda = await db_session.get(
        LoteComprobanteGrupo,
        int(inspect(grupos[1]).identity[0]),
    )
    grupo_sin_moneda.moneda_duplicados = None
    await db_session.commit()
    control = await service.calcular_control(
        lote_id=lote_id,
        empresa_id=int(inspect(test_empresa).identity[0]),
        estados={"validado"},
    )
    assert control["importe_actual"] is None
    assert control["importes_actuales"]["cantidad_sin_moneda_acreditada"] == 1
    assert control["importes_actuales"]["por_moneda"] == [
        {"moneda": "PES", "importe": "100.00", "cantidad": 1}
    ]


@pytest.mark.asyncio
async def test_bloqueo_incierto_con_reserva_cuenta_un_solo_grupo(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    previo_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="incierto-previo.xlsx",
        cantidad=1,
    )
    actual_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="incierto-actual.xlsx",
        cantidad=1,
    )
    previo = await db_session.scalar(
        select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == previo_id)
    )
    previo.estado = "requiere_reconciliacion"
    previo.duplicados_reserva_operacion_id = 999
    await db_session.commit()

    control = await DuplicadosLotesService(db_session).calcular_control(
        lote_id=actual_id,
        empresa_id=test_empresa.id,
        estados={"validado"},
    )

    assert control["bloqueo_operacion_ajena"]["estado"] == "incierta"
    assert control["bloqueo_operacion_ajena"]["cantidad_afectada"] == 1
    antecedente = control["antecedentes_resumen"][0]
    assert antecedente["cantidad_incierta"] == 1
    assert antecedente["cantidad_reservada_en_curso"] == 0


@pytest.mark.asyncio
async def test_importe_afectado_suma_union_actual_con_testigo_autorizado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Dos testigos de A no duplican importe ni incorporan B sólo validado."""
    actual_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="importe-union-actual.xlsx",
        cantidad=2,
    )
    actuales = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == actual_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    actuales[1].total_estimado = Decimal("12100.00")
    actuales[1].total_centavos = 1210000

    def copiar_grupo(
        lote: LoteComprobante,
        original: LoteComprobanteGrupo,
        *,
        estado: str,
        referencia: str,
    ) -> LoteComprobanteGrupo:
        return LoteComprobanteGrupo(
            lote=lote,
            empresa_id=original.empresa_id,
            comprobante_ref=referencia,
            orden=1,
            estado=estado,
            tipo_comprobante=original.tipo_comprobante,
            punto_venta_numero=original.punto_venta_numero,
            total_estimado=original.total_estimado,
            duplicados_version=original.duplicados_version,
            duplicados_cobertura=original.duplicados_cobertura,
            huella_fiscal_completa=original.huella_fiscal_completa,
            identidad_nombre_hash=original.identidad_nombre_hash,
            identidad_documento_hash=original.identidad_documento_hash,
            identidad_nombre_original=original.identidad_nombre_original,
            identidad_tipo_documento_original=(
                original.identidad_tipo_documento_original
            ),
            identidad_numero_documento_original=(
                original.identidad_numero_documento_original
            ),
            fecha_emision_normalizada=original.fecha_emision_normalizada,
            moneda_duplicados=original.moneda_duplicados,
            cotizacion_duplicados=original.cotizacion_duplicados,
            total_centavos=original.total_centavos,
            punto_venta_id=original.punto_venta_id,
            ambiente=original.ambiente,
            punto_venta_elegibilidad_revision_id=(
                original.punto_venta_elegibilidad_revision_id
            ),
            punto_venta_revision_fiscal=original.punto_venta_revision_fiscal,
        )

    lotes_previos = []
    for indice, (original, estado) in enumerate(
        (
            (actuales[0], "autorizado"),
            (actuales[0], "autorizado"),
            (actuales[1], "validado"),
        ),
        start=1,
    ):
        lote = LoteComprobante(
            empresa_id=test_empresa.id,
            nombre_archivo=f"importe-union-previo-{indice}.xlsx",
            archivo_hash=f"{indice + 20:064d}",
            estado="completado" if estado == "autorizado" else "validado",
            total_filas=1,
            total_grupos=1,
            grupos_validos=0 if estado == "autorizado" else 1,
            grupos_emitidos=1 if estado == "autorizado" else 0,
        )
        lote.grupos.append(
            copiar_grupo(
                lote,
                original,
                estado=estado,
                referencia=f"PREVIO-{indice}",
            )
        )
        lotes_previos.append(lote)
    db_session.add_all(lotes_previos)
    await db_session.commit()

    control = await DuplicadosLotesService(db_session).calcular_control(
        lote_id=actual_id,
        empresa_id=test_empresa.id,
        estados={"validado"},
    )

    assert control["cantidad_afectada"] == 1
    assert control["importe_afectado"] == "1210.00"


@pytest.mark.asyncio
async def test_segundo_preflight_v2_distingue_testigos_propios_y_nuevos(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """La cobertura v2 acepta sólo testigos presentados o autorizaciones propias."""
    previo_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="preflight-previo.xlsx",
        cantidad=1,
    )
    actual_id = await _validar_multi_para_duplicados(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre="preflight-actual.xlsx",
        cantidad=1,
    )
    grupo_previo = await db_session.scalar(
        select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == previo_id)
    )
    grupo_propio = await db_session.scalar(
        select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == actual_id)
    )
    assert grupo_previo is not None
    assert grupo_propio is not None

    def comprobante(numero: int) -> Comprobante:
        return Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=numero,
            fecha_emision=FECHA_FISCAL_CONTROLADA_PF19B,
            subtotal=Decimal("1000.00"),
            descuento=Decimal("0.00"),
            iva_21=Decimal("210.00"),
            iva_10_5=Decimal("0.00"),
            iva_27=Decimal("0.00"),
            otros_impuestos=Decimal("0.00"),
            total=Decimal("1210.00"),
            cae=f"{numero:014d}"[-14:],
            cae_vencimiento=date(2026, 8, 20),
            estado="autorizado",
            empresa_id=test_empresa.id,
            punto_venta_id=test_punto_venta.id,
            receptor_tipo_documento=96,
            receptor_numero_documento="30000001",
            receptor_razon_social="Persona Sintética",
            receptor_condicion_iva="CF",
        )

    previo = comprobante(901)
    propio = comprobante(902)
    individual_presentado = comprobante(903)
    nuevo = comprobante(904)
    db_session.add_all([previo, propio, individual_presentado, nuevo])
    await db_session.flush()
    operacion = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=await db_session.scalar(
            select(UsuarioEmisorAcceso.usuario_id).where(
                UsuarioEmisorAcceso.empresa_id == test_empresa.id
            )
        ),
        idempotency_key="pf13-segundo-preflight",
        tipo_operacion="procesar_lote",
        payload_hash="b" * 64,
        estado="en_proceso",
        lote_id=actual_id,
    )
    db_session.add(operacion)
    await db_session.flush()

    def intento(comp: Comprobante, grupo: LoteComprobanteGrupo):
        return IntentoEmisionFiscal(
            operacion_id=operacion.id,
            empresa_id=test_empresa.id,
            usuario_id=None,
            punto_venta_id=test_punto_venta.id,
            punto_venta_numero=test_punto_venta.numero,
            tipo_comprobante=6,
            numero_planificado=comp.numero,
            fecha_emision=comp.fecha_emision,
            total=comp.total,
            receptor_tipo_documento=96,
            receptor_numero_documento="30000001",
            receptor_razon_social="Persona Sintética",
            payload_hash=f"{comp.numero:064d}"[-64:],
            huella_logica=f"{comp.numero + 1:064d}"[-64:],
            estado="autorizado",
            cae=comp.cae,
            cae_vencimiento=comp.cae_vencimiento,
            comprobante_id=comp.id,
            lote_id=grupo.lote_id,
            grupo_id=grupo.id,
        )

    db_session.add_all([intento(previo, grupo_previo), intento(propio, grupo_propio)])
    empresa_id = int(test_empresa.id)
    operacion_id = int(operacion.id)
    grupo_propio_id = int(grupo_propio.id)
    comprobante_ids = [
        int(previo.id),
        int(propio.id),
        int(individual_presentado.id),
        int(nuevo.id),
    ]
    await db_session.commit()
    comprobantes = [
        await db_session.get(Comprobante, comprobante_id)
        for comprobante_id in comprobante_ids
    ]
    assert all(comprobante is not None for comprobante in comprobantes)
    previo, propio, individual_presentado, nuevo = comprobantes
    grupo_propio = await db_session.get(LoteComprobanteGrupo, grupo_propio_id)
    operacion = await db_session.get(OperacionIdempotente, operacion_id)
    assert grupo_propio is not None
    assert operacion is not None
    matches = [previo, propio, individual_presentado]

    async def buscar_matches(*_args, **_kwargs):
        return list(matches)

    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "buscar_duplicados_logicos_lote",
        buscar_matches,
    )
    service = DuplicadosLotesService(db_session)
    baseline, acceptance_id, accepted = await service.evaluar_y_reservar(
        operacion_id=operacion_id,
        lote_id=actual_id,
        empresa_id=empresa_id,
        estados={"validado"},
        grupo_ids=[grupo_propio_id],
        aceptacion_recibida=None,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    assert acceptance_id is not None
    assert accepted is False
    baseline, same_acceptance_id, accepted = await service.evaluar_y_reservar(
        operacion_id=operacion_id,
        lote_id=actual_id,
        empresa_id=empresa_id,
        estados={"validado"},
        grupo_ids=[grupo_propio_id],
        aceptacion_recibida=acceptance_id,
        solicitante_nombre="Operador sintético",
        reservar=False,
        ambiente=settings.arca_env,
    )
    assert same_acceptance_id == acceptance_id
    assert accepted is True

    vigente = await service.revalidar_operacion_lote(
        operacion_id=operacion.id,
        lote_id=actual_id,
        empresa_id=empresa_id,
    )
    assert vigente["evidencia_id"] == baseline["evidencia_id"]

    matches.append(nuevo)
    with pytest.raises(DuplicadosLotePreflightCambioError):
        await service.revalidar_operacion_lote(
            operacion_id=operacion.id,
            lote_id=actual_id,
            empresa_id=empresa_id,
        )


def _crear_error_db_temporal(
    error_type: type[Exception],
) -> SQLAlchemyTimeoutError | OperationalError:
    """Construye errores transitorios de SQLAlchemy sin una base externa."""
    if error_type is SQLAlchemyTimeoutError:
        return SQLAlchemyTimeoutError()
    return OperationalError(
        "UPDATE lotes_comprobantes SET estado = :estado",
        {"estado": "procesando"},
        RuntimeError("base temporalmente no disponible"),
    )


# Identificadores sintéticos de fixtures. Se construyen en partes para evitar
# versionar por accidente datos fiscales reales o emitidos.
CUIT_RECEPTOR_TEST_NO_REAL = "".join(("20", "40937847", "2"))
CUIT_RECEPTOR_TEST_NO_REAL_INT = int(CUIT_RECEPTOR_TEST_NO_REAL)
CAE_TEST_NO_REAL_SERIE = "".join(("1234567", "89012"))
CAE_TEST_NO_REAL_PREFIX = f"{CAE_TEST_NO_REAL_SERIE}3"
CAE_TEST_NO_REAL = f"{CAE_TEST_NO_REAL_SERIE}34"
CAE_TEST_NO_REAL_ALT = f"{CAE_TEST_NO_REAL_SERIE}35"
CAE_TEST_NO_REAL_36 = f"{CAE_TEST_NO_REAL_SERIE}36"
CAE_TEST_NO_REAL_37 = f"{CAE_TEST_NO_REAL_SERIE}37"
CAE_TEST_NO_REAL_38 = f"{CAE_TEST_NO_REAL_SERIE}38"
CAE_TEST_NO_REAL_39 = f"{CAE_TEST_NO_REAL_SERIE}39"
CAE_TEST_NO_REAL_40 = f"{CAE_TEST_NO_REAL_SERIE}40"
FECHA_FISCAL_PF02B2 = date(2026, 7, 29)
FECHA_FISCAL_CONTROLADA_PF19B = date(2026, 8, 9)
FECHA_DOCUMENTO_RECE_TEST = date(2026, 8, 1)
FECHA_VIGENCIA_RECE_TEST = date(2099, 12, 31)
INSTANTE_RECE_TEST = datetime(2026, 8, 1, 12, 0, 0)


class _FechaFiscalControlada(date):
    """Reloj estable para conservar activa la ventana fiscal de facturación."""

    @classmethod
    def today(cls) -> date:
        """Devuelve la fecha fiscal explícita compartida por estos tests."""
        return cls(
            FECHA_FISCAL_CONTROLADA_PF19B.year,
            FECHA_FISCAL_CONTROLADA_PF19B.month,
            FECHA_FISCAL_CONTROLADA_PF19B.day,
        )


@pytest.fixture(autouse=True)
def _controlar_reloj_fecha_fiscal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fija el reloj de facturación sin omitir su validación de ventana ARCA."""
    monkeypatch.setattr(
        "app.services.facturacion_service.date",
        _FechaFiscalControlada,
    )


@pytest.fixture(autouse=True)
def _configurar_ambiente_rece_productivo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fija el ambiente RECE requerido sin depender del entorno del runner."""
    monkeypatch.setattr(settings, "arca_env", "produccion")


@pytest.fixture(autouse=True)
def _desactivar_batch_arca_por_defecto(monkeypatch: pytest.MonkeyPatch):
    """Evita consultas WSAA/WSFE reales en tests que no prueban batching ARCA."""
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", False)


def _build_lote_excel(
    empresa_cuit: str,
    punto_venta_numero: int | str = 1,
    concepto: int | str = 1,
    tipo_comprobante: int = 6,
    iva: int | float = 21,
    cliente_tipo_documento: str = "CUIT",
    cliente_numero_documento: str = CUIT_RECEPTOR_TEST_NO_REAL,
    cliente_razon_social: str = "Cliente Lote SA",
    cliente_condicion_iva: str | None = None,
    item_precio_unitario: int | float = 1000,
    fecha_servicio_desde: date | str = "",
    fecha_servicio_hasta: date | str = "",
    fecha_vto_pago: date | str = "",
    asociado_tipo_comprobante: int | str = "",
    asociado_punto_venta: int | str = "",
    asociado_numero: int | str = "",
    asociado_fecha: date | str = "",
    asociado_cuit: str = "",
) -> bytes:
    if cliente_condicion_iva is None:
        cliente_condicion_iva = (
            "Responsable Inscripto" if tipo_comprobante in {1, 2, 3} else "Exento"
        )
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Comprobantes"
    sheet.append(
        [
            "comprobante_ref",
            "empresa_cuit",
            "punto_venta_numero",
            "tipo_comprobante",
            "concepto",
            "fecha_emision",
            "cliente_tipo_documento",
            "cliente_numero_documento",
            "cliente_razon_social",
            "cliente_condicion_iva",
            "cliente_domicilio",
            "fecha_servicio_desde",
            "fecha_servicio_hasta",
            "fecha_vto_pago",
            "item_codigo",
            "item_descripcion",
            "item_cantidad",
            "item_unidad",
            "item_precio_unitario",
            "item_descuento_porcentaje",
            "item_iva_porcentaje",
            "observaciones",
            "asociado_tipo_comprobante",
            "asociado_punto_venta",
            "asociado_numero",
            "asociado_fecha",
            "asociado_cuit",
        ]
    )
    asociado_fecha_valor = (
        asociado_fecha.isoformat()
        if isinstance(asociado_fecha, date)
        else asociado_fecha
    )
    fecha_servicio_desde_valor = (
        fecha_servicio_desde.isoformat()
        if isinstance(fecha_servicio_desde, date)
        else fecha_servicio_desde
    )
    fecha_servicio_hasta_valor = (
        fecha_servicio_hasta.isoformat()
        if isinstance(fecha_servicio_hasta, date)
        else fecha_servicio_hasta
    )
    fecha_vto_pago_valor = (
        fecha_vto_pago.isoformat()
        if isinstance(fecha_vto_pago, date)
        else fecha_vto_pago
    )
    sheet.append(
        [
            "LOTE-001",
            empresa_cuit,
            punto_venta_numero,
            tipo_comprobante,
            concepto,
            FECHA_FISCAL_CONTROLADA_PF19B.isoformat(),
            cliente_tipo_documento,
            cliente_numero_documento,
            cliente_razon_social,
            cliente_condicion_iva,
            "Av. Siempre Viva 123",
            fecha_servicio_desde_valor,
            fecha_servicio_hasta_valor,
            fecha_vto_pago_valor,
            "ITEM-001",
            "Servicio mensual",
            1,
            "unidad",
            item_precio_unitario,
            0,
            iva,
            "Factura de prueba",
            asociado_tipo_comprobante,
            asociado_punto_venta,
            asociado_numero,
            asociado_fecha_valor,
            asociado_cuit,
        ]
    )

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


async def _confirmacion_fecha_fiscal_header_lote(
    db_session: AsyncSession,
    *,
    lote_id: int,
    estados: set[str],
    grupo_ids: list[int] | None = None,
    idempotency_key: str = "idem-lote-test",
) -> dict[str, str]:
    """Obtiene el token fiscal RECE exacto del lote usado por el test."""
    confirmacion = await LoteComprobantesService(
        db_session
    ).obtener_confirmacion_fiscal_grupos(
        lote_id=lote_id,
        empresa_id=int(
            await db_session.scalar(
                select(LoteComprobante.empresa_id).where(LoteComprobante.id == lote_id)
            )
        ),
        estados=estados,
        grupo_ids=grupo_ids,
    )
    return {
        "X-Confirmacion-Fecha-Fiscal": str(confirmacion["confirmacion_fecha_fiscal"]),
        "X-Idempotency-Key": idempotency_key,
    }


@pytest.mark.asyncio
async def test_archivo_observado_escapa_textos_con_formulas(
    db_session: AsyncSession,
    test_empresa,
):
    """El Excel observado no debe abrir formulas tomadas del archivo original."""
    datos = {column: "" for column in LoteComprobantesService.TEMPLATE_COLUMNS}
    datos.update(
        {
            "comprobante_ref": "=SUM(1,1)",
            "empresa_cuit": test_empresa.cuit,
            "item_descripcion": "+cmd",
            "observaciones": " @malicioso",
        }
    )
    lote = LoteComprobante(
        nombre_archivo="observado.xlsx",
        archivo_hash="hash-observado-formulas",
        estado="con_errores",
        total_filas=1,
        total_grupos=1,
        grupos_con_error=1,
        empresa_id=test_empresa.id,
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="=SUM(1,1)",
        orden=1,
        estado="con_error",
        mensajes_json=["=HYPERLINK('http://malicioso')"],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="=SUM(1,1)",
        estado="con_error",
        datos_json=datos,
        mensajes_json=["=HYPERLINK('http://malicioso')"],
    )
    db_session.add_all([lote, grupo, fila])
    await db_session.commit()
    await db_session.refresh(lote)

    service = LoteComprobantesService(db_session)
    contenido = await service.generar_archivo_observado(lote.id, test_empresa.id)

    workbook = load_workbook(BytesIO(contenido), data_only=False)
    sheet = workbook["Resultados"]
    headers = [cell.value for cell in sheet[1]]
    row = {
        header: sheet.cell(row=2, column=index + 1).value
        for index, header in enumerate(headers)
    }

    assert row["comprobante_ref"] == "'=SUM(1,1)"
    assert row["item_descripcion"] == "'+cmd"
    assert row["observaciones"] == "' @malicioso"
    assert row["resultado_mensajes"] == "'=HYPERLINK('http://malicioso')"
    assert sheet["A2"].data_type == "s"


def _build_lote_excel_multi_grupo(empresa_cuit: str, total_grupos: int = 2) -> bytes:
    """Construye un Excel de prueba con varios comprobantes independientes."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Comprobantes"
    sheet.append(
        [
            "comprobante_ref",
            "empresa_cuit",
            "punto_venta_numero",
            "tipo_comprobante",
            "concepto",
            "fecha_emision",
            "cliente_tipo_documento",
            "cliente_numero_documento",
            "cliente_razon_social",
            "cliente_condicion_iva",
            "cliente_domicilio",
            "fecha_servicio_desde",
            "fecha_servicio_hasta",
            "fecha_vto_pago",
            "item_codigo",
            "item_descripcion",
            "item_cantidad",
            "item_unidad",
            "item_precio_unitario",
            "item_descuento_porcentaje",
            "item_iva_porcentaje",
            "observaciones",
            "asociado_tipo_comprobante",
            "asociado_punto_venta",
            "asociado_numero",
            "asociado_fecha",
            "asociado_cuit",
        ]
    )
    for index in range(1, total_grupos + 1):
        sheet.append(
            [
                f"LOTE-{index:03d}",
                empresa_cuit,
                1,
                6,
                1,
                FECHA_FISCAL_CONTROLADA_PF19B.isoformat(),
                "DNI",
                str(30000000 + index),
                f"Cliente Lote {index}",
                "Exento",
                "Av. Siempre Viva 123",
                "",
                "",
                "",
                f"ITEM-{index:03d}",
                "Servicio mensual",
                1,
                "unidad",
                1000,
                0,
                21,
                "Factura de prueba",
                "",
                "",
                "",
                "",
                "",
            ]
        )

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _build_extracto_bancario_excel(
    empresa_cuit: str,
    fecha_movimiento: date | None = None,
    fecha_como_serial: bool = False,
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Extracto"
    sheet.append(
        [
            "Fecha",
            "Créditos",
            "Leyendas Adicionales1",
            "Leyendas Adicionales2",
            "Pto Vta",
        ]
    )
    fecha_base = fecha_movimiento or FECHA_FISCAL_CONTROLADA_PF19B
    fecha = (
        to_excel(fecha_base) if fecha_como_serial else fecha_base.strftime("%d/%m/%Y")
    )
    sheet.append([fecha, "59.500,00", "CLIENTE UNO", CUIT_RECEPTOR_TEST_NO_REAL, 1])
    sheet.append([fecha, "70.500,00", "CLIENTE DOS", CUIT_RECEPTOR_TEST_NO_REAL, 10])
    sheet.append([fecha, "140.000,00", "CLIENTE TRES", CUIT_RECEPTOR_TEST_NO_REAL, 13])

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _build_cano_factura_b_excel(fecha_movimiento: date | None = None) -> bytes:
    """Genera una muestra del formato Cano con Factura B e IVA discriminado."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Hoja1"
    sheet.append(
        [
            "Fecha",
            "Tipo",
            "Punto de Venta",
            "Número Desde",
            "Número Hasta",
            "Cód. Autorización",
            "Tipo Doc. Receptor",
            "Nro. Doc. Receptor",
            "Denominación Receptor",
            "Tipo Cambio",
            "Moneda",
            "Imp. Neto Gravado",
            "Imp. Neto No Gravado",
            "Imp. Op. Exentas",
            "Otros Tributos",
            "IVA",
            "Imp. Total",
        ]
    )
    fecha = fecha_movimiento or FECHA_FISCAL_CONTROLADA_PF19B
    sheet.append(
        [
            fecha,
            "6 - Factura B",
            2,
            1,
            "",
            "",
            "DNI",
            "HEBER YOEL ASANCHEZ CA -",
            "",
            1,
            "$",
            74380.1652892562,
            0,
            0,
            "",
            15619.8347107438,
            90000,
        ]
    )

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _config_formato_cano_factura_b() -> dict:
    """Devuelve la configuración del formato Cano Factura B con IVA 21%."""
    return {
        "tipo": "cano_factura_b_iva_21",
        "header_row": 1,
        "modo_agrupacion": "fila",
        "campos": {
            "fecha_origen": {
                "origen": "header",
                "encabezados": ["Fecha"],
                "transformacion": "fecha",
                "requerido": True,
            },
            "importe_total": {
                "origen": "header",
                "encabezados": ["Imp. Total"],
                "transformacion": "decimal",
                "requerido": False,
            },
            "item_precio_unitario": {
                "origen": "header",
                "encabezados": ["Imp. Neto Gravado"],
                "transformacion": "decimal",
                "requerido": True,
            },
            "cliente_razon_social": {
                "origen": "header",
                "encabezados": ["Nro. Doc. Receptor", "Denominación Receptor"],
                "transformacion": "texto",
                "requerido": False,
                "default": "",
            },
            "punto_venta_numero": {
                "origen": "header",
                "encabezados": ["Punto de Venta"],
                "transformacion": "entero",
                "requerido": True,
            },
            "tipo_comprobante": {"origen": "constante", "valor": 6},
            "cliente_condicion_iva": {
                "origen": "constante",
                "valor": "Consumidor Final",
            },
            "item_cantidad": {"origen": "constante", "valor": 1},
            "item_unidad": {"origen": "constante", "valor": "unidad"},
            "item_iva_porcentaje": {"origen": "constante", "valor": 21},
            "item_descuento_porcentaje": {"origen": "constante", "valor": 0},
            "guardar_cliente": {"origen": "constante", "valor": False},
        },
    }


def _fecha_argentina(value: date | str) -> str:
    """Formatea una fecha de test en DD/MM/AAAA."""
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return datetime.strptime(str(value), "%Y-%m-%d").strftime("%d/%m/%Y")


def test_reconciliacion_externa_item_rechaza_fecha_calendario_invalida():
    """El schema no debe aceptar fechas externas imposibles."""
    with pytest.raises(ValueError):
        LoteReconciliacionExternaItem(
            grupo_id=1,
            tipo_comprobante=6,
            punto_venta_numero=1,
            numero=123,
            fecha_emision="31/02/2026",
            total=Decimal("1210.00"),
            motivo="Emitido manualmente por ARCA Web",
        )


def _hashes_fiscales_request(
    request: EmitirComprobanteRequest,
    punto_venta_numero: int,
    total: Decimal,
) -> tuple[str, str]:
    """Calcula los hashes fiscales del request igual que producción."""
    payload = request.model_dump(mode="json")
    payload_hash = IdempotenciaFiscalService.calcular_payload_hash(
        IdempotenciaFiscalService.payload_sin_confirmacion_duplicado(payload)
    )
    huella = IdempotenciaFiscalService.calcular_huella_logica(
        request=request,
        punto_venta_numero=punto_venta_numero,
        total=total,
    )
    return payload_hash, huella


def _payload_lote_basico(
    empresa_id: int,
    punto_venta_id: int,
    fecha_fiscal: date,
    razon_social: str = "Cliente Lote SA",
) -> dict[str, object]:
    """Construye un payload fiscal sintético y estable para tests de lotes."""
    return {
        "empresa_id": empresa_id,
        "punto_venta_id": punto_venta_id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
        "razon_social": razon_social,
        "condicion_iva": "RI",
        "domicilio": "Av. Siempre Viva 123",
        "moneda": "PES",
        "cotizacion": "1",
        "guardar_cliente": False,
        "items": [
            {
                "descripcion": "Servicio mensual",
                "cantidad": "1",
                "unidad": "unidad",
                "precio_unitario": "1000",
                "iva_porcentaje": "21",
            }
        ],
    }


def _opciones_fechas(
    fecha_emision_modo: str = "archivo",
    fecha_emision_fija: date | str | None = None,
    concepto_modo: str = "productos",
    descripcion_item_modo: str = "archivo",
    descripcion_item_fija: str | None = None,
    punto_venta_modo: str = "archivo",
    punto_venta_numero: int | None = None,
    fecha_servicio_desde_fija: date | str | None = None,
    fecha_servicio_hasta_fija: date | str | None = None,
    fecha_vto_pago_fija: date | str | None = None,
) -> dict[str, str]:
    """Devuelve opciones explícitas para validar lotes."""
    data = {
        "concepto_modo": concepto_modo,
        "descripcion_item_modo": descripcion_item_modo,
        "punto_venta_modo": punto_venta_modo,
        "fecha_emision_modo": fecha_emision_modo,
        "fecha_servicio_desde_modo": "archivo",
        "fecha_servicio_hasta_modo": "archivo",
        "fecha_vto_pago_modo": "archivo",
    }
    for key, value in {
        "fecha_emision_fija": fecha_emision_fija,
        "fecha_servicio_desde_fija": fecha_servicio_desde_fija,
        "fecha_servicio_hasta_fija": fecha_servicio_hasta_fija,
        "fecha_vto_pago_fija": fecha_vto_pago_fija,
    }.items():
        if value:
            data[key] = value.isoformat() if isinstance(value, date) else value
    if descripcion_item_fija:
        data["descripcion_item_fija"] = descripcion_item_fija
    if punto_venta_numero:
        data["punto_venta_numero"] = str(punto_venta_numero)
    return data


async def _crear_punto_venta_rece_verificado(
    db_session: AsyncSession,
    empresa: Empresa,
    *,
    usuario_id: int,
    numero: int,
    nombre: str,
    documento_emitido_en: date,
    vigente_hasta: date,
    observado_en: datetime,
) -> PuntoVenta:
    """Crea un punto sintético con ledger y cabeza RECE positivos explícitos."""
    assert settings.arca_env == "produccion"
    punto = PuntoVenta(
        numero=numero,
        nombre=nombre,
        activo=True,
        es_webservice=True,
        empresa_id=empresa.id,
        ultima_comprobacion_arca_en=observado_en,
        revision_fiscal=1,
    )
    db_session.add(punto)
    await db_session.flush()
    elegibilidad = ElegibilidadReceService(db_session)
    await elegibilidad.crear_contextos_iniciales_no_verificados(
        punto,
        creado_por_usuario_id=usuario_id,
    )
    revision = PuntoVentaElegibilidadReceRevision(
        empresa_id=empresa.id,
        punto_venta_id=punto.id,
        ambiente="produccion",
        revision=2,
        estado="verificado_rece",
        fuente="constancia_arca_atestada",
        evidencia_tipo="rece_aplicativo_web_services_v1",
        evidencia_sha256=f"{numero:064x}",
        clasificador_version="rece-v1-test",
        empresa_cuit_snapshot=empresa.cuit,
        punto_venta_numero_snapshot=numero,
        punto_revision_fiscal=1,
        documento_emitido_en=documento_emitido_en,
        vigente_hasta=vigente_hasta,
        observado_en=observado_en,
        verificado_en=observado_en,
        creado_por_usuario_id=usuario_id,
        actor_usuario_id_snapshot=usuario_id,
        created_at=observado_en,
    )
    db_session.add(revision)
    await db_session.flush()
    head = await db_session.scalar(
        select(PuntoVentaElegibilidadReceActual).where(
            PuntoVentaElegibilidadReceActual.punto_venta_id == punto.id,
            PuntoVentaElegibilidadReceActual.ambiente == "produccion",
        )
    )
    assert head is not None
    head.revision_actual_id = revision.id
    await db_session.flush()
    return punto


@pytest.fixture
async def test_punto_venta(
    db_session: AsyncSession,
    test_empresa,
    test_user,
) -> PuntoVenta:
    """Crea un punto con evidencia RECE positiva únicamente para tests felices."""
    punto = await _crear_punto_venta_rece_verificado(
        db_session,
        test_empresa,
        usuario_id=int(test_user.id),
        numero=1,
        nombre="Principal",
        documento_emitido_en=FECHA_DOCUMENTO_RECE_TEST,
        vigente_hasta=FECHA_VIGENCIA_RECE_TEST,
        observado_en=INSTANTE_RECE_TEST,
    )
    await db_session.commit()
    return punto


@pytest.fixture
async def test_certificado(db_session: AsyncSession, test_empresa) -> Certificado:
    certificado = Certificado(
        nombre="Certificado homologacion",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2026, 12, 31),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    db_session.add(certificado)
    await db_session.commit()
    await db_session.refresh(certificado)
    return certificado


async def _persistir_comprobante_autorizado(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta: PuntoVenta,
    *,
    tipo_comprobante: int,
    numero: int,
    fecha_emision: date,
    cae: str,
    cae_vencimiento: date,
    total: Decimal,
) -> int:
    """Crea un comprobante sintético para fakes que simulan CAE autorizado."""
    empresa_id = inspect(test_empresa).identity[0]
    punto_venta_id = inspect(test_punto_venta).identity[0]
    comprobante = Comprobante(
        tipo_comprobante=tipo_comprobante,
        concepto=1,
        numero=numero,
        fecha_emision=fecha_emision,
        subtotal=total,
        descuento=Decimal("0.00"),
        iva_21=Decimal("0.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=total,
        cae=cae,
        cae_vencimiento=cae_vencimiento,
        estado="autorizado",
        empresa_id=empresa_id,
        punto_venta_id=punto_venta_id,
        receptor_tipo_documento=99,
        receptor_numero_documento="0",
        receptor_razon_social="A CONSUMIDOR FINAL",
        receptor_condicion_iva="Consumidor Final",
    )
    db_session.add(comprobante)
    await db_session.flush()
    return comprobante.id


async def _crear_lote_validado_por_api(
    client: AsyncClient,
    auth_headers: dict,
    empresa_cuit: str,
    nombre_archivo: str = "lote-resolucion.xlsx",
    total_grupos: int = 1,
) -> int:
    """Crea un lote validado usando el endpoint público de carga masiva."""
    archivo = (
        _build_lote_excel_multi_grupo(empresa_cuit, total_grupos)
        if total_grupos > 1
        else _build_lote_excel(empresa_cuit)
    )
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                nombre_archivo,
                archivo,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    return int(response.json()["lote"]["id"])


async def _marcar_grupos_lote(
    db_session: AsyncSession,
    lote_id: int,
    estados: list[str],
) -> list[LoteComprobanteGrupo]:
    """Actualiza estados de grupos y recalcula el lote en pruebas."""
    grupos = list(
        (
            await db_session.execute(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        )
        .scalars()
        .all()
    )
    assert len(grupos) >= len(estados)
    for grupo, estado in zip(grupos, estados, strict=False):
        grupo.estado = estado
        grupo.mensajes_json = [f"Estado de prueba: {estado}"]
        if estado in {"autorizado", "requiere_reconciliacion"}:
            grupo.cae = CAE_TEST_NO_REAL
            grupo.numero_asignado = 100 + grupo.orden
        filas = list(
            (
                await db_session.execute(
                    select(LoteComprobanteFila).where(
                        LoteComprobanteFila.grupo_id == grupo.id
                    )
                )
            )
            .scalars()
            .all()
        )
        for fila in filas:
            fila.estado = estado
            fila.mensajes_json = grupo.mensajes_json

    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    await db_session.flush()
    service = LoteComprobantesService(db_session)
    await service._actualizar_estado_lote(lote)
    await db_session.commit()
    return grupos


async def _preparar_reintento_manual_pf02b2(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta: PuntoVenta,
    wsfe_client_class: type,
    *,
    nombre_archivo: str,
    total_grupos: int = 1,
    ultimo_local: int | None = None,
) -> tuple[int, list[LoteComprobanteGrupo]]:
    """Prepara un reintento manual determinista con un doble WSFE controlado."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo=nombre_archivo,
        total_grupos=total_grupos,
    )
    grupos = await _marcar_grupos_lote(
        db_session,
        lote_id,
        ["fallido"] * total_grupos,
    )
    for grupo in grupos:
        payload = dict(grupo.payload_json or {})
        payload["fecha_emision"] = FECHA_FISCAL_PF02B2.isoformat()
        grupo.payload_json = payload

    if ultimo_local is not None:
        await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=6,
            numero=ultimo_local,
            fecha_emision=date(2026, 7, 28),
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 8, 31),
            total=Decimal("1210.00"),
        )
    await db_session.commit()

    async def fake_validar_datos(self, request):
        """Aísla la ventana temporal ARCA para usar una fecha fiscal fija."""

    async def fake_ticket(self, empresa, certificado):
        """Evita leer certificados o contactar WSAA."""
        return SimpleNamespace(token="token-test", sign="sign-test")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        """Mantiene el punto sintético habilitado sin consultar ARCA."""

    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        wsfe_client_class,
    )
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    return lote_id, grupos


@pytest.mark.asyncio
async def test_reintentar_solo_y_de_lote_autorizado_parcial_alcanza_cae(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """X autorizado/Y rechazado permite solicitar únicamente el retry de Y."""

    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)

    class FakeWSFEClient:
        consultas_numeracion = 0
        solicitudes_fecae = 0
        ultimo_autorizado = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def fe_comp_tot_x_request(self):
            return 2

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            FakeWSFEClient.consultas_numeracion += 1
            return FakeWSFEClient.ultimo_autorizado

        async def fe_cae_solicitar_lote(self, arca_requests):
            assert [request.cbte_desde for request in arca_requests] == [1, 2]
            FakeWSFEClient.solicitudes_fecae += 2
            FakeWSFEClient.ultimo_autorizado = 1
            primero, segundo = arca_requests
            return [
                CAEResponse(
                    cae=CAE_TEST_NO_REAL,
                    cae_vencimiento="20260831",
                    numero_comprobante=primero.cbte_desde,
                    tipo_cbte=primero.tipo_cbte,
                    punto_venta=primero.punto_venta,
                    resultado="A",
                ),
                CAEResponse(
                    cae=None,
                    cae_vencimiento=None,
                    numero_comprobante=segundo.cbte_desde,
                    tipo_cbte=segundo.tipo_cbte,
                    punto_venta=segundo.punto_venta,
                    resultado="R",
                    errores=[{"code": 10016, "msg": "Rechazo sintético explícito"}],
                ),
            ]

        async def fe_cae_solicitar(self, arca_request):
            FakeWSFEClient.solicitudes_fecae += 1
            assert arca_request.cbte_desde == 2
            FakeWSFEClient.ultimo_autorizado = 2
            return CAEResponse(
                cae=CAE_TEST_NO_REAL_ALT,
                cae_vencimiento="20260831",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    async def fake_validar_datos(self, request):
        """Aísla sólo la ventana temporal; conserva el borde fiscal restante."""

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token-test", sign="sign-test")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        FakeWSFEClient,
    )
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )

    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-retry-x-autorizado-y-rechazado.xlsx",
        total_grupos=2,
    )
    headers_iniciales = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="idem-lote-x-autorizado-y-rechazado",
    )
    inicial = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_iniciales},
    )
    assert inicial.status_code == 200, inicial.text
    assert inicial.json()["lote"]["estado"] == "autorizado_parcial"
    assert FakeWSFEClient.solicitudes_fecae == 2

    db_session.expire_all()
    x, y = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    x_id = int(x.id)
    y_id = int(y.id)
    assert (x.estado, x.numero_asignado, x.cae) == (
        "autorizado",
        1,
        CAE_TEST_NO_REAL,
    )
    assert y.estado == "fallido"
    intentos_iniciales = list(
        (
            await db_session.scalars(
                select(IntentoEmisionFiscal)
                .where(IntentoEmisionFiscal.lote_id == lote_id)
                .order_by(IntentoEmisionFiscal.id)
            )
        ).all()
    )
    assert [intento.estado for intento in intentos_iniciales] == [
        "autorizado",
        "rechazado_arca",
    ]
    headers_retry = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[y_id],
        idempotency_key="idem-retry-solo-y-autorizado",
    )
    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_retry},
        json={"grupo_ids": [y_id]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["lote"]["estado"] == "completado"
    assert FakeWSFEClient.solicitudes_fecae == 3
    db_session.expire_all()
    x = await db_session.get(LoteComprobanteGrupo, x_id)
    y = await db_session.get(LoteComprobanteGrupo, y_id)
    assert x is not None
    assert y is not None
    assert x.estado == "autorizado"
    assert x.numero_asignado == 1
    assert x.cae == CAE_TEST_NO_REAL
    assert y.estado == "autorizado"
    assert y.numero_asignado == 2
    assert y.cae == CAE_TEST_NO_REAL_ALT
    intentos_finales = list(
        (
            await db_session.scalars(
                select(IntentoEmisionFiscal)
                .where(IntentoEmisionFiscal.lote_id == lote_id)
                .order_by(IntentoEmisionFiscal.id)
            )
        ).all()
    )
    assert [intento.grupo_id for intento in intentos_finales] == [x_id, y_id, y_id]
    assert [intento.estado for intento in intentos_finales] == [
        "autorizado",
        "rechazado_arca",
        "autorizado",
    ]


@pytest.mark.asyncio
async def test_guarda_retry_rechaza_grupo_que_deja_estado_reintentando(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """La membresía final bloquea un grupo autorizado antes de solicitar CAE."""

    test_certificado.ambiente = settings.arca_env

    class FakeWSFEClient:
        solicitudes_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            return 0

        async def fe_cae_solicitar(self, arca_request):
            FakeWSFEClient.solicitudes_fecae += 1
            raise AssertionError("La guarda debe bloquear el grupo antes de FECAE")

    lote_id, [grupo] = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo="lote-retry-grupo-deja-reintentando.xlsx",
    )
    grupo_id = int(grupo.id)
    headers_retry = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
        idempotency_key="idem-retry-grupo-deja-reintentando",
    )
    marcar_original = ElegibilidadReceService.marcar_arca_iniciada
    guardas_evaluadas = 0

    async def marcar_con_grupo_autorizado(self, **kwargs):
        nonlocal guardas_evaluadas
        guardas_evaluadas += 1
        actualizado = await self.db.execute(
            update(LoteComprobanteGrupo)
            .where(
                LoteComprobanteGrupo.id == grupo_id,
                LoteComprobanteGrupo.estado == "reintentando",
            )
            .values(estado="autorizado")
        )
        assert actualizado.rowcount == 1
        await self.db.flush()
        return await marcar_original(self, **kwargs)

    monkeypatch.setattr(
        ElegibilidadReceService,
        "marcar_arca_iniciada",
        marcar_con_grupo_autorizado,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_retry},
        json={"grupo_ids": [grupo_id]},
    )

    assert response.status_code == 200, response.text
    assert guardas_evaluadas == 1
    assert FakeWSFEClient.solicitudes_fecae == 0
    db_session.expire_all()
    grupo_durable = await db_session.get(LoteComprobanteGrupo, grupo_id)
    assert grupo_durable is not None
    assert grupo_durable.estado == "fallido"
    [intento] = list(
        (
            await db_session.scalars(
                select(IntentoEmisionFiscal).where(
                    IntentoEmisionFiscal.lote_id == lote_id,
                    IntentoEmisionFiscal.grupo_id == grupo_id,
                )
            )
        ).all()
    )
    assert intento.estado == "fallido_verificado"
    assert intento.solicitud_arca_at is None
    guarda = await db_session.get(
        PuntoVentaGuardaEmisionRece,
        intento.guarda_rece_id,
    )
    assert guarda is not None
    assert guarda.fase == "cerrada_pre_arca"
    assert guarda.arca_iniciada_en is None


async def _crear_lote_stale_moderno_intacto(
    db_session: AsyncSession,
    empresa: Empresa,
    *,
    grupos_payload: list[tuple[str, dict]],
    idempotency_key: str,
) -> tuple[LoteComprobante, tuple[LoteComprobanteGrupo, ...]]:
    """Persiste ownership worker moderno para grupos stale aún intactos."""
    empresa_id = int(empresa.id)
    elegibilidad = ElegibilidadReceService(db_session)
    contextos_por_punto: dict[int, ContextoElegibilidadRece] = {}
    for _, payload in grupos_payload:
        punto_venta_id = int(payload["punto_venta_id"])
        if punto_venta_id in contextos_por_punto:
            continue
        contextos_por_punto[
            punto_venta_id
        ] = await elegibilidad.exigir_contexto_preautorizacion(
            empresa_id=empresa_id,
            punto_venta_id=punto_venta_id,
            ambiente=settings.arca_env,
            tipo_comprobante=int(payload["tipo_comprobante"]),
        )

    lote = LoteComprobante(
        nombre_archivo=f"{idempotency_key}.xlsx",
        archivo_hash=f"hash-{idempotency_key}",
        estado="validado",
        total_filas=len(grupos_payload),
        total_grupos=len(grupos_payload),
        grupos_validos=len(grupos_payload),
        empresa_id=empresa_id,
        metadata_json={
            "opciones_concepto": {"concepto_modo": "archivo"},
            "opciones_descripcion_item": {"descripcion_item_modo": "archivo"},
        },
    )
    db_session.add(lote)
    await db_session.flush()
    lote_id = int(lote.id)

    grupos: list[LoteComprobanteGrupo] = []
    for orden, (comprobante_ref, payload) in enumerate(grupos_payload, start=1):
        contexto = contextos_por_punto[int(payload["punto_venta_id"])]
        grupo = LoteComprobanteGrupo(
            lote_id=lote_id,
            empresa_id=empresa_id,
            comprobante_ref=comprobante_ref,
            orden=orden,
            estado="validado",
            tipo_comprobante=int(payload["tipo_comprobante"]),
            punto_venta_id=contexto.punto_venta_id,
            punto_venta_numero=contexto.punto_venta_numero,
            ambiente=contexto.ambiente,
            punto_venta_elegibilidad_revision_id=(contexto.elegibilidad_revision_id),
            punto_venta_revision_fiscal=contexto.punto_venta_revision_fiscal,
            cliente_documento=str(payload.get("numero_documento") or ""),
            cliente_razon_social=str(payload.get("razon_social") or ""),
            total_estimado=Decimal("1210.00"),
            payload_json=deepcopy(payload),
            mensajes_json=["Validado correctamente. Listo para emitir."],
        )
        db_session.add(grupo)
        grupos.append(grupo)
    await db_session.flush()

    service = LoteComprobantesService(db_session)
    material_rece = await service.calcular_material_idempotente_grupos(
        lote_id=lote_id,
        empresa_id=empresa_id,
        estados={"validado"},
    )
    idempotencia = IdempotenciaFiscalService(db_session)
    payload_hash = idempotencia.calcular_payload_hash(
        {
            "lote_id": lote_id,
            "grupo_ids": material_rece["grupo_ids"],
            "grupos_hash": material_rece["grupos_hash"],
        }
    )
    operacion, creada = await idempotencia.obtener_o_crear_operacion(
        empresa_id=empresa_id,
        usuario_id=None,
        idempotency_key=idempotency_key,
        tipo_operacion="procesar_lote",
        payload_hash=payload_hash,
        lote_id=lote_id,
        contextos_rece=list(contextos_por_punto.values()),
    )
    assert creada is True
    operacion_id = int(operacion.id)

    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    lote = await service.encolar_lote(
        lote_id=lote_id,
        empresa_id=empresa_id,
        operacion_id=operacion_id,
        material_rece=material_rece,
        commit=False,
    )
    respuesta_encolada = LoteProcesamientoResponse(
        lote=LoteComprobanteResponse.model_validate(lote),
        mensaje="El lote quedó en cola y se está procesando en segundo plano.",
        en_progreso=True,
    )
    publicada = await idempotencia.guardar_respuesta_operacion_cas(
        operacion_id=operacion_id,
        response_json=respuesta_encolada,
        estado="en_proceso",
        estado_esperado="en_proceso",
        respuesta_esperada_nula=True,
        commit=False,
    )
    assert publicada is True
    await db_session.commit()

    await service._tomar_lote_para_procesamiento(
        lote_id=lote_id,
        empresa_id=empresa_id,
        procesamiento_async=True,
        modo_procesamiento="background",
    )
    await db_session.flush()
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    await db_session.refresh(lote)
    lote.updated_at = datetime.utcnow() - timedelta(
        minutes=settings.batch_processing_stale_minutes + 1
    )
    await service._guardar_respuesta_operacion_background(lote, operacion_id)
    await db_session.commit()

    db_session.expire_all()
    lote = await db_session.get(LoteComprobante, lote_id)
    operacion = await db_session.get(OperacionIdempotente, operacion_id)
    grupos_actuales = tuple(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    assert lote is not None
    assert operacion is not None
    assert lote.estado == "procesando"
    assert lote.metadata_json["operacion_idempotente_id"] == operacion_id
    assert lote.metadata_json["pf19b_rece_material"] == material_rece
    assert operacion.estado == "en_proceso"
    assert operacion.response_json["en_progreso"] is True
    assert operacion.response_json["lote"]["estado"] == "procesando"
    assert (
        operacion.response_json["lote"]["metadata_json"]["pf19b_rece_material"]
        == material_rece
    )
    return lote, grupos_actuales


def _instalar_oraculos_stale_sin_arca(
    service: LoteComprobantesService,
) -> dict[str, int]:
    """Hace observables WSAA, FEComp y FECAE en casos stale fail-closed."""
    llamadas = {"wsaa": 0, "fecomp": 0, "fecae": 0}

    async def fail_wsaa(*args, **kwargs):
        llamadas["wsaa"] += 1
        raise AssertionError("El caso stale no debe solicitar WSAA")

    async def fail_fecomp(*args, **kwargs):
        llamadas["fecomp"] += 1
        raise AssertionError("El caso stale no debe consultar FEComp")

    async def fail_fecae(*args, **kwargs):
        llamadas["fecae"] += 1
        raise AssertionError("El caso stale no debe solicitar FECAE")

    service.facturacion_service._obtener_ticket_acceso = fail_wsaa
    service.facturacion_service.verificar_numeracion_segura_para_emision = fail_fecomp
    service.facturacion_service.emitir_comprobante = fail_fecae
    service.facturacion_service._emitir_comprobante_locked = fail_fecae
    return llamadas


@pytest.mark.asyncio
async def test_descargar_plantilla_lote(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.get(
        "/api/lotes-comprobantes/plantilla", headers=auth_headers
    )

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment;" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_obtener_resumen_y_grupos_paginados_lote(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """El detalle paginado debe evitar traer todo el lote para abrir la UI."""
    lote = LoteComprobante(
        nombre_archivo="lote-grande.xlsx",
        archivo_hash="hash-lote-grande-paginado",
        estado="validado",
        total_filas=3,
        total_grupos=3,
        grupos_validos=2,
        grupos_con_error=1,
        empresa_id=test_empresa.id,
    )
    db_session.add(lote)
    await db_session.flush()

    for index, estado in enumerate(["validado", "validado", "con_error"], start=1):
        payload = _payload_lote_basico(test_empresa.id, 1, date(2026, 5, 20))
        payload["items"][0]["descripcion"] = f"Servicio {index}"
        grupo = LoteComprobanteGrupo(
            lote_id=lote.id,
            empresa_id=lote.empresa_id,
            comprobante_ref=f"LOTE-{index:03d}",
            orden=index,
            estado=estado,
            tipo_comprobante=6,
            punto_venta_numero=1,
            cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
            cliente_razon_social=f"Cliente {index}",
            total_estimado=Decimal("1210"),
            payload_json=payload,
            mensajes_json=["Validado correctamente. Listo para emitir."]
            if estado == "validado"
            else ["Observado"],
        )
        db_session.add(grupo)
        await db_session.flush()
        db_session.add(
            LoteComprobanteFila(
                lote_id=lote.id,
                grupo_id=grupo.id,
                fila_excel=index + 1,
                comprobante_ref=grupo.comprobante_ref,
                estado=estado,
                datos_json={"item_descripcion": f"Servicio {index}"},
                mensajes_json=grupo.mensajes_json,
            )
        )
    await db_session.commit()
    material_resumen = await LoteComprobantesService(
        db_session
    ).calcular_material_idempotente_grupos(
        lote_id=lote.id,
        empresa_id=test_empresa.id,
        estados={"validado"},
    )

    resumen = await client.get(
        f"/api/lotes-comprobantes/{lote.id}/resumen",
        headers=auth_headers,
    )
    assert resumen.status_code == 200, resumen.text
    resumen_data = resumen.json()
    assert "grupos" not in resumen_data
    assert "filas" not in resumen_data
    assert resumen_data["confirmacion_fecha_fiscal"] == (
        "fechas=2026-05-20;puntos_venta=1;" f"rece={material_resumen['grupos_hash']}"
    )
    assert resumen_data["fechas_emision_validas"] == ["2026-05-20"]
    assert resumen_data["puntos_venta_validos"] == [1]
    assert resumen_data["totales_listos_para_emitir"] == {
        "comprobantes": 2,
        "neto": 2000,
        "iva21": 420,
        "iva105": 0,
        "total": 2420,
        "valores_invalidos": 0,
    }

    pagina = await client.get(
        f"/api/lotes-comprobantes/{lote.id}/grupos?page=1&per_page=2",
        headers=auth_headers,
    )
    assert pagina.status_code == 200, pagina.text
    pagina_data = pagina.json()
    assert pagina_data["total"] == 3
    assert pagina_data["total_pages"] == 2
    assert [item["comprobante_ref"] for item in pagina_data["items"]] == [
        "LOTE-001",
        "LOTE-002",
    ]
    assert pagina_data["items"][0]["descripcion_facturada"] == "Servicio 1"

    filtrada = await client.get(
        f"/api/lotes-comprobantes/{lote.id}/grupos?estado=validado&per_page=10",
        headers=auth_headers,
    )
    assert filtrada.status_code == 200, filtrada.text
    filtrada_data = filtrada.json()
    assert filtrada_data["total"] == 2
    assert {item["estado"] for item in filtrada_data["items"]} == {"validado"}


@pytest.mark.asyncio
async def test_seguimiento_lote_es_liviano_y_no_muta_updated_at(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El polling consulta una vez el resumen persistido y no refresca el lote."""
    lote = LoteComprobante(
        nombre_archivo="lote-seguimiento.xlsx",
        archivo_hash="hash-lote-seguimiento-liviano",
        estado="en_cola",
        modo_procesamiento="background",
        procesamiento_async=True,
        total_filas=200,
        total_grupos=100,
        grupos_validos=100,
        empresa_id=test_empresa.id,
    )
    db_session.add(lote)
    await db_session.commit()
    await db_session.refresh(lote)
    updated_at_antes = lote.updated_at

    original = LoteComprobantesService.obtener_seguimiento_lote
    consultas = 0

    async def contar_consulta(
        self: LoteComprobantesService,
        lote_id: int,
        empresa_id: int,
    ) -> LoteComprobanteSeguimientoResponse:
        nonlocal consultas
        consultas += 1
        return await original(self, lote_id, empresa_id)

    monkeypatch.setattr(
        LoteComprobantesService,
        "obtener_seguimiento_lote",
        contar_consulta,
    )

    response = await client.get(
        f"/api/lotes-comprobantes/{lote.id}/seguimiento",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert consultas == 1
    assert data["id"] == lote.id
    assert data["estado"] == "en_cola"
    assert data["modo_procesamiento"] == "background"
    assert set(data) == {
        "operacion_progreso",
        "id",
        "estado",
        "modo_procesamiento",
        "procesamiento_async",
        "total_filas",
        "total_grupos",
        "grupos_validos",
        "grupos_con_error",
        "grupos_emitidos",
        "grupos_fallidos",
        "grupos_reconciliados_externos",
        "grupos_descartados",
        "mensaje_resumen",
        "started_at",
        "finished_at",
        "updated_at",
    }
    for forbidden in (
        "archivo_hash",
        "metadata_json",
        "mapeo_usado_json",
        "headers_detectados_json",
        "empresa_id",
        "usuario_id",
        "formato_importacion_id",
    ):
        assert forbidden not in data
    await db_session.refresh(lote)
    assert lote.updated_at == updated_at_antes


@pytest.mark.asyncio
async def test_seguimiento_lote_respeta_scope_del_emisor(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """Un usuario común no puede seguir lotes de otro emisor."""
    otra_empresa = Empresa(
        razon_social="Otra Empresa Test S.A.",
        cuit="20999999991",
        condicion_iva="RI",
        domicilio="Av. Prueba 456",
        localidad="Buenos Aires",
        provincia="Buenos Aires",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(otra_empresa)
    await db_session.flush()
    lote_ajeno = LoteComprobante(
        nombre_archivo="lote-ajeno-seguimiento.xlsx",
        archivo_hash="hash-lote-ajeno-seguimiento",
        estado="en_cola",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=otra_empresa.id,
    )
    db_session.add(lote_ajeno)
    await db_session.commit()

    response = await client.get(
        f"/api/lotes-comprobantes/{lote_ajeno.id}/seguimiento",
        headers={**auth_headers, "X-Empresa-Id": str(otra_empresa.id)},
    )

    assert response.status_code == 403
    assert "permiso" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("con_perfil", [False, True])
@pytest.mark.parametrize(
    "campo,valor,valido",
    [
        ("item_descuento_porcentaje", None, True),
        ("item_descuento_porcentaje", 0, True),
        ("item_descuento_porcentaje", 100, True),
        ("item_descuento_porcentaje", "10,5", True),
        ("item_descuento_porcentaje", "ilegible", False),
        ("item_descuento_porcentaje", -1, False),
        ("item_descuento_porcentaje", 101, False),
        ("item_descuento_porcentaje", "NaN", False),
        ("item_descuento_porcentaje", "Infinity", False),
        ("item_cantidad", "NaN", False),
        ("item_precio_unitario", "Infinity", False),
        ("item_precio_unitario", "1e30", False),
        ("importe_total", "ilegible", False),
        ("importe_total", "NaN", False),
    ],
)
async def test_pf03b_importacion_rechaza_valores_sin_sustituirlos(
    client,
    auth_headers,
    db_session,
    test_empresa,
    test_punto_venta,
    test_certificado,
    campo,
    valor,
    valido,
    con_perfil,
):
    workbook = load_workbook(BytesIO(_build_lote_excel(test_empresa.cuit)))
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    if campo not in headers:
        headers.append(campo)
        sheet.cell(1, len(headers), campo)
    sheet.cell(2, headers.index(campo) + 1).value = valor
    output = BytesIO()
    workbook.save(output)
    opciones = _opciones_fechas()
    if con_perfil:
        campos = {
            header: {"origen": "header", "encabezados": [header]} for header in headers
        }
        for nombre in (
            "item_cantidad",
            "item_precio_unitario",
            "item_descuento_porcentaje",
            "item_iva_porcentaje",
            "importe_total",
        ):
            if nombre in campos:
                campos[nombre]["transformacion"] = "decimal"
        formato = await client.post(
            "/api/formatos-importacion",
            headers=auth_headers,
            json={
                "nombre": "PF03B formato con decimales",
                "alcance": "emisor",
                "configuracion_json": {
                    "tipo": "pf03b",
                    "header_row": 1,
                    "campos": campos,
                },
            },
        )
        assert formato.status_code == 201, formato.text
        perfil = await client.post(
            "/api/perfiles-carga-masiva",
            headers=auth_headers,
            json={
                "nombre": "PF03B perfil de importación",
                "configuracion_json": {
                    "version": 1,
                    "formato_importacion_version_id": formato.json()["version_vigente"][
                        "id"
                    ],
                    "concepto_modo": "productos",
                    "descripcion_item_modo": "archivo",
                    "fecha_emision": {"modo": "archivo"},
                    "periodo_servicio": {"modo": "archivo"},
                    "fecha_vto_pago": {"modo": "archivo"},
                },
            },
        )
        assert perfil.status_code == 201, perfil.text
        opciones["perfil_carga_masiva_id"] = str(perfil.json()["id"])
        opciones["formato_version_id"] = str(formato.json()["version_vigente"]["id"])
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=opciones,
        files={
            "archivo": (
                "pf03b.xlsx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["puede_emitirse"] is valido
    if con_perfil:
        lote = await db_session.get(LoteComprobante, response.json()["lote"]["id"])
        assert (
            lote.formato_importacion_version_id
            == formato.json()["version_vigente"]["id"]
        )
    detalle = await client.get(
        f"/api/lotes-comprobantes/{response.json()['lote']['id']}",
        headers=auth_headers,
    )
    assert detalle.status_code == 200, detalle.text
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == ("validado" if valido else "con_error")
    if not valido:
        assert grupo["total_estimado"] == "0.00"
    assert (await db_session.scalars(select(IntentoEmisionFiscal))).all() == []
    assert (await db_session.scalars(select(OperacionIdempotente))).all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("configurable", [False, True])
async def test_pf03b_xlsx_no_finito_numerico_conserva_json_y_error(
    client,
    auth_headers,
    db_session,
    test_empresa,
    test_punto_venta,
    test_certificado,
    configurable,
):
    original = _build_lote_excel(test_empresa.cuit)
    data = _opciones_fechas()
    if configurable:
        sheet = load_workbook(BytesIO(original)).active
        campos = {
            cell.value: {"origen": "header", "encabezados": [cell.value]}
            for cell in sheet[1]
        }
        crear = await client.post(
            "/api/formatos-importacion",
            headers=auth_headers,
            json={
                "nombre": "Formato PF03B sin transformación",
                "alcance": "emisor",
                "configuracion_json": {
                    "tipo": "pf03b",
                    "header_row": 1,
                    "campos": campos,
                },
            },
        )
        assert crear.status_code == 201, crear.text
        data["formato_version_id"] = str(crear.json()["version_vigente"]["id"])
    output = BytesIO()
    with ZipFile(BytesIO(original)) as source, ZipFile(output, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                root = ElementTree.fromstring(content)
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                root.find(".//s:c[@r='S2']/s:v", ns).text = "1e309"
                content = ElementTree.tostring(root)
            target.writestr(info, content)
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=data,
        files={
            "archivo": (
                "pf03b-infinito.xlsx",
                output.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["puede_emitirse"] is False
    detalle = await client.get(
        f"/api/lotes-comprobantes/{response.json()['lote']['id']}", headers=auth_headers
    )
    assert detalle.status_code == 200, detalle.text
    filas = (await db_session.scalars(select(LoteComprobanteFila))).all()
    assert isinstance(filas[0].datos_json["item_precio_unitario"], str)
    assert filas[0].datos_json["item_precio_unitario"]
    json.dumps(filas[0].datos_json, allow_nan=False)
    assert (await db_session.scalars(select(IntentoEmisionFiscal))).all() == []
    assert (await db_session.scalars(select(OperacionIdempotente))).all() == []


@pytest.mark.parametrize(
    "invalidez", ["extra", "descuento", "estimado_nan", "estimado_negativo"]
)
def test_pf03b_resumen_no_totaliza_snapshot_invalido(invalidez):
    valido = _payload_lote_basico(1, 1, FECHA_FISCAL_CONTROLADA_PF19B)
    invalido = deepcopy(valido)
    estimado = Decimal("1210")
    if invalidez == "extra":
        invalido["items"][0]["subtotal"] = 999
    elif invalidez == "descuento":
        invalido["items"][0]["descuento_porcentaje"] = 101
    else:
        estimado = Decimal("NaN" if invalidez == "estimado_nan" else "-1")
    service = LoteComprobantesService(None)
    result = service._calcular_totales_payloads(
        [(valido, 1, Decimal("1210")), (invalido, 1, estimado)]
    )
    assert result["valores_invalidos"] == 1
    assert result["comprobantes"] == 1
    assert result["total"] == Decimal("1210.00")


@pytest.mark.asyncio
async def test_validar_lote_registra_grupos_y_filas(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True
    assert data["lote"]["estado"] == "validado"
    assert data["lote"]["grupos_validos"] == 1
    assert data["lote"]["grupos_con_error"] == 0

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    assert detalle.status_code == 200
    detalle_data = detalle.json()
    assert len(detalle_data["grupos"]) == 1
    assert len(detalle_data["filas"]) == 1
    assert detalle_data["grupos"][0]["estado"] == "validado"


@pytest.mark.asyncio
async def test_validar_lote_productos_acepta_fechas_servicio_omitidas(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote de productos no debe exigir campos de servicio en multipart."""
    data = _opciones_fechas(concepto_modo="productos")
    for key in [
        "fecha_servicio_desde_modo",
        "fecha_servicio_hasta_modo",
        "fecha_vto_pago_modo",
    ]:
        data.pop(key)

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=data,
        files={
            "archivo": (
                "lote-productos-sin-servicio.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    detalle = await client.get(
        f"/api/lotes-comprobantes/{response.json()['lote']['id']}",
        headers=auth_headers,
    )
    assert detalle.status_code == 200, detalle.text
    grupo = detalle.json()["grupos"][0]
    assert grupo["concepto"] == 1
    assert grupo["fecha_servicio_desde"] is None
    assert grupo["fecha_servicio_hasta"] is None
    assert grupo["fecha_vto_pago"] is None


@pytest.mark.asyncio
async def test_validar_lote_mixto_no_anuncia_emision_si_estado_no_procesable(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote con errores conserva contrato consistente: no puede emitirse."""
    workbook = load_workbook(BytesIO(_build_lote_excel_multi_grupo(test_empresa.cuit)))
    sheet = workbook["Comprobantes"]
    sheet.cell(row=3, column=4).value = 11
    sheet.cell(row=3, column=21).value = 21
    stream = BytesIO()
    workbook.save(stream)

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-mixto.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["estado"] == "con_errores"
    assert data["lote"]["grupos_validos"] == 1
    assert data["lote"]["grupos_con_error"] == 1


@pytest.mark.asyncio
async def test_validar_lote_rechaza_xlsx_malformado(
    client: AsyncClient,
    auth_headers: dict,
):
    """Un .xlsx corrupto debe devolver error funcional, no 500."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "corrupto.xlsx",
                b"esto no es un zip",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "No se pudo leer el archivo Excel" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_rechaza_archivo_demasiado_grande(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """El límite de bytes debe aplicarse antes de parsear el Excel."""
    monkeypatch.setattr(settings, "batch_max_upload_bytes", 10)

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "grande.xlsx",
                b"01234567890",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "tamaño máximo" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_punto_venta_fijo_sobrescribe_archivo(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe permitir fijar un punto de venta habilitado para todo el lote."""
    punto_fijo = PuntoVenta(
        numero=13,
        nombre="Web Services 13",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_fijo)
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            punto_venta_modo="fijo",
            punto_venta_numero=13,
        ),
        files={
            "archivo": (
                "lote-pv-fijo.xlsx",
                _build_lote_excel(test_empresa.cuit, punto_venta_numero=1),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    detalle = await client.get(
        f"/api/lotes-comprobantes/{response.json()['lote']['id']}",
        headers=auth_headers,
    )
    detalle_data = detalle.json()
    assert detalle_data["grupos"][0]["punto_venta_numero"] == 13
    assert detalle_data["filas"][0]["datos_json"]["punto_venta_numero"] == 13
    assert (
        detalle_data["metadata_json"]["opciones_punto_venta"]["punto_venta_numero"]
        == 13
    )


@pytest.mark.asyncio
async def test_validar_lote_acepta_fecha_fija_argentina(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe aceptar DD/MM/AAAA en fechas fijas del formulario."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            fecha_emision_modo="fija",
            fecha_emision_fija="20/05/2026",
        ),
        files={
            "archivo": (
                "lote-fecha-fija-argentina.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    detalle = await client.get(
        f"/api/lotes-comprobantes/{response.json()['lote']['id']}",
        headers=auth_headers,
    )
    assert detalle.json()["grupos"][0]["fecha_emision"] == "2026-05-20"


@pytest.mark.asyncio
async def test_validar_lote_rechaza_fecha_fija_argentina_invalida(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe rechazar fechas fijas con calendario imposible."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            fecha_emision_modo="fija",
            fecha_emision_fija="31/02/2026",
        ),
        files={
            "archivo": (
                "lote-fecha-fija-invalida.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "fecha_emision_fija debe ser una fecha válida" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_rechaza_punto_venta_fijo_no_habilitado(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe validar con un punto fijo no usable por el emisor activo."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            punto_venta_modo="fijo",
            punto_venta_numero=99,
        ),
        files={
            "archivo": (
                "lote-pv-invalido.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "Puntos de venta" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_guarda_snapshot_perfil_carga_masiva(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe conservar el perfil usado aunque luego se edite."""
    test_certificado.ambiente = settings.arca_env
    perfil = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json={
            "nombre": "Servicios mensuales",
            "descripcion": "Perfil de prueba",
            "configuracion_json": {
                "version": 1,
                "formato_importacion_version_id": None,
                "concepto_modo": "productos",
                "descripcion_item_modo": "archivo",
                "fecha_emision": {"modo": "archivo"},
                "periodo_servicio": {"modo": "archivo"},
                "fecha_vto_pago": {"modo": "archivo"},
            },
            "es_predeterminado": True,
            "activo": True,
        },
    )
    assert perfil.status_code == 201, perfil.text

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(),
            "perfil_carga_masiva_id": str(perfil.json()["id"]),
        },
        files={
            "archivo": (
                "lote-con-perfil.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    detalle = await client.get(
        f"/api/lotes-comprobantes/{response.json()['lote']['id']}",
        headers=auth_headers,
    )
    metadata = detalle.json()["metadata_json"]
    assert metadata["perfil_carga_masiva"]["id"] == perfil.json()["id"]
    assert metadata["perfil_carga_masiva"]["nombre"] == "Servicios mensuales"
    assert (
        metadata["perfil_carga_masiva"]["configuracion_json"]["concepto_modo"]
        == "productos"
    )


@pytest.mark.asyncio
async def test_validar_lote_rechaza_descripcion_item_faltante(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe validar un lote sin política de descripción facturada."""
    opciones = _opciones_fechas()
    opciones.pop("descripcion_item_modo")

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=opciones,
        files={
            "archivo": (
                "lote-sin-descripcion-modo.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validar_lote_descripcion_item_fija_sobrescribe_archivo(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe aplicar la descripción fija elegida para todo el lote."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            descripcion_item_modo="fija",
            descripcion_item_fija="Honorarios profesionales",
        ),
        files={
            "archivo": (
                "lote-descripcion-fija.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    fila = detalle.json()["filas"][0]
    assert fila["datos_json"]["item_descripcion"] == "Honorarios profesionales"


@pytest.mark.asyncio
async def test_validar_lote_rechaza_empresa_distinta(
    client: AsyncClient,
    auth_headers: dict,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-otra-empresa.xlsx",
                _build_lote_excel("30999999999"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "empresa activa" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_rechaza_iva_invalido(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-iva-invalido.xlsx",
                _build_lote_excel(test_empresa.cuit, iva=22),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["estado"] == "con_errores"
    assert data["lote"]["grupos_con_error"] == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("alícuota de IVA" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_rechaza_factura_c_con_iva(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Factura C no puede quedar lista si el archivo trae IVA."""
    test_empresa.condicion_iva = "Exento"
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-factura-c-con-iva.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    tipo_comprobante=11,
                    iva=21,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="A CONSUMIDOR FINAL",
                    cliente_condicion_iva="Consumidor Final",
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["estado"] == "con_errores"

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("tipo C no pueden incluir IVA" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "condicion", ["", "RNI", "Responsable No Inscripto", "Otra", "RI"]
)
async def test_rg5616_importacion_no_infiere_iva_por_documento_99(
    client, auth_headers, test_empresa, test_punto_venta, test_certificado, condicion
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "iva-receptor-invalido.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    cliente_tipo_documento="CI",
                    cliente_numero_documento="",
                    cliente_razon_social="",
                    cliente_condicion_iva=condicion,
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}", headers=auth_headers
    )
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == "con_error"
    assert "IVA" in str(grupo["mensajes_json"])


@pytest.mark.asyncio
async def test_validar_lote_consumidor_final_sin_documento_bajo_umbral(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-cf-sin-documento.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="",
                    cliente_condicion_iva="Consumidor Final",
                    item_precio_unitario=1000,
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == "validado"
    assert grupo["cliente_documento"] == "0"
    assert grupo["cliente_razon_social"] == "A CONSUMIDOR FINAL"


@pytest.mark.asyncio
async def test_validar_lote_nota_credito_requiere_comprobante_asociado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una nota de crédito no puede quedar lista sin comprobante asociado."""
    test_empresa.condicion_iva = "Exento"
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(concepto_modo="servicios"),
        files={
            "archivo": (
                "lote-nc-sin-asociado.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    tipo_comprobante=13,
                    concepto=2,
                    iva=0,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="A CONSUMIDOR FINAL",
                    cliente_condicion_iva="Consumidor Final",
                    fecha_servicio_desde=FECHA_FISCAL_CONTROLADA_PF19B,
                    fecha_servicio_hasta=FECHA_FISCAL_CONTROLADA_PF19B,
                    fecha_vto_pago=FECHA_FISCAL_CONTROLADA_PF19B,
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["grupos_con_error"] == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("requiere comprobante asociado" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_nota_debito_requiere_comprobante_asociado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una nota de débito no puede quedar lista sin comprobante asociado."""
    test_empresa.condicion_iva = "Exento"
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(concepto_modo="servicios"),
        files={
            "archivo": (
                "lote-nd-sin-asociado.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    tipo_comprobante=12,
                    concepto=2,
                    iva=0,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="A CONSUMIDOR FINAL",
                    cliente_condicion_iva="Consumidor Final",
                    fecha_servicio_desde=date(2026, 5, 31),
                    fecha_servicio_hasta=date(2026, 5, 31),
                    fecha_vto_pago=date(2026, 5, 31),
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["grupos_con_error"] == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("requiere comprobante asociado" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_nota_credito_guarda_comprobante_asociado_en_payload(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El lote debe persistir el asociado que luego se informa como CbtesAsoc."""
    test_empresa.condicion_iva = "Exento"
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(concepto_modo="servicios"),
        files={
            "archivo": (
                "lote-nc-con-asociado.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    tipo_comprobante=13,
                    concepto=2,
                    iva=0,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="A CONSUMIDOR FINAL",
                    cliente_condicion_iva="Consumidor Final",
                    fecha_servicio_desde=FECHA_FISCAL_CONTROLADA_PF19B,
                    fecha_servicio_hasta=FECHA_FISCAL_CONTROLADA_PF19B,
                    fecha_vto_pago=FECHA_FISCAL_CONTROLADA_PF19B,
                    asociado_tipo_comprobante=11,
                    asociado_punto_venta=1,
                    asociado_numero=1234,
                    asociado_fecha=date(2026, 4, 30),
                    asociado_cuit=test_empresa.cuit,
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True
    stmt = select(LoteComprobanteGrupo).where(
        LoteComprobanteGrupo.lote_id == data["lote"]["id"]
    )
    grupo = (await db_session.execute(stmt)).scalar_one()
    asociado = grupo.payload_json["comprobantes_asociados"][0]
    assert asociado["tipo_comprobante"] == 11
    assert asociado["punto_venta"] == 1
    assert asociado["numero"] == 1234
    assert asociado["fecha"] == "2026-04-30"
    assert asociado["cuit"] == test_empresa.cuit


@pytest.mark.asyncio
async def test_detectar_formato_extracto_bancario(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    response = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-bancario.xlsx",
                _build_extracto_bancario_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["headers_detectados"] == [
        "Fecha",
        "Créditos",
        "Leyendas Adicionales1",
        "Leyendas Adicionales2",
        "Pto Vta",
    ]
    assert data["formato_sugerido_version_id"] is not None
    assert data["candidatos"][0]["confianza"] == "alta"


@pytest.mark.asyncio
async def test_detectar_formato_rechaza_archivo_demasiado_grande(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """La detección de formatos debe aplicar el mismo límite de upload."""
    monkeypatch.setattr(settings, "batch_max_upload_bytes", 10)

    response = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "grande.xlsx",
                b"01234567890",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "tamaño máximo" in response.json()["detail"]


@pytest.mark.asyncio
async def test_crear_formato_rechaza_configuracion_malformada(
    client: AsyncClient,
    auth_headers: dict,
):
    """La configuración de formato debe validarse antes de persistir."""
    response = await client.post(
        "/api/formatos-importacion",
        headers=auth_headers,
        json={
            "nombre": "Formato invalido",
            "descripcion": "No debe persistirse",
            "configuracion_json": {"campos": {"importe_total": None}},
        },
    )

    assert response.status_code == 400
    assert "debe ser un objeto" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_formato_cano_factura_b_iva_21(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    test_punto_venta,
    test_certificado,
):
    """Debe validar el formato Cano como Factura B con IVA 21%."""
    test_empresa.condicion_iva = "RI"
    await _crear_punto_venta_rece_verificado(
        db_session,
        test_empresa,
        usuario_id=int(test_user.id),
        numero=2,
        nombre="Cano PV 2",
        documento_emitido_en=FECHA_DOCUMENTO_RECE_TEST,
        vigente_hasta=FECHA_VIGENCIA_RECE_TEST,
        observado_en=INSTANTE_RECE_TEST,
    )
    await db_session.commit()

    crear = await client.post(
        "/api/formatos-importacion",
        headers=auth_headers,
        json={
            "nombre": "Cano - Factura B IVA 21%",
            "descripcion": (
                "Formato particular para planillas Cano: neto gravado, IVA "
                "discriminado y total de Factura B a consumidor final."
            ),
            "configuracion_json": _config_formato_cano_factura_b(),
        },
    )
    assert crear.status_code == 201, crear.text

    contenido = _build_cano_factura_b_excel(FECHA_FISCAL_CONTROLADA_PF19B)
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "cano-factura-b.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert detectar.status_code == 200, detectar.text
    formato_version_id = detectar.json()["formato_sugerido_version_id"]
    assert formato_version_id == crear.json()["version_vigente"]["id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="productos",
                descripcion_item_modo="fija",
                descripcion_item_fija="Venta mostrador",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "cano-factura-b.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True
    assert data["lote"]["grupos_validos"] == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupo = detalle.json()["grupos"][0]
    fila = detalle.json()["filas"][0]["datos_json"]
    assert grupo["tipo_comprobante"] == 6
    assert grupo["punto_venta_numero"] == 2
    assert grupo["cliente_documento"] == "0"
    assert grupo["total_estimado"] == "90000.00"
    assert fila["item_precio_unitario"] == "74380.1652892562"
    assert fila["item_iva_porcentaje"] == 21


@pytest.mark.asyncio
async def test_validar_lote_formato_cano_bloquea_total_usado_como_neto(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe bloquear un formato que recalcula IVA sobre un total ya final."""
    test_empresa.condicion_iva = "RI"
    db_session.add(
        PuntoVenta(
            numero=2,
            nombre="Cano PV 2",
            activo=True,
            es_webservice=True,
            empresa_id=test_empresa.id,
        )
    )
    await db_session.commit()

    configuracion = _config_formato_cano_factura_b()
    configuracion["campos"]["item_precio_unitario"] = {
        "origen": "header",
        "encabezados": ["Imp. Total"],
        "transformacion": "decimal",
        "requerido": True,
    }
    crear = await client.post(
        "/api/formatos-importacion",
        headers=auth_headers,
        json={
            "nombre": "Cano - Formato erroneo total como neto",
            "descripcion": "Config de prueba que no debe quedar emitible.",
            "configuracion_json": configuracion,
        },
    )
    assert crear.status_code == 201, crear.text

    contenido = _build_cano_factura_b_excel(FECHA_FISCAL_CONTROLADA_PF19B)
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="productos",
                descripcion_item_modo="fija",
                descripcion_item_fija="Venta mostrador",
            ),
            "formato_version_id": str(crear.json()["version_vigente"]["id"]),
        },
        files={
            "archivo": (
                "cano-total-como-neto.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["grupos_con_error"] == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("no coincide con el total informado" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_extracto_bancario_varios_puntos_venta(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    test_punto_venta,
    test_certificado,
):
    test_empresa.condicion_iva = "Exento"
    for numero in [10, 13]:
        await _crear_punto_venta_rece_verificado(
            db_session,
            test_empresa,
            usuario_id=int(test_user.id),
            numero=numero,
            nombre=f"Punto {numero}",
            documento_emitido_en=FECHA_DOCUMENTO_RECE_TEST,
            vigente_hasta=FECHA_VIGENCIA_RECE_TEST,
            observado_en=INSTANTE_RECE_TEST,
        )
    await db_session.commit()
    contenido = _build_extracto_bancario_excel(
        test_empresa.cuit,
        fecha_movimiento=FECHA_FISCAL_CONTROLADA_PF19B,
    )
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-bancario-multi-pv.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-bancario-multi-pv.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True
    assert data["lote"]["grupos_validos"] == 3
    assert data["lote"]["formato_importacion_version_id"] is not None

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupos = detalle.json()["grupos"]
    assert [grupo["punto_venta_numero"] for grupo in grupos] == [1, 10, 13]
    assert [grupo["cliente_documento"] for grupo in grupos] == ["0", "0", "0"]
    assert [grupo["total_estimado"] for grupo in grupos] == [
        "59500.00",
        "70500.00",
        "140000.00",
    ]
    assert [grupo["concepto"] for grupo in grupos] == [2, 2, 2]
    assert grupos[0]["fecha_emision"] == FECHA_FISCAL_CONTROLADA_PF19B.isoformat()


@pytest.mark.asyncio
async def test_validar_lote_formato_con_header_blanco_preserva_indices(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_user,
    test_punto_venta,
    test_certificado,
):
    """Los headers vacíos no deben desplazar los índices físicos del Excel."""
    test_empresa.condicion_iva = "Exento"
    for numero in [10, 13]:
        await _crear_punto_venta_rece_verificado(
            db_session,
            test_empresa,
            usuario_id=int(test_user.id),
            numero=numero,
            nombre=f"Punto {numero}",
            documento_emitido_en=FECHA_DOCUMENTO_RECE_TEST,
            vigente_hasta=FECHA_VIGENCIA_RECE_TEST,
            observado_en=INSTANTE_RECE_TEST,
        )
    await db_session.commit()
    workbook = load_workbook(
        BytesIO(
            _build_extracto_bancario_excel(
                test_empresa.cuit,
                fecha_movimiento=FECHA_FISCAL_CONTROLADA_PF19B,
            )
        )
    )
    workbook.active.insert_cols(1)
    stream = BytesIO()
    workbook.save(stream)
    contenido = stream.getvalue()

    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-header-blanco.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert detectar.status_code == 200, detectar.text
    assert detectar.json()["headers_detectados"][0] == ""
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-header-blanco.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupos = detalle.json()["grupos"]
    assert [grupo["punto_venta_numero"] for grupo in grupos] == [1, 10, 13]
    assert [grupo["total_estimado"] for grupo in grupos] == [
        "59500.00",
        "70500.00",
        "140000.00",
    ]


@pytest.mark.asyncio
async def test_validar_lote_rechaza_fecha_emision_fuera_de_ventana_arca(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe observar el lote si la fecha del archivo no puede usarse en ARCA."""
    test_empresa.condicion_iva = "Exento"
    for numero in [10, 13]:
        db_session.add(
            PuntoVenta(
                numero=numero,
                nombre=f"Punto {numero}",
                activo=True,
                es_webservice=True,
                empresa_id=test_empresa.id,
            )
        )
    await db_session.commit()
    contenido = _build_extracto_bancario_excel(
        test_empresa.cuit,
        fecha_movimiento=FECHA_FISCAL_CONTROLADA_PF19B - timedelta(days=20),
        fecha_como_serial=True,
    )
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-fecha-vieja.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-fecha-vieja.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["grupos_con_error"] == 3

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("ventana ARCA" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_concepto_definido_por_archivo(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe aceptar Producto/Servicio del Excel cuando se elige archivo."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(concepto_modo="archivo"),
        files={
            "archivo": (
                "lote-concepto-archivo.xlsx",
                _build_lote_excel(test_empresa.cuit, concepto="Producto"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupo = detalle.json()["grupos"][0]
    assert grupo["concepto"] == 1


@pytest.mark.asyncio
async def test_validar_lote_rechaza_concepto_archivo_sin_columna(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe rechazar 'Definido por archivo' si el formato no trae columna."""
    test_empresa.condicion_iva = "Exento"
    contenido = _build_extracto_bancario_excel(test_empresa.cuit)
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-sin-concepto.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="archivo",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-sin-concepto.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "columna de concepto fiscal" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_rechaza_descripcion_archivo_sin_columna(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe rechazar descripción desde archivo si el formato no la mapea."""
    test_empresa.condicion_iva = "Exento"
    contenido = _build_extracto_bancario_excel(test_empresa.cuit)
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-sin-descripcion.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="archivo",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-sin-descripcion.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "descripción facturada" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_extracto_bancario_exige_confirmar_formato(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "extracto-sin-formato.xlsx",
                _build_extracto_bancario_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "formato de importación" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_extracto_bancario_rechaza_factura_c_para_ri(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    for numero in [10, 13]:
        db_session.add(
            PuntoVenta(
                numero=numero,
                nombre=f"Punto {numero}",
                activo=True,
                es_webservice=True,
                empresa_id=test_empresa.id,
            )
        )
    await db_session.commit()
    contenido = _build_extracto_bancario_excel(test_empresa.cuit)
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-ri.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-ri.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["grupos_con_error"] == 3

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("Responsable Inscripto" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_consumidor_final_sin_documento_sobre_umbral(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-cf-sin-documento-alto.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="",
                    cliente_condicion_iva="Consumidor Final",
                    item_precio_unitario=10_000_000,
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("$10.000.000" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_rechaza_archivo_duplicado(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    contenido = _build_lote_excel(test_empresa.cuit)
    files = {
        "archivo": (
            "lote-duplicado.xlsx",
            contenido,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    primera = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files=files,
    )
    assert primera.status_code == 200, primera.text

    segunda = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-duplicado.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert segunda.status_code == 400
    assert "ya fue cargado" in segunda.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_permite_reintentar_fallido_sin_emitidos(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote fallido sin CAE emitidos puede revalidarse con el mismo archivo."""
    contenido = _build_lote_excel(test_empresa.cuit)
    files = {
        "archivo": (
            "lote-reintento.xlsx",
            contenido,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    primera = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files=files,
    )
    assert primera.status_code == 200, primera.text
    lote_id = primera.json()["lote"]["id"]

    lote_previo = await db_session.get(LoteComprobante, lote_id)
    lote_previo.estado = "fallido"
    lote_previo.grupos_validos = 0
    lote_previo.grupos_fallidos = 1
    lote_previo.grupos_emitidos = 0
    await db_session.commit()

    segunda = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-reintento.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["lote"]["id"] != lote_id
    await db_session.refresh(lote_previo)
    assert lote_previo.metadata_json["reemplazado_por_reintento"][
        "archivo_hash_original"
    ]


@pytest.mark.asyncio
async def test_procesar_lote_sync_actualiza_resultados(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    test_certificado.ambiente = settings.arca_env
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=456,
            fecha_emision=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=456,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-procesar.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is False
    assert data["lote"]["estado"] == "completado"
    assert data["lote"]["grupos_emitidos"] == 1
    assert data["lote"]["grupos_fallidos"] == 0
    assert llamadas == 1

    replay = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert replay.status_code == 200, replay.text
    replay_data = replay.json()
    assert replay_data["en_progreso"] is False
    assert replay_data["lote"]["estado"] == "completado"
    assert replay_data["lote"]["grupos_emitidos"] == 1
    assert llamadas == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/resultados",
        headers=auth_headers,
    )
    assert detalle.status_code == 200
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == "autorizado"
    assert grupo["cae"] == CAE_TEST_NO_REAL


@pytest.mark.asyncio
async def test_procesar_lote_no_reabre_reserva_tras_cambio_tardio_de_evidencia(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-evidencia-tardia-procesar.xlsx",
    )
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="idem-evidencia-tardia-procesar",
    )

    async def cambio_tardio(self, lote_id, empresa_id, **kwargs):
        await self.db.execute(
            update(LoteComprobanteGrupo)
            .where(
                LoteComprobanteGrupo.lote_id == lote_id,
                LoteComprobanteGrupo.empresa_id == empresa_id,
            )
            .values(duplicados_reserva_operacion_id=None)
        )
        await self.db.commit()
        raise LoteDuplicadosEvidenciaCambioError(
            "La evidencia cambió antes de solicitar CAE."
        )

    monkeypatch.setattr(LoteComprobantesService, "procesar_lote", cambio_tardio)

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )

    assert response.status_code == 409, response.text
    db_session.expire_all()
    reservas = list(
        await db_session.scalars(
            select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                LoteComprobanteGrupo.lote_id == lote_id
            )
        )
    )
    assert reservas and all(reserva is None for reserva in reservas)


@pytest.mark.asyncio
@pytest.mark.parametrize("anidado", [False, True])
async def test_procesar_lote_sanitiza_payload_con_clave_desconocida(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    anidado,
) -> None:
    """El procesamiento no debe exponer el valor de un payload no canónico."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-payload-no-canonico.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["validado"])
    grupo = grupos[0]
    valor_no_publicable = "dato-sintetico-no-publicable"
    payload = deepcopy(grupo.payload_json or {})
    destino = payload["items"][0] if anidado else payload
    destino["instruccion_fiscal_desconocida"] = valor_no_publicable
    grupo.payload_json = payload
    await db_session.commit()
    llamadas_emision = 0

    async def fail_emitir(self, request, **kwargs):
        nonlocal llamadas_emision
        llamadas_emision += 1
        raise AssertionError("No debe emitir un payload fiscal no canónico")

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fail_emitir)

    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="idem-lote-payload-no-canonico",
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert response.status_code == 200, response.text
    assert llamadas_emision == 0
    await db_session.refresh(grupo)
    assert grupo.estado == "fallido"
    assert grupo.mensajes_json == [
        "El payload fiscal guardado no cumple el contrato vigente. "
        "No se solicitó CAE; revisá el lote antes de reintentar."
    ]
    assert valor_no_publicable not in response.text
    assert valor_no_publicable not in str(grupo.mensajes_json)
    assert grupo.numero_asignado is None
    assert grupo.cae is None
    assert grupo.comprobante_id is None


@pytest.mark.asyncio
async def test_procesar_lote_background_encola_lote_chico(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Permite iniciar un lote chico en segundo plano para observar progreso."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: True,
    )
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        numero = 500 + llamadas
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=numero,
            fecha_emision=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=numero,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-background-chico.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    confirmacion = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **confirmacion},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is True
    assert data["lote"]["estado"] == "en_cola"
    assert data["lote"]["modo_procesamiento"] == "background"

    operacion = (
        (
            await db_session.execute(
                select(OperacionIdempotente).where(
                    OperacionIdempotente.idempotency_key == "idem-lote-test"
                )
            )
        )
        .scalars()
        .one()
    )
    assert operacion.estado == "en_proceso"
    assert operacion.response_json["en_progreso"] is True

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        lote_publicado = await observador.get(LoteComprobante, lote_id)
        operacion_publicada = await observador.get(
            OperacionIdempotente,
            operacion.id,
        )
        assert lote_publicado.estado == "en_cola"
        assert lote_publicado.metadata_json["operacion_idempotente_id"] == operacion.id
        assert operacion_publicada.estado == "en_proceso"
        assert operacion_publicada.response_json["en_progreso"] is True
        assert operacion_publicada.response_json["lote"]["id"] == lote_id

    service = LoteComprobantesService(db_session)
    lote = await service.procesar_lote(
        lote_id,
        inspect(test_empresa).identity[0],
        reanudar=True,
    )
    await db_session.refresh(operacion)

    assert lote.estado == "completado"
    assert lote.procesamiento_async is True
    assert lote.modo_procesamiento == "background"
    assert llamadas == 1
    assert operacion.estado == "finalizado"
    assert operacion.response_json["en_progreso"] is False
    assert operacion.response_json["lote"]["estado"] == "completado"


@pytest.mark.asyncio
async def test_procesar_background_encolado_durable_no_reabre_operacion(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Una falla al publicar ownership revierte también el encolado."""
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: True,
    )

    async def fail_guardar_respuesta(self, **kwargs):
        raise SQLAlchemyTimeoutError()

    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "guardar_respuesta_operacion_cas",
        fail_guardar_respuesta,
    )
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-background-respuesta-db.xlsx",
    )
    confirmacion = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **confirmacion},
    )

    assert response.status_code == 503, response.text
    assert response.headers["Retry-After"] == "2"
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        lote = await observador.get(LoteComprobante, lote_id)
        assert lote is not None
        assert lote.estado == "validado"
        assert lote.procesamiento_async is False
        assert lote.metadata_json.get("operacion_idempotente_id") is None
        operacion = await observador.scalar(
            select(OperacionIdempotente).where(
                OperacionIdempotente.idempotency_key == "idem-lote-test"
            )
        )
        assert operacion is not None
        assert operacion.estado == "interrumpida_pre_arca"
        assert operacion.response_json is None
        intentos = await observador.scalars(
            select(IntentoEmisionFiscal).where(
                IntentoEmisionFiscal.operacion_id == operacion.id
            )
        )
        assert intentos.all() == []
        publicable_al_worker = await observador.scalar(
            select(LoteComprobante.id).where(
                LoteComprobante.id == lote_id,
                LoteComprobante.estado == "en_cola",
            )
        )
        assert publicable_al_worker is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "perdida_ownership",
    ["progreso_adulterado", "terminal", "cas_updated_at"],
)
async def test_publicacion_background_revierte_lote_si_pierde_ownership(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    perdida_ownership: str,
) -> None:
    """La publicación worker es atómica ante ownership adulterado o perdido."""
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: True,
    )
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo=f"lote-publicacion-{perdida_ownership}.xlsx",
    )
    idempotency_key = f"idem-publicacion-{perdida_ownership}"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=idempotency_key,
    )
    encolado = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **headers},
    )
    assert encolado.status_code == 200, encolado.text
    lote = await db_session.get(LoteComprobante, lote_id)
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == idempotency_key
        )
    )
    assert lote is not None
    assert operacion is not None
    operacion_id = int(operacion.id)

    if perdida_ownership == "progreso_adulterado":
        respuesta_adulterada = deepcopy(operacion.response_json)
        respuesta_adulterada["lote"]["metadata_json"]["pf19b_rece_material"][
            "grupos_hash"
        ] = ("f" * 64)
        operacion.response_json = respuesta_adulterada
        await db_session.commit()
    elif perdida_ownership == "terminal":
        respuesta_terminal = deepcopy(operacion.response_json)
        respuesta_terminal["en_progreso"] = False
        respuesta_terminal["lote"]["estado"] = "completado"
        operacion.estado = "finalizado"
        operacion.response_json = respuesta_terminal
        await db_session.commit()

    lote.estado = "completado"
    lote.finished_at = datetime.utcnow()
    if perdida_ownership == "cas_updated_at":
        execute_original = db_session.execute

        async def perder_cas_updated_at(statement, *args, **kwargs):
            """Simula rowcount cero tras perder el CAS de publicación."""
            if (
                getattr(statement, "is_update", False)
                and getattr(getattr(statement, "table", None), "name", None)
                == "operaciones_idempotentes"
            ):
                return SimpleNamespace(rowcount=0)
            return await execute_original(statement, *args, **kwargs)

        monkeypatch.setattr(db_session, "execute", perder_cas_updated_at)

    with pytest.raises(LoteComprobanteConflictoError):
        await LoteComprobantesService(
            db_session
        )._guardar_respuesta_operacion_background(lote, operacion_id)

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        lote_visible = await observador.get(LoteComprobante, lote_id)
        operacion_visible = await observador.get(OperacionIdempotente, operacion_id)
    assert lote_visible is not None
    assert operacion_visible is not None
    assert lote_visible.estado == "en_cola"
    if perdida_ownership == "terminal":
        assert operacion_visible.estado == "finalizado"
        assert operacion_visible.response_json["en_progreso"] is False
    else:
        assert operacion_visible.estado == "en_proceso"
        if perdida_ownership == "progreso_adulterado":
            assert (
                operacion_visible.response_json["lote"]["metadata_json"][
                    "pf19b_rece_material"
                ]["grupos_hash"]
                == "f" * 64
            )
        else:
            assert operacion_visible.response_json["en_progreso"] is True


@pytest.mark.asyncio
async def test_publicacion_background_confirma_reconciliacion_sin_reabrir(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """El worker reemplaza su progress solo por el terminal recon del mismo lote."""
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: True,
    )
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-publicacion-reconciliacion.xlsx",
    )
    idempotency_key = "idem-publicacion-reconciliacion"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=idempotency_key,
    )
    encolado = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **headers},
    )
    assert encolado.status_code == 200, encolado.text
    lote = await db_session.get(LoteComprobante, lote_id)
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == idempotency_key
        )
    )
    assert lote is not None
    assert operacion is not None
    operacion_id = int(operacion.id)
    assert operacion.estado == "en_proceso"
    assert operacion.response_json["en_progreso"] is True

    operacion.estado = "requiere_reconciliacion"
    lote.estado = "requiere_reconciliacion"
    lote.finished_at = datetime.utcnow()
    lote.mensaje_resumen = "El lote requiere reconciliación fiscal."
    await db_session.commit()
    await db_session.refresh(lote)
    await LoteComprobantesService(db_session)._guardar_respuesta_operacion_background(
        lote, operacion_id
    )
    await db_session.commit()

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        lote_visible = await observador.get(LoteComprobante, lote_id)
        operacion_visible = await observador.get(
            OperacionIdempotente,
            operacion_id,
        )
    assert lote_visible is not None
    assert lote_visible.estado == "requiere_reconciliacion"
    assert operacion_visible is not None
    assert operacion_visible.estado == "requiere_reconciliacion"
    assert operacion_visible.response_json["en_progreso"] is False
    assert (
        operacion_visible.response_json["lote"]["estado"] == "requiere_reconciliacion"
    )


@pytest.mark.asyncio
async def test_procesar_lote_background_sin_worker_no_encola(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Sin worker disponible no debe mutar el lote ni crear idempotencia."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "batch_worker_enabled", False)

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-worker-no-disponible.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 503, procesar.text
    detail = procesar.json()["detail"]
    assert detail["categoria_error"] == "worker_lotes_no_disponible"
    assert "No se encoló el lote" in detail["mensaje"]

    lote = await db_session.get(LoteComprobante, lote_id)
    await db_session.refresh(lote)
    assert lote.estado == "validado"
    assert lote.procesamiento_async is False
    operacion = (
        await db_session.execute(
            select(OperacionIdempotente).where(
                OperacionIdempotente.idempotency_key == "idem-lote-test"
            )
        )
    ).scalar_one_or_none()
    assert operacion is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("estado_operacion", "respuesta_es_error"),
    [
        pytest.param("finalizado", False, id="finalizado"),
        pytest.param("fallido", True, id="fallido-legacy"),
    ],
)
async def test_replay_terminal_background_no_depende_del_worker(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    estado_operacion: str,
    respuesta_es_error: bool,
) -> None:
    """Un resultado terminal legacy se reproduce antes del gate del worker."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-replay-terminal-worker-caido.xlsx",
    )
    idempotency_key = "idem-replay-terminal-worker-caido"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=idempotency_key,
    )
    service = LoteComprobantesService(db_session)
    material = await service.calcular_material_idempotente_grupos(
        lote_id=lote_id,
        empresa_id=test_empresa.id,
        estados={
            "validado",
            "procesando",
            "autorizado",
            "fallido",
            "requiere_reconciliacion",
        },
    )
    payload = {
        "lote_id": lote_id,
        "background": True,
        "confirmacion_fecha_fiscal": headers["X-Confirmacion-Fecha-Fiscal"],
        "grupo_ids": material["grupo_ids"],
        "grupos_hash": material["grupos_hash"],
    }
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    if respuesta_es_error:
        respuesta_terminal = {
            "mensaje": "Fallo terminal legacy ya confirmado.",
            "errores": ["El procesamiento ya terminó con un error conocido."],
            "categoria_error": "lote_fallido_legacy",
            "status_code": 409,
        }
    else:
        respuesta_terminal = {
            "lote": LoteComprobanteResponse.model_validate(lote).model_dump(
                mode="json"
            ),
            "mensaje": "Resultado terminal sintético ya confirmado.",
            "en_progreso": False,
        }
    operacion = OperacionIdempotente(
        empresa_id=test_empresa.id,
        idempotency_key=idempotency_key,
        tipo_operacion="procesar_lote",
        payload_hash=IdempotenciaFiscalService.calcular_payload_hash(payload),
        lote_id=lote_id,
        estado=estado_operacion,
        response_json=respuesta_terminal,
    )
    db_session.add(operacion)
    await db_session.commit()

    async def fail_resolver(*args, **kwargs):
        """El replay terminal no debe volver a resolver RECE ni crear operación."""
        raise AssertionError("No debe resolver una operación terminal nuevamente")

    async def fail_procesar(*args, **kwargs):
        """El replay terminal no debe entrar al servicio de emisión."""
        raise AssertionError("No debe procesar un lote con respuesta terminal")

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: False,
    )
    monkeypatch.setattr(
        "app.api.lotes_comprobantes._resolver_operacion_lote",
        fail_resolver,
    )
    monkeypatch.setattr(LoteComprobantesService, "procesar_lote", fail_procesar)

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **headers},
    )

    if respuesta_es_error:
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == respuesta_terminal
    else:
        assert response.status_code == 200, response.text
        assert response.json() == LoteProcesamientoResponse.model_validate(
            respuesta_terminal
        ).model_dump(mode="json")
    assert await db_session.scalar(select(func.count(IntentoEmisionFiscal.id))) == 0
    assert (
        await db_session.scalar(select(func.count(PuntoVentaGuardaEmisionRece.id))) == 0
    )
    await db_session.refresh(operacion)
    assert operacion.estado == estado_operacion
    assert operacion.response_json == respuesta_terminal


@pytest.mark.asyncio
async def test_procesar_lote_actualiza_contadores_parciales(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe persistir avance real entre grupos durante la emisión."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-progreso-parcial.xlsx",
                _build_lote_excel_multi_grupo(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    llamadas = 0
    avance_observado = None

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas, avance_observado
        llamadas += 1
        if llamadas == 2:
            result = await db_session.execute(
                select(LoteComprobante).where(LoteComprobante.id == lote_id)
            )
            lote = result.scalar_one()
            avance_observado = (
                lote.grupos_emitidos,
                lote.grupos_fallidos,
                lote.grupos_validos,
                lote.mensaje_resumen,
            )
        numero = 200 + llamadas
        cae = f"{CAE_TEST_NO_REAL_PREFIX}{llamadas}"
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=numero,
            fecha_emision=request.fecha_emision,
            cae=cae,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=numero,
            fecha=request.fecha_emision,
            cae=cae,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 200, procesar.text
    assert avance_observado == (
        1,
        0,
        1,
        "Procesando comprobante 1 de 2...",
    )
    data = procesar.json()
    assert data["lote"]["estado"] == "completado"
    assert data["lote"]["grupos_emitidos"] == 2


@pytest.mark.asyncio
async def test_procesar_lote_usa_sublotes_arca_segun_regxreq(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote elegible se divide en sublotes según RegXReq."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    llamadas_batch: list[int] = []
    numero = 0

    async def fake_regxreq(self, empresa_id):
        return 2

    async def fake_emitir_lote(
        self,
        requests,
        max_registros=None,
        contextos=None,
        fase_solicitud_arca=None,
        commit_rechazo_global=True,
    ):
        nonlocal numero
        assert fase_solicitud_arca.iniciada is False
        llamadas_batch.append(len(requests))
        respuestas = []
        for request in requests:
            numero += 1
            cae = f"{CAE_TEST_NO_REAL_PREFIX}{numero}"
            comprobante_id = await _persistir_comprobante_autorizado(
                db_session,
                test_empresa,
                test_punto_venta,
                tipo_comprobante=request.tipo_comprobante,
                numero=numero,
                fecha_emision=request.fecha_emision,
                cae=cae,
                cae_vencimiento=date(2026, 3, 31),
                total=Decimal("1210.00"),
            )
            respuestas.append(
                EmitirComprobanteResponse(
                    exito=True,
                    comprobante_id=comprobante_id,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=1,
                    numero=numero,
                    fecha=request.fecha_emision,
                    cae=cae,
                    cae_vencimiento=date(2026, 3, 31),
                    total=Decimal("1210.00"),
                    mensaje="Comprobante autorizado",
                    errores=[],
                )
            )
        return respuestas

    async def fail_emitir_unitario(self, request, **kwargs):
        raise AssertionError("No debe usar emisión unitaria en sublotes de tamaño 2")

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.obtener_registros_maximos_por_request",
        fake_regxreq,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobantes_lote",
        fake_emitir_lote,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fail_emitir_unitario,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-batch-regxreq.xlsx",
                _build_lote_excel_multi_grupo(test_empresa.cuit, total_grupos=4),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert llamadas_batch == [2, 2]
    assert data["lote"]["estado"] == "completado"
    assert data["lote"]["metadata_json"]["arca_batch"]["reg_x_req"] == 2
    assert data["lote"]["metadata_json"]["arca_batch"]["chunk_size"] == 2
    assert data["lote"]["metadata_json"]["arca_batch"]["modo"] == "batch"


@pytest.mark.asyncio
async def test_procesar_lote_10005_cierra_sublote_y_aborta_remanentes_sin_replay_arca(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Todos los enviados conservan 10005 y los demás quedan no enviados."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    llamadas_fecae = 0

    class FakeWSFEClient:
        """Expone capacidad dos y rechaza globalmente el primer sublote."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva sin abrir red."""

        async def fe_comp_tot_x_request(self):
            return 2

        async def fe_comp_ultimo_autorizado(self, punto, tipo):
            return 0

        async def fe_cae_solicitar_lote(self, arca_requests):
            nonlocal llamadas_fecae
            llamadas_fecae += 1
            primero = arca_requests[0]
            raise ArcaErrorGlobalEstructurado(
                cabecera=CabeceraRespuestaFecae(
                    cuit=int(test_empresa.cuit),
                    punto_venta=primero.punto_venta,
                    tipo_comprobante=primero.tipo_cbte,
                    cantidad=len(arca_requests),
                    resultado="R",
                ),
                errores=(MensajeArcaEstructurado(10005, "mensaje privado ARCA"),),
                eventos=(),
                detalles_presentes=False,
                senales_cae_presentes=False,
                request_cuit=int(test_empresa.cuit),
                request_punto_venta=primero.punto_venta,
                request_tipo_comprobante=primero.tipo_cbte,
                request_cantidad=len(arca_requests),
                request_rangos=tuple(
                    (request.cbte_desde, request.cbte_hasta)
                    for request in arca_requests
                ),
            )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, numero):
        return None

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

    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-pf19c-10005.xlsx",
        total_grupos=4,
    )
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="idem-lote-pf19c-10005",
    )
    primera = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )
    assert primera.status_code == 200, primera.text
    assert llamadas_fecae == 1
    errores_arca_esperados = [
        {
            "codigo": 10005,
            "alcance": "global",
            "mensaje": "El punto de venta no está dado de alta como RECE en ARCA.",
        }
    ]
    assert primera.json()["errores_arca"] == errores_arca_esperados
    assert (
        primera.json()["lote"]["metadata_json"]["pf19c_rechazo_global"]["errores_arca"]
        == errores_arca_esperados
    )

    db_session.expire_all()
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        ).all()
    )
    intentos = list(
        (
            await db_session.scalars(
                select(IntentoEmisionFiscal)
                .where(IntentoEmisionFiscal.lote_id == lote_id)
                .order_by(IntentoEmisionFiscal.id)
            )
        ).all()
    )
    assert len(intentos) == 2
    assert {intento.grupo_id for intento in intentos} == {
        grupos[0].id,
        grupos[1].id,
    }
    assert {intento.estado for intento in intentos} == {"rechazado_arca"}
    assert all(
        intento.errores_arca_json == errores_arca_esperados for intento in intentos
    )
    assert all(grupo.estado == "fallido" for grupo in grupos), [
        grupo.estado for grupo in grupos
    ]
    assert all(
        any(
            "no_enviado_por_rechazo_global" in mensaje
            for mensaje in grupos[indice].mensajes_json
        )
        for indice in (2, 3)
    )
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-lote-pf19c-10005"
        )
    )
    assert operacion is not None
    assert operacion.estado == "rechazado_arca"
    assert (
        primera.json()["lote"]["metadata_json"]["pf19c_rechazo_global"]["operacion_id"]
        == operacion.id
    )
    assert operacion.response_json == primera.json()

    segunda = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )
    assert segunda.status_code == 200, segunda.text
    assert segunda.json() == primera.json()
    assert llamadas_fecae == 1

    respuesta_original = deepcopy(operacion.response_json)
    respuesta_adulterada = deepcopy(respuesta_original)
    respuesta_adulterada["errores_arca"][0]["codigo"] = 10006
    operacion.response_json = respuesta_adulterada
    await db_session.commit()
    desconocida = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )
    assert desconocida.status_code == 409, desconocida.text
    assert llamadas_fecae == 1

    respuesta_sin_evidencia = deepcopy(respuesta_original)
    respuesta_sin_evidencia["errores_arca"] = []
    respuesta_sin_evidencia["lote"]["metadata_json"].pop("pf19c_rechazo_global")
    operacion.response_json = respuesta_sin_evidencia
    await db_session.commit()
    reatestiguada = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )
    assert reatestiguada.status_code == 409, reatestiguada.text
    assert llamadas_fecae == 1


@pytest.mark.asyncio
async def test_reintento_exitoso_no_publica_10005_historico_y_replay_a_es_exacto(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """El retry B revalida RECE sin heredar el rechazo durable de A."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", False)

    class FakeWSFEClient:
        """Rechaza A con 10005 y autoriza B sin abrir red."""

        solicitudes_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva."""

        async def fe_comp_ultimo_autorizado(self, punto, tipo):
            """Mantiene disponible el mismo número tras el rechazo."""
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Expone el rechazo inicial y la autorización posterior."""
            FakeWSFEClient.solicitudes_fecae += 1
            if FakeWSFEClient.solicitudes_fecae == 1:
                raise ArcaErrorGlobalEstructurado(
                    cabecera=CabeceraRespuestaFecae(
                        cuit=int(test_empresa.cuit),
                        punto_venta=arca_request.punto_venta,
                        tipo_comprobante=arca_request.tipo_cbte,
                        cantidad=1,
                        resultado="R",
                    ),
                    errores=(MensajeArcaEstructurado(10005, "mensaje privado ARCA"),),
                    eventos=(),
                    detalles_presentes=False,
                    senales_cae_presentes=False,
                    request_cuit=int(test_empresa.cuit),
                    request_punto_venta=arca_request.punto_venta,
                    request_tipo_comprobante=arca_request.tipo_cbte,
                    request_cantidad=1,
                    request_rangos=(
                        (arca_request.cbte_desde, arca_request.cbte_hasta),
                    ),
                )
            return CAEResponse(
                cae=CAE_TEST_NO_REAL_ALT,
                cae_vencimiento="20260831",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, numero):
        return None

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

    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-pf19c-owner-historico.xlsx",
    )
    headers_a = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="idem-pf19c-owner-a",
    )
    respuesta_a = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_a},
    )
    assert respuesta_a.status_code == 200, respuesta_a.text
    assert respuesta_a.json()["errores_arca"][0]["codigo"] == 10005

    db_session.expire_all()
    [grupo] = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id
                )
            )
        ).all()
    )
    operacion_a = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-pf19c-owner-a"
        )
    )
    assert operacion_a is not None
    assert operacion_a.estado == "rechazado_arca"
    assert grupo.estado == "fallido", grupo.estado
    operacion_a_id = int(operacion_a.id)
    assert (
        respuesta_a.json()["lote"]["metadata_json"]["pf19c_rechazo_global"][
            "operacion_id"
        ]
        == operacion_a_id
    )

    headers_b = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[int(grupo.id)],
        idempotency_key="idem-pf19c-owner-b",
    )
    respuesta_b = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_b},
        json={"grupo_ids": [int(grupo.id)]},
    )
    assert respuesta_b.status_code == 200, respuesta_b.text
    assert respuesta_b.json()["errores_arca"] == []
    assert respuesta_b.json()["lote"]["estado"] == "completado"
    assert (
        respuesta_b.json()["lote"]["metadata_json"]["pf19c_rechazo_global"][
            "operacion_id"
        ]
        == operacion_a_id
    )

    operacion_b = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-pf19c-owner-b"
        )
    )
    assert operacion_b is not None
    assert operacion_b.estado == "finalizado"
    assert operacion_b.response_json == respuesta_b.json()
    intentos = list(
        (
            await db_session.scalars(
                select(IntentoEmisionFiscal)
                .where(IntentoEmisionFiscal.lote_id == lote_id)
                .order_by(IntentoEmisionFiscal.id)
            )
        ).all()
    )
    assert [(intento.operacion_id, intento.estado) for intento in intentos] == [
        (operacion_a_id, "rechazado_arca"),
        (int(operacion_b.id), "autorizado"),
    ]
    assert FakeWSFEClient.solicitudes_fecae == 2

    replay_a = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_a},
    )
    assert replay_a.status_code == 200, replay_a.text
    assert replay_a.json() == respuesta_a.json()
    assert FakeWSFEClient.solicitudes_fecae == 2

    operacion_a_sin_respuesta = await db_session.get(
        OperacionIdempotente,
        operacion_a_id,
        populate_existing=True,
    )
    assert operacion_a_sin_respuesta is not None
    operacion_a_sin_respuesta.response_json = None
    await db_session.commit()
    reconstruccion_cruzada = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_a},
    )
    assert reconstruccion_cruzada.status_code == 409, reconstruccion_cruzada.text
    assert FakeWSFEClient.solicitudes_fecae == 2


@pytest.mark.parametrize(
    "error_raw",
    [
        {
            "codigo": 10006,
            "alcance": "global",
            "mensaje": "ARCA informó un error global para el requerimiento.",
        },
        {
            "codigo": "10005",
            "alcance": "global",
            "mensaje": "El punto de venta no está dado de alta como RECE en ARCA.",
        },
        {
            "codigo": 10005,
            "alcance": "global",
            "mensaje": "mensaje privado ARCA",
        },
    ],
    ids=["desconocido", "coaccionable", "mensaje-no-canonico"],
)
def test_metadata_lote_desconocida_no_publica_rechazo_global_10005(
    error_raw: dict,
) -> None:
    """Metadata no canónica nunca se reatestigua como evidencia terminal 10005."""
    metadata = {
        "pf19c_rechazo_global": {
            "operacion_id": 17,
            "categoria": "arca_rechazo_global_excluyente",
            "grupos_rechazo_ids": [1],
            "grupos_no_enviados_ids": [2],
            "errores_arca": [error_raw],
        }
    }

    assert (
        LoteComprobantesService.errores_arca_publicables_desde_metadata(
            metadata,
            operacion_id=17,
        )
        == []
    )


@pytest.mark.parametrize(
    ("owner_marker", "owner_actual"),
    [
        pytest.param(17, 18, id="operacion-distinta"),
        pytest.param(True, 1, id="marker-bool"),
        pytest.param(17, True, id="owner-actual-bool"),
        pytest.param("17", 17, id="marker-string"),
    ],
)
def test_metadata_lote_10005_exige_owner_entero_exacto(
    owner_marker: object,
    owner_actual: object,
) -> None:
    """Un marker canónico no prueba el rechazo de otra operación."""
    metadata = {
        "pf19c_rechazo_global": {
            "operacion_id": owner_marker,
            "categoria": "arca_rechazo_global_excluyente",
            "grupos_rechazo_ids": [1],
            "grupos_no_enviados_ids": [],
            "errores_arca": [
                {
                    "codigo": 10005,
                    "alcance": "global",
                    "mensaje": (
                        "El punto de venta no está dado de alta como RECE en ARCA."
                    ),
                }
            ],
        }
    }

    assert (
        LoteComprobantesService.errores_arca_publicables_desde_metadata(
            metadata,
            operacion_id=owner_actual,
        )
        == []
    )


@pytest.mark.parametrize("estado", ["finalizado", "fallido", "fallido_verificado"])
def test_replay_lote_sin_10005_conserva_terminal_historico(estado: str) -> None:
    """Terminales históricos sin evidencia global siguen siendo publicables."""
    respuesta = SimpleNamespace(
        lote=SimpleNamespace(
            id=9,
            empresa_id=1,
            estado="fallido",
            metadata_json={},
        ),
        errores_arca=[],
    )

    assert LoteComprobantesService.respuesta_lote_coincide_operacion(
        respuesta,
        estado_operacion=estado,
        operacion_id=17,
        lote_id=9,
        empresa_id=1,
    )


def test_ownership_worker_acepta_legacy_o_errores_vacios_pero_no_evidencia() -> None:
    """El progress worker admite el default nuevo sin aceptar un 10005 terminal."""
    grupo = {
        "grupo_id": 1,
        "empresa_id": 1,
        "punto_venta_id": 1,
        "punto_venta_numero": 41,
        "ambiente": "produccion",
        "elegibilidad_revision_id": 1,
        "punto_venta_revision_fiscal": 1,
        "tipo_comprobante": 6,
        "payload_hash": "a" * 64,
    }
    material = {
        "grupo_ids": [1],
        "grupos_hash": hashlib.sha256(
            json.dumps([grupo], sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "grupos": [grupo],
    }
    respuesta_legacy = {
        "lote": {
            "id": 9,
            "empresa_id": 1,
            "estado": "en_cola",
            "modo_procesamiento": "background",
            "procesamiento_async": True,
            "metadata_json": {
                "operacion_idempotente_id": 7,
                "pf19b_rece_material": material,
            },
        },
        "mensaje": "El lote quedó en cola.",
        "en_progreso": True,
    }
    respuesta_nueva = {**respuesta_legacy, "errores_arca": []}
    respuesta_adulterada = {
        **respuesta_legacy,
        "errores_arca": [
            {
                "codigo": 10005,
                "alcance": "global",
                "mensaje": (
                    "El punto de venta no está dado de alta como RECE en ARCA."
                ),
            }
        ],
    }

    for respuesta in (respuesta_legacy, respuesta_nueva):
        assert IdempotenciaFiscalService.respuesta_worker_en_progreso_valida(
            respuesta,
            lote_id=9,
            empresa_id=1,
            operacion_id=7,
            material_rece=material,
        )
    assert not IdempotenciaFiscalService.respuesta_worker_en_progreso_valida(
        respuesta_adulterada,
        lote_id=9,
        empresa_id=1,
        operacion_id=7,
        material_rece=material,
    )


@pytest.mark.asyncio
async def test_procesar_lote_error_inesperado_post_arca_inmoviliza_todo_y_detiene(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Un fallo post-FECAE no publica datos crudos ni inicia otro sublote."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    llamadas_batch = 0

    async def fake_regxreq(self, empresa_id):
        return 2

    async def fake_emitir_lote(
        self,
        requests,
        max_registros=None,
        contextos=None,
        fase_solicitud_arca=None,
        commit_rechazo_global=True,
    ):
        nonlocal llamadas_batch
        llamadas_batch += 1
        fase_solicitud_arca.marcar_iniciada()
        raise RuntimeError("detalle privado post ARCA")

    async def fail_emitir_unitario(self, request, **kwargs):
        raise AssertionError("No debe degradar a unitario")

    monkeypatch.setattr(
        FacturacionService,
        "obtener_registros_maximos_por_request",
        fake_regxreq,
    )
    monkeypatch.setattr(
        FacturacionService,
        "emitir_comprobantes_lote",
        fake_emitir_lote,
    )
    monkeypatch.setattr(
        FacturacionService,
        "emitir_comprobante",
        fail_emitir_unitario,
    )
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-pf19c-incierto.xlsx",
        total_grupos=4,
    )
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="idem-lote-pf19c-incierto",
    )
    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )
    assert response.status_code == 200, response.text
    assert llamadas_batch == 1
    assert "detalle privado" not in response.text
    db_session.expire_all()
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id
                )
            )
        ).all()
    )
    assert len(grupos) == 4
    assert {grupo.estado for grupo in grupos} == {"requiere_reconciliacion"}
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-lote-pf19c-incierto"
        )
    )
    assert operacion is not None
    assert operacion.estado == "requiere_reconciliacion"


@pytest.mark.asyncio
async def test_procesar_lote_fallback_regxreq_degrada_a_unitario_con_aviso(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Si RegXReq no está disponible, el lote usa modo unitario y avisa."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)

    async def fake_regxreq(self, empresa_id):
        raise RuntimeError("RegXReq no disponible")

    async def fake_emitir(self, request, **kwargs):
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=456,
            fecha_emision=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=456,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.obtener_registros_maximos_por_request",
        fake_regxreq,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-fallback-regxreq.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    arca_batch = data["lote"]["metadata_json"]["arca_batch"]
    assert arca_batch["modo"] == "unitario_fallback"
    assert arca_batch["fallback_unitario"] is True
    assert "RegXReq no disponible" in arca_batch["fallback_motivo"]
    assert "modo unitario" in data["lote"]["mensaje_resumen"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyTimeoutError, OperationalError],
    ids=["timeout", "operational"],
)
async def test_procesar_lote_db_temporal_pre_arca_devuelve_503_sin_fallar_grupo(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    error_type: type[Exception],
) -> None:
    """Un lote pre-ARCA queda intacto y la API delega el 503 sanitizado."""
    test_certificado.ambiente = settings.arca_env

    async def fail_emitir(self, request, **kwargs):
        raise _crear_error_db_temporal(error_type)

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fail_emitir,
    )

    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-db-temporal-pre-arca.xlsx",
    )
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )
    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert response.status_code == 503, response.text
    assert response.headers["Retry-After"] == "2"
    assert "UPDATE lotes_comprobantes" not in response.text
    assert "base temporalmente no disponible" not in response.text
    grupo = await db_session.scalar(
        select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == lote_id)
    )
    assert grupo is not None
    assert grupo.estado == "validado"
    assert not any(
        "UPDATE lotes_comprobantes" in mensaje
        for mensaje in (grupo.mensajes_json or [])
    )
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    assert lote.estado == "validado"
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-lote-test"
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
async def test_procesar_lote_post_arca_db_temporal_devuelve_409_sanitizado(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Una caída DB con FECAE iniciado nunca se presenta como reintentable."""
    test_certificado.ambiente = settings.arca_env

    async def fail_post_arca(self, lote_id, empresa_id, **kwargs):
        kwargs["fase_solicitud_arca"].marcar_iniciada()
        raise _crear_error_db_temporal(OperationalError)

    monkeypatch.setattr(
        LoteComprobantesService,
        "procesar_lote",
        fail_post_arca,
    )
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-db-temporal-post-arca.xlsx",
    )
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert response.status_code == 409
    assert "Retry-After" not in response.headers
    detail = response.json()["detail"]
    assert detail["requiere_reconciliacion"] is True
    assert "UPDATE lotes_comprobantes" not in response.text
    assert "base temporalmente no disponible" not in response.text


@pytest.mark.asyncio
async def test_procesar_lote_post_arca_requiere_reconciliacion(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un fallo post-ARCA en lote no debe quedar como reintentable."""
    test_certificado.ambiente = settings.arca_env
    empresa_id = inspect(test_empresa).identity[0]

    async def fake_emitir(self, request, **kwargs):
        operacion_id = int(kwargs["operacion_id"])
        transicion = await self.db.execute(
            update(OperacionIdempotente)
            .where(
                OperacionIdempotente.id == operacion_id,
                OperacionIdempotente.estado == "en_proceso",
                OperacionIdempotente.response_json.is_(None),
            )
            .values(estado="requiere_reconciliacion")
        )
        assert transicion.rowcount == 1
        await self.db.flush()
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=654,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL_ALT,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="ARCA autorizó el comprobante, pero FactuFlow no pudo guardarlo",
            errores=["No reintentes esta emisión"],
            requiere_reconciliacion=True,
            categoria_error="post_arca_persistencia",
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-reconciliacion.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["lote"]["estado"] == "requiere_reconciliacion"
    assert data["lote"]["grupos_emitidos"] == 0
    assert data["lote"]["grupos_fallidos"] == 0

    detalle = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/resultados",
        headers=auth_headers,
    )
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == "requiere_reconciliacion"
    assert grupo["cae"] == CAE_TEST_NO_REAL_ALT
    assert grupo["numero_asignado"] == 654

    service = LoteComprobantesService(db_session)
    lote = await service.obtener_lote(lote_id, empresa_id)
    assert service._lote_permite_reintento(lote) is False
    operacion = (
        await db_session.execute(
            select(OperacionIdempotente).where(
                OperacionIdempotente.lote_id == lote_id,
                OperacionIdempotente.tipo_operacion == "procesar_lote",
            )
        )
    ).scalar_one()
    assert operacion.estado == "requiere_reconciliacion"
    assert operacion.response_json is not None


@pytest.mark.asyncio
async def test_descartar_grupos_cierra_lote_con_descartes(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Descartar pendientes no emitidos debe cerrar un lote parcial."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-descartar-pendientes.xlsx",
        total_grupos=2,
    )
    grupos = await _marcar_grupos_lote(
        db_session,
        lote_id,
        ["autorizado", "fallido"],
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/descartar-grupos",
        headers=auth_headers,
        json={
            "grupo_ids": [grupos[1].id],
            "motivo": "Emitido manualmente en otro flujo operativo",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["lote"]
    assert data["estado"] == "cerrado_con_descartes"
    assert data["grupos_emitidos"] == 1
    assert data["grupos_descartados"] == 1

    grupo_descartado = await db_session.get(LoteComprobanteGrupo, grupos[1].id)
    assert grupo_descartado.estado == "descartado"


@pytest.mark.asyncio
async def test_reintentar_fallidos_exige_confirmacion_fecha_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El reintento de fallidos también debe confirmar fecha fiscal exacta."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-sin-confirmacion.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["fallido"])

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={
            **auth_headers,
            "X-Idempotency-Key": "idem-reintento-sin-confirmacion",
        },
        json={"grupo_ids": []},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "confirmar la fecha fiscal exacta" in detail["mensaje"]
    assert "0001" in detail["mensaje"]


@pytest.mark.asyncio
async def test_reintentar_fallidos_reclama_grupo_antes_de_emitir(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El reintento debe sacar el grupo de fallido antes de pedir CAE."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-claim.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]
    estados_vistos: list[str] = []

    async def fake_emitir_locked(self, request, commit=True, **kwargs):
        estado = await db_session.scalar(
            select(LoteComprobanteGrupo.estado).where(
                LoteComprobanteGrupo.id == grupo.id
            )
        )
        estados_vistos.append(str(estado))
        assert commit is False
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=grupo.punto_venta_numero,
            numero=0,
            fecha=request.fecha_emision,
            total=Decimal("1210.00"),
            mensaje="Error controlado",
            errores=["Error controlado"],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService._emitir_comprobante_locked",
        fake_emitir_locked,
    )
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo.id],
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": [grupo.id]},
    )

    assert response.status_code == 200, response.text
    assert estados_vistos == ["reintentando"]
    await db_session.refresh(grupo)
    assert grupo.estado == "fallido"


@pytest.mark.asyncio
@pytest.mark.parametrize("adulteracion", ["owner", "material"])
async def test_reintentar_fallidos_revalida_ownership_post_claim_sin_arca(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    adulteracion: str,
) -> None:
    """Una mutación post-claim bloquea todo I/O fiscal y no habilita recovery ajeno."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo=f"lote-reintento-post-claim-{adulteracion}.xlsx",
    )
    [grupo] = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo_id = int(grupo.id)
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
        idempotency_key=f"idem-reintento-post-claim-{adulteracion}",
    )
    original_claim = LoteComprobantesService._reclamar_grupo_para_reintento
    operacion_perdedora_id: int | None = None
    owner_adulterado_id: int | None = None

    async def claim_con_adulteracion(self, **kwargs):
        nonlocal operacion_perdedora_id, owner_adulterado_id
        resultado = await original_claim(self, **kwargs)
        if kwargs.get("solo_revalidar") is True or resultado[0] is None:
            return resultado
        operacion_perdedora_id = int(kwargs["operacion_id"])
        lote = await self.db.get(LoteComprobante, lote_id)
        operacion = await self.db.get(
            OperacionIdempotente,
            operacion_perdedora_id,
        )
        assert lote is not None
        assert operacion is not None
        metadata = deepcopy(lote.metadata_json or {})
        if adulteracion == "owner":
            owner_adulterado = OperacionIdempotente(
                empresa_id=operacion.empresa_id,
                usuario_id=operacion.usuario_id,
                idempotency_key="idem-reintento-owner-concurrente",
                tipo_operacion="reintentar_fallidos_lote",
                payload_hash="f" * 64,
                estado="en_proceso",
                lote_id=lote_id,
                rece_snapshot_hash=operacion.rece_snapshot_hash,
            )
            self.db.add(owner_adulterado)
            await self.db.flush()
            owner_adulterado_id = int(owner_adulterado.id)
            metadata["operacion_idempotente_id"] = owner_adulterado_id
        else:
            material = deepcopy(metadata["pf19b_rece_material"])
            material["grupos_hash"] = "0" * 64
            metadata["pf19b_rece_material"] = material
        lote.metadata_json = metadata
        await self.db.commit()
        return resultado

    llamadas = {"ticket": 0, "fecomp": 0, "fecae": 0}

    async def fail_ticket(*args, **kwargs):
        llamadas["ticket"] += 1
        raise AssertionError("No debe solicitar ticket con ownership adulterado")

    async def fail_fecomp(*args, **kwargs):
        llamadas["fecomp"] += 1
        raise AssertionError("No debe consultar numeración con ownership adulterado")

    async def fail_fecae(*args, **kwargs):
        llamadas["fecae"] += 1
        raise AssertionError("No debe solicitar CAE con ownership adulterado")

    monkeypatch.setattr(
        LoteComprobantesService,
        "_reclamar_grupo_para_reintento",
        claim_con_adulteracion,
    )
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_ticket_acceso",
        fail_ticket,
    )
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_diagnostico_numeracion",
        fail_fecomp,
    )
    monkeypatch.setattr(
        "app.arca.wsfev1.WSFEv1Client.fe_cae_solicitar",
        fail_fecae,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": [grupo_id]},
    )

    assert response.status_code == 409, response.text
    assert llamadas == {"ticket": 0, "fecomp": 0, "fecae": 0}
    assert operacion_perdedora_id is not None
    db_session.expire_all()
    grupo_durable = await db_session.get(LoteComprobanteGrupo, grupo_id)
    lote_durable = await db_session.get(LoteComprobante, lote_id)
    assert grupo_durable is not None
    assert lote_durable is not None
    assert grupo_durable.estado == "reintentando"
    if adulteracion == "owner":
        assert owner_adulterado_id is not None
        assert (
            lote_durable.metadata_json["operacion_idempotente_id"]
            == owner_adulterado_id
        )

    recovery = await LoteComprobantesService(
        db_session
    ).recuperar_reintento_interrumpido_pre_arca(
        lote_id=lote_id,
        grupo_id=grupo_id,
        operacion_id=operacion_perdedora_id,
        mensajes_previos=["Fallo previo sintético."],
    )

    assert recovery == "no_recuperable"
    db_session.expire_all()
    assert (await db_session.get(LoteComprobanteGrupo, grupo_id)).estado == (
        "reintentando"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "estado_intento_previo", ["en_proceso", "requiere_reconciliacion"]
)
async def test_reintentar_fallidos_no_transfiere_owner_con_intento_previo_activo(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    estado_intento_previo: str,
) -> None:
    """Un owner terminal con intento activo o incierto no puede transferirse."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo=f"lote-owner-previo-{estado_intento_previo}.xlsx",
    )
    [grupo] = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo_id = int(grupo.id)
    original_emitir = FacturacionService._emitir_comprobante_locked

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=grupo.punto_venta_numero,
            numero=0,
            fecha=request.fecha_emision,
            total=Decimal("1210.00"),
            mensaje="Fallo verificado sintético.",
            errores=["Fallo verificado sintético."],
        )

    monkeypatch.setattr(
        FacturacionService,
        "_emitir_comprobante_locked",
        fake_emitir,
    )
    headers_previos = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
        idempotency_key=f"idem-owner-previo-{estado_intento_previo}",
    )
    primera = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_previos},
        json={"grupo_ids": [grupo_id]},
    )
    assert primera.status_code == 200, primera.text

    operacion_previa = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key
            == f"idem-owner-previo-{estado_intento_previo}"
        )
    )
    grupo_previo = await db_session.get(LoteComprobanteGrupo, grupo_id)
    assert operacion_previa is not None
    assert grupo_previo is not None
    assert grupo_previo.estado == "fallido"
    owner_previo_id = int(operacion_previa.id)
    owner_previo_usuario_id = operacion_previa.usuario_id
    request = EmitirComprobanteRequest.model_validate(grupo_previo.payload_json or {})
    contexto = ContextoElegibilidadRece(
        empresa_id=int(grupo_previo.empresa_id),
        punto_venta_id=int(grupo_previo.punto_venta_id),
        punto_venta_numero=int(grupo_previo.punto_venta_numero),
        ambiente=str(grupo_previo.ambiente),
        elegibilidad_revision_id=int(grupo_previo.punto_venta_elegibilidad_revision_id),
        punto_venta_revision_fiscal=int(grupo_previo.punto_venta_revision_fiscal),
    )
    guarda_cerrada = PuntoVentaGuardaEmisionRece(
        token=("a" if estado_intento_previo == "en_proceso" else "b") * 64,
        fase="cerrada_pre_arca",
        operacion_id=owner_previo_id,
        empresa_id=grupo_previo.empresa_id,
        punto_venta_id=grupo_previo.punto_venta_id,
        ambiente=grupo_previo.ambiente,
        elegibilidad_revision_id=grupo_previo.punto_venta_elegibilidad_revision_id,
        punto_venta_revision_fiscal=grupo_previo.punto_venta_revision_fiscal,
        cerrada_en=datetime.utcnow(),
    )
    db_session.add(guarda_cerrada)
    await db_session.flush()
    await db_session.refresh(test_punto_venta)
    intento_previo = await IdempotenciaFiscalService(db_session).crear_intento_emision(
        request=request,
        punto_venta=test_punto_venta,
        numero_planificado=1,
        total=FacturacionService(db_session)._calcular_totales(request.items)["total"],
        operacion_id=owner_previo_id,
        usuario_id=owner_previo_usuario_id,
        lote_id=lote_id,
        grupo_id=grupo_id,
        duplicados_generacion_id=operacion_previa.duplicados_generacion_id,
        contexto_rece=contexto,
        guarda_rece_id=int(guarda_cerrada.id),
        commit=False,
    )
    intento_previo.estado = estado_intento_previo
    await db_session.commit()

    monkeypatch.setattr(
        FacturacionService,
        "_emitir_comprobante_locked",
        original_emitir,
    )
    llamadas = {"ticket": 0, "fecomp": 0, "fecae": 0}

    async def fail_ticket(*args, **kwargs):
        llamadas["ticket"] += 1
        raise AssertionError("No debe solicitar ticket con intento previo bloqueante")

    async def fail_fecomp(*args, **kwargs):
        llamadas["fecomp"] += 1
        raise AssertionError(
            "No debe consultar numeración con intento previo bloqueante"
        )

    async def fail_fecae(*args, **kwargs):
        llamadas["fecae"] += 1
        raise AssertionError("No debe solicitar CAE con intento previo bloqueante")

    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fail_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_diagnostico_numeracion",
        fail_fecomp,
    )
    monkeypatch.setattr(
        "app.arca.wsfev1.WSFEv1Client.fe_cae_solicitar",
        fail_fecae,
    )
    headers_nuevos = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
        idempotency_key=f"idem-owner-nuevo-{estado_intento_previo}",
    )

    segunda = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_nuevos},
        json={"grupo_ids": [grupo_id]},
    )

    assert segunda.status_code == 409, segunda.text
    assert llamadas == {"ticket": 0, "fecomp": 0, "fecae": 0}
    db_session.expire_all()
    lote_durable = await db_session.get(LoteComprobante, lote_id)
    grupo_durable = await db_session.get(LoteComprobanteGrupo, grupo_id)
    assert lote_durable is not None
    assert grupo_durable is not None
    assert lote_durable.metadata_json["operacion_idempotente_id"] == owner_previo_id
    assert grupo_durable.estado == "fallido"


@pytest.mark.asyncio
async def test_reintentar_fallidos_segunda_key_pierde_cas_y_conserva_owner_previo(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """La segunda key que pierde el CAS no publica metadata ni devuelve 200 vacío."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-dos-keys-cas.xlsx",
    )
    [grupo] = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo_id = int(grupo.id)

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=grupo.punto_venta_numero,
            numero=0,
            fecha=request.fecha_emision,
            total=Decimal("1210.00"),
            mensaje="Fallo verificado sintético.",
            errores=["Fallo verificado sintético."],
        )

    monkeypatch.setattr(
        FacturacionService,
        "_emitir_comprobante_locked",
        fake_emitir,
    )
    headers_owner = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
        idempotency_key="idem-dos-keys-owner",
    )
    primera = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_owner},
        json={"grupo_ids": [grupo_id]},
    )
    assert primera.status_code == 200, primera.text
    operacion_owner = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-dos-keys-owner"
        )
    )
    assert operacion_owner is not None
    owner_id = int(operacion_owner.id)

    headers_perdedora = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
        idempotency_key="idem-dos-keys-perdedora",
    )
    original_execute = db_session.execute
    cas_interceptado = False

    async def execute_con_cas_perdido(statement, *args, **kwargs):
        nonlocal cas_interceptado
        tabla = getattr(statement, "table", None)
        if (
            not cas_interceptado
            and getattr(statement, "is_update", False)
            and getattr(tabla, "name", None) == "lotes_comprobantes_grupos"
        ):
            cas_interceptado = True
            return SimpleNamespace(rowcount=0)
        return await original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", execute_con_cas_perdido)

    segunda = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_perdedora},
        json={"grupo_ids": [grupo_id]},
    )

    assert segunda.status_code == 409, segunda.text
    assert cas_interceptado is True
    db_session.expire_all()
    lote_durable = await db_session.get(LoteComprobante, lote_id)
    grupo_durable = await db_session.get(LoteComprobanteGrupo, grupo_id)
    assert lote_durable is not None
    assert grupo_durable is not None
    assert lote_durable.metadata_json["operacion_idempotente_id"] == owner_id
    assert grupo_durable.estado == "fallido"


@pytest.mark.asyncio
@pytest.mark.parametrize("anidado", [False, True])
async def test_reintentar_fallidos_bloquea_payload_con_clave_desconocida(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    anidado,
) -> None:
    """Un reintento no debe emitir si el snapshot fiscal no es canónico."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-payload-no-canonico.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]
    payload = deepcopy(grupo.payload_json or {})
    destino = payload["items"][0] if anidado else payload
    destino["cotizaccion"] = "2"
    grupo.payload_json = payload
    await db_session.commit()
    llamadas_emision = 0

    async def fail_emitir_locked(self, request, commit=True, **kwargs):
        nonlocal llamadas_emision
        llamadas_emision += 1
        raise AssertionError("No debe emitir un payload fiscal no canónico")

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService._emitir_comprobante_locked",
        fail_emitir_locked,
    )
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo.id],
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": [grupo.id]},
    )

    assert response.status_code == 200, response.text
    assert llamadas_emision == 0
    await db_session.refresh(grupo)
    assert grupo.estado == "fallido"
    assert grupo.mensajes_json == [
        "No se pudo completar el reintento antes de solicitar CAE. "
        "El detalle técnico quedó registrado en logs privados."
    ]
    assert "cotizaccion" not in str(grupo.mensajes_json)
    assert grupo.numero_asignado is None
    assert grupo.cae is None
    assert grupo.comprobante_id is None


@pytest.mark.asyncio
async def test_reintentar_fallidos_usa_historia_externa_y_replay_no_reemite(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """El reintento usa el siguiente ARCA y el replay no vuelve a solicitar CAE."""

    class FakeWSFEClient:
        """Simula historia externa estable y una autorización verificable."""

        consultas_numeracion = 0
        numeros_solicitados: list[int] = []

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Informa un comprobante externo posterior a la historia local."""
            FakeWSFEClient.consultas_numeracion += 1
            return 77

        async def fe_cae_solicitar(self, arca_request):
            """Autoriza únicamente el número confirmado por ambos preflights."""
            FakeWSFEClient.numeros_solicitados.append(arca_request.cbte_desde)
            return CAEResponse(
                cae=CAE_TEST_NO_REAL_ALT,
                cae_vencimiento="20260831",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo="lote-reintento-historia-externa.xlsx",
        total_grupos=2,
        ultimo_local=76,
    )
    grupo_id = grupos[0].id
    otro_grupo_id = grupos[1].id
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
        idempotency_key="idem-reintento-historia-externa",
    )
    headers = {**auth_headers, **headers_reintento}
    body = {"grupo_ids": [grupo_id]}

    primera = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers=headers,
        json=body,
    )
    segunda = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers=headers,
        json=body,
    )
    conflicto = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers=headers,
        json={"grupo_ids": [otro_grupo_id]},
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert conflicto.status_code == 409, conflicto.text
    assert segunda.json() == primera.json()
    assert FakeWSFEClient.consultas_numeracion == 2
    assert FakeWSFEClient.numeros_solicitados == [78]
    db_session.expire_all()
    grupo = await db_session.get(LoteComprobanteGrupo, grupo_id)
    assert grupo is not None
    assert grupo.estado == "autorizado"
    assert grupo.numero_asignado == 78
    assert grupo.cae == CAE_TEST_NO_REAL_ALT
    assert grupo.comprobante_id is not None
    intentos = (
        (
            await db_session.execute(
                select(IntentoEmisionFiscal).where(
                    IntentoEmisionFiscal.grupo_id == grupo.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(intentos) == 1
    assert intentos[0].estado == "autorizado"
    assert intentos[0].numero_planificado == 78
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-reintento-historia-externa"
        )
    )
    assert operacion is not None
    assert operacion.estado == "finalizado"


@pytest.mark.asyncio
async def test_reintentar_10005_reconstruye_publicacion_tras_crash_sin_reemitir(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Un crash tras cerrar 10005 publica desde lote fallido sin otra FECAE."""

    class FakeWSFEClient:
        """Rechaza exactamente una solicitud con el 10005 global canónico."""

        consultas_numeracion = 0
        solicitudes_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva sin abrir red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene estable la numeración sintética."""
            FakeWSFEClient.consultas_numeracion += 1
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Devuelve un rechazo global exacto sin detalle ni CAE."""
            FakeWSFEClient.solicitudes_fecae += 1
            raise ArcaErrorGlobalEstructurado(
                cabecera=CabeceraRespuestaFecae(
                    cuit=int(test_empresa.cuit),
                    punto_venta=arca_request.punto_venta,
                    tipo_comprobante=arca_request.tipo_cbte,
                    cantidad=1,
                    resultado="R",
                ),
                errores=(MensajeArcaEstructurado(10005, "mensaje privado ARCA"),),
                eventos=(),
                detalles_presentes=False,
                senales_cae_presentes=False,
                request_cuit=int(test_empresa.cuit),
                request_punto_venta=arca_request.punto_venta,
                request_tipo_comprobante=arca_request.tipo_cbte,
                request_cantidad=1,
                request_rangos=((arca_request.cbte_desde, arca_request.cbte_hasta),),
            )

    lote_id, [grupo] = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo="lote-reintento-pf19c-10005-crash.xlsx",
    )
    idempotency_key = "idem-reintento-pf19c-10005-crash"
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[int(grupo.id)],
        idempotency_key=idempotency_key,
    )
    headers = {**auth_headers, **headers_reintento}
    body = {"grupo_ids": [int(grupo.id)]}
    guardar_original = IdempotenciaFiscalService.guardar_resultado_operacion_sync
    publicaciones_fallidas = 0

    async def fallar_primera_publicacion(
        self,
        operacion,
        *,
        response_json,
        estado,
    ):
        """Simula el crash posterior al commit del grafo y previo al response CAS."""
        nonlocal publicaciones_fallidas
        if publicaciones_fallidas == 0 and estado == "rechazado_arca":
            publicaciones_fallidas += 1
            raise SQLAlchemyTimeoutError("crash sintético post-cierre")
        return await guardar_original(
            self,
            operacion,
            response_json=response_json,
            estado=estado,
        )

    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "guardar_resultado_operacion_sync",
        fallar_primera_publicacion,
    )

    cierre_sin_publicar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers=headers,
        json=body,
    )
    assert cierre_sin_publicar.status_code == 409, cierre_sin_publicar.text
    db_session.expire_all()
    lote_cerrado = await db_session.get(LoteComprobante, lote_id)
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == idempotency_key
        )
    )
    assert lote_cerrado is not None
    assert lote_cerrado.estado == "fallido"
    assert operacion is not None
    assert operacion.estado == "en_proceso"
    assert operacion.response_json is None

    reconstruida = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers=headers,
        json=body,
    )
    replay = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers=headers,
        json=body,
    )

    assert reconstruida.status_code == 200, reconstruida.text
    assert replay.status_code == 200, replay.text
    assert replay.json() == reconstruida.json()
    assert reconstruida.json()["lote"]["estado"] == "fallido"
    assert reconstruida.json()["errores_arca"] == [
        {
            "codigo": 10005,
            "alcance": "global",
            "mensaje": "El punto de venta no está dado de alta como RECE en ARCA.",
        }
    ]
    assert FakeWSFEClient.solicitudes_fecae == 1
    await db_session.refresh(operacion)
    assert operacion.estado == "rechazado_arca"
    assert operacion.response_json == reconstruida.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "caso"),
    [
        pytest.param({}, "omitido", id="grupo_ids-omitido"),
        pytest.param({"grupo_ids": []}, "vacio", id="grupo_ids-vacio"),
    ],
)
async def test_reintentar_fallidos_replay_terminal_sin_seleccion_no_reemite(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    body: dict[str, list[int]],
    caso: str,
) -> None:
    """Omitir o vaciar la selección reejecuta la misma respuesta terminal sin I/O."""

    class FakeWSFEClient:
        """Autoriza una vez y contabiliza cualquier I/O fiscal posterior."""

        consultas_fecomp = 0
        solicitudes_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Devuelve una historia vacía y contabiliza FEComp."""
            FakeWSFEClient.consultas_fecomp += 1
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Autoriza una única solicitud fiscal sintética."""
            FakeWSFEClient.solicitudes_fecae += 1
            return CAEResponse(
                cae=CAE_TEST_NO_REAL_36,
                cae_vencimiento="20260831",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    lote_id, [grupo] = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo=f"lote-replay-sin-seleccion-{caso}.xlsx",
    )
    grupo_id = int(grupo.id)
    idempotency_key = f"idem-replay-sin-seleccion-{caso}"
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        idempotency_key=idempotency_key,
    )
    llamadas_ticket = 0

    async def fake_ticket(self, empresa, certificado):
        nonlocal llamadas_ticket
        llamadas_ticket += 1
        return SimpleNamespace(token="token-test", sign="sign-test")

    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)

    primera = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json=body,
    )
    assert primera.status_code == 200, primera.text
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == idempotency_key
        )
    )
    assert operacion is not None
    operacion_id = int(operacion.id)
    conteos_antes = {
        "operaciones": int(
            await db_session.scalar(
                select(func.count(OperacionIdempotente.id)).where(
                    OperacionIdempotente.idempotency_key == idempotency_key
                )
            )
            or 0
        ),
        "guardas": int(
            await db_session.scalar(
                select(func.count(PuntoVentaGuardaEmisionRece.id)).where(
                    PuntoVentaGuardaEmisionRece.operacion_id == operacion_id
                )
            )
            or 0
        ),
        "intentos": int(
            await db_session.scalar(
                select(func.count(IntentoEmisionFiscal.id)).where(
                    IntentoEmisionFiscal.operacion_id == operacion_id
                )
            )
            or 0
        ),
    }
    assert conteos_antes == {"operaciones": 1, "guardas": 1, "intentos": 1}
    llamadas_ticket = 0
    FakeWSFEClient.consultas_fecomp = 0
    FakeWSFEClient.solicitudes_fecae = 0

    replay = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json=body,
    )

    assert replay.status_code == 200, replay.text
    assert replay.json() == primera.json()
    assert llamadas_ticket == 0
    assert FakeWSFEClient.consultas_fecomp == 0
    assert FakeWSFEClient.solicitudes_fecae == 0
    db_session.expire_all()
    assert (await db_session.get(LoteComprobanteGrupo, grupo_id)).estado == (
        "autorizado"
    )
    conteos_despues = {
        "operaciones": int(
            await db_session.scalar(
                select(func.count(OperacionIdempotente.id)).where(
                    OperacionIdempotente.idempotency_key == idempotency_key
                )
            )
            or 0
        ),
        "guardas": int(
            await db_session.scalar(
                select(func.count(PuntoVentaGuardaEmisionRece.id)).where(
                    PuntoVentaGuardaEmisionRece.operacion_id == operacion_id
                )
            )
            or 0
        ),
        "intentos": int(
            await db_session.scalar(
                select(func.count(IntentoEmisionFiscal.id)).where(
                    IntentoEmisionFiscal.operacion_id == operacion_id
                )
            )
            or 0
        ),
    }
    assert conteos_despues == conteos_antes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("segundo_preflight", "categoria_error"),
    [
        ("avanza", "numeracion_arca_cambio_pre_arca"),
        ("falla", "preflight_arca_no_disponible"),
    ],
)
async def test_reintentar_fallidos_aborta_seleccion_si_falla_segundo_preflight(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    segundo_preflight: str,
    categoria_error: str,
) -> None:
    """La numeración inestable cierra el intento y no reclama otro grupo."""

    class FakeWSFEClient:
        """Desestabiliza el segundo preflight y prohíbe continuar la selección."""

        consultas_numeracion = 0
        llamadas_cae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Cambia o falla después de reservar el primer grupo."""
            FakeWSFEClient.consultas_numeracion += 1
            if FakeWSFEClient.consultas_numeracion == 1:
                return 5
            if FakeWSFEClient.consultas_numeracion == 2:
                if segundo_preflight == "avanza":
                    return 6
                raise ArcaServiceError("preflight sintético no disponible")
            raise AssertionError("No debe consultar la numeración de otro grupo")

        async def fe_cae_solicitar(self, arca_request):
            """No debe invocarse con una reserva no reconfirmada."""
            FakeWSFEClient.llamadas_cae += 1
            raise AssertionError("No debe solicitar CAE")

    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo=f"lote-reintento-{segundo_preflight}.xlsx",
        total_grupos=2,
    )
    grupo_ids = [grupo.id for grupo in grupos]
    mensajes_segundo = list(grupos[1].mensajes_json or [])
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=grupo_ids,
        idempotency_key=f"idem-reintento-{segundo_preflight}",
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": grupo_ids},
    )

    assert response.status_code == 200, response.text
    assert FakeWSFEClient.consultas_numeracion == 2
    assert FakeWSFEClient.llamadas_cae == 0
    db_session.expire_all()
    primero = await db_session.get(LoteComprobanteGrupo, grupo_ids[0])
    segundo = await db_session.get(LoteComprobanteGrupo, grupo_ids[1])
    assert primero is not None
    assert segundo is not None
    assert primero.estado == "fallido"
    assert primero.numero_asignado is None
    assert primero.cae is None
    assert primero.comprobante_id is None
    assert segundo.estado == "fallido"
    assert segundo.mensajes_json == mensajes_segundo
    intentos = (
        (
            await db_session.execute(
                select(IntentoEmisionFiscal).order_by(IntentoEmisionFiscal.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(intentos) == 1
    assert intentos[0].grupo_id == primero.id
    assert intentos[0].estado == "fallido_verificado"
    assert intentos[0].categoria_error == categoria_error


@pytest.mark.asyncio
async def test_reintento_restaura_grupo_si_cambia_evidencia_en_segundo_preflight(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """El rollback real de Facturación no expira el identificador a restaurar."""

    class FakeWSFEClient:
        llamadas_cae = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            return 5

        async def fe_cae_solicitar(self, arca_request):
            FakeWSFEClient.llamadas_cae += 1
            raise AssertionError("No debe solicitar CAE con evidencia nueva")

    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo="lote-reintento-evidencia-tardia.xlsx",
        total_grupos=2,
    )
    grupo_id = int(inspect(grupos[0]).identity[0])
    otro_grupo_id = int(inspect(grupos[1]).identity[0])
    otro_mensaje = list(grupos[1].mensajes_json or [])
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
        idempotency_key="idem-reintento-evidencia-tardia",
    )
    revalidaciones = 0

    async def evidencia_cambia_en_segundo_preflight(self, **kwargs):
        nonlocal revalidaciones
        revalidaciones += 1
        if revalidaciones == 1:
            return {"estado": "sin_coincidencias", "evidencia_id": None}
        raise DuplicadosLotePreflightCambioError(
            {
                "version": "duplicados_lotes/v2",
                "estado": "requiere_confirmacion",
                "evidencia_id": "v2.evidencia-nueva",
            }
        )

    monkeypatch.setattr(
        DuplicadosLotesService,
        "revalidar_operacion_lote",
        evidencia_cambia_en_segundo_preflight,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers},
        json={"grupo_ids": [grupo_id]},
    )

    assert response.status_code == 409, response.text
    assert revalidaciones == 2
    assert FakeWSFEClient.llamadas_cae == 0
    db_session.expire_all()
    grupo = await db_session.get(LoteComprobanteGrupo, grupo_id)
    otro = await db_session.get(LoteComprobanteGrupo, otro_grupo_id)
    assert grupo is not None
    assert otro is not None
    assert grupo.estado == "fallido"
    assert grupo.duplicados_reserva_operacion_id is None
    assert grupo.numero_asignado is None
    assert grupo.cae is None
    assert otro.estado == "fallido"
    assert otro.mensajes_json == otro_mensaje
    assert (
        int(await db_session.scalar(select(func.count(IntentoEmisionFiscal.id))) or 0)
        == 0
    )


@pytest.mark.asyncio
async def test_reintentar_fallidos_detiene_seleccion_ante_respuesta_incierta(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Una respuesta ambigua bloquea el lote y deja intactos los demás grupos."""

    class FakeWSFEClient:
        """Simula una excepción incierta después de iniciar FECAE."""

        consultas_numeracion = 0
        llamadas_cae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene estable la numeración antes del primer FECAE."""
            FakeWSFEClient.consultas_numeracion += 1
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Falla sin confirmar si ARCA autorizó el comprobante."""
            FakeWSFEClient.llamadas_cae += 1
            raise ArcaServiceError("respuesta sintética incierta")

    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo="lote-reintento-incierto.xlsx",
        total_grupos=2,
    )
    grupo_ids = [grupo.id for grupo in grupos]
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=grupo_ids,
        idempotency_key="idem-reintento-incierto",
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": grupo_ids},
    )

    assert response.status_code == 200, response.text
    assert response.json()["lote"]["estado"] == "requiere_reconciliacion"
    assert FakeWSFEClient.consultas_numeracion == 2
    assert FakeWSFEClient.llamadas_cae == 1
    db_session.expire_all()
    primero = await db_session.get(LoteComprobanteGrupo, grupo_ids[0])
    segundo = await db_session.get(LoteComprobanteGrupo, grupo_ids[1])
    assert primero is not None
    assert segundo is not None
    assert primero.estado == "requiere_reconciliacion"
    assert primero.numero_asignado == 1
    assert segundo.estado == "requiere_reconciliacion"
    assert segundo.numero_asignado is None
    assert segundo.cae is None
    assert segundo.comprobante_id is None
    assert "No se enviaron grupos posteriores" in segundo.mensajes_json[0]
    intentos = (
        (
            await db_session.execute(
                select(IntentoEmisionFiscal).order_by(IntentoEmisionFiscal.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(intentos) == 1
    assert intentos[0].estado == "requiere_reconciliacion"
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-reintento-incierto"
        )
    )
    assert operacion is not None
    assert operacion.estado == "requiere_reconciliacion"


@pytest.mark.asyncio
async def test_reintentar_fallidos_no_degrada_autorizacion_si_falla_capa_lote(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Un fallo local posterior al CAE debe bloquear, nunca volver a fallido."""

    class FakeWSFEClient:
        """Autoriza el primer comprobante antes del fallo local inyectado."""

        llamadas_cae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene estable la numeración sintética."""
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Devuelve un CAE sintético válido."""
            FakeWSFEClient.llamadas_cae += 1
            return CAEResponse(
                cae=CAE_TEST_NO_REAL_ALT,
                cae_vencimiento="20260831",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo="lote-reintento-fallo-capa-lote.xlsx",
        total_grupos=2,
    )
    grupo_ids = [grupo.id for grupo in grupos]
    mensajes_segundo = list(grupos[1].mensajes_json or [])

    async def fail_aplicar_resultado(self, grupo, resultado):
        raise RuntimeError("detalle interno sintético")

    monkeypatch.setattr(
        LoteComprobantesService,
        "_aplicar_resultado_emision_grupo",
        fail_aplicar_resultado,
    )
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=grupo_ids,
        idempotency_key="idem-reintento-fallo-capa-lote",
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": grupo_ids},
    )

    assert response.status_code == 200, response.text
    assert response.json()["lote"]["estado"] == "requiere_reconciliacion"
    assert "detalle interno sintético" not in response.text
    assert FakeWSFEClient.llamadas_cae == 1
    db_session.expire_all()
    primero = await db_session.get(LoteComprobanteGrupo, grupo_ids[0])
    segundo = await db_session.get(LoteComprobanteGrupo, grupo_ids[1])
    assert primero is not None
    assert segundo is not None
    assert primero.estado == "requiere_reconciliacion"
    assert primero.numero_asignado == 1
    assert primero.cae == CAE_TEST_NO_REAL_ALT
    assert primero.comprobante_id is None
    assert segundo.estado == "fallido"
    assert segundo.mensajes_json == mensajes_segundo
    intentos = (
        (
            await db_session.execute(
                select(IntentoEmisionFiscal).order_by(IntentoEmisionFiscal.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(intentos) == 1
    assert intentos[0].estado == "requiere_reconciliacion"
    assert intentos[0].cae == CAE_TEST_NO_REAL_ALT
    comprobantes = (await db_session.execute(select(Comprobante))).scalars().all()
    assert comprobantes == []


@pytest.mark.asyncio
async def test_reintentar_fallidos_continua_solo_tras_rechazo_arca_explicito(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Un rechazo explícito libera el número y permite el siguiente grupo."""

    class FakeWSFEClient:
        """Rechaza el primer request y autoriza el segundo de forma explícita."""

        consultas_numeracion = 0
        llamadas_cae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene disponible el mismo número tras el rechazo."""
            FakeWSFEClient.consultas_numeracion += 1
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Devuelve primero R y luego A con respuestas completas."""
            FakeWSFEClient.llamadas_cae += 1
            if FakeWSFEClient.llamadas_cae == 1:
                return CAEResponse(
                    cae=None,
                    cae_vencimiento=None,
                    numero_comprobante=arca_request.cbte_desde,
                    tipo_cbte=arca_request.tipo_cbte,
                    punto_venta=arca_request.punto_venta,
                    resultado="R",
                    errores=[
                        {
                            "code": 10016,
                            "msg": "Rechazo sintético explícito",
                        }
                    ],
                )
            return CAEResponse(
                cae=CAE_TEST_NO_REAL_ALT,
                cae_vencimiento="20260831",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo="lote-reintento-rechazo-explicito.xlsx",
        total_grupos=2,
    )
    grupo_ids = [grupo.id for grupo in grupos]
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=grupo_ids,
        idempotency_key="idem-reintento-rechazo-explicito",
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": grupo_ids},
    )

    assert response.status_code == 200, response.text
    assert FakeWSFEClient.consultas_numeracion == 4
    assert FakeWSFEClient.llamadas_cae == 2
    db_session.expire_all()
    primero = await db_session.get(LoteComprobanteGrupo, grupo_ids[0])
    segundo = await db_session.get(LoteComprobanteGrupo, grupo_ids[1])
    assert primero is not None
    assert segundo is not None
    assert primero.estado == "fallido"
    assert primero.numero_asignado is None
    assert segundo.estado == "autorizado"
    assert segundo.numero_asignado == 1
    intentos = list(
        (
            await db_session.scalars(
                select(IntentoEmisionFiscal).order_by(IntentoEmisionFiscal.id)
            )
        ).all()
    )
    assert [intento.estado for intento in intentos] == [
        "rechazado_arca",
        "autorizado",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bloqueo",
    ["local_adelantada", "en_proceso", "requiere_reconciliacion"],
)
async def test_reintentar_fallidos_detiene_seleccion_ante_bloqueo_propio(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    bloqueo: str,
) -> None:
    """La historia local o un intento propio incierto bloquean toda selección."""

    class FakeWSFEClient:
        """Expone historia ARCA solo para el caso local adelantado."""

        consultas_numeracion = 0
        llamadas_cae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Deja a la historia local exactamente un número adelantada."""
            FakeWSFEClient.consultas_numeracion += 1
            if bloqueo != "local_adelantada":
                raise AssertionError("Un intento propio debe bloquear antes de ARCA")
            return 4

        async def fe_cae_solicitar(self, arca_request):
            """No debe solicitar CAE bajo ningún bloqueo."""
            FakeWSFEClient.llamadas_cae += 1
            raise AssertionError("No debe solicitar CAE")

    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        FakeWSFEClient,
        nombre_archivo=f"lote-reintento-bloqueo-{bloqueo}.xlsx",
        total_grupos=2,
        ultimo_local=5 if bloqueo == "local_adelantada" else None,
    )
    grupo_ids = [grupo.id for grupo in grupos]
    mensajes_segundo = list(grupos[1].mensajes_json or [])
    if bloqueo != "local_adelantada":
        db_session.add(
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=test_punto_venta.numero,
                numero_planificado=1,
                fecha_emision=FECHA_FISCAL_PF02B2,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash=f"payload-bloqueante-{bloqueo}",
                huella_logica=f"huella-bloqueante-{bloqueo}",
                estado=bloqueo,
                empresa_id=test_empresa.id,
                punto_venta_id=test_punto_venta.id,
            )
        )
        await db_session.commit()
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=grupo_ids,
        idempotency_key=f"idem-reintento-bloqueo-{bloqueo}",
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": grupo_ids},
    )

    assert response.status_code == 200, response.text
    assert FakeWSFEClient.consultas_numeracion == (
        1 if bloqueo == "local_adelantada" else 0
    )
    assert FakeWSFEClient.llamadas_cae == 0
    db_session.expire_all()
    primero = await db_session.get(LoteComprobanteGrupo, grupo_ids[0])
    segundo = await db_session.get(LoteComprobanteGrupo, grupo_ids[1])
    assert primero is not None
    assert segundo is not None
    assert primero.estado == "fallido"
    assert primero.numero_asignado is None
    assert primero.cae is None
    assert segundo.estado == "fallido"
    assert segundo.mensajes_json == mensajes_segundo
    intentos_grupo = list(
        (
            await db_session.scalars(
                select(IntentoEmisionFiscal).where(
                    IntentoEmisionFiscal.grupo_id.in_(grupo_ids)
                )
            )
        ).all()
    )
    assert intentos_grupo == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyTimeoutError, OperationalError],
    ids=["timeout", "operational"],
)
async def test_reintentar_lote_db_temporal_pre_arca_restaura_grupo_exacto(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    error_type: type[Exception],
) -> None:
    """La caída DB pre-ARCA restaura solo el grupo reclamado y abre replay."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-db-temporal.xlsx",
        total_grupos=2,
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido", "fallido"])
    grupo = grupos[0]
    otro_grupo = grupos[1]
    grupo_id = grupo.id
    otro_grupo_id = otro_grupo.id
    mensajes_previos = list(grupo.mensajes_json or [])

    async def fail_emitir_locked(self, request, **kwargs):
        assert kwargs["fase_solicitud_arca"].iniciada is False
        raise _crear_error_db_temporal(error_type)

    monkeypatch.setattr(
        FacturacionService,
        "_emitir_comprobante_locked",
        fail_emitir_locked,
    )
    confirmacion = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=[grupo_id],
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **confirmacion},
        json={"grupo_ids": [grupo_id]},
    )

    assert response.status_code == 503, response.text
    assert response.headers["Retry-After"] == "2"
    assert "UPDATE lotes_comprobantes" not in response.text
    db_session.expire_all()
    grupo_actual = await db_session.get(LoteComprobanteGrupo, grupo_id)
    assert grupo_actual is not None
    assert grupo_actual.estado == "fallido"
    assert grupo_actual.mensajes_json == mensajes_previos
    otro_actual = await db_session.get(LoteComprobanteGrupo, otro_grupo_id)
    assert otro_actual is not None
    assert otro_actual.estado == "fallido"
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-lote-test"
        )
    )
    assert operacion is not None
    assert operacion.estado == "interrumpida_pre_arca"
    intentos_actuales = (
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
    assert intentos_actuales == []
    assert not any(
        "UPDATE lotes_comprobantes" in mensaje
        for mensaje in (grupo_actual.mensajes_json or [])
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metodo_fallido",
    [
        "obtener_resumen_operativo_lote",
        "obtener_confirmacion_duplicado_logico_grupos",
    ],
)
async def test_procesar_lote_recupera_consultas_db_post_operacion(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    metodo_fallido: str,
) -> None:
    """Resumen y duplicados quedan dentro de la recuperación atómica pre-ARCA."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo=f"lote-fallo-{metodo_fallido}.xlsx",
    )

    async def fail_db(self, *args, **kwargs):
        raise SQLAlchemyTimeoutError()

    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )
    monkeypatch.setattr(LoteComprobantesService, metodo_fallido, fail_db)
    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert response.status_code == 503, response.text
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    assert lote.estado == "validado"
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-lote-test"
        )
    )
    assert operacion is not None
    assert operacion.estado == "interrumpida_pre_arca"
    intentos = await db_session.scalars(
        select(IntentoEmisionFiscal).where(
            IntentoEmisionFiscal.operacion_id == operacion.id
        )
    )
    assert intentos.all() == []


@pytest.mark.asyncio
async def test_reintentar_fallo_db_antes_de_operacion_devuelve_503_sin_unboundlocal(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Una caída antes del resolver se propaga sin leer variables inexistentes."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-fallo-temprano.xlsx",
    )
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    async def fail_lookup(self, *args, **kwargs):
        raise OperationalError("SELECT lote", {}, RuntimeError("db caída"))

    monkeypatch.setattr(
        LoteComprobantesService,
        "obtener_lote_resumen",
        fail_lookup,
    )
    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **headers_reintento},
        json={"grupo_ids": []},
    )

    assert response.status_code == 503
    assert "UnboundLocalError" not in response.text
    assert response.headers["Retry-After"] == "2"


@pytest.mark.asyncio
async def test_reintentar_commit_ambiguo_confirmado_habilita_replay(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """El reintento recupera un commit ambiguo y la misma clave puede reclamarlo."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-commit-ambiguo.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    original_commit = db_session.commit
    fallo_inyectado = False

    async def commit_ambiguo():
        nonlocal fallo_inyectado
        await original_commit()
        if not fallo_inyectado:
            fallo_inyectado = True
            raise SQLAlchemyTimeoutError()

    monkeypatch.setattr(db_session, "commit", commit_ambiguo)

    async def fake_reintentar(self, lote_id, empresa_id, **kwargs):
        return await self.obtener_lote(lote_id, empresa_id)

    monkeypatch.setattr(
        LoteComprobantesService,
        "reintentar_grupos_fallidos",
        fake_reintentar,
    )
    grupo_ids = [grupos[0].id]
    headers_reintento = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"fallido"},
        grupo_ids=grupo_ids,
        idempotency_key="idem-reintento-create-ambiguo",
    )
    headers = {**auth_headers, **headers_reintento}
    body = {"grupo_ids": grupo_ids}

    primera = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers=headers,
        json=body,
    )
    segunda = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers=headers,
        json=body,
    )

    assert primera.status_code == 503, primera.text
    assert segunda.status_code == 200, segunda.text
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-reintento-create-ambiguo"
        )
    )
    assert operacion is not None
    assert operacion.estado == "finalizado"
    assert fallo_inyectado is True


@pytest.mark.asyncio
@pytest.mark.parametrize("caso", ["inexistente", "cruzado"])
async def test_reconciliar_externo_valida_ownership_antes_de_arca(
    caso: str,
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """Un lote inexistente o ajeno corta antes de WSAA/FEComp/FECAE."""
    lote_id = 999_999
    if caso == "cruzado":
        otra_empresa = Empresa(
            razon_social="Empresa lote cruzado sintética",
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
        lote_ajeno = LoteComprobante(
            empresa_id=otra_empresa.id,
            nombre_archivo="lote-reconciliacion-cruzado.xlsx",
            archivo_hash="d" * 64,
            estado="con_errores",
        )
        db_session.add(lote_ajeno)
        await db_session.commit()
        lote_id = int(lote_ajeno.id)

    llamadas = {"wsaa": 0, "fecomp": 0, "fecae": 0}

    class FakeWSFEClient:
        """Registra cualquier cruce indebido de la frontera ARCA."""

        async def fe_comp_consultar(self, **kwargs):
            """Registra una consulta FEComp indebida."""
            llamadas["fecomp"] += 1
            raise AssertionError("No debe consultar ARCA para un lote ajeno")

        async def fe_cae_solicitar(self, request):
            """Registra una solicitud FECAE indebida."""
            llamadas["fecae"] += 1
            raise AssertionError("La reconciliación nunca solicita CAE")

    async def fake_get_wsfe_client(*args, **kwargs):
        """Representa la autenticación WSAA que debe quedar en cero."""
        llamadas["wsaa"] += 1
        return FakeWSFEClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": 1,
                    "tipo_comprobante": 6,
                    "punto_venta_numero": 1,
                    "numero": 1,
                    "fecha_emision": "08/08/2026",
                    "total": 121.0,
                    "cae": CAE_TEST_NO_REAL,
                    "motivo": "Reconciliación sintética",
                }
            ]
        },
    )

    assert response.status_code == 400, response.text
    assert "No se encontró el lote solicitado" in response.json()["detail"]
    assert llamadas == {"wsaa": 0, "fecomp": 0, "fecae": 0}


@pytest.mark.asyncio
async def test_reconciliar_externo_verifica_arca_y_crea_comprobante(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un comprobante manual se reconcilia solo si ARCA confirma los datos."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-externo.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_ALT,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "cae": CAE_TEST_NO_REAL_ALT,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["lote"]
    assert data["estado"] == "cerrado_reconciliado"
    assert data["grupos_reconciliados_externos"] == 1

    await db_session.refresh(grupo)
    assert grupo.estado == "autorizado_externo"
    assert grupo.numero_asignado == 456
    assert grupo.comprobante_id is not None
    comprobante = await db_session.get(Comprobante, grupo.comprobante_id)
    assert comprobante.origen_emision == "arca_web"
    assert comprobante.estado == "autorizado"


@pytest.mark.asyncio
async def test_reconciliar_externo_rechaza_receptor_distinto_en_arca(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No se debe vincular un comprobante ARCA emitido a otro receptor."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-receptor-distinto.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_38,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=30712345678,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "cae": CAE_TEST_NO_REAL_38,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "receptor informado por ARCA no coincide" in response.json()["detail"]
    await db_session.refresh(grupo)
    assert grupo.estado == "fallido"
    assert grupo.comprobante_id is None


@pytest.mark.asyncio
async def test_reconciliar_externo_rechaza_comprobante_ya_vinculado(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un comprobante externo no puede cerrar dos grupos distintos."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-externo-duplicado.xlsx",
        total_grupos=2,
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido", "fallido"])
    payload_segundo = deepcopy(grupos[1].payload_json or {})
    payload_segundo["tipo_documento"] = grupos[0].payload_json["tipo_documento"]
    payload_segundo["numero_documento"] = grupos[0].payload_json["numero_documento"]
    payload_segundo["razon_social"] = grupos[0].payload_json["razon_social"]
    grupos[1].payload_json = payload_segundo
    await db_session.commit()

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_39,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupos[0].fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=96,
                nro_doc=30000001,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    payload_base = {
        "tipo_comprobante": grupos[0].tipo_comprobante,
        "punto_venta_numero": grupos[0].punto_venta_numero,
        "numero": 456,
        "fecha_emision": str(grupos[0].fecha_emision),
        "total": 1210.0,
        "cae": CAE_TEST_NO_REAL_39,
        "motivo": "Emitido manualmente por ARCA Web",
    }
    primera = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={"comprobantes": [{**payload_base, "grupo_id": grupos[0].id}]},
    )
    assert primera.status_code == 200, primera.text

    segunda = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={"comprobantes": [{**payload_base, "grupo_id": grupos[1].id}]},
    )

    assert segunda.status_code == 400
    assert "ya está vinculado a otro grupo" in segunda.json()["detail"]
    await db_session.refresh(grupos[1])
    assert grupos[1].estado == "fallido"
    assert grupos[1].comprobante_id is None


@pytest.mark.asyncio
async def test_reconciliar_externo_resuelve_lote_con_reconciliacion_tecnica(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Los grupos inciertos deben poder cerrarse con verificación de ARCA."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-requiere-reconciliacion.xlsx",
    )
    grupos = await _marcar_grupos_lote(
        db_session,
        lote_id,
        ["requiere_reconciliacion"],
    )
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_36,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 789,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "motivo": "Recuperación luego de corte post-ARCA",
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["lote"]["estado"] == "cerrado_reconciliado"


@pytest.mark.asyncio
async def test_reconciliar_externo_resuelve_reintento_interrumpido(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un grupo reclamado para reintento debe cerrarse verificando ARCA."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-interrumpido.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["reintentando"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_40,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 790,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "motivo": "Recuperación de reintento interrumpido",
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["lote"]["estado"] == "cerrado_reconciliado"


@pytest.mark.asyncio
async def test_reconciliar_externo_error_arca_responde_400_controlado(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un error esperado de consulta ARCA no debe escapar como 500."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-error-arca.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(self, *args, **kwargs):
            raise ArcaServiceError("Comprobante inexistente")

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert (
        "No se pudo verificar el comprobante externo contra ARCA"
        in response.json()["detail"]
    )


@pytest.mark.asyncio
async def test_reconciliar_externo_rechaza_arca_sin_cae(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una consulta ARCA autorizada pero sin CAE no puede cerrar el grupo."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-sin-cae.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae="",
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "ARCA no devolvió un CAE válido" in response.json()["detail"]
    await db_session.refresh(grupo)
    assert grupo.estado == "fallido"
    assert grupo.comprobante_id is None


@pytest.mark.asyncio
async def test_reconciliar_externo_con_error_incompleto_responde_400(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un grupo observado sin payload fiscal completo no debe escapar como 500."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-con-error-incompleto.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["con_error"])
    grupo = grupos[0]
    fecha_emision = str(grupo.fecha_emision)
    grupo.payload_json = {}
    await db_session.commit()

    class FakeWsfeClient:
        async def fe_comp_consultar(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("No debe consultar ARCA con payload incompleto")

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": fecha_emision,
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "datos fiscales completos" in response.json()["detail"]


@pytest.mark.asyncio
async def test_reconciliar_externos_multi_item_es_atomico_si_un_item_falla(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una reconciliación parcial fallida no debe dejar comprobantes huérfanos."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-atomico.xlsx",
        total_grupos=2,
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido", "fallido"])
    consultas = 0

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            nonlocal consultas
            consultas += 1
            if consultas == 2:
                raise ArcaServiceError("Comprobante inexistente")
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_37,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupos[0].fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=96,
                nro_doc=30000001,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupos[0].id,
                    "tipo_comprobante": grupos[0].tipo_comprobante,
                    "punto_venta_numero": grupos[0].punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": str(grupos[0].fecha_emision),
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                },
                {
                    "grupo_id": grupos[1].id,
                    "tipo_comprobante": grupos[1].tipo_comprobante,
                    "punto_venta_numero": grupos[1].punto_venta_numero,
                    "numero": 457,
                    "fecha_emision": str(grupos[1].fecha_emision),
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                },
            ]
        },
    )

    assert response.status_code == 400
    assert consultas == 2

    comprobantes = await db_session.scalar(
        select(func.count())
        .select_from(Comprobante)
        .where(Comprobante.origen_emision == "arca_web")
    )
    assert comprobantes == 0

    for grupo in grupos:
        await db_session.refresh(grupo)
        assert grupo.estado == "fallido"
        assert grupo.comprobante_id is None


@pytest.mark.asyncio
async def test_compactar_lote_cerrado_elimina_filas_y_bloquea_observado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Compactar debe eliminar filas pesadas sin borrar grupos ni resumen."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-compactar.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["autorizado"])

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/compactar",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    lote_data = response.json()["lote"]
    assert lote_data["compactado_at"] is not None

    filas = await db_session.scalar(
        select(func.count())
        .select_from(LoteComprobanteFila)
        .where(LoteComprobanteFila.lote_id == lote_id)
    )
    grupos = await db_session.scalar(
        select(func.count())
        .select_from(LoteComprobanteGrupo)
        .where(LoteComprobanteGrupo.lote_id == lote_id)
    )
    assert filas == 0
    assert grupos == 1
    evento = (
        await db_session.execute(
            select(LoteComprobanteEvento).where(
                LoteComprobanteEvento.accion == "compactar_lote"
            )
        )
    ).scalar_one()
    assert evento.motivo == "Compactación para ahorro de almacenamiento"

    observado = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/archivo-observado",
        headers=auth_headers,
    )
    assert observado.status_code == 400
    assert "compactado" in observado.json()["detail"]


@pytest.mark.asyncio
async def test_eliminar_lote_sin_emision_permite_y_conserva_evento(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Solo se elimina físicamente un lote sin emisión ni incertidumbre."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-eliminar-sin-emision.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["con_error"])

    response = await client.request(
        "DELETE",
        f"/api/lotes-comprobantes/{lote_id}",
        headers=auth_headers,
        json={"motivo": "Carga con archivo equivocado"},
    )

    assert response.status_code == 204, response.text
    assert await db_session.get(LoteComprobante, lote_id) is None

    evento = (
        await db_session.execute(
            select(LoteComprobanteEvento).where(
                LoteComprobanteEvento.accion == "eliminar_lote"
            )
        )
    ).scalar_one()
    assert evento.lote_id is None
    assert evento.metadata_json["lote_id_original"] == lote_id


@pytest.mark.asyncio
async def test_eliminar_lote_permite_control_pendiente_sin_intento_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-eliminar-control-pendiente.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["con_error"])
    operation = OperacionIdempotente(
        empresa_id=int(test_empresa.id),
        idempotency_key="pf13-h3-borrar-pendiente",
        tipo_operacion="procesar_lote",
        payload_hash="3" * 64,
        estado="en_proceso",
        lote_id=lote_id,
        duplicados_version="duplicados_lotes/v2",
    )
    db_session.add(operation)
    await db_session.flush()
    generation = LoteDuplicadoEvidencia(
        operacion_id=int(operation.id),
        empresa_id=int(test_empresa.id),
        ambiente=settings.arca_env,
        lote_id=lote_id,
        generacion=1,
        formato="duplicados_relacion/1",
        evidencia_id=None,
        snapshot_hash="3" * 64,
        control_snapshot_json={"manifiesto": {"bloques": 0, "miembros": 0}},
    )
    db_session.add(generation)
    await db_session.flush()
    generation_id = int(generation.id)
    operation.duplicados_generacion_id = int(generation.id)
    await db_session.commit()

    response = await client.request(
        "DELETE",
        f"/api/lotes-comprobantes/{lote_id}",
        headers=auth_headers,
        json={"motivo": "Carga descartada antes de emitir"},
    )

    assert response.status_code == 204, response.text
    assert await db_session.get(LoteComprobante, lote_id) is None
    await db_session.refresh(operation)
    assert operation.lote_id is None
    assert operation.duplicados_generacion_id is None
    assert (
        await db_session.scalar(
            select(func.count(LoteDuplicadoEvidencia.id)).where(
                LoteDuplicadoEvidencia.id == generation_id
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_eliminar_lote_rechaza_emitidos_o_inciertos(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote con emisión o incertidumbre fiscal no puede borrarse."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-no-eliminar-emitido.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["autorizado"])

    response = await client.request(
        "DELETE",
        f"/api/lotes-comprobantes/{lote_id}",
        headers=auth_headers,
        json={"motivo": "No quiero conservarlo"},
    )

    assert response.status_code == 400
    assert "comprobantes emitidos" in response.json()["detail"]
    assert await db_session.get(LoteComprobante, lote_id) is not None


@pytest.mark.asyncio
async def test_eliminar_lote_rechaza_cualquier_intento_con_conflicto(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Todo intento fiscal preserva el lote aunque haya fallado de forma segura."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-no-eliminar-intento.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["requiere_reconciliacion"])
    grupo = (
        await db_session.execute(
            select(LoteComprobanteGrupo).where(LoteComprobanteGrupo.lote_id == lote_id)
        )
    ).scalar_one()
    db_session.add(
        IntentoEmisionFiscal(
            tipo_comprobante=6,
            punto_venta_numero=test_punto_venta.numero,
            fecha_emision=date(2026, 8, 8),
            total=Decimal("121.00"),
            payload_hash="1" * 64,
            huella_logica="2" * 64,
            estado="fallido_verificado",
            empresa_id=test_empresa.id,
            punto_venta_id=test_punto_venta.id,
            lote_id=lote_id,
            grupo_id=grupo.id,
        )
    )
    await db_session.commit()

    response = await client.request(
        "DELETE",
        f"/api/lotes-comprobantes/{lote_id}",
        headers=auth_headers,
        json={"motivo": "No quiero conservarlo"},
    )

    assert response.status_code == 409
    assert "intentos fiscales" in response.json()["detail"]
    assert await db_session.get(LoteComprobante, lote_id) is not None


@pytest.mark.asyncio
async def test_eliminar_lote_reconciliacion_sin_intentos_devuelve_conflicto(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Un lote incierto devuelve 409 aun sin una fila de intento asociada."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-no-eliminar-reconciliacion.xlsx",
    )
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    lote.estado = "requiere_reconciliacion"
    grupos = list(
        (
            await db_session.scalars(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id
                )
            )
        ).all()
    )
    filas = list(
        (
            await db_session.scalars(
                select(LoteComprobanteFila).where(
                    LoteComprobanteFila.lote_id == lote_id
                )
            )
        ).all()
    )
    for grupo in grupos:
        grupo.estado = "requiere_reconciliacion"
    for fila in filas:
        fila.estado = "requiere_reconciliacion"
    await db_session.commit()

    response = await client.request(
        "DELETE",
        f"/api/lotes-comprobantes/{lote_id}",
        headers=auth_headers,
        json={"motivo": "No quiero conservarlo"},
    )

    assert response.status_code == 409
    assert "requiere reconciliación" in response.json()["detail"]
    assert await db_session.get(LoteComprobante, lote_id) is not None


@pytest.mark.asyncio
async def test_reanudar_lote_vincula_comprobante_ya_guardado_sin_reemitir(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
):
    """Si el comprobante ya fue guardado, reanudar no debe volver a emitirlo."""
    fecha_fiscal = date(2026, 3, 20)
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
        "razon_social": "Cliente Lote SA",
        "condicion_iva": "RI",
        "domicilio": "Av. Siempre Viva 123",
        "moneda": "PES",
        "cotizacion": "1",
        "guardar_cliente": False,
        "items": [
            {
                "descripcion": "Servicio mensual",
                "cantidad": "1",
                "unidad": "unidad",
                "precio_unitario": "1000",
                "iva_porcentaje": "21",
            }
        ],
    }
    lote = LoteComprobante(
        nombre_archivo="lote-reanudar-idempotente.xlsx",
        archivo_hash="hash-reanudar-idempotente",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        metadata_json={
            "opciones_concepto": {"concepto_modo": "archivo"},
            "opciones_descripcion_item": {"descripcion_item_modo": "archivo"},
        },
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        payload_json=emitir_request,
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="validado",
        datos_json={},
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]
    request_model = EmitirComprobanteRequest.model_validate(emitir_request)
    payload_hash, huella = _hashes_fiscales_request(
        request_model,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    db_session.add_all([lote, grupo, fila, comprobante])
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=fecha_fiscal,
        total=Decimal("1210.00"),
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=comprobante.cae,
        cae_vencimiento=comprobante.cae_vencimiento,
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=comprobante.id,
        lote_id=lote.id,
        grupo_id=grupo.id,
    )
    db_session.add(intento)
    await db_session.commit()
    await db_session.refresh(lote)
    lote_id = lote.id
    empresa_id = test_empresa.id
    comprobante_id = comprobante.id
    comprobante_numero = comprobante.numero
    db_session.expire_all()

    service = LoteComprobantesService(db_session)

    async def fail_emitir(_request, **kwargs):
        raise AssertionError("No debe reemitir un grupo ya guardado")

    service.facturacion_service.emitir_comprobante = fail_emitir

    resultado = await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    assert resultado.estado == "completado"
    assert resultado.finished_at is not None
    detalle = await service.obtener_lote(lote_id, empresa_id)
    assert detalle.grupos[0].estado == "autorizado"
    assert detalle.grupos[0].comprobante_id == comprobante_id
    assert detalle.grupos[0].numero_asignado == comprobante_numero


@pytest.mark.asyncio
async def test_reanudar_lote_stale_con_grupos_autorizados_cierra_sin_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un lote stale localmente emitido se cierra sin pedir nuevos CAE."""
    fecha_fiscal = date(2026, 3, 20)
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
        "razon_social": "Cliente Lote SA",
        "condicion_iva": "RI",
        "domicilio": "Av. Siempre Viva 123",
        "moneda": "PES",
        "cotizacion": "1",
        "guardar_cliente": False,
        "items": [
            {
                "descripcion": "Servicio mensual",
                "cantidad": "1",
                "unidad": "unidad",
                "precio_unitario": "1000",
                "iva_porcentaje": "21",
            }
        ],
    }
    lote = LoteComprobante(
        nombre_archivo="lote-stale-ya-autorizado.xlsx",
        archivo_hash="hash-stale-ya-autorizado",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        empresa_id=test_empresa.id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]
    request_model = EmitirComprobanteRequest.model_validate(emitir_request)
    payload_hash, huella = _hashes_fiscales_request(
        request_model,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    db_session.add_all([lote, comprobante])
    await db_session.flush()
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        payload_json=emitir_request,
        cae=comprobante.cae,
        numero_asignado=comprobante.numero,
        comprobante_id=comprobante.id,
        mensajes_json=["Comprobante autorizado."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="autorizado",
        datos_json={},
        mensajes_json=["Comprobante autorizado."],
    )
    db_session.add_all([grupo, fila])
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=comprobante.numero,
        fecha_emision=fecha_fiscal,
        total=Decimal("1210.00"),
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=comprobante.cae,
        cae_vencimiento=comprobante.cae_vencimiento,
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=comprobante.id,
        lote_id=lote.id,
        grupo_id=grupo.id,
    )
    db_session.add(intento)
    await db_session.commit()
    await db_session.refresh(lote)
    lote_id = lote.id
    empresa_id = test_empresa.id
    db_session.expire_all()

    service = LoteComprobantesService(db_session)
    llamadas_arca = _instalar_oraculos_stale_sin_arca(service)

    resultado = await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    assert resultado.estado == "completado"
    assert resultado.finished_at is not None
    assert resultado.grupos_emitidos == 1
    assert "Todos los comprobantes" in resultado.mensaje_resumen

    eventos = (
        (
            await db_session.execute(
                select(LoteComprobanteEvento).where(
                    LoteComprobanteEvento.lote_id == lote_id,
                    LoteComprobanteEvento.accion == "reconciliacion_local_stale",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].metadata_json["grupos_reconciliados"] == 0
    assert llamadas_arca == {"wsaa": 0, "fecomp": 0, "fecae": 0}


@pytest.mark.asyncio
async def test_reanudar_lote_stale_legacy_no_consulta_arca_y_exige_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un lote stale legacy nunca consulta ARCA ni vuelve automáticamente a cola."""
    fecha_fiscal = date(2026, 3, 20)
    payload_autorizado = _payload_lote_basico(
        test_empresa.id,
        test_punto_venta.id,
        fecha_fiscal,
        razon_social="Cliente Autorizado SA",
    )
    payload_pendiente = _payload_lote_basico(
        test_empresa.id,
        test_punto_venta.id,
        fecha_fiscal,
        razon_social="Cliente Pendiente SA",
    )
    lote = LoteComprobante(
        nombre_archivo="lote-stale-parcial-intacto.xlsx",
        archivo_hash="hash-stale-parcial-intacto",
        estado="procesando",
        total_filas=2,
        total_grupos=2,
        empresa_id=test_empresa.id,
        metadata_json={
            "opciones_concepto": {"concepto_modo": "archivo"},
            "opciones_descripcion_item": {"descripcion_item_modo": "archivo"},
        },
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Autorizado SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]
    db_session.add_all([lote, comprobante])
    await db_session.flush()

    grupo_autorizado = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Autorizado SA",
        total_estimado=Decimal("1210.00"),
        payload_json=payload_autorizado,
        cae=comprobante.cae,
        numero_asignado=comprobante.numero,
        comprobante_id=comprobante.id,
        mensajes_json=["Comprobante autorizado."],
    )
    grupo_pendiente = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-002",
        orden=2,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Pendiente SA",
        total_estimado=Decimal("1210.00"),
        payload_json=payload_pendiente,
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    filas = [
        LoteComprobanteFila(
            lote=lote,
            grupo=grupo_autorizado,
            fila_excel=2,
            comprobante_ref="LOTE-001",
            estado="autorizado",
            datos_json={},
            mensajes_json=["Comprobante autorizado."],
        ),
        LoteComprobanteFila(
            lote=lote,
            grupo=grupo_pendiente,
            fila_excel=3,
            comprobante_ref="LOTE-002",
            estado="validado",
            datos_json={},
            mensajes_json=["Validado correctamente. Listo para emitir."],
        ),
    ]
    db_session.add_all([grupo_autorizado, grupo_pendiente, *filas])
    await db_session.flush()

    request_autorizado = EmitirComprobanteRequest.model_validate(payload_autorizado)
    payload_hash, huella = _hashes_fiscales_request(
        request_autorizado,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    db_session.add(
        IntentoEmisionFiscal(
            tipo_comprobante=6,
            punto_venta_numero=test_punto_venta.numero,
            numero_planificado=comprobante.numero,
            fecha_emision=fecha_fiscal,
            total=Decimal("1210.00"),
            receptor_tipo_documento=80,
            receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
            receptor_razon_social="Cliente Autorizado SA",
            payload_hash=payload_hash,
            huella_logica=huella,
            cae=comprobante.cae,
            cae_vencimiento=comprobante.cae_vencimiento,
            estado="autorizado",
            empresa_id=test_empresa.id,
            punto_venta_id=test_punto_venta.id,
            comprobante_id=comprobante.id,
            lote_id=lote.id,
            grupo_id=grupo_autorizado.id,
        )
    )
    lote_id = lote.id
    empresa_id = test_empresa.id
    await db_session.commit()
    db_session.expire_all()

    service = LoteComprobantesService(db_session)
    llamadas_arca = _instalar_oraculos_stale_sin_arca(service)

    resultado = await service.bloquear_lote_procesando_stale(
        lote_id,
        empresa_id,
    )

    assert resultado.estado == "requiere_reconciliacion"
    assert resultado.finished_at is not None
    assert resultado.grupos_emitidos == 1
    assert resultado.grupos_validos == 0

    segundo_resultado = await service.bloquear_lote_procesando_stale(
        lote_id,
        empresa_id,
    )
    assert segundo_resultado.estado == "requiere_reconciliacion"

    detalle = await service.obtener_lote(lote_id, empresa_id)
    pendiente = next(
        grupo for grupo in detalle.grupos if grupo.comprobante_ref == "LOTE-002"
    )
    assert pendiente.estado == "requiere_reconciliacion"
    assert pendiente.cae is None
    assert pendiente.numero_asignado is None
    assert pendiente.comprobante_id is None
    intentos_pendiente = await db_session.scalar(
        select(func.count(IntentoEmisionFiscal.id)).where(
            IntentoEmisionFiscal.grupo_id == pendiente.id
        )
    )
    assert intentos_pendiente == 0

    eventos = (
        (
            await db_session.execute(
                select(LoteComprobanteEvento).where(
                    LoteComprobanteEvento.lote_id == lote_id,
                    LoteComprobanteEvento.accion == "bloqueo_operativo_no_reemitir",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].metadata_json["estado_nuevo"] == "requiere_reconciliacion"
    assert eventos[0].metadata_json["grupos_marcados_reconciliacion"] == 1
    assert eventos[0].metadata_json["preflight_arca"] == []
    assert eventos[0].metadata_json["preflight_error"] == (
        "operacion_o_snapshot_rece_legacy"
    )
    assert llamadas_arca == {"wsaa": 0, "fecomp": 0, "fecae": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("segunda_combinacion_segura", [True, False])
async def test_preflight_stale_exige_todas_las_combinaciones_seguras(
    db_session: AsyncSession,
    test_empresa,
    test_user,
    test_punto_venta,
    segunda_combinacion_segura: bool,
) -> None:
    """Un lote mixto solo supera el preflight si todas sus combinaciones son seguras."""
    fecha_fiscal = date(2026, 8, 4)
    empresa_id = int(test_empresa.id)
    primer_punto_venta_id = int(test_punto_venta.id)
    primer_punto_venta_numero = int(test_punto_venta.numero)
    segundo_punto_venta = await _crear_punto_venta_rece_verificado(
        db_session,
        test_empresa,
        usuario_id=int(test_user.id),
        numero=2,
        nombre="Punto stale 2",
        documento_emitido_en=FECHA_DOCUMENTO_RECE_TEST,
        vigente_hasta=FECHA_VIGENCIA_RECE_TEST,
        observado_en=INSTANTE_RECE_TEST,
    )
    segundo_punto_venta_id = int(segundo_punto_venta.id)
    lote, grupos = await _crear_lote_stale_moderno_intacto(
        db_session,
        test_empresa,
        grupos_payload=[
            (
                "MIXTO-001",
                _payload_lote_basico(
                    empresa_id,
                    primer_punto_venta_id,
                    fecha_fiscal,
                    razon_social="Cliente Alineado SA",
                ),
            ),
            (
                "MIXTO-002",
                _payload_lote_basico(
                    empresa_id,
                    segundo_punto_venta_id,
                    fecha_fiscal,
                    razon_social="Cliente Historia Externa SA",
                ),
            ),
        ],
        idempotency_key=(
            f"idem-stale-combinaciones-{str(segunda_combinacion_segura).lower()}"
        ),
    )
    service = LoteComprobantesService(db_session)
    llamadas: list[dict[str, int]] = []

    async def fake_preflight(**kwargs):
        llamadas.append(dict(kwargs))
        if kwargs["punto_venta_id"] == segundo_punto_venta_id:
            if not segunda_combinacion_segura:
                raise RuntimeError("segunda combinación no verificable")
            return {
                **kwargs,
                "punto_venta_numero": 2,
                "ultimo_local": 70,
                "ultimo_arca": 75,
                "proximo_local": 71,
                "proximo_arca": 76,
                "proximo_numero": 76,
                "estado": "arca_adelantada",
            }
        return {
            **kwargs,
            "punto_venta_numero": primer_punto_venta_numero,
            "ultimo_local": 70,
            "ultimo_arca": 70,
            "proximo_local": 71,
            "proximo_arca": 71,
            "proximo_numero": 71,
            "estado": "alineada",
        }

    service.facturacion_service.verificar_numeracion_segura_para_emision = (
        fake_preflight
    )

    (
        preflight_ok,
        checks,
        error,
    ) = await service._preflight_reanudar_grupos_intactos_stale(lote, grupos)

    assert llamadas == [
        {
            "empresa_id": empresa_id,
            "punto_venta_id": primer_punto_venta_id,
            "tipo_comprobante": 6,
        },
        {
            "empresa_id": empresa_id,
            "punto_venta_id": segundo_punto_venta_id,
            "tipo_comprobante": 6,
        },
    ]
    if segunda_combinacion_segura:
        assert preflight_ok is True
        assert error is None
        assert [check["estado"] for check in checks] == [
            "alineada",
            "arca_adelantada",
        ]
    else:
        assert preflight_ok is False
        assert error == "numeracion_no_verificable"
        assert [check["estado"] for check in checks] == ["alineada"]


@pytest.mark.asyncio
@pytest.mark.parametrize("anidado", [False, True])
async def test_preflight_stale_bloquea_payload_con_clave_superior_desconocida(
    db_session: AsyncSession,
    test_empresa,
    test_user,
    test_punto_venta,
    anidado,
) -> None:
    """Un payload no canónico bloquea todo el conjunto antes del preflight."""
    fecha_fiscal = date(2026, 8, 5)
    empresa_id = int(test_empresa.id)
    primer_punto_venta_id = int(test_punto_venta.id)
    segundo_punto_venta = await _crear_punto_venta_rece_verificado(
        db_session,
        test_empresa,
        usuario_id=int(test_user.id),
        numero=2,
        nombre="Punto stale payload 2",
        documento_emitido_en=FECHA_DOCUMENTO_RECE_TEST,
        vigente_hasta=FECHA_VIGENCIA_RECE_TEST,
        observado_en=INSTANTE_RECE_TEST,
    )
    segundo_punto_venta_id = int(segundo_punto_venta.id)
    payload_invalido = _payload_lote_basico(
        empresa_id,
        segundo_punto_venta_id,
        fecha_fiscal,
        razon_social="Cliente con payload no canónico SA",
    )
    destino = payload_invalido["items"][0] if anidado else payload_invalido
    destino["monedaa"] = "USD"
    lote, grupos = await _crear_lote_stale_moderno_intacto(
        db_session,
        test_empresa,
        grupos_payload=[
            (
                "MIXTO-VALIDO",
                _payload_lote_basico(
                    empresa_id,
                    primer_punto_venta_id,
                    fecha_fiscal,
                ),
            ),
            ("MIXTO-INVALIDO", payload_invalido),
        ],
        idempotency_key="idem-stale-payload-invalido",
    )
    service = LoteComprobantesService(db_session)
    llamadas_preflight = 0

    async def fail_preflight(**kwargs):
        nonlocal llamadas_preflight
        llamadas_preflight += 1
        raise AssertionError("No debe consultar numeración con payload inválido")

    service.facturacion_service.verificar_numeracion_segura_para_emision = (
        fail_preflight
    )

    (
        preflight_ok,
        checks,
        error,
    ) = await service._preflight_reanudar_grupos_intactos_stale(lote, grupos)

    assert preflight_ok is False
    assert checks == []
    assert error == "payload_fiscal_invalido"
    assert llamadas_preflight == 0


@pytest.mark.asyncio
async def test_reanudar_lote_stale_autorizado_sin_evidencia_requiere_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un estado autorizado sin evidencia fiscal no alcanza para cerrar stale."""
    fecha_fiscal = date(2026, 3, 20)
    lote = LoteComprobante(
        nombre_archivo="lote-stale-autorizado-sin-evidencia.xlsx",
        archivo_hash="hash-stale-autorizado-sin-evidencia",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        empresa_id=test_empresa.id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, comprobante])
    await db_session.flush()
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        cae=comprobante.cae,
        numero_asignado=comprobante.numero,
        comprobante_id=comprobante.id,
        mensajes_json=["Comprobante autorizado."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="autorizado",
        datos_json={},
        mensajes_json=["Comprobante autorizado."],
    )
    db_session.add_all([grupo, fila])
    await db_session.commit()
    await db_session.refresh(lote)

    service = LoteComprobantesService(db_session)
    llamadas_arca = _instalar_oraculos_stale_sin_arca(service)

    resultado = await service.procesar_lote(lote.id, test_empresa.id, reanudar=True)

    assert resultado.estado == "requiere_reconciliacion"
    assert resultado.grupos_emitidos == 1
    assert "reconciliar contra ARCA" in resultado.mensaje_resumen
    assert llamadas_arca == {"wsaa": 0, "fecomp": 0, "fecae": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "estado_intento",
    ["en_proceso", "requiere_reconciliacion"],
)
async def test_reanudar_lote_stale_autorizado_con_intento_incierto_requiere_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    estado_intento: str,
) -> None:
    """Un lote localmente autorizado no se cierra si conserva intentos inciertos."""
    fecha_fiscal = date(2026, 3, 20)
    empresa_id = int(test_empresa.id)
    punto_venta_id = int(test_punto_venta.id)
    punto_venta_numero = int(test_punto_venta.numero)
    lote = LoteComprobante(
        nombre_archivo="lote-stale-autorizado-incierto.xlsx",
        archivo_hash="hash-stale-autorizado-incierto",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        empresa_id=empresa_id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=empresa_id,
        punto_venta_id=punto_venta_id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, comprobante])
    await db_session.flush()
    lote_id = int(lote.id)
    grupo = LoteComprobanteGrupo(
        lote=lote,
        empresa_id=empresa_id,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=punto_venta_numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        cae=comprobante.cae,
        numero_asignado=comprobante.numero,
        comprobante_id=comprobante.id,
        mensajes_json=["Comprobante autorizado."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="autorizado",
        datos_json={},
        mensajes_json=["Comprobante autorizado."],
    )
    db_session.add_all([grupo, fila])
    await db_session.flush()
    grupo_id = int(grupo.id)
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=punto_venta_numero,
        numero_planificado=78,
        fecha_emision=fecha_fiscal,
        total=Decimal("1210.00"),
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        payload_hash="hash-payload-incierto",
        huella_logica="hash-huella-incierta",
        estado=estado_intento,
        operacion_id=None,
        empresa_id=empresa_id,
        punto_venta_id=punto_venta_id,
        lote_id=lote_id,
        grupo_id=grupo_id,
        ambiente=None,
        punto_venta_elegibilidad_revision_id=None,
        punto_venta_revision_fiscal=None,
        guarda_rece_id=None,
    )
    db_session.add(intento)
    assert intento.operacion_id is None
    assert intento.ambiente is None
    assert intento.punto_venta_elegibilidad_revision_id is None
    assert intento.punto_venta_revision_fiscal is None
    assert intento.guarda_rece_id is None
    await db_session.commit()

    service = LoteComprobantesService(db_session)
    llamadas_arca = _instalar_oraculos_stale_sin_arca(service)

    await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        lote_actual = await observador.get(LoteComprobante, lote_id)
    assert lote_actual is not None
    assert lote_actual.estado == "requiere_reconciliacion"
    assert lote_actual.grupos_emitidos == 1
    assert "reconciliar contra ARCA" in lote_actual.mensaje_resumen
    assert llamadas_arca == {"wsaa": 0, "fecomp": 0, "fecae": 0}


@pytest.mark.asyncio
async def test_reanudar_lote_no_vincula_comprobante_sin_intento_del_grupo(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
):
    """Un comprobante parecido pero sin intento del grupo no cierra el lote."""
    fecha_fiscal = date(2026, 3, 20)
    empresa_id = int(test_empresa.id)
    punto_venta_id = int(test_punto_venta.id)
    punto_venta_numero = int(test_punto_venta.numero)
    emitir_request = {
        "empresa_id": empresa_id,
        "punto_venta_id": punto_venta_id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
        "razon_social": "Cliente Lote SA",
        "condicion_iva": "RI",
        "domicilio": "Av. Siempre Viva 123",
        "moneda": "PES",
        "cotizacion": "1",
        "guardar_cliente": False,
        "items": [
            {
                "descripcion": "Servicio mensual",
                "cantidad": "1",
                "unidad": "unidad",
                "precio_unitario": "1000",
                "iva_porcentaje": "21",
            }
        ],
    }
    lote = LoteComprobante(
        nombre_archivo="lote-reanudar-sin-intento.xlsx",
        archivo_hash="hash-reanudar-sin-intento",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=empresa_id,
        metadata_json={
            "opciones_concepto": {"concepto_modo": "archivo"},
            "opciones_descripcion_item": {"descripcion_item_modo": "archivo"},
        },
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        empresa_id=empresa_id,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=punto_venta_numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        payload_json=emitir_request,
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="validado",
        datos_json={},
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=empresa_id,
        punto_venta_id=punto_venta_id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, grupo, fila, comprobante])
    await db_session.flush()
    lote_id = int(lote.id)
    assert grupo.ambiente is None
    assert grupo.punto_venta_elegibilidad_revision_id is None
    assert grupo.punto_venta_revision_fiscal is None
    await db_session.commit()

    service = LoteComprobantesService(db_session)
    llamadas_arca = _instalar_oraculos_stale_sin_arca(service)

    await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        detalle = await LoteComprobantesService(observador).obtener_lote(
            lote_id,
            empresa_id,
        )
    assert detalle.estado == "requiere_reconciliacion"
    assert detalle.grupos[0].estado == "requiere_reconciliacion"
    assert detalle.grupos[0].comprobante_id is None
    assert detalle.grupos[0].numero_asignado is None
    assert "reconciliar" in detalle.mensaje_resumen
    assert llamadas_arca == {"wsaa": 0, "fecomp": 0, "fecae": 0}


@pytest.mark.asyncio
async def test_reanudar_lote_no_reconcilia_intentos_autorizados_duplicados(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Múltiples intentos autorizados del mismo grupo requieren auditoría."""
    fecha_fiscal = date(2026, 3, 20)
    empresa_id = int(test_empresa.id)
    punto_venta_id = int(test_punto_venta.id)
    punto_venta_numero = int(test_punto_venta.numero)
    emitir_request = {
        "empresa_id": empresa_id,
        "punto_venta_id": punto_venta_id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
        "razon_social": "Cliente Lote SA",
        "condicion_iva": "RI",
        "domicilio": "Av. Siempre Viva 123",
        "moneda": "PES",
        "cotizacion": "1",
        "guardar_cliente": False,
        "items": [
            {
                "descripcion": "Servicio mensual",
                "cantidad": "1",
                "unidad": "unidad",
                "precio_unitario": "1000",
                "iva_porcentaje": "21",
            }
        ],
    }
    lote = LoteComprobante(
        nombre_archivo="lote-reanudar-intentos-duplicados.xlsx",
        archivo_hash="hash-reanudar-intentos-duplicados",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=empresa_id,
        metadata_json={
            "opciones_concepto": {"concepto_modo": "archivo"},
            "opciones_descripcion_item": {"descripcion_item_modo": "archivo"},
        },
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        empresa_id=empresa_id,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=punto_venta_numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        payload_json=emitir_request,
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="validado",
        datos_json={},
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    comprobante_1 = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=empresa_id,
        punto_venta_id=punto_venta_id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante_2 = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=78,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL_ALT,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=empresa_id,
        punto_venta_id=punto_venta_id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, grupo, fila, comprobante_1, comprobante_2])
    await db_session.flush()
    lote_id = int(lote.id)
    grupo_id = int(grupo.id)
    db_session.add_all(
        [
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=punto_venta_numero,
                numero_planificado=comprobante_1.numero,
                fecha_emision=fecha_fiscal,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash="hash-payload-grupo-001-a",
                huella_logica="hash-logica-grupo-001",
                cae=comprobante_1.cae,
                cae_vencimiento=comprobante_1.cae_vencimiento,
                estado="autorizado",
                operacion_id=None,
                empresa_id=empresa_id,
                punto_venta_id=punto_venta_id,
                comprobante_id=comprobante_1.id,
                lote_id=lote_id,
                grupo_id=grupo_id,
                ambiente=None,
                punto_venta_elegibilidad_revision_id=None,
                punto_venta_revision_fiscal=None,
                guarda_rece_id=None,
            ),
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=punto_venta_numero,
                numero_planificado=comprobante_2.numero,
                fecha_emision=fecha_fiscal,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash="hash-payload-grupo-001-b",
                huella_logica="hash-logica-grupo-001-b",
                cae=comprobante_2.cae,
                cae_vencimiento=comprobante_2.cae_vencimiento,
                estado="autorizado",
                operacion_id=None,
                empresa_id=empresa_id,
                punto_venta_id=punto_venta_id,
                comprobante_id=comprobante_2.id,
                lote_id=lote_id,
                grupo_id=grupo_id,
                ambiente=None,
                punto_venta_elegibilidad_revision_id=None,
                punto_venta_revision_fiscal=None,
                guarda_rece_id=None,
            ),
        ]
    )
    await db_session.commit()

    service = LoteComprobantesService(db_session)
    llamadas_arca = _instalar_oraculos_stale_sin_arca(service)

    await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        detalle = await LoteComprobantesService(observador).obtener_lote(
            lote_id,
            empresa_id,
        )
    assert detalle.estado == "requiere_reconciliacion"
    assert detalle.grupos[0].estado == "requiere_reconciliacion"
    assert detalle.grupos[0].comprobante_id is None
    assert detalle.grupos[0].numero_asignado is None
    assert "reconciliar" in detalle.mensaje_resumen
    assert llamadas_arca == {"wsaa": 0, "fecomp": 0, "fecae": 0}


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_intento_incierto_del_grupo(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un intento incierto del mismo grupo bloquea el cierre local automático."""
    fecha_fiscal = date(2026, 3, 20)
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
        "razon_social": "Cliente Lote SA",
        "condicion_iva": "RI",
        "domicilio": "Av. Siempre Viva 123",
        "moneda": "PES",
        "cotizacion": "1",
        "guardar_cliente": False,
        "items": [
            {
                "descripcion": "Servicio mensual",
                "cantidad": "1",
                "unidad": "unidad",
                "precio_unitario": "1000",
                "iva_porcentaje": "21",
            }
        ],
    }
    request = EmitirComprobanteRequest.model_validate(emitir_request)
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    lote = LoteComprobante(
        nombre_archivo="lote-intento-incierto.xlsx",
        archivo_hash="hash-intento-incierto",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        payload_json=emitir_request,
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]
    db_session.add_all([lote, grupo, comprobante])
    await db_session.flush()
    db_session.add_all(
        [
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=test_punto_venta.numero,
                numero_planificado=77,
                fecha_emision=fecha_fiscal,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash=payload_hash,
                huella_logica=huella,
                cae=comprobante.cae,
                cae_vencimiento=comprobante.cae_vencimiento,
                estado="autorizado",
                empresa_id=test_empresa.id,
                punto_venta_id=test_punto_venta.id,
                comprobante_id=comprobante.id,
                lote_id=lote.id,
                grupo_id=grupo.id,
            ),
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=test_punto_venta.numero,
                numero_planificado=78,
                fecha_emision=fecha_fiscal,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash=payload_hash,
                huella_logica=huella,
                estado="en_proceso",
                empresa_id=test_empresa.id,
                punto_venta_id=test_punto_venta.id,
                lote_id=lote.id,
                grupo_id=grupo.id,
            ),
        ]
    )
    await db_session.commit()

    assert (
        await LoteComprobantesService(
            db_session
        )._reconciliar_grupo_autorizado_existente(grupo, request)
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_payload_drift(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """La reconciliación local exige que la huella fiscal completa coincida."""
    request_original = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": "2026-03-20",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
            "razon_social": "Cliente Lote SA",
            "condicion_iva": "RI",
            "domicilio": "Av. Siempre Viva 123",
            "moneda": "PES",
            "cotizacion": "1",
            "guardar_cliente": False,
            "items": [
                {
                    "descripcion": "Servicio mensual original",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "1000",
                    "iva_porcentaje": "21",
                }
            ],
        }
    )
    request_drift = request_original.model_copy(deep=True)
    request_drift.items[0].descripcion = "Servicio mensual cambiado"
    payload_hash, huella = _hashes_fiscales_request(
        request_original,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request_original.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request_original.tipo_documento,
        receptor_numero_documento=request_original.numero_documento,
        receptor_razon_social=request_original.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=request_original.fecha_emision,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request_original.tipo_documento,
        receptor_numero_documento=request_original.numero_documento,
        receptor_razon_social=request_original.razon_social,
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual original",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request_drift,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_nota_usa_huella_del_intento_con_asociado(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """La huella autorizada del intento conserva el asociado fiscal de la nota."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 13,
            "concepto": 2,
            "fecha_emision": "2026-06-01",
            "fecha_servicio_desde": "2026-06-01",
            "fecha_servicio_hasta": "2026-06-01",
            "fecha_vto_pago": "2026-06-10",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 99,
            "numero_documento": "0",
            "razon_social": "A CONSUMIDOR FINAL",
            "condicion_iva": "CF",
            "moneda": "PES",
            "cotizacion": "1",
            "guardar_cliente": False,
            "comprobantes_asociados": [
                {
                    "tipo_comprobante": 11,
                    "punto_venta": test_punto_venta.numero,
                    "numero": 1645,
                    "fecha": "2026-04-30",
                    "cuit": test_empresa.cuit,
                }
            ],
            "items": [
                {
                    "descripcion": "Anulación por duplicado",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "59500",
                    "iva_porcentaje": "0",
                }
            ],
        }
    )
    total = Decimal("59500.00")
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        total,
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=request.tipo_comprobante,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=27,
        fecha_emision=request.fecha_emision,
        total=total,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 6, 11),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=request.tipo_comprobante,
        concepto=request.concepto,
        numero=27,
        fecha_emision=request.fecha_emision,
        fecha_servicio_desde=request.fecha_servicio_desde,
        fecha_servicio_hasta=request.fecha_servicio_hasta,
        fecha_vto_pago=request.fecha_vto_pago,
        fecha_vencimiento=request.fecha_vto_pago,
        subtotal=total,
        descuento=Decimal("0.00"),
        iva_21=Decimal("0.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=total,
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva="CF",
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Anulación por duplicado",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("59500"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("0"),
            subtotal=total,
            orden=0,
        )
    ]

    assert LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
        intento=intento,
        comprobante=comprobante,
        request=request,
        total=total,
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_snapshot_comprobante_distinto(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """El comprobante local debe conservar el snapshot completo del request."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": "2026-03-20",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
            "razon_social": "Cliente Lote SA",
            "condicion_iva": "RI",
            "domicilio": "Av. Siempre Viva 123",
            "moneda": "PES",
            "cotizacion": "1",
            "guardar_cliente": False,
            "items": [
                {
                    "descripcion": "Servicio mensual",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "1000",
                    "iva_porcentaje": "21",
                }
            ],
        }
    )
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=request.fecha_emision,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva=request.condicion_iva,
        receptor_domicilio=request.domicilio,
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="hora",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_cae_vencimiento_distinto(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """El vencimiento de CAE local debe coincidir con el intento autorizado."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": "2026-03-20",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
            "razon_social": "Cliente Lote SA",
            "condicion_iva": "RI",
            "domicilio": "Av. Siempre Viva 123",
            "moneda": "PES",
            "cotizacion": "1",
            "guardar_cliente": False,
            "items": [
                {
                    "descripcion": "Servicio mensual",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "1000",
                    "iva_porcentaje": "21",
                }
            ],
        }
    )
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=request.fecha_emision,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=date(2026, 5, 27),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva=request.condicion_iva,
        receptor_domicilio=request.domicilio,
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_fechas_servicio_distintas(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Las fechas fiscales de servicio deben coincidir con el request."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 2,
            "fecha_emision": "2026-03-20",
            "fecha_servicio_desde": "2026-03-01",
            "fecha_servicio_hasta": "2026-03-31",
            "fecha_vto_pago": "2026-04-10",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
            "razon_social": "Cliente Lote SA",
            "condicion_iva": "RI",
            "domicilio": "Av. Siempre Viva 123",
            "moneda": "PES",
            "cotizacion": "1",
            "guardar_cliente": False,
            "items": [
                {
                    "descripcion": "Servicio mensual",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "1000",
                    "iva_porcentaje": "21",
                }
            ],
        }
    )
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=2,
        numero=77,
        fecha_emision=request.fecha_emision,
        fecha_servicio_desde=date(2026, 3, 2),
        fecha_servicio_hasta=request.fecha_servicio_hasta,
        fecha_vto_pago=request.fecha_vto_pago,
        fecha_vencimiento=request.fecha_vto_pago,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva=request.condicion_iva,
        receptor_domicilio=request.domicilio,
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_comprobante_con_tipo_doc_distinto(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """La reconciliación local exige identidad fiscal completa del receptor."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": "2026-03-20",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
            "razon_social": "Cliente Lote SA",
            "condicion_iva": "RI",
            "domicilio": "Av. Siempre Viva 123",
            "moneda": "PES",
            "cotizacion": "1",
            "guardar_cliente": False,
            "items": [
                {
                    "descripcion": "Servicio mensual",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "1000",
                    "iva_porcentaje": "21",
                }
            ],
        }
    )
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=request.fecha_emision,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=96,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_procesar_lote_exige_confirmacion_fecha_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe procesar lotes por API sin confirmacion fiscal final."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-sin-confirmacion.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, "X-Idempotency-Key": "idem-lote-sin-confirmacion"},
    )

    assert response.status_code == 400
    detalle = response.json()["detail"]
    assert "confirmar la fecha fiscal exacta" in detalle["mensaje"]
    assert FECHA_FISCAL_CONTROLADA_PF19B.strftime("%d/%m/%y") in detalle["mensaje"]
    assert "0001" in detalle["mensaje"]
    assert "XX/XX/XX" not in detalle["mensaje"]


@pytest.mark.asyncio
async def test_procesar_lote_exige_idempotency_key(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe procesar un lote confirmado sin clave de idempotencia."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-sin-idem.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={
            **auth_headers,
            "X-Confirmacion-Fecha-Fiscal": (
                f"fechas={FECHA_FISCAL_CONTROLADA_PF19B.isoformat()};puntos_venta=1"
            ),
        },
    )

    assert response.status_code == 400
    assert "X-Idempotency-Key" in response.json()["detail"]["mensaje"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "estado_lote",
    [
        "en_cola",
        "procesando",
        "requiere_reconciliacion",
        "completado",
        "cerrado_reconciliado",
        "cerrado_con_descartes",
    ],
)
async def test_lote_activo_o_incierto_no_admite_reintento_manual(
    db_session: AsyncSession,
    estado_lote: str,
) -> None:
    """El worker y el reintento manual no pueden resolver el mismo lote."""
    lote = SimpleNamespace(estado=estado_lote)
    service = LoteComprobantesService(db_session)

    with pytest.raises(LoteComprobanteError):
        service._validar_lote_resoluble(lote)


@pytest.mark.asyncio
async def test_tomar_lote_para_procesamiento_es_atomico(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote ya tomado no puede volver a tomarse para emisión."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-lock.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    service = LoteComprobantesService(db_session)

    await service._tomar_lote_para_procesamiento(
        lote_id=lote_id,
        empresa_id=test_empresa.id,
        procesamiento_async=False,
        modo_procesamiento="sincronico",
    )
    await db_session.commit()

    with pytest.raises(LoteComprobanteError, match="ya está siendo procesado"):
        await service._tomar_lote_para_procesamiento(
            lote_id=lote_id,
            empresa_id=test_empresa.id,
            procesamiento_async=False,
            modo_procesamiento="sincronico",
        )


@pytest.mark.asyncio
async def test_procesar_background_no_reencola_lote_en_proceso(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote en procesamiento no debe volver a estado en_cola."""
    test_certificado.ambiente = settings.arca_env
    empresa_id = int(test_empresa.id)
    worker_iniciado = False

    def fake_ensure_worker(_app):
        nonlocal worker_iniciado
        worker_iniciado = True
        return True

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        fake_ensure_worker,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-procesando-background.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    idempotency_key = "idem-lote-procesando-background"
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=idempotency_key,
    )
    encolado = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **headers_procesar},
    )
    assert encolado.status_code == 200, encolado.text

    db_session.expire_all()
    lote = await db_session.get(LoteComprobante, lote_id)
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == idempotency_key
        )
    )
    assert lote is not None
    assert operacion is not None
    operacion_id = int(operacion.id)
    material_rece = deepcopy(lote.metadata_json["pf19b_rece_material"])
    assert lote.estado == "en_cola"
    assert lote.metadata_json["operacion_idempotente_id"] == operacion_id
    assert operacion.estado == "en_proceso"
    assert operacion.response_json["en_progreso"] is True
    assert (
        operacion.response_json["lote"]["metadata_json"]["pf19b_rece_material"]
        == material_rece
    )

    service = LoteComprobantesService(db_session)
    await service._tomar_lote_para_procesamiento(
        lote_id=lote_id,
        empresa_id=empresa_id,
        procesamiento_async=True,
        modo_procesamiento="background",
    )
    await db_session.commit()
    db_session.expire_all()
    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    await service._guardar_respuesta_operacion_background(lote, operacion_id)
    await db_session.commit()

    db_session.expire_all()
    operacion = await db_session.get(OperacionIdempotente, operacion_id)
    assert operacion is not None
    assert operacion.estado == "en_proceso"
    assert operacion.response_json["en_progreso"] is True
    assert operacion.response_json["lote"]["estado"] == "procesando"
    assert (
        operacion.response_json["lote"]["metadata_json"]["pf19b_rece_material"]
        == material_rece
    )
    worker_iniciado = False

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is True
    assert data["lote"]["estado"] == "procesando"
    assert data["mensaje"] == "Procesando comprobantes..."
    assert worker_iniciado is False


@pytest.mark.asyncio
async def test_tomar_lote_no_reanuda_procesando_stale(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote procesando vencido no debe volver a tomarse para emitir."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-procesando-stale.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    service = LoteComprobantesService(db_session)

    await service._tomar_lote_para_procesamiento(
        lote_id=lote_id,
        empresa_id=test_empresa.id,
        procesamiento_async=True,
        modo_procesamiento="background",
    )
    await db_session.commit()

    with pytest.raises(LoteComprobanteError, match="ya está siendo procesado"):
        await service._tomar_lote_para_procesamiento(
            lote_id=lote_id,
            empresa_id=test_empresa.id,
            procesamiento_async=True,
            modo_procesamiento="background",
            reanudar=True,
        )

    lote = await db_session.get(LoteComprobante, lote_id)
    lote.updated_at = datetime.utcnow() - timedelta(
        minutes=settings.batch_processing_stale_minutes + 1
    )
    await db_session.commit()

    with pytest.raises(LoteComprobanteError, match="ya está siendo procesado"):
        await service._tomar_lote_para_procesamiento(
            lote_id=lote_id,
            empresa_id=test_empresa.id,
            procesamiento_async=True,
            modo_procesamiento="background",
            reanudar=True,
        )


@pytest.mark.asyncio
async def test_procesar_lote_procesando_stale_bloquea_y_preserva_intactos_sin_emitir(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El worker bloquea si no puede comprobar una reanudación segura."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "batch_sync_limit", 0)
    llamadas_emitir = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas_emitir
        llamadas_emitir += 1
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=432,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=987,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL_36,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-procesando-stale-worker.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    service = LoteComprobantesService(db_session)

    async def fail_preflight(**_kwargs):
        raise RuntimeError(
            "preflight ARCA no disponible en C:\\privado\\certificado.key"
        )

    service.facturacion_service.verificar_numeracion_segura_para_emision = (
        fail_preflight
    )

    await service._tomar_lote_para_procesamiento(
        lote_id=lote_id,
        empresa_id=test_empresa.id,
        procesamiento_async=True,
        modo_procesamiento="background",
    )
    lote = await db_session.get(LoteComprobante, lote_id)
    lote.updated_at = datetime.utcnow() - timedelta(
        minutes=settings.batch_processing_stale_minutes + 1
    )
    await db_session.commit()

    lote = await service.procesar_lote(lote_id, test_empresa.id, reanudar=True)

    assert lote.estado == "requiere_reconciliacion"
    assert lote.grupos_validos == 0
    assert lote.grupos_emitidos == 0
    assert llamadas_emitir == 0
    assert "reconciliar contra ARCA" in lote.mensaje_resumen
    grupo = (
        (
            await db_session.execute(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id
                )
            )
        )
        .scalars()
        .one()
    )
    assert grupo.estado == "requiere_reconciliacion"
    assert grupo.cae is None
    assert grupo.numero_asignado is None
    assert grupo.comprobante_id is None
    eventos = (
        (
            await db_session.execute(
                select(LoteComprobanteEvento).where(
                    LoteComprobanteEvento.lote_id == lote_id,
                    LoteComprobanteEvento.accion == "bloqueo_operativo_no_reemitir",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].metadata_json["estado_nuevo"] == "requiere_reconciliacion"
    assert eventos[0].metadata_json["grupos_marcados_reconciliacion"] == 1
    assert eventos[0].metadata_json["grupos_intactos_preservados"] == 1
    assert eventos[0].metadata_json["preflight_error"] == (
        "operacion_o_snapshot_rece_legacy"
    )
    metadata_serializada = str(
        {
            "lote": lote.metadata_json,
            "evento": eventos[0].metadata_json,
        }
    )
    assert "preflight ARCA no disponible" not in metadata_serializada
    assert "certificado.key" not in metadata_serializada


@pytest.mark.asyncio
async def test_worker_usa_factory_dedicada_e_instrumenta_sin_mutar_lote(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """El ciclo usa conexiones worker y guarda métricas solo en memoria."""
    monkeypatch.setattr(settings, "batch_worker_enabled", True)
    lote = LoteComprobante(
        nombre_archivo="lote-worker-instrumentado.xlsx",
        archivo_hash="hash-lote-worker-instrumentado",
        estado="en_cola",
        modo_procesamiento="background",
        procesamiento_async=True,
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    db_session.add(lote)
    await db_session.commit()
    await db_session.refresh(lote)
    updated_at_antes = lote.updated_at

    class SessionFactory:
        aperturas = 0

        async def __aenter__(self):
            SessionFactory.aperturas += 1
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    roles: list[str] = []
    reanudar_recibido: list[bool] = []

    async def fake_acquire(session: AsyncSession, role: str) -> None:
        assert session is db_session
        roles.append(role)

    async def fake_procesar(
        self: LoteComprobantesService,
        lote_id: int,
        empresa_id: int,
        **kwargs,
    ) -> LoteComprobante:
        reanudar_recibido.append(bool(kwargs.get("reanudar")))
        return await self.obtener_lote_resumen(lote_id, empresa_id)

    monkeypatch.setattr(
        "app.services.lote_worker.WorkerSessionLocal",
        SessionFactory,
    )
    monkeypatch.setattr(
        "app.services.lote_worker.acquire_database_connection",
        fake_acquire,
    )
    monkeypatch.setattr(
        LoteComprobantesService,
        "procesar_lote",
        fake_procesar,
    )

    worker = LoteWorker()
    resultado = await worker.procesar_pendientes()
    app = SimpleNamespace(
        state=SimpleNamespace(
            lote_worker=worker,
            lote_worker_task=SimpleNamespace(done=lambda: False),
        )
    )
    runtime = get_lote_worker_status(app)

    assert SessionFactory.aperturas == 3
    assert roles == ["worker", "worker", "worker"]
    assert reanudar_recibido == [True]
    assert resultado.stale_detectados == 0
    assert resultado.lotes_en_cola_detectados == 1
    assert resultado.lotes_procesados == 1
    assert resultado.tuvo_error is False
    assert runtime["estado"] == "esperando"
    assert runtime["ocupado"] is False
    assert runtime["ultimo_resultado"] == "exitoso"
    assert runtime["ciclo_iniciado_at"] is not None
    assert runtime["ciclo_finalizado_at"] is not None
    assert runtime["ultima_duracion_ms"] is not None
    assert runtime["stale_detectados_ultimo_ciclo"] == 0
    assert runtime["lotes_en_cola_ultimo_ciclo"] == 1
    assert runtime["lotes_procesados_ultimo_ciclo"] == 1
    assert not any("mensaje" in key for key in runtime)
    await db_session.refresh(lote)
    assert lote.updated_at == updated_at_antes


@pytest.mark.asyncio
async def test_lote_encolado_continua_tras_revocacion_y_bloquea_acciones_nuevas(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_empresa,
    test_user,
) -> None:
    """La autorización aceptada por el worker es durable, no una sesión viva."""
    lote = LoteComprobante(
        nombre_archivo="lote-revocacion-sintetico.xlsx",
        archivo_hash="hash-lote-revocacion-sintetico",
        estado="en_cola",
        modo_procesamiento="background",
        procesamiento_async=True,
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        usuario_id=test_user.id,
    )
    db_session.add(lote)
    await db_session.commit()

    await db_session.execute(
        delete(UsuarioEmisorAcceso).where(
            UsuarioEmisorAcceso.usuario_id == test_user.id,
            UsuarioEmisorAcceso.empresa_id == test_empresa.id,
        )
    )
    test_user.empresa_id = None
    await db_session.commit()

    nueva_accion = await client.get("/api/clientes", headers=auth_headers)
    assert nueva_accion.status_code == 403

    class SessionFactory:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    lotes_procesados: list[int] = []

    async def fake_acquire(session: AsyncSession, role: str) -> None:
        assert session is db_session
        assert role == "worker"

    async def fake_procesar(
        self: LoteComprobantesService,
        lote_id: int,
        empresa_id: int,
        **kwargs,
    ) -> LoteComprobante:
        assert empresa_id == test_empresa.id
        assert kwargs.get("reanudar") is True
        lotes_procesados.append(lote_id)
        return await self.obtener_lote_resumen(lote_id, empresa_id)

    monkeypatch.setattr("app.services.lote_worker.WorkerSessionLocal", SessionFactory)
    monkeypatch.setattr(
        "app.services.lote_worker.acquire_database_connection", fake_acquire
    )
    monkeypatch.setattr(LoteComprobantesService, "procesar_lote", fake_procesar)

    resultado = await LoteWorker().procesar_pendientes()

    assert lotes_procesados == [lote.id]
    assert resultado.lotes_procesados == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyTimeoutError, OperationalError],
    ids=["timeout", "operational"],
)
async def test_worker_corta_ciclo_tras_db_temporal_del_primer_lote(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    error_type: type[Exception],
) -> None:
    """El worker no avanza al segundo lote si la base falla en el primero."""

    class SessionFactory:
        """Reutiliza la sesión aislada de pruebas como sesión worker."""

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    lotes = [
        LoteComprobante(
            nombre_archivo=f"lote-worker-db-{indice}.xlsx",
            archivo_hash=f"hash-lote-worker-db-{indice}",
            estado="en_cola",
            modo_procesamiento="background",
            procesamiento_async=True,
            total_filas=1,
            total_grupos=1,
            grupos_validos=1,
            empresa_id=test_empresa.id,
        )
        for indice in (1, 2)
    ]
    db_session.add_all(lotes)
    await db_session.flush()
    operacion_worker = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=None,
        lote_id=lotes[0].id,
        idempotency_key="idem-worker-pre-arca",
        tipo_operacion="procesar_lote",
        payload_hash="payload-worker-pre-arca",
        estado="en_proceso",
    )
    db_session.add(operacion_worker)
    await db_session.commit()
    lote_ids = [lote.id for lote in lotes]
    operacion_worker_id = operacion_worker.id

    procesados: list[int] = []

    async def fake_acquire(session: AsyncSession, role: str) -> None:
        assert session is db_session
        assert role == "worker"

    async def fail_primer_lote(self, lote_id, empresa_id, **kwargs):
        procesados.append(lote_id)
        raise _crear_error_db_temporal(error_type)

    monkeypatch.setattr("app.services.lote_worker.WorkerSessionLocal", SessionFactory)
    monkeypatch.setattr(
        "app.services.lote_worker.acquire_database_connection",
        fake_acquire,
    )
    monkeypatch.setattr(
        LoteComprobantesService,
        "procesar_lote",
        fail_primer_lote,
    )

    resultado = await LoteWorker().procesar_pendientes()

    assert procesados == [lote_ids[0]]
    assert resultado.lotes_en_cola_detectados == 1
    assert resultado.lotes_procesados == 0
    assert resultado.tuvo_error is True
    db_session.expire_all()
    primer_lote = await db_session.get(LoteComprobante, lote_ids[0])
    segundo_lote = await db_session.get(LoteComprobante, lote_ids[1])
    operacion_actual = await db_session.get(
        OperacionIdempotente,
        operacion_worker_id,
    )
    assert primer_lote is not None
    assert segundo_lote is not None
    assert operacion_actual is not None
    assert primer_lote.estado == "en_cola"
    assert segundo_lote.estado == "en_cola"
    assert operacion_actual.estado == "en_proceso"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutacion",
    ["json_null", "progreso_adulterado", "terminal"],
)
async def test_worker_rechaza_ownership_invalido_antes_de_consultar_arca(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    mutacion: str,
) -> None:
    """Ownership inválido deja el lote en cola y corta toda capacidad/FECAE."""
    empresa_id = int(inspect(test_empresa).identity[0])
    llamadas_wsaa = 0
    llamadas_fecomp = 0
    llamadas_fecae = 0

    async def fake_ticket(empresa, certificado):
        nonlocal llamadas_wsaa
        llamadas_wsaa += 1
        raise AssertionError("No debe solicitar WSAA sin ownership worker")

    class FakeWSFEClient:
        """Hace observables FECompTotXRequest y FECAE si se cruza la compuerta."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva sin abrir red."""

        async def fe_comp_tot_x_request(self):
            """Registra una consulta de capacidad indebida."""
            nonlocal llamadas_fecomp
            llamadas_fecomp += 1
            return 1

        async def fe_cae_solicitar(self, arca_request):
            """Registra una solicitud FECAE indebida."""
            nonlocal llamadas_fecae
            llamadas_fecae += 1
            raise AssertionError("No debe solicitar FECAE sin ownership worker")

    async def fail_emitir(request, **kwargs):
        nonlocal llamadas_fecae
        llamadas_fecae += 1
        raise AssertionError("No debe solicitar FECAE sin ownership worker")

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: True,
    )
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        FakeWSFEClient,
    )
    test_certificado.ambiente = settings.arca_env
    await db_session.commit()
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo=f"lote-worker-ownership-{mutacion}.xlsx",
    )
    idempotency_key = f"idem-worker-ownership-{mutacion}"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=idempotency_key,
    )
    encolado = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **headers},
    )
    assert encolado.status_code == 200, encolado.text
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == idempotency_key
        )
    )
    assert operacion is not None
    if mutacion == "json_null":
        operacion.response_json = JSON.NULL
    elif mutacion == "progreso_adulterado":
        respuesta = deepcopy(operacion.response_json)
        respuesta["lote"]["metadata_json"]["pf19b_rece_material"]["grupos_hash"] = (
            "0" * 64
        )
        operacion.response_json = respuesta
    else:
        operacion.estado = "finalizado"
    await db_session.commit()

    service = LoteComprobantesService(db_session)
    monkeypatch.setattr(
        service.facturacion_service, "_obtener_ticket_acceso", fake_ticket
    )
    monkeypatch.setattr(service.facturacion_service, "emitir_comprobante", fail_emitir)

    with pytest.raises(LoteComprobanteError, match="perdió el ownership"):
        await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        lote = await observador.get(LoteComprobante, lote_id)
        assert lote is not None
        assert lote.estado == "en_cola"
        assert lote.started_at is None
    assert llamadas_wsaa == 0
    assert llamadas_fecomp == 0
    assert llamadas_fecae == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mutacion", ["progreso_adulterado", "terminal"])
async def test_worker_revalida_ownership_post_claim_antes_de_capacidad(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
    mutacion: str,
) -> None:
    """Una segunda sesión que cambia la operación post-claim corta toda ARCA."""
    empresa_id = int(inspect(test_empresa).identity[0])
    llamadas_wsaa = 0
    llamadas_fecomp = 0
    llamadas_fecae = 0

    class FakeWSFEClient:
        """Hace observables capacidad y FECAE después del segundo gate."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva sin abrir red."""

        async def fe_comp_tot_x_request(self):
            """Registra una consulta de capacidad indebida."""
            nonlocal llamadas_fecomp
            llamadas_fecomp += 1
            return 1

        async def fe_cae_solicitar(self, arca_request):
            """Registra una solicitud FECAE indebida."""
            nonlocal llamadas_fecae
            llamadas_fecae += 1
            raise AssertionError("No debe solicitar FECAE tras perder ownership")

    async def fake_ticket(empresa, certificado):
        nonlocal llamadas_wsaa
        llamadas_wsaa += 1
        raise AssertionError("No debe solicitar WSAA tras perder ownership")

    async def fail_emitir(request, **kwargs):
        nonlocal llamadas_fecae
        llamadas_fecae += 1
        raise AssertionError("No debe emitir tras perder ownership")

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: True,
    )
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        FakeWSFEClient,
    )
    test_certificado.ambiente = settings.arca_env
    await db_session.commit()
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo=f"lote-worker-post-claim-{mutacion}.xlsx",
    )
    key = f"idem-worker-post-claim-{mutacion}"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=key,
    )
    encolado = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **headers},
    )
    assert encolado.status_code == 200, encolado.text
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(OperacionIdempotente.idempotency_key == key)
    )
    assert operacion is not None
    operacion_id = int(operacion.id)
    commit_original = db_session.commit
    mutada = False
    commits = 0

    async def commit_claim_con_carrera() -> None:
        """Publica el claim y luego muta ownership desde otra sesión."""
        nonlocal commits, mutada
        await commit_original()
        commits += 1
        # El primer commit pertenece ahora al coordinador PF-13. La carrera
        # buscada debe ocurrir después del commit que toma el lote.
        if mutada or commits < 2:
            return
        mutada = True
        async with AsyncSession(
            bind=db_session.bind,
            expire_on_commit=False,
        ) as competidora:
            operacion_competidora = await competidora.get(
                OperacionIdempotente,
                operacion_id,
            )
            assert operacion_competidora is not None
            respuesta = deepcopy(operacion_competidora.response_json)
            if mutacion == "terminal":
                operacion_competidora.estado = "finalizado"
                respuesta["en_progreso"] = False
                respuesta["mensaje"] = "Resultado terminal sintético"
            else:
                respuesta["lote"]["metadata_json"]["pf19b_rece_material"][
                    "grupos_hash"
                ] = ("f" * 64)
            operacion_competidora.response_json = respuesta
            await competidora.commit()

    service = LoteComprobantesService(db_session)
    monkeypatch.setattr(db_session, "commit", commit_claim_con_carrera)
    monkeypatch.setattr(
        service.facturacion_service, "_obtener_ticket_acceso", fake_ticket
    )
    monkeypatch.setattr(service.facturacion_service, "emitir_comprobante", fail_emitir)

    with pytest.raises(LoteComprobanteError, match="perdió el ownership"):
        await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    assert mutada is True
    assert commits >= 2
    assert llamadas_wsaa == 0
    assert llamadas_fecomp == 0
    assert llamadas_fecae == 0
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        lote = await observador.get(LoteComprobante, lote_id)
        grupos = list(
            (
                await observador.scalars(
                    select(LoteComprobanteGrupo).where(
                        LoteComprobanteGrupo.lote_id == lote_id
                    )
                )
            ).all()
        )
        filas = list(
            (
                await observador.scalars(
                    select(LoteComprobanteFila).where(
                        LoteComprobanteFila.lote_id == lote_id
                    )
                )
            ).all()
        )
        operacion_visible = await observador.get(
            OperacionIdempotente,
            operacion_id,
        )
        assert lote is not None
        assert operacion_visible is not None
        assert lote.estado == "requiere_reconciliacion"
        assert {grupo.estado for grupo in grupos} == {"requiere_reconciliacion"}
        assert {fila.estado for fila in filas} == {"requiere_reconciliacion"}
        if mutacion == "terminal":
            assert operacion_visible.estado == "finalizado"
        else:
            assert operacion_visible.estado == "en_proceso"


@pytest.mark.asyncio
async def test_worker_background_recupera_guarda_pre_arca_con_ownership_durable(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """Endpoint y worker cierran una guarda pre-ARCA sin publicar ownership parcial."""

    class SessionFactory:
        """Reutiliza la sesión del test en todos los ciclos del worker."""

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeWSFEClient:
        """Permite lecturas de numeración y hace observable cualquier FECAE."""

        llamadas_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva sin abrir red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene estable el doble preflight seguro de numeración."""
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Registra una violación: este caso nunca debe llegar a FECAE."""
            FakeWSFEClient.llamadas_fecae += 1
            raise AssertionError("No debe solicitar FECAE después del fallo del CAS")

    async def fake_acquire(session: AsyncSession, role: str) -> None:
        assert session is db_session
        assert role == "worker"

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    async def fallar_cas_pre_fecae(self, **kwargs):
        raise SQLAlchemyTimeoutError()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: True,
    )
    monkeypatch.setattr("app.services.lote_worker.WorkerSessionLocal", SessionFactory)
    monkeypatch.setattr(
        "app.services.lote_worker.acquire_database_connection",
        fake_acquire,
    )
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
        "marcar_arca_iniciada",
        fallar_cas_pre_fecae,
    )

    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-worker-ownership-durable.xlsx",
    )
    confirmacion = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="idem-worker-ownership-durable",
    )
    encolado = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **confirmacion},
    )
    assert encolado.status_code == 200, encolado.text
    assert encolado.json()["en_progreso"] is True

    resultado = await LoteWorker().procesar_pendientes()

    assert resultado.tuvo_error is True
    assert resultado.lotes_procesados == 0
    assert FakeWSFEClient.llamadas_fecae == 0
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        lote = await observador.get(LoteComprobante, lote_id)
        operacion = await observador.scalar(
            select(OperacionIdempotente).where(
                OperacionIdempotente.idempotency_key == "idem-worker-ownership-durable"
            )
        )
        assert lote is not None
        assert operacion is not None
        guardas = list(
            (
                await observador.scalars(
                    select(PuntoVentaGuardaEmisionRece).where(
                        PuntoVentaGuardaEmisionRece.operacion_id == operacion.id
                    )
                )
            ).all()
        )
        intentos = list(
            (
                await observador.scalars(
                    select(IntentoEmisionFiscal).where(
                        IntentoEmisionFiscal.operacion_id == operacion.id
                    )
                )
            ).all()
        )
        assert len(guardas) == 1
        assert guardas[0].fase == "cerrada_pre_arca"
        assert guardas[0].arca_iniciada_en is None
        assert len(intentos) == 1
        assert intentos[0].estado == "fallido_verificado"
        assert lote.estado == "en_cola"
        assert operacion.estado == "en_proceso"
        assert operacion.response_json["en_progreso"] is True
        assert operacion.response_json["lote"]["id"] == lote_id
        assert lote.metadata_json["operacion_idempotente_id"] == operacion.id
        comprobantes = list((await observador.scalars(select(Comprobante))).all())
        assert comprobantes == []


@pytest.mark.asyncio
async def test_procesar_lote_recupera_fallo_durable_al_cerrar_pre_arca_batch(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """El cierre batch fallido se recupera completo sin publicar ni emitir CAE."""
    consultas_numeracion = 0
    consultas_capacidad = 0
    llamadas_fecae = 0
    cierres = 0

    class FakeWSFEClient:
        """Fuerza cambio de rango luego de reservar el sublote completo."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva sin abrir red."""

        async def fe_comp_tot_x_request(self):
            """Permite agrupar los dos comprobantes en una única guarda."""
            nonlocal consultas_capacidad
            consultas_capacidad += 1
            return 2

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Cambia el próximo número en el segundo preflight seguro."""
            nonlocal consultas_numeracion
            consultas_numeracion += 1
            return 0 if consultas_numeracion == 1 else 1

        async def fe_cae_solicitar_lote(self, arca_requests):
            """Hace observable cualquier FECAE batch indebido."""
            nonlocal llamadas_fecae
            llamadas_fecae += 1
            raise AssertionError("No debe solicitar FECAE batch en este escenario")

        async def fe_cae_solicitar(self, arca_request):
            """Hace observable un fallback unitario indebido."""
            nonlocal llamadas_fecae
            llamadas_fecae += 1
            raise AssertionError("No debe solicitar FECAE unitario en este escenario")

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    cierre_original = ElegibilidadReceService.cerrar_pre_arca

    async def fallar_primer_cierre(self, guarda, **kwargs):
        nonlocal cierres
        cierres += 1
        if cierres == 1:
            raise RuntimeError("fallo sintético al confirmar cierre batch")
        return await cierre_original(self, guarda, **kwargs)

    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_max_registros", 2)
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
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-fallo-cierre-pre-arca-batch.xlsx",
        total_grupos=2,
    )
    key = "idem-fallo-cierre-pre-arca-batch"
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key=key,
    )
    resumen = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/resumen",
        headers=auth_headers,
    )
    assert resumen.status_code == 200, resumen.text
    duplicado = resumen.json()["confirmacion_duplicado_logico"]
    if duplicado:
        headers["X-Confirmacion-Duplicado-Logico"] = duplicado

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )

    assert response.status_code == 503, response.text
    assert consultas_capacidad == 1
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
        lote = await observador.get(LoteComprobante, lote_id)
        guardas = list(
            (
                await observador.scalars(
                    select(PuntoVentaGuardaEmisionRece).where(
                        PuntoVentaGuardaEmisionRece.operacion_id == operacion.id
                    )
                )
            ).all()
        )
        intentos = list(
            (
                await observador.scalars(
                    select(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.operacion_id == operacion.id)
                    .order_by(IntentoEmisionFiscal.id)
                )
            ).all()
        )
        assert lote is not None
        assert lote.estado == "validado"
        assert len(guardas) == 1
        assert guardas[0].fase == "cerrada_pre_arca"
        assert guardas[0].arca_iniciada_en is None
        assert len(intentos) == 2
        assert {intento.estado for intento in intentos} == {"fallido_verificado"}
        assert operacion.estado == "interrumpida_pre_arca"
        assert operacion.response_json is None
        comprobantes = list((await observador.scalars(select(Comprobante))).all())
        assert comprobantes == []


@pytest.mark.asyncio
async def test_procesar_lote_recupera_segundo_chunk_pre_arca_automaticamente(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
) -> None:
    """El caller conserva el primer CAE y cierra la segunda guarda sin reemitir."""

    class FakeWSFEClient:
        """Autoriza el primer grupo y no recibe la segunda solicitud FECAE."""

        consultas_numeracion = 0
        llamadas_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma real sin abrir red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Refleja el primer CAE antes de evaluar el segundo grupo."""
            FakeWSFEClient.consultas_numeracion += 1
            return 0 if FakeWSFEClient.consultas_numeracion <= 2 else 1

        async def fe_cae_solicitar(self, arca_request):
            """Autoriza solamente el primer chunk unitario."""
            FakeWSFEClient.llamadas_fecae += 1
            return CAEResponse(
                cae=CAE_TEST_NO_REAL,
                cae_vencimiento="20260819",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    marcar_original = ElegibilidadReceService.marcar_arca_iniciada
    guardas_evaluadas = 0

    async def fallar_segundo_cas(self, **kwargs):
        nonlocal guardas_evaluadas
        guardas_evaluadas += 1
        if guardas_evaluadas == 2:
            raise SQLAlchemyTimeoutError()
        return await marcar_original(self, **kwargs)

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
        "marcar_arca_iniciada",
        fallar_segundo_cas,
    )

    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-dos-chunks-recovery-automatico.xlsx",
        total_grupos=2,
    )
    headers = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
        idempotency_key="idem-dos-chunks-recovery-automatico",
    )
    resumen = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/resumen",
        headers=auth_headers,
    )
    assert resumen.status_code == 200, resumen.text
    duplicado = resumen.json()["confirmacion_duplicado_logico"]
    if duplicado:
        headers["X-Confirmacion-Duplicado-Logico"] = duplicado

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["categoria_error"] == "post_arca_persistencia"
    assert guardas_evaluadas == 2
    assert FakeWSFEClient.llamadas_fecae == 1
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        operacion = await observador.scalar(
            select(OperacionIdempotente).where(
                OperacionIdempotente.idempotency_key
                == "idem-dos-chunks-recovery-automatico"
            )
        )
        assert operacion is not None
        lote = await observador.get(LoteComprobante, lote_id)
        grupos = list(
            (
                await observador.scalars(
                    select(LoteComprobanteGrupo)
                    .where(LoteComprobanteGrupo.lote_id == lote_id)
                    .order_by(LoteComprobanteGrupo.orden)
                )
            ).all()
        )
        guardas = list(
            (
                await observador.scalars(
                    select(PuntoVentaGuardaEmisionRece)
                    .where(PuntoVentaGuardaEmisionRece.operacion_id == operacion.id)
                    .order_by(PuntoVentaGuardaEmisionRece.id)
                )
            ).all()
        )
        intentos = list(
            (
                await observador.scalars(
                    select(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.operacion_id == operacion.id)
                    .order_by(IntentoEmisionFiscal.id)
                )
            ).all()
        )
        assert lote.estado == "requiere_reconciliacion"
        assert [grupo.estado for grupo in grupos] == [
            "autorizado",
            "requiere_reconciliacion",
        ]
        assert [guarda.fase for guarda in guardas] == [
            "cerrada_terminal",
            "cerrada_pre_arca",
        ]
        assert [intento.estado for intento in intentos] == [
            "autorizado",
            "fallido_verificado",
        ]
        assert operacion.estado == "requiere_reconciliacion"
        comprobantes = list((await observador.scalars(select(Comprobante))).all())
        assert len(comprobantes) == 1


@pytest.mark.asyncio
async def test_worker_propaga_guarda_actual_a_recovery_aunque_hubo_fecae_previo(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """El worker usa id/token de la guarda actual, no el bit global acumulado."""

    class SessionFactory:
        """Reutiliza la sesión aislada como conexión del worker."""

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    lote = LoteComprobante(
        nombre_archivo="lote-worker-guarda-actual.xlsx",
        archivo_hash="hash-lote-worker-guarda-actual",
        estado="en_cola",
        modo_procesamiento="background",
        procesamiento_async=True,
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    db_session.add(lote)
    await db_session.commit()
    lote_id = lote.id
    empresa_id = test_empresa.id
    guarda_id = 9876
    guarda_token = "f" * 64
    recovery_recibido: list[tuple[int | None, str | None]] = []

    async def fake_acquire(session: AsyncSession, role: str) -> None:
        assert session is db_session
        assert role == "worker"

    async def fail_segundo_chunk(self, lote_id, empresa_id, **kwargs):
        fase = kwargs["fase_solicitud_arca"]
        fase.marcar_iniciada()
        fase.registrar_guarda_pre_arca(
            SimpleNamespace(id=guarda_id, token=guarda_token)
        )
        assert fase.iniciada is True
        assert fase.guarda_actual_iniciada is False
        raise SQLAlchemyTimeoutError()

    async def fake_recovery(
        self,
        *,
        lote_id,
        empresa_id,
        guarda_rece_id,
        guarda_rece_token,
    ):
        recovery_recibido.append((guarda_rece_id, guarda_rece_token))
        return "requiere_reconciliacion"

    monkeypatch.setattr("app.services.lote_worker.WorkerSessionLocal", SessionFactory)
    monkeypatch.setattr(
        "app.services.lote_worker.acquire_database_connection",
        fake_acquire,
    )
    monkeypatch.setattr(
        LoteComprobantesService,
        "procesar_lote",
        fail_segundo_chunk,
    )
    monkeypatch.setattr(
        LoteComprobantesService,
        "recuperar_lote_worker_interrumpido_pre_arca",
        fake_recovery,
    )

    resultado = await LoteWorker().procesar_pendientes()

    assert resultado.lotes_en_cola_detectados == 1
    assert resultado.lotes_procesados == 0
    assert resultado.tuvo_error is True
    assert recovery_recibido == [(guarda_id, guarda_token)]
    assert (await db_session.get(LoteComprobante, lote_id)).empresa_id == empresa_id


@pytest.mark.asyncio
async def test_worker_no_procesa_en_cola_si_falla_bloqueo_stale(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
):
    """Si no puede bloquear un stale, el worker no sigue con nuevos CAE."""

    class SessionFactory:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    stale = LoteComprobante(
        nombre_archivo="lote-stale-worker.xlsx",
        archivo_hash="hash-stale-worker",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    en_cola = LoteComprobante(
        nombre_archivo="lote-en-cola-worker.xlsx",
        archivo_hash="hash-en-cola-worker",
        estado="en_cola",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([stale, en_cola])
    await db_session.commit()

    bloqueados: list[int] = []
    procesados: list[int] = []

    async def fail_bloquear(self, lote_id, empresa_id, **kwargs):
        bloqueados.append(lote_id)
        raise RuntimeError("fallo controlado de bloqueo stale")

    async def record_procesar(self, lote_id, empresa_id, **kwargs):
        procesados.append(lote_id)
        return await self.obtener_lote_resumen(lote_id, empresa_id)

    monkeypatch.setattr("app.services.lote_worker.WorkerSessionLocal", SessionFactory)
    monkeypatch.setattr(
        LoteComprobantesService,
        "bloquear_lote_procesando_stale",
        fail_bloquear,
    )
    monkeypatch.setattr(LoteComprobantesService, "procesar_lote", record_procesar)

    await LoteWorker().procesar_pendientes()

    assert bloqueados == [stale.id]
    assert procesados == []


@pytest.mark.asyncio
async def test_worker_no_procesa_en_cola_si_quedan_stale_fuera_del_batch(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """Si quedan stale fuera del batch, el worker posterga nuevos CAE."""

    class SessionFactory:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(settings, "batch_worker_batch_size", 1)
    vencido = datetime.utcnow() - timedelta(
        minutes=settings.batch_processing_stale_minutes + 3
    )
    stale_1 = LoteComprobante(
        nombre_archivo="lote-stale-worker-1.xlsx",
        archivo_hash="hash-stale-worker-1",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        updated_at=vencido,
    )
    stale_2 = LoteComprobante(
        nombre_archivo="lote-stale-worker-2.xlsx",
        archivo_hash="hash-stale-worker-2",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        updated_at=vencido + timedelta(minutes=1),
    )
    en_cola = LoteComprobante(
        nombre_archivo="lote-en-cola-worker-overflow.xlsx",
        archivo_hash="hash-en-cola-worker-overflow",
        estado="en_cola",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([stale_1, stale_2, en_cola])
    await db_session.commit()

    bloqueados: list[int] = []
    procesados: list[int] = []

    async def fake_bloquear(self, lote_id, empresa_id, **kwargs):
        bloqueados.append(lote_id)
        lote = await self.db.get(LoteComprobante, lote_id)
        lote.estado = "requiere_reconciliacion"
        await self.db.commit()
        return lote

    async def record_procesar(self, lote_id, empresa_id, **kwargs):
        procesados.append(lote_id)
        return await self.obtener_lote_resumen(lote_id, empresa_id)

    monkeypatch.setattr("app.services.lote_worker.WorkerSessionLocal", SessionFactory)
    monkeypatch.setattr(
        LoteComprobantesService,
        "bloquear_lote_procesando_stale",
        fake_bloquear,
    )
    monkeypatch.setattr(LoteComprobantesService, "procesar_lote", record_procesar)

    await LoteWorker().procesar_pendientes()

    assert bloqueados == [stale_1.id]
    assert procesados == []


@pytest.mark.asyncio
async def test_procesar_lote_legacy_sin_descripcion_item_bloquea_emision(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe emitir lotes validados antes de confirmar descripción facturada."""
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-legacy-descripcion.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    metadata = dict(lote.metadata_json or {})
    metadata.pop("opciones_descripcion_item", None)
    lote.metadata_json = metadata
    await db_session.commit()
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 400
    detail = procesar.json()["detail"]
    assert "descripción facturada" in detail["mensaje"]


@pytest.mark.asyncio
async def test_procesar_lote_grande_encola_y_se_reanuda(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    empresa_id = int(inspect(test_empresa).identity[0])
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "batch_sync_limit", 0)

    async def fake_emitir(self, request, **kwargs):
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=654,
            fecha_emision=request.fecha_emision,
            cae=CAE_TEST_NO_REAL_ALT,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=654,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL_ALT,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-background.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    headers_procesar = await _confirmacion_fecha_fiscal_header_lote(
        db_session,
        lote_id=lote_id,
        estados={"validado"},
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **headers_procesar},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is True
    assert data["lote"]["estado"] == "en_cola"

    service = LoteComprobantesService(db_session)
    lote = await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    assert lote.estado == "completado"
    assert lote.grupos_emitidos == 1
