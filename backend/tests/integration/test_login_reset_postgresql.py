"""SC-11: intercalados deterministas con sesiones PostgreSQL independientes."""

import asyncio
from datetime import datetime

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import auth, usuarios
from app.core.security import (
    decode_access_token,
    get_current_user,
    get_current_user_optional,
    get_password_hash,
)
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioLogin, UsuarioPasswordReset
from app.scripts.reset_user_password import reset_password
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "reset_kind,phase",
    [
        ("admin", "bcrypt"),
        ("console", "bcrypt"),
        ("admin", "after_commit"),
        ("console", "after_commit"),
        ("console", "reset_uncommitted"),
    ],
)
async def test_concurrent_reset_never_grants_access(monkeypatch, reset_kind, phase):
    url = require_disposable_postgres_url(purpose="login y reset SC-11")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    reached = asyncio.Event()
    resume = asyncio.Event()
    pending = None
    try:
        async with factory() as db:
            user = Usuario(
                email="operator@example.com",
                nombre="Operador sintético",
                hashed_password=get_password_hash("old-synthetic-password"),
                activo=True,
                es_admin=False,
            )
            db.add(user)
            await db.commit()
            user_id = user.id
            old_hash = user.hashed_password

        async with factory() as login_db, factory() as reset_db:
            original_verify = auth._verify_password
            original_commit = login_db.commit

            async def pause_verify(password, hashed):
                result = await original_verify(password, hashed)
                reached.set()
                await resume.wait()
                return result

            async def pause_commit():
                await original_commit()
                reached.set()
                await resume.wait()

            if phase == "after_commit":
                monkeypatch.setattr(login_db, "commit", pause_commit)
            else:
                monkeypatch.setattr(auth, "_verify_password", pause_verify)

            if phase == "reset_uncommitted":
                await reset_password(reset_db, user.email, "new-synthetic-password")
                # El timestamp ya existe, pero otro lector aún ve el hash anterior.

            pending = asyncio.create_task(
                auth._login(
                    UsuarioLogin(email=user.email, password="old-synthetic-password"),
                    login_db,
                )
            )
            await asyncio.wait_for(reached.wait(), 10)
            if phase != "reset_uncommitted":
                if reset_kind == "console":
                    await reset_password(reset_db, user.email, "new-synthetic-password")
                else:
                    await usuarios.reset_password_usuario(
                        user_id,
                        UsuarioPasswordReset(password="new-synthetic-password"),
                        db=reset_db,
                        _admin=Usuario(es_admin=True),
                    )
            await reset_db.commit()
            resume.set()
            if phase == "after_commit":
                response = await asyncio.wait_for(pending, 10)
                token = response["access_token"]
                async with factory() as check_db:
                    current = await check_db.get(Usuario, user_id)
                    assert current.hashed_password != old_hash
                    assert (
                        datetime.utcfromtimestamp(decode_access_token(token)["iat"])
                        > current.password_changed_at
                    )
                    for dependency in (get_current_user, get_current_user_optional):
                        with pytest.raises(HTTPException) as error:
                            await dependency(
                                credentials=HTTPAuthorizationCredentials(
                                    scheme="Bearer", credentials=token
                                ),
                                db=check_db,
                            )
                        assert error.value.status_code == 401
            else:
                with pytest.raises(HTTPException) as error:
                    await asyncio.wait_for(pending, 10)
                assert error.value.status_code == 401

        # Otra sesión legítima opera con la credencial nueva y conserva su rol.
        async with factory() as fresh_db:
            fresh = await auth._login(
                UsuarioLogin(email=user.email, password="new-synthetic-password"),
                fresh_db,
            )
            current = await get_current_user(
                credentials=HTTPAuthorizationCredentials(
                    scheme="Bearer", credentials=fresh["access_token"]
                ),
                db=fresh_db,
            )
            assert current.id == user_id
            assert current.activo and not current.es_admin
    finally:
        resume.set()
        if pending is not None:
            if not pending.done():
                pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await engine.dispose()
