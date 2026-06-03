"""Tests de autenticación."""

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.usuario import Usuario


@pytest.mark.asyncio
async def test_setup_status_required_when_no_users(client: AsyncClient):
    """Test que setup-status pide instalación si no hay usuarios."""
    response = await client.get("/api/auth/setup-status")

    assert response.status_code == 200
    assert response.json() == {"setup_required": True}


@pytest.mark.asyncio
async def test_setup_status_not_required_when_user_exists(
    client: AsyncClient, auth_headers: dict
):
    """Test que setup-status se cierra cuando ya existe un usuario."""
    response = await client.get("/api/auth/setup-status")

    assert response.status_code == 200
    assert response.json() == {"setup_required": False}


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
async def test_login_acepta_email_legacy_con_mayusculas(
    client: AsyncClient, test_user, db_session
):
    """Test login contra emails legacy guardados con mayúsculas."""
    test_user.email = "Test@User.COM"
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "testpassword123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"].lower() == "test@user.com"


@pytest.mark.asyncio
async def test_login_duplicado_legacy_por_mayusculas_no_responde_500(
    client: AsyncClient, test_user, test_empresa, db_session
):
    """El login ambiguo por duplicados legacy debe fallar de forma controlada."""
    duplicado = Usuario(
        email="Test@User.COM",
        hashed_password=get_password_hash("otra-password"),
        nombre="Usuario Duplicado",
        activo=True,
        es_admin=False,
        empresa_id=test_empresa.id,
    )
    db_session.add(duplicado)
    await db_session.commit()

    exact_response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "testpassword123"},
    )
    ambiguous_response = await client.post(
        "/api/auth/login",
        json={"email": "TEST@USER.COM", "password": "testpassword123"},
    )

    assert exact_response.status_code == 200
    assert ambiguous_response.status_code == 401
    assert ambiguous_response.json()["detail"] == "Email o contraseña incorrectos"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    """Test login con contraseña incorrecta."""
    response = await client.post(
        "/api/auth/login", json={"email": "test@user.com", "password": "wrongpassword"}
    )

    assert response.status_code == 401
    assert "Email o contraseña incorrectos" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(client: AsyncClient, test_user, db_session):
    """Test que un usuario inactivo no puede iniciar sesión."""
    test_user.activo = False
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "testpassword123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Usuario inactivo"


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
