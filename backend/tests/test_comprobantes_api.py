"""Tests de endpoints de comprobantes."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.punto_venta import PuntoVenta


@pytest.mark.asyncio
async def test_emitir_comprobante_rechaza_concepto_faltante(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    """No debe completar Productos por defecto si falta concepto."""
    response = await client.post(
        "/api/comprobantes/emitir",
        headers=auth_headers,
        json={
            "empresa_id": test_empresa.id,
            "punto_venta_id": 1,
            "tipo_comprobante": 6,
            "fecha_emision": date.today().isoformat(),
            "tipo_documento": 96,
            "numero_documento": "12345678",
            "razon_social": "Cliente sin concepto",
            "condicion_iva": "Consumidor Final",
            "items": [
                {
                    "descripcion": "Servicio",
                    "cantidad": 1,
                    "unidad": "unidad",
                    "precio_unitario": 100,
                    "iva_porcentaje": 0,
                }
            ],
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_emitir_comprobante_exige_confirmacion_fecha_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    """No debe emitir por API si no se confirmó la fecha fiscal en la UI."""
    response = await client.post(
        "/api/comprobantes/emitir",
        headers=auth_headers,
        json={
            "empresa_id": test_empresa.id,
            "punto_venta_id": 1,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": date.today().isoformat(),
            "tipo_documento": 96,
            "numero_documento": "12345678",
            "razon_social": "Cliente sin confirmacion",
            "condicion_iva": "Consumidor Final",
            "items": [
                {
                    "descripcion": "Servicio",
                    "cantidad": 1,
                    "unidad": "unidad",
                    "precio_unitario": 100,
                    "iva_porcentaje": 0,
                }
            ],
        },
    )

    assert response.status_code == 400
    assert "confirmar la fecha fiscal" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_comprobante_detalle_con_items(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """Debe devolver el detalle de un comprobante con items sin error 500."""
    cliente = Cliente(
        razon_social="Cliente API Test",
        tipo_documento="DNI",
        numero_documento="12345678",
        condicion_iva="CF",
        empresa_id=test_empresa.id,
    )
    punto_venta = PuntoVenta(
        numero=5,
        nombre="PV Test",
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([cliente, punto_venta])
    await db_session.flush()

    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=1,
        fecha_emision=date(2026, 3, 9),
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae="86100017097127",
        cae_vencimiento=date(2026, 3, 19),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1.000000"),
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        cliente_id=cliente.id,
    )
    db_session.add(comprobante)
    await db_session.flush()

    item = ComprobanteItem(
        codigo="ITEM-1",
        descripcion="Producto API Test",
        cantidad=Decimal("1.00"),
        unidad="unidades",
        precio_unitario=Decimal("1000.00"),
        descuento_porcentaje=Decimal("0.00"),
        iva_porcentaje=Decimal("21.00"),
        subtotal=Decimal("1000.00"),
        orden=1,
        comprobante_id=comprobante.id,
    )
    db_session.add(item)
    await db_session.commit()

    response = await client.get(
        f"/api/comprobantes/{comprobante.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == comprobante.id
    assert data["cliente_nombre"] == "Cliente API Test"
    assert data["punto_venta_numero"] == 5
    assert len(data["items"]) == 1
    assert data["items"][0]["descripcion"] == "Producto API Test"
