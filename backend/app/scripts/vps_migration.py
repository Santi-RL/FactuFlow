"""Herramienta privada para preparar migración local a VPS.

El flujo está pensado para mover una instalación SQLite local hacia una base
PostgreSQL limpia, preservando datos operativos necesarios para continuar
facturando sin arrastrar lotes, archivos temporales ni evidencia privada
descargable.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.hazmat.primitives import serialization
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Table
from sqlalchemy.sql.sqltypes import Boolean, Date, DateTime, JSON, Numeric

import app.models  # noqa: F401
from app.arca.crypto import load_private_key
from app.arca.exceptions import ArcaCertificateError
from app.core.database import Base


MIGRATION_PACKAGE_VERSION = 1
SCOPE = "operacion_futura_con_comprobantes"

INCLUDED_TABLES = [
    "empresas",
    "usuarios",
    "clientes",
    "puntos_venta",
    "certificados",
    "formatos_importacion",
    "formatos_importacion_versiones",
    "formatos_importacion_campos",
    "formatos_importacion_reglas",
    "perfiles_carga_masiva",
    "comprobantes",
    "comprobante_items",
]

EXCLUDED_TABLES = [
    "lotes_comprobantes",
    "lotes_comprobantes_grupos",
    "lotes_comprobantes_filas",
    "lotes_comprobantes_eventos",
    "eventos_sistema",
    "exportaciones_almacenamiento",
]

# Alembic crea formatos globales seed; el importador los reemplaza por el paquete.
OPERATIONAL_TARGET_EMPTY_TABLES = [
    "empresas",
    "usuarios",
    "clientes",
    "puntos_venta",
    "certificados",
    "perfiles_carga_masiva",
    "comprobantes",
    "comprobante_items",
]
TARGET_EMPTY_TABLES = OPERATIONAL_TARGET_EMPTY_TABLES + EXCLUDED_TABLES

REQUIRED_ENV_KEYS = [
    "APP_SECRET_KEY",
    "ARCA_PRIVATE_KEY_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "ARCA_ENV",
    "CORS_ORIGINS",
    "VITE_API_URL",
    "FACTUFLOW_CERTS_DIR",
]


class MigrationError(RuntimeError):
    """Error funcional de preparación o restauración de migración."""


@dataclass(frozen=True)
class PreflightResult:
    """Resultado resumido de la validación previa."""

    source_db: Path
    certs_dir: Path
    alembic_version: str
    repo_head: str
    included_counts: dict[str, int]
    excluded_counts: dict[str, int]
    active_certificates: int


def default_backend_dir() -> Path:
    """Devuelve el directorio `backend` del repositorio actual."""
    return Path(__file__).resolve().parents[2]


def default_repo_root() -> Path:
    """Devuelve la raíz del repositorio actual."""
    return default_backend_dir().parent


def default_source_db() -> Path:
    """Devuelve la ruta de la base SQLite local vigente."""
    return default_backend_dir() / "data" / "factuflow.db"


def default_source_certs_dir() -> Path:
    """Devuelve la ruta local donde el backend guarda certificados."""
    return default_backend_dir() / "certs"


def get_repo_alembic_head(backend_dir: Path | None = None) -> str:
    """Obtiene el head único de Alembic declarado por el repo."""
    backend = (backend_dir or default_backend_dir()).resolve()
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        raise MigrationError(f"Se esperaba un único head Alembic y hay {heads}")
    return heads[0]


def run_preflight(
    source_db: Path,
    certs_dir: Path,
    backend_dir: Path | None = None,
) -> PreflightResult:
    """Valida que la fuente local sea apta para preparar el paquete."""
    db_path = source_db.resolve()
    certs_base = certs_dir.resolve()
    if not db_path.is_file() or db_path.stat().st_size == 0:
        raise MigrationError(f"La base SQLite fuente no existe o está vacía: {db_path}")
    if not certs_base.is_dir():
        raise MigrationError(f"No existe el directorio de certificados: {certs_base}")

    repo_head = get_repo_alembic_head(backend_dir)
    with connect_sqlite_readonly(db_path) as conn:
        tables = get_sqlite_tables(conn)
        required = set(INCLUDED_TABLES + EXCLUDED_TABLES + ["alembic_version"])
        missing = sorted(required - tables)
        if missing:
            raise MigrationError(
                "La base fuente no tiene las tablas esperadas: " + ", ".join(missing)
            )

        versions = [
            row["version_num"]
            for row in conn.execute("SELECT version_num FROM alembic_version")
        ]
        if versions != [repo_head]:
            raise MigrationError(
                "La base fuente no está en el head Alembic del repo. "
                f"Fuente={versions}; repo={repo_head}."
            )

        included_counts = count_tables(conn, INCLUDED_TABLES)
        excluded_counts = count_tables(conn, EXCLUDED_TABLES)
        active_certs = list_active_certificates(conn)
        missing_certs = find_missing_certificate_files(active_certs, certs_base)
        if missing_certs:
            ids = ", ".join(str(item["id"]) for item in missing_certs)
            raise MigrationError(
                "Hay certificados activos sin .crt/.key resolubles en CERTS_PATH. "
                f"IDs afectados: {ids}. Corregí esos certificados antes de exportar."
            )

    return PreflightResult(
        source_db=db_path,
        certs_dir=certs_base,
        alembic_version=repo_head,
        repo_head=repo_head,
        included_counts=included_counts,
        excluded_counts=excluded_counts,
        active_certificates=len(active_certs),
    )


def export_package(
    source_db: Path,
    certs_dir: Path,
    output_root: Path,
    target_key_password: str,
    source_key_password: str | None = None,
    backend_dir: Path | None = None,
) -> Path:
    """Genera un paquete privado de migración en `.tmp/vps-migration`."""
    if not target_key_password:
        raise MigrationError("ARCA_PRIVATE_KEY_PASSWORD destino es obligatorio")

    preflight = run_preflight(source_db, certs_dir, backend_dir=backend_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_dir = (output_root / timestamp).resolve()
    if package_dir.exists():
        raise MigrationError(f"Ya existe el paquete destino: {package_dir}")
    data_dir = package_dir / "data"
    package_certs_dir = package_dir / "certs"
    data_dir.mkdir(parents=True, mode=0o700)
    package_certs_dir.mkdir(parents=True, mode=0o700)

    data_files: dict[str, dict[str, Any]] = {}
    cert_files: dict[str, dict[str, Any]] = {}
    with connect_sqlite_readonly(preflight.source_db) as conn:
        active_certs = list_active_certificates(conn)
        active_by_id = {int(row["id"]): row for row in active_certs}
        copied_names = export_active_certificate_files(
            active_certs=active_certs,
            certs_dir=preflight.certs_dir,
            package_certs_dir=package_certs_dir,
            target_key_password=target_key_password,
            source_key_password=source_key_password,
        )

        for table_name in INCLUDED_TABLES:
            rows = read_table_rows(conn, table_name)
            if table_name == "certificados":
                rows = normalize_certificate_rows(rows, active_by_id, copied_names)
            file_path = data_dir / f"{table_name}.jsonl"
            write_jsonl(file_path, rows)
            data_files[table_name] = {
                "path": str(file_path.relative_to(package_dir)).replace("\\", "/"),
                "sha256": sha256_file(file_path),
                "rows": len(rows),
            }

    for path in sorted(package_certs_dir.iterdir()):
        cert_files[path.name] = {
            "path": str(path.relative_to(package_dir)).replace("\\", "/"),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }

    manifest = {
        "package_version": MIGRATION_PACKAGE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": SCOPE,
        "alembic_version": preflight.alembic_version,
        "included_tables": INCLUDED_TABLES,
        "excluded_tables": EXCLUDED_TABLES,
        "included_counts": preflight.included_counts,
        "excluded_counts": preflight.excluded_counts,
        "active_certificates": preflight.active_certificates,
        "data_files": data_files,
        "certificate_files": cert_files,
        "required_env_keys": REQUIRED_ENV_KEYS,
        "notes": [
            "No incluye lotes, filas, temporales, PDFs, Excels, logs ni cache ARCA.",
            "Las claves privadas se re-cifraron con ARCA_PRIVATE_KEY_PASSWORD destino.",
            "La SQLite local debe conservarse como evidencia histórica privada.",
        ],
    }
    write_json(package_dir / "manifest.json", manifest)
    write_env_template(package_dir / "env.production.required.example")
    return package_dir


def import_package(
    package_dir: Path,
    database_url: str,
    production_env: Path,
    target_certs_dir: Path | None = None,
) -> None:
    """Restaura un paquete privado sobre una PostgreSQL limpia."""
    package = package_dir.resolve()
    manifest = load_and_verify_manifest(package)
    env_values = parse_env_file(production_env)
    target_password = env_values.get("ARCA_PRIVATE_KEY_PASSWORD") or os.getenv(
        "ARCA_PRIVATE_KEY_PASSWORD"
    )
    if not target_password:
        raise MigrationError(
            "El importador requiere ARCA_PRIVATE_KEY_PASSWORD en .env.production"
        )
    certs_dir = (
        target_certs_dir or Path(env_values.get("FACTUFLOW_CERTS_DIR", ""))
    ).resolve()
    if not str(certs_dir):
        raise MigrationError(
            "Indicá FACTUFLOW_CERTS_DIR en .env.production o --target-certs-dir"
        )

    verify_package_certificates(package, manifest, target_password)
    engine = create_postgres_engine(database_url)
    with engine.connect() as conn:
        ensure_target_database_ready(conn, manifest)

    restore_certificate_files(package, manifest, certs_dir)

    with engine.begin() as conn:
        ensure_target_database_ready(conn, manifest)
        clear_seeded_included_tables(conn)
        for table_name in INCLUDED_TABLES:
            rows = read_package_rows(package, manifest, table_name)
            insert_rows(conn, table_name, rows)
        reset_postgres_sequences(conn)


def validate_import(
    package_dir: Path,
    database_url: str,
    production_env: Path,
    target_certs_dir: Path | None = None,
    api_url: str | None = None,
    login_email: str | None = None,
) -> None:
    """Valida conteos, certificados y disponibilidad básica post-importación."""
    package = package_dir.resolve()
    manifest = load_and_verify_manifest(package)
    env_values = parse_env_file(production_env)
    target_password = env_values.get("ARCA_PRIVATE_KEY_PASSWORD") or os.getenv(
        "ARCA_PRIVATE_KEY_PASSWORD"
    )
    if not target_password:
        raise MigrationError("Falta ARCA_PRIVATE_KEY_PASSWORD para validar claves")
    certs_dir = (
        target_certs_dir or Path(env_values.get("FACTUFLOW_CERTS_DIR", ""))
    ).resolve()
    if not str(certs_dir):
        raise MigrationError(
            "Indicá FACTUFLOW_CERTS_DIR en .env.production o --target-certs-dir"
        )

    engine = create_postgres_engine(database_url)
    with engine.connect() as conn:
        for table_name in INCLUDED_TABLES:
            expected = int(manifest["data_files"][table_name]["rows"])
            actual = scalar_count(conn, table_name)
            if actual != expected:
                raise MigrationError(
                    f"Conteo inesperado en {table_name}: esperado={expected}, actual={actual}"
                )
        for table_name in EXCLUDED_TABLES:
            actual = scalar_count(conn, table_name)
            if actual != 0:
                raise MigrationError(
                    f"La tabla excluida {table_name} no debería tener filas: {actual}"
                )

    verify_restored_certificate_files(certs_dir, manifest, target_password)
    if api_url:
        validate_api_health(api_url)
        if login_email:
            validate_api_login(api_url, login_email)


def connect_sqlite_readonly(db_path: Path) -> sqlite3.Connection:
    """Abre una conexión SQLite de solo lectura."""
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    """Lista tablas SQLite de usuario."""
    return {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def count_tables(conn: sqlite3.Connection, tables: Iterable[str]) -> dict[str, int]:
    """Cuenta filas de tablas conocidas."""
    counts: dict[str, int] = {}
    for table_name in tables:
        counts[table_name] = int(
            conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        )
    return counts


def list_active_certificates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Devuelve certificados activos de la fuente SQLite."""
    rows = conn.execute(
        """
        SELECT id, archivo_crt, archivo_key
        FROM certificados
        WHERE activo = 1
        ORDER BY id
        """
    )
    return [dict(row) for row in rows]


def find_missing_certificate_files(
    active_certs: Iterable[dict[str, Any]], certs_dir: Path
) -> list[dict[str, Any]]:
    """Detecta certificados activos cuyos archivos no existen."""
    missing: list[dict[str, Any]] = []
    for row in active_certs:
        cert_path = resolve_cert_source_path(str(row["archivo_crt"]), certs_dir)
        key_path = resolve_cert_source_path(str(row["archivo_key"]), certs_dir)
        if not cert_path.is_file() or not key_path.is_file():
            missing.append(
                {
                    "id": row["id"],
                    "crt_exists": cert_path.is_file(),
                    "key_exists": key_path.is_file(),
                }
            )
    return missing


def resolve_cert_source_path(stored_value: str, certs_dir: Path) -> Path:
    """Resuelve un path de certificado dentro de un directorio administrado."""
    base = certs_dir.resolve()
    candidate = Path(stored_value)
    if not candidate.is_absolute():
        parts = list(candidate.parts)
        if parts and parts[0] == base.name:
            candidate = Path(*parts[1:])
        candidate = base / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise MigrationError(
            "Un certificado activo apunta fuera del directorio administrado"
        ) from exc
    return resolved


def export_active_certificate_files(
    active_certs: Iterable[dict[str, Any]],
    certs_dir: Path,
    package_certs_dir: Path,
    target_key_password: str,
    source_key_password: str | None,
) -> dict[int, dict[str, str]]:
    """Copia certificados activos y re-cifra claves privadas."""
    copied: dict[int, dict[str, str]] = {}
    for row in active_certs:
        cert_path = resolve_cert_source_path(str(row["archivo_crt"]), certs_dir)
        key_path = resolve_cert_source_path(str(row["archivo_key"]), certs_dir)
        cert_dest = package_certs_dir / cert_path.name
        key_dest = package_certs_dir / key_path.name
        shutil.copy2(cert_path, cert_dest)
        reencrypt_private_key(
            source_key=key_path,
            target_key=key_dest,
            target_password=target_key_password,
            source_password=source_key_password,
        )
        os.chmod(key_dest, 0o600)
        copied[int(row["id"])] = {
            "archivo_crt": cert_dest.name,
            "archivo_key": key_dest.name,
        }
    return copied


def reencrypt_private_key(
    source_key: Path,
    target_key: Path,
    target_password: str,
    source_password: str | None = None,
) -> None:
    """Re-cifra una clave privada PEM con una contraseña destino."""
    password_bytes = source_password.encode("utf-8") if source_password else None
    private_key = load_private_key(str(source_key), password=password_bytes)
    encrypted = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(
            target_password.encode("utf-8")
        ),
    )
    with open(target_key, "xb") as fh:
        fh.write(encrypted)


def read_table_rows(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    """Lee filas de una tabla incluida en orden estable."""
    rows = conn.execute(f'SELECT * FROM "{table_name}" ORDER BY id')
    return [dict(row) for row in rows]


def normalize_certificate_rows(
    rows: list[dict[str, Any]],
    active_by_id: dict[int, dict[str, Any]],
    copied_names: dict[int, dict[str, str]],
) -> list[dict[str, Any]]:
    """Normaliza paths de certificados activos a nombres dentro de CERTS_PATH."""
    normalized: list[dict[str, Any]] = []
    for row in rows:
        cert_id = int(row["id"])
        copy_info = copied_names.get(cert_id)
        if cert_id in active_by_id and copy_info:
            row = {**row, **copy_info}
        normalized.append(row)
    return normalized


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Escribe filas JSONL con orden de claves estable."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str))
            fh.write("\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Escribe un archivo JSON legible y estable."""
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_env_template(path: Path) -> None:
    """Escribe una plantilla de variables requeridas sin secretos reales."""
    lines = [
        "# Plantilla privada para restaurar el paquete en VPS.",
        "# Reemplazar todos los valores antes de operar producción.",
        "APP_SECRET_KEY=<generar-clave-larga>",
        "ARCA_PRIVATE_KEY_PASSWORD=<misma-clave-usada-al-exportar>",
        "POSTGRES_DB=factuflow",
        "POSTGRES_USER=factuflow",
        "POSTGRES_PASSWORD=<password-fuerte>",
        "ARCA_ENV=produccion",
        "CORS_ORIGINS=https://factuflow.tu-dominio.com",
        "VITE_API_URL=https://factuflow.tu-dominio.com",
        "FACTUFLOW_CERTS_DIR=./certs",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def sha256_file(path: Path) -> str:
    """Calcula SHA-256 de un archivo."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_verify_manifest(package_dir: Path) -> dict[str, Any]:
    """Carga el manifest y verifica checksums del paquete."""
    package_root = package_dir.resolve()
    manifest_path = package_root / "manifest.json"
    if not manifest_path.is_file():
        raise MigrationError(f"No existe manifest.json en {package_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("package_version") != MIGRATION_PACKAGE_VERSION:
        raise MigrationError("Versión de paquete de migración no soportada")
    if manifest.get("scope") != SCOPE:
        raise MigrationError("El paquete no corresponde al alcance esperado")

    for item in manifest["data_files"].values():
        file_path = resolve_package_member(package_root, item["path"])
        if not file_path.is_file():
            raise MigrationError(f"Falta archivo del paquete: {item['path']}")
        if sha256_file(file_path) != item["sha256"]:
            raise MigrationError(f"Checksum inválido en {item['path']}")

    for filename, item in manifest["certificate_files"].items():
        validate_certificate_filename(filename)
        file_path = resolve_package_member(package_root, item["path"])
        if not file_path.is_file():
            raise MigrationError(f"Falta archivo del paquete: {item['path']}")
        if sha256_file(file_path) != item["sha256"]:
            raise MigrationError(f"Checksum inválido en {item['path']}")
    return manifest


def resolve_package_member(package_dir: Path, relative_path: str) -> Path:
    """Resuelve un miembro del paquete sin permitir path traversal."""
    if not relative_path:
        raise MigrationError("El paquete contiene un path vacío")
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise MigrationError(f"El paquete contiene un path absoluto: {relative_path}")
    package_root = package_dir.resolve()
    resolved = (package_root / candidate).resolve()
    try:
        resolved.relative_to(package_root)
    except ValueError as exc:
        raise MigrationError(
            f"El paquete contiene un path fuera de su directorio: {relative_path}"
        ) from exc
    return resolved


def validate_certificate_filename(filename: str) -> str:
    """Valida nombres de certificados para restaurar solo basenames."""
    if not filename:
        raise MigrationError("El paquete contiene un nombre de certificado vacío")
    candidate = Path(filename)
    if candidate.is_absolute() or candidate.name != filename:
        raise MigrationError(f"Nombre de certificado inválido en paquete: {filename}")
    return filename


def parse_env_file(path: Path) -> dict[str, str]:
    """Parsea un `.env.production` sin imprimir secretos."""
    env_path = path.resolve()
    if not env_path.is_file():
        raise MigrationError(f"No existe el archivo de entorno: {env_path}")
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    missing = [key for key in REQUIRED_ENV_KEYS if not values.get(key)]
    if missing:
        raise MigrationError(
            "Faltan variables requeridas en .env.production: " + ", ".join(missing)
        )
    return values


def verify_package_certificates(
    package_dir: Path, manifest: dict[str, Any], target_password: str
) -> None:
    """Verifica que las claves del paquete abran con la clave destino."""
    for filename, info in manifest["certificate_files"].items():
        if not filename.endswith(".key"):
            continue
        key_path = resolve_package_member(package_dir, info["path"])
        try:
            load_private_key(str(key_path), password=target_password.encode("utf-8"))
        except ArcaCertificateError as exc:
            raise MigrationError(
                f"La clave exportada {filename} no abre con ARCA_PRIVATE_KEY_PASSWORD"
            ) from exc


def create_postgres_engine(database_url: str) -> Engine:
    """Crea un engine SQLAlchemy síncrono para PostgreSQL."""
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://", 1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg2://", 1
        )
    if not database_url.startswith("postgresql+psycopg2://"):
        raise MigrationError("El destino de importación debe ser PostgreSQL")
    return create_engine(database_url, future=True)


def ensure_target_database_ready(conn, manifest: dict[str, Any]) -> None:
    """Valida que PostgreSQL esté migrada y sin datos operativos."""
    version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    if version != manifest["alembic_version"]:
        raise MigrationError(
            "La base destino no está en el mismo head Alembic. "
            f"Destino={version}; paquete={manifest['alembic_version']}."
        )
    non_empty = {
        table_name: scalar_count(conn, table_name) for table_name in TARGET_EMPTY_TABLES
    }
    dirty = {table: count for table, count in non_empty.items() if count}
    if dirty:
        raise MigrationError(
            "La base destino no está limpia. Tablas con datos: "
            + ", ".join(f"{table}={count}" for table, count in dirty.items())
        )


def clear_seeded_included_tables(conn) -> None:
    """Limpia tablas incluidas para reemplazar seeds por datos del paquete."""
    for table_name in reversed(INCLUDED_TABLES):
        conn.execute(Base.metadata.tables[table_name].delete())


def read_package_rows(
    package_dir: Path, manifest: dict[str, Any], table_name: str
) -> list[dict[str, Any]]:
    """Lee filas JSONL de una tabla del paquete."""
    file_path = resolve_package_member(
        package_dir, manifest["data_files"][table_name]["path"]
    )
    rows: list[dict[str, Any]] = []
    table = Base.metadata.tables[table_name]
    with open(file_path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rows.append(convert_row_for_table(table, json.loads(line)))
    return rows


def convert_row_for_table(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    """Convierte valores JSONL al tipo esperado por SQLAlchemy/PostgreSQL."""
    converted: dict[str, Any] = {}
    for column in table.columns:
        if column.name not in row:
            continue
        value = row[column.name]
        converted[column.name] = convert_value(column.type, value)
    return converted


def convert_value(column_type: Any, value: Any) -> Any:
    """Convierte un valor serializado al tipo de columna esperado."""
    if value is None:
        return None
    if isinstance(column_type, Boolean):
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "si", "sí"}
        return bool(value)
    if isinstance(column_type, DateTime):
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(column_type, Date):
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
    if isinstance(column_type, Numeric):
        return Decimal(str(value))
    if isinstance(column_type, JSON) and isinstance(value, str):
        return json.loads(value)
    return value


def insert_rows(conn, table_name: str, rows: list[dict[str, Any]]) -> None:
    """Inserta filas preservando IDs."""
    if not rows:
        return
    table = Base.metadata.tables[table_name]
    for start in range(0, len(rows), 500):
        conn.execute(table.insert(), rows[start : start + 500])


def reset_postgres_sequences(conn) -> None:
    """Ajusta secuencias PostgreSQL al máximo ID restaurado."""
    for table_name in INCLUDED_TABLES:
        table = Base.metadata.tables[table_name]
        if "id" not in table.columns:
            continue
        seq = conn.execute(
            text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
            {"table_name": table_name},
        ).scalar()
        if not seq:
            continue
        max_id = conn.execute(select(func.max(table.c.id))).scalar()
        if max_id is None:
            conn.execute(
                text("SELECT setval(CAST(:seq AS regclass), 1, false)"),
                {"seq": seq},
            )
        else:
            conn.execute(
                text("SELECT setval(CAST(:seq AS regclass), :value, true)"),
                {"seq": seq, "value": int(max_id)},
            )


def restore_certificate_files(
    package_dir: Path, manifest: dict[str, Any], target_certs_dir: Path
) -> None:
    """Copia certificados restaurados al directorio destino."""
    target = target_certs_dir.resolve()
    target.mkdir(parents=True, exist_ok=True)
    for filename, info in manifest["certificate_files"].items():
        safe_filename = validate_certificate_filename(filename)
        source = resolve_package_member(package_dir, info["path"])
        dest = (target / safe_filename).resolve()
        try:
            dest.relative_to(target)
        except ValueError as exc:
            raise MigrationError(
                f"Destino de certificado fuera de CERTS_PATH: {safe_filename}"
            ) from exc
        if dest.exists() and sha256_file(dest) != info["sha256"]:
            raise MigrationError(
                f"Ya existe un certificado destino distinto: {dest.name}"
            )
        if not dest.exists():
            shutil.copy2(source, dest)
        if filename.endswith(".key"):
            os.chmod(dest, 0o600)


def verify_restored_certificate_files(
    certs_dir: Path, manifest: dict[str, Any], target_password: str
) -> None:
    """Verifica certificados restaurados y claves re-cifradas."""
    for filename, info in manifest["certificate_files"].items():
        safe_filename = validate_certificate_filename(filename)
        path = (certs_dir / safe_filename).resolve()
        try:
            path.relative_to(certs_dir.resolve())
        except ValueError as exc:
            raise MigrationError(
                f"Certificado restaurado fuera de CERTS_PATH: {safe_filename}"
            ) from exc
        if not path.is_file():
            raise MigrationError(f"Falta certificado restaurado: {filename}")
        if sha256_file(path) != info["sha256"]:
            raise MigrationError(f"Checksum inválido en certificado: {filename}")
        if filename.endswith(".key"):
            load_private_key(str(path), password=target_password.encode("utf-8"))


def scalar_count(conn, table_name: str) -> int:
    """Cuenta filas en una tabla PostgreSQL conocida."""
    table = Base.metadata.tables[table_name]
    return int(conn.execute(select(func.count()).select_from(table)).scalar_one())


def validate_api_health(api_url: str) -> None:
    """Valida disponibilidad básica del backend por HTTP."""
    url = api_url.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status >= 400:
                raise MigrationError(f"Healthcheck devolvió HTTP {response.status}")
    except urllib.error.URLError as exc:
        raise MigrationError(f"No se pudo consultar healthcheck: {url}") from exc


def validate_api_login(api_url: str, login_email: str) -> None:
    """Valida login real contra la API sin imprimir contraseña ni token."""
    password = getpass.getpass(f"Contraseña para {login_email}: ")
    payload = json.dumps({"email": login_email, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        api_url.rstrip("/") + "/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise MigrationError(f"Login devolvió HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        raise MigrationError(f"Login falló con HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise MigrationError("No se pudo ejecutar login de validación") from exc


def get_password_from_env_or_prompt(
    env_name: str,
    prompt: str,
    confirm: bool = False,
    non_interactive: bool = False,
) -> str:
    """Obtiene una contraseña desde variable de entorno o prompt seguro."""
    value = os.getenv(env_name)
    if value:
        return value
    if non_interactive:
        raise MigrationError(f"Falta la variable de entorno {env_name}")
    first = getpass.getpass(prompt)
    if confirm:
        second = getpass.getpass("Repetí la contraseña: ")
        if first != second:
            raise MigrationError("Las contraseñas no coinciden")
    return first


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser CLI."""
    parser = argparse.ArgumentParser(
        description="Prepara y restaura paquetes privados de migración a VPS."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    add_source_args(preflight)

    export = subparsers.add_parser("export")
    add_source_args(export)
    export.add_argument(
        "--output-root",
        type=Path,
        default=default_repo_root() / ".tmp" / "vps-migration",
    )
    export.add_argument(
        "--target-key-password-env",
        default="ARCA_MIGRATION_TARGET_KEY_PASSWORD",
    )
    export.add_argument(
        "--source-key-password-env",
        default="ARCA_MIGRATION_SOURCE_KEY_PASSWORD",
    )
    export.add_argument("--non-interactive", action="store_true")

    import_cmd = subparsers.add_parser("import")
    add_target_args(import_cmd)
    import_cmd.add_argument("package_dir", type=Path)

    validate = subparsers.add_parser("validate")
    add_target_args(validate)
    validate.add_argument("package_dir", type=Path)
    validate.add_argument("--api-url")
    validate.add_argument("--login-email")
    return parser


def add_source_args(parser: argparse.ArgumentParser) -> None:
    """Agrega argumentos comunes de fuente local."""
    parser.add_argument("--source-db", type=Path, default=default_source_db())
    parser.add_argument("--certs-dir", type=Path, default=default_source_certs_dir())
    parser.add_argument("--backend-dir", type=Path, default=default_backend_dir())


def add_target_args(parser: argparse.ArgumentParser) -> None:
    """Agrega argumentos comunes de destino PostgreSQL."""
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="URL PostgreSQL destino. Si se omite, usa DATABASE_URL.",
    )
    parser.add_argument("--production-env", type=Path, default=Path(".env.production"))
    parser.add_argument("--target-certs-dir", type=Path)


def main(argv: list[str] | None = None) -> int:
    """Ejecuta la interfaz de línea de comandos."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = run_preflight(args.source_db, args.certs_dir, args.backend_dir)
            print(
                "Preflight OK: "
                f"alembic={result.alembic_version}, "
                f"certificados_activos={result.active_certificates}"
            )
            return 0

        if args.command == "export":
            target_password = get_password_from_env_or_prompt(
                args.target_key_password_env,
                "ARCA_PRIVATE_KEY_PASSWORD destino: ",
                confirm=True,
                non_interactive=args.non_interactive,
            )
            source_password = os.getenv(args.source_key_password_env)
            package = export_package(
                source_db=args.source_db,
                certs_dir=args.certs_dir,
                output_root=args.output_root,
                target_key_password=target_password,
                source_key_password=source_password,
                backend_dir=args.backend_dir,
            )
            print(f"Paquete creado en: {package}")
            return 0

        if not args.database_url:
            raise MigrationError("Indicá --database-url o DATABASE_URL")

        if args.command == "import":
            import_package(
                package_dir=args.package_dir,
                database_url=args.database_url,
                production_env=args.production_env,
                target_certs_dir=args.target_certs_dir,
            )
            print("Importación OK")
            return 0

        if args.command == "validate":
            validate_import(
                package_dir=args.package_dir,
                database_url=args.database_url,
                production_env=args.production_env,
                target_certs_dir=args.target_certs_dir,
                api_url=args.api_url,
                login_email=args.login_email,
            )
            print("Validación OK")
            return 0
    except MigrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
