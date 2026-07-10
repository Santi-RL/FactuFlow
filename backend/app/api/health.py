"""Health check endpoints."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_database_pool_status, get_db
from app.core.security import get_current_admin_user
from app.models.usuario import Usuario
from app.schemas.health import (
    DatabasePoolsStatusResponse,
    LoteWorkerHealthResponse,
    LoteWorkerRuntimeStatusResponse,
)
from app.services.lote_worker import get_lote_worker_status

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def health_check():
    """
    Health check básico.

    Returns:
        Status de la aplicación
    """
    return {"status": "healthy", "message": "FactuFlow API funcionando correctamente"}


@router.get("/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    """
    Health check de la base de datos.

    Args:
        db: Sesión de base de datos

    Returns:
        Status de la conexión a la base de datos

    Raises:
        HTTPException: Si no se puede conectar a la base de datos
    """
    try:
        # Ejecutar una query simple para verificar la conexión
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        return {"status": "healthy", "message": "Conexión a la base de datos OK"}
    except (SQLAlchemyTimeoutError, OperationalError):
        raise
    except Exception as exc:
        logger.warning(
            "event=database_healthcheck_failed type_error=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="No se pudo verificar la conexión a la base de datos.",
        ) from exc


@router.get("/worker", response_model=LoteWorkerHealthResponse)
async def health_check_worker(
    request: Request,
    _current_admin: Usuario = Depends(get_current_admin_user),
) -> LoteWorkerHealthResponse:
    """Expone a administradores el estado sanitizado del worker y sus pools."""
    try:
        worker = LoteWorkerRuntimeStatusResponse.model_validate(
            get_lote_worker_status(request.app)
        )
        pools = DatabasePoolsStatusResponse.model_validate(get_database_pool_status())
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="No se pudo obtener el estado interno del worker.",
        ) from exc

    status_value: Literal["healthy", "degraded", "disabled"]
    if not worker.habilitado:
        status_value = "disabled"
    elif (
        not worker.ejecutando
        or worker.ultimo_resultado == "error"
        or (pools.separation_required and not pools.separated)
    ):
        status_value = "degraded"
    else:
        status_value = "healthy"

    return LoteWorkerHealthResponse(
        status=status_value,
        worker=worker,
        pools=pools,
    )
