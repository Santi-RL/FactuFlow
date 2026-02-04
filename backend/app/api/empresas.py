"""Endpoints de Empresas."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin_user
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.schemas.empresa import EmpresaCreate, EmpresaUpdate, EmpresaResponse

router = APIRouter()


@router.get("", response_model=list[EmpresaResponse])
async def list_empresas(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
):
    """
    Listar todas las empresas (solo admin).

    Args:
        db: Sesión de base de datos
        current_user: Usuario administrador autenticado

    Returns:
        Lista de empresas
    """
    result = await db.execute(select(Empresa))
    empresas = result.scalars().all()
    return empresas


@router.post("", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
async def create_empresa(
    empresa_data: EmpresaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
):
    """
    Crear una nueva empresa (solo admin).

    Args:
        empresa_data: Datos de la empresa
        db: Sesión de base de datos
        current_user: Usuario administrador autenticado

    Returns:
        Empresa creada

    Raises:
        HTTPException: Si el CUIT ya existe
    """
    # Verificar que el CUIT no exista
    result = await db.execute(select(Empresa).where(Empresa.cuit == empresa_data.cuit))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una empresa con el CUIT {empresa_data.cuit}",
        )

    # Crear empresa
    nueva_empresa = Empresa(**empresa_data.model_dump())
    db.add(nueva_empresa)
    await db.commit()
    await db.refresh(nueva_empresa)

    return nueva_empresa


@router.get("/{empresa_id}", response_model=EmpresaResponse)
async def get_empresa(
    empresa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtener una empresa por ID.

    Args:
        empresa_id: ID de la empresa
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Empresa

    Raises:
        HTTPException: Si la empresa no existe o el usuario no tiene permiso
    """
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
        )

    # Verificar permisos: solo admin o usuario de la misma empresa
    if not current_user.es_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta empresa",
        )

    return empresa


@router.put("/{empresa_id}", response_model=EmpresaResponse)
async def update_empresa(
    empresa_id: int,
    empresa_data: EmpresaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualizar una empresa.

    Args:
        empresa_id: ID de la empresa
        empresa_data: Datos a actualizar
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Empresa actualizada

    Raises:
        HTTPException: Si la empresa no existe o el usuario no tiene permiso
    """
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
        )

    # Verificar permisos: solo admin o usuario de la misma empresa
    if not current_user.es_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar esta empresa",
        )

    # Actualizar campos
    update_data = empresa_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(empresa, field, value)

    await db.commit()
    await db.refresh(empresa)

    return empresa


@router.delete("/{empresa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_empresa(
    empresa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
):
    """
    Eliminar una empresa (solo admin).

    Args:
        empresa_id: ID de la empresa
        db: Sesión de base de datos
        current_user: Usuario administrador autenticado

    Raises:
        HTTPException: Si la empresa no existe
    """
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
        )

    await db.delete(empresa)
    await db.commit()
