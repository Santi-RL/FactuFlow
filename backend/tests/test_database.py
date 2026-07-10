"""Tests de pools y observabilidad segura de base de datos."""

import asyncio
import json
import logging
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool, StaticPool

from app.core import database
from app.core.config import settings


@pytest.mark.asyncio
async def test_postgresql_separa_pools_api_y_worker_sin_conectar() -> None:
    """PostgreSQL debe reservar cuatro conexiones API y una del worker."""
    api_engine, worker_engine = database._create_database_engines(
        "postgresql+asyncpg://127.0.0.1:5432/prueba"
    )
    try:
        assert api_engine is not worker_engine
        assert isinstance(api_engine.pool, AsyncAdaptedQueuePool)
        assert isinstance(worker_engine.pool, AsyncAdaptedQueuePool)
        assert api_engine.pool.size() == settings.database_api_pool_size
        assert api_engine.pool._max_overflow == settings.database_api_max_overflow
        assert api_engine.pool._timeout == settings.database_pool_timeout_seconds
        assert worker_engine.pool.size() == settings.database_worker_pool_size
        assert worker_engine.pool._max_overflow == 0
        assert worker_engine.pool._timeout == settings.database_pool_timeout_seconds
        assert api_engine.pool._pre_ping is True
        assert worker_engine.pool._pre_ping is True
    finally:
        await worker_engine.dispose()
        await api_engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_archivo_comparte_engine_y_conserva_nullpool(
    tmp_path: Path,
) -> None:
    """SQLite de archivo no debe recibir configuración de QueuePool."""
    database_path = (tmp_path / "database-pool.db").as_posix()
    api_engine, worker_engine = database._create_database_engines(
        f"sqlite+aiosqlite:///{database_path}"
    )
    try:
        assert api_engine is worker_engine
        assert isinstance(api_engine.pool, NullPool)
    finally:
        await api_engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_memoria_comparte_engine_y_conserva_staticpool() -> None:
    """SQLite en memoria debe mantener una sola base visible para ambos roles."""
    api_engine, worker_engine = database._create_database_engines(
        "sqlite+aiosqlite:///:memory:"
    )
    try:
        assert api_engine is worker_engine
        assert isinstance(api_engine.pool, StaticPool)
    finally:
        await api_engine.dispose()


def test_snapshot_pool_no_expone_secretos() -> None:
    """El estado público solo debe contener contadores y duraciones."""
    snapshot = database.get_database_pool_status()
    expected_role_keys = {
        "pool_size",
        "max_overflow",
        "capacity",
        "checked_out",
        "checked_in",
        "overflow",
        "high_water_mark",
        "acquisition_count",
        "timeout_count",
        "last_wait_ms",
        "max_wait_ms",
    }

    assert set(snapshot) == {
        "separation_required",
        "separated",
        "api",
        "worker",
    }
    assert set(snapshot["api"]) == expected_role_keys
    assert set(snapshot["worker"]) == expected_role_keys

    serialized = json.dumps(snapshot, sort_keys=True).lower()
    for forbidden in (
        "database_url",
        "password",
        "credential",
        "postgresql",
        "sqlite",
        "usuario",
        "clave",
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_get_db_adquiere_lazy_en_el_primer_uso_real(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crear la dependencia no debe ocupar una conexión antes de ejecutar SQL."""
    database_path = (tmp_path / "lazy-api-session.db").as_posix()
    api_engine, _ = database._create_database_engines(
        f"sqlite+aiosqlite:///{database_path}"
    )
    factory = database._create_session_factory(api_engine)
    monkeypatch.setattr(database, "AsyncSessionLocal", factory)
    monkeypatch.setitem(database._role_metrics, "api", database._RoleMetrics())
    dependency = database.get_db()
    try:
        session = await anext(dependency)
        assert database._role_metrics["api"].acquisition_count == 0

        await session.execute(text("SELECT 1"))

        assert database._role_metrics["api"].acquisition_count == 1
        assert database._role_metrics["api"].timeout_count == 0
    finally:
        await dependency.aclose()
        await api_engine.dispose()


@pytest.mark.asyncio
async def test_checkout_largo_genera_warning_sanitizado(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Una conexión retenida debe advertirse sin identificar la base."""
    monkeypatch.setattr(settings, "database_pool_hold_warning_seconds", 0.001)
    database_path = (tmp_path / "held-connection.db").as_posix()
    api_engine, _ = database._create_database_engines(
        f"sqlite+aiosqlite:///{database_path}"
    )
    try:
        with caplog.at_level(logging.WARNING, logger="app.core.database"):
            async with api_engine.connect():
                await asyncio.sleep(0.01)

        messages = "\n".join(caplog.messages).lower()
        assert "event=database_connection_held" in messages
        assert "role=api" in messages
        assert "held_ms=" in messages
        for forbidden in ("sqlite", "database_url", "password", "usuario", "clave"):
            assert forbidden not in messages
    finally:
        await api_engine.dispose()


@pytest.mark.asyncio
async def test_timeout_adquisicion_genera_warning_sanitizado(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un timeout debe conservar la excepción y registrar solo métricas seguras."""
    monkeypatch.setitem(database._role_metrics, "worker", database._RoleMetrics())

    class TimeoutSession:
        """Sesión mínima que simula agotamiento del pool."""

        async def connection(self) -> None:
            """Simula el timeout emitido por SQLAlchemy."""
            raise SQLAlchemyTimeoutError()

    session = cast(AsyncSession, TimeoutSession())
    with caplog.at_level(logging.WARNING, logger="app.core.database"):
        with pytest.raises(SQLAlchemyTimeoutError):
            await database.acquire_database_connection(session, "worker")

    metrics = database._role_metrics["worker"]
    assert metrics.acquisition_count == 0
    assert metrics.timeout_count == 1
    messages = "\n".join(caplog.messages).lower()
    assert "event=database_pool_timeout" in messages
    assert "role=worker" in messages
    assert "wait_ms=" in messages
    for forbidden in ("database_url", "password", "usuario", "clave"):
        assert forbidden not in messages
