"""Recuperación conservando identidad, autorizaciones y datos relacionados."""

from sqlalchemy import select
import os
from pathlib import Path
import subprocess
import sys
import pytest

from app.core.security import create_access_token, verify_password
from app.models.usuario import Usuario
from app.models.usuario_emisor_acceso import UsuarioEmisorAcceso
from app.scripts.reset_user_password import reset_password, main


@pytest.mark.asyncio
async def test_recovery_preserves_account_permissions_and_revokes_session(
    client, test_user, test_empresa, db_session
):
    previous_id = test_user.id
    test_user.puede_crear_editar_emisores = True
    await db_session.commit()
    previous_token = create_access_token({"sub": test_user.email})
    previous_access = (
        (await db_session.execute(select(UsuarioEmisorAcceso))).scalars().all()
    )
    previous_ids = [
        (access.usuario_id, access.empresa_id) for access in previous_access
    ]
    await reset_password(db_session, "TEST@USER.COM", "newpassword123")
    await db_session.commit()
    assert test_user.id == previous_id
    assert test_user.es_admin is False
    assert test_user.activo is True
    assert test_user.empresa_id == test_empresa.id
    assert test_user.puede_crear_editar_emisores is True
    assert [
        (access.usuario_id, access.empresa_id)
        for access in (await db_session.execute(select(UsuarioEmisorAcceso))).scalars()
    ] == previous_ids
    assert verify_password("newpassword123", test_user.hashed_password)
    assert not verify_password("testpassword123", test_user.hashed_password)
    assert (
        await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {previous_token}"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "newpassword123"},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_admin_recovery_and_inactive_account_not_reactivated(
    test_admin, db_session
):
    test_admin.activo = False
    await db_session.commit()
    await reset_password(db_session, test_admin.email, "newpassword123")
    assert test_admin.es_admin is True
    assert test_admin.empresa_id is None
    assert test_admin.activo is False


@pytest.mark.asyncio
async def test_missing_and_ambiguous_email_fail_closed(test_user, db_session):
    previous = test_user.hashed_password
    with pytest.raises(ValueError):
        await reset_password(db_session, "missing@example.com", "newpassword123")
    db_session.add(
        Usuario(
            email="Test@User.COM",
            hashed_password=previous,
            nombre="Synthetic",
            activo=True,
            es_admin=False,
        )
    )
    await db_session.flush()
    with pytest.raises(ValueError):
        await reset_password(db_session, test_user.email, "newpassword123")
    assert test_user.hashed_password == previous


def test_console_no_secret_arguments_or_errors(monkeypatch, capsys):
    from app.scripts import reset_user_password as script

    monkeypatch.setattr(
        "sys.argv", ["reset_user_password", "--email", "admin@example.com"]
    )
    answers = iter(["private-example", "different-example"])
    monkeypatch.setattr(script, "getpass", lambda label: next(answers))
    assert main() == 1
    output = capsys.readouterr()
    assert "coinciden" in output.err
    assert "private-example" not in output.err


def test_console_sanitizes_configuration_failures(monkeypatch, capsys):
    from app.scripts import reset_user_password as script

    monkeypatch.setattr(
        "sys.argv", ["reset_user_password", "--email", "admin@example.com"]
    )
    monkeypatch.setattr(script, "getpass", lambda label: "newpassword123")

    async def unavailable(*args):
        raise ValueError("synthetic-private-config-value")

    monkeypatch.setattr(script, "_run", unavailable)
    assert main() == 1
    output = capsys.readouterr()
    assert "No se pudo completar" in output.err
    assert "synthetic-private-config-value" not in output.err


def test_real_console_invalid_settings_are_sanitized():
    env = {
        **os.environ,
        "APP_ENV": "production",
        "APP_SECRET_KEY": "short-private-placeholder",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            # getpass en Windows lee la consola aunque stdin sea un pipe.
            # Sólo sustituir la interacción; importar y ejecutar el CLI real.
            "from app.scripts import reset_user_password as s; "
            "s.getpass = lambda _: 'newpassword123'; raise SystemExit(s.main())",
            "--email",
            "admin@example.com",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "No se pudo completar" in result.stderr
    assert "short-private-placeholder" not in result.stderr + result.stdout
    assert "newpassword123" not in result.stderr + result.stdout
    assert "Traceback" not in result.stderr
