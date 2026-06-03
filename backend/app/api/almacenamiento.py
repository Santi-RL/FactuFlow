"""Endpoints administrativos del gestor de almacenamiento."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.usuario import Usuario
from app.schemas.almacenamiento import (
    AccionAlmacenamientoResponse,
    ConfirmarDescargaExportacionRequest,
    AlmacenamientoItemResponse,
    AlmacenamientoResumenResponse,
    ConfirmarLiberacionRequest,
    CrearExportacionAlmacenamientoRequest,
    ExportacionAlmacenamientoResponse,
    LimpiarArchivosAlmacenamientoRequest,
    LoteCompactableResponse,
)
from app.services.almacenamiento_service import (
    AlmacenamientoError,
    AlmacenamientoService,
    StorageFileCandidate,
)

router = APIRouter()


def _http_error(exc: AlmacenamientoError) -> HTTPException:
    """Convierte errores del servicio en respuestas HTTP de negocio."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _serialize_candidate(candidate: StorageFileCandidate) -> AlmacenamientoItemResponse:
    """Serializa un archivo candidato sin rutas absolutas."""
    return AlmacenamientoItemResponse(
        id=candidate.id,
        nombre=candidate.nombre,
        categoria=candidate.categoria,
        bytes_usados=candidate.bytes_usados,
        bytes_recuperables=candidate.bytes_usados,
        descripcion=candidate.descripcion,
        created_at=candidate.created_at,
    )


def _serialize_exportacion(exportacion) -> ExportacionAlmacenamientoResponse:
    """Serializa una exportación de almacenamiento."""
    return ExportacionAlmacenamientoResponse(
        token=exportacion.token,
        estado=exportacion.estado,
        archivo_nombre=exportacion.archivo_nombre,
        checksum_sha256=exportacion.checksum_sha256,
        size_bytes=exportacion.size_bytes,
        created_at=exportacion.created_at,
        downloaded_at=exportacion.downloaded_at,
        released_at=exportacion.released_at,
        manifest=exportacion.manifest_json or {},
    )


@router.get("/resumen", response_model=AlmacenamientoResumenResponse)
async def obtener_resumen_almacenamiento(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """Devuelve uso de almacenamiento para diagnóstico administrativo."""
    service = AlmacenamientoService(db)
    return await service.obtener_resumen()


@router.get("/lotes-compactables", response_model=list[LoteCompactableResponse])
async def listar_lotes_compactables(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """Lista lotes cerrados cuyo detalle puede resguardarse y compactarse."""
    service = AlmacenamientoService(db)
    return await service.listar_lotes_compactables()


@router.get("/logs", response_model=list[AlmacenamientoItemResponse])
async def listar_logs_antiguos(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """Lista logs antiguos o rotados disponibles para resguardo o limpieza."""
    service = AlmacenamientoService(db)
    return [_serialize_candidate(item) for item in service.listar_logs_antiguos()]


@router.get("/temporales", response_model=list[AlmacenamientoItemResponse])
async def listar_temporales(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """Lista archivos temporales administrados."""
    service = AlmacenamientoService(db)
    return [_serialize_candidate(item) for item in service.listar_temporales()]


@router.get("/certificados-huerfanos", response_model=list[AlmacenamientoItemResponse])
async def listar_certificados_huerfanos(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """Lista certificados gestionados sin referencia activa en base."""
    service = AlmacenamientoService(db)
    return [
        _serialize_candidate(item)
        for item in await service.listar_certificados_huerfanos()
    ]


@router.post("/exportaciones", response_model=ExportacionAlmacenamientoResponse)
async def crear_exportacion(
    request: CrearExportacionAlmacenamientoRequest,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin_user),
):
    """Prepara un ZIP de resguardo antes de liberar espacio."""
    service = AlmacenamientoService(db)
    try:
        exportacion = await service.crear_exportacion(
            request.model_dump(), usuario_id=admin.id
        )
    except AlmacenamientoError as exc:
        raise _http_error(exc) from exc
    return _serialize_exportacion(exportacion)


@router.get("/exportaciones/{token}/descargar")
async def descargar_exportacion(
    token: str,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin_user),
):
    """Descarga una exportación por token opaco."""
    service = AlmacenamientoService(db)
    try:
        exportacion, download_token = await service.preparar_descarga_exportacion(token)
        path = service.exportacion_path(exportacion)
    except AlmacenamientoError as exc:
        raise _http_error(exc) from exc
    return FileResponse(
        path=path,
        media_type="application/zip",
        filename=exportacion.archivo_nombre,
        headers={
            "X-FactuFlow-Download-Token": download_token,
            "Access-Control-Expose-Headers": "X-FactuFlow-Download-Token",
        },
    )


@router.post(
    "/exportaciones/{token}/confirmar-descarga",
    response_model=ExportacionAlmacenamientoResponse,
)
async def confirmar_descarga_exportacion(
    token: str,
    request: ConfirmarDescargaExportacionRequest,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin_user),
):
    """Confirma explícitamente que el ZIP fue descargado por el cliente."""
    service = AlmacenamientoService(db)
    try:
        exportacion = await service.confirmar_descarga_exportacion(
            token,
            request.checksum_sha256,
            request.download_token,
            usuario_id=admin.id,
        )
    except AlmacenamientoError as exc:
        raise _http_error(exc) from exc
    return _serialize_exportacion(exportacion)


@router.post(
    "/exportaciones/{token}/confirmar-liberacion",
    response_model=AccionAlmacenamientoResponse,
)
async def confirmar_liberacion_exportacion(
    token: str,
    request: ConfirmarLiberacionRequest,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin_user),
):
    """Libera espacio después de confirmar que el ZIP fue descargado."""
    service = AlmacenamientoService(db)
    try:
        result = await service.confirmar_liberacion(
            token, request.confirmacion, usuario_id=admin.id
        )
    except AlmacenamientoError as exc:
        raise _http_error(exc) from exc
    return AccionAlmacenamientoResponse(
        mensaje=result["mensaje"],
        bytes_afectados=result["bytes"],
        items_afectados=result["items"],
    )


@router.post(
    "/certificados-huerfanos/limpiar",
    response_model=AccionAlmacenamientoResponse,
)
async def limpiar_certificados_huerfanos(
    request: LimpiarArchivosAlmacenamientoRequest,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin_user),
):
    """Elimina certificados huérfanos gestionados y no referenciados."""
    service = AlmacenamientoService(db)
    try:
        result = await service.limpiar_certificados_huerfanos(
            request.ids, usuario_id=admin.id
        )
    except AlmacenamientoError as exc:
        raise _http_error(exc) from exc
    return AccionAlmacenamientoResponse(
        mensaje=result["mensaje"],
        bytes_afectados=result["bytes"],
        items_afectados=result["items"],
    )
