"""Tests de endpoints de clientes."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente


@pytest.mark.asyncio
async def test_create_cliente(client: AsyncClient, auth_headers: dict):
    """Test crear un cliente."""
    response = await client.post(
        "/api/clientes",
        headers=auth_headers,
        json={
            "razon_social": "Cliente Test S.A.",
            "tipo_documento": "CUIT",
            "numero_documento": "20987654321",
            "condicion_iva": "RI",
            "domicilio": "Av. Cliente 456",
            "localidad": "CABA",
            "provincia": "Buenos Aires",
            "codigo_postal": "1001",
            "email": "cliente@test.com",
            "telefono": "1122334455",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["razon_social"] == "Cliente Test S.A."
    assert data["tipo_documento"] == "CUIT"
    assert data["numero_documento"] == "20987654321"
    assert data["activo"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_list_clientes(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """Test listar clientes."""
    # Crear algunos clientes de prueba
    from app.models.empresa import Empresa

    # Obtener la empresa del usuario autenticado
    # (el auth_headers proviene del setup user que no tiene empresa,
    # así que necesitamos crear una para el test)

    response = await client.get("/api/clientes", headers=auth_headers)

    # Puede estar vacío o tener los clientes creados en otros tests
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data


@pytest.mark.asyncio
async def test_get_cliente(client: AsyncClient, auth_headers: dict):
    """Test obtener un cliente por ID."""
    # Primero crear un cliente
    create_response = await client.post(
        "/api/clientes",
        headers=auth_headers,
        json={
            "razon_social": "Cliente Get Test",
            "tipo_documento": "CUIT",
            "numero_documento": "20111222333",
            "condicion_iva": "Monotributo",
        },
    )

    cliente_id = create_response.json()["id"]

    # Obtener el cliente
    response = await client.get(f"/api/clientes/{cliente_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cliente_id
    assert data["razon_social"] == "Cliente Get Test"


@pytest.mark.asyncio
async def test_update_cliente(client: AsyncClient, auth_headers: dict):
    """Test actualizar un cliente."""
    # Primero crear un cliente
    create_response = await client.post(
        "/api/clientes",
        headers=auth_headers,
        json={
            "razon_social": "Cliente Update Test",
            "tipo_documento": "CUIT",
            "numero_documento": "20444555666",
            "condicion_iva": "RI",
        },
    )

    cliente_id = create_response.json()["id"]

    # Actualizar el cliente
    response = await client.put(
        f"/api/clientes/{cliente_id}",
        headers=auth_headers,
        json={"razon_social": "Cliente Actualizado", "email": "actualizado@test.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["razon_social"] == "Cliente Actualizado"
    assert data["email"] == "actualizado@test.com"
    assert data["tipo_documento"] == "CUIT"  # No cambió


@pytest.mark.asyncio
async def test_delete_cliente(client: AsyncClient, auth_headers: dict):
    """Test eliminar (desactivar) un cliente."""
    # Primero crear un cliente
    create_response = await client.post(
        "/api/clientes",
        headers=auth_headers,
        json={
            "razon_social": "Cliente Delete Test",
            "tipo_documento": "DNI",
            "numero_documento": "12345678",
            "condicion_iva": "CF",
        },
    )

    cliente_id = create_response.json()["id"]

    # Eliminar el cliente
    response = await client.delete(f"/api/clientes/{cliente_id}", headers=auth_headers)

    assert response.status_code == 204

    # Verificar que el cliente existe pero está inactivo
    get_response = await client.get(f"/api/clientes/{cliente_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["activo"] is False


@pytest.mark.asyncio
async def test_get_cliente_not_found(client: AsyncClient, auth_headers: dict):
    """Test obtener un cliente que no existe."""
    response = await client.get("/api/clientes/99999", headers=auth_headers)

    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_cliente_without_auth(client: AsyncClient):
    """Test crear cliente sin autenticación."""
    response = await client.post(
        "/api/clientes",
        json={
            "razon_social": "Cliente Sin Auth",
            "tipo_documento": "CUIT",
            "numero_documento": "20777888999",
            "condicion_iva": "RI",
        },
    )

    assert response.status_code == 403
