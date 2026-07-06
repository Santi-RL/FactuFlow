"""Tests para endpoints de PDF."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.comprobante import Comprobante
from app.models.punto_venta import PuntoVenta


async def _crear_comprobante_pdf(
    db_session,
    empresa_id: int,
    *,
    estado: str = "borrador",
    cae: str | None = None,
    cae_vencimiento: date | None = None,
) -> Comprobante:
    """Crea un comprobante mínimo para probar endpoints PDF."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Punto PDF",
        es_webservice=True,
        empresa_id=empresa_id,
    )
    db_session.add(punto_venta)
    await db_session.flush()

    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=1,
        fecha_emision=date(2026, 2, 3),
        subtotal=Decimal("100.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("21.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("121.00"),
        cae=cae,
        cae_vencimiento=cae_vencimiento,
        estado=estado,
        empresa_id=empresa_id,
        punto_venta_id=punto_venta.id,
    )
    db_session.add(comprobante)
    await db_session.commit()
    await db_session.refresh(comprobante)
    return comprobante


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ruta",
    [
        "/api/pdf/comprobante/{comprobante_id}",
        "/api/pdf/comprobante/{comprobante_id}/preview",
    ],
)
async def test_pdf_rechaza_comprobante_sin_autorizacion_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_empresa,
    ruta: str,
):
    """No debe generar PDF fiscal si el comprobante no tiene CAE persistido."""
    comprobante = await _crear_comprobante_pdf(db_session, test_empresa.id)

    with patch(
        "app.api.pdf.pdf_service.generar_pdf_comprobante",
        new_callable=AsyncMock,
    ) as generar_pdf:
        response = await client.get(
            ruta.format(comprobante_id=comprobante.id), headers=auth_headers
        )

    assert response.status_code == 409
    assert "Solo se puede generar PDF fiscal" in response.json()["detail"]
    generar_pdf.assert_not_called()


@pytest.mark.asyncio
async def test_pdf_permite_comprobante_autorizado(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_empresa,
):
    """Debe generar PDF cuando el comprobante tiene estado, CAE y vencimiento."""
    comprobante = await _crear_comprobante_pdf(
        db_session,
        test_empresa.id,
        estado="autorizado",
        cae="12345678901234",
        cae_vencimiento=date(2026, 2, 13),
    )

    with patch(
        "app.api.pdf.pdf_service.generar_pdf_comprobante",
        new_callable=AsyncMock,
    ) as generar_pdf:
        generar_pdf.return_value = b"%PDF-test"
        response = await client.get(
            f"/api/pdf/comprobante/{comprobante.id}", headers=auth_headers
        )

    assert response.status_code == 200
    assert response.content == b"%PDF-test"
    assert response.headers["content-type"] == "application/pdf"
    generar_pdf.assert_awaited_once()
