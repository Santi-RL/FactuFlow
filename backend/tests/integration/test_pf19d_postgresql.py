"""Upgrade y rollback PostgreSQL de la autoridad de puntos PF-19D."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.test_integridad_fiscal_postgresql import (
    REVISION_INTEGRIDAD_FISCAL,
    _crear_contexto_sintetico,
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url


REVISION_PDV_DURABLE = "d1e2f3a4b5c6"
REVISION_PF19D = "e3f4a5b6c7d8"


@pytest.mark.asyncio
async def test_postgresql_pf19d_upgrade_rollback_y_reupgrade() -> None:
    """La migración real conserva el punto legacy y vuelve al head."""
    database_url = require_disposable_postgres_url(
        purpose="migración PostgreSQL PF-19D"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    engine = create_async_engine(database_url)
    try:
        await _crear_contexto_sintetico(engine)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO puntos_venta (
                        id, numero, nombre, es_webservice, bloqueado, fecha_baja,
                        activo, empresa_id, created_at
                    ) VALUES
                        (2, 42, 'Otro sistema sintético', false, false, NULL,
                         true, 1, now()),
                        (3, 43, 'Web Services bloqueado', true, true, NULL,
                         false, 1, now())
                    """
                )
            )
    finally:
        await engine.dispose()

    _run_alembic("upgrade", REVISION_PF19D, database_url)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            columnas = {
                str(row.column_name)
                for row in (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' "
                            "AND table_name = 'puntos_venta'"
                        )
                    )
                )
            }
            assert {
                "usar_en_factuflow",
                "domicilio_fuente",
                "nombre_fantasia_fuente",
            } <= columnas
            preferencias = list(
                (
                    await connection.execute(
                        text(
                            "SELECT id, usar_en_factuflow FROM puntos_venta "
                            "ORDER BY id"
                        )
                    )
                ).all()
            )
            assert preferencias == [(1, True), (2, False), (3, True)]
    finally:
        await engine.dispose()

    _run_alembic("downgrade", REVISION_PDV_DURABLE, database_url)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            columnas_downgrade = {
                str(row.column_name)
                for row in (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' "
                            "AND table_name = 'puntos_venta'"
                        )
                    )
                )
            }
            assert {
                "usar_en_factuflow",
                "domicilio_fuente",
                "nombre_fantasia_fuente",
            }.isdisjoint(columnas_downgrade)
    finally:
        await engine.dispose()

    _run_alembic("upgrade", REVISION_PF19D, database_url)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            preferencias_reupgrade = list(
                (
                    await connection.execute(
                        text(
                            "SELECT id, usar_en_factuflow FROM puntos_venta "
                            "ORDER BY id"
                        )
                    )
                ).all()
            )
            assert preferencias_reupgrade == [(1, True), (2, False), (3, True)]
    finally:
        await engine.dispose()
