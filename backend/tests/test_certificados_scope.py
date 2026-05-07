"""Tests de scoping de certificados por emisor activo."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certificado import Certificado
from app.models.empresa import Empresa


@pytest.fixture
async def segundo_emisor_cert(db_session: AsyncSession) -> Empresa:
    """Crear un segundo emisor para validar scoping admin."""
    emisor = Empresa(
        razon_social="Segundo Emisor Cert",
        cuit="30716164175",
        condicion_iva="Exento",
        domicilio="Gorriti 133",
        localidad="Boulogne",
        provincia="Buenos Aires",
        codigo_postal="1609",
        inicio_actividades=date(2018, 8, 1),
    )
    db_session.add(emisor)
    await db_session.commit()
    await db_session.refresh(emisor)
    return emisor


@pytest.fixture
async def certificado_demo(
    db_session: AsyncSession, test_empresa: Empresa
) -> Certificado:
    """Crear certificado asociado al primer emisor."""
    certificado = Certificado(
        nombre="Certificado demo",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2026, 12, 31),
        archivo_crt="demo.crt",
        archivo_key="demo.key",
        activo=True,
        ambiente="produccion",
        empresa_id=test_empresa.id,
    )
    db_session.add(certificado)
    await db_session.commit()
    await db_session.refresh(certificado)
    return certificado


@pytest.mark.asyncio
async def test_admin_lista_certificados_solo_del_emisor_activo(
    client: AsyncClient,
    admin_auth_headers: dict,
    segundo_emisor_cert: Empresa,
    certificado_demo: Certificado,
):
    """Un admin debe ver solo certificados del emisor indicado por X-Empresa-Id."""
    response = await client.get(
        "/api/certificados",
        headers={**admin_auth_headers, "X-Empresa-Id": str(segundo_emisor_cert.id)},
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_admin_no_puede_ver_certificado_de_otro_emisor(
    client: AsyncClient,
    admin_auth_headers: dict,
    segundo_emisor_cert: Empresa,
    certificado_demo: Certificado,
):
    """Un admin con emisor activo B no debe abrir certificado del emisor A."""
    response = await client.get(
        f"/api/certificados/{certificado_demo.id}",
        headers={**admin_auth_headers, "X-Empresa-Id": str(segundo_emisor_cert.id)},
    )

    assert response.status_code == 403
