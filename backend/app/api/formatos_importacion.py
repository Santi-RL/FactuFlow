"""API para formatos configurables de importación."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_empresa_id, get_current_empresa_user
from app.core.config import settings
from app.core.database import get_db
from app.models.formato_importacion import FormatoImportacion
from app.models.usuario import Usuario
from app.schemas.formato_importacion import (
    FormatoImportacionCampoCatalogoResponse,
    FormatoImportacionCandidatoResponse,
    FormatoImportacionClone,
    FormatoImportacionCompatibilidadMensaje,
    FormatoImportacionCompatibilidadRequest,
    FormatoImportacionCompatibilidadResponse,
    FormatoImportacionCreate,
    FormatoImportacionDeteccionResponse,
    FormatoImportacionExcelAnalisisResponse,
    FormatoImportacionExcelColumnaResponse,
    FormatoImportacionResponse,
    FormatoImportacionUpdate,
    FormatoImportacionVersionResponse,
)
from app.services.formatos_importacion_service import (
    FormatoImportacionError,
    FormatosImportacionService,
)
from app.services.lote_comprobantes_service import LoteComprobantesService

router = APIRouter()


def _serialize_formato(formato: FormatoImportacion) -> FormatoImportacionResponse:
    versiones = [
        version for version in formato.versiones if version.estado == "vigente"
    ]
    version_vigente = (
        sorted(
            versiones,
            key=lambda version: version.version,
            reverse=True,
        )[0]
        if versiones
        else None
    )
    return FormatoImportacionResponse(
        id=formato.id,
        nombre=formato.nombre,
        descripcion=formato.descripcion,
        alcance=formato.alcance,
        activo=formato.activo,
        empresa_id=formato.empresa_id,
        created_at=formato.created_at,
        updated_at=formato.updated_at,
        version_vigente=(
            FormatoImportacionVersionResponse.model_validate(version_vigente)
            if version_vigente
            else None
        ),
    )


def _requiere_admin_para_global(
    usuario: Usuario,
    *,
    alcance_solicitado: str | None = None,
    formato_actual: FormatoImportacion | None = None,
) -> None:
    """Impide que usuarios comunes modifiquen plantillas globales."""
    afecta_global = alcance_solicitado == "global" or (
        formato_actual is not None and formato_actual.alcance == "global"
    )
    if afecta_global and not usuario.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede crear o modificar plantillas globales",
        )


@router.get("", response_model=list[FormatoImportacionResponse])
async def listar_formatos_importacion(
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Lista formatos globales y particulares del emisor activo."""
    service = FormatosImportacionService(db)
    formatos = await service.listar_formatos(empresa_id)
    return [_serialize_formato(formato) for formato in formatos]


@router.get(
    "/catalogo-campos",
    response_model=list[FormatoImportacionCampoCatalogoResponse],
)
async def catalogo_campos_formatos_importacion(
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
):
    """Lista campos disponibles para el constructor visual de plantillas."""
    service = FormatosImportacionService(db)
    return [
        FormatoImportacionCampoCatalogoResponse(**campo)
        for campo in service.catalogo_campos()
    ]


@router.post("/analizar-excel", response_model=FormatoImportacionExcelAnalisisResponse)
async def analizar_excel_formato_importacion(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
):
    """Lee encabezados de un Excel de ejemplo para iniciar una plantilla."""
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes subir un archivo Excel .xlsx",
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
    service = FormatosImportacionService(db)
    try:
        analisis = service.analizar_excel(contenido)
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return FormatoImportacionExcelAnalisisResponse(
        hoja=analisis.hoja,
        fila_encabezado=analisis.fila_encabezado,
        columnas=[
            FormatoImportacionExcelColumnaResponse(**columna.__dict__)
            for columna in analisis.columnas
        ],
    )


@router.post(
    "/compatibilidad",
    response_model=FormatoImportacionCompatibilidadResponse,
)
async def evaluar_compatibilidad_formato_importacion(
    data: FormatoImportacionCompatibilidadRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Evalúa plantilla, perfil y emisor antes de guardar o descargar."""
    service = FormatosImportacionService(db)
    try:
        resultado = await service.evaluar_compatibilidad(
            configuracion=data.configuracion_json,
            empresa_id=empresa_id,
            perfil_configuracion=data.perfil_configuracion_json,
        )
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    def serializar_mensaje(mensaje) -> FormatoImportacionCompatibilidadMensaje:
        return FormatoImportacionCompatibilidadMensaje(**mensaje.__dict__)

    return FormatoImportacionCompatibilidadResponse(
        estado=resultado.estado,
        faltantes=[serializar_mensaje(item) for item in resultado.faltantes],
        omitibles=[serializar_mensaje(item) for item in resultado.omitibles],
        advertencias=[serializar_mensaje(item) for item in resultado.advertencias],
        conflictos=[serializar_mensaje(item) for item in resultado.conflictos],
    )


@router.post(
    "",
    response_model=FormatoImportacionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_formato_importacion(
    data: FormatoImportacionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Crea una plantilla configurable para carga masiva."""
    _requiere_admin_para_global(current_user, alcance_solicitado=data.alcance)
    service = FormatosImportacionService(db)
    try:
        formato = await service.crear_formato(
            empresa_id=empresa_id,
            nombre=data.nombre,
            descripcion=data.descripcion,
            configuracion=data.configuracion_json,
            alcance=data.alcance,
        )
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    formatos = await service.listar_formatos(empresa_id)
    creado = next(item for item in formatos if item.id == formato.id)
    return _serialize_formato(creado)


@router.post("/detectar", response_model=FormatoImportacionDeteccionResponse)
async def detectar_formato_importacion(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Detecta formatos posibles a partir de encabezados de un Excel."""
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes subir un archivo Excel .xlsx",
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
    service = FormatosImportacionService(db)
    try:
        headers, candidatos = await service.detectar_formato(
            contenido,
            empresa_id,
            LoteComprobantesService.TEMPLATE_COLUMNS,
        )
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    sugerido = next(
        (
            candidato
            for candidato in candidatos
            if candidato.confianza == "alta" and candidato.score >= 0.85
        ),
        None,
    )
    if await service.hay_ambiguedad_fiscal_entre_candidatos(candidatos, empresa_id):
        sugerido = None
    return FormatoImportacionDeteccionResponse(
        headers_detectados=headers,
        candidatos=[
            FormatoImportacionCandidatoResponse(**candidato.__dict__)
            for candidato in candidatos
        ],
        formato_sugerido_version_id=(sugerido.formato_version_id if sugerido else None),
        requiere_confirmacion=True,
    )


@router.get("/{formato_id}", response_model=FormatoImportacionResponse)
async def obtener_formato_importacion(
    formato_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Obtiene el detalle de una plantilla accesible."""
    service = FormatosImportacionService(db)
    try:
        formato = await service.obtener_formato(formato_id, empresa_id)
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _serialize_formato(formato)


@router.put("/{formato_id}", response_model=FormatoImportacionResponse)
async def actualizar_formato_importacion(
    formato_id: int,
    data: FormatoImportacionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Actualiza una plantilla y versiona el mapeo vigente."""
    service = FormatosImportacionService(db)
    try:
        formato_actual = await service.obtener_formato(formato_id, empresa_id)
        _requiere_admin_para_global(
            current_user,
            alcance_solicitado=data.alcance,
            formato_actual=formato_actual,
        )
        formato = await service.actualizar_formato(
            formato_id=formato_id,
            empresa_id=empresa_id,
            nombre=data.nombre,
            descripcion=data.descripcion,
            actualizar_descripcion="descripcion" in data.model_fields_set,
            alcance=data.alcance,
            configuracion=data.configuracion_json,
        )
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _serialize_formato(formato)


@router.delete("/{formato_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desactivar_formato_importacion(
    formato_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Desactiva una plantilla sin borrar versiones históricas."""
    service = FormatosImportacionService(db)
    try:
        formato_actual = await service.obtener_formato(formato_id, empresa_id)
        _requiere_admin_para_global(current_user, formato_actual=formato_actual)
        await service.desactivar_formato(formato_id, empresa_id)
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{formato_id}/clonar",
    response_model=FormatoImportacionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clonar_formato_importacion(
    formato_id: int,
    data: FormatoImportacionClone,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Clona una plantilla global, de emisor o protegida del sistema."""
    _requiere_admin_para_global(current_user, alcance_solicitado=data.alcance)
    service = FormatosImportacionService(db)
    try:
        formato = await service.clonar_formato(
            formato_id=formato_id,
            empresa_id=empresa_id,
            nombre=data.nombre,
            alcance=data.alcance,
        )
        formatos = await service.listar_formatos(empresa_id)
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    clonado = next(item for item in formatos if item.id == formato.id)
    return _serialize_formato(clonado)


@router.get("/{formato_id}/descargar")
async def descargar_formato_importacion(
    formato_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Descarga un .xlsx generado desde la plantilla visual."""
    service = FormatosImportacionService(db)
    try:
        contenido, filename = await service.generar_excel_formato(
            formato_id,
            empresa_id,
        )
    except FormatoImportacionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return Response(
        content=contenido,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
