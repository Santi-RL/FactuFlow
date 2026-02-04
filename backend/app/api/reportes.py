"""API endpoints para reportes."""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.reportes_service import reportes_service

router = APIRouter()


@router.get("/ventas")
async def reporte_ventas(
    empresa_id: int = Query(..., description="ID de la empresa"),
    desde: date = Query(..., description="Fecha desde (YYYY-MM-DD)"),
    hasta: date = Query(..., description="Fecha hasta (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Genera reporte de ventas por período.

    Args:
        empresa_id: ID de la empresa
        desde: Fecha desde
        hasta: Fecha hasta
        db: Sesión de base de datos

    Returns:
        Diccionario con comprobantes y resumen de ventas
    """
    if desde > hasta:
        raise HTTPException(
            status_code=400,
            detail="La fecha 'desde' no puede ser mayor que la fecha 'hasta'",
        )

    try:
        reporte = await reportes_service.generar_reporte_ventas(
            db, empresa_id, desde, hasta
        )
        return reporte
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al generar reporte: {str(e)}"
        )


@router.get("/iva-ventas")
async def reporte_iva_ventas(
    empresa_id: int = Query(..., description="ID de la empresa"),
    periodo_mes: int = Query(..., ge=1, le=12, description="Mes del período (1-12)"),
    periodo_anio: int = Query(..., ge=2000, le=2100, description="Año del período"),
    db: AsyncSession = Depends(get_db),
):
    """
    Genera subdiario de IVA Ventas para DDJJ.

    Args:
        empresa_id: ID de la empresa
        periodo_mes: Mes del período (1-12)
        periodo_anio: Año del período
        db: Sesión de base de datos

    Returns:
        Diccionario con detalle de IVA
    """
    try:
        reporte = await reportes_service.generar_reporte_iva(
            db, empresa_id, periodo_mes, periodo_anio
        )
        return reporte
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al generar reporte de IVA: {str(e)}"
        )


@router.get("/clientes")
async def reporte_clientes(
    empresa_id: int = Query(..., description="ID de la empresa"),
    desde: date = Query(..., description="Fecha desde (YYYY-MM-DD)"),
    hasta: date = Query(..., description="Fecha hasta (YYYY-MM-DD)"),
    limite: int = Query(10, ge=1, le=100, description="Cantidad de clientes a mostrar"),
    db: AsyncSession = Depends(get_db),
):
    """
    Ranking de clientes por facturación.

    Args:
        empresa_id: ID de la empresa
        desde: Fecha desde
        hasta: Fecha hasta
        limite: Cantidad de clientes a devolver
        db: Sesión de base de datos

    Returns:
        Lista de clientes con totales facturados
    """
    if desde > hasta:
        raise HTTPException(
            status_code=400,
            detail="La fecha 'desde' no puede ser mayor que la fecha 'hasta'",
        )

    try:
        ranking = await reportes_service.obtener_ranking_clientes(
            db, empresa_id, desde, hasta, limite
        )
        return {
            "clientes": ranking,
            "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error al generar ranking de clientes: {str(e)}"
        )
