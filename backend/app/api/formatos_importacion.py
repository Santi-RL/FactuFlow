"""API para formatos configurables de importación."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_empresa_id, get_current_empresa_user
from app.core.database import get_db
from app.models.formato_importacion import FormatoImportacion
from app.models.usuario import Usuario
from app.schemas.formato_importacion import (
    FormatoImportacionCandidatoResponse,
    FormatoImportacionCreate,
    FormatoImportacionDeteccionResponse,
    FormatoImportacionResponse,
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


@router.post(
    "",
    response_model=FormatoImportacionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_formato_importacion(
    data: FormatoImportacionCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Crea un formato configurable particular del emisor activo."""
    service = FormatosImportacionService(db)
    formato = await service.crear_formato(
        empresa_id=empresa_id,
        nombre=data.nombre,
        descripcion=data.descripcion,
        configuracion=data.configuracion_json,
    )
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

    contenido = await archivo.read()
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
    return FormatoImportacionDeteccionResponse(
        headers_detectados=headers,
        candidatos=[
            FormatoImportacionCandidatoResponse(**candidato.__dict__)
            for candidato in candidatos
        ],
        formato_sugerido_version_id=(sugerido.formato_version_id if sugerido else None),
        requiere_confirmacion=True,
    )
