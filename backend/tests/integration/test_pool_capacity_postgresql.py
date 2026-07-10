"""Prueba controlada y no fiscal de capacidad de pools PostgreSQL."""

import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.config import settings


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_aisla_capacidad_api_y_worker_bajo_saturacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El worker conserva su conexión cuando las cuatro conexiones API están ocupadas."""
    configured_url = os.getenv("FACTUFLOW_TEST_POSTGRES_URL", "").strip()
    if not configured_url:
        pytest.skip("Requiere PostgreSQL desechable explícito para capacidad")

    normalized_url = database._normalize_database_url(configured_url)
    if not database._is_postgresql_url(normalized_url):
        pytest.fail("FACTUFLOW_TEST_POSTGRES_URL debe apuntar a PostgreSQL")

    monkeypatch.setattr(settings, "database_api_pool_size", 4)
    monkeypatch.setattr(settings, "database_api_max_overflow", 0)
    monkeypatch.setattr(settings, "database_worker_pool_size", 1)
    monkeypatch.setattr(settings, "database_pool_timeout_seconds", 5.0)
    monkeypatch.setitem(database._role_metrics, "api", database._RoleMetrics())
    monkeypatch.setitem(database._role_metrics, "worker", database._RoleMetrics())

    api_engine, worker_engine = database._create_database_engines(normalized_url)
    monkeypatch.setattr(database, "database_url", normalized_url)
    monkeypatch.setattr(database, "engine", api_engine)
    monkeypatch.setattr(database, "worker_engine", worker_engine)
    api_factory = database._create_session_factory(api_engine)
    worker_factory = database._create_session_factory(worker_engine)

    api_sessions: list[AsyncSession] = [api_factory() for _ in range(4)]
    worker_session = worker_factory()
    fifth_api_session = api_factory()
    second_worker_session = worker_factory()
    try:
        await asyncio.gather(
            *(
                database.acquire_database_connection(session, "api")
                for session in api_sessions
            )
        )
        await asyncio.gather(
            *(session.execute(text("SELECT 1")) for session in api_sessions)
        )

        await asyncio.wait_for(
            database.acquire_database_connection(worker_session, "worker"),
            timeout=2,
        )
        await worker_session.execute(text("SELECT 1"))

        timeout_results = await asyncio.wait_for(
            asyncio.gather(
                database.acquire_database_connection(fifth_api_session, "api"),
                database.acquire_database_connection(
                    second_worker_session,
                    "worker",
                ),
                return_exceptions=True,
            ),
            timeout=7,
        )
        assert all(
            isinstance(result, SQLAlchemyTimeoutError) for result in timeout_results
        )

        snapshot = database.get_database_pool_status()
        assert snapshot["separation_required"] is True
        assert snapshot["separated"] is True
        assert snapshot["api"]["capacity"] == 4
        assert snapshot["worker"]["capacity"] == 1
        assert snapshot["api"]["checked_out"] == 4
        assert snapshot["worker"]["checked_out"] == 1
        assert snapshot["api"]["high_water_mark"] == 4
        assert snapshot["worker"]["high_water_mark"] == 1
        assert snapshot["api"]["acquisition_count"] == 4
        assert snapshot["worker"]["acquisition_count"] == 1
        assert snapshot["api"]["timeout_count"] == 1
        assert snapshot["worker"]["timeout_count"] == 1
    finally:
        await asyncio.gather(
            *(session.close() for session in api_sessions),
            worker_session.close(),
            fifth_api_session.close(),
            second_worker_session.close(),
            return_exceptions=True,
        )
        await worker_engine.dispose()
        await api_engine.dispose()
