"""Tests de endpoints de emisores."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.usuario import Usuario


@pytest.mark.asyncio
async def test_usuario_comun_puede_listar_y_crear_emisores(
    client: AsyncClient,
    auth_headers: dict,
):
    """Los usuarios activos pueden administrar emisores configurados."""
    list_response = await client.get("/api/empresas", headers=auth_headers)

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    create_response = await client.post(
        "/api/empresas",
        headers=auth_headers,
        json={
            "razon_social": "Nuevo Emisor S.A.",
            "cuit": "30999999995",
            "condicion_iva": "RI",
            "domicilio": "Av. Nueva 123",
            "localidad": "CABA",
            "provincia": "Buenos Aires",
            "codigo_postal": "1000",
            "inicio_actividades": date(2024, 1, 1).isoformat(),
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()["razon_social"] == "Nuevo Emisor S.A."


@pytest.mark.asyncio
async def test_no_puede_crear_emisor_sin_auth_si_ya_hay_usuarios(
    client: AsyncClient,
    auth_headers: dict,
):
    """La creación anónima solo queda disponible durante el setup inicial."""
    assert auth_headers

    response = await client.post(
        "/api/empresas",
        json={
            "razon_social": "Emisor Anónimo S.A.",
            "cuit": "30888888889",
            "condicion_iva": "RI",
            "domicilio": "Av. Anónima 123",
            "localidad": "CABA",
            "provincia": "Buenos Aires",
            "codigo_postal": "1000",
            "inicio_actividades": date(2024, 1, 1).isoformat(),
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_usuario_comun_no_puede_eliminar_emisor(
    client: AsyncClient,
    auth_headers: dict,
):
    """El borrado físico de emisores queda reservado a administradores."""
    list_response = await client.get("/api/empresas", headers=auth_headers)
    empresa_id = list_response.json()[0]["id"]

    response = await client.delete(f"/api/empresas/{empresa_id}", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_elimina_emisor_sin_borrar_usuarios_preferidos(
    client: AsyncClient,
    admin_auth_headers: dict,
    auth_headers: dict,
    db_session,
):
    """Borrar un emisor debe limpiar preferencias, no borrar usuarios globales."""
    assert auth_headers
    list_response = await client.get("/api/empresas", headers=admin_auth_headers)
    empresa_id = list_response.json()[0]["id"]

    response = await client.delete(
        f"/api/empresas/{empresa_id}",
        headers=admin_auth_headers,
    )

    assert response.status_code == 204

    result = await db_session.execute(
        select(Usuario).where(Usuario.email == "test@user.com")
    )
    usuario = result.scalar_one()
    assert usuario.empresa_id is None
