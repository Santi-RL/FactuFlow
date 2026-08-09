"""Tests del guard destructivo compartido para PostgreSQL."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from tests.postgresql_harness import (
    DISPOSABLE_DATABASE_NAME,
    POSTGRES_URL_ENV,
    SCHEMA_RESET_ENV,
    require_disposable_postgres_url,
    validate_disposable_postgres_url,
)
from tests.integration import test_integridad_fiscal_postgresql
from tests.integration import test_vps_migration_postgresql


def test_postgresql_guard_requiere_opt_in_exacto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El harness no autoriza la base si el opt-in no es exactamente uno."""
    monkeypatch.setenv(
        POSTGRES_URL_ENV,
        f"postgresql://user@127.0.0.1/{DISPOSABLE_DATABASE_NAME}",
    )
    monkeypatch.setenv(SCHEMA_RESET_ENV, "true")

    with pytest.raises(pytest.fail.Exception, match=f"{SCHEMA_RESET_ENV}=1"):
        require_disposable_postgres_url(purpose="guard")

    monkeypatch.setenv(SCHEMA_RESET_ENV, " 1 ")
    with pytest.raises(pytest.fail.Exception, match=f"{SCHEMA_RESET_ENV}=1"):
        require_disposable_postgres_url(purpose="guard")


@pytest.mark.parametrize(
    "configured_url",
    [
        "sqlite:///factuflow_integration_test.db",
        "postgresql://user@db/factuflow_integration_test",
        "postgresql://user@localhost/factuflow_contest",
        "postgresql://user@localhost/factuflow_template_prod",
        "postgresql://user@localhost/FactuFlow_Integration_Test",
        "postgresql+psycopg2://user@localhost/factuflow_integration_test",
        "postgresql://user@localhost/factuflow_integration_test?host=db",
        (
            "postgresql://user@localhost/factuflow_integration_test"
            "?database=factuflow_contest"
        ),
        (
            "postgresql://user@localhost/factuflow_integration_test"
            "?host=/var/run/postgresql"
        ),
        (
            "postgresql://user@localhost/factuflow_integration_test"
            "?host=db&database=factuflow_template_prod"
        ),
    ],
)
def test_postgresql_guard_rechaza_destinos_no_inequivocos(
    configured_url: str,
) -> None:
    """Esquema, host o nombre aproximado nunca habilitan un reset destructivo."""
    with pytest.raises(pytest.fail.Exception):
        validate_disposable_postgres_url(
            configured_url,
            schema_reset_opt_in="1",
        )


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "[::1]"],
)
def test_postgresql_guard_acepta_solo_loopback_y_nombre_exacto(host: str) -> None:
    """Las tres formas loopback explícitas normalizan al driver asyncpg."""
    result = validate_disposable_postgres_url(
        f"postgresql://user:secret@{host}:5432/{DISPOSABLE_DATABASE_NAME}",
        schema_reset_opt_in="1",
    )

    assert result.startswith("postgresql+asyncpg://user:secret@")
    assert result.endswith(f"/{DISPOSABLE_DATABASE_NAME}")


def test_postgresql_guard_sanitiza_url_malformada() -> None:
    """El diagnóstico no repite credenciales de una URL que no pudo parsearse."""
    with pytest.raises(pytest.fail.Exception) as caught:
        validate_disposable_postgres_url(
            "postgresql://usuario:dato-secreto@[::1",
            schema_reset_opt_in="1",
        )

    assert "dato-secreto" not in str(caught.value)


@pytest.mark.asyncio
async def test_reset_schema_revalida_opt_in_antes_de_crear_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El sink destructivo no confía en que su caller haya ejecutado el guard."""
    monkeypatch.delenv(SCHEMA_RESET_ENV, raising=False)
    calls: list[str] = []
    monkeypatch.setattr(
        test_integridad_fiscal_postgresql,
        "create_async_engine",
        lambda url, **kwargs: calls.append(url),
    )

    with pytest.raises(pytest.fail.Exception, match=f"{SCHEMA_RESET_ENV}=1"):
        await test_integridad_fiscal_postgresql._reset_schema(
            "postgresql+asyncpg://user@127.0.0.1/factuflow_integration_test"
        )

    assert calls == []


@pytest.mark.parametrize("failure", ["missing_opt_in", "mutated_url"])
def test_run_alembic_revalida_guard_antes_de_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    """Alembic no recibe env ni se ejecuta si cambió el destino autorizado."""
    if failure == "missing_opt_in":
        monkeypatch.delenv(SCHEMA_RESET_ENV, raising=False)
        database_url = (
            "postgresql+asyncpg://user@127.0.0.1/" "factuflow_integration_test"
        )
    else:
        monkeypatch.setenv(SCHEMA_RESET_ENV, "1")
        database_url = (
            "postgresql+asyncpg://user@db.internal/" "factuflow_integration_test"
        )
    calls: list[str] = []
    monkeypatch.setattr(
        test_integridad_fiscal_postgresql.subprocess,
        "run",
        lambda *args, **kwargs: calls.append("subprocess"),
    )

    with pytest.raises(pytest.fail.Exception):
        test_integridad_fiscal_postgresql._run_alembic(
            "upgrade",
            "head",
            database_url,
        )

    assert calls == []


def test_run_alembic_traduce_timeout_sin_exponer_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un Alembic colgado falla de forma acotada y sin imprimir credenciales."""
    monkeypatch.setenv(SCHEMA_RESET_ENV, "1")

    def timeout(*args: object, **kwargs: object) -> None:
        assert kwargs["timeout"] == (
            test_integridad_fiscal_postgresql.ALEMBIC_TIMEOUT_SECONDS
        )
        raise subprocess.TimeoutExpired(cmd="alembic", timeout=300)

    monkeypatch.setattr(
        test_integridad_fiscal_postgresql.subprocess,
        "run",
        timeout,
    )
    with pytest.raises(pytest.fail.Exception, match="timeout controlado") as caught:
        test_integridad_fiscal_postgresql._run_alembic(
            "upgrade",
            "head",
            (
                "postgresql+asyncpg://user:dato-secreto@127.0.0.1/"
                "factuflow_integration_test"
            ),
        )

    assert "dato-secreto" not in str(caught.value)


def test_ci_backend_conserva_job_y_habilita_postgres_solo_en_pytest() -> None:
    """CI mantiene el check backend y acota credenciales/opt-in al step de tests."""
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    backend_job = workflow.split("  backend:\n", 1)[1].split("  frontend:\n", 1)[0]
    run_tests_step = backend_job.split("      - name: Run tests\n", 1)[1].split(
        "      - name: Upload coverage\n",
        1,
    )[0]

    assert "    name: Backend Tests\n" in backend_job
    assert "    timeout-minutes: 30\n" in backend_job
    assert (
        "        image: ${{ needs.scope.outputs.runtime == 'true' && "
        "'postgres:16-alpine' || '' }}\n" in backend_job
    )
    assert "        image: postgres:16-alpine\n" not in backend_job
    assert "          POSTGRES_DB: factuflow_integration_test\n" in backend_job
    assert "          POSTGRES_USER: factuflow_test\n" in backend_job
    assert "pg_isready -U factuflow_test -d factuflow_integration_test" in backend_job
    assert "FACTUFLOW_TEST_POSTGRES_URL:" in run_tests_step
    assert "@127.0.0.1:5432/factuflow_integration_test" in run_tests_step
    assert 'FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET: "1"' in run_tests_step
    assert "DATABASE_URL:" not in backend_job
    assert backend_job.count("FACTUFLOW_TEST_POSTGRES_URL:") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["import", "validate"])
@pytest.mark.parametrize("failure", ["missing_opt_in", "mutated_url"])
async def test_vps_postgresql_revalida_guard_antes_del_sink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    action: str,
    failure: str,
) -> None:
    """Los wrappers VPS no abren sinks si cambió el opt-in o el destino."""
    if failure == "missing_opt_in":
        monkeypatch.delenv(SCHEMA_RESET_ENV, raising=False)
        database_url = (
            "postgresql+asyncpg://user@127.0.0.1/" "factuflow_integration_test"
        )
    else:
        monkeypatch.setenv(SCHEMA_RESET_ENV, "1")
        database_url = (
            "postgresql+asyncpg://user@db.internal/" "factuflow_integration_test"
        )
    calls: list[str] = []
    monkeypatch.setattr(
        test_vps_migration_postgresql.vps_migration,
        "import_package",
        lambda *args: calls.append("import"),
    )
    monkeypatch.setattr(
        test_vps_migration_postgresql.vps_migration,
        "validate_import",
        lambda *args: calls.append("validate"),
    )
    kwargs = {
        "package": tmp_path / "package",
        "database_url": database_url,
        "env_path": tmp_path / ".env.production",
        "target_certs": tmp_path / "certs",
    }

    with pytest.raises(pytest.fail.Exception):
        if action == "import":
            await test_vps_migration_postgresql._importar_paquete(**kwargs)
        else:
            await test_vps_migration_postgresql._validar_paquete(**kwargs)

    assert calls == []
