"""Dependencias comunes para los endpoints de la API."""

from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.usuario import Usuario


async def get_current_empresa_user(
    current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    """
    Dependency para verificar que el usuario tiene una empresa asignada.
    
    Args:
        current_user: Usuario actual
        
    Returns:
        Usuario con empresa asignada
        
    Raises:
        HTTPException: Si el usuario no tiene empresa asignada
    """
    if current_user.empresa_id is None and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no tiene empresa asignada"
        )
    return current_user
