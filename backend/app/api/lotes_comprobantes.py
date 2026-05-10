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
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_empresa_id, get_current_empresa_user
from app.core.config import settings
from app.core.database import get_db
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.schemas.lote_comprobante import (
    LoteComprobanteDetalleResponse,
    LoteComprobanteResponse,
    LoteProcesamientoResponse,
    LoteValidacionResponse,
)
from app.services.lote_comprobantes_service import (
    LoteComprobanteError,
    LoteComprobantesService,
    OpcionesConceptoLote,
    OpcionesDescripcionItemLote,
    OpcionesFechasLote,
)
from app.services.lote_worker import ensure_lote_worker_running
from app.services.perfiles_carga_masiva_service import (
    PerfilCargaMasivaError,
    PerfilesCargaMasivaService,
)

logger = logging.getLogger(__name__)
router = APIRouter()
CONFIRMACION_FECHA_FISCAL_HEADER = "true"


def _serialize_lote(lote) -> LoteComprobanteResponse:
    return LoteComprobanteResponse.model_validate(lote)


def _serialize_lote_detalle(lote) -> LoteComprobanteDetalleResponse:
    return LoteComprobanteDetalleResponse.model_validate(lote)


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

    contenido = await archivo.read()
    empresa = await _get_empresa(db, empresa_activa_id)
    service = LoteComprobantesService(db)
    opciones_concepto = OpcionesConceptoLote(concepto_modo=concepto_modo)
    opciones_descripcion_item = OpcionesDescripcionItemLote(
        descripcion_item_modo=descripcion_item_modo,
        descripcion_item_fija=descripcion_item_fija,
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
            formato_version_id=formato_version_id,
            perfil_carga_masiva_snapshot=perfil_snapshot,
        )
    except LoteComprobanteError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return LoteValidacionResponse(
        lote=_serialize_lote(lote),
        puede_emitirse=lote.grupos_validos > 0,
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
    if x_confirmacion_fecha_fiscal != CONFIRMACION_FECHA_FISCAL_HEADER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Antes de emitir debes confirmar la fecha fiscal. "
                "Está seguro que quiere emitir comprobantes con fecha "
                "XX/XX/XX? Recuerde que luego no podrá emitir comprobantes "
                "con fecha anterior para ese mismo punto de venta."
            ),
        )

    service = LoteComprobantesService(db)
    try:
        lote = await service.obtener_lote(lote_id, empresa_activa_id)
    except LoteComprobanteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if lote.grupos_validos == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El lote no tiene comprobantes válidos para emitir",
        )

    if background or lote.total_grupos > settings.batch_sync_limit:
        lote = await service.encolar_lote(lote_id, empresa_activa_id)
        ensure_lote_worker_running(request.app)
        return LoteProcesamientoResponse(
            lote=_serialize_lote(lote),
            mensaje="El lote quedó en cola y se está procesando en segundo plano.",
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    stem = Path(lote.nombre_archivo).stem
    filename = f"{stem}-observado.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
