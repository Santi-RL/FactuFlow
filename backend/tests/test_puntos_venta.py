"""Tests de puntos de venta."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
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


@pytest.mark.asyncio
async def test_punto_venta_numero_unico_por_emisor(
    db_session: AsyncSession,
    test_empresa: Empresa,
):
    """La base debe impedir dos puntos con el mismo número en un emisor."""
    db_session.add_all(
        [
            PuntoVenta(
                numero=22, nombre="PV A", activo=True, empresa_id=test_empresa.id
            ),
            PuntoVenta(
                numero=22, nombre="PV B", activo=True, empresa_id=test_empresa.id
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_update_punto_venta_rechaza_numero_duplicado_por_emisor(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa: Empresa,
):
    """La API no debe permitir duplicar el número al editar un punto."""
    punto_a = PuntoVenta(
        numero=31,
        nombre="PV A",
        activo=True,
        empresa_id=test_empresa.id,
    )
    punto_b = PuntoVenta(
        numero=32,
        nombre="PV B",
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_a, punto_b])
    await db_session.commit()
    await db_session.refresh(punto_b)

    response = await client.put(
        f"/api/puntos-venta/{punto_b.id}",
        headers=admin_auth_headers,
        json={"numero": 31},
    )

    assert response.status_code == 400
    assert "Ya existe un punto de venta con el número 31" in response.json()["detail"]
