"""API para emisión masiva de comprobantes."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Body,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_empresa_id, get_current_empresa_user
from app.api.arca import get_wsfe_client
from app.core.config import settings
from app.core.database import DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS
from app.core.database import get_db
from app.core.date_parsing import parse_fecha_input
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import OperacionIdempotente
from app.models.lote_comprobante import LoteComprobante
from app.models.usuario import Usuario
from app.schemas.comprobante import ErrorArcaFiscalResponse
from app.schemas.lote_comprobante import (
    LoteAccionResponse,
    LoteComprobanteDetalleResponse,
    LoteComprobanteGrupoDetalleResponse,
    LoteComprobanteGruposPageResponse,
    LoteComprobanteResponse,
    LoteComprobanteResumenResponse,
    LoteComprobanteSeguimientoResponse,
    LoteDescartarGruposRequest,
    LoteEliminarCompactarRequest,
    LoteGrupoIdsRequest,
    LoteProcesamientoResponse,
    LoteReconciliacionExternaRequest,
    LoteValidacionResponse,
)
from app.services.facturacion_service import FaseSolicitudArca
from app.services.lote_comprobantes_service import (
    LoteComprobanteConflictoError,
    LoteComprobanteError,
    LoteComprobantesService,
    OpcionesConceptoLote,
    OpcionesDescripcionItemLote,
    OpcionesFechasLote,
    OpcionesPuntoVentaLote,
)
from app.services.lote_worker import ensure_lote_worker_running
from app.services.idempotencia_fiscal_service import (
    CreacionOperacionAmbiguaError,
    IdempotenciaFiscalError,
    IdempotenciaFiscalService,
)
from app.services.elegibilidad_rece_service import (
    ContextoElegibilidadRece,
    ElegibilidadReceError,
    ElegibilidadReceService,
)
from app.services.puntos_venta_arca_service import PuntosVentaArcaService
from app.services.perfiles_carga_masiva_service import (
    PerfilCargaMasivaError,
    PerfilesCargaMasivaService,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_fecha_form(value: str | None, field_name: str) -> date | None:
    """Parsea fechas opcionales recibidas por multipart/form-data."""
    try:
        return parse_fecha_input(value, field_name=field_name, allow_empty=True)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


def _error_db_post_arca_lote() -> HTTPException:
    """Devuelve conflicto sanitizado si la DB cae después de solicitar CAE."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "mensaje": (
                "La solicitud fiscal pudo haber sido procesada por ARCA, pero "
                "FactuFlow no pudo cerrar la persistencia del lote."
            ),
            "errores": [
                "No reintentes el lote. Reconciliá sus comprobantes antes de continuar."
            ],
            "requiere_reconciliacion": True,
            "categoria_error": "post_arca_persistencia",
        },
    )


def _error_db_pre_arca_lote_bloqueado() -> HTTPException:
    """Devuelve un conflicto seguro si no pudo abrirse un replay pre-ARCA."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "mensaje": "No se pudo dejar la operación lista para reintento seguro.",
            "errores": [
                "Conservá la misma clave de idempotencia y revisá el estado antes de continuar."
            ],
            "categoria_error": "pre_arca_estado_bloqueado",
        },
    )


def _error_idempotencia_en_proceso_lote() -> HTTPException:
    """Informa que otra request ganó el reclamo de la operación."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "mensaje": "La operación fiscal ya está en proceso.",
            "errores": ["Esperá a que finalice antes de volver a consultar."],
            "categoria_error": "idempotencia_en_proceso",
        },
    )


async def _reclamar_operacion_lote_pre_arca_segura(
    db: AsyncSession,
    idempotencia: IdempotenciaFiscalService,
    operacion: OperacionIdempotente,
) -> tuple[OperacionIdempotente, bool]:
    """Ejecuta el CAS de replay sin aceptar un resultado durable ambiguo."""
    try:
        return await idempotencia.reclamar_operacion_interrumpida_pre_arca(operacion)
    except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "event=pre_arca_lote_replay_rollback_failed tipo_error=%s",
                type(rollback_exc).__name__,
            )
        raise _error_db_pre_arca_lote_bloqueado()


async def _recuperar_operacion_lote_pre_arca(
    db: AsyncSession,
    idempotencia: IdempotenciaFiscalService,
    operacion_id: int,
    fase_solicitud_arca: FaseSolicitudArca,
) -> Literal["recuperada_pre_arca", "requiere_reconciliacion", "no_recuperable",]:
    """Recupera una operación solo si su guarda prueba cero inicio ARCA."""
    try:
        await db.rollback()
        if (
            fase_solicitud_arca.guarda_rece_id is not None
            and fase_solicitud_arca.guarda_rece_token is not None
        ):
            resultado_guarda = await ElegibilidadReceService(
                db
            ).recuperar_guarda_interrumpida_pre_arca(
                operacion_id=operacion_id,
                guarda_id=fase_solicitud_arca.guarda_rece_id,
                token=fase_solicitud_arca.guarda_rece_token,
            )
            if resultado_guarda == "recuperada_pre_arca":
                return resultado_guarda
            if resultado_guarda == "requiere_reconciliacion":
                return resultado_guarda
        recuperada = await idempotencia.marcar_operacion_interrumpida_pre_arca(
            operacion_id
        )
        return "recuperada_pre_arca" if recuperada else "no_recuperable"
    except Exception as recovery_exc:
        logger.error(
            "event=pre_arca_lote_operation_recovery_failed tipo_error=%s",
            type(recovery_exc).__name__,
        )
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "event=pre_arca_lote_operation_rollback_failed tipo_error=%s",
                type(rollback_exc).__name__,
            )
        return "no_recuperable"


def _estado_operacion_lote_desde_respuesta(
    response_json: dict,
    *,
    operacion_id: int,
) -> str:
    """Mapea una respuesta de lote al estado de operación idempotente."""
    if response_json.get("categoria_error") == "duplicado_logico_lote":
        return "requiere_confirmacion_duplicado"
    lote = response_json.get("lote") or {}
    if lote.get("estado") == "requiere_reconciliacion":
        return "requiere_reconciliacion"
    metadata = lote.get("metadata_json") or {}
    errores_arca = LoteComprobantesService.errores_arca_publicables_desde_metadata(
        metadata,
        operacion_id=operacion_id,
    )
    if errores_arca and response_json.get("errores_arca") == [
        error.model_dump(mode="json") for error in errores_arca
    ]:
        return "rechazado_arca"
    return "finalizado"


def _respuesta_lote_replay_validada(
    response_json: dict,
    response_schema: type[LoteProcesamientoResponse] | type[LoteAccionResponse],
    *,
    operacion: OperacionIdempotente,
    lote_id: int,
    empresa_id: int,
) -> LoteProcesamientoResponse | LoteAccionResponse:
    """Valida que un replay durable pertenezca a su operación y lote exactos."""
    try:
        respuesta = response_schema.model_validate(response_json)
    except PydanticValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La respuesta fiscal durable del lote no conserva un formato "
                "publicable válido."
            ),
        ) from exc
    if (
        operacion.lote_id != lote_id
        or operacion.empresa_id != empresa_id
        or not LoteComprobantesService.respuesta_lote_coincide_operacion(
            respuesta,
            estado_operacion=operacion.estado,
            operacion_id=int(operacion.id),
            lote_id=lote_id,
            empresa_id=empresa_id,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La respuesta fiscal durable del lote perdió su identidad o "
                "evidencia ARCA canónica."
            ),
        )
    return respuesta


async def _resolver_operacion_lote(
    *,
    db: AsyncSession,
    empresa_id: int,
    usuario_id: int | None,
    idempotency_key: str | None,
    tipo_operacion: str,
    payload: dict,
    lote_id: int,
    material_rece: dict,
) -> tuple[
    IdempotenciaFiscalService,
    OperacionIdempotente,
    bool,
    list[ContextoElegibilidadRece] | None,
]:
    """Obtiene o crea una operación idempotente de lote."""
    idempotencia = IdempotenciaFiscalService(db)
    payload_hash = idempotencia.calcular_payload_hash(
        idempotencia.payload_sin_confirmacion_duplicado(payload)
    )
    try:
        existente = await idempotencia.obtener_operacion_existente(
            empresa_id=empresa_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
        )
        if existente is not None:
            return idempotencia, existente, False, None
        puntos_ids = {
            int(grupo["punto_venta_id"])
            for grupo in list(material_rece.get("grupos") or [])
            if grupo.get("punto_venta_id") is not None
        }
        await PuntosVentaArcaService(db).asegurar_comprobacion_reciente(
            empresa_id=empresa_id,
            puntos_venta_ids=puntos_ids,
            actor_usuario_id=usuario_id,
        )
        async with _contextos_rece_lote_bloqueados(
            db=db,
            lote_id=lote_id,
            empresa_id=empresa_id,
            material_rece=material_rece,
        ) as contextos_rece:
            operacion, creada = await idempotencia.obtener_o_crear_operacion(
                empresa_id=empresa_id,
                usuario_id=usuario_id,
                idempotency_key=idempotency_key,
                tipo_operacion=tipo_operacion,
                payload_hash=payload_hash,
                lote_id=lote_id,
                contextos_rece=contextos_rece,
            )
    except ElegibilidadReceError as exc:
        raise _error_elegibilidad_lote(exc) from exc
    except IdempotenciaFiscalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except CreacionOperacionAmbiguaError as exc:
        try:
            recuperada = await idempotencia.recuperar_creacion_ambigua_pre_arca(
                empresa_id=empresa_id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                tipo_operacion=tipo_operacion,
                lote_id=lote_id,
                contextos_rece=contextos_rece,
            )
        except Exception as recovery_exc:
            logger.error(
                "event=pre_arca_lote_ambiguous_create_recovery_failed tipo_error=%s",
                type(recovery_exc).__name__,
            )
            recuperada = False
        if not recuperada:
            raise _error_db_pre_arca_lote_bloqueado()
        raise exc.error_original
    return idempotencia, operacion, creada, contextos_rece


def _error_elegibilidad_lote(exc: ElegibilidadReceError) -> HTTPException:
    """Devuelve un conflicto fail-closed sin filtrar evidencia fiscal."""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "mensaje": exc.mensaje,
            "errores": ["No se solicitó CAE ni se consultó capacidad batch a ARCA."],
            "categoria_error": exc.categoria,
        },
    )


async def _resolver_contextos_rece_lote(
    *,
    db: AsyncSession,
    lote_id: int,
    empresa_id: int,
    material_rece: dict,
    operacion: OperacionIdempotente | None = None,
) -> list[ContextoElegibilidadRece]:
    """Resuelve contextos bajo locks durante toda la validación."""
    try:
        puntos_ids = {
            int(grupo["punto_venta_id"])
            for grupo in list(material_rece.get("grupos") or [])
            if grupo.get("punto_venta_id") is not None
        }
        await PuntosVentaArcaService(db).asegurar_comprobacion_reciente(
            empresa_id=empresa_id,
            puntos_venta_ids=puntos_ids,
            actor_usuario_id=None,
        )
        async with _contextos_rece_lote_bloqueados(
            db=db,
            lote_id=lote_id,
            empresa_id=empresa_id,
            material_rece=material_rece,
            operacion=operacion,
        ) as contextos:
            return contextos
    except ElegibilidadReceError as exc:
        raise _error_elegibilidad_lote(exc) from exc


@asynccontextmanager
async def _contextos_rece_lote_bloqueados(
    *,
    db: AsyncSession,
    lote_id: int,
    empresa_id: int,
    material_rece: dict,
    operacion: OperacionIdempotente | None = None,
) -> AsyncIterator[list[ContextoElegibilidadRece]]:
    """Mantiene locks multipunto hasta que el caller termina su transacción."""
    grupos = list(material_rece.get("grupos") or [])
    grupo_ids = [int(grupo["grupo_id"]) for grupo in grupos]
    puntos_ids = sorted(
        {
            int(grupo["punto_venta_id"])
            for grupo in grupos
            if grupo.get("punto_venta_id") is not None
        }
    )
    if (
        not grupos
        or len(puntos_ids) == 0
        or any(grupo.get("punto_venta_id") is None for grupo in grupos)
    ):
        raise ElegibilidadReceError(
            "El lote no tiene una membresía RECE completa y emitible."
        )
    tipos = {
        int(grupo["grupo_id"]): int(grupo["tipo_comprobante"])
        for grupo in grupos
        if grupo.get("tipo_comprobante") is not None
    }
    elegibilidad = ElegibilidadReceService(db)
    async with AsyncExitStack() as stack:
        for punto_venta_id in puntos_ids:
            await stack.enter_async_context(
                elegibilidad.bloqueo_local_punto(
                    empresa_id=empresa_id,
                    punto_venta_id=punto_venta_id,
                )
            )
        contextos = await elegibilidad.validar_grupos_lote(
            lote_id=lote_id,
            empresa_id=empresa_id,
            grupo_ids=grupo_ids,
            tipo_comprobante_por_grupo=tipos,
            material_confirmado=grupos,
            bloquear=True,
        )
        if operacion is not None:
            await elegibilidad.validar_operacion_para_continuar(
                operacion_id=operacion.id,
                empresa_id=empresa_id,
                contextos_esperados=contextos,
            )
        yield contextos


def _lote_puede_emitirse(lote) -> bool:
    return (
        lote.grupos_validos > 0
        and lote.estado in LoteComprobantesService.ESTADOS_PROCESABLES
    )


def _serialize_lote(lote) -> LoteComprobanteResponse:
    return LoteComprobanteResponse.model_validate(lote)


def _errores_arca_lote(
    lote: LoteComprobante,
    *,
    operacion_id: int | None = None,
) -> list[ErrorArcaFiscalResponse]:
    """Extrae evidencia fiscal publicable desde la metadata durable del lote."""
    return LoteComprobantesService.errores_arca_publicables_desde_metadata(
        lote.metadata_json,
        operacion_id=operacion_id,
    )


def _serialize_lote_detalle(lote) -> LoteComprobanteDetalleResponse:
    return LoteComprobanteDetalleResponse.model_validate(lote)


def _serialize_lote_resumen(
    lote, resumen_operativo: dict
) -> LoteComprobanteResumenResponse:
    data = LoteComprobanteResponse.model_validate(lote).model_dump()
    return LoteComprobanteResumenResponse(**data, **resumen_operativo)


def _operacion_lote_esta_cerrada(operacion: OperacionIdempotente) -> bool:
    """Indica si una operación idempotente de lote ya tiene resultado final."""
    return operacion.estado in {
        "finalizado",
        "fallido",
        "requiere_reconciliacion",
        "fallido_verificado",
        "rechazado_arca",
    }


async def _publicar_respuesta_lote_reconstruida(
    *,
    db: AsyncSession,
    service: LoteComprobantesService,
    idempotencia: IdempotenciaFiscalService,
    operacion: OperacionIdempotente,
    lote: LoteComprobante,
    respuesta: LoteProcesamientoResponse | LoteAccionResponse,
) -> None:
    """Publica un replay de lote sin sobrescribir ownership concurrente."""
    metadata = lote.metadata_json or {}
    owner_actual = metadata.get("operacion_idempotente_id")
    if (
        not isinstance(owner_actual, int)
        or isinstance(owner_actual, bool)
        or owner_actual != operacion.id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El lote ya no conserva el ownership de la operación fiscal "
                "que intenta reconstruirse."
            ),
        )
    material_rece = metadata.get("pf19b_rece_material")
    ownership_worker = (
        operacion.tipo_operacion == "procesar_lote"
        and isinstance(material_rece, dict)
        and IdempotenciaFiscalService.respuesta_worker_en_progreso_valida(
            operacion.response_json,
            lote_id=int(lote.id),
            empresa_id=int(lote.empresa_id),
            operacion_id=int(operacion.id),
            material_rece=material_rece,
        )
    )
    if ownership_worker:
        try:
            await service._guardar_respuesta_operacion_background(
                lote,
                int(operacion.id),
            )
        except LoteComprobanteConflictoError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        await db.commit()
        await db.refresh(operacion)
        return

    await idempotencia.guardar_resultado_operacion_sync(
        operacion,
        response_json=respuesta,
        estado=_estado_operacion_lote_desde_respuesta(
            respuesta.model_dump(mode="json"),
            operacion_id=int(operacion.id),
        ),
    )


def _raise_error_operacion_lote(response_json: dict) -> None:
    """Reemite un error guardado en una operación idempotente de lote."""
    status_code = int(response_json.get("status_code") or status.HTTP_409_CONFLICT)
    raise HTTPException(status_code=status_code, detail=response_json)


async def _guardar_y_lanzar_error_operacion_lote(
    idempotencia: IdempotenciaFiscalService,
    operacion: OperacionIdempotente,
    *,
    mensaje: str,
    categoria_error: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    errores: list[str] | None = None,
) -> None:
    """Guarda un error pre-CAE para que la misma clave no quede varada."""
    detail = {
        "mensaje": mensaje,
        "errores": errores or [mensaje],
        "categoria_error": categoria_error,
        "status_code": status_code,
    }
    await idempotencia.guardar_resultado_operacion_sync(
        operacion,
        response_json=detail,
        estado="fallido_verificado",
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _descripcion_facturada_grupo(grupo) -> str | None:
    for fila in grupo.filas:
        descripcion = (fila.datos_json or {}).get("item_descripcion")
        if descripcion is None:
            continue
        descripcion_texto = str(descripcion).strip()
        if descripcion_texto:
            return descripcion_texto
    return None


def _serialize_grupo_detalle(grupo) -> LoteComprobanteGrupoDetalleResponse:
    data = LoteComprobanteGrupoDetalleResponse.model_validate(grupo).model_dump()
    data["descripcion_facturada"] = _descripcion_facturada_grupo(grupo)
    return LoteComprobanteGrupoDetalleResponse(**data)


async def _get_empresa(db: AsyncSession, empresa_id: int) -> Empresa:
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


@router.get("", response_model=list[LoteComprobanteResponse])
async def listar_lotes(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Lista los lotes recientes de la empresa activa."""
    service = LoteComprobantesService(db)
    lotes = await service.listar_lotes(empresa_activa_id)
    return [_serialize_lote(lote) for lote in lotes]


@router.get("/plantilla")
async def descargar_plantilla(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Descarga la plantilla fija de Excel para emisión masiva."""
    empresa = await _get_empresa(db, empresa_activa_id)
    service = LoteComprobantesService(db)
    contenido = await service.generar_plantilla(empresa)
    filename = f"factuflow-lote-{empresa.cuit}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/validar", response_model=LoteValidacionResponse)
async def validar_archivo_lote(
    archivo: UploadFile = File(...),
    formato_version_id: int | None = Form(None),
    perfil_carga_masiva_id: int | None = Form(None),
    punto_venta_modo: str = Form("archivo"),
    punto_venta_numero: int | None = Form(None),
    concepto_modo: str = Form(...),
    descripcion_item_modo: str = Form(...),
    descripcion_item_fija: str | None = Form(None),
    fecha_emision_modo: str = Form(...),
    fecha_emision_fija: str | None = Form(None),
    fecha_servicio_desde_modo: str | None = Form(None),
    fecha_servicio_desde_fija: str | None = Form(None),
    fecha_servicio_hasta_modo: str | None = Form(None),
    fecha_servicio_hasta_fija: str | None = Form(None),
    fecha_vto_pago_modo: str | None = Form(None),
    fecha_vto_pago_fija: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Valida y registra un lote de comprobantes a partir de un Excel."""
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes subir un archivo Excel .xlsx generado desde la plantilla oficial",
        )

    contenido = await archivo.read(settings.batch_max_upload_bytes + 1)
    if len(contenido) > settings.batch_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El archivo supera el tamaño máximo permitido "
                f"de {settings.batch_max_upload_bytes // (1024 * 1024)} MB"
            ),
        )
    empresa = await _get_empresa(db, empresa_activa_id)
    service = LoteComprobantesService(db)
    opciones_concepto = OpcionesConceptoLote(concepto_modo=concepto_modo)
    opciones_descripcion_item = OpcionesDescripcionItemLote(
        descripcion_item_modo=descripcion_item_modo,
        descripcion_item_fija=descripcion_item_fija,
    )
    opciones_punto_venta = OpcionesPuntoVentaLote(
        punto_venta_modo=punto_venta_modo,
        punto_venta_numero=punto_venta_numero,
    )
    opciones_fechas = OpcionesFechasLote(
        fecha_emision_modo=fecha_emision_modo,
        fecha_emision_fija=_parse_fecha_form(fecha_emision_fija, "fecha_emision_fija"),
        fecha_servicio_desde_modo=fecha_servicio_desde_modo or "",
        fecha_servicio_desde_fija=_parse_fecha_form(
            fecha_servicio_desde_fija, "fecha_servicio_desde_fija"
        ),
        fecha_servicio_hasta_modo=fecha_servicio_hasta_modo or "",
        fecha_servicio_hasta_fija=_parse_fecha_form(
            fecha_servicio_hasta_fija, "fecha_servicio_hasta_fija"
        ),
        fecha_vto_pago_modo=fecha_vto_pago_modo or "",
        fecha_vto_pago_fija=_parse_fecha_form(
            fecha_vto_pago_fija, "fecha_vto_pago_fija"
        ),
    )
    perfil_snapshot = None
    if perfil_carga_masiva_id:
        perfiles_service = PerfilesCargaMasivaService(db)
        try:
            perfil_snapshot = await perfiles_service.snapshot(
                perfil_carga_masiva_id,
                empresa_activa_id,
            )
        except PerfilCargaMasivaError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
    try:
        lote = await service.validar_y_registrar_lote(
            contenido,
            archivo.filename,
            empresa,
            current_user,
            opciones_fechas=opciones_fechas,
            opciones_concepto=opciones_concepto,
            opciones_descripcion_item=opciones_descripcion_item,
            opciones_punto_venta=opciones_punto_venta,
            formato_version_id=formato_version_id,
            perfil_carga_masiva_snapshot=perfil_snapshot,
        )
    except LoteComprobanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return LoteValidacionResponse(
        lote=_serialize_lote(lote),
        puede_emitirse=_lote_puede_emitirse(lote),
        requiere_background=lote.total_grupos > settings.batch_sync_limit,
        mensaje=lote.mensaje_resumen or "Lote validado",
    )


@router.post("/{lote_id}/procesar", response_model=LoteProcesamientoResponse)
async def procesar_lote(
    lote_id: int,
    request: Request,
    background: bool = Query(False),
    x_confirmacion_fecha_fiscal: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
    x_confirmacion_duplicado_logico: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Procesa el lote validado."""
    service = LoteComprobantesService(db)
    fase_solicitud_arca = FaseSolicitudArca()
    try:
        lote = await service.obtener_lote_resumen(lote_id, empresa_activa_id)
    except LoteComprobanteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    requiere_background = background or lote.total_grupos > settings.batch_sync_limit
    material_grupos = await service.calcular_material_idempotente_grupos(
        lote_id=lote_id,
        empresa_id=empresa_activa_id,
        estados={
            "validado",
            "procesando",
            "autorizado",
            "fallido",
            "requiere_reconciliacion",
        },
    )
    material_rece = await service.calcular_material_idempotente_grupos(
        lote_id=lote_id,
        empresa_id=empresa_activa_id,
        estados={"validado"},
    )
    payload_operacion = {
        "lote_id": lote_id,
        "background": background,
        "confirmacion_fecha_fiscal": x_confirmacion_fecha_fiscal,
        "grupo_ids": material_grupos["grupo_ids"],
        "grupos_hash": material_grupos["grupos_hash"],
    }
    if x_idempotency_key:
        idempotencia_replay = IdempotenciaFiscalService(db)
        payload_hash_replay = idempotencia_replay.calcular_payload_hash(
            idempotencia_replay.payload_sin_confirmacion_duplicado(payload_operacion)
        )
        try:
            operacion_replay = await idempotencia_replay.obtener_operacion_existente(
                empresa_id=empresa_activa_id,
                idempotency_key=x_idempotency_key,
                payload_hash=payload_hash_replay,
            )
        except IdempotenciaFiscalError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=exc.detail,
            ) from exc
        if (
            operacion_replay is not None
            and operacion_replay.response_json is not None
            and _operacion_lote_esta_cerrada(operacion_replay)
        ):
            if "categoria_error" in operacion_replay.response_json:
                _raise_error_operacion_lote(operacion_replay.response_json)
            return _respuesta_lote_replay_validada(
                operacion_replay.response_json,
                LoteProcesamientoResponse,
                operacion=operacion_replay,
                lote_id=lote_id,
                empresa_id=empresa_activa_id,
            )

    if (
        requiere_background
        and lote.estado in service.ESTADOS_PROCESABLES
        and not ensure_lote_worker_running(request.app)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "mensaje": (
                    "El procesamiento en segundo plano no está disponible. "
                    "No se encoló el lote ni se solicitó CAE."
                ),
                "errores": [
                    "Habilita el worker de lotes y vuelve a intentar con la misma clave."
                ],
                "categoria_error": "worker_lotes_no_disponible",
            },
        )

    idempotencia, operacion, creada, contextos_rece = await _resolver_operacion_lote(
        db=db,
        empresa_id=empresa_activa_id,
        usuario_id=current_user.id,
        idempotency_key=x_idempotency_key,
        tipo_operacion="procesar_lote",
        payload=payload_operacion,
        lote_id=lote_id,
        material_rece=material_rece,
    )
    operacion_id_durable = int(operacion.id)
    try:
        continuar_operacion = creada
        if not creada and operacion.estado == "interrumpida_pre_arca":
            contextos_rece = await _resolver_contextos_rece_lote(
                db=db,
                lote_id=lote_id,
                empresa_id=empresa_activa_id,
                material_rece=material_rece,
                operacion=operacion,
            )
            (
                operacion,
                continuar_operacion,
            ) = await _reclamar_operacion_lote_pre_arca_segura(
                db,
                idempotencia,
                operacion,
            )
            if not continuar_operacion:
                raise _error_idempotencia_en_proceso_lote()
        if not creada and not continuar_operacion:
            if operacion.response_json is not None:
                if (
                    IdempotenciaFiscalService.requiere_confirmacion_duplicado(
                        operacion.response_json
                    )
                    and x_confirmacion_duplicado_logico
                ):
                    contextos_rece = await _resolver_contextos_rece_lote(
                        db=db,
                        lote_id=lote_id,
                        empresa_id=empresa_activa_id,
                        material_rece=material_rece,
                        operacion=operacion,
                    )
                    operacion, tomada = await idempotencia.marcar_operacion_en_proceso(
                        operacion
                    )
                    continuar_operacion = tomada
                elif "categoria_error" in operacion.response_json:
                    _raise_error_operacion_lote(operacion.response_json)
                elif _operacion_lote_esta_cerrada(operacion):
                    return _respuesta_lote_replay_validada(
                        operacion.response_json,
                        LoteProcesamientoResponse,
                        operacion=operacion,
                        lote_id=lote_id,
                        empresa_id=empresa_activa_id,
                    )
            if not continuar_operacion:
                lote_actual = await service.obtener_lote_resumen(
                    lote_id, empresa_activa_id
                )
                respuesta_actual = LoteProcesamientoResponse(
                    lote=_serialize_lote(lote_actual),
                    mensaje=lote_actual.mensaje_resumen
                    or "La operación está en curso.",
                    en_progreso=lote_actual.estado in {"en_cola", "procesando"},
                    errores_arca=_errores_arca_lote(
                        lote_actual,
                        operacion_id=int(operacion.id),
                    ),
                )
                if (
                    not respuesta_actual.en_progreso
                    and lote_actual.estado in service.ESTADOS_TERMINALES
                ):
                    await _publicar_respuesta_lote_reconstruida(
                        db=db,
                        service=service,
                        idempotencia=idempotencia,
                        operacion=operacion,
                        lote=lote_actual,
                        respuesta=respuesta_actual,
                    )
                return respuesta_actual

        if contextos_rece is None:
            contextos_rece = await _resolver_contextos_rece_lote(
                db=db,
                lote_id=lote_id,
                empresa_id=empresa_activa_id,
                material_rece=material_rece,
                operacion=operacion,
            )

        if lote.grupos_validos == 0:
            await _guardar_y_lanzar_error_operacion_lote(
                idempotencia,
                operacion,
                mensaje="El lote no tiene comprobantes válidos para emitir",
                categoria_error="lote_sin_comprobantes_validos",
            )

        resumen_operativo = await service.obtener_resumen_operativo_lote(
            lote_id, empresa_activa_id
        )
        confirmacion_esperada = resumen_operativo["confirmacion_fecha_fiscal"]
        mensaje_confirmacion = resumen_operativo["mensaje_confirmacion_fecha_fiscal"]
        if x_confirmacion_fecha_fiscal != confirmacion_esperada:
            await _guardar_y_lanzar_error_operacion_lote(
                idempotencia,
                operacion,
                mensaje=(
                    "Antes de emitir debes confirmar la fecha fiscal exacta del lote. "
                    f"{mensaje_confirmacion} "
                    "Volvé a confirmar desde la pantalla del lote antes de procesar."
                ),
                categoria_error="confirmacion_fecha_fiscal_invalida",
            )

        duplicados = await service.obtener_confirmacion_duplicado_logico_grupos(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            estados={"validado"},
        )
        confirmacion_duplicado_ok = False
        if duplicados["cantidad_duplicados_logicos"]:
            confirmacion_duplicado_ok = (
                x_confirmacion_duplicado_logico
                == duplicados["confirmacion_duplicado_logico"]
            )
            if not confirmacion_duplicado_ok:
                detail = {
                    "mensaje": duplicados["mensaje_confirmacion_duplicado_logico"],
                    "errores": [
                        "Confirmá el duplicado lógico antes de solicitar CAE para este lote."
                    ],
                    "categoria_error": "duplicado_logico_lote",
                    "confirmacion_duplicado_logico": duplicados[
                        "confirmacion_duplicado_logico"
                    ],
                    "cantidad_duplicados_logicos": duplicados[
                        "cantidad_duplicados_logicos"
                    ],
                }
                await idempotencia.guardar_resultado_operacion_sync(
                    operacion,
                    response_json=detail,
                    estado="requiere_confirmacion_duplicado",
                )
                raise HTTPException(status_code=409, detail=detail)

        if requiere_background:
            lote = await service.encolar_lote(
                lote_id,
                empresa_activa_id,
                operacion_id=operacion.id,
                confirmacion_duplicado_logico=confirmacion_duplicado_ok,
                material_rece=material_rece,
                commit=False,
            )
            if lote.estado != "en_cola":
                await db.rollback()
                raise _error_idempotencia_en_proceso_lote()
            respuesta = LoteProcesamientoResponse(
                lote=_serialize_lote(lote),
                mensaje=(
                    "El lote quedó en cola y se está procesando en segundo plano."
                ),
                en_progreso=True,
                errores_arca=_errores_arca_lote(
                    lote,
                    operacion_id=int(operacion.id),
                ),
            )
            respuesta_publicada = await idempotencia.guardar_respuesta_operacion_cas(
                operacion_id=operacion.id,
                response_json=respuesta,
                estado="en_proceso",
                estado_esperado="en_proceso",
                respuesta_esperada_nula=True,
                commit=False,
            )
            if not respuesta_publicada:
                await db.rollback()
                raise _error_idempotencia_en_proceso_lote()
            await db.commit()
            await db.refresh(lote)
            await db.refresh(operacion)
            return respuesta

        try:
            lote = await service.procesar_lote(
                lote_id,
                empresa_activa_id,
                operacion_id=operacion.id,
                usuario_id=current_user.id,
                confirmacion_duplicado_logico=confirmacion_duplicado_ok,
                contextos_rece=contextos_rece,
                material_rece_confirmado=material_rece,
                fase_solicitud_arca=fase_solicitud_arca,
            )
        except LoteComprobanteError as exc:
            await _guardar_y_lanzar_error_operacion_lote(
                idempotencia,
                operacion,
                mensaje=str(exc),
                categoria_error="lote_no_procesable",
            )
        respuesta = LoteProcesamientoResponse(
            lote=_serialize_lote(lote),
            mensaje=lote.mensaje_resumen or "Lote procesado",
            en_progreso=False,
            errores_arca=_errores_arca_lote(
                lote,
                operacion_id=int(operacion.id),
            ),
        )
        try:
            await idempotencia.guardar_resultado_operacion_sync(
                operacion,
                response_json=respuesta,
                estado=_estado_operacion_lote_desde_respuesta(
                    respuesta.model_dump(mode="json"),
                    operacion_id=int(operacion.id),
                ),
            )
        except SQLAlchemyTimeoutError:
            await db.rollback()
            operacion_ganadora = await db.get(
                OperacionIdempotente,
                int(operacion.id),
                populate_existing=True,
            )
            if (
                operacion_ganadora is None
                or not _operacion_lote_esta_cerrada(operacion_ganadora)
                or not isinstance(operacion_ganadora.response_json, dict)
            ):
                raise
            try:
                respuesta_ganadora = LoteProcesamientoResponse.model_validate(
                    operacion_ganadora.response_json
                )
            except PydanticValidationError:
                raise
            if (
                respuesta_ganadora.en_progreso
                or respuesta_ganadora.lote.id != lote_id
                or respuesta_ganadora.lote.empresa_id != empresa_activa_id
                or not service.respuesta_lote_coincide_operacion(
                    respuesta_ganadora,
                    estado_operacion=operacion_ganadora.estado,
                    operacion_id=int(operacion_ganadora.id),
                    lote_id=lote_id,
                    empresa_id=empresa_activa_id,
                )
            ):
                raise
            return respuesta_ganadora
        return respuesta
    except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
        if fase_solicitud_arca.guarda_actual_iniciada:
            raise _error_db_post_arca_lote()
        recuperacion = fase_solicitud_arca.resultado_recuperacion_pre_arca
        if recuperacion is None:
            recuperacion = await service.recuperar_lote_interrumpido_pre_arca(
                lote_id=lote_id,
                empresa_id=empresa_activa_id,
                operacion_id=operacion_id_durable,
                estado_reanudable="validado",
                estados_claim=(
                    {"validado"} if requiere_background else {"procesando", "validado"}
                ),
                mensaje_seguro="El lote puede volver a procesarse de forma segura.",
                guarda_rece_id=fase_solicitud_arca.guarda_rece_id,
                guarda_rece_token=fase_solicitud_arca.guarda_rece_token,
            )
            fase_solicitud_arca.registrar_recuperacion_pre_arca(recuperacion)
        if recuperacion == "recuperada_pre_arca":
            raise
        if recuperacion == "requiere_reconciliacion":
            raise _error_db_post_arca_lote()
        raise _error_db_pre_arca_lote_bloqueado()


@router.post("/{lote_id}/reintentar-fallidos", response_model=LoteAccionResponse)
async def reintentar_fallidos_lote(
    lote_id: int,
    request_body: LoteGrupoIdsRequest = Body(default_factory=LoteGrupoIdsRequest),
    x_confirmacion_fecha_fiscal: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
    x_confirmacion_duplicado_logico: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Reintenta grupos fallidos del lote con confirmación fiscal exacta."""
    service = LoteComprobantesService(db)
    fase_solicitud_arca = FaseSolicitudArca()
    grupo_ids = request_body.grupo_ids or None
    idempotencia: IdempotenciaFiscalService | None = None
    operacion: OperacionIdempotente | None = None
    try:
        await service.obtener_lote_resumen(lote_id, empresa_activa_id)
        material_grupos = await service.calcular_material_idempotente_grupos(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            estados=(
                None
                if grupo_ids
                else {
                    "fallido",
                    "reintentando",
                    "autorizado",
                    "requiere_reconciliacion",
                }
            ),
            grupo_ids=grupo_ids,
        )
        material_rece = await service.calcular_material_idempotente_grupos(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            estados=None if grupo_ids else {"fallido"},
            grupo_ids=grupo_ids,
        )
        (
            idempotencia,
            operacion,
            creada,
            contextos_rece,
        ) = await _resolver_operacion_lote(
            db=db,
            empresa_id=empresa_activa_id,
            usuario_id=current_user.id,
            idempotency_key=x_idempotency_key,
            tipo_operacion="reintentar_fallidos_lote",
            payload={
                "lote_id": lote_id,
                "grupo_ids": sorted(grupo_ids or []),
                "confirmacion_fecha_fiscal": x_confirmacion_fecha_fiscal,
                "grupo_ids_resueltos": material_grupos["grupo_ids"],
                "grupos_hash": material_grupos["grupos_hash"],
            },
            lote_id=lote_id,
            material_rece=material_rece,
        )
        continuar_operacion = creada
        if not creada and operacion.estado == "interrumpida_pre_arca":
            contextos_rece = await _resolver_contextos_rece_lote(
                db=db,
                lote_id=lote_id,
                empresa_id=empresa_activa_id,
                material_rece=material_rece,
                operacion=operacion,
            )
            (
                operacion,
                continuar_operacion,
            ) = await _reclamar_operacion_lote_pre_arca_segura(
                db,
                idempotencia,
                operacion,
            )
            if not continuar_operacion:
                raise _error_idempotencia_en_proceso_lote()
        if not creada and not continuar_operacion:
            if operacion.response_json is not None:
                if (
                    IdempotenciaFiscalService.requiere_confirmacion_duplicado(
                        operacion.response_json
                    )
                    and x_confirmacion_duplicado_logico
                ):
                    contextos_rece = await _resolver_contextos_rece_lote(
                        db=db,
                        lote_id=lote_id,
                        empresa_id=empresa_activa_id,
                        material_rece=material_rece,
                        operacion=operacion,
                    )
                    operacion, tomada = await idempotencia.marcar_operacion_en_proceso(
                        operacion
                    )
                    continuar_operacion = tomada
                elif "categoria_error" in operacion.response_json:
                    _raise_error_operacion_lote(operacion.response_json)
                elif _operacion_lote_esta_cerrada(operacion):
                    return _respuesta_lote_replay_validada(
                        operacion.response_json,
                        LoteAccionResponse,
                        operacion=operacion,
                        lote_id=lote_id,
                        empresa_id=empresa_activa_id,
                    )
            if not continuar_operacion:
                lote_actual = await service.obtener_lote_resumen(
                    lote_id,
                    empresa_activa_id,
                )
                respuesta_actual = LoteAccionResponse(
                    lote=_serialize_lote(lote_actual),
                    mensaje=lote_actual.mensaje_resumen
                    or "La operación está en curso.",
                    errores_arca=_errores_arca_lote(
                        lote_actual,
                        operacion_id=int(operacion.id),
                    ),
                )
                if lote_actual.estado in service.ESTADOS_TERMINALES:
                    await _publicar_respuesta_lote_reconstruida(
                        db=db,
                        service=service,
                        idempotencia=idempotencia,
                        operacion=operacion,
                        lote=lote_actual,
                        respuesta=respuesta_actual,
                    )
                return respuesta_actual

        if contextos_rece is None:
            contextos_rece = await _resolver_contextos_rece_lote(
                db=db,
                lote_id=lote_id,
                empresa_id=empresa_activa_id,
                material_rece=material_rece,
                operacion=operacion,
            )

        try:
            confirmacion = await service.obtener_confirmacion_fiscal_grupos(
                lote_id=lote_id,
                empresa_id=empresa_activa_id,
                estados={"fallido"},
                grupo_ids=grupo_ids,
            )
        except LoteComprobanteError as exc:
            await _guardar_y_lanzar_error_operacion_lote(
                idempotencia,
                operacion,
                mensaje=str(exc),
                categoria_error="lote_sin_grupos_reintentables",
            )
        if x_confirmacion_fecha_fiscal != confirmacion["confirmacion_fecha_fiscal"]:
            await _guardar_y_lanzar_error_operacion_lote(
                idempotencia,
                operacion,
                mensaje=(
                    "Antes de reintentar debes confirmar la fecha fiscal exacta. "
                    f"{confirmacion['mensaje_confirmacion_fecha_fiscal']}"
                ),
                categoria_error="confirmacion_fecha_fiscal_invalida",
            )

        duplicados = await service.obtener_confirmacion_duplicado_logico_grupos(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            estados={"fallido"},
            grupo_ids=grupo_ids,
        )
        confirmacion_duplicado_ok = False
        if duplicados["cantidad_duplicados_logicos"]:
            confirmacion_duplicado_ok = (
                x_confirmacion_duplicado_logico
                == duplicados["confirmacion_duplicado_logico"]
            )
            if not confirmacion_duplicado_ok:
                detail = {
                    "mensaje": duplicados["mensaje_confirmacion_duplicado_logico"],
                    "errores": [
                        "Confirmá el duplicado lógico antes de reintentar estos comprobantes."
                    ],
                    "categoria_error": "duplicado_logico_lote",
                    "confirmacion_duplicado_logico": duplicados[
                        "confirmacion_duplicado_logico"
                    ],
                    "cantidad_duplicados_logicos": duplicados[
                        "cantidad_duplicados_logicos"
                    ],
                }
                await idempotencia.guardar_resultado_operacion_sync(
                    operacion,
                    response_json=detail,
                    estado="requiere_confirmacion_duplicado",
                )
                raise HTTPException(status_code=409, detail=detail)

        lote = await service.reintentar_grupos_fallidos(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            usuario_id=current_user.id,
            grupo_ids=grupo_ids,
            operacion_id=operacion.id,
            contextos_rece=contextos_rece,
            material_rece_confirmado=material_rece,
            confirmacion_duplicado_logico=confirmacion_duplicado_ok,
            fase_solicitud_arca=fase_solicitud_arca,
        )
    except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
        if fase_solicitud_arca.guarda_actual_iniciada:
            raise _error_db_post_arca_lote()
        if idempotencia is None or operacion is None:
            raise
        recuperacion = fase_solicitud_arca.resultado_recuperacion_pre_arca
        if recuperacion is None:
            recuperacion = await _recuperar_operacion_lote_pre_arca(
                db,
                idempotencia,
                operacion.id,
                fase_solicitud_arca,
            )
            fase_solicitud_arca.registrar_recuperacion_pre_arca(recuperacion)
        if recuperacion == "recuperada_pre_arca":
            raise
        if recuperacion == "requiere_reconciliacion":
            raise _error_db_post_arca_lote()
        raise _error_db_pre_arca_lote_bloqueado()
    except HTTPException:
        raise
    except LoteComprobanteConflictoError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except LoteComprobanteError as exc:
        if idempotencia is not None and operacion is not None:
            await _guardar_y_lanzar_error_operacion_lote(
                idempotencia,
                operacion,
                mensaje=str(exc),
                categoria_error="lote_no_procesable",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    respuesta = LoteAccionResponse(
        lote=_serialize_lote(lote),
        mensaje=lote.mensaje_resumen or "Reintento finalizado",
        errores_arca=_errores_arca_lote(
            lote,
            operacion_id=int(operacion.id),
        ),
    )
    try:
        await idempotencia.guardar_resultado_operacion_sync(
            operacion,
            response_json=respuesta,
            estado=_estado_operacion_lote_desde_respuesta(
                respuesta.model_dump(mode="json"),
                operacion_id=int(operacion.id),
            ),
        )
    except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
        if not fase_solicitud_arca.guarda_actual_iniciada:
            recuperacion = await _recuperar_operacion_lote_pre_arca(
                db,
                idempotencia,
                operacion.id,
                fase_solicitud_arca,
            )
            fase_solicitud_arca.registrar_recuperacion_pre_arca(recuperacion)
            if recuperacion == "recuperada_pre_arca":
                raise
            if recuperacion == "requiere_reconciliacion":
                raise _error_db_post_arca_lote()
            raise _error_db_pre_arca_lote_bloqueado()
        raise _error_db_post_arca_lote()
    return respuesta


@router.post("/{lote_id}/reconciliar-externos", response_model=LoteAccionResponse)
async def reconciliar_emitidos_externos(
    lote_id: int,
    request_body: LoteReconciliacionExternaRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Registra comprobantes emitidos fuera de FactuFlow tras verificarlos en ARCA."""
    service = LoteComprobantesService(db)
    empresa = await _get_empresa(db, empresa_activa_id)
    try:
        await service.validar_lote_para_reconciliacion_externa(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
        )
        wsfe_client = await get_wsfe_client(db, current_user, empresa_activa_id)
        lote = await service.reconciliar_emitidos_externos(
            lote_id=lote_id,
            empresa=empresa,
            usuario_id=current_user.id,
            comprobantes=[
                item.model_dump(mode="json") for item in request_body.comprobantes
            ],
            consultar_comprobante=wsfe_client.fe_comp_consultar,
        )
    except LoteComprobanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return LoteAccionResponse(
        lote=_serialize_lote(lote),
        mensaje=lote.mensaje_resumen or "Comprobantes externos reconciliados",
        errores_arca=_errores_arca_lote(lote),
    )


@router.post("/{lote_id}/descartar-grupos", response_model=LoteAccionResponse)
async def descartar_grupos_lote(
    lote_id: int,
    request_body: LoteDescartarGruposRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Descarta grupos pendientes que el usuario decide no emitir."""
    service = LoteComprobantesService(db)
    try:
        lote = await service.descartar_grupos(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            usuario_id=current_user.id,
            grupo_ids=request_body.grupo_ids,
            motivo=request_body.motivo,
        )
    except LoteComprobanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return LoteAccionResponse(
        lote=_serialize_lote(lote),
        mensaje=lote.mensaje_resumen or "Comprobantes descartados",
        errores_arca=_errores_arca_lote(lote),
    )


@router.post("/{lote_id}/compactar", response_model=LoteAccionResponse)
async def compactar_lote(
    lote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Compacta el detalle pesado de filas de un lote cerrado."""
    service = LoteComprobantesService(db)
    try:
        lote = await service.compactar_lote(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            usuario_id=current_user.id,
        )
    except LoteComprobanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return LoteAccionResponse(
        lote=_serialize_lote(lote),
        mensaje="El lote se compactó correctamente.",
        errores_arca=_errores_arca_lote(lote),
    )


@router.delete("/{lote_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_lote(
    lote_id: int,
    request_body: LoteEliminarCompactarRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Elimina físicamente un lote sin comprobantes emitidos ni inciertos."""
    service = LoteComprobantesService(db)
    try:
        await service.eliminar_lote_sin_emision(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            usuario_id=current_user.id,
            motivo=request_body.motivo,
        )
    except LoteComprobanteConflictoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except LoteComprobanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{lote_id}/resumen", response_model=LoteComprobanteResumenResponse)
async def obtener_resumen_lote(
    lote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Obtiene el resumen liviano de un lote."""
    service = LoteComprobantesService(db)
    try:
        lote = await service.obtener_lote_resumen(lote_id, empresa_activa_id)
        resumen_operativo = await service.obtener_resumen_operativo_lote(
            lote_id, empresa_activa_id
        )
    except LoteComprobanteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_lote_resumen(lote, resumen_operativo)


@router.get(
    "/{lote_id}/seguimiento",
    response_model=LoteComprobanteSeguimientoResponse,
)
async def obtener_seguimiento_lote(
    lote_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
) -> LoteComprobanteSeguimientoResponse:
    """Obtiene solo el estado persistido necesario para seguir un lote."""
    service = LoteComprobantesService(db)
    try:
        return await service.obtener_seguimiento_lote(lote_id, empresa_activa_id)
    except LoteComprobanteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{lote_id}/grupos", response_model=LoteComprobanteGruposPageResponse)
async def listar_grupos_lote(
    lote_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=200),
    estado: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Lista los grupos de un lote con paginación server-side."""
    service = LoteComprobantesService(db)
    try:
        grupos, total = await service.obtener_grupos_lote_paginados(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            page=page,
            per_page=per_page,
            estado=estado,
        )
    except LoteComprobanteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    total_pages = (total + per_page - 1) // per_page if total else 0
    return LoteComprobanteGruposPageResponse(
        items=[_serialize_grupo_detalle(grupo) for grupo in grupos],
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        estado=estado,
    )


@router.get("/{lote_id}", response_model=LoteComprobanteDetalleResponse)
async def obtener_lote(
    lote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Obtiene el detalle completo del lote."""
    service = LoteComprobantesService(db)
    try:
        lote = await service.obtener_lote(lote_id, empresa_activa_id)
    except LoteComprobanteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_lote_detalle(lote)


@router.get("/{lote_id}/resultados", response_model=LoteComprobanteDetalleResponse)
async def obtener_resultados_lote(
    lote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Alias semántico para consultar resultados del lote."""
    service = LoteComprobantesService(db)
    try:
        lote = await service.obtener_lote(lote_id, empresa_activa_id)
    except LoteComprobanteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _serialize_lote_detalle(lote)


@router.get("/{lote_id}/archivo-observado")
async def descargar_archivo_observado(
    lote_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Descarga el Excel observado con estado y mensajes por fila."""
    service = LoteComprobantesService(db)
    try:
        contenido = await service.generar_archivo_observado(lote_id, empresa_activa_id)
        lote = await service.obtener_lote(lote_id, empresa_activa_id)
    except LoteComprobanteError as exc:
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if "compactado" in str(exc)
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    stem = Path(lote.nombre_archivo).stem
    filename = f"{stem}-observado.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
