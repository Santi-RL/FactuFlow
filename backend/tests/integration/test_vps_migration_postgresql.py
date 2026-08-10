"""Roundtrip PostgreSQL real del paquete privado VPS v2 PF-19B."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.scripts import vps_migration
from tests.integration.test_integridad_fiscal_postgresql import (
    _postgres_url,
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import (
    SCHEMA_RESET_ENV,
    validate_disposable_postgres_url,
)
from tests.test_vps_migration import (
    _create_source_db,
    _insert_operation,
    _insert_terminal_guard_context,
    _lote_response_payload,
    _rece_digest,
    _write_production_env,
)


async def _preparar_destino_vps(database_url: str) -> AsyncEngine:
    """Recrea bajo guard y migra el destino PostgreSQL al head actual."""
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    return create_async_engine(database_url)


def _exportar_paquete_terminal(tmp_path: Path) -> Path:
    """Exporta ledger, replay moderno y normalización de lote sintéticos."""
    db_path, certs_dir = _create_source_db(tmp_path)
    _insert_terminal_guard_context(db_path, with_attempt=True)
    _insert_operation(
        db_path,
        estado="finalizado",
        response_json={
            "lote": _lote_response_payload(),
            "mensaje": "Lote procesado",
            "en_progreso": False,
        },
        tipo_operacion="procesar_lote",
        lote_id=130,
        operacion_id=150,
    )
    return vps_migration.export_package(
        source_db=db_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages",
        target_key_password="clave-destino-larga",
        source_quiesced=True,
    )


async def _importar_paquete(
    *,
    package: Path,
    database_url: str,
    env_path: Path,
    target_certs: Path,
) -> None:
    """Ejecuta el importador síncrono fuera del event loop asyncpg."""
    database_url = validate_disposable_postgres_url(
        database_url,
        schema_reset_opt_in=os.getenv(SCHEMA_RESET_ENV, ""),
    )
    await asyncio.to_thread(
        vps_migration.import_package,
        package,
        database_url,
        env_path,
        target_certs,
    )


async def _validar_paquete(
    *,
    package: Path,
    database_url: str,
    env_path: Path,
    target_certs: Path,
) -> None:
    """Revalida el guard justo antes del postflight standalone."""
    database_url = validate_disposable_postgres_url(
        database_url,
        schema_reset_opt_in=os.getenv(SCHEMA_RESET_ENV, ""),
    )
    await asyncio.to_thread(
        vps_migration.validate_import,
        package,
        database_url,
        env_path,
        target_certs,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_vps_v2_roundtrip_y_validate(
    tmp_path: Path,
) -> None:
    """Import/validate preserva ledger, replay, digest, claves y secuencias."""
    database_url = _postgres_url()
    package = _exportar_paquete_terminal(tmp_path)
    manifest = vps_migration.load_and_verify_manifest(package)
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    target_certs = tmp_path / "target-certs"
    engine = await _preparar_destino_vps(database_url)
    await engine.dispose()

    await _importar_paquete(
        package=package,
        database_url=database_url,
        env_path=env_path,
        target_certs=target_certs,
    )
    await _validar_paquete(
        package=package,
        database_url=database_url,
        env_path=env_path,
        target_certs=target_certs,
    )

    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        operations = await connection.execute(
            text(
                """
                SELECT id, idempotency_key, lote_id, rece_snapshot_hash
                FROM operaciones_idempotentes
                ORDER BY id
                """
            )
        )
        operation_rows = [tuple(row) for row in operations]
        assert operation_rows == [
            (140, "vps-guarda-terminal", None, _rece_digest()),
            (150, "vps-operacion-150", None, None),
        ]
        association = await connection.execute(
            text(
                """
                SELECT operacion_id, empresa_id, punto_venta_id, ambiente,
                       elegibilidad_revision_id, punto_venta_revision_fiscal
                FROM operaciones_idempotentes_elegibilidad_rece
                """
            )
        )
        assert tuple(association.one()) == (140, 10, 40, "produccion", 45, 1)
        heads = await connection.execute(
            text(
                """
                SELECT a.ambiente, a.revision_actual_id, r.revision
                FROM puntos_venta_elegibilidad_rece_actual a
                JOIN puntos_venta_elegibilidad_rece_revisiones r
                  ON r.id = a.revision_actual_id
                ORDER BY a.ambiente
                """
            )
        )
        assert [tuple(row) for row in heads] == [
            ("homologacion", 41, 1),
            ("produccion", 45, 2),
        ]
        sequence_state = await connection.execute(
            text(
                """
                SELECT last_value, is_called
                FROM operaciones_idempotentes_id_seq
                """
            )
        )
        assert tuple(sequence_state.one()) == (151, False)
        excluded_counts = await connection.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM intentos_emision_fiscal),
                  (SELECT COUNT(*) FROM puntos_venta_guardas_emision_rece),
                  (SELECT COUNT(*) FROM lotes_comprobantes)
                """
            )
        )
        assert tuple(excluded_counts.one()) == (0, 0, 0)
    await engine.dispose()

    assert {path.name for path in target_certs.iterdir()} == set(
        manifest["certificate_files"]
    )
    key_name = next(
        filename
        for filename in manifest["certificate_files"]
        if filename.endswith(".key")
    )
    assert b"ENCRYPTED PRIVATE KEY" in (target_certs / key_name).read_bytes()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_vps_v2_dirty_y_rollback_limpian_solo_propios(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Destino sucio y postflight fallido no publican una restauración parcial."""
    database_url = _postgres_url()
    package = _exportar_paquete_terminal(tmp_path)
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    target_certs = tmp_path / "target-certs"
    engine = await _preparar_destino_vps(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO empresas (
                    id, razon_social, cuit, condicion_iva, domicilio,
                    localidad, provincia, codigo_postal, inicio_actividades,
                    created_at, updated_at
                ) VALUES (
                    999, 'Destino ajeno', '20999999991', 'RI', 'Sintético',
                    'Sintética', 'Sintética', '1000', DATE '2020-01-01',
                    now(), now()
                )
                """
            )
        )
    await engine.dispose()

    with pytest.raises(vps_migration.MigrationError, match="no está limpia"):
        await _importar_paquete(
            package=package,
            database_url=database_url,
            env_path=env_path,
            target_certs=target_certs,
        )
    assert not target_certs.exists() or not list(target_certs.iterdir())

    engine = await _preparar_destino_vps(database_url)
    await engine.dispose()
    real_postflight = vps_migration.validate_imported_database

    def fail_after_postflight(conn: object, manifest: dict, rows: dict) -> None:
        """Falla después de verificar que los inserts eran semánticamente válidos."""
        real_postflight(conn, manifest, rows)
        raise vps_migration.MigrationError("postflight sintético")

    monkeypatch.setattr(
        vps_migration,
        "validate_imported_database",
        fail_after_postflight,
    )
    with pytest.raises(vps_migration.MigrationError, match="postflight sintético"):
        await _importar_paquete(
            package=package,
            database_url=database_url,
            env_path=env_path,
            target_certs=target_certs,
        )

    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT COUNT(*) FROM empresas")) == 0
        assert (
            await connection.scalar(
                text("SELECT COUNT(*) FROM operaciones_idempotentes")
            )
            == 0
        )
    await engine.dispose()
    assert not target_certs.exists() or not list(target_certs.iterdir())
