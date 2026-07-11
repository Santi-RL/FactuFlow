"""Tests de pools y observabilidad segura de base de datos."""

import asyncio
import json
import logging
from pathlib import Path
from typing import cast

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool, StaticPool

from app.core import database
from app.core.config import settings


def _crear_error_db_temporal(
    error_type: type[SQLAlchemyTimeoutError] | type[OperationalError],
) -> SQLAlchemyTimeoutError | OperationalError:
    """Construye errores temporales reales sin depender de un motor activo."""
    if error_type is SQLAlchemyTimeoutError:
        return SQLAlchemyTimeoutError()
    return OperationalError(
        "ROLLBACK",
        {},
        RuntimeError("base temporalmente no disponible"),
    )


def test_errores_db_temporales_excluyen_integrity_error() -> None:
    """La clasificación transitoria debe preservar conflictos de integridad."""
    assert set(database.DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS) == {
        SQLAlchemyTimeoutError,
        OperationalError,
    }
    assert IntegrityError not in database.DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS


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
@pytest.mark.parametrize(
    "rollback_error_type",
    [SQLAlchemyTimeoutError, OperationalError],
)
async def test_get_db_preserva_http_exception_si_falla_rollback(
    monkeypatch: pytest.MonkeyPatch,
    rollback_error_type: type[SQLAlchemyTimeoutError] | type[OperationalError],
) -> None:
    """El rollback secundario no debe ocultar un conflicto HTTP primario."""
    eventos: list[str] = []

    class FakeSession:
        """Sesión mínima cuyo rollback reproduce una caída secundaria."""

        async def rollback(self) -> None:
            """Registra el intento y falla con el error parametrizado."""
            eventos.append("rollback")
            raise _crear_error_db_temporal(rollback_error_type)

        async def close(self) -> None:
            """Registra la liberación explícita de la sesión."""
            eventos.append("close")

    class FakeSessionFactory:
        """Factory mínima compatible con AsyncSessionLocal."""

        def __new__(cls) -> FakeSession:
            """Entrega la sesión falsa."""
            return FakeSession()

    monkeypatch.setattr(database, "AsyncSessionLocal", FakeSessionFactory)
    monkeypatch.setitem(database._role_metrics, "api", database._RoleMetrics())
    dependency = database.get_db()
    await anext(dependency)
    primary = HTTPException(status_code=409, detail={"categoria_error": "conflicto"})

    with pytest.raises(HTTPException) as exc_info:
        await dependency.athrow(primary)

    assert exc_info.value is primary
    assert eventos == ["rollback", "close"]
    assert database._role_metrics["api"].timeout_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rollback_error_type",
    [SQLAlchemyTimeoutError, OperationalError],
)
async def test_get_db_preserva_timeout_primario_si_falla_rollback(
    monkeypatch: pytest.MonkeyPatch,
    rollback_error_type: type[SQLAlchemyTimeoutError] | type[OperationalError],
) -> None:
    """El timeout primario se contabiliza una vez aunque falle el rollback."""
    eventos: list[str] = []

    class FakeSession:
        """Sesión mínima cuyo rollback reproduce una caída secundaria."""

        async def rollback(self) -> None:
            """Registra el intento y falla con el error parametrizado."""
            eventos.append("rollback")
            raise _crear_error_db_temporal(rollback_error_type)

        async def close(self) -> None:
            """Registra la liberación explícita de la sesión."""
            eventos.append("close")

    class FakeSessionFactory:
        """Factory mínima compatible con AsyncSessionLocal."""

        def __new__(cls) -> FakeSession:
            """Entrega la sesión falsa."""
            return FakeSession()

    monkeypatch.setattr(database, "AsyncSessionLocal", FakeSessionFactory)
    monkeypatch.setitem(database._role_metrics, "api", database._RoleMetrics())
    dependency = database.get_db()
    await anext(dependency)
    primary = SQLAlchemyTimeoutError()

    with pytest.raises(SQLAlchemyTimeoutError) as exc_info:
        await dependency.athrow(primary)

    assert exc_info.value is primary
    assert eventos == ["rollback", "close"]
    assert database._role_metrics["api"].timeout_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "primary",
    [
        HTTPException(status_code=409, detail="conflicto primario"),
        SQLAlchemyTimeoutError(),
    ],
    ids=["http-409", "timeout"],
)
async def test_get_db_preserva_excepcion_primaria_si_falla_close(
    monkeypatch: pytest.MonkeyPatch,
    primary: Exception,
) -> None:
    """Una falla secundaria de close no debe reemplazar la excepción primaria."""
    eventos: list[str] = []

    class FakeSession:
        """Sesión mínima con rollback exitoso y cierre fallido."""

        async def rollback(self) -> None:
            """Registra el rollback exitoso."""
            eventos.append("rollback")

        async def close(self) -> None:
            """Registra el cierre y reproduce una falla secundaria."""
            eventos.append("close")
            raise OperationalError("CLOSE", {}, RuntimeError("falla secundaria"))

    monkeypatch.setattr(database, "AsyncSessionLocal", FakeSession)
    monkeypatch.setitem(database._role_metrics, "api", database._RoleMetrics())
    dependency = database.get_db()
    await anext(dependency)

    with pytest.raises(type(primary)) as exc_info:
        await dependency.athrow(primary)

    assert exc_info.value is primary
    assert eventos == ["rollback", "close"]
    assert database._role_metrics["api"].timeout_count == (
        1 if isinstance(primary, SQLAlchemyTimeoutError) else 0
    )


@pytest.mark.asyncio
async def test_get_db_propaga_falla_close_sin_excepcion_primaria(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un cierre fallido en camino exitoso debe seguir siendo observable."""
    close_error = OperationalError(
        "CLOSE",
        {},
        RuntimeError("falla de cierre observable"),
    )

    class FakeSession:
        """Sesión mínima con commit exitoso y cierre fallido."""

        async def commit(self) -> None:
            """Completa el camino principal sin errores."""

        async def close(self) -> None:
            """Propaga el error de cierre configurado."""
            raise close_error

    monkeypatch.setattr(database, "AsyncSessionLocal", FakeSession)
    dependency = database.get_db()
    await anext(dependency)

    with pytest.raises(OperationalError) as exc_info:
        await dependency.aclose()

    assert exc_info.value is close_error


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
