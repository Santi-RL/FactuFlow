"""Dependencias comunes para los endpoints de la API."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.empresa import Empresa
from app.models.usuario import Usuario


def _parse_empresa_id_param(value: str | None, source: str) -> int | None:
    """Parsea un identificador de empresa recibido por header o query."""
    if not value:
        return None

    try:
        parsed = int(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El {source} de empresa es inválido",
        ) from exc
    if parsed <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El {source} de empresa debe ser positivo",
        )
    return parsed


async def get_current_empresa_user(
    current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    """
    Dependency para verificar que el usuario autenticado puede operar emisores.

    Args:
        current_user: Usuario actual

    Returns:
        Usuario autenticado activo
    """
    return current_user


async def get_current_empresa_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> int:
    """
    Resuelve la empresa activa del request.

    Reglas:
    - Cualquier usuario activo con header `X-Empresa-Id`: usa esa empresa si existe.
    - Cualquier usuario activo con query legacy `empresa_id`: usa esa empresa si existe.
    - Sin selección explícita y con empresa asignada: usa esa empresa preferida.
    - Sin selección explícita ni empresa asignada:
      - si existe una sola empresa en el sistema, la usa.
      - si hay más de una, exige seleccionar empresa.
    """
    empresa_header_id = _parse_empresa_id_param(
        request.headers.get("X-Empresa-Id"), "header X-Empresa-Id"
    )
    empresa_query_id = _parse_empresa_id_param(
        request.query_params.get("empresa_id"), "query empresa_id"
    )

    if (
        empresa_header_id is not None
        and empresa_query_id is not None
        and empresa_header_id != empresa_query_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Empresa-Id y empresa_id no coinciden",
        )

    empresa_solicitada_id = (
        empresa_header_id if empresa_header_id is not None else empresa_query_id
    )

    if empresa_solicitada_id is not None:
        result = await db.execute(
            select(Empresa.id).where(Empresa.id == empresa_solicitada_id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La empresa seleccionada no existe",
            )

        return empresa_solicitada_id

    if current_user.empresa_id is not None:
        result = await db.execute(
            select(Empresa.id).where(Empresa.id == current_user.empresa_id)
        )
        if result.scalar_one_or_none() is not None:
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
