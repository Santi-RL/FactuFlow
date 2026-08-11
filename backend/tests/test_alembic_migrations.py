"""Tests de migraciones Alembic en SQLite."""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
REVISION_FORMATOS_IMPORTACION = "a6b7c8d9e0f1"
REVISION_RECEPTOR_SNAPSHOT = "e5f6a7b8c9d0"
REVISION_ANTERIOR_INTEGRIDAD_FISCAL = "f7a8b9c0d1e2"
REVISION_INTEGRIDAD_FISCAL = "a8b9c0d1e2f3"
REVISION_ELEGIBILIDAD_RECE = "b9c0d1e2f3a4"
REVISION_PF19C_LEGACY = "c0d1e2f3a4b"
COLUMNAS_FORMATOS_LOTE = {
    "mapeo_usado_json",
    "headers_detectados_json",
    "formato_importacion_id",
    "formato_importacion_version_id",
}
CAE_SINTETICO = "12345678901234"
FECHA_SINTETICA = "2026-07-13"
FECHA_HORA_SINTETICA = "2026-07-13 12:00:00"


def _run_alembic(
    action: str,
    revision: str,
    database_url: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> None:
    """Ejecuta Alembic contra una base temporal de test."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["APP_ENV"] = "testing"
    env.pop("PF19B_SQLITE_BACKUP_CONFIRMED", None)
    env.pop("PF19B_SQLITE_BACKUP_PATH", None)
    env.update(extra_env or {})

    result = subprocess.run(
        [sys.executable, "-m", "alembic", action, revision],
        cwd=BACKEND_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def _run_alembic_failure(
    action: str,
    revision: str,
    database_url: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> str:
    """Ejecuta Alembic y devuelve la salida de un fallo esperado."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["APP_ENV"] = "testing"
    env.pop("PF19B_SQLITE_BACKUP_CONFIRMED", None)
    env.pop("PF19B_SQLITE_BACKUP_PATH", None)
    env.update(extra_env or {})

    result = subprocess.run(
        [sys.executable, "-m", "alembic", action, revision],
        cwd=BACKEND_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    return result.stdout + result.stderr


def _table_columns(db_path: Path, table_name: str) -> set[str]:
    """Devuelve las columnas existentes de una tabla SQLite."""
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _table_sql(db_path: Path, table_name: str) -> str:
    """Devuelve el DDL SQLite vigente de una tabla."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
    assert row is not None
    return str(row[0])


def _alembic_version(db_path: Path) -> str:
    """Devuelve la revisión Alembic aplicada en la base SQLite."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert row is not None
    return str(row[0])


def _backup_env_pf19(db_path: Path, backup_path: Path) -> dict[str, str]:
    """Copia y declara un backup SQLite físico para la puerta PF-19B."""
    shutil.copy2(db_path, backup_path)
    return {
        "PF19B_SQLITE_BACKUP_CONFIRMED": "1",
        "PF19B_SQLITE_BACKUP_PATH": str(backup_path.resolve()),
    }


def _foreign_key_targets(db_path: Path, table_name: str) -> set[str]:
    """Devuelve las tablas referenciadas con FKs SQLite activables."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        return {
            str(row[2])
            for row in conn.execute(f"PRAGMA foreign_key_list({table_name})")
        }


def _foreign_key_actions(
    db_path: Path,
    table_name: str,
    column_name: str,
    referred_table: str,
) -> set[str]:
    """Devuelve políticas ON DELETE de las FKs que incluyen una columna."""
    with sqlite3.connect(db_path) as conn:
        return {
            str(row[6]).upper()
            for row in conn.execute(f"PRAGMA foreign_key_list({table_name})")
            if row[2] == referred_table and row[3] == column_name
        }


def _crear_contexto_fiscal_sintetico(db_path: Path) -> None:
    """Inserta emisor y punto de venta sintéticos para las regresiones."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO empresas (
                id, razon_social, cuit, condicion_iva, domicilio, localidad,
                provincia, codigo_postal, inicio_actividades, created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "Emisor sintético",
                "20000000001",
                "RI",
                "Domicilio sintético",
                "Localidad sintética",
                "Provincia sintética",
                "1000",
                FECHA_SINTETICA,
                FECHA_HORA_SINTETICA,
                FECHA_HORA_SINTETICA,
            ),
        )
        conn.execute(
            """
            INSERT INTO puntos_venta (
                id, numero, nombre, es_webservice, bloqueado, activo,
                empresa_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                41,
                "Punto sintético",
                1,
                0,
                1,
                1,
                FECHA_HORA_SINTETICA,
            ),
        )


def _insertar_comprobante_sintetico(
    db_path: Path,
    *,
    estado: str,
    cae: str | None,
    cae_vencimiento: str | None,
) -> None:
    """Inserta un comprobante sintético en el esquema anterior a PF-01B."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO comprobantes (
                id, tipo_comprobante, concepto, numero, fecha_emision,
                subtotal, descuento, iva_21, iva_10_5, iva_27,
                otros_impuestos, total, cae, cae_vencimiento, estado,
                moneda, cotizacion, empresa_id, punto_venta_id,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                1,
                6,
                1,
                201,
                FECHA_SINTETICA,
                100,
                0,
                21,
                0,
                0,
                0,
                121,
                cae,
                cae_vencimiento,
                estado,
                "PES",
                1,
                1,
                1,
                FECHA_HORA_SINTETICA,
                FECHA_HORA_SINTETICA,
            ),
        )


def _insertar_intento_sintetico(
    db_path: Path,
    *,
    row_id: int,
    estado: str,
    numero_planificado: int = 101,
) -> None:
    """Inserta un intento fiscal sintético en el esquema anterior a PF-01B."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO intentos_emision_fiscal (
                id, tipo_comprobante, punto_venta_numero, numero_planificado,
                fecha_emision, total, payload_hash, huella_logica, estado,
                created_at, updated_at, empresa_id, punto_venta_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                6,
                41,
                numero_planificado,
                FECHA_SINTETICA,
                121,
                f"{row_id:064d}",
                f"{row_id + 1:064d}",
                estado,
                FECHA_HORA_SINTETICA,
                FECHA_HORA_SINTETICA,
                1,
                1,
            ),
        )


def _preparar_base_pre_pf01b(tmp_path: Path) -> tuple[Path, str]:
    """Crea una base en la revisión inmediatamente anterior a PF-01B."""
    db_path = tmp_path / "factuflow.db"
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"
    _run_alembic(
        "upgrade",
        REVISION_ANTERIOR_INTEGRIDAD_FISCAL,
        database_url,
    )
    _crear_contexto_fiscal_sintetico(db_path)
    return db_path, database_url


def test_sqlite_downgrade_formatos_importacion_remueve_columnas_de_lotes(
    tmp_path: Path,
) -> None:
    """El downgrade debe remover columnas de formatos sin depender de PostgreSQL."""
    db_path = tmp_path / "factuflow.db"
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"

    _run_alembic("upgrade", REVISION_FORMATOS_IMPORTACION, database_url)
    assert COLUMNAS_FORMATOS_LOTE <= _table_columns(db_path, "lotes_comprobantes")

    _run_alembic("downgrade", REVISION_RECEPTOR_SNAPSHOT, database_url)

    assert not COLUMNAS_FORMATOS_LOTE & _table_columns(db_path, "lotes_comprobantes")
    assert _alembic_version(db_path) == REVISION_RECEPTOR_SNAPSHOT


def test_sqlite_integridad_fiscal_upgrade_downgrade_y_reupgrade(
    tmp_path: Path,
) -> None:
    """PF-01B debe instalar y retirar solo sus checks con datos válidos."""
    db_path, database_url = _preparar_base_pre_pf01b(tmp_path)
    _insertar_intento_sintetico(
        db_path,
        row_id=1,
        estado="en_proceso",
    )
    _insertar_comprobante_sintetico(
        db_path,
        estado="autorizado",
        cae=CAE_SINTETICO,
        cae_vencimiento=FECHA_SINTETICA,
    )

    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)

    assert _alembic_version(db_path) == REVISION_INTEGRIDAD_FISCAL
    assert "ck_intentos_emision_fiscal_estado_valido" in _table_sql(
        db_path, "intentos_emision_fiscal"
    )
    comprobantes_sql = _table_sql(db_path, "comprobantes")
    assert "ck_comprobantes_estado_valido" in comprobantes_sql
    assert "ck_comprobantes_estado_cae_coherente" in comprobantes_sql

    _run_alembic(
        "downgrade",
        REVISION_ANTERIOR_INTEGRIDAD_FISCAL,
        database_url,
    )

    assert _alembic_version(db_path) == REVISION_ANTERIOR_INTEGRIDAD_FISCAL
    assert "ck_intentos_emision_fiscal_estado_valido" not in _table_sql(
        db_path, "intentos_emision_fiscal"
    )
    comprobantes_sql = _table_sql(db_path, "comprobantes")
    assert "ck_comprobantes_estado_valido" not in comprobantes_sql
    assert "ck_comprobantes_estado_cae_coherente" not in comprobantes_sql

    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    assert _alembic_version(db_path) == REVISION_INTEGRIDAD_FISCAL


@pytest.mark.parametrize(
    ("conflicto", "categoria"),
    (
        ("intento_estado", "intentos_estado_desconocido=1"),
        ("comprobante_estado", "comprobantes_estado_desconocido=1"),
        (
            "autorizado_incompleto",
            "comprobantes_autorizados_incompletos=1",
        ),
        (
            "no_autorizado_con_cae",
            "comprobantes_no_autorizados_con_cae=1",
        ),
        ("reservas_duplicadas", "reservas_activas_duplicadas=1"),
    ),
)
def test_sqlite_integridad_fiscal_preflight_bloquea_datos_ambiguos(
    tmp_path: Path,
    conflicto: str,
    categoria: str,
) -> None:
    """El preflight debe abortar sin DDL ni avance de revisión."""
    db_path, database_url = _preparar_base_pre_pf01b(tmp_path)

    if conflicto == "intento_estado":
        _insertar_intento_sintetico(
            db_path,
            row_id=1,
            estado="estado_inexistente",
        )
    elif conflicto == "comprobante_estado":
        _insertar_comprobante_sintetico(
            db_path,
            estado="estado_inexistente",
            cae=None,
            cae_vencimiento=None,
        )
    elif conflicto == "autorizado_incompleto":
        _insertar_comprobante_sintetico(
            db_path,
            estado="autorizado",
            cae=None,
            cae_vencimiento=FECHA_SINTETICA,
        )
    elif conflicto == "no_autorizado_con_cae":
        _insertar_comprobante_sintetico(
            db_path,
            estado="pendiente",
            cae=CAE_SINTETICO,
            cae_vencimiento=None,
        )
    else:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP INDEX uq_intentos_emision_fiscal_reserva_activa")
        _insertar_intento_sintetico(
            db_path,
            row_id=1,
            estado="en_proceso",
        )
        _insertar_intento_sintetico(
            db_path,
            row_id=2,
            estado="requiere_reconciliacion",
        )

    output = _run_alembic_failure(
        "upgrade",
        REVISION_INTEGRIDAD_FISCAL,
        database_url,
    )

    assert categoria in output
    assert _alembic_version(db_path) == REVISION_ANTERIOR_INTEGRIDAD_FISCAL
    assert "ck_intentos_emision_fiscal_estado_valido" not in _table_sql(
        db_path, "intentos_emision_fiscal"
    )
    comprobantes_sql = _table_sql(db_path, "comprobantes")
    assert "ck_comprobantes_estado_valido" not in comprobantes_sql
    assert "ck_comprobantes_estado_cae_coherente" not in comprobantes_sql


def test_sqlite_pf19b_upgrade_downgrade_reupgrade_fail_closed(
    tmp_path: Path,
) -> None:
    """PF-19B debe migrar cerrado y revertir solo con backups congruentes."""
    db_path = tmp_path / "pf19b.db"
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    _crear_contexto_fiscal_sintetico(db_path)

    upgrade_env = _backup_env_pf19(db_path, tmp_path / "pf19b-pre-upgrade.db")
    _run_alembic(
        "upgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
        extra_env=upgrade_env,
    )

    assert _alembic_version(db_path) == REVISION_ELEGIBILIDAD_RECE
    assert "revision_fiscal" in _table_columns(db_path, "puntos_venta")
    assert "rece_snapshot_hash" in _table_columns(db_path, "operaciones_idempotentes")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        revisiones = conn.execute(
            "SELECT ambiente, estado, fuente, revision FROM "
            "puntos_venta_elegibilidad_rece_revisiones ORDER BY ambiente"
        ).fetchall()
        cabezas = conn.execute(
            "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_actual"
        ).fetchone()
        foreign_key_check = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert revisiones == [
        ("homologacion", "no_verificado", "migracion_legacy", 1),
        ("produccion", "no_verificado", "migracion_legacy", 1),
    ]
    assert cabezas == (2,)
    assert foreign_key_check == []
    assert {
        "puntos_venta_guardas_emision_rece",
        "puntos_venta_elegibilidad_rece_revisiones",
        "operaciones_idempotentes",
    } <= _foreign_key_targets(db_path, "intentos_emision_fiscal")
    assert _foreign_key_actions(
        db_path,
        "intentos_emision_fiscal",
        "lote_id",
        "lotes_comprobantes",
    ) == {"RESTRICT"}
    assert _foreign_key_actions(
        db_path,
        "intentos_emision_fiscal",
        "grupo_id",
        "lotes_comprobantes_grupos",
    ) == {"RESTRICT"}

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        revision_produccion = conn.execute(
            "SELECT id FROM puntos_venta_elegibilidad_rece_revisiones "
            "WHERE punto_venta_id = 1 AND ambiente = 'produccion'"
        ).fetchone()
        assert revision_produccion is not None
        revision_id = int(revision_produccion[0])
        for operacion_id in (10, 11):
            conn.execute(
                "INSERT INTO operaciones_idempotentes ("
                "id, idempotency_key, tipo_operacion, payload_hash, estado, "
                "created_at, updated_at, empresa_id, rece_snapshot_hash"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    operacion_id,
                    f"pf19b-{operacion_id}",
                    "emitir_comprobante",
                    f"{operacion_id:064d}",
                    "en_proceso",
                    FECHA_HORA_SINTETICA,
                    FECHA_HORA_SINTETICA,
                    1,
                    f"{operacion_id + 20:064d}",
                ),
            )
        conn.execute(
            "INSERT INTO operaciones_idempotentes_elegibilidad_rece ("
            "id, operacion_id, empresa_id, punto_venta_id, ambiente, "
            "elegibilidad_revision_id, punto_venta_revision_fiscal, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (20, 10, 1, 1, "produccion", revision_id, 1, FECHA_HORA_SINTETICA),
        )
        conn.execute(
            "INSERT INTO puntos_venta_guardas_emision_rece ("
            "id, token, fase, operacion_id, empresa_id, punto_venta_id, "
            "ambiente, elegibilidad_revision_id, punto_venta_revision_fiscal, "
            "created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                30,
                "6" * 64,
                "pre_arca",
                10,
                1,
                1,
                "produccion",
                revision_id,
                1,
                FECHA_HORA_SINTETICA,
                FECHA_HORA_SINTETICA,
            ),
        )
        for lote_id in (50, 51):
            conn.execute(
                "INSERT INTO lotes_comprobantes ("
                "id, nombre_archivo, archivo_hash, estado, modo_procesamiento, "
                "procesamiento_async, total_filas, total_grupos, grupos_validos, "
                "grupos_con_error, grupos_emitidos, grupos_fallidos, "
                "grupos_reconciliados_externos, grupos_descartados, created_at, "
                "updated_at, empresa_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    lote_id,
                    f"pf19b-{lote_id}.xlsx",
                    f"{lote_id:064d}",
                    "validado",
                    "sincronico",
                    0,
                    1,
                    1,
                    1,
                    0,
                    0,
                    0,
                    0,
                    0,
                    FECHA_HORA_SINTETICA,
                    FECHA_HORA_SINTETICA,
                    1,
                ),
            )
        conn.execute(
            "INSERT INTO lotes_comprobantes_grupos ("
            "id, comprobante_ref, orden, estado, tipo_comprobante, "
            "punto_venta_numero, total_estimado, created_at, updated_at, "
            "lote_id, empresa_id, punto_venta_id, ambiente, "
            "punto_venta_elegibilidad_revision_id, punto_venta_revision_fiscal"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                60,
                "PF19B-GRUPO-1",
                1,
                "validado",
                6,
                41,
                121,
                FECHA_HORA_SINTETICA,
                FECHA_HORA_SINTETICA,
                50,
                1,
                1,
                "produccion",
                revision_id,
                1,
            ),
        )
        conn.execute(
            "INSERT INTO intentos_emision_fiscal ("
            "id, tipo_comprobante, punto_venta_numero, numero_planificado, "
            "fecha_emision, total, payload_hash, huella_logica, estado, "
            "created_at, updated_at, operacion_id, empresa_id, punto_venta_id, "
            "ambiente, punto_venta_elegibilidad_revision_id, "
            "punto_venta_revision_fiscal, guarda_rece_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                40,
                6,
                41,
                1,
                FECHA_SINTETICA,
                121,
                "7" * 64,
                "8" * 64,
                "en_proceso",
                FECHA_HORA_SINTETICA,
                FECHA_HORA_SINTETICA,
                10,
                1,
                1,
                "produccion",
                revision_id,
                1,
                30,
            ),
        )
        conn.commit()

        conn.execute(
            "INSERT INTO intentos_emision_fiscal ("
            "id, tipo_comprobante, punto_venta_numero, numero_planificado, "
            "fecha_emision, total, payload_hash, huella_logica, estado, "
            "created_at, updated_at, operacion_id, empresa_id, punto_venta_id, "
            "lote_id, grupo_id, ambiente, punto_venta_elegibilidad_revision_id, "
            "punto_venta_revision_fiscal, guarda_rece_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                42,
                6,
                41,
                2,
                FECHA_SINTETICA,
                121,
                "b" * 64,
                "c" * 64,
                "en_proceso",
                FECHA_HORA_SINTETICA,
                FECHA_HORA_SINTETICA,
                10,
                1,
                1,
                50,
                60,
                "produccion",
                revision_id,
                1,
                30,
            ),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO lotes_comprobantes_grupos ("
                "id, comprobante_ref, orden, estado, tipo_comprobante, "
                "punto_venta_numero, total_estimado, created_at, updated_at, "
                "lote_id, empresa_id, punto_venta_id, ambiente, "
                "punto_venta_elegibilidad_revision_id, punto_venta_revision_fiscal"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    61,
                    "PF19B-GRUPO-PARCIAL",
                    2,
                    "validado",
                    6,
                    41,
                    121,
                    FECHA_HORA_SINTETICA,
                    FECHA_HORA_SINTETICA,
                    50,
                    1,
                    1,
                    None,
                    revision_id,
                    1,
                ),
            )
        conn.rollback()

        for sentencia in (
            "UPDATE lotes_comprobantes_grupos "
            "SET punto_venta_revision_fiscal = NULL WHERE id = 60",
            "UPDATE lotes_comprobantes_grupos "
            "SET punto_venta_numero = NULL WHERE id = 60",
            "UPDATE lotes_comprobantes_grupos "
            "SET tipo_comprobante = NULL WHERE id = 60",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sentencia)
            conn.rollback()
        grupo_persistido = conn.execute(
            "SELECT ambiente, punto_venta_revision_fiscal, "
            "punto_venta_numero, tipo_comprobante "
            "FROM lotes_comprobantes_grupos WHERE id = 60"
        ).fetchone()
        assert grupo_persistido == ("produccion", 1, 41, 6)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO intentos_emision_fiscal ("
                "id, tipo_comprobante, punto_venta_numero, numero_planificado, "
                "fecha_emision, total, payload_hash, huella_logica, estado, "
                "created_at, updated_at, operacion_id, empresa_id, punto_venta_id, "
                "lote_id, grupo_id, ambiente, "
                "punto_venta_elegibilidad_revision_id, "
                "punto_venta_revision_fiscal, guarda_rece_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    43,
                    6,
                    41,
                    3,
                    FECHA_SINTETICA,
                    121,
                    "d" * 64,
                    "e" * 64,
                    "en_proceso",
                    FECHA_HORA_SINTETICA,
                    FECHA_HORA_SINTETICA,
                    10,
                    1,
                    1,
                    51,
                    60,
                    "produccion",
                    revision_id,
                    1,
                    30,
                ),
            )
        conn.rollback()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO intentos_emision_fiscal ("
                "id, tipo_comprobante, punto_venta_numero, numero_planificado, "
                "fecha_emision, total, payload_hash, huella_logica, estado, "
                "created_at, updated_at, operacion_id, empresa_id, punto_venta_id, "
                "ambiente, punto_venta_elegibilidad_revision_id, "
                "punto_venta_revision_fiscal, guarda_rece_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    41,
                    6,
                    41,
                    2,
                    FECHA_SINTETICA,
                    121,
                    "9" * 64,
                    "a" * 64,
                    "en_proceso",
                    FECHA_HORA_SINTETICA,
                    FECHA_HORA_SINTETICA,
                    11,
                    1,
                    1,
                    "produccion",
                    revision_id,
                    1,
                    30,
                ),
            )
        conn.rollback()
        conn.execute("DELETE FROM intentos_emision_fiscal WHERE id IN (40, 42)")
        conn.execute("DELETE FROM lotes_comprobantes_grupos WHERE id = 60")
        conn.execute("DELETE FROM lotes_comprobantes WHERE id IN (50, 51)")
        conn.execute("DELETE FROM puntos_venta_guardas_emision_rece WHERE id = 30")
        conn.execute(
            "DELETE FROM operaciones_idempotentes_elegibilidad_rece WHERE id = 20"
        )
        conn.execute("DELETE FROM operaciones_idempotentes WHERE id IN (10, 11)")
        conn.commit()

    downgrade_env = _backup_env_pf19(db_path, tmp_path / "pf19b-pre-downgrade.db")
    _run_alembic(
        "downgrade",
        REVISION_INTEGRIDAD_FISCAL,
        database_url,
        extra_env=downgrade_env,
    )
    assert _alembic_version(db_path) == REVISION_INTEGRIDAD_FISCAL
    assert "revision_fiscal" not in _table_columns(db_path, "puntos_venta")
    assert _foreign_key_actions(
        db_path,
        "intentos_emision_fiscal",
        "lote_id",
        "lotes_comprobantes",
    ) == {"SET NULL"}
    assert _foreign_key_actions(
        db_path,
        "intentos_emision_fiscal",
        "grupo_id",
        "lotes_comprobantes_grupos",
    ) == {"SET NULL"}

    reupgrade_env = _backup_env_pf19(db_path, tmp_path / "pf19b-pre-reupgrade.db")
    _run_alembic(
        "upgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
        extra_env=reupgrade_env,
    )
    assert _alembic_version(db_path) == REVISION_ELEGIBILIDAD_RECE


def test_sqlite_pf19b_bloquea_sin_backup_antes_del_ddl(tmp_path: Path) -> None:
    """La falta de backup físico debe abortar antes de agregar columnas PF-19B."""
    db_path = tmp_path / "pf19b-sin-backup.db"
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)

    output = _run_alembic_failure(
        "upgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
    )

    assert "PF19B_SQLITE_BACKUP_CONFIRMED=1" in output
    assert _alembic_version(db_path) == REVISION_INTEGRIDAD_FISCAL
    assert "revision_fiscal" not in _table_columns(db_path, "puntos_venta")


def test_sqlite_pf19b_rechaza_backup_distinto_con_igual_conteo(
    tmp_path: Path,
) -> None:
    """Un backup con las mismas filas pero distinto contenido no habilita DDL."""
    db_path = tmp_path / "pf19b-backup-origen.db"
    backup_path = tmp_path / "pf19b-backup-distinto.db"
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    _crear_contexto_fiscal_sintetico(db_path)
    backup_env = _backup_env_pf19(db_path, backup_path)
    with sqlite3.connect(backup_path) as conn:
        conn.execute(
            "UPDATE puntos_venta SET nombre = ? WHERE id = ?",
            ("Punto sintético distinto", 1),
        )

    output = _run_alembic_failure(
        "upgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
        extra_env=backup_env,
    )

    assert "equivalencia semántica exacta" in output
    assert _alembic_version(db_path) == REVISION_INTEGRIDAD_FISCAL
    assert "revision_fiscal" not in _table_columns(db_path, "puntos_venta")


def test_sqlite_pf19c_upgrade_downgrade_reupgrade_y_journal_append_only(
    tmp_path: Path,
) -> None:
    """PF-19C instala journal protegido y solo permite downgrade sin evidencia."""
    db_path = tmp_path / "pf19c-migracion.db"
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    backup_env = _backup_env_pf19(db_path, tmp_path / "pf19c-pf19b-backup.db")
    _run_alembic(
        "upgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
        extra_env=backup_env,
    )
    _run_alembic("upgrade", REVISION_PF19C_LEGACY, database_url)
    assert "errores_arca_json" in _table_columns(db_path, "intentos_emision_fiscal")
    _run_alembic("downgrade", REVISION_ELEGIBILIDAD_RECE, database_url)
    assert "errores_arca_json" not in _table_columns(db_path, "intentos_emision_fiscal")
    _run_alembic("upgrade", REVISION_PF19C_LEGACY, database_url)
    assert _alembic_version(db_path) == REVISION_PF19C_LEGACY
    assert "resoluciones_legacy_pf19_journal" in {
        row[0]
        for row in sqlite3.connect(db_path).execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    with sqlite3.connect(db_path) as conn:
        triggers = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                "AND name LIKE 'tr_resoluciones_legacy_pf19_journal_%'"
            )
        }
        assert triggers == {
            "tr_resoluciones_legacy_pf19_journal_update",
            "tr_resoluciones_legacy_pf19_journal_delete",
        }
        conn.execute(
            "INSERT INTO resoluciones_legacy_pf19_journal "
            "(accion, plan_sha256, terminal_response_sha256, actor_usuario_id, "
            "ambiente_consultado, resultado, resultado_consultas_json, "
            "backup_metadata_json, backup_sha256, created_at, intento_id, empresa_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cerrar_legacy_sin_autorizacion_verificada",
                "a" * 64,
                "c" * 64,
                1,
                "ambos",
                "legacy_sin_autorizacion_verificada",
                "{}",
                "{}",
                "b" * 64,
                FECHA_HORA_SINTETICA,
                1,
                1,
            ),
        )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute(
                "UPDATE resoluciones_legacy_pf19_journal SET resultado = ?", ("x",)
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM resoluciones_legacy_pf19_journal")
    output = _run_alembic_failure("downgrade", REVISION_ELEGIBILIDAD_RECE, database_url)
    assert "no eliminar journal administrativo" in output


def test_sqlite_pf19c_downgrade_bloquea_evidencia_arca_estructurada(
    tmp_path: Path,
) -> None:
    """PF-19C nunca descarta una columna que ya contiene evidencia estructurada."""
    db_path = tmp_path / "pf19c-evidencia-estructurada.db"
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    _crear_contexto_fiscal_sintetico(db_path)
    _insertar_intento_sintetico(
        db_path,
        row_id=1,
        estado="fallido_verificado",
    )
    backup_env = _backup_env_pf19(
        db_path,
        tmp_path / "pf19c-evidencia-pf19b-backup.db",
    )
    _run_alembic(
        "upgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
        extra_env=backup_env,
    )
    _run_alembic("upgrade", REVISION_PF19C_LEGACY, database_url)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE intentos_emision_fiscal SET errores_arca_json = ? WHERE id = ?",
            ("[]", 1),
        )
    output = _run_alembic_failure(
        "downgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
    )
    assert "no eliminar evidencia ARCA estructurada" in output
    assert _alembic_version(db_path) == REVISION_PF19C_LEGACY
    assert "errores_arca_json" in _table_columns(db_path, "intentos_emision_fiscal")


def test_sqlite_pf19c_downgrade_no_confunde_json_null_con_evidencia(
    tmp_path: Path,
) -> None:
    """JSON null es ausencia semántica y no bloquea un downgrade sin journal."""
    db_path = tmp_path / "pf19c-json-null.db"
    database_url = f"sqlite:///{db_path.resolve().as_posix()}"
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    _crear_contexto_fiscal_sintetico(db_path)
    _insertar_intento_sintetico(
        db_path,
        row_id=1,
        estado="fallido_verificado",
    )
    backup_env = _backup_env_pf19(
        db_path,
        tmp_path / "pf19c-json-null-pf19b-backup.db",
    )
    _run_alembic(
        "upgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
        extra_env=backup_env,
    )
    _run_alembic("upgrade", REVISION_PF19C_LEGACY, database_url)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE intentos_emision_fiscal SET errores_arca_json = ? WHERE id = ?",
            ("null", 1),
        )
    _run_alembic("downgrade", REVISION_ELEGIBILIDAD_RECE, database_url)
    assert _alembic_version(db_path) == REVISION_ELEGIBILIDAD_RECE
    assert "errores_arca_json" not in _table_columns(
        db_path,
        "intentos_emision_fiscal",
    )
