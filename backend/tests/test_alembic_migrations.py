"""Tests de migraciones Alembic en SQLite."""

from __future__ import annotations

import os
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
COLUMNAS_FORMATOS_LOTE = {
    "mapeo_usado_json",
    "headers_detectados_json",
    "formato_importacion_id",
    "formato_importacion_version_id",
}
CAE_SINTETICO = "12345678901234"
FECHA_SINTETICA = "2026-07-13"
FECHA_HORA_SINTETICA = "2026-07-13 12:00:00"


def _run_alembic(action: str, revision: str, database_url: str) -> None:
    """Ejecuta Alembic contra una base temporal de test."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["APP_ENV"] = "testing"

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
) -> str:
    """Ejecuta Alembic y devuelve la salida de un fallo esperado."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["APP_ENV"] = "testing"

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
