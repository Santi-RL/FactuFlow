"""Tests de endpoints de clientes."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente
from app.models.empresa import Empresa


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


@pytest.mark.asyncio
async def test_admin_puede_resolver_empresa_por_query_legacy(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
):
    """El query legacy empresa_id debe seleccionar emisor si no hay header."""
    empresa = Empresa(
        razon_social="Empresa Query S.A.",
        cuit="30111111118",
        condicion_iva="RI",
        domicilio="Av. Query 123",
        localidad="CABA",
        provincia="Buenos Aires",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(empresa)
    await db_session.flush()
    db_session.add(
        Cliente(
            empresa_id=empresa.id,
            razon_social="Cliente Query",
            tipo_documento="CUIT",
            numero_documento="30123456780",
            condicion_iva="RI",
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/clientes?empresa_id={empresa.id}",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["razon_social"] == "Cliente Query"


@pytest.mark.asyncio
async def test_admin_rechaza_conflicto_header_y_query_empresa(
    client: AsyncClient,
    admin_auth_headers: dict,
    db_session: AsyncSession,
    test_empresa: Empresa,
):
    """El backend no debe aceptar dos emisores distintos en el mismo request."""
    segunda = Empresa(
        razon_social="Empresa Header S.A.",
        cuit="30222222224",
        condicion_iva="RI",
        domicilio="Av. Header 123",
        localidad="CABA",
        provincia="Buenos Aires",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(segunda)
    await db_session.commit()
    await db_session.refresh(segunda)

    response = await client.get(
        f"/api/clientes?empresa_id={test_empresa.id}",
        headers={**admin_auth_headers, "X-Empresa-Id": str(segunda.id)},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Empresa-Id y empresa_id no coinciden"


@pytest.mark.asyncio
async def test_admin_rechaza_header_empresa_cero(
    client: AsyncClient,
    admin_auth_headers: dict,
):
    """Un selector explícito X-Empresa-Id=0 no debe caer al emisor por defecto."""
    response = await client.get(
        "/api/clientes",
        headers={**admin_auth_headers, "X-Empresa-Id": "0"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "El header X-Empresa-Id de empresa debe ser positivo"
    )


@pytest.mark.asyncio
async def test_usuario_comun_no_resuelve_emisor_ajeno_por_query_legacy(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Un usuario común no debe operar un emisor distinto del asignado."""
    segunda = Empresa(
        razon_social="Empresa Ajena S.A.",
        cuit="30333333330",
        condicion_iva="RI",
        domicilio="Av. Ajena 123",
        localidad="CABA",
        provincia="Buenos Aires",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(segunda)
    await db_session.flush()
    db_session.add(
        Cliente(
            empresa_id=segunda.id,
            razon_social="Cliente Segundo Emisor",
            tipo_documento="CUIT",
            numero_documento="30777777774",
            condicion_iva="RI",
        )
    )
    await db_session.commit()
    await db_session.refresh(segunda)

    response = await client.get(
        f"/api/clientes?empresa_id={segunda.id}",
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "No tenés permiso para operar el emisor seleccionado"
    )


@pytest.mark.asyncio
async def test_usuario_comun_puede_resolver_su_emisor_asignado_por_header(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa: Empresa,
):
    """Un usuario común puede seleccionar explícitamente su emisor asignado."""
    db_session.add(
        Cliente(
            empresa_id=test_empresa.id,
            razon_social="Cliente Emisor Asignado",
            tipo_documento="CUIT",
            numero_documento="30999999992",
            condicion_iva="RI",
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/clientes",
        headers={**auth_headers, "X-Empresa-Id": str(test_empresa.id)},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["razon_social"] == "Cliente Emisor Asignado"
