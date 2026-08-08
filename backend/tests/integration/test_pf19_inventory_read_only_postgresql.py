"""Integración PostgreSQL desechable del modo lectura PF-19A."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.inventario_legacy_pf19_service import (
    activar_transaccion_solo_lectura,
)


URL_ENV = "FACTUFLOW_TEST_POSTGRES_URL"
SCHEMA_RESET_ENV = "FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET"
NOMBRES_DESCARTABLES = ("test", "tmp", "temp", "pf01b")


def _postgres_url_desechable() -> str:
    """Exige la misma base explícitamente descartable que la suite fiscal."""
    configured_url = os.getenv(URL_ENV, "").strip()
    if not configured_url:
        pytest.skip("Requiere PostgreSQL desechable explícito para PF-19A")
    if configured_url.startswith("postgresql://"):
        configured_url = configured_url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    if not configured_url.startswith("postgresql+asyncpg://"):
        pytest.fail(f"{URL_ENV} debe apuntar a PostgreSQL")
    if os.getenv(SCHEMA_RESET_ENV, "").strip() != "1":
        pytest.fail(
            f"{SCHEMA_RESET_ENV}=1 es obligatorio para confirmar que la base "
            "es descartable"
        )
    database_name = (make_url(configured_url).database or "").lower()
    if not any(marker in database_name for marker in NOMBRES_DESCARTABLES):
        pytest.fail("La base debe declarar un nombre descartable")
    return configured_url


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19_confirma_read_only_y_rechaza_ddl() -> None:
    """PostgreSQL debe impedir escritura aunque el inventario se desviara."""
    engine = create_async_engine(_postgres_url_desechable())
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await activar_transaccion_solo_lectura(connection)
                verificacion = await connection.execute(
                    text("SHOW transaction_read_only")
                )
                assert str(verificacion.scalar_one()).lower() == "on"
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text("CREATE TEMP TABLE pf19_escritura_prohibida (id integer)")
                    )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
