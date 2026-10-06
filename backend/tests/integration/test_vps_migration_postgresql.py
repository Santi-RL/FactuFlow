"""Roundtrips PostgreSQL reales de los paquetes privados VPS v4 y v3."""

from __future__ import annotations

import asyncio
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.database import Base
from tests.fiscal_legacy_schema import legacy_metadata
from app.scripts import vps_migration, vps_migration_v3, vps_migration_v4
from app.core.fiscal_storage_legacy import A01_HEAD
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
    _build_historical_v3_package,
    _build_v4_package,
    _create_source_db,
    _insert_operation,
    _insert_terminal_guard_context,
    _lote_response_payload,
    _rece_digest,
    _write_production_env,
)


def _validated_postgres_url(database_url: str) -> str:
    """Aplica el guard del harness antes de cada acceso PostgreSQL directo."""
    return validate_disposable_postgres_url(
        database_url,
        schema_reset_opt_in=os.getenv(SCHEMA_RESET_ENV, ""),
    )


async def _preparar_destino_vps(database_url: str) -> AsyncEngine:
    """Recrea bajo guard y migra el destino PostgreSQL al head actual."""
    database_url = _validated_postgres_url(database_url)
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    return create_async_engine(database_url)


@pytest.mark.integration
async def test_postgresql_v5_datos_ampliados_roundtrip(tmp_path: Path) -> None:
    database_url = _postgres_url()
    source, certs = _create_source_db(tmp_path, fiscal_head=True)
    source_engine = create_engine(f"sqlite:///{source}")
    with source_engine.begin() as connection:
        connection.execute(
            Base.metadata.tables["comprobante_items"]
            .update()
            .values(
                codigo="S" * 101,
                cantidad=Decimal("1.00005"),
                precio_unitario=Decimal("0.1234567890123456789012345678"),
                descuento_porcentaje=Decimal("0.00123"),
            )
        )
        connection.execute(
            Base.metadata.tables["comprobantes"]
            .update()
            .values(
                cotizacion=Decimal("1E200000"), total=Decimal("9007199254740992.01")
            )
        )
    source_engine.dispose()
    package = vps_migration.export_package(
        source,
        certs,
        tmp_path / "packages-v5",
        "clave-destino-larga",
        source_quiesced=True,
    )
    manifest = vps_migration.load_and_verify_manifest(package)
    assert manifest["package_version"] == 5
    assert manifest["alembic_version"] == A01_HEAD
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
    try:
        async with engine.connect() as connection:
            item = (
                (
                    await connection.execute(
                        select(Base.metadata.tables["comprobante_items"])
                    )
                )
                .mappings()
                .one()
            )
            receipt = (
                (await connection.execute(select(Base.metadata.tables["comprobantes"])))
                .mappings()
                .one()
            )
            assert item["cantidad"] == Decimal("1.00005")
            assert item["precio_unitario"] == Decimal("0.1234567890123456789012345678")
            assert item["descuento_porcentaje"] == Decimal("0.00123")
            assert item["codigo"] == "S" * 101
            assert receipt["cotizacion"] == Decimal("1E200000")
            assert receipt["total"] == Decimal("9007199254740992.01")
    finally:
        await engine.dispose()


def _exportar_paquete_terminal(tmp_path: Path) -> Path:
    """Exporta replay legacy y su evidencia terminal individual real."""
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


def _crear_fuente_v4_pf13(tmp_path: Path) -> tuple[Path, Path]:
    """Materializa en SQLite el grafo PF-13 completo del fixture v4."""
    fixture_package, _, _ = _build_v4_package(tmp_path / "material-v4")
    fixture_manifest = vps_migration.load_and_verify_manifest(fixture_package)
    package_rows = _read_package_tables(
        fixture_package,
        fixture_manifest,
        vps_migration_v4.INCLUDED_TABLES,
    )
    source_path = tmp_path / "source-v4.db"
    source_metadata = legacy_metadata()
    engine = create_engine(f"sqlite:///{source_path}", future=True)
    try:
        source_metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32))")
            )
            connection.execute(
                text("INSERT INTO alembic_version VALUES (:version)"),
                {"version": vps_migration_v4.ALEMBIC_HEAD},
            )
            for table_name in vps_migration_v4.INSERT_ORDER:
                rows = package_rows[table_name]
                deferred_columns = vps_migration_v4.DEFERRED_COLUMNS.get(table_name, ())
                if deferred_columns:
                    rows = [
                        {
                            **row,
                            **{column_name: None for column_name in deferred_columns},
                        }
                        for row in rows
                    ]
                if rows:
                    connection.execute(
                        source_metadata.tables[table_name].insert(), rows
                    )
            vps_migration.restore_deferred_columns(
                connection,
                package_rows,
                vps_migration_v4.V4_CONTRACT,
            )
            omitted_lote = {
                **package_rows["lotes_comprobantes"][0],
                "id": 130,
                "nombre_archivo": "legacy-omitido.xlsx",
                "archivo_hash": "3" * 64,
            }
            connection.execute(
                source_metadata.tables["lotes_comprobantes"].insert(), omitted_lote
            )
            connection.execute(
                source_metadata.tables["operaciones_idempotentes"]
                .update()
                .where(source_metadata.tables["operaciones_idempotentes"].c.id == 140)
                .values(lote_id=130)
            )
            connection.execute(
                source_metadata.tables["lotes_duplicados_coordinacion"].insert(),
                [
                    {"empresa_id": 10, "ambiente": "homologacion", "revision": 9},
                    {"empresa_id": 10, "ambiente": "produccion", "revision": 7},
                ],
            )
    finally:
        engine.dispose()
    return source_path, fixture_package / "certs"


def _exportar_paquete_v4_pf13(tmp_path: Path) -> Path:
    """Ejecuta preflight y export reales sobre la SQLite PF-13 sintética."""
    source_path, certs_dir = _crear_fuente_v4_pf13(tmp_path)
    return vps_migration.export_package(
        source_db=source_path,
        certs_dir=certs_dir,
        output_root=tmp_path / "packages-v4",
        target_key_password="clave-destino-larga",
        source_key_password="clave-v3-sintetica",
        source_quiesced=True,
    )


def _write_env_with_password(path: Path, password: str) -> None:
    """Escribe el entorno sintético con la contraseña propia del paquete."""
    _write_production_env(path)
    content = path.read_text(encoding="utf-8")
    current = "ARCA_PRIVATE_KEY_PASSWORD=clave-destino-larga"
    assert current in content
    path.write_text(
        content.replace(current, f"ARCA_PRIVATE_KEY_PASSWORD={password}"),
        encoding="utf-8",
    )


async def _importar_paquete(
    *,
    package: Path,
    database_url: str,
    env_path: Path,
    target_certs: Path,
) -> None:
    """Ejecuta el importador síncrono fuera del event loop asyncpg."""
    database_url = _validated_postgres_url(database_url)
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
    database_url = _validated_postgres_url(database_url)
    await asyncio.to_thread(
        vps_migration.validate_import,
        package,
        database_url,
        env_path,
        target_certs,
    )


def _read_package_tables(
    package: Path,
    manifest: dict[str, Any],
    table_names: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    """Precarga una vez las filas tipadas declaradas por el paquete."""
    return {
        table_name: vps_migration.read_package_rows(package, manifest, table_name)
        for table_name in table_names
    }


async def _read_postgres_tables(
    database_url: str,
    table_names: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    """Lee tablas PostgreSQL en el orden canónico de sus claves primarias."""
    engine = create_async_engine(_validated_postgres_url(database_url))
    try:
        async with engine.connect() as connection:
            rows: dict[str, list[dict[str, Any]]] = {}
            for table_name in table_names:
                rows[table_name] = await connection.run_sync(
                    lambda sync_connection, current_table=table_name: (
                        vps_migration.read_database_rows(
                            sync_connection,
                            current_table,
                        )
                    )
                )
            return rows
    finally:
        await engine.dispose()


async def _read_sequence_states(
    database_url: str,
    table_names: Iterable[str],
) -> dict[str, tuple[str, int, int, bool]]:
    """Lee secuencia, máximo ID y próximo valor sin consumir `nextval`."""
    engine = create_async_engine(_validated_postgres_url(database_url))
    try:
        async with engine.connect() as connection:
            states: dict[str, tuple[str, int, int, bool]] = {}
            for table_name in table_names:
                sequence_name = await connection.scalar(
                    text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
                    {"table_name": table_name},
                )
                assert sequence_name
                maximum_id = await connection.scalar(
                    select(func.max(Base.metadata.tables[table_name].c.id))
                )
                quoted_sequence = vps_migration.quote_postgres_sequence_name(
                    str(sequence_name)
                )
                result = await connection.execute(
                    text(f"SELECT last_value, is_called FROM {quoted_sequence}")
                )
                last_value, is_called = result.one()
                states[table_name] = (
                    str(sequence_name),
                    int(maximum_id or 0),
                    int(last_value),
                    bool(is_called),
                )
            return states
    finally:
        await engine.dispose()


def _assert_imported_rows_match_package(
    actual_rows: dict[str, list[dict[str, Any]]],
    package_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Compara contenido completo con canonización de tipos del migrador."""
    assert set(actual_rows) == set(package_rows)
    for table_name, expected_rows in package_rows.items():
        assert vps_migration.canonicalize_table_rows(
            table_name, actual_rows[table_name]
        ) == vps_migration.canonicalize_table_rows(table_name, expected_rows)


def _assert_sequences_point_to_next_id(
    states: dict[str, tuple[str, int, int, bool]],
    expected_tables: Iterable[str],
) -> None:
    """Acredita todas las secuencias declaradas sin alterar su estado."""
    assert tuple(states) == tuple(expected_tables)
    for _, maximum_id, last_value, is_called in states.values():
        assert last_value == maximum_id + 1
        assert is_called is False


async def _assert_regenerated_and_excluded_tables(
    *,
    database_url: str,
    company_ids: Iterable[int],
    regenerated_tables: Iterable[str],
    excluded_tables: Iterable[str],
) -> None:
    """Verifica coordinadores regenerados y partición excluida vacía."""
    regenerated_tables = tuple(regenerated_tables)
    excluded_tables = tuple(excluded_tables)
    actual = await _read_postgres_tables(
        database_url,
        (*regenerated_tables, *excluded_tables),
    )
    assert regenerated_tables == ("lotes_duplicados_coordinacion",)
    coordinators = actual["lotes_duplicados_coordinacion"]
    assert [
        (row["empresa_id"], row["ambiente"], row["revision"]) for row in coordinators
    ] == [
        (company_id, environment, 0)
        for company_id in sorted(company_ids)
        for environment in ("homologacion", "produccion")
    ]
    assert all(actual[table_name] == [] for table_name in excluded_tables)


async def _assert_v4_relations(database_url: str) -> None:
    """Acredita las aristas PF-13, incluida actual G2 versus intento G1."""
    engine = create_async_engine(_validated_postgres_url(database_url))
    try:
        async with engine.connect() as connection:
            operations = await connection.execute(text("""
                    SELECT id, operacion_raiz_id, duplicados_generacion_id, lote_id
                    FROM operaciones_idempotentes
                    WHERE id IN (140, 200, 201, 202, 203)
                    ORDER BY id
                    """))
            assert [tuple(row) for row in operations] == [
                (140, None, None, None),
                (200, 200, 301, 100),
                (201, 200, 302, 100),
                (202, None, None, 90),
                (203, None, None, None),
            ]
            operation_control = await connection.scalar(
                text(
                    "SELECT control_duplicados_json "
                    "FROM operaciones_idempotentes WHERE id = 200"
                )
            )
            assert operation_control["seleccion_original"] == [{"grupo_id": 101}]

            generations = await connection.execute(text("""
                    SELECT id, operacion_id, generacion,
                           aceptacion_origen_generacion_id
                    FROM lotes_duplicados_evidencias
                    ORDER BY id
                    """))
            assert [tuple(row) for row in generations] == [
                (300, 200, 1, 300),
                (301, 200, 2, 300),
                (302, 201, 1, 300),
            ]
            blocks = await connection.execute(text("""
                    SELECT id, generacion_id, operacion_id, lote_id
                    FROM lotes_duplicados_coincidencias
                    ORDER BY id
                    """))
            assert [tuple(row) for row in blocks] == [
                (400, 300, 200, 100),
                (401, 301, 200, 100),
                (402, 302, 201, 100),
            ]
            members = await connection.execute(text("""
                    SELECT id, bloque_id, lado, grupo_id, comprobante_id
                    FROM lotes_duplicados_coincidencias_miembros
                    ORDER BY id
                    """))
            assert [tuple(row) for row in members] == [
                (500, 400, "actual", 101, None),
                (501, 400, "anterior", None, 110),
                (502, 401, "actual", 101, None),
                (503, 401, "anterior", None, 110),
                (504, 402, "actual", 101, None),
                (505, 402, "anterior", None, 110),
            ]
            attempts = await connection.execute(text("""
                    SELECT id, operacion_id, guarda_rece_id,
                           duplicados_generacion_id, lote_id, grupo_id
                    FROM intentos_emision_fiscal
                    ORDER BY id
                    """))
            assert [tuple(row) for row in attempts] == [
                (700, 200, 600, 300, 100, 101),
                (701, 202, None, None, 90, 91),
            ]
            group_counts = await connection.execute(text("""
                    SELECT lote_id, COUNT(*)
                    FROM lotes_comprobantes_grupos
                    GROUP BY lote_id
                    ORDER BY lote_id
                    """))
            assert [tuple(row) for row in group_counts] == [(90, 1), (100, 100)]
            reservation = await connection.execute(text("""
                    SELECT id, duplicados_reserva_operacion_id
                    FROM lotes_comprobantes_grupos
                    WHERE id = 101
                    """))
            assert tuple(reservation.one()) == (101, 200)
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_vps_v2_roundtrip_y_validate(
    tmp_path: Path,
) -> None:
    """R5 preserva replay legacy y evidencia terminal individual material."""
    database_url = _postgres_url()
    package = _exportar_paquete_terminal(tmp_path)
    manifest = vps_migration.load_and_verify_manifest(package)
    assert manifest["package_version"] == 4
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

    engine = create_async_engine(_validated_postgres_url(database_url))
    try:
        async with engine.connect() as connection:
            operations = await connection.execute(text("""
                    SELECT id, idempotency_key, lote_id, rece_snapshot_hash
                    FROM operaciones_idempotentes
                    ORDER BY id
                    """))
            assert [tuple(row) for row in operations] == [
                (140, "vps-guarda-terminal", None, _rece_digest()),
                (150, "vps-operacion-150", None, None),
            ]
            association = await connection.execute(text("""
                    SELECT operacion_id, empresa_id, punto_venta_id, ambiente,
                           elegibilidad_revision_id, punto_venta_revision_fiscal
                    FROM operaciones_idempotentes_elegibilidad_rece
                    """))
            assert tuple(association.one()) == (140, 10, 40, "produccion", 45, 1)
            heads = await connection.execute(text("""
                    SELECT a.ambiente, a.revision_actual_id, r.revision
                    FROM puntos_venta_elegibilidad_rece_actual a
                    JOIN puntos_venta_elegibilidad_rece_revisiones r
                      ON r.id = a.revision_actual_id
                    ORDER BY a.ambiente
                    """))
            assert [tuple(row) for row in heads] == [
                ("homologacion", 41, 1),
                ("produccion", 45, 2),
            ]
            attempts = await connection.execute(text("""
                    SELECT id, operacion_id, guarda_rece_id, estado,
                           duplicados_generacion_id, lote_id, grupo_id
                    FROM intentos_emision_fiscal
                    ORDER BY id
                    """))
            assert [tuple(row) for row in attempts] == [
                (143, 140, 142, "fallido_verificado", None, None, None)
            ]
            guards = await connection.execute(text("""
                    SELECT id, operacion_id, fase
                    FROM puntos_venta_guardas_emision_rece
                    ORDER BY id
                    """))
            assert [tuple(row) for row in guards] == [(142, 140, "cerrada_pre_arca")]
            assert (
                await connection.scalar(text("SELECT COUNT(*) FROM lotes_comprobantes"))
                == 0
            )
    finally:
        await engine.dispose()

    sequence_states = await _read_sequence_states(
        database_url, vps_migration_v4.SEQUENCE_TABLES
    )
    _assert_sequences_point_to_next_id(
        sequence_states, vps_migration_v4.SEQUENCE_TABLES
    )
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
async def test_postgresql_v4_roundtrip_pf13_completo(tmp_path: Path) -> None:
    """Roundtrip v4 conserva contenido, grafo, tipos y todas las secuencias."""
    database_url = _postgres_url()
    package = _exportar_paquete_v4_pf13(tmp_path)
    manifest = vps_migration.load_and_verify_manifest(package)
    contract = vps_migration.select_import_contract(manifest)
    assert contract is vps_migration_v4.V4_CONTRACT
    assert tuple(manifest["complete_tables"]) == vps_migration_v4.COMPLETE_TABLES
    assert tuple(manifest["filtered_tables"]) == vps_migration_v4.FILTERED_TABLES
    assert tuple(manifest["regenerated_tables"]) == vps_migration_v4.REGENERATED_TABLES
    assert tuple(manifest["excluded_tables"]) == vps_migration_v4.EXCLUDED_TABLES
    package_rows = _read_package_tables(package, manifest, contract.included_tables)
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

    actual_rows = await _read_postgres_tables(database_url, contract.included_tables)
    _assert_imported_rows_match_package(actual_rows, package_rows)
    await _assert_regenerated_and_excluded_tables(
        database_url=database_url,
        company_ids=(row["id"] for row in package_rows["empresas"]),
        regenerated_tables=contract.regenerated_tables,
        excluded_tables=contract.excluded_tables,
    )
    await _assert_v4_relations(database_url)
    sequence_states = await _read_sequence_states(
        database_url, contract.sequence_tables
    )
    _assert_sequences_point_to_next_id(sequence_states, contract.sequence_tables)

    receipt = actual_rows["comprobantes"][0]
    operation = next(
        row for row in actual_rows["operaciones_idempotentes"] if row["id"] == 200
    )
    lot = next(row for row in actual_rows["lotes_comprobantes"] if row["id"] == 100)
    assert isinstance(receipt["fecha_emision"], date)
    assert not isinstance(receipt["fecha_emision"], datetime)
    assert isinstance(receipt["total"], Decimal)
    assert isinstance(operation["response_json"], dict)
    assert isinstance(operation["solicitud_emision_at"], datetime)
    assert isinstance(lot["procesamiento_async"], bool)
    assert isinstance(
        actual_rows["formatos_importacion_versiones"][0]["configuracion_json"],
        dict,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_v3_historico_material_roundtrip(tmp_path: Path) -> None:
    """El paquete v3 material se adapta sin inventar evidencia PF-13."""
    database_url = _postgres_url()
    package = _build_historical_v3_package(tmp_path / "material-v3")
    manifest = vps_migration.load_and_verify_manifest(package)
    contract = vps_migration.select_import_contract(manifest)
    assert contract is vps_migration_v3.V3_CONTRACT
    assert manifest["package_version"] == 3
    assert manifest["alembic_version"] == vps_migration_v3.ALEMBIC_HEAD
    package_rows = _read_package_tables(package, manifest, contract.included_tables)
    env_path = tmp_path / ".env.production"
    _write_env_with_password(env_path, "clave-v3-sintetica")
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

    actual_rows = await _read_postgres_tables(database_url, contract.included_tables)
    _assert_imported_rows_match_package(actual_rows, package_rows)
    operation = actual_rows["operaciones_idempotentes"][0]
    assert operation["lote_id"] is None
    assert all(
        operation[column_name] is None
        for column_name in vps_migration_v3.TARGET_NULL_ADDITIONS[
            "operaciones_idempotentes"
        ]
    )
    await _assert_regenerated_and_excluded_tables(
        database_url=database_url,
        company_ids=(row["id"] for row in package_rows["empresas"]),
        regenerated_tables=("lotes_duplicados_coordinacion",),
        excluded_tables=contract.excluded_tables,
    )
    adapter_empty = await _read_postgres_tables(
        database_url,
        contract.adapter_target_empty_tables[1:],
    )
    assert all(rows == [] for rows in adapter_empty.values())
    sequence_states = await _read_sequence_states(
        database_url, contract.sequence_tables
    )
    _assert_sequences_point_to_next_id(sequence_states, contract.sequence_tables)
    assert {path.name for path in target_certs.iterdir()} == set(
        manifest["certificate_files"]
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_vps_v2_dirty_y_rollback_limpian_solo_propios(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Destino sucio y rollback v4 preservan filas, secuencias y certs ajenos."""
    database_url = _postgres_url()
    package = _exportar_paquete_v4_pf13(tmp_path)
    manifest = vps_migration.load_and_verify_manifest(package)
    contract = vps_migration.select_import_contract(manifest)
    assert contract is vps_migration_v4.V4_CONTRACT
    env_path = tmp_path / ".env.production"
    _write_production_env(env_path)
    target_certs = tmp_path / "target-certs"
    target_certs.mkdir()
    preexisting_name = sorted(manifest["certificate_files"])[0]
    preexisting_info = manifest["certificate_files"][preexisting_name]
    preexisting_path = target_certs / preexisting_name
    preexisting_bytes = (package / preexisting_info["path"]).read_bytes()
    preexisting_path.write_bytes(preexisting_bytes)

    engine = await _preparar_destino_vps(database_url)
    async with engine.begin() as connection:
        await connection.execute(text("""
                INSERT INTO empresas (
                    id, razon_social, cuit, condicion_iva, domicilio,
                    localidad, provincia, codigo_postal, inicio_actividades,
                    created_at, updated_at
                ) VALUES (
                    999, 'Destino ajeno', '20999999991', 'RI', 'Sintético',
                    'Sintética', 'Sintética', '1000', DATE '2020-01-01',
                    now(), now()
                )
                """))
    await engine.dispose()

    with pytest.raises(vps_migration.MigrationError, match="no está limpia"):
        await _importar_paquete(
            package=package,
            database_url=database_url,
            env_path=env_path,
            target_certs=target_certs,
        )
    dirty_rows = await _read_postgres_tables(database_url, ("empresas",))
    assert [(row["id"], row["razon_social"]) for row in dirty_rows["empresas"]] == [
        (999, "Destino ajeno")
    ]
    assert {path.name for path in target_certs.iterdir()} == {preexisting_name}
    assert preexisting_path.read_bytes() == preexisting_bytes

    engine = await _preparar_destino_vps(database_url)
    await engine.dispose()
    rollback_tables = tuple(
        dict.fromkeys(
            (
                *contract.included_tables,
                *contract.regenerated_tables,
                *contract.excluded_tables,
            )
        )
    )
    rows_before = await _read_postgres_tables(database_url, rollback_tables)
    sequences_before = await _read_sequence_states(
        database_url, contract.sequence_tables
    )
    real_sequence_verification = vps_migration.verify_postgres_sequences

    def fail_after_postflight_and_sequences(conn: object, selected: object) -> None:
        """Falla tras postflight y tras verificar cada `RESTART WITH`."""
        real_sequence_verification(conn, selected)
        raise vps_migration.MigrationError("rollback sintético post-secuencias")

    monkeypatch.setattr(
        vps_migration,
        "verify_postgres_sequences",
        fail_after_postflight_and_sequences,
    )
    with pytest.raises(
        vps_migration.MigrationError,
        match="rollback sintético post-secuencias",
    ):
        await _importar_paquete(
            package=package,
            database_url=database_url,
            env_path=env_path,
            target_certs=target_certs,
        )

    rows_after = await _read_postgres_tables(database_url, rollback_tables)
    sequences_after = await _read_sequence_states(
        database_url, contract.sequence_tables
    )
    assert rows_after == rows_before
    assert sequences_after == sequences_before
    assert {path.name for path in target_certs.iterdir()} == {preexisting_name}
    assert preexisting_path.read_bytes() == preexisting_bytes
