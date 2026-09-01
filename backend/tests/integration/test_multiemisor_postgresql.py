"""Upgrade, downgrade y reupgrade multiemisor en PostgreSQL descartable."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.test_integridad_fiscal_postgresql import (
    _crear_contexto_sintetico,
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url


REVISION_PF19D = "e3f4a5b6c7d8"
REVISION_MULTIEMISOR = "f4a5b6c7d8e9"


@pytest.mark.asyncio
async def test_postgresql_multiemisor_upgrade_downgrade_y_reupgrade() -> None:
    """PostgreSQL conserva el acceso más antiguo y reconstruye el explícito."""
    database_url = require_disposable_postgres_url(
        purpose="migración PostgreSQL de operadores multiemisor"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_PF19D, database_url)
    engine = create_async_engine(database_url)
    try:
        await _crear_contexto_sintetico(engine)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO empresas (
                        id, razon_social, cuit, condicion_iva, domicilio,
                        localidad, provincia, codigo_postal, inicio_actividades,
                        created_at, updated_at
                    ) VALUES (
                        2, 'Emisor sintético dos', '20000000002', 'RI',
                        'Domicilio sintético', 'Localidad sintética',
                        'Provincia sintética', '1000', DATE '2020-01-01',
                        now(), now()
                    )
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO usuarios (
                        id, email, hashed_password, nombre, activo, es_admin,
                        empresa_id, created_at, updated_at
                    ) VALUES (
                        1, 'operador@example.test', 'hash-sintetico',
                        'Operador sintético', true, false, 1, now(), now()
                    )
                    """
                )
            )
    finally:
        await engine.dispose()

    _run_alembic("upgrade", REVISION_MULTIEMISOR, database_url)
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            acceso = (
                await connection.execute(
                    text(
                        "SELECT usuario_id, empresa_id, origen "
                        "FROM usuario_emisor_acceso"
                    )
                )
            ).one()
            assert acceso == (1, 1, "migracion_legacy")
            capacidad = await connection.scalar(
                text("SELECT puede_crear_editar_emisores FROM usuarios WHERE id = 1")
            )
            assert capacidad is False
            await connection.execute(
                text(
                    "UPDATE usuario_emisor_acceso "
                    "SET otorgado_en = TIMESTAMP '2026-02-01 00:00:00'"
                )
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO usuario_emisor_acceso (
                        usuario_id, empresa_id, otorgado_por_usuario_id, origen,
                        otorgado_en
                    ) VALUES (
                        1, 2, NULL, 'asignacion_admin',
                        TIMESTAMP '2026-01-01 00:00:00'
                    )
                    """
                )
            )
            await connection.execute(
                text("UPDATE usuarios SET empresa_id = NULL WHERE id = 1")
            )
    finally:
        await engine.dispose()

    _run_alembic("downgrade", REVISION_PF19D, database_url)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT empresa_id FROM usuarios WHERE id = 1")
                )
                == 2
            )
            descripcion = await connection.scalar(
                text(
                    "SELECT descripcion FROM eventos_sistema "
                    "WHERE accion = 'downgrade_operadores_multiemisor'"
                )
            )
            assert descripcion is not None
            assert "descartó 1" in descripcion
    finally:
        await engine.dispose()

    _run_alembic("upgrade", REVISION_MULTIEMISOR, database_url)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            accesos = list(
                (
                    await connection.execute(
                        text(
                            "SELECT usuario_id, empresa_id, origen "
                            "FROM usuario_emisor_acceso ORDER BY usuario_id, empresa_id"
                        )
                    )
                ).all()
            )
            assert accesos == [(1, 2, "migracion_legacy")]
    finally:
        await engine.dispose()
