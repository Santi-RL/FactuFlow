"""API para perfiles de carga masiva por emisor."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_empresa_id, get_current_empresa_user
from app.core.database import get_db
from app.models.usuario import Usuario
from app.schemas.perfil_carga_masiva import (
    PerfilCargaMasivaCreate,
    PerfilCargaMasivaResponse,
    PerfilCargaMasivaUpdate,
)
from app.services.perfiles_carga_masiva_service import (
    PerfilCargaMasivaError,
    PerfilesCargaMasivaService,
)

router = APIRouter()


@router.get("", response_model=list[PerfilCargaMasivaResponse])
async def listar_perfiles_carga_masiva(
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Lista perfiles de carga masiva del emisor activo."""
    service = PerfilesCargaMasivaService(db)
    return await service.listar(empresa_id)


@router.post(
    "",
    response_model=PerfilCargaMasivaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def crear_perfil_carga_masiva(
    data: PerfilCargaMasivaCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Crea un perfil de carga masiva para el emisor activo."""
    service = PerfilesCargaMasivaService(db)
    try:
        return await service.crear(
            empresa_id=empresa_id,
            nombre=data.nombre,
            descripcion=data.descripcion,
            configuracion=data.configuracion_json,
            es_predeterminado=data.es_predeterminado,
            activo=data.activo,
        )
    except PerfilCargaMasivaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{perfil_id}", response_model=PerfilCargaMasivaResponse)
async def actualizar_perfil_carga_masiva(
    perfil_id: int,
    data: PerfilCargaMasivaUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Actualiza un perfil de carga masiva del emisor activo."""
    service = PerfilesCargaMasivaService(db)
    try:
        return await service.actualizar(
            perfil_id,
            empresa_id,
            data.model_dump(exclude_unset=True),
        )
    except PerfilCargaMasivaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{perfil_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_perfil_carga_masiva(
    perfil_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Elimina un perfil de carga masiva del emisor activo."""
    service = PerfilesCargaMasivaService(db)
    try:
        await service.eliminar(perfil_id, empresa_id)
    except PerfilCargaMasivaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{perfil_id}/predeterminado",
    response_model=PerfilCargaMasivaResponse,
)
async def marcar_perfil_carga_masiva_predeterminado(
    perfil_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Marca un perfil como predeterminado del emisor activo."""
    service = PerfilesCargaMasivaService(db)
    try:
        return await service.marcar_predeterminado(perfil_id, empresa_id)
    except PerfilCargaMasivaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
