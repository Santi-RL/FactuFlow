"""Integración PostgreSQL desechable del modo lectura PF-19A."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.inventario_legacy_pf19_service import (
    activar_transaccion_solo_lectura,
)
from tests.postgresql_harness import require_disposable_postgres_url


def _postgres_url_desechable() -> str:
    """Exige la misma base explícitamente descartable que la suite fiscal."""
    return require_disposable_postgres_url(purpose="PF-19A")


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
