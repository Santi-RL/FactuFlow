"""Dependencias comunes para los endpoints de la API."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.empresa import Empresa
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
            detail="Usuario no tiene empresa asignada",
        )
    return current_user


async def get_current_empresa_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> int:
    """
    Resuelve la empresa activa del request.

    Reglas:
    - Usuario no admin: siempre usa su empresa asignada.
    - Admin con header `X-Empresa-Id`: usa esa empresa si existe.
    - Admin sin header y con empresa asignada: usa su empresa.
    - Admin sin header ni empresa asignada:
      - si existe una sola empresa en el sistema, la usa.
      - si hay más de una, exige seleccionar empresa.
    """
    if not current_user.es_admin:
        if current_user.empresa_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario no tiene empresa asignada",
            )
        return current_user.empresa_id

    empresa_header = request.headers.get("X-Empresa-Id")
    if empresa_header:
        try:
            empresa_id = int(empresa_header)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El header X-Empresa-Id es inválido",
            ) from exc

        result = await db.execute(select(Empresa.id).where(Empresa.id == empresa_id))
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La empresa seleccionada no existe",
            )

        return empresa_id

    if current_user.empresa_id is not None:
        return current_user.empresa_id

    result = await db.execute(select(func.count(Empresa.id)))
    total_empresas = result.scalar_one()

    if total_empresas == 1:
        unica_empresa = await db.execute(select(Empresa.id))
        return unica_empresa.scalar_one()

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Debes seleccionar una empresa antes de continuar",
    )
