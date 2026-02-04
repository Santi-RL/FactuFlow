"""Endpoints de Puntos de Venta."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_empresa_user
from app.models.usuario import Usuario
from app.models.punto_venta import PuntoVenta
from app.schemas.punto_venta import (
    PuntoVentaCreate,
    PuntoVentaUpdate,
    PuntoVentaResponse,
)

router = APIRouter()


@router.get("", response_model=list[PuntoVentaResponse])
async def list_puntos_venta(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Listar puntos de venta.

    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Lista de puntos de venta
    """
    query = select(PuntoVenta)

    if not current_user.es_admin:
        query = query.where(PuntoVenta.empresa_id == current_user.empresa_id)

    result = await db.execute(query)
    puntos_venta = result.scalars().all()

    return puntos_venta


@router.post("", response_model=PuntoVentaResponse, status_code=status.HTTP_201_CREATED)
async def create_punto_venta(
    punto_venta_data: PuntoVentaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Crear un nuevo punto de venta.

    Args:
        punto_venta_data: Datos del punto de venta
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Punto de venta creado

    Raises:
        HTTPException: Si ya existe un punto de venta con ese número
    """
    # Verificar que no exista otro punto de venta con ese número en la empresa
    result = await db.execute(
        select(PuntoVenta).where(
            PuntoVenta.empresa_id == current_user.empresa_id,
            PuntoVenta.numero == punto_venta_data.numero,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un punto de venta con el número {punto_venta_data.numero}",
        )

    # Crear punto de venta
    nuevo_punto_venta = PuntoVenta(
        **punto_venta_data.model_dump(), empresa_id=current_user.empresa_id
    )

    db.add(nuevo_punto_venta)
    await db.commit()
    await db.refresh(nuevo_punto_venta)

    return nuevo_punto_venta


@router.put("/{punto_venta_id}", response_model=PuntoVentaResponse)
async def update_punto_venta(
    punto_venta_id: int,
    punto_venta_data: PuntoVentaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Actualizar un punto de venta.

    Args:
        punto_venta_id: ID del punto de venta
        punto_venta_data: Datos a actualizar
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Punto de venta actualizado

    Raises:
        HTTPException: Si el punto de venta no existe o no pertenece a la empresa
    """
    result = await db.execute(select(PuntoVenta).where(PuntoVenta.id == punto_venta_id))
    punto_venta = result.scalar_one_or_none()

    if not punto_venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Punto de venta no encontrado"
        )

    # Verificar permisos
    if not current_user.es_admin and punto_venta.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar este punto de venta",
        )

    # Actualizar campos
    update_data = punto_venta_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(punto_venta, field, value)

    await db.commit()
    await db.refresh(punto_venta)

    return punto_venta


@router.delete("/{punto_venta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_punto_venta(
    punto_venta_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Desactivar un punto de venta.

    Args:
        punto_venta_id: ID del punto de venta
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Raises:
        HTTPException: Si el punto de venta no existe o no pertenece a la empresa
    """
    result = await db.execute(select(PuntoVenta).where(PuntoVenta.id == punto_venta_id))
    punto_venta = result.scalar_one_or_none()

    if not punto_venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Punto de venta no encontrado"
        )

    # Verificar permisos
    if not current_user.es_admin and punto_venta.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este punto de venta",
        )

    # Desactivar
    punto_venta.activo = False
    await db.commit()
