"""Tests de migraciones Alembic en SQLite."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
REVISION_FORMATOS_IMPORTACION = "a6b7c8d9e0f1"
REVISION_RECEPTOR_SNAPSHOT = "e5f6a7b8c9d0"
COLUMNAS_FORMATOS_LOTE = {
    "mapeo_usado_json",
    "headers_detectados_json",
    "formato_importacion_id",
    "formato_importacion_version_id",
}


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


def _table_columns(db_path: Path, table_name: str) -> set[str]:
    """Devuelve las columnas existentes de una tabla SQLite."""
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _alembic_version(db_path: Path) -> str:
    """Devuelve la revisión Alembic aplicada en la base SQLite."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert row is not None
    return str(row[0])


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
