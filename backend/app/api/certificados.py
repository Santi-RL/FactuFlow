"""Endpoints de Certificados."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_empresa_user
from app.models.usuario import Usuario
from app.models.certificado import Certificado
from app.schemas.certificado import CertificadoResponse

router = APIRouter()


@router.get("", response_model=list[CertificadoResponse])
async def list_certificados(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user)
):
    """
    Listar certificados.
    
    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Lista de certificados
    """
    query = select(Certificado)
    
    if not current_user.es_admin:
        query = query.where(Certificado.empresa_id == current_user.empresa_id)
    
    result = await db.execute(query)
    certificados = result.scalars().all()
    
    return certificados


@router.get("/{certificado_id}", response_model=CertificadoResponse)
async def get_certificado(
    certificado_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user)
):
    """
    Obtener un certificado por ID.
    
    Args:
        certificado_id: ID del certificado
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Returns:
        Certificado
        
    Raises:
        HTTPException: Si el certificado no existe o no pertenece a la empresa
    """
    result = await db.execute(
        select(Certificado).where(Certificado.id == certificado_id)
    )
    certificado = result.scalar_one_or_none()
    
    if not certificado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificado no encontrado"
        )
    
    # Verificar permisos
    if not current_user.es_admin and certificado.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este certificado"
        )
    
    return certificado


@router.delete("/{certificado_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certificado(
    certificado_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user)
):
    """
    Eliminar un certificado.
    
    Args:
        certificado_id: ID del certificado
        db: Sesión de base de datos
        current_user: Usuario autenticado
        
    Raises:
        HTTPException: Si el certificado no existe o no pertenece a la empresa
    """
    result = await db.execute(
        select(Certificado).where(Certificado.id == certificado_id)
    )
    certificado = result.scalar_one_or_none()
    
    if not certificado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificado no encontrado"
        )
    
    # Verificar permisos
    if not current_user.es_admin and certificado.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este certificado"
        )
    
    await db.delete(certificado)
    await db.commit()
