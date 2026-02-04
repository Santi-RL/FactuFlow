"""API de Comprobantes - Endpoints para emisión y gestión de facturas."""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_db, get_current_user
from app.models.comprobante import Comprobante
from app.models.usuario import Usuario
from app.schemas.comprobante import (
    EmitirComprobanteRequest,
    EmitirComprobanteResponse,
    ComprobanteResponse,
    ComprobanteDetalleResponse,
    ComprobanteListResponse,
    PaginatedComprobantesResponse,
    ProximoNumeroResponse,
    ItemComprobanteResponse,
)
from app.services.facturacion_service import FacturacionService


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=PaginatedComprobantesResponse)
async def listar_comprobantes(
    empresa_id: int = Query(..., description="ID de la empresa"),
    desde: Optional[date] = Query(None, description="Fecha desde (filtro)"),
    hasta: Optional[date] = Query(None, description="Fecha hasta (filtro)"),
    tipo: Optional[int] = Query(None, description="Tipo de comprobante (filtro)"),
    cliente_id: Optional[int] = Query(None, description="ID del cliente (filtro)"),
    buscar: Optional[str] = Query(None, description="Búsqueda por número o cliente"),
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(20, ge=1, le=100, description="Resultados por página"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista comprobantes con filtros y paginación.
    
    Filtros disponibles:
    - desde/hasta: Rango de fechas
    - tipo: Tipo de comprobante
    - cliente_id: Cliente específico
    - buscar: Búsqueda por número o nombre de cliente
    """
    # Base query
    stmt = (
        select(Comprobante)
        .where(Comprobante.empresa_id == empresa_id)
        .options(
            joinedload(Comprobante.cliente),
            joinedload(Comprobante.punto_venta)
        )
    )
    
    # Aplicar filtros
    if desde:
        stmt = stmt.where(Comprobante.fecha_emision >= desde)
    if hasta:
        stmt = stmt.where(Comprobante.fecha_emision <= hasta)
    if tipo:
        stmt = stmt.where(Comprobante.tipo_comprobante == tipo)
    if cliente_id:
        stmt = stmt.where(Comprobante.cliente_id == cliente_id)
    if buscar:
        stmt = stmt.where(
            or_(
                Comprobante.numero.cast(db.bind.dialect.type_descriptor(str)).like(f"%{buscar}%"),
                Comprobante.cliente.has(
                    or_(
                        Comprobante.cliente.property.mapper.class_.nombre.like(f"%{buscar}%"),
                        Comprobante.cliente.property.mapper.class_.cuit.like(f"%{buscar}%")
                    )
                )
            )
        )
    
    # Contar total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()
    
    # Aplicar paginación
    stmt = stmt.order_by(Comprobante.fecha_emision.desc(), Comprobante.numero.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    
    # Ejecutar query
    result = await db.execute(stmt)
    comprobantes = result.scalars().all()
    
    # Mapear a response
    items = [
        ComprobanteListResponse(
            id=c.id,
            tipo_comprobante=c.tipo_comprobante,
            numero=c.numero,
            fecha_emision=c.fecha_emision,
            total=c.total,
            estado=c.estado,
            cae=c.cae,
            cliente_nombre=c.cliente.nombre if c.cliente else "Desconocido",
            cliente_documento=c.cliente.cuit or c.cliente.dni or "N/A" if c.cliente else "N/A",
            punto_venta_numero=c.punto_venta.numero if c.punto_venta else 0
        )
        for c in comprobantes
    ]
    
    return PaginatedComprobantesResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/{comprobante_id}", response_model=ComprobanteDetalleResponse)
async def obtener_comprobante(
    comprobante_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene detalle completo de un comprobante.
    
    Incluye todos los items, datos del cliente y punto de venta.
    """
    stmt = (
        select(Comprobante)
        .where(Comprobante.id == comprobante_id)
        .options(
            joinedload(Comprobante.items),
            joinedload(Comprobante.cliente),
            joinedload(Comprobante.punto_venta)
        )
    )
    
    result = await db.execute(stmt)
    comprobante = result.scalar_one_or_none()
    
    if not comprobante:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    
    # Mapear items
    items = [
        ItemComprobanteResponse(
            id=item.id,
            codigo=item.codigo,
            descripcion=item.descripcion,
            cantidad=item.cantidad,
            unidad=item.unidad,
            precio_unitario=item.precio_unitario,
            descuento_porcentaje=item.descuento_porcentaje,
            iva_porcentaje=item.iva_porcentaje,
            subtotal=item.subtotal,
            orden=item.orden,
            comprobante_id=item.comprobante_id
        )
        for item in sorted(comprobante.items, key=lambda x: x.orden)
    ]
    
    return ComprobanteDetalleResponse(
        id=comprobante.id,
        tipo_comprobante=comprobante.tipo_comprobante,
        numero=comprobante.numero,
        fecha_emision=comprobante.fecha_emision,
        fecha_vencimiento=comprobante.fecha_vencimiento,
        subtotal=comprobante.subtotal,
        descuento=comprobante.descuento,
        iva_21=comprobante.iva_21,
        iva_10_5=comprobante.iva_10_5,
        iva_27=comprobante.iva_27,
        otros_impuestos=comprobante.otros_impuestos,
        total=comprobante.total,
        cae=comprobante.cae,
        cae_vencimiento=comprobante.cae_vencimiento,
        estado=comprobante.estado,
        moneda=comprobante.moneda,
        cotizacion=comprobante.cotizacion,
        observaciones=comprobante.observaciones,
        empresa_id=comprobante.empresa_id,
        punto_venta_id=comprobante.punto_venta_id,
        cliente_id=comprobante.cliente_id,
        items=items,
        cliente_nombre=comprobante.cliente.nombre if comprobante.cliente else None,
        cliente_cuit=comprobante.cliente.cuit if comprobante.cliente else None,
        punto_venta_numero=comprobante.punto_venta.numero if comprobante.punto_venta else None
    )


@router.post("/emitir", response_model=EmitirComprobanteResponse)
async def emitir_comprobante(
    request: EmitirComprobanteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Emite un comprobante electrónico.
    
    Flujo:
    1. Valida datos según tipo de comprobante
    2. Obtiene próximo número
    3. Calcula totales e IVA
    4. Solicita CAE a ARCA
    5. Guarda en base de datos
    6. Retorna comprobante con CAE
    
    Tipos de comprobante soportados:
    - 1: Factura A
    - 2: Nota de Débito A
    - 3: Nota de Crédito A
    - 6: Factura B
    - 7: Nota de Débito B
    - 8: Nota de Crédito B
    - 11: Factura C
    - 12: Nota de Débito C
    - 13: Nota de Crédito C
    """
    service = FacturacionService(db)
    
    try:
        resultado = await service.emitir_comprobante(request)
        
        if not resultado.exito:
            # Si hay error, retornar 400
            raise HTTPException(
                status_code=400,
                detail={
                    "mensaje": resultado.mensaje,
                    "errores": resultado.errores
                }
            )
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error al emitir comprobante: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "mensaje": "Error interno al emitir comprobante",
                "errores": [str(e)]
            }
        )


@router.get("/proximo-numero/{punto_venta}/{tipo}", response_model=ProximoNumeroResponse)
async def obtener_proximo_numero(
    punto_venta: int,
    tipo: int,
    empresa_id: int = Query(..., description="ID de la empresa"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene el próximo número de comprobante disponible.
    
    Este endpoint es útil para mostrar al usuario qué número se
    asignará al comprobante antes de emitirlo.
    """
    # Buscar punto de venta
    from app.models.punto_venta import PuntoVenta
    
    stmt = select(PuntoVenta).where(
        and_(
            PuntoVenta.numero == punto_venta,
            PuntoVenta.empresa_id == empresa_id
        )
    )
    result = await db.execute(stmt)
    pv = result.scalar_one_or_none()
    
    if not pv:
        raise HTTPException(status_code=404, detail="Punto de venta no encontrado")
    
    # Obtener próximo número
    service = FacturacionService(db)
    proximo = await service.obtener_proximo_numero(empresa_id, pv.id, tipo)
    
    return ProximoNumeroResponse(
        punto_venta=punto_venta,
        tipo_comprobante=tipo,
        proximo_numero=proximo
    )
