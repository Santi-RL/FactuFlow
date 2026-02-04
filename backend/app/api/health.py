"""Health check endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

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
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Error de conexión a la base de datos: {str(e)}"
        )
