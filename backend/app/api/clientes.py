"""Endpoints de Clientes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.api.deps import get_current_empresa_user
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.schemas.cliente import (
    ClienteCreate,
    ClienteUpdate,
    ClienteResponse,
    ClienteList,
)

router = APIRouter()


@router.get("", response_model=ClienteList)
async def list_clientes(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    search: Optional[str] = None,
    activo: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Listar clientes con paginación y búsqueda.

    Args:
        page: Número de página
        per_page: Resultados por página
        search: Término de búsqueda (razon_social, numero_documento)
        activo: Filtrar por estado activo/inactivo
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Lista paginada de clientes
    """
    # Base query: solo clientes de la empresa del usuario (o todos si es admin)
    query = select(Cliente)

    if not current_user.es_admin:
        query = query.where(Cliente.empresa_id == current_user.empresa_id)

    # Filtrar por búsqueda
    if search:
        search_filter = or_(
            Cliente.razon_social.ilike(f"%{search}%"),
            Cliente.numero_documento.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)

    # Filtrar por activo
    if activo is not None:
        query = query.where(Cliente.activo == activo)

    # Contar total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginación
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    # Ejecutar query
    result = await db.execute(query)
    clientes = result.scalars().all()

    # Calcular páginas
    pages = (total + per_page - 1) // per_page

    return {
        "items": clientes,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.post("", response_model=ClienteResponse, status_code=status.HTTP_201_CREATED)
async def create_cliente(
    cliente_data: ClienteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Crear un nuevo cliente.

    Args:
        cliente_data: Datos del cliente
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Cliente creado
    """
    # Crear cliente asociado a la empresa del usuario
    nuevo_cliente = Cliente(
        **cliente_data.model_dump(), empresa_id=current_user.empresa_id
    )

    db.add(nuevo_cliente)
    await db.commit()
    await db.refresh(nuevo_cliente)

    return nuevo_cliente


@router.get("/{cliente_id}", response_model=ClienteResponse)
async def get_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtener un cliente por ID.

    Args:
        cliente_id: ID del cliente
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Cliente

    Raises:
        HTTPException: Si el cliente no existe o no pertenece a la empresa
    """
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    cliente = result.scalar_one_or_none()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )

    # Verificar que pertenezca a la empresa del usuario (o sea admin)
    if not current_user.es_admin and cliente.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este cliente",
        )

    return cliente


@router.put("/{cliente_id}", response_model=ClienteResponse)
async def update_cliente(
    cliente_id: int,
    cliente_data: ClienteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Actualizar un cliente.

    Args:
        cliente_id: ID del cliente
        cliente_data: Datos a actualizar
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Cliente actualizado

    Raises:
        HTTPException: Si el cliente no existe o no pertenece a la empresa
    """
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    cliente = result.scalar_one_or_none()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )

    # Verificar permisos
    if not current_user.es_admin and cliente.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar este cliente",
        )

    # Actualizar campos
    update_data = cliente_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cliente, field, value)

    await db.commit()
    await db.refresh(cliente)

    return cliente


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Desactivar un cliente (soft delete).

    Args:
        cliente_id: ID del cliente
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Raises:
        HTTPException: Si el cliente no existe o no pertenece a la empresa
    """
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    cliente = result.scalar_one_or_none()

    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )

    # Verificar permisos
    if not current_user.es_admin and cliente.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este cliente",
        )

    # Soft delete: marcar como inactivo
    cliente.activo = False
    await db.commit()
