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
from app.models.empresa import Empresa
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
from app.services.perfiles_carga_masiva_service import (
    PerfilCargaMasivaError,
    PerfilesCargaMasivaService,
)

logger = logging.getLogger(__name__)
router = APIRouter()


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
    fecha_emision_fija: date | None = Form(None),
    fecha_servicio_desde_modo: str = Form(...),
    fecha_servicio_desde_fija: date | None = Form(None),
    fecha_servicio_hasta_modo: str = Form(...),
    fecha_servicio_hasta_fija: date | None = Form(None),
    fecha_vto_pago_modo: str = Form(...),
    fecha_vto_pago_fija: date | None = Form(None),
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
        fecha_emision_fija=fecha_emision_fija,
        fecha_servicio_desde_modo=fecha_servicio_desde_modo,
        fecha_servicio_desde_fija=fecha_servicio_desde_fija,
        fecha_servicio_hasta_modo=fecha_servicio_hasta_modo,
        fecha_servicio_hasta_fija=fecha_servicio_hasta_fija,
        fecha_vto_pago_modo=fecha_vto_pago_modo,
        fecha_vto_pago_fija=fecha_vto_pago_fija,
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

    if lote.grupos_validos == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El lote no tiene comprobantes válidos para emitir",
        )

    resumen_operativo = await service.obtener_resumen_operativo_lote(
        lote_id, empresa_activa_id
    )
    confirmacion_esperada = resumen_operativo["confirmacion_fecha_fiscal"]
    mensaje_confirmacion = resumen_operativo["mensaje_confirmacion_fecha_fiscal"]
    if x_confirmacion_fecha_fiscal != confirmacion_esperada:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Antes de emitir debes confirmar la fecha fiscal exacta del lote. "
                f"{mensaje_confirmacion} "
                "Volvé a confirmar desde la pantalla del lote antes de procesar."
            ),
        )

    if background or lote.total_grupos > settings.batch_sync_limit:
        lote = await service.encolar_lote(lote_id, empresa_activa_id)
        if lote.estado != "procesando":
            ensure_lote_worker_running(request.app)
            mensaje = "El lote quedó en cola y se está procesando en segundo plano."
        else:
            mensaje = "El lote ya está siendo procesado."
        return LoteProcesamientoResponse(
            lote=_serialize_lote(lote),
            mensaje=mensaje,
            en_progreso=True,
        )

    try:
        lote = await service.procesar_lote(lote_id, empresa_activa_id)
    except LoteComprobanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return LoteProcesamientoResponse(
        lote=_serialize_lote(lote),
        mensaje=lote.mensaje_resumen or "Lote procesado",
        en_progreso=False,
    )


@router.post("/{lote_id}/reintentar-fallidos", response_model=LoteAccionResponse)
async def reintentar_fallidos_lote(
    lote_id: int,
    request_body: LoteGrupoIdsRequest = Body(default_factory=LoteGrupoIdsRequest),
    x_confirmacion_fecha_fiscal: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """Reintenta grupos fallidos del lote con confirmación fiscal exacta."""
    service = LoteComprobantesService(db)
    grupo_ids = request_body.grupo_ids or None
    try:
        confirmacion = await service.obtener_confirmacion_fiscal_grupos(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            estados={"fallido"},
            grupo_ids=grupo_ids,
        )
        if x_confirmacion_fecha_fiscal != confirmacion["confirmacion_fecha_fiscal"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Antes de reintentar debes confirmar la fecha fiscal exacta. "
                    f"{confirmacion['mensaje_confirmacion_fecha_fiscal']}"
                ),
            )
        lote = await service.reintentar_grupos_fallidos(
            lote_id=lote_id,
            empresa_id=empresa_activa_id,
            usuario_id=current_user.id,
            grupo_ids=grupo_ids,
        )
    except HTTPException:
        raise
    except LoteComprobanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return LoteAccionResponse(
        lote=_serialize_lote(lote),
        mensaje=lote.mensaje_resumen or "Reintento finalizado",
    )


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
