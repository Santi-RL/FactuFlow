"""Tests del servicio de facturación."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService


@pytest.mark.asyncio
async def test_guardar_comprobante_masivo_no_crea_cliente(
    db_session: AsyncSession,
    test_empresa,
):
    """La emisión masiva puede guardar snapshot sin crear cliente persistente."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()

    service = FacturacionService(db_session)
    request = service.normalizar_receptor(
        EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=1,
            tipo_documento=99,
            numero_documento="",
            razon_social="",
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Cuota mensual",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000"),
                    iva_porcentaje=Decimal("21"),
                )
            ],
        )
    )
    totales = service._calcular_totales(request.items)
    resultado_arca = SimpleNamespace(
        cae="12345678901234",
        cae_vencimiento=date(2026, 5, 15).strftime("%Y%m%d"),
    )

    comprobante = await service._guardar_comprobante(
        request=request,
        numero=1,
        totales=totales,
        resultado_arca=resultado_arca,
        punto_venta=punto_venta,
    )

    clientes = (await db_session.execute(select(Cliente))).scalars().all()
    assert clientes == []
    assert comprobante.cliente_id is None
    assert comprobante.receptor_tipo_documento == 99
    assert comprobante.receptor_numero_documento == "0"
    assert comprobante.receptor_razon_social == "A CONSUMIDOR FINAL"
    assert comprobante.receptor_condicion_iva == "CF"
