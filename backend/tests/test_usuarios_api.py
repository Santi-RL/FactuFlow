"""Tests de administración de usuarios."""

import pytest
from httpx import AsyncClient

from app.models.empresa import Empresa
from app.models.usuario import Usuario


@pytest.mark.asyncio
async def test_admin_crea_usuario_operativo(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_empresa: Empresa,
):
    """Un administrador puede crear usuarios comunes para operar emisores."""
    response = await client.post(
        "/api/usuarios",
        headers=admin_auth_headers,
        json={
            "email": "Nuevo@Test.com",
            "nombre": "Usuario Nuevo",
            "password": "password123",
            "es_admin": False,
            "activo": True,
            "empresa_id": test_empresa.id,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "nuevo@test.com"
    assert data["nombre"] == "Usuario Nuevo"
    assert data["es_admin"] is False
    assert data["activo"] is True
    assert data["empresa_id"] == test_empresa.id
    assert "hashed_password" not in data

    login_response = await client.post(
        "/api/auth/login",
        json={"email": "nuevo@test.com", "password": "password123"},
    )

    assert login_response.status_code == 200


@pytest.mark.asyncio
async def test_usuario_comun_no_accede_administracion_usuarios(
    client: AsyncClient,
    auth_headers: dict,
):
    """Solo administradores pueden acceder al menú/API de usuarios."""
    response = await client.get("/api/usuarios", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_no_crea_usuario_duplicado_por_mayusculas(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_user: Usuario,
    db_session,
):
    """El alta evita duplicados que solo cambian mayúsculas/minúsculas."""
    test_user.email = "Duplicado@Test.com"
    await db_session.commit()

    response = await client.post(
        "/api/usuarios",
        headers=admin_auth_headers,
        json={
            "email": "duplicado@test.com",
            "nombre": "Duplicado",
            "password": "password123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Ya existe un usuario con ese email"


@pytest.mark.asyncio
async def test_admin_desactiva_usuario_y_bloquea_login(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_user: Usuario,
):
    """Desactivar un usuario impide nuevos inicios de sesión."""
    response = await client.post(
        f"/api/usuarios/{test_user.id}/desactivar",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["activo"] is False

    login_response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "testpassword123"},
    )

    assert login_response.status_code == 403
    assert login_response.json()["detail"] == "Usuario inactivo"


@pytest.mark.asyncio
async def test_admin_no_puede_desactivarse_a_si_mismo(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_admin: Usuario,
):
    """El administrador actual no debe poder bloquear su propio acceso."""
    response = await client.post(
        f"/api/usuarios/{test_admin.id}/desactivar",
        headers=admin_auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No puedes desactivar tu propio usuario"


@pytest.mark.asyncio
async def test_admin_no_puede_quitarse_admin_a_si_mismo(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_admin: Usuario,
):
    """El administrador actual no debe poder degradar su propio usuario."""
    response = await client.put(
        f"/api/usuarios/{test_admin.id}",
        headers=admin_auth_headers,
        json={"es_admin": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No puedes quitarte permisos de administrador"


@pytest.mark.asyncio
async def test_admin_no_puede_cambiar_su_propio_email(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_admin: Usuario,
):
    """Cambiar el email propio invalidaría el token actual basado en email."""
    response = await client.put(
        f"/api/usuarios/{test_admin.id}",
        headers=admin_auth_headers,
        json={"email": "otro-admin@test.com"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "No puedes cambiar el email de tu propio usuario desde esta sesión"
    )


@pytest.mark.asyncio
async def test_admin_legacy_email_mayusculas_puede_editar_su_nombre(
    client: AsyncClient,
    test_admin: Usuario,
    db_session,
):
    """Un admin legacy con email mixto puede editar campos no-email propios."""
    test_admin.email = "Admin@Test.COM"
    await db_session.commit()

    login_response = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "adminpass123"},
    )
    token = login_response.json()["access_token"]

    response = await client.put(
        f"/api/usuarios/{test_admin.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nombre": "Admin Actualizado",
            "email": "admin@test.com",
        },
    )

    assert response.status_code == 200
    assert response.json()["nombre"] == "Admin Actualizado"
    await db_session.refresh(test_admin)
    assert test_admin.email == "Admin@Test.COM"


@pytest.mark.asyncio
async def test_admin_rechaza_null_en_campos_no_nulos(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_user: Usuario,
):
    """Un update no debe persistir nulls en campos obligatorios de usuario."""
    response = await client.put(
        f"/api/usuarios/{test_user.id}",
        headers=admin_auth_headers,
        json={"email": None},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "El campo email no puede ser nulo"


@pytest.mark.asyncio
async def test_admin_resetea_password_de_usuario(
    client: AsyncClient,
    admin_auth_headers: dict,
    test_user: Usuario,
):
    """Un administrador puede restablecer la contraseña de otro usuario."""
    old_login_response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "testpassword123"},
    )
    old_token = old_login_response.json()["access_token"]

    response = await client.post(
        f"/api/usuarios/{test_user.id}/reset-password",
        headers=admin_auth_headers,
        json={"password": "nueva-password"},
    )

    assert response.status_code == 200

    old_token_response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    old_password_response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "testpassword123"},
    )
    new_login_response = await client.post(
        "/api/auth/login",
        json={"email": "test@user.com", "password": "nueva-password"},
    )

    assert old_token_response.status_code == 401
    assert old_password_response.status_code == 401
    assert new_login_response.status_code == 200
