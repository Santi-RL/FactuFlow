"""SC-11: un reset concurrente no convierte una credencial vieja en sesión válida."""

import asyncio
from datetime import datetime, timedelta

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import pytest

from app.api import auth
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_current_user,
    get_current_user_optional,
)
from app.scripts.reset_user_password import reset_password


@pytest.mark.parametrize("reset_kind", ["admin", "console"])
async def test_reset_during_verification_rejects_old_login(
    client, test_user, admin_auth_headers, db_session, monkeypatch, reset_kind
):
    verified = asyncio.Event()
    resume = asyncio.Event()
    original = auth._verify_password

    async def pause(password, hashed):
        result = await original(password, hashed)
        if result:
            verified.set()
            await resume.wait()
        return result

    monkeypatch.setattr(auth, "_verify_password", pause)
    pending = asyncio.create_task(
        client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
    )
    try:
        await asyncio.wait_for(verified.wait(), 10)
        if reset_kind == "admin":
            response = await client.post(
                f"/api/usuarios/{test_user.id}/reset-password",
                headers=admin_auth_headers,
                json={"password": "new-synthetic-password"},
            )
            assert response.status_code == 200
        else:
            await reset_password(db_session, test_user.email, "new-synthetic-password")
            await db_session.commit()
    finally:
        resume.set()
        response = await asyncio.wait_for(pending, 10)
    assert response.status_code == 401
    assert response.json()["detail"] == "Email o contraseña incorrectos"
    assert test_user.ultimo_login is None
    assert test_user.activo and not test_user.es_admin
    assert test_user.empresa_id is not None
    fresh = await client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "new-synthetic-password"},
    )
    assert fresh.status_code == 200
    assert fresh.json()["user"]["empresa_ids"] == [test_user.empresa_id]
    assert (
        await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {fresh.json()['access_token']}"},
        )
    ).status_code == 200


async def test_deactivation_during_verification_preserves_403(
    client, test_user, db_session, monkeypatch
):
    original = auth._verify_password

    async def deactivate(password, hashed):
        result = await original(password, hashed)
        test_user.activo = False
        await db_session.commit()
        return result

    monkeypatch.setattr(auth, "_verify_password", deactivate)
    response = await client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "testpassword123"},
    )
    assert response.status_code == 403
    assert test_user.ultimo_login is None


async def test_login_token_does_not_disclose_password_hash(client, test_user):
    response = await client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "testpassword123"},
    )
    assert response.status_code == 200
    payload = decode_access_token(response.json()["access_token"])
    assert len(payload["pwdv"]) == 64
    assert test_user.hashed_password not in str(payload)
    assert "testpassword123" not in str(payload)


async def test_account_deleted_during_verification_is_generic_401(
    client, test_user, db_session, monkeypatch
):
    original = auth._verify_password

    async def delete_account(password, hashed):
        result = await original(password, hashed)
        await db_session.delete(test_user)
        await db_session.commit()
        return result

    monkeypatch.setattr(auth, "_verify_password", delete_account)
    response = await client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "testpassword123"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email o contraseña incorrectos"


@pytest.mark.parametrize("dependency", [get_current_user, get_current_user_optional])
@pytest.mark.parametrize("version", [None, [], {}, 1, "", "é" * 64, "0" * 64])
async def test_invalid_credential_version_is_401(
    test_user, db_session, dependency, version
):
    token = create_access_token({"sub": test_user.email, "pwdv": version})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as error:
        await dependency(credentials=credentials, db=db_session)
    assert error.value.status_code == 401


@pytest.mark.parametrize("dependency", [get_current_user, get_current_user_optional])
@pytest.mark.parametrize("previous_reset", [False, True])
async def test_legacy_sessions_keep_existing_revocation(
    test_user, db_session, dependency, previous_reset
):
    if previous_reset:
        test_user.password_changed_at = datetime.utcnow() - timedelta(seconds=1)
        await db_session.commit()
    token = create_access_token({"sub": test_user.email})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert await dependency(credentials=credentials, db=db_session) is test_user
    test_user.password_changed_at = datetime.utcnow() + timedelta(seconds=1)
    await db_session.commit()
    with pytest.raises(HTTPException) as error:
        await dependency(credentials=credentials, db=db_session)
    assert error.value.status_code == 401


@pytest.mark.parametrize("dependency", [get_current_user, get_current_user_optional])
async def test_bound_token_rejects_reset_with_later_iat(
    test_user, db_session, dependency
):
    verified_hash = test_user.hashed_password
    await reset_password(db_session, test_user.email, "new-synthetic-password")
    await db_session.commit()
    token = create_access_token(
        {"sub": test_user.email}, verified_password_hash=verified_hash
    )
    payload = decode_access_token(token)
    assert datetime.utcfromtimestamp(payload["iat"]) > test_user.password_changed_at
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as error:
        await dependency(credentials=credentials, db=db_session)
    assert error.value.status_code == 401
