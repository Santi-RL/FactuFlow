"""API para emisión masiva de comprobantes."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_empresa_id, get_current_empresa_user
from app.api.arca import get_wsfe_client
from app.core.config import settings
from app.core.database import get_db
from app.core.date_parsing import parse_fecha_input
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import OperacionIdempotente
from app.models.usuario import Usuario
from app.schemas.lote_comprobante import (
    LoteAccionResponse,
    LoteComprobanteDetalleResponse,
    LoteComprobanteGrupoDetalleResponse,
    LoteComprobanteGruposPageResponse,
    LoteComprobanteResponse,
    LoteComprobanteResumenResponse,
    LoteDescartarGruposRequest,
    LoteEliminarCompactarRequest,
    LoteGrupoIdsRequest,
    LoteProcesamientoResponse,
    LoteReconciliacionExternaRequest,
    LoteValidacionResponse,
)
from app.services.lote_comprobantes_service import (
    LoteComprobanteError,
    LoteComprobantesService,
    OpcionesConceptoLote,
    OpcionesDescripcionItemLote,
    OpcionesFechasLote,
    OpcionesPuntoVentaLote,
)
from app.services.lote_worker import ensure_lote_worker_running
from app.services.idempotencia_fiscal_service import (
    IdempotenciaFiscalError,
    IdempotenciaFiscalService,
)
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


def _estado_operacion_lote_desde_respuesta(response_json: dict) -> str:
    """Mapea una respuesta de lote al estado de operación idempotente."""
    if response_json.get("categoria_error") == "duplicado_logico_lote":
        return "requiere_confirmacion_duplicado"
    lote = response_json.get("lote") or {}
    if lote.get("estado") == "requiere_reconciliacion":
        return "requiere_reconciliacion"
    return "finalizado"


async def _resolver_operacion_lote(
    *,
    db: AsyncSession,
    empresa_id: int,
    usuario_id: int | None,
    idempotency_key: str | None,
    tipo_operacion: str,
    payload: dict,
    lote_id: int,
) -> tuple[IdempotenciaFiscalService, OperacionIdempotente, bool]:
    """Obtiene o crea una operación idempotente de lote."""
    idempotencia = IdempotenciaFiscalService(db)
    payload_hash = idempotencia.calcular_payload_hash(
        idempotencia.payload_sin_confirmacion_duplicado(payload)
    )
    try:
        operacion, creada = await idempotencia.obtener_o_crear_operacion(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            idempotency_key=idempotency_key,
            tipo_operacion=tipo_operacion,
            payload_hash=payload_hash,
            lote_id=lote_id,
        )
    except IdempotenciaFiscalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return idempotencia, operacion, creada


def _lote_puede_emitirse(lote) -> bool:
    return (
        lote.grupos_validos > 0
        and lote.estado in LoteComprobantesService.ESTADOS_PROCESABLES
    )


def _serialize_lote(lote) -> LoteComprobanteResponse:
    return LoteComprobanteResponse.model_validate(lote)


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
        "requiere_reconciliacion",
        "fallido_verificado",
        "rechazado_arca",
    }


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
    await idempotencia.guardar_respuesta_operacion(
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
    try:
        lote = await service.obtener_lote_resumen(lote_id, empresa_activa_id)
    except LoteComprobanteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

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
    idempotencia, operacion, creada = await _resolver_operacion_lote(
        db=db,
        empresa_id=empresa_activa_id,
        usuario_id=current_user.id,
        idempotency_key=x_idempotency_key,
        tipo_operacion="procesar_lote",
        payload={
            "lote_id": lote_id,
            "background": background,
            "confirmacion_fecha_fiscal": x_confirmacion_fecha_fiscal,
            "grupo_ids": material_grupos["grupo_ids"],
            "grupos_hash": material_grupos["grupos_hash"],
        },
        lote_id=lote_id,
    )
    continuar_operacion = creada
    if not creada:
        if operacion.response_json is not None:
            if (
                IdempotenciaFiscalService.requiere_confirmacion_duplicado(
                    operacion.response_json
                )
                and x_confirmacion_duplicado_logico
            ):
                operacion, tomada = await idempotencia.marcar_operacion_en_proceso(
                    operacion
                )
                continuar_operacion = tomada
            elif "categoria_error" in operacion.response_json:
                _raise_error_operacion_lote(operacion.response_json)
            elif _operacion_lote_esta_cerrada(operacion):
                return LoteProcesamientoResponse.model_validate(operacion.response_json)
        if not continuar_operacion:
            lote_actual = await service.obtener_lote_resumen(lote_id, empresa_activa_id)
            respuesta_actual = LoteProcesamientoResponse(
                lote=_serialize_lote(lote_actual),
                mensaje=lote_actual.mensaje_resumen or "La operación está en curso.",
                en_progreso=lote_actual.estado in {"en_cola", "procesando"},
            )
            if not respuesta_actual.en_progreso and lote_actual.estado in {
                "completado",
                "con_errores",
                "requiere_reconciliacion",
            }:
                await idempotencia.guardar_respuesta_operacion(
                    operacion,
                    response_json=respuesta_actual,
                    estado=_estado_operacion_lote_desde_respuesta(
                        respuesta_actual.model_dump(mode="json")
                    ),
                )
            return respuesta_actual

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
            await idempotencia.guardar_respuesta_operacion(
                operacion,
                response_json=detail,
                estado="requiere_confirmacion_duplicado",
            )
            raise HTTPException(status_code=409, detail=detail)

    if background or lote.total_grupos > settings.batch_sync_limit:
        lote = await service.encolar_lote(
            lote_id,
            empresa_activa_id,
            operacion_id=operacion.id,
            confirmacion_duplicado_logico=confirmacion_duplicado_ok,
        )
        if lote.estado != "procesando":
            ensure_lote_worker_running(request.app)
            mensaje = "El lote quedó en cola y se está procesando en segundo plano."
        else:
            mensaje = "El lote ya está siendo procesado."
        respuesta = LoteProcesamientoResponse(
            lote=_serialize_lote(lote),
            mensaje=mensaje,
            en_progreso=True,
        )
        await idempotencia.guardar_respuesta_operacion(
            operacion,
            response_json=respuesta,
            estado="en_proceso",
        )
        return respuesta

    try:
        lote = await service.procesar_lote(
            lote_id,
            empresa_activa_id,
            operacion_id=operacion.id,
            usuario_id=current_user.id,
            confirmacion_duplicado_logico=confirmacion_duplicado_ok,
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
    )
    await idempotencia.guardar_respuesta_operacion(
        operacion,
        response_json=respuesta,
        estado=_estado_operacion_lote_desde_respuesta(
            respuesta.model_dump(mode="json")
        ),
    )
    return respuesta


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
    grupo_ids = request_body.grupo_ids or None
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
        idempotencia, operacion, creada = await _resolver_operacion_lote(
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
        )
        continuar_operacion = creada
        if not creada:
            if operacion.response_json is not None:
                if (
                    IdempotenciaFiscalService.requiere_confirmacion_duplicado(
                        operacion.response_json
                    )
                    and x_confirmacion_duplicado_logico
                ):
                    operacion, tomada = await idempotencia.marcar_operacion_en_proceso(
                        operacion
                    )
                    continuar_operacion = tomada
                elif "categoria_error" in operacion.response_json:
                    _raise_error_operacion_lote(operacion.response_json)
                elif _operacion_lote_esta_cerrada(operacion):
                    return LoteAccionResponse.model_validate(operacion.response_json)
            if not continuar_operacion:
                lote_actual = await service.obtener_lote_resumen(
                    lote_id,
                    empresa_activa_id,
                )
                respuesta_actual = LoteAccionResponse(
                    lote=_serialize_lote(lote_actual),
                    mensaje=lote_actual.mensaje_resumen
                    or "La operación está en curso.",
                )
                if lote_actual.estado in {
                    "completado",
                    "con_errores",
                    "requiere_reconciliacion",
                    "cerrado_reconciliado",
                }:
                    await idempotencia.guardar_respuesta_operacion(
                        operacion,
                        response_json=respuesta_actual,
                        estado=_estado_operacion_lote_desde_respuesta(
                            respuesta_actual.model_dump(mode="json")
                        ),
                    )
                return respuesta_actual

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
                await idempotencia.guardar_respuesta_operacion(
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
            confirmacion_duplicado_logico=confirmacion_duplicado_ok,
        )
    except HTTPException:
        raise
    except LoteComprobanteError as exc:
        if "idempotencia" in locals() and "operacion" in locals():
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
    )
    await idempotencia.guardar_respuesta_operacion(
        operacion,
        response_json=respuesta,
        estado=_estado_operacion_lote_desde_respuesta(
            respuesta.model_dump(mode="json")
        ),
    )
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
