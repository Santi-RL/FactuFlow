"""Tests de puntos de venta."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.empresa import Empresa
from app.models.punto_venta import PuntoVenta


@pytest.fixture
async def segundo_emisor(db_session: AsyncSession) -> Empresa:
    """Crear un segundo emisor para validar scoping admin."""
    emisor = Empresa(
        razon_social="Segundo Emisor",
        cuit="30123456789",
        condicion_iva="Exento",
        domicilio="Calle Falsa 123",
        localidad="Ciudad de Prueba",
        provincia="Buenos Aires",
        codigo_postal="1609",
        inicio_actividades=date(2018, 8, 1),
    )
    db_session.add(emisor)
    await db_session.commit()
    await db_session.refresh(emisor)
    return emisor


@pytest.fixture
async def punto_venta_demo(
    db_session: AsyncSession, test_empresa: Empresa
) -> PuntoVenta:
    """Crear un punto de venta asociado al primer emisor."""
    punto = PuntoVenta(
        numero=5,
        nombre="Webservices",
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto)
    await db_session.commit()
    await db_session.refresh(punto)
    return punto


@pytest.mark.asyncio
async def test_admin_lista_puntos_venta_solo_del_emisor_activo(
    client: AsyncClient,
    admin_auth_headers: dict,
    segundo_emisor: Empresa,
    punto_venta_demo: PuntoVenta,
):
    """Un admin debe ver solo puntos del emisor indicado por X-Empresa-Id."""
    response = await client.get(
        "/api/puntos-venta",
        headers={**admin_auth_headers, "X-Empresa-Id": str(segundo_emisor.id)},
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_admin_crea_punto_venta_en_emisor_activo(
    client: AsyncClient,
    admin_auth_headers: dict,
    segundo_emisor: Empresa,
):
    """La creacion admin debe asociarse al emisor activo, no a otro emisor."""
    response = await client.post(
        "/api/puntos-venta",
        headers={**admin_auth_headers, "X-Empresa-Id": str(segundo_emisor.id)},
        json={"numero": 12, "nombre": "Produccion"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["numero"] == 12
    assert data["empresa_id"] == segundo_emisor.id
