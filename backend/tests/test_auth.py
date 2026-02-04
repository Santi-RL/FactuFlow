"""Tests de autenticación."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_setup_initial_user(client: AsyncClient):
    """Test crear usuario inicial."""
    response = await client.post(
        "/api/auth/setup",
        json={
            "email": "initial@test.com",
            "password": "password123",
            "nombre": "Initial User",
            "empresa_id": None,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "initial@test.com"
    assert data["nombre"] == "Initial User"
    assert data["es_admin"] is True
    assert data["activo"] is True


@pytest.mark.asyncio
async def test_setup_fails_if_user_exists(client: AsyncClient, auth_headers: dict):
    """Test que setup falla si ya existe un usuario."""
    response = await client.post(
        "/api/auth/setup",
        json={
            "email": "another@test.com",
            "password": "password123",
            "nombre": "Another User",
            "empresa_id": None,
        },
    )

    assert response.status_code == 400
    assert "Ya existe al menos un usuario" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    """Test login exitoso."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "testpassword123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@user.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    """Test login con contraseña incorrecta."""
    response = await client.post(
        "/api/auth/login", json={"email": "test@user.com", "password": "wrongpassword"}
    )

    assert response.status_code == 401
    assert "Email o contraseña incorrectos" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login con usuario que no existe."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "nonexistent@test.com", "password": "password123"},
    )

    assert response.status_code == 401
    assert "Email o contraseña incorrectos" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers: dict):
    """Test obtener usuario actual."""
    response = await client.get("/api/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@user.com"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_get_me_without_auth(client: AsyncClient):
    """Test obtener usuario sin autenticación."""
    response = await client.get("/api/auth/me")

    assert response.status_code == 403
