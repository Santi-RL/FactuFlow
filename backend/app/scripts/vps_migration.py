"""Herramienta privada para preparar migración local a VPS.

El flujo está pensado para mover una instalación SQLite local hacia una base
PostgreSQL limpia, preservando datos operativos necesarios para continuar
facturando sin arrastrar lotes, archivos temporales ni evidencia privada
descargable.
"""

from __future__ import annotations

import argparse
from contextvars import ContextVar
from functools import wraps
import inspect
import ast
import getpass
import hashlib
import json
import os
import stat
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, DecimalException
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Table
from sqlalchemy.sql.sqltypes import (
    Boolean,
    Date,
    DateTime,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)

import app.models  # noqa: F401
from app.arca.crypto import (
    load_certificate,
    load_private_key,
    verify_certificate_validity,
)
from app.arca.exceptions import ArcaCertificateError
from app.core.database import Base
from app.core.fiscal_storage import (
    ExactAmount,
    ExactDecimal,
    ExactInteger,
    _install_sqlite_functions,
    decimal_search_key,
    encode_decimal,
)
from app.core.fiscal_storage_legacy import A01_HEAD, LEGACY_COLUMNS
from app.schemas.comprobante import EmitirComprobanteResponse
from app.schemas.lote_comprobante import (
    LoteAccionResponse,
    LoteComprobanteResponse,
    LoteProcesamientoResponse,
)
from app.services.resolucion_legacy_pf19_service import BackupLegacyPF19
from app.scripts import vps_migration_v3, vps_migration_v4, vps_migration_v5

_package_format = ContextVar(
    "fiscal_migration_package_format", default=vps_migration_v4
)


def _fiscal_package_format():
    return _package_format.get()


def _format_context(function):
    """Selecciona el descriptor de origen por evidencia explícita y lo restaura.

    La selección no valida el paquete: los loaders estrictos y sus hashes siguen
    siendo obligatorios antes de cualquier escritura. Cada llamada conserva su
    propio contexto; v3/v4 no heredan el formato de una importación anterior.
    """
    signature = inspect.signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        arguments = signature.bind(*args, **kwargs).arguments
        version = None
        manifest = arguments.get("manifest")
        if isinstance(manifest, dict):
            version = manifest.get("package_version")
        package_dir = arguments.get("package_dir")
        if version is None and package_dir is not None:
            try:
                version = json.loads(
                    (Path(package_dir) / "manifest.json").read_text(encoding="utf-8")
                ).get("package_version")
            except (OSError, ValueError, AttributeError):
                pass  # El loader estricto emitirá el diagnóstico funcional.
        source_db = arguments.get("source_db")
        if source_db is not None and Path(source_db).is_file():
            try:
                with connect_sqlite_readonly(Path(source_db)) as source_connection:
                    heads = [
                        row[0]
                        for row in source_connection.execute(
                            "SELECT version_num FROM alembic_version"
                        )
                    ]
            except sqlite3.Error:
                heads = []  # El preflight conserva la autoridad del diagnóstico.
            if heads == [A01_HEAD]:
                version = 5
            elif heads == [vps_migration_v4.ALEMBIC_HEAD]:
                version = 4
        elif arguments.get("repo_head") == A01_HEAD:
            version = 5
        selected = (
            vps_migration_v5
            if version == 5
            else vps_migration_v4 if version in {3, 4} else _package_format.get()
        )
        token = _package_format.set(selected)
        try:
            return function(*args, **kwargs)
        finally:
            _package_format.reset(token)

    return wrapped


def _historical_v4_table(table_name: str) -> Table:
    """Descriptor de origen v4 congelado para las columnas ampliadas en A-01."""
    from sqlalchemy import Column, MetaData

    current = Base.metadata.tables[table_name]
    columns = []
    for name in _fiscal_package_format().V4_COLUMNS[table_name]:
        original = current.c[name]
        old_type = (
            vps_migration_v5.DECIMAL_TYPES.get((table_name, name), original.type)
            if _fiscal_package_format().PACKAGE_VERSION == 5
            else LEGACY_COLUMNS.get(table_name, {}).get(name, original.type)
        )
        columns.append(
            Column(
                name,
                old_type,
                nullable=original.nullable,
                primary_key=original.primary_key,
            )
        )
    return Table(table_name, MetaData(), *columns)


def _a01_destination_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    if table_name != "lotes_comprobantes_grupos":
        return row
    quotation = row.get("cotizacion_duplicados")
    return {
        **row,
        "cotizacion_busqueda": (
            decimal_search_key(Decimal(quotation)) if quotation is not None else None
        ),
    }


SCOPE = "operacion_futura_con_comprobantes"

INCLUDED_TABLES = [
    "empresas",
    "usuarios",
    "usuario_emisor_acceso",
    "clientes",
    "puntos_venta",
    "puntos_venta_elegibilidad_rece_revisiones",
    "puntos_venta_elegibilidad_rece_actual",
    "operaciones_idempotentes",
    "operaciones_idempotentes_elegibilidad_rece",
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
    "intentos_emision_fiscal",
    "resoluciones_legacy_pf19_journal",
    "puntos_venta_guardas_emision_rece",
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
    "usuario_emisor_acceso",
    "clientes",
    "puntos_venta",
    "puntos_venta_elegibilidad_rece_revisiones",
    "puntos_venta_elegibilidad_rece_actual",
    "operaciones_idempotentes",
    "operaciones_idempotentes_elegibilidad_rece",
    "certificados",
    "perfiles_carga_masiva",
    "comprobantes",
    "comprobante_items",
]
SEEDED_INCLUDED_TABLES = [
    "formatos_importacion",
    "formatos_importacion_versiones",
    "formatos_importacion_campos",
    "formatos_importacion_reglas",
]
TARGET_EMPTY_TABLES = OPERATIONAL_TARGET_EMPTY_TABLES + EXCLUDED_TABLES
V3_ADAPTER_TARGET_EMPTY_TABLES = [
    "lotes_duplicados_coordinacion",
    "lotes_duplicados_evidencias",
    "lotes_duplicados_coincidencias",
    "lotes_duplicados_coincidencias_miembros",
]

REQUIRED_ENV_KEYS = [
    "APP_SECRET_KEY",
    "ARCA_PRIVATE_KEY_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "ARCA_ENV",
    "CORS_ORIGINS",
    "VITE_API_URL",
    "CERTS_PATH",
]

ENV_TEMPLATE_FILENAME = "env.production.required.example"
OPERATION_LOTE_NORMALIZATION_KEY = "operaciones_idempotentes.lote_id"
OPERATION_LOTE_NORMALIZATION_RULE = (
    "set_null_preserve_source_pairs_and_group_inventory_sha256_v2"
)
IDEMPOTENCY_BARRIER_ALGORITHM = "sha256-json-c14n-v1"
PACKAGE_NOTES = [
    "No incluye lotes, filas, temporales, PDFs, Excels, logs ni cache ARCA.",
    "Las claves privadas se re-cifraron con ARCA_PRIVATE_KEY_PASSWORD destino.",
    "La SQLite local debe conservarse como evidencia histórica privada.",
]
MANIFEST_TOP_LEVEL_KEYS = {
    "package_version",
    "created_at",
    "scope",
    "alembic_version",
    "included_tables",
    "excluded_tables",
    "target_empty_tables",
    "included_counts",
    "excluded_counts",
    "active_certificates",
    "safe_omitted",
    "normalizations",
    "source_barrier",
    "idempotency_barrier",
    "data_files",
    "certificate_files",
    "env_template",
    "required_env_keys",
    "notes",
}
DATA_FILE_INFO_KEYS = {"path", "sha256", "rows", "bytes"}
CERTIFICATE_FILE_INFO_KEYS = {"path", "sha256", "bytes"}
ENV_TEMPLATE_INFO_KEYS = {"path", "sha256", "bytes"}
NORMALIZATION_INFO_KEYS = {"rule", "rows", "sha256", "pairs"}
SOURCE_BARRIER_KEYS = {"source_quiesced", "sqlite_transaction", "data_version"}
IDEMPOTENCY_BARRIER_KEYS = {"version", "algorithm", "rows", "sha256"}

AMBIENTES_RECE = set(vps_migration_v3.AMBIENTES_RECE)
ESTADOS_OPERACION_TERMINALES = set(vps_migration_v3.ESTADOS_OPERACION_TERMINALES)
ESTADOS_OPERACION_CONOCIDOS = ESTADOS_OPERACION_TERMINALES | {
    "en_proceso",
    "interrumpida_pre_arca",
    "requiere_confirmacion_duplicado",
    "requiere_reconciliacion",
}
ESTADOS_INTENTO_TERMINALES = {
    "autorizado",
    "fallido_verificado",
    "rechazado_arca",
}
ESTADOS_INTENTO_CONOCIDOS = ESTADOS_INTENTO_TERMINALES | {
    "en_proceso",
    "requiere_reconciliacion",
}
FASES_GUARDA_TERMINALES = {"cerrada_pre_arca", "cerrada_terminal"}
FASES_GUARDA_CONOCIDAS = FASES_GUARDA_TERMINALES | {
    "pre_arca",
    "arca_iniciada",
    "requiere_reconciliacion",
}
ESTADOS_LOTE_SEGUROS_OMITIBLES = set(vps_migration_v3.ESTADOS_LOTE_SEGUROS_OMITIBLES)
ESTADOS_GRUPO_SEGUROS_OMITIBLES = {
    "cargado",
    "validado",
    "con_error",
    "autorizado",
    "autorizado_externo",
    "fallido",
    "descartado",
}
ESTADOS_FILA_SEGUROS_OMITIBLES = set(ESTADOS_GRUPO_SEGUROS_OMITIBLES)
SAFE_OMITTED_COUNT_KEYS = {
    "intentos_emision_fiscal": "intentos_terminales_omitidos",
    "resoluciones_legacy_pf19_journal": "resoluciones_legacy_pf19_omitidas",
    "puntos_venta_guardas_emision_rece": "guardas_terminales_omitidas",
    "lotes_comprobantes": "lotes_seguros_omitidos",
    "lotes_comprobantes_grupos": "grupos_seguros_omitidos",
    "lotes_comprobantes_filas": "filas_omitidas",
    "lotes_comprobantes_eventos": "eventos_lote_omitidos",
    "eventos_sistema": "eventos_sistema_omitidos",
    "exportaciones_almacenamiento": "exportaciones_omitidas",
}
ARCA_RECHAZO_GLOBAL_CATEGORIA = vps_migration_v3.ARCA_RECHAZO_GLOBAL_CATEGORIA
ARCA_RECHAZO_GLOBAL_MENSAJE = vps_migration_v3.ARCA_RECHAZO_GLOBAL_MENSAJE
ARCA_RECHAZO_GLOBAL_INDIVIDUAL_MENSAJE = (
    vps_migration_v3.ARCA_RECHAZO_GLOBAL_INDIVIDUAL_MENSAJE
)
ARCA_RECHAZO_GLOBAL_INDIVIDUAL_ERRORES = list(
    vps_migration_v3.ARCA_RECHAZO_GLOBAL_INDIVIDUAL_ERRORES
)
ARCA_RECHAZO_GLOBAL_LOTE_MENSAJE = vps_migration_v3.ARCA_RECHAZO_GLOBAL_LOTE_MENSAJE
ARCA_RECHAZO_GLOBAL_ERRORES = [
    dict(item) for item in vps_migration_v3.ARCA_RECHAZO_GLOBAL_ERRORES
]
LEGACY_PF19_CATEGORIA = vps_migration_v3.LEGACY_PF19_CATEGORIA
LEGACY_PF19_MENSAJE = vps_migration_v3.LEGACY_PF19_MENSAJE
SAFE_OMITTED_KEYS = {
    "blockers",
    "excluded_counts",
    "operaciones_terminales_preservadas",
    "operaciones_lote_normalizado",
    "asociaciones_rece_preservadas",
    *SAFE_OMITTED_COUNT_KEYS.values(),
}


class MigrationError(RuntimeError):
    """Error funcional de preparación o restauración de migración."""


def select_import_contract(manifest: dict[str, Any]):
    """Selecciona el contrato congelado, nunca el esquema del ORM vigente."""
    version = manifest.get("package_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise MigrationError("Versión de paquete de migración no soportada")
    contracts = {
        3: vps_migration_v3.V3_CONTRACT,
        4: vps_migration_v4.V4_CONTRACT,
        5: vps_migration_v5.V4_CONTRACT,
    }
    if version not in contracts:
        raise MigrationError("Versión de paquete de migración no soportada")
    return contracts[version]


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
    safe_omitted: dict[str, Any]


@dataclass(frozen=True)
class CertificateRestoreItem:
    """Archivo de certificado ya validado y su destino determinista."""

    filename: str
    source: Path
    destination: Path
    sha256: str
    existed: bool


@dataclass(frozen=True)
class CertificateRestorePlan:
    """Plan de copia sin efectos laterales para material criptográfico."""

    target_dir: Path
    items: tuple[CertificateRestoreItem, ...]


@dataclass
class CertificateRestoreJournal:
    """Registra exclusivamente archivos creados por este intento."""

    created: list[CertificateRestoreItem]
    identities: dict[Path, tuple[int, int]] = field(default_factory=dict)
    temporary: dict[Path, tuple[int, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class V4Capture:
    """Selección cerrada y canónica producida desde una única snapshot SQLite."""

    rows: dict[str, list[dict[str, Any]]]
    source_counts: dict[str, int]
    included_counts: dict[str, int]
    omitted_counts: dict[str, int]
    safe_omitted: dict[str, Any]
    normalization: dict[str, Any]
    closure: dict[str, Any]


@dataclass(frozen=True)
class StagingDirectoryOwnership:
    """Identidad inmutable del staging privado creado por esta exportación."""

    parent: Path
    device: int
    inode: int


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


def _json_dict_or_none(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        decoded = json.loads(
            value,
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
        if isinstance(decoded, dict):
            return decoded
    raise MigrationError("La evidencia PF-13 contiene JSON no canónico")


def _is_v4_operation(row: dict[str, Any]) -> bool:
    control = row.get("control_duplicados_json")
    return row.get("duplicados_version") == "duplicados_lotes/v2" or (
        control is not None and control != "null"
    )


def _is_comparable_v4_group(row: dict[str, Any]) -> bool:
    return bool(
        row.get("estado") in {"autorizado", "autorizado_externo"}
        and row.get("duplicados_version") == "duplicados_lotes/v2"
        and row.get("duplicados_cobertura")
        in {"completa", "parcial_legacy", "no_comprobable"}
        and isinstance(row.get("huella_fiscal_completa"), str)
        and len(row["huella_fiscal_completa"]) == 64
        and row.get("fecha_emision_normalizada") is not None
        and row.get("moneda_duplicados") is not None
        and row.get("cotizacion_duplicados") is not None
        and row.get("total_centavos") is not None
    )


def _is_exact_terminal_pf19c_batch_operation(row: dict[str, Any]) -> bool:
    """Identifica un rechazo PF-19C batch cuya historia debe viajar completa."""
    if (
        row.get("tipo_operacion") not in {"procesar_lote", "reintentar_fallidos_lote"}
        or row.get("estado") != "rechazado_arca"
        or row.get("lote_id") is None
    ):
        return False
    try:
        response = _json_dict_or_none(row.get("response_json"))
        return bool(
            response is not None
            and _batch_global_rejection_context(
                response,
                operation_type=str(row["tipo_operacion"]),
                operation_id=int(row["id"]),
            )
            is not None
        )
    except (KeyError, TypeError, ValueError):
        return False


def _v4_closure_payload(
    *,
    rows: dict[str, list[dict[str, Any]]],
    normalization: dict[str, Any],
) -> dict[str, Any]:
    operations = rows["operaciones_idempotentes"]
    v4_operations = [row for row in operations if _is_v4_operation(row)]
    lotes = rows["lotes_comprobantes"]
    groups = rows["lotes_comprobantes_grupos"]
    attempts = rows["intentos_emision_fiscal"]
    guards = rows["puntos_venta_guardas_emision_rece"]
    generations = rows["lotes_duplicados_evidencias"]
    blocks = rows["lotes_duplicados_coincidencias"]
    members = rows["lotes_duplicados_coincidencias_miembros"]
    payload = {
        "version": 1,
        "algorithm": _fiscal_package_format().CLOSURE_ALGORITHM,
        "operation_ids": sorted(int(row["id"]) for row in operations),
        "root_operation_ids": sorted(
            {int(row.get("operacion_raiz_id") or row["id"]) for row in v4_operations}
        ),
        "preserved_lote_ids": sorted(int(row["id"]) for row in lotes),
        "preserved_group_ids": sorted(int(row["id"]) for row in groups),
        "legacy_normalized_operation_ids": sorted(
            int(pair["operacion_id"]) for pair in normalization["pairs"]
        ),
        "attempt_ids": sorted(int(row["id"]) for row in attempts),
        "guard_ids": sorted(int(row["id"]) for row in guards),
        "generation_ids": sorted(int(row["id"]) for row in generations),
        "block_ids": sorted(int(row["id"]) for row in blocks),
        "member_ids": sorted(int(row["id"]) for row in members),
        "group_counts_by_lote": {
            str(int(lote["id"])): sum(
                int(group["lote_id"]) == int(lote["id"]) for group in groups
            )
            for lote in lotes
        },
    }
    return {**payload, "sha256": _fiscal_package_format().canonical_sha256(payload)}


def normalize_v4_operation_rows(
    rows: list[dict[str, Any]],
    *,
    preserved_lote_ids: set[int],
    group_ids_by_lote: dict[int, list[int]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Conserva lotes PF-13 y normaliza sólo operaciones legacy omitidas."""
    pairs = [
        _operation_lote_normalization_pair(
            row,
            group_ids_by_lote=group_ids_by_lote,
        )
        for row in rows
        if row.get("lote_id") is not None
        and int(row["lote_id"]) not in preserved_lote_ids
    ]
    pairs.sort(key=lambda item: (item["operacion_id"], item["lote_id"]))
    normalized = [
        (
            {**row, "lote_id": None}
            if row.get("lote_id") is not None
            and int(row["lote_id"]) not in preserved_lote_ids
            else dict(row)
        )
        for row in rows
    ]
    return normalized, {
        "rule": _fiscal_package_format().OPERATION_LOTE_NORMALIZATION_RULE,
        "rows": len(pairs),
        "sha256": _fiscal_package_format().canonical_sha256(pairs),
        "pairs": pairs,
    }


def capture_v4_rows(conn: sqlite3.Connection) -> V4Capture:
    """Calcula la clausura PF-13 sobre la snapshot inmóvil de la fuente."""
    legacy_safety = classify_safe_omissions(conn)
    complete_rows = {
        table_name: read_table_rows(conn, table_name)
        for table_name in _fiscal_package_format().COMPLETE_TABLES
    }
    all_filtered = {
        table_name: read_table_rows(conn, table_name)
        for table_name in _fiscal_package_format().FILTERED_TABLES
    }
    operations = complete_rows["operaciones_idempotentes"]
    all_lotes = all_filtered["lotes_comprobantes"]
    all_groups = all_filtered["lotes_comprobantes_grupos"]
    all_attempts = all_filtered["intentos_emision_fiscal"]
    all_generations = all_filtered["lotes_duplicados_evidencias"]
    all_blocks = all_filtered["lotes_duplicados_coincidencias"]
    all_members = all_filtered["lotes_duplicados_coincidencias_miembros"]

    v4_operation_ids = {int(row["id"]) for row in operations if _is_v4_operation(row)}
    terminal_individual_operation_ids = {
        int(row["id"])
        for row in operations
        if row.get("tipo_operacion") == "emitir_comprobante"
        and row.get("estado") in ESTADOS_OPERACION_TERMINALES
    }
    generation_ids = {int(row["id"]) for row in all_generations}
    block_ids = {
        int(row["id"])
        for row in all_blocks
        if int(row["generacion_id"]) in generation_ids
    }
    selected_members = [
        row for row in all_members if int(row["bloque_id"]) in block_ids
    ]
    group_lote = {int(row["id"]): int(row["lote_id"]) for row in all_groups}
    preserved_lote_ids = {
        int(row["lote_id"])
        for row in operations
        if _is_v4_operation(row) and row.get("lote_id") is not None
    }
    preserved_lote_ids.update(
        int(row["lote_id"]) for row in all_groups if _is_comparable_v4_group(row)
    )
    preserved_lote_ids.update(int(row["lote_id"]) for row in all_generations)
    preserved_lote_ids.update(
        int(row["lote_id"])
        for row in operations
        if _is_exact_terminal_pf19c_batch_operation(row)
    )
    preserved_lote_ids.update(
        int(row["lote_id"])
        for row in all_attempts
        if row.get("lote_id") is not None
        and (
            int(row.get("operacion_id") or 0) in v4_operation_ids
            or row.get("duplicados_generacion_id") is not None
        )
    )
    preserved_lote_ids.update(
        group_lote[int(row["grupo_id"])]
        for row in selected_members
        if row.get("grupo_id") is not None and int(row["grupo_id"]) in group_lote
    )

    selected_lotes = [row for row in all_lotes if int(row["id"]) in preserved_lote_ids]
    selected_groups = [
        row for row in all_groups if int(row["lote_id"]) in preserved_lote_ids
    ]
    selected_group_ids = {int(row["id"]) for row in selected_groups}
    selected_attempts = [
        row
        for row in all_attempts
        if int(row.get("operacion_id") or 0) in v4_operation_ids
        or int(row.get("operacion_id") or 0) in terminal_individual_operation_ids
        or int(row.get("grupo_id") or 0) in selected_group_ids
        or int(row.get("lote_id") or 0) in preserved_lote_ids
        or int(row.get("duplicados_generacion_id") or 0) in generation_ids
    ]
    selected_guard_ids = {
        int(row["guarda_rece_id"])
        for row in selected_attempts
        if row.get("guarda_rece_id") is not None
    }
    selected_guards = [
        row
        for row in all_filtered["puntos_venta_guardas_emision_rece"]
        if int(row["id"]) in selected_guard_ids
    ]

    group_ids_by_lote: dict[int, list[int]] = {}
    for row in all_groups:
        group_ids_by_lote.setdefault(int(row["lote_id"]), []).append(int(row["id"]))
    normalized_operations, normalization = normalize_v4_operation_rows(
        operations,
        preserved_lote_ids=preserved_lote_ids,
        group_ids_by_lote=group_ids_by_lote,
    )
    selected_rows = {
        **complete_rows,
        "operaciones_idempotentes": normalized_operations,
        "lotes_comprobantes": selected_lotes,
        "lotes_comprobantes_grupos": selected_groups,
        "puntos_venta_guardas_emision_rece": selected_guards,
        "lotes_duplicados_evidencias": all_generations,
        "lotes_duplicados_coincidencias": [
            row for row in all_blocks if int(row["id"]) in block_ids
        ],
        "lotes_duplicados_coincidencias_miembros": selected_members,
        "intentos_emision_fiscal": selected_attempts,
    }
    source_counts = {
        table_name: int(
            conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        )
        for table_name in (
            _fiscal_package_format().INCLUDED_TABLES
            + _fiscal_package_format().REGENERATED_TABLES
            + _fiscal_package_format().EXCLUDED_TABLES
        )
    }
    included_counts = {
        table_name: len(selected_rows[table_name])
        for table_name in _fiscal_package_format().INCLUDED_TABLES
    }
    omitted_counts = {
        table_name: source_counts[table_name] - included_counts.get(table_name, 0)
        for table_name in (
            _fiscal_package_format().FILTERED_TABLES
            + _fiscal_package_format().EXCLUDED_TABLES
        )
    }
    closure = _v4_closure_payload(
        rows=selected_rows,
        normalization=normalization,
    )
    safe_omitted = {
        "blockers": 0,
        "legacy_preflight": legacy_safety,
        "source_counts": source_counts,
        "included_counts": included_counts,
        "omitted_counts": omitted_counts,
    }
    validate_v4_graph(
        selected_rows,
        normalization=normalization,
        closure=closure,
    )
    return V4Capture(
        rows=selected_rows,
        source_counts=source_counts,
        included_counts=included_counts,
        omitted_counts=omitted_counts,
        safe_omitted=safe_omitted,
        normalization=normalization,
        closure=closure,
    )


def validate_v4_source_coordinators(conn: sqlite3.Connection) -> None:
    """Valida coordenadas fuente sin trasladar su revisión técnica."""
    companies = {
        int(row["id"]) for row in conn.execute("SELECT id FROM empresas ORDER BY id")
    }
    rows = [
        (int(row["empresa_id"]), str(row["ambiente"]))
        for row in conn.execute(
            "SELECT empresa_id, ambiente FROM lotes_duplicados_coordinacion "
            "ORDER BY empresa_id, ambiente"
        )
    ]
    expected = sorted(
        (company_id, environment)
        for company_id in companies
        for environment in ("homologacion", "produccion")
    )
    if rows != expected:
        raise MigrationError(
            "La coordinación PF-13 fuente no tiene dos ambientes exactos por emisor"
        )


def validate_v4_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Exige columnas v4 exactas antes de calcular cualquier selección."""
    for table_name in _fiscal_package_format().INCLUDED_TABLES:
        columns = tuple(
            str(row["name"])
            for row in conn.execute(f'PRAGMA table_info("{table_name}")')
        )
        if columns != _fiscal_package_format().V4_COLUMNS[table_name]:
            raise MigrationError(
                f"La fuente SQLite ya no representa el contrato v4 de {table_name}"
            )


def _v4_json_object(value: Any, *, label: str) -> dict[str, Any]:
    try:
        result = _json_dict_or_none(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MigrationError(f"JSON inválido en {label}") from exc
    if result is None:
        raise MigrationError(f"Falta JSON obligatorio en {label}")
    return result


def _v4_generation_relation(
    generation: dict[str, Any],
    *,
    blocks: list[dict[str, Any]],
    members_by_block: dict[int, list[dict[str, Any]]],
    group_ids: set[int],
    receipt_ids: set[int],
) -> list[dict[str, Any]]:
    relation: list[dict[str, Any]] = []
    for block in sorted(blocks, key=lambda item: str(item["bloque_clave"])):
        if (
            int(block["operacion_id"]) != int(generation["operacion_id"])
            or int(block["empresa_id"]) != int(generation["empresa_id"])
            or int(block["lote_id"]) != int(generation["lote_id"])
            or str(block["ambiente"]) != str(generation["ambiente"])
        ):
            raise MigrationError("Un bloque PF-13 no pertenece a su generación")
        block_snapshot = _v4_json_object(
            block["snapshot_json"],
            label=f"bloque {block['id']}",
        )
        block_members = sorted(
            members_by_block.get(int(block["id"]), []),
            key=lambda item: (
                str(item["lado"]),
                int(item["ordinal"]) if item["ordinal"] is not None else -1,
                str(item["miembro_clave"]),
            ),
        )
        current = [row for row in block_members if row["lado"] == "actual"]
        previous = [row for row in block_members if row["lado"] == "anterior"]
        if block["clase"] in {"interna_nombre", "interna_documento"}:
            valid_shape = (
                len(current) >= 2
                and not previous
                and all(row["ordinal"] is None for row in current)
            )
        elif block["clase"] == "completa":
            current_ordinals = {row["ordinal"] for row in current}
            previous_ordinals = {row["ordinal"] for row in previous}
            multiplicity = block_snapshot.get("multiplicidad_total")
            valid_shape = (
                bool(current)
                and bool(previous)
                and (
                    None not in current_ordinals
                    and current_ordinals == previous_ordinals
                    and len(current_ordinals) == len(current)
                    and len(previous_ordinals) == len(previous)
                    and isinstance(multiplicity, int)
                    and all(
                        0 <= int(value) < multiplicity for value in current_ordinals
                    )
                )
            )
        else:
            valid_shape = (
                block["clase"]
                in {"parcial_nombre", "parcial_documento", "individual_legacy"}
                and bool(current)
                and bool(previous)
                and all(row["ordinal"] is None for row in block_members)
            )
        if not valid_shape:
            raise MigrationError("La multiplicidad u ordinal PF-13 no es canónica")

        canonical_members = []
        for member in block_members:
            snapshot = _v4_json_object(
                member["snapshot_json"],
                label=f"miembro {member['id']}",
            )
            decision = snapshot.get("decision")
            if not isinstance(decision, dict):
                raise MigrationError("Un miembro PF-13 no conserva decisión")
            group_id = member.get("grupo_id")
            receipt_id = member.get("comprobante_id")
            if (group_id is None) == (receipt_id is None):
                raise MigrationError("Un miembro PF-13 no identifica una entidad única")
            if group_id is not None:
                if int(group_id) not in group_ids or decision.get("grupo_id") != int(
                    group_id
                ):
                    raise MigrationError("Un miembro PF-13 perdió su grupo")
            elif int(receipt_id) not in receipt_ids or decision.get(
                "comprobante_id"
            ) != int(receipt_id):
                raise MigrationError("Un miembro PF-13 perdió su comprobante")
            if member["lado"] == "actual":
                if group_id is None or member["relevancia"] != "actual":
                    raise MigrationError("Un miembro actual PF-13 es incoherente")
            elif member["lado"] != "anterior" or member["relevancia"] not in {
                "autorizado",
                "reservado",
                "incierto",
            }:
                raise MigrationError("Un miembro anterior PF-13 es incoherente")
            canonical_members.append(
                {
                    "lado": member["lado"],
                    "miembro_clave": member["miembro_clave"],
                    "grupo_id": group_id,
                    "comprobante_id": receipt_id,
                    "nombre_hash": member["nombre_hash"],
                    "documento_hash": member["documento_hash"],
                    "ordinal": member["ordinal"],
                    "relevancia": member["relevancia"],
                    "snapshot": snapshot,
                }
            )
        relation.append(
            {
                "bloque_clave": block["bloque_clave"],
                "clase": block["clase"],
                "antecedente_clave": block["antecedente_clave"],
                "snapshot": block_snapshot,
                "miembros": canonical_members,
            }
        )
    return relation


def _v4_replay_lot_matches_durable(
    replay_lot: dict[str, Any],
    durable_lot: dict[str, Any],
) -> bool:
    """Coteja identidad inmutable sin exigir que el snapshot replique cierres posteriores."""

    def utc_creation_instant(lot: dict[str, Any]) -> datetime:
        # Ambos created_at proceden del reloj UTC del lote. La forma legacy
        # sin zona y la respuesta con zona representan el mismo instante.
        created_at = datetime.fromisoformat(
            str(lot.get("created_at")).replace("Z", "+00:00")
        )
        if created_at.utcoffset() is None:
            return created_at.replace(tzinfo=timezone.utc)
        return created_at.astimezone(timezone.utc)

    immutable_fields = (
        "id",
        "nombre_archivo",
        "archivo_hash",
        "modo_procesamiento",
        "procesamiento_async",
        "total_filas",
        "total_grupos",
        "empresa_id",
        "usuario_id",
        "formato_importacion_id",
        "formato_importacion_version_id",
    )
    try:
        return bool(
            all(
                replay_lot.get(field) == durable_lot.get(field)
                for field in immutable_fields
            )
            and replay_lot.get("estado") in ESTADOS_LOTE_SEGUROS_OMITIBLES
            and durable_lot.get("estado") in ESTADOS_LOTE_SEGUROS_OMITIBLES
            and utc_creation_instant(replay_lot) == utc_creation_instant(durable_lot)
        )
    except (TypeError, ValueError):
        return False


def _v4_has_minimum_authorization_evidence(
    *,
    receipt_id: Any,
    number: Any,
    cae: Any,
    cae_expiration: Any,
) -> bool:
    """Exige la evidencia positiva histórica antes de cotejar copias v4."""
    return bool(
        isinstance(receipt_id, int)
        and not isinstance(receipt_id, bool)
        and receipt_id > 0
        and isinstance(number, int)
        and not isinstance(number, bool)
        and number > 0
        and isinstance(cae, str)
        and cae.strip()
        and cae_expiration is not None
    )


def _validate_v4_terminal_replays(
    rows: dict[str, list[dict[str, Any]]],
    *,
    normalization_pairs: list[dict[str, Any]],
) -> None:
    """Valida replay terminal v4 con lote preservado o normalización legacy explícita."""
    companies = {int(row["id"]) for row in rows["empresas"]}
    receipts = {int(row["id"]): row for row in rows["comprobantes"]}
    lotes = {int(row["id"]): row for row in rows["lotes_comprobantes"]}
    revisions = {
        int(row["id"]): row for row in rows["puntos_venta_elegibilidad_rece_revisiones"]
    }
    associations_by_operation: dict[int, list[dict[str, Any]]] = {}
    for association in rows["operaciones_idempotentes_elegibilidad_rece"]:
        associations_by_operation.setdefault(
            int(association["operacion_id"]), []
        ).append(association)
    pair_by_operation = {
        int(pair["operacion_id"]): pair for pair in normalization_pairs
    }
    identities: set[tuple[int, str]] = set()

    for operation in rows["operaciones_idempotentes"]:
        try:
            operation_id = _require_nonnegative_int(
                operation["id"], label="operacion.id"
            )
            company_id = _require_nonnegative_int(
                operation["empresa_id"], label="operacion.empresa_id"
            )
            key = operation["idempotency_key"]
            operation_type = operation["tipo_operacion"]
            state = operation["estado"]
            if (
                operation_id <= 0
                or company_id <= 0
                or company_id not in companies
                or not isinstance(key, str)
                or not 1 <= len(key.strip()) <= 128
                or key != key.strip()
                or operation_type
                not in {
                    "emitir_comprobante",
                    "procesar_lote",
                    "reintentar_fallidos_lote",
                }
                or state not in ESTADOS_OPERACION_TERMINALES
            ):
                raise MigrationError("Replay terminal v4 con operación inválida")
            _require_sha256(operation["payload_hash"], label="operacion.payload_hash")
            identity = (company_id, key)
            if identity in identities:
                raise MigrationError("Replay terminal v4 con identidad duplicada")
            identities.add(identity)
            response = _v4_json_object(
                operation.get("response_json"),
                label=f"replay terminal v4 {operation_id}",
            )
            pair = pair_by_operation.get(operation_id)

            if operation_type == "emitir_comprobante":
                if operation.get("lote_id") is not None or pair is not None:
                    raise MigrationError("Replay terminal v4 individual conserva lote")
                parsed = vps_migration_v3.parse_individual_replay(response)
                if parsed.requiere_reconciliacion:
                    raise MigrationError("Replay terminal v4 individual incierto")
                associations = associations_by_operation.get(operation_id, [])
                if operation.get("rece_snapshot_hash") is not None:
                    if len(associations) != 1:
                        raise MigrationError(
                            "Replay terminal v4 individual sin asociación RECE exacta"
                        )
                    revision = revisions[
                        int(associations[0]["elegibilidad_revision_id"])
                    ]
                    if (
                        int(revision["punto_venta_numero_snapshot"])
                        != parsed.punto_venta
                    ):
                        raise MigrationError(
                            "Replay terminal v4 individual cruza el snapshot RECE"
                        )
                if parsed.exito:
                    if not _v4_has_minimum_authorization_evidence(
                        receipt_id=parsed.comprobante_id,
                        number=parsed.numero,
                        cae=parsed.cae,
                        cae_expiration=parsed.cae_vencimiento,
                    ):
                        raise MigrationError(
                            "Replay terminal v4 exitoso sin evidencia fiscal completa"
                        )
                    receipt = receipts.get(int(parsed.comprobante_id or 0))
                    if receipt is None:
                        raise MigrationError(
                            "Replay terminal v4 exitoso sin comprobante"
                        )
                    if (
                        state != "finalizado"
                        or not _v4_has_minimum_authorization_evidence(
                            receipt_id=receipt["id"],
                            number=receipt["numero"],
                            cae=receipt["cae"],
                            cae_expiration=receipt["cae_vencimiento"],
                        )
                        or receipt["estado"] != "autorizado"
                        or int(receipt["empresa_id"]) != company_id
                        or int(receipt["tipo_comprobante"]) != parsed.tipo_comprobante
                        or int(receipt["numero"]) != parsed.numero
                        or date.fromisoformat(str(receipt["fecha_emision"])[:10])
                        != parsed.fecha
                        or Decimal(str(receipt["total"])) != parsed.total
                        or str(receipt["cae"]) != str(parsed.cae)
                        or date.fromisoformat(str(receipt["cae_vencimiento"])[:10])
                        != parsed.cae_vencimiento
                        or (
                            associations
                            and int(receipt["punto_venta_id"])
                            != int(associations[0]["punto_venta_id"])
                        )
                    ):
                        raise MigrationError(
                            "Replay terminal v4 individual no coincide con su comprobante"
                        )
                elif (
                    state == "finalizado"
                    or parsed.comprobante_id is not None
                    or parsed.cae is not None
                    or parsed.cae_vencimiento is not None
                    or parsed.categoria_error
                    in {"duplicado_logico", "idempotencia_en_proceso"}
                ):
                    raise MigrationError(
                        "Replay terminal v4 individual negativo inválido"
                    )
                if parsed.categoria_error == ARCA_RECHAZO_GLOBAL_CATEGORIA and (
                    state != "rechazado_arca"
                    or not _response_is_exact_global_10005(parsed)
                ):
                    raise MigrationError("Replay terminal v4 individual 10005 inválido")
                continue

            preserved_lote_id = operation.get("lote_id")
            expected_lote_id = (
                int(preserved_lote_id)
                if preserved_lote_id is not None
                else int(pair["lote_id"] if pair is not None else 0)
            )
            if expected_lote_id <= 0 or (preserved_lote_id is None) != (
                pair is not None
            ):
                raise MigrationError("Replay terminal v4 batch sin lote trazable")
            if "categoria_error" in response:
                parsed_error = vps_migration_v3.parse_batch_error_replay(response)
                if (
                    state in {"finalizado", "rechazado_arca"}
                    or not parsed_error.categoria_error.strip()
                    or parsed_error.categoria_error
                    in {
                        "duplicado_logico_lote",
                        "idempotencia_en_proceso",
                        "post_arca_persistencia",
                    }
                    or (
                        parsed_error.status_code is not None
                        and not 400 <= parsed_error.status_code <= 599
                    )
                ):
                    raise MigrationError("Replay terminal v4 batch negativo inválido")
                continue
            parsed_batch = vps_migration_v3.parse_batch_replay(
                response,
                operation_type=operation_type,
            )
            if operation_type == "procesar_lote" and parsed_batch.en_progreso:
                raise MigrationError("Replay terminal v4 batch todavía en progreso")
            global_rejection = _batch_global_rejection_context(
                response,
                operation_type=operation_type,
                operation_id=operation_id,
            )
            if state == "rechazado_arca":
                if global_rejection is None:
                    raise MigrationError("Replay terminal v4 batch 10005 inválido")
            elif global_rejection is not None or parsed_batch.errores_arca:
                raise MigrationError("Replay terminal v4 batch contradice su estado")
            if (
                state not in {"finalizado", "fallido", "rechazado_arca"}
                or parsed_batch.lote.id != expected_lote_id
                or parsed_batch.lote.empresa_id != company_id
                or parsed_batch.lote.estado not in ESTADOS_LOTE_SEGUROS_OMITIBLES
            ):
                raise MigrationError("Replay terminal v4 batch no coincide con su lote")
            if preserved_lote_id is not None:
                durable_lot = lotes.get(expected_lote_id)
                replay_lot = response.get("lote")
                if (
                    durable_lot is None
                    or not isinstance(replay_lot, dict)
                    or not _v4_replay_lot_matches_durable(replay_lot, durable_lot)
                ):
                    raise MigrationError(
                        "Replay terminal v4 batch no coincide con el lote durable"
                    )
        except MigrationError:
            raise
        except (
            DecimalException,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise MigrationError("Replay terminal v4 semánticamente inválido") from exc


def _validate_v4_attempt_fiscal_evidence(
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Coteja cada intento terminal con operación, grupo, guarda y comprobante."""
    receipts = {int(row["id"]): row for row in rows["comprobantes"]}
    sale_points = {int(row["id"]): row for row in rows["puntos_venta"]}
    lotes = {int(row["id"]): row for row in rows["lotes_comprobantes"]}
    groups = {int(row["id"]): row for row in rows["lotes_comprobantes_grupos"]}
    operations = {int(row["id"]): row for row in rows["operaciones_idempotentes"]}
    revisions = {
        int(row["id"]): row for row in rows["puntos_venta_elegibilidad_rece_revisiones"]
    }
    generations = {int(row["id"]): row for row in rows["lotes_duplicados_evidencias"]}
    guards = {int(row["id"]): row for row in rows["puntos_venta_guardas_emision_rece"]}
    attempts = rows["intentos_emision_fiscal"]
    attempts_by_guard: dict[int, list[dict[str, Any]]] = {}
    attempts_by_operation: dict[int, list[dict[str, Any]]] = {}
    associations_by_operation: dict[int, list[dict[str, Any]]] = {}
    for association in rows["operaciones_idempotentes_elegibilidad_rece"]:
        associations_by_operation.setdefault(
            int(association["operacion_id"]), []
        ).append(association)

    for attempt in attempts:
        try:
            attempt_id = int(attempt["id"])
            state = attempt["estado"]
            operation = operations.get(int(attempt.get("operacion_id") or 0))
            if state not in ESTADOS_INTENTO_TERMINALES or operation is None:
                raise MigrationError("Intento terminal v4 sin operación válida")
            attempts_by_operation.setdefault(int(operation["id"]), []).append(attempt)
            if int(operation["empresa_id"]) != int(attempt["empresa_id"]):
                raise MigrationError("Intento terminal v4 cruza el emisor")
            sale_point = sale_points.get(int(attempt["punto_venta_id"]))
            revision_id = attempt.get("punto_venta_elegibilidad_revision_id")
            revision = (
                revisions.get(int(revision_id)) if revision_id is not None else None
            )
            historical_sale_point_number = (
                revision.get("punto_venta_numero_snapshot")
                if revision is not None
                else None
            )
            if (
                sale_point is None
                or int(sale_point["empresa_id"]) != int(attempt["empresa_id"])
                or (
                    revision_id is None
                    and int(sale_point["numero"]) != int(attempt["punto_venta_numero"])
                )
                or (
                    revision_id is not None
                    and (
                        revision is None
                        or int(revision["empresa_id"]) != int(attempt["empresa_id"])
                        or int(revision["punto_venta_id"])
                        != int(attempt["punto_venta_id"])
                        or revision["ambiente"] != attempt.get("ambiente")
                        or int(revision["punto_revision_fiscal"])
                        != int(attempt.get("punto_venta_revision_fiscal") or 0)
                        or int(historical_sale_point_number or 0)
                        != int(attempt["punto_venta_numero"])
                    )
                )
            ):
                raise MigrationError("Intento terminal v4 cruza el punto de venta")
            group = None
            if attempt.get("lote_id") is not None:
                group = groups.get(int(attempt.get("grupo_id") or 0))
                if (
                    int(attempt["lote_id"]) not in lotes
                    or group is None
                    or int(group["lote_id"]) != int(attempt["lote_id"])
                    or int(group["empresa_id"]) != int(attempt["empresa_id"])
                    or int(operation.get("lote_id") or 0) != int(attempt["lote_id"])
                ):
                    raise MigrationError("Intento terminal v4 perdió lote o grupo")
            elif attempt.get("grupo_id") is not None:
                raise MigrationError("Intento terminal v4 conserva grupo sin lote")

            generation = None
            generation_id = attempt.get("duplicados_generacion_id")
            if generation_id is not None:
                generation = generations.get(int(generation_id))
                if (
                    generation is None
                    or int(generation["operacion_id"]) != int(attempt["operacion_id"])
                    or int(generation["empresa_id"]) != int(attempt["empresa_id"])
                    or int(generation["lote_id"]) != int(attempt["lote_id"])
                    or generation["ambiente"] != attempt["ambiente"]
                ):
                    raise MigrationError("Intento terminal v4 perdió su generación")
                selected = _v4_json_object(
                    generation["control_snapshot_json"],
                    label=f"generación del intento {attempt_id}",
                ).get("seleccion_original")
                selected_ids = {
                    item.get("grupo_id") for item in selected if isinstance(item, dict)
                }
                if group is None or int(group["id"]) not in selected_ids:
                    raise MigrationError(
                        "Intento terminal v4 quedó fuera de su selección"
                    )

            guard = None
            guard_id = attempt.get("guarda_rece_id")
            rece_snapshot_values = (
                attempt.get("ambiente"),
                attempt.get("punto_venta_elegibilidad_revision_id"),
                attempt.get("punto_venta_revision_fiscal"),
                guard_id,
            )
            legacy_rece = all(value is None for value in rece_snapshot_values)
            modern_rece = all(value is not None for value in rece_snapshot_values)
            if not (legacy_rece or modern_rece):
                raise MigrationError(
                    "Intento terminal v4 conserva un snapshot RECE parcial"
                )
            if guard_id is not None:
                guard = guards.get(int(guard_id))
                if (
                    guard is None
                    or any(
                        guard[field] != attempt[field]
                        for field in (
                            "operacion_id",
                            "empresa_id",
                            "punto_venta_id",
                            "ambiente",
                            "punto_venta_revision_fiscal",
                        )
                    )
                    or int(guard["elegibilidad_revision_id"])
                    != int(attempt["punto_venta_elegibilidad_revision_id"])
                ):
                    raise MigrationError("Intento terminal v4 perdió su guarda RECE")
                attempts_by_guard.setdefault(int(guard_id), []).append(attempt)

            if state == "autorizado":
                authorized_operation_state_is_valid = bool(
                    operation["estado"] == "finalizado"
                    or (
                        operation["tipo_operacion"]
                        in {"procesar_lote", "reintentar_fallidos_lote"}
                        and operation["estado"]
                        in {"finalizado", "fallido", "rechazado_arca"}
                    )
                )
                if not _v4_has_minimum_authorization_evidence(
                    receipt_id=attempt.get("comprobante_id"),
                    number=attempt.get("numero_planificado"),
                    cae=attempt.get("cae"),
                    cae_expiration=attempt.get("cae_vencimiento"),
                ):
                    raise MigrationError(
                        "Intento autorizado v4 sin evidencia fiscal completa"
                    )
                receipt = receipts.get(int(attempt.get("comprobante_id") or 0))
                if receipt is None:
                    raise MigrationError("Intento autorizado v4 sin comprobante")
                if (
                    not authorized_operation_state_is_valid
                    or not _v4_has_minimum_authorization_evidence(
                        receipt_id=receipt["id"],
                        number=receipt["numero"],
                        cae=receipt["cae"],
                        cae_expiration=receipt["cae_vencimiento"],
                    )
                    or receipt["estado"] != "autorizado"
                    or int(receipt["empresa_id"]) != int(attempt["empresa_id"])
                    or int(receipt["punto_venta_id"]) != int(attempt["punto_venta_id"])
                    or int(receipt["tipo_comprobante"])
                    != int(attempt["tipo_comprobante"])
                    or int(receipt["numero"]) != int(attempt["numero_planificado"])
                    or date.fromisoformat(str(receipt["fecha_emision"])[:10])
                    != date.fromisoformat(str(attempt["fecha_emision"])[:10])
                    or Decimal(str(receipt["total"])) != Decimal(str(attempt["total"]))
                    or str(receipt["cae"]) != str(attempt["cae"])
                    or date.fromisoformat(str(receipt["cae_vencimiento"])[:10])
                    != date.fromisoformat(str(attempt["cae_vencimiento"])[:10])
                    or (
                        modern_rece
                        and (guard is None or guard["fase"] != "cerrada_terminal")
                    )
                ):
                    raise MigrationError(
                        "Intento autorizado v4 contradice su comprobante"
                    )
                if group is not None and (
                    group["estado"] != "autorizado"
                    or int(group.get("comprobante_id") or 0) != int(receipt["id"])
                    or int(group["punto_venta_id"]) != int(attempt["punto_venta_id"])
                    or int(group["punto_venta_numero"])
                    != int(attempt["punto_venta_numero"])
                    or int(group["tipo_comprobante"])
                    != int(attempt["tipo_comprobante"])
                    or int(group.get("numero_asignado") or 0)
                    != int(attempt["numero_planificado"])
                    or Decimal(str(group["total_estimado"]))
                    != Decimal(str(attempt["total"]))
                    or str(group.get("cae")) != str(attempt["cae"])
                    or (
                        group.get("duplicados_version") == "duplicados_lotes/v2"
                        and date.fromisoformat(
                            str(group["fecha_emision_normalizada"])[:10]
                        )
                        != date.fromisoformat(str(attempt["fecha_emision"])[:10])
                    )
                ):
                    raise MigrationError("Intento autorizado v4 contradice su grupo")
                continue

            if any(
                attempt.get(field) is not None
                for field in ("comprobante_id", "cae", "cae_vencimiento")
            ):
                raise MigrationError(
                    "Intento terminal v4 negativo conserva evidencia positiva"
                )
            if guard is not None and (
                (state == "fallido_verificado" and guard["fase"] != "cerrada_pre_arca")
                or (state == "rechazado_arca" and guard["fase"] != "cerrada_terminal")
            ):
                raise MigrationError("Intento terminal v4 contradice la fase de guarda")
            if state == "fallido_verificado" and not _is_json_null_sqlite(
                attempt.get("errores_arca_json")
            ):
                raise MigrationError("Intento fallido v4 inventa evidencia ARCA")
            if state == "rechazado_arca" and (
                attempt.get("categoria_error") == ARCA_RECHAZO_GLOBAL_CATEGORIA
                or not _is_json_null_sqlite(attempt.get("errores_arca_json"))
            ):
                lot = lotes.get(int(operation.get("lote_id") or 0))
                operation_view = {
                    **operation,
                    "lote_encontrado": None if lot is None else lot["id"],
                    "lote_empresa_id": None if lot is None else lot["empresa_id"],
                    "lote_estado": None if lot is None else lot["estado"],
                }
                if not pf19c_global_rejection_matches_operation(
                    attempt, operation_view
                ):
                    raise MigrationError("Intento rechazado v4 no acredita PF-19C")
        except MigrationError:
            raise
        except (
            DecimalException,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise MigrationError("Intento terminal v4 semánticamente inválido") from exc

    for guard_id, guard in guards.items():
        guarded = attempts_by_guard.get(guard_id, [])
        states = {attempt["estado"] for attempt in guarded}
        if (
            not guarded
            or (
                guard["fase"] == "cerrada_pre_arca" and states != {"fallido_verificado"}
            )
            or (
                guard["fase"] == "cerrada_terminal"
                and not states <= {"autorizado", "rechazado_arca"}
            )
            or guard["fase"] not in FASES_GUARDA_TERMINALES
        ):
            raise MigrationError("Guarda terminal v4 sin intentos coherentes")

    for operation_id, operation in operations.items():
        if operation["tipo_operacion"] != "emitir_comprobante":
            continue
        response = _v4_json_object(
            operation["response_json"],
            label=f"replay individual del intento {operation_id}",
        )
        try:
            replay = vps_migration_v3.parse_individual_replay(response)
            operation_attempts = attempts_by_operation.get(operation_id, [])
            authorized = [
                attempt
                for attempt in operation_attempts
                if attempt["estado"] == "autorizado"
            ]
            if not replay.exito:
                if authorized:
                    raise MigrationError(
                        "Replay individual negativo v4 conserva autorización"
                    )
                continue
            operation_guards = [
                guard
                for guard in guards.values()
                if int(guard["operacion_id"]) == operation_id
            ]
            if (
                operation.get("rece_snapshot_hash") is None
                and not operation_attempts
                and not operation_guards
            ):
                continue
            if len(authorized) != 1:
                raise MigrationError(
                    "Replay individual exitoso v4 no conserva una autorización única"
                )
            attempt = authorized[0]
            if (
                int(attempt["comprobante_id"]) != int(replay.comprobante_id or 0)
                or int(attempt["empresa_id"]) != int(operation["empresa_id"])
                or int(attempt["tipo_comprobante"]) != replay.tipo_comprobante
                or int(attempt["punto_venta_numero"]) != replay.punto_venta
                or int(attempt["numero_planificado"]) != replay.numero
                or date.fromisoformat(str(attempt["fecha_emision"])[:10])
                != replay.fecha
                or Decimal(str(attempt["total"])) != replay.total
                or str(attempt["cae"]) != str(replay.cae)
                or date.fromisoformat(str(attempt["cae_vencimiento"])[:10])
                != replay.cae_vencimiento
            ):
                raise MigrationError(
                    "La autorización individual v4 contradice su replay"
                )
            if operation.get("rece_snapshot_hash") is not None:
                associations = associations_by_operation.get(operation_id, [])
                guard = guards.get(int(attempt.get("guarda_rece_id") or 0))
                if (
                    len(associations) != 1
                    or guard is None
                    or guard["fase"] != "cerrada_terminal"
                    or attempt["ambiente"] != associations[0]["ambiente"]
                    or int(attempt["punto_venta_id"])
                    != int(associations[0]["punto_venta_id"])
                    or int(attempt["punto_venta_elegibilidad_revision_id"])
                    != int(associations[0]["elegibilidad_revision_id"])
                    or int(attempt["punto_venta_revision_fiscal"])
                    != int(associations[0]["punto_venta_revision_fiscal"])
                    or int(guard["empresa_id"]) != int(associations[0]["empresa_id"])
                    or int(guard["punto_venta_id"])
                    != int(associations[0]["punto_venta_id"])
                    or guard["ambiente"] != associations[0]["ambiente"]
                    or int(guard["elegibilidad_revision_id"])
                    != int(associations[0]["elegibilidad_revision_id"])
                    or int(guard["punto_venta_revision_fiscal"])
                    != int(associations[0]["punto_venta_revision_fiscal"])
                ):
                    raise MigrationError(
                        "La autorización individual v4 contradice RECE"
                    )
        except MigrationError:
            raise
        except (DecimalException, KeyError, TypeError, ValueError) as exc:
            raise MigrationError(
                "La evidencia de autorización individual v4 es inválida"
            ) from exc


def _validate_v4_pf19c_history(
    rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Conserva el rechazo global exacto y un único sucesor autorizado legítimo."""
    groups = {int(row["id"]): row for row in rows["lotes_comprobantes_grupos"]}
    operations = {int(row["id"]): row for row in rows["operaciones_idempotentes"]}
    attempts_by_operation: dict[int, list[dict[str, Any]]] = {}
    attempts_by_group: dict[int, list[dict[str, Any]]] = {}
    for attempt in rows["intentos_emision_fiscal"]:
        attempts_by_operation.setdefault(int(attempt["operacion_id"]), []).append(
            attempt
        )
        if attempt.get("grupo_id") is not None:
            attempts_by_group.setdefault(int(attempt["grupo_id"]), []).append(attempt)

    for operation_id, operation in operations.items():
        if operation["tipo_operacion"] not in {
            "procesar_lote",
            "reintentar_fallidos_lote",
        }:
            continue
        response = _v4_json_object(
            operation["response_json"], label=f"replay PF-19C {operation_id}"
        )
        context = _batch_global_rejection_context(
            response,
            operation_type=operation["tipo_operacion"],
            operation_id=operation_id,
        )
        if operation["estado"] != "rechazado_arca" and context is None:
            continue
        if context is None or operation.get("lote_id") is None:
            raise MigrationError("El rechazo global v4 no conserva su lote")
        rejection_ids, not_sent_ids = context
        operation_attempts = attempts_by_operation.get(operation_id, [])
        rejection_attempts = [
            attempt
            for attempt in operation_attempts
            if attempt.get("grupo_id") is not None
            and attempt["estado"] == "rechazado_arca"
            and attempt["categoria_error"] == ARCA_RECHAZO_GLOBAL_CATEGORIA
            and _is_exact_global_10005_errors(attempt.get("errores_arca_json"))
        ]
        rejected_group_ids = [
            int(attempt["grupo_id"]) for attempt in rejection_attempts
        ]
        context_groups = [
            groups.get(group_id) for group_id in rejection_ids | not_sent_ids
        ]

        def group_preserves_history(group: dict[str, Any]) -> bool:
            if int(group["lote_id"]) != int(operation["lote_id"]) or int(
                group["empresa_id"]
            ) != int(operation["empresa_id"]):
                return False
            if group["estado"] == "fallido":
                return True
            if group["estado"] != "autorizado":
                return False
            successors = []
            for attempt in attempts_by_group.get(int(group["id"]), []):
                successor_id = int(attempt.get("operacion_id") or 0)
                successor = operations.get(successor_id)
                if (
                    attempt["estado"] == "autorizado"
                    and attempt.get("comprobante_id") is not None
                    and successor_id > operation_id
                    and successor is not None
                    and successor["tipo_operacion"]
                    in {"procesar_lote", "reintentar_fallidos_lote"}
                    and successor["estado"] == "finalizado"
                    and int(successor.get("lote_id") or 0) == int(group["lote_id"])
                    and int(successor["empresa_id"]) == int(group["empresa_id"])
                    and (
                        not _is_v4_operation(operation)
                        or (
                            _is_v4_operation(successor)
                            and successor["tipo_operacion"]
                            == "reintentar_fallidos_lote"
                            and int(successor["operacion_raiz_id"])
                            == int(operation["operacion_raiz_id"])
                        )
                    )
                ):
                    successors.append(attempt)
            return len(successors) == 1

        if (
            len(rejected_group_ids) != len(rejection_ids)
            or set(rejected_group_ids) != set(rejection_ids)
            or len(rejected_group_ids) != len(set(rejected_group_ids))
            or any(
                len(
                    [
                        attempt
                        for attempt in operation_attempts
                        if attempt.get("grupo_id") is not None
                        and int(attempt["grupo_id"]) == group_id
                    ]
                )
                != 1
                for group_id in rejection_ids
            )
            or any(group is None for group in context_groups)
            or any(
                not group_preserves_history(group)
                for group in context_groups
                if group is not None
            )
            or any(
                attempt.get("grupo_id") is not None
                and int(attempt["grupo_id"]) in not_sent_ids
                for attempt in operation_attempts
            )
        ):
            raise MigrationError("El rechazo global v4 perdió su historia terminal")


def validate_v4_graph(
    rows: dict[str, list[dict[str, Any]]],
    *,
    normalization: dict[str, Any],
    closure: dict[str, Any],
) -> None:
    """Valida clausura, procedencia y barrera semántica PF-13 sin ORM mutable."""
    if set(rows) != set(_fiscal_package_format().INCLUDED_TABLES):
        raise MigrationError("La selección v4 no contiene su partición exacta")
    _validate_packaged_v4_foreign_keys(rows)
    companies = {int(row["id"]) for row in rows["empresas"]}
    users = {int(row["id"]): row for row in rows["usuarios"]}
    receipts = {int(row["id"]): row for row in rows["comprobantes"]}
    lotes = {int(row["id"]): row for row in rows["lotes_comprobantes"]}
    groups = {int(row["id"]): row for row in rows["lotes_comprobantes_grupos"]}
    operations = {int(row["id"]): row for row in rows["operaciones_idempotentes"]}
    generations = {int(row["id"]): row for row in rows["lotes_duplicados_evidencias"]}
    blocks = {int(row["id"]): row for row in rows["lotes_duplicados_coincidencias"]}
    group_ids = set(groups)
    receipt_ids = set(receipts)
    latest_generation_by_operation: dict[int, dict[str, Any]] = {}
    for generation in generations.values():
        operation_id = int(generation["operacion_id"])
        latest = latest_generation_by_operation.get(operation_id)
        if latest is None or int(generation["generacion"]) > int(latest["generacion"]):
            latest_generation_by_operation[operation_id] = generation

    pairs = normalization.get("pairs")
    if (
        normalization.get("rule")
        != _fiscal_package_format().OPERATION_LOTE_NORMALIZATION_RULE
        or not isinstance(pairs, list)
        or normalization.get("rows") != len(pairs)
        or normalization.get("sha256")
        != _fiscal_package_format().canonical_sha256(pairs)
    ):
        raise MigrationError("La normalización legacy v4 no es canónica")
    pair_operations: set[int] = set()
    for pair in pairs:
        validated = _validate_normalization_pairs([pair])[0]
        operation_id = int(validated["operacion_id"])
        if (
            operation_id in pair_operations
            or operation_id not in operations
            or operations[operation_id]["lote_id"] is not None
            or _is_v4_operation(operations[operation_id])
            or int(validated["lote_id"]) in lotes
        ):
            raise MigrationError("Una operación no pertenece sólo a legacy omitido")
        pair_operations.add(operation_id)

    _validate_v4_terminal_replays(rows, normalization_pairs=pairs)

    for lote_id, lote in lotes.items():
        if int(lote["empresa_id"]) not in companies:
            raise MigrationError("Un lote v4 no pertenece a un emisor incluido")
        lote_groups = [row for row in groups.values() if int(row["lote_id"]) == lote_id]
        if len(lote_groups) != int(
            closure.get("group_counts_by_lote", {}).get(str(lote_id), -1)
        ) or len(lote_groups) != int(lote["total_grupos"]):
            raise MigrationError("Un lote v4 no conserva todos sus grupos")
        if any(
            int(row["empresa_id"]) != int(lote["empresa_id"]) for row in lote_groups
        ):
            raise MigrationError("Un grupo v4 cruza el emisor de su lote")
        state_counts = {
            state: sum(row["estado"] == state for row in lote_groups)
            for state in ESTADOS_GRUPO_SEGUROS_OMITIBLES
        }
        if (
            int(lote["grupos_con_error"]) != state_counts["con_error"]
            or int(lote["grupos_emitidos"]) != state_counts["autorizado"]
            or int(lote["grupos_reconciliados_externos"])
            != state_counts["autorizado_externo"]
            or int(lote["grupos_fallidos"]) != state_counts["fallido"]
            or int(lote["grupos_descartados"]) != state_counts["descartado"]
        ):
            raise MigrationError("Los estados de grupos v4 no reconcilian con su lote")

    for group in groups.values():
        state = group["estado"]
        if state not in ESTADOS_GRUPO_SEGUROS_OMITIBLES:
            raise MigrationError("Un grupo v4 conserva un estado no terminal seguro")
        if state in {"autorizado", "autorizado_externo"}:
            receipt = receipts.get(int(group.get("comprobante_id") or 0))
            snapshot_values = (
                group.get("punto_venta_id"),
                group.get("ambiente"),
                group.get("punto_venta_elegibilidad_revision_id"),
                group.get("punto_venta_revision_fiscal"),
            )
            snapshot_legacy = all(value is None for value in snapshot_values)
            snapshot_modern = all(value is not None for value in snapshot_values)
            if (
                receipt is None
                or not _v4_has_minimum_authorization_evidence(
                    receipt_id=group.get("comprobante_id"),
                    number=group.get("numero_asignado"),
                    cae=group.get("cae"),
                    cae_expiration=receipt.get("cae_vencimiento"),
                )
                or not _v4_has_minimum_authorization_evidence(
                    receipt_id=receipt.get("id"),
                    number=receipt.get("numero"),
                    cae=receipt.get("cae"),
                    cae_expiration=receipt.get("cae_vencimiento"),
                )
                or receipt["estado"] != "autorizado"
                or int(receipt["empresa_id"]) != int(group["empresa_id"])
                or not (
                    snapshot_legacy
                    or (
                        snapshot_modern
                        and int(receipt["punto_venta_id"])
                        == int(group["punto_venta_id"])
                    )
                )
                or int(receipt["tipo_comprobante"]) != int(group["tipo_comprobante"])
                or int(receipt["numero"]) != int(group["numero_asignado"])
                or str(receipt["cae"]) != str(group["cae"])
                or Decimal(str(receipt["total"]))
                != Decimal(str(group["total_estimado"]))
            ):
                raise MigrationError("Un grupo v4 perdió su evidencia fiscal")
        elif any(
            group.get(field) is not None
            for field in ("comprobante_id", "numero_asignado", "cae")
        ):
            raise MigrationError("Un grupo v4 no autorizado conserva evidencia fiscal")

    for operation_id, operation in operations.items():
        company_id = int(operation["empresa_id"])
        if (
            company_id not in companies
            or operation["estado"] not in ESTADOS_OPERACION_TERMINALES
        ):
            raise MigrationError("Una operación v4 no es terminal o perdió su emisor")
        root_id = int(operation.get("operacion_raiz_id") or operation_id)
        root = operations.get(root_id)
        if (
            root is None
            or int(root["empresa_id"]) != company_id
            or (
                _is_v4_operation(operation)
                and (
                    not _is_v4_operation(root)
                    or root.get("lote_id") != operation.get("lote_id")
                )
            )
        ):
            raise MigrationError("Una operación v4 perdió su raíz")
        if root.get("operacion_raiz_id") not in {None, root_id}:
            raise MigrationError("La raíz v4 no es terminal en su linaje")
        if operation.get("lote_id") is not None:
            lote = lotes.get(int(operation["lote_id"]))
            if lote is None or int(lote["empresa_id"]) != company_id:
                raise MigrationError("Una operación v4 perdió su lote preservado")
        if not _is_v4_operation(operation):
            continue
        if (
            operation.get("lote_id") is None
            or operation.get("operacion_raiz_id") is None
        ):
            raise MigrationError("Una operación PF-13 no conserva lote y raíz")
        control = _v4_json_object(
            operation["control_duplicados_json"],
            label=f"operación {operation_id}",
        )
        selection = control.get("seleccion_original")
        if not isinstance(selection, list) or not selection:
            raise MigrationError("Una operación PF-13 no conserva selección original")
        selection_ids = [
            item.get("grupo_id") if isinstance(item, dict) else None
            for item in selection
        ]
        if (
            any(not isinstance(group_id, int) for group_id in selection_ids)
            or len(selection_ids) != len(set(selection_ids))
            or any(
                group_id not in groups
                or int(groups[group_id]["lote_id"]) != int(operation["lote_id"])
                or int(groups[group_id]["empresa_id"]) != company_id
                for group_id in selection_ids
            )
        ):
            raise MigrationError("La selección original PF-13 no es cerrada")
        generation_id = operation.get("duplicados_generacion_id")
        generation = generations.get(int(generation_id or 0))
        if (
            generation is None
            or int(generation["operacion_id"]) != operation_id
            or int(latest_generation_by_operation.get(operation_id, {}).get("id") or 0)
            != int(generation_id or 0)
            or control.get("duplicados_generacion_id") != generation_id
            or control.get("duplicados_generacion") != generation["generacion"]
            or control.get("formato_relacion") != generation["formato"]
        ):
            raise MigrationError("La operación PF-13 perdió su generación seleccionada")
        generation_control = _v4_json_object(
            generation["control_snapshot_json"],
            label=f"generación seleccionada {generation_id}",
        )
        if any(
            control.get(field) != generation_control.get(field)
            for field in ("datos_hash", "seleccion_hash", "seleccion_original")
        ):
            raise MigrationError("La operación PF-13 perdió su selección original")

    generation_blocks: dict[int, list[dict[str, Any]]] = {}
    for block in blocks.values():
        generation_blocks.setdefault(int(block["generacion_id"]), []).append(block)
    members_by_block: dict[int, list[dict[str, Any]]] = {}
    for member in rows["lotes_duplicados_coincidencias_miembros"]:
        block_id = int(member["bloque_id"])
        if block_id not in blocks:
            raise MigrationError("Un miembro PF-13 perdió su bloque")
        members_by_block.setdefault(block_id, []).append(member)

    generation_numbers: dict[int, list[int]] = {}
    for generation_id, generation in generations.items():
        operation = operations.get(int(generation["operacion_id"]))
        lote = lotes.get(int(generation["lote_id"]))
        if (
            operation is None
            or lote is None
            or not _is_v4_operation(operation)
            or int(generation["empresa_id"]) != int(operation["empresa_id"])
            or int(lote["empresa_id"]) != int(generation["empresa_id"])
            or generation["ambiente"] not in AMBIENTES_RECE
            or generation["formato"] != _fiscal_package_format().RELATION_FORMAT
        ):
            raise MigrationError("Una generación PF-13 perdió su procedencia")
        control_snapshot = _v4_json_object(
            generation["control_snapshot_json"],
            label=f"generación {generation_id}",
        )
        if (
            control_snapshot.get("formato_relacion")
            != _fiscal_package_format().RELATION_FORMAT
            or control_snapshot.get("evidencia_id") != generation["evidencia_id"]
            or not isinstance(control_snapshot.get("seleccion_original"), list)
            or not isinstance(control_snapshot.get("manifiesto"), dict)
        ):
            raise MigrationError("Una generación PF-13 no conserva cabecera válida")
        relation = _v4_generation_relation(
            generation,
            blocks=generation_blocks.get(generation_id, []),
            members_by_block=members_by_block,
            group_ids=group_ids,
            receipt_ids=receipt_ids,
        )
        manifest = control_snapshot["manifiesto"]
        relation_member_count = sum(len(block["miembros"]) for block in relation)
        if (
            manifest.get("bloques") != len(relation)
            or manifest.get("miembros") != relation_member_count
        ):
            raise MigrationError("El manifiesto compacto PF-13 no reconcilia")
        stable_control = {
            key: value
            for key, value in control_snapshot.items()
            if key
            not in {
                "estado",
                "detalle_url",
                "aceptacion_habilitada",
                "aceptacion_requerida",
            }
        }
        expected_snapshot_hash = _fiscal_package_format().canonical_sha256(
            {
                "dominio": _fiscal_package_format().RELATION_FORMAT,
                "control": stable_control,
                "relacion": relation,
            }
        )
        if expected_snapshot_hash != generation["snapshot_hash"]:
            raise MigrationError("El snapshot PF-13 perdió un bloque o testigo")
        generation_numbers.setdefault(int(generation["operacion_id"]), []).append(
            int(generation["generacion"])
        )
        accepted_at = generation.get("aceptada_at")
        acceptance_fields = (
            generation.get("aceptada_por_usuario_id"),
            generation.get("aceptada_por_nombre"),
            accepted_at,
        )
        origin_id = generation.get("aceptacion_origen_generacion_id")
        if accepted_at is None:
            if (
                any(value is not None for value in acceptance_fields)
                or origin_id is not None
            ):
                raise MigrationError("Una aceptación PF-13 pendiente es contradictoria")
        elif (
            generation.get("aceptacion_id") is None
            or any(value is None for value in acceptance_fields)
            or origin_id is None
            or int(generation["aceptada_por_usuario_id"]) not in users
        ):
            raise MigrationError("Una aceptación PF-13 perdió actor o tiempo")

    for operation_id, numbers in generation_numbers.items():
        ordered = sorted(numbers)
        if ordered != list(range(1, len(ordered) + 1)):
            raise MigrationError(
                f"Las generaciones de la operación {operation_id} no son completas"
            )

    for generation_id, generation in generations.items():
        origin_id = generation.get("aceptacion_origen_generacion_id")
        if origin_id is None or int(origin_id) == generation_id:
            continue
        seen = {generation_id}
        current = generation
        while int(current["aceptacion_origen_generacion_id"]) != int(current["id"]):
            candidate_id = int(current["aceptacion_origen_generacion_id"])
            if candidate_id in seen:
                raise MigrationError("La aceptación PF-13 contiene un ciclo")
            seen.add(candidate_id)
            origin = generations.get(candidate_id)
            if origin is None:
                raise MigrationError("La aceptación PF-13 perdió su origen")
            current_operation = operations[int(current["operacion_id"])]
            origin_operation = operations[int(origin["operacion_id"])]
            current_snapshot = _v4_json_object(
                current["control_snapshot_json"], label="aceptación heredada"
            )
            origin_snapshot = _v4_json_object(
                origin["control_snapshot_json"], label="origen de aceptación"
            )
            if (
                int(
                    current_operation.get("operacion_raiz_id")
                    or current_operation["id"]
                )
                != int(
                    origin_operation.get("operacion_raiz_id") or origin_operation["id"]
                )
                or any(
                    current[field] != origin[field]
                    for field in ("empresa_id", "lote_id", "ambiente", "evidencia_id")
                )
                or any(
                    current_snapshot.get(field) != origin_snapshot.get(field)
                    for field in ("datos_hash", "seleccion_hash", "seleccion_original")
                )
                or any(
                    current.get(field) != origin.get(field)
                    for field in (
                        "aceptacion_id",
                        "aceptada_por_usuario_id",
                        "aceptada_por_nombre",
                        "aceptada_at",
                    )
                )
            ):
                raise MigrationError("La aceptación PF-13 heredada no es compatible")
            current = origin

    for group in groups.values():
        reservation = group.get("duplicados_reserva_operacion_id")
        if reservation is not None:
            operation = operations.get(int(reservation))
            if (
                operation is None
                or int(operation["empresa_id"]) != int(group["empresa_id"])
                or int(operation.get("lote_id") or 0) != int(group["lote_id"])
            ):
                raise MigrationError("Una reserva PF-13 perdió su operación")

    _validate_v4_attempt_fiscal_evidence(rows)
    for receipt in receipts.values():
        if receipt["estado"] == "autorizado" and not (
            _v4_has_minimum_authorization_evidence(
                receipt_id=receipt.get("id"),
                number=receipt.get("numero"),
                cae=receipt.get("cae"),
                cae_expiration=receipt.get("cae_vencimiento"),
            )
        ):
            raise MigrationError(
                "Comprobante autorizado v4 sin evidencia fiscal completa"
            )
    _validate_v4_pf19c_history(rows)

    expected_closure = _v4_closure_payload(
        rows=rows,
        normalization=normalization,
    )
    if closure != expected_closure:
        raise MigrationError("La clausura declarada del paquete v4 no verifica")


def _canonical_v4_barrier_rows(
    rows: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for table_name in _fiscal_package_format().INCLUDED_TABLES:
        table = _historical_v4_table(table_name)
        normalized_rows = []
        for row in rows[table_name]:
            normalized = {}
            for column_name in _fiscal_package_format().V4_COLUMNS[table_name]:
                value = row[column_name]
                column_type = table.c[column_name].type
                if value is not None and isinstance(column_type, Boolean):
                    value = bool(value)
                elif value is not None and isinstance(column_type, DateTime):
                    parsed = (
                        value
                        if isinstance(value, datetime)
                        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                    )
                    if column_type.timezone:
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        else:
                            parsed = parsed.astimezone(timezone.utc)
                    value = parsed.isoformat()
                elif value is not None and isinstance(column_type, Date):
                    value = (
                        value
                        if isinstance(value, date)
                        else date.fromisoformat(str(value))
                    ).isoformat()
                elif value is not None and isinstance(
                    column_type, (ExactAmount, ExactDecimal, ExactInteger)
                ):
                    value = (
                        str(value)
                        if isinstance(column_type, ExactInteger)
                        else encode_decimal(Decimal(str(value)))
                    )
                elif value is not None and isinstance(column_type, Numeric):
                    value = format(Decimal(str(value)).normalize(), "f")
                elif value is not None and isinstance(column_type, JSON):
                    value = json.loads(value) if isinstance(value, str) else value
                normalized[column_name] = value
            normalized_rows.append(normalized)
        primary_key = _fiscal_package_format().PRIMARY_KEYS[table_name]
        normalized_rows.sort(key=lambda item: tuple(item[name] for name in primary_key))
        result[table_name] = normalized_rows
    return result


def build_v4_idempotency_barrier(
    *,
    source_barrier: dict[str, Any],
    normalization: dict[str, Any],
    closure: dict[str, Any],
    rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Atestigua todos los campos decisorios y relaciones del paquete v4."""
    material = {
        "version": 2,
        "algorithm": _fiscal_package_format().BARRIER_ALGORITHM,
        "source_barrier": source_barrier,
        "normalization": normalization,
        "closure": closure,
        "tables": _canonical_v4_barrier_rows(rows),
    }
    return {
        "version": 2,
        "algorithm": _fiscal_package_format().BARRIER_ALGORITHM,
        "rows": sum(len(table_rows) for table_rows in rows.values()),
        "sha256": _fiscal_package_format().canonical_sha256(material),
    }


@_format_context
def run_preflight(
    source_db: Path,
    certs_dir: Path,
    backend_dir: Path | None = None,
) -> PreflightResult:
    """Diagnostica si la fuente es apta; export vuelve a validar en snapshot."""
    repo_head = get_repo_alembic_head(backend_dir)
    if repo_head not in {_fiscal_package_format().ALEMBIC_HEAD, A01_HEAD}:
        raise MigrationError("El preflight v4 exige el head PF-13 exacto del contrato")
    db_path, certs_base = resolve_source_paths(source_db, certs_dir)
    with connect_sqlite_readonly(db_path) as conn:
        return run_preflight_on_connection(
            conn,
            db_path=db_path,
            certs_base=certs_base,
            repo_head=_fiscal_package_format().ALEMBIC_HEAD,
        )


def resolve_source_paths(source_db: Path, certs_dir: Path) -> tuple[Path, Path]:
    """Resuelve y valida las rutas privadas de la fuente local."""
    db_path = source_db.resolve()
    certs_base = certs_dir.resolve()
    if not db_path.is_file() or db_path.stat().st_size == 0:
        raise MigrationError(f"La base SQLite fuente no existe o está vacía: {db_path}")
    if not certs_base.is_dir():
        raise MigrationError(f"No existe el directorio de certificados: {certs_base}")
    return db_path, certs_base


@_format_context
def run_preflight_on_connection(
    conn: sqlite3.Connection,
    *,
    db_path: Path,
    certs_base: Path,
    repo_head: str,
) -> PreflightResult:
    """Ejecuta todas las barreras SQLite usando una conexión ya inmovilizada."""
    validate_table_partition()
    tables = get_sqlite_tables(conn)
    expected_tables = {
        *_fiscal_package_format().INCLUDED_TABLES,
        *_fiscal_package_format().REGENERATED_TABLES,
        *_fiscal_package_format().EXCLUDED_TABLES,
        "alembic_version",
    }
    if tables != expected_tables:
        missing = sorted(expected_tables - tables)
        unexpected = sorted(tables - expected_tables)
        detail = []
        if missing:
            detail.append("faltantes=" + ",".join(missing))
        if unexpected:
            detail.append("no clasificadas=" + ",".join(unexpected))
        raise MigrationError(
            "La base fuente no coincide con la partición exacta de tablas: "
            + "; ".join(detail)
        )

    quick_check = [str(row[0]) for row in conn.execute("PRAGMA quick_check")]
    if quick_check != ["ok"]:
        raise MigrationError("PRAGMA quick_check detectó corrupción en la fuente")
    foreign_key_errors = list(conn.execute("PRAGMA foreign_key_check"))
    if foreign_key_errors:
        raise MigrationError(
            "PRAGMA foreign_key_check detectó referencias inválidas en la fuente"
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

    validate_rece_ledger_sqlite(conn)
    validate_user_accesses_sqlite(conn)
    validate_v4_sqlite_schema(conn)
    validate_v4_source_coordinators(conn)
    capture = capture_v4_rows(conn)
    included_counts = capture.included_counts
    excluded_counts = {
        table_name: capture.source_counts[table_name]
        for table_name in _fiscal_package_format().EXCLUDED_TABLES
    }
    safe_omitted = capture.safe_omitted
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
        repo_head=_fiscal_package_format().ALEMBIC_HEAD,
        included_counts=included_counts,
        excluded_counts=excluded_counts,
        active_certificates=len(active_certs),
        safe_omitted=safe_omitted,
    )


def _staging_is_reparse(info: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def capture_staging_directory_ownership(
    staging_dir: Path,
    output_base: Path,
) -> StagingDirectoryOwnership:
    """Captura la identidad del directorio recién creado y verifica su padre."""
    parent = output_base.resolve()
    if staging_dir.parent.resolve() != parent or staging_dir.is_symlink():
        raise MigrationError("El staging de exportación no pertenece al destino")
    try:
        info = os.stat(staging_dir, follow_symlinks=False)
    except OSError as exc:
        raise MigrationError("No se pudo acreditar el staging de exportación") from exc
    if not stat.S_ISDIR(info.st_mode) or _staging_is_reparse(info):
        raise MigrationError("El staging de exportación no es un directorio real")
    return StagingDirectoryOwnership(
        parent=parent,
        device=int(info.st_dev),
        inode=int(info.st_ino),
    )


def verify_owned_staging_directory(
    staging_dir: Path,
    ownership: StagingDirectoryOwnership,
) -> None:
    """Falla cerrado si el staging desapareció, cambió o dejó de ser propio."""
    if staging_dir.parent.resolve() != ownership.parent or staging_dir.is_symlink():
        raise MigrationError("El staging propio cambió de ubicación o tipo")
    try:
        info = os.stat(staging_dir, follow_symlinks=False)
    except OSError as exc:
        raise MigrationError("El staging propio ya no está disponible") from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or _staging_is_reparse(info)
        or (int(info.st_dev), int(info.st_ino)) != (ownership.device, ownership.inode)
    ):
        raise MigrationError("La identidad del staging propio cambió")


def publish_staging_directory(
    staging_dir: Path,
    package_dir: Path,
    ownership: StagingDirectoryOwnership,
    *,
    platform_name: str | None = None,
    sleep: Any = time.sleep,
) -> Path:
    """Publica mediante el mismo rename, con tolerancia acotada a WinError 5."""
    platform = os.name if platform_name is None else platform_name
    if package_dir.parent.resolve() != ownership.parent:
        raise MigrationError("El paquete destino no comparte el padre del staging")
    delays = (0.05, 0.10, 0.20, 0.40)
    attempts = 5 if platform == "nt" else 1
    for attempt in range(attempts):
        verify_owned_staging_directory(staging_dir, ownership)
        if os.path.lexists(package_dir):
            raise MigrationError(f"Ya existe el paquete destino: {package_dir}")
        try:
            staging_dir.rename(package_dir)
            return package_dir
        except PermissionError as exc:
            if platform != "nt" or getattr(exc, "winerror", None) != 5:
                raise
            if attempt == attempts - 1:
                raise MigrationError(
                    "No se pudo publicar el paquete de forma atómica tras "
                    "5 intentos en Windows"
                ) from exc
            if os.path.lexists(package_dir):
                raise MigrationError(f"Ya existe el paquete destino: {package_dir}")
            verify_owned_staging_directory(staging_dir, ownership)
            sleep(delays[attempt])
    raise AssertionError("Bucle de publicación atómica incompleto")


def cleanup_owned_staging_directory(
    staging_dir: Path,
    ownership: StagingDirectoryOwnership,
) -> None:
    """Elimina sólo el staging que conserva la identidad capturada."""
    if not os.path.lexists(staging_dir):
        return
    verify_owned_staging_directory(staging_dir, ownership)
    shutil.rmtree(staging_dir)


@_format_context
def export_package(
    source_db: Path,
    certs_dir: Path,
    output_root: Path,
    target_key_password: str,
    source_key_password: str | None = None,
    backend_dir: Path | None = None,
    source_quiesced: bool = False,
) -> Path:
    """Genera un paquete privado de migración en `.tmp/vps-migration`."""
    if not target_key_password:
        raise MigrationError("ARCA_PRIVATE_KEY_PASSWORD destino es obligatorio")
    if not source_quiesced:
        raise MigrationError(
            "Confirmá explícitamente que backend y worker están detenidos "
            "con --source-quiesced antes de exportar."
        )

    repo_head = get_repo_alembic_head(backend_dir)
    if repo_head not in {_fiscal_package_format().ALEMBIC_HEAD, A01_HEAD}:
        raise MigrationError(
            "La exportación v4 PF-13 exige el head exacto del contrato"
        )
    db_path, certs_base = resolve_source_paths(source_db, certs_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = output_root.resolve()
    output_base.mkdir(parents=True, exist_ok=True)
    package_dir = output_base / timestamp
    if os.path.lexists(package_dir):
        raise MigrationError(f"Ya existe el paquete destino: {package_dir}")
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{timestamp}.",
            suffix=".tmp",
            dir=output_base,
        )
    )
    staging_ownership = capture_staging_directory_ownership(staging_dir, output_base)
    try:
        os.chmod(staging_dir, 0o700)
        data_files: dict[str, dict[str, Any]] = {}
        cert_files: dict[str, dict[str, Any]] = {}
        normalizations: dict[str, dict[str, Any]] = {}
        package_rows: dict[str, list[dict[str, Any]]] = {}
        capture: V4Capture | None = None
        conn = connect_sqlite_export_snapshot(db_path)
        try:
            data_version_inicio = int(conn.execute("PRAGMA data_version").fetchone()[0])
            preflight = run_preflight_on_connection(
                conn,
                db_path=db_path,
                certs_base=certs_base,
                repo_head=_fiscal_package_format().ALEMBIC_HEAD,
            )
            capture = capture_v4_rows(conn)
            data_dir = staging_dir / "data"
            package_certs_dir = staging_dir / "certs"
            data_dir.mkdir(parents=True, mode=0o700)
            package_certs_dir.mkdir(parents=True, mode=0o700)

            active_certs = list_active_certificates(conn)
            active_by_id = {int(row["id"]): row for row in active_certs}
            copied_names = export_active_certificate_files(
                active_certs=active_certs,
                certs_dir=preflight.certs_dir,
                package_certs_dir=package_certs_dir,
                target_key_password=target_key_password,
                source_key_password=source_key_password,
            )

            normalizations[
                _fiscal_package_format().OPERATION_LOTE_NORMALIZATION_KEY
            ] = capture.normalization
            for table_name in _fiscal_package_format().INCLUDED_TABLES:
                rows = [dict(row) for row in capture.rows[table_name]]
                if table_name == "certificados":
                    rows = normalize_certificate_rows(
                        rows,
                        active_by_id,
                        copied_names,
                    )
                package_rows[table_name] = rows
                file_path = data_dir / f"{table_name}.jsonl"
                write_jsonl(file_path, rows)
                data_files[table_name] = {
                    "path": str(file_path.relative_to(staging_dir)).replace("\\", "/"),
                    "sha256": sha256_file(file_path),
                    "rows": len(rows),
                    "bytes": file_path.stat().st_size,
                }

            data_version_fin = int(conn.execute("PRAGMA data_version").fetchone()[0])
            if data_version_fin != data_version_inicio:
                raise MigrationError(
                    "La fuente cambió durante la instantánea de exportación"
                )
        finally:
            conn.rollback()
            conn.close()

        for path in sorted(package_certs_dir.iterdir()):
            cert_files[path.name] = {
                "path": str(path.relative_to(staging_dir)).replace("\\", "/"),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }

        source_barrier = {
            "source_quiesced": True,
            "sqlite_transaction": "BEGIN IMMEDIATE",
            "data_version": data_version_inicio,
        }
        if capture is None:
            raise MigrationError("La captura v4 no llegó a completarse")
        idempotency_barrier = build_v4_idempotency_barrier(
            source_barrier=source_barrier,
            normalization=capture.normalization,
            closure=capture.closure,
            rows=package_rows,
        )
        env_template_path = staging_dir / ENV_TEMPLATE_FILENAME
        write_env_template(env_template_path)
        env_template = {
            "path": ENV_TEMPLATE_FILENAME,
            "sha256": sha256_file(env_template_path),
            "bytes": env_template_path.stat().st_size,
        }
        manifest = {
            "package_version": _fiscal_package_format().PACKAGE_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scope": SCOPE,
            "alembic_version": preflight.alembic_version,
            "complete_tables": list(_fiscal_package_format().COMPLETE_TABLES),
            "filtered_tables": list(_fiscal_package_format().FILTERED_TABLES),
            "regenerated_tables": list(_fiscal_package_format().REGENERATED_TABLES),
            "included_tables": list(_fiscal_package_format().INCLUDED_TABLES),
            "excluded_tables": list(_fiscal_package_format().EXCLUDED_TABLES),
            "target_empty_tables": list(_fiscal_package_format().TARGET_EMPTY_TABLES),
            "source_counts": capture.source_counts,
            "included_counts": capture.included_counts,
            "omitted_counts": capture.omitted_counts,
            "active_certificates": preflight.active_certificates,
            "safe_omitted": preflight.safe_omitted,
            "normalizations": normalizations,
            "closure": capture.closure,
            "source_barrier": source_barrier,
            "idempotency_barrier": idempotency_barrier,
            "data_files": data_files,
            "certificate_files": cert_files,
            "env_template": env_template,
            "required_env_keys": REQUIRED_ENV_KEYS,
            "notes": list(_fiscal_package_format().PACKAGE_NOTES),
        }
        write_json(staging_dir / "manifest.json", manifest)
        publish_staging_directory(staging_dir, package_dir, staging_ownership)
    except BaseException as publication_error:
        try:
            cleanup_owned_staging_directory(staging_dir, staging_ownership)
        except BaseException as cleanup_error:
            if isinstance(cleanup_error, (KeyboardInterrupt, SystemExit)):
                cleanup_error.add_note(
                    "La limpieza del staging propio quedó incompleta después "
                    "de un fallo de publicación"
                )
                raise cleanup_error from publication_error
            if isinstance(publication_error, (KeyboardInterrupt, SystemExit)):
                publication_error.add_note(
                    "La publicación fue interrumpida y la limpieza del staging "
                    "propio quedó incompleta"
                )
                raise publication_error from cleanup_error
            failures = BaseExceptionGroup(
                "Fallaron la publicación y la limpieza del staging propio",
                [publication_error, cleanup_error],
            )
            raise MigrationError(
                "La publicación del paquete falló y la limpieza del staging "
                "propio quedó incompleta"
            ) from failures
        raise
    return package_dir


@_format_context
def import_package(
    package_dir: Path,
    database_url: str,
    production_env: Path,
    target_certs_dir: Path | None = None,
) -> None:
    """Restaura un paquete privado sobre una PostgreSQL limpia."""
    package = package_dir.resolve()
    manifest = load_and_verify_manifest(package)
    contract = select_import_contract(manifest)
    env_values = parse_env_file(production_env)
    target_password = env_values.get("ARCA_PRIVATE_KEY_PASSWORD") or os.getenv(
        "ARCA_PRIVATE_KEY_PASSWORD"
    )
    if not target_password:
        raise MigrationError(
            "El importador requiere ARCA_PRIVATE_KEY_PASSWORD en .env.production"
        )
    certs_dir = (target_certs_dir or Path(env_values.get("CERTS_PATH", ""))).resolve()
    if not str(certs_dir):
        raise MigrationError(
            "Indicá CERTS_PATH en .env.production o --target-certs-dir"
        )

    package_rows = {
        table_name: read_package_rows(package, manifest, table_name)
        for table_name in contract.included_tables
    }
    verify_package_certificates(
        package,
        manifest,
        target_password,
        package_rows,
    )
    certificate_plan = plan_certificate_restore(package, manifest, certs_dir)
    certificate_journal = CertificateRestoreJournal(created=[])
    engine = create_postgres_engine(database_url)
    transaction_body_completed = False
    try:
        with engine.begin() as conn:
            lock_target_tables_for_import(conn, contract)
            ensure_target_database_ready(conn, manifest, contract)
            materialize_certificate_restore(
                certificate_plan,
                certificate_journal,
            )
            clear_seeded_included_tables(conn, contract)
            insert_order = (
                contract.insert_order
                if contract.package_version == _fiscal_package_format().PACKAGE_VERSION
                else contract.included_tables
            )
            for table_name in insert_order:
                rows = package_rows[table_name]
                deferred = (
                    contract.deferred_columns.get(table_name, ())
                    if contract.package_version
                    == _fiscal_package_format().PACKAGE_VERSION
                    else ()
                )
                if deferred:
                    rows = [
                        {**row, **{column_name: None for column_name in deferred}}
                        for row in rows
                    ]
                insert_rows(conn, table_name, rows)
            if contract.package_version == _fiscal_package_format().PACKAGE_VERSION:
                restore_deferred_columns(conn, package_rows, contract)
            regenerate_v3_coordinators(conn)
            validate_imported_database(conn, manifest, package_rows, contract)
            reset_postgres_sequences(conn, contract)
            verify_postgres_sequences(conn, contract)
            verify_restored_certificate_files(
                certs_dir,
                manifest,
                target_password,
                package_rows,
            )
            transaction_body_completed = True
    except BaseException as exc:
        if not transaction_body_completed:
            cleanup_complete = cleanup_certificate_restore(certificate_journal)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                if not cleanup_complete:
                    exc.add_note("limpieza_certificados_incompleta")
                raise
            if not cleanup_complete:
                raise MigrationError(
                    "La importación falló y la limpieza de certificados "
                    "quedó incompleta"
                ) from exc
            if isinstance(exc, MigrationError):
                raise
            raise MigrationError(
                "La importación falló; la transacción fue revertida y los "
                "certificados propios fueron limpiados"
            ) from exc
        if isinstance(exc, Exception):
            raise MigrationError(
                "El commit del import quedó en estado incierto; no reimporte "
                "hasta ejecutar validate sobre la base y los certificados"
            ) from exc
        raise
    finally:
        engine.dispose()


@_format_context
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
    certs_dir = (target_certs_dir or Path(env_values.get("CERTS_PATH", ""))).resolve()
    if not str(certs_dir):
        raise MigrationError(
            "Indicá CERTS_PATH en .env.production o --target-certs-dir"
        )

    try:
        _validate_import_runtime(
            package=package,
            manifest=manifest,
            database_url=database_url,
            certs_dir=certs_dir,
            target_password=target_password,
            api_url=api_url,
            login_email=login_email,
        )
    except MigrationError:
        raise
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        raise MigrationError(
            "La validación del import no pudo completarse de forma controlada"
        ) from exc


def _validate_import_runtime(
    *,
    package: Path,
    manifest: dict[str, Any],
    database_url: str,
    certs_dir: Path,
    target_password: str,
    api_url: str | None,
    login_email: str | None,
) -> None:
    """Ejecuta la validación bajo lock y clasifica un commit no confirmado."""
    contract = select_import_contract(manifest)
    retry_safe = False
    engine = create_postgres_engine(database_url)
    try:
        with engine.begin() as conn:
            lock_target_tables_for_import(conn, contract)
            package_rows = {
                table_name: read_package_rows(package, manifest, table_name)
                for table_name in contract.included_tables
            }
            try:
                validate_imported_database(conn, manifest, package_rows, contract)
                verify_postgres_sequences(conn, contract)
            except MigrationError:
                try:
                    ensure_target_database_ready(conn, manifest, contract)
                except MigrationError as dirty_error:
                    raise MigrationError(
                        "El import quedó parcial o corrupto; requiere intervención "
                        "antes de reintentar"
                    ) from dirty_error
                retry_safe = True
            verify_restored_certificate_files(
                certs_dir,
                manifest,
                target_password,
                package_rows,
            )
            if retry_safe:
                raise MigrationError(
                    "El import no fue confirmado: el destino está limpio y los "
                    "certificados son idénticos; el reintento es seguro"
                )
    finally:
        engine.dispose()
    if api_url:
        validate_api_health(api_url)
        if login_email:
            validate_api_login(api_url, login_email)


def connect_sqlite_readonly(db_path: Path) -> sqlite3.Connection:
    """Abre una conexión SQLite de solo lectura."""
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    _install_sqlite_functions(conn, None)
    conn.row_factory = sqlite3.Row
    return conn


def connect_sqlite_export_snapshot(db_path: Path) -> sqlite3.Connection:
    """Abre una instantánea que bloquea escritores hasta terminar el paquete."""
    uri = f"file:{db_path.as_posix()}?mode=rw"
    conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=5)
    try:
        _install_sqlite_functions(conn, None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.Error as exc:
        conn.close()
        raise MigrationError(
            "No se pudo inmovilizar la SQLite fuente para exportarla"
        ) from exc
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


def validate_table_partition() -> None:
    """Exige una clasificación exhaustiva y sin solapamientos del modelo."""
    included = set(_fiscal_package_format().INCLUDED_TABLES)
    regenerated = set(_fiscal_package_format().REGENERATED_TABLES)
    excluded = set(_fiscal_package_format().EXCLUDED_TABLES)
    overlap = sorted(
        (included & regenerated) | (included & excluded) | (regenerated & excluded)
    )
    if overlap:
        raise MigrationError(
            "Hay tablas simultáneamente incluidas y excluidas: " + ", ".join(overlap)
        )
    modeled = set(Base.metadata.tables)
    classified = included | regenerated | excluded
    if modeled != classified:
        missing = sorted(modeled - classified)
        unknown = sorted(classified - modeled)
        detail = []
        if missing:
            detail.append("sin clasificar=" + ",".join(missing))
        if unknown:
            detail.append("fuera del modelo=" + ",".join(unknown))
        raise MigrationError(
            "La partición de tablas VPS no coincide con el modelo: " + "; ".join(detail)
        )


def _json_object_sqlite(value: Any) -> dict[str, Any] | None:
    """Decodifica un objeto JSON SQLite sin aceptar escalares ni listas."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _json_list_sqlite(value: Any) -> list[Any] | None:
    """Decodifica una lista JSON SQLite sin aceptar objetos ni escalares."""
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, list) else None


def _is_json_null_sqlite(value: Any) -> bool:
    """Distingue el `NULL` JSON durable del texto no estructurado legacy."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    try:
        return json.loads(value) is None
    except (TypeError, ValueError):
        return False


def _is_exact_global_10005_errors(value: Any) -> bool:
    """Exige la evidencia sanitaria PF-19C sin coerciones JSON ambiguas."""
    errors = _json_list_sqlite(value)
    if errors is None or len(errors) != 1 or not isinstance(errors[0], dict):
        return False
    error = errors[0]
    return bool(
        set(error) == {"codigo", "alcance", "mensaje"}
        and isinstance(error["codigo"], int)
        and not isinstance(error["codigo"], bool)
        and error["codigo"] == 10005
        and error["alcance"] == "global"
        and error["mensaje"] == ARCA_RECHAZO_GLOBAL_MENSAJE
    )


def _response_is_exact_global_10005(
    response: Any,
) -> bool:
    """Comprueba que un DTO individual conserva el rechazo global canónico."""
    return bool(
        response.exito is False
        and response.requiere_reconciliacion is False
        and response.comprobante_id is None
        and response.cae is None
        and response.cae_vencimiento is None
        and response.mensaje == ARCA_RECHAZO_GLOBAL_INDIVIDUAL_MENSAJE
        and tuple(response.errores) == tuple(ARCA_RECHAZO_GLOBAL_INDIVIDUAL_ERRORES)
        and response.categoria_error == ARCA_RECHAZO_GLOBAL_CATEGORIA
        and len(response.errores_arca) == 1
        and response.errores_arca[0].codigo == 10005
        and response.errores_arca[0].alcance == "global"
        and response.errores_arca[0].mensaje == ARCA_RECHAZO_GLOBAL_MENSAJE
    )


def _strict_positive_id_list(value: Any) -> tuple[int, ...] | None:
    """Acepta una lista ordenada de IDs positivos, únicos y sin coerciones."""
    if not isinstance(value, list):
        return None
    if any(
        not isinstance(item, int) or isinstance(item, bool) or item <= 0
        for item in value
    ):
        return None
    ids = tuple(value)
    if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
        return None
    return ids


def _batch_global_rejection_context(
    response: dict[str, Any],
    *,
    operation_type: str,
    operation_id: int,
) -> tuple[frozenset[int], frozenset[int]] | None:
    """Extrae únicamente el rechazo batch PF-19C canónico y autocontenido."""
    if (
        not isinstance(operation_id, int)
        or isinstance(operation_id, bool)
        or operation_id <= 0
    ):
        return None
    expected_keys = {"lote", "mensaje", "errores_arca"}
    if operation_type == "procesar_lote":
        expected_keys.add("en_progreso")
    elif operation_type != "reintentar_fallidos_lote":
        return None
    if set(response) != expected_keys:
        return None
    if (
        response.get("mensaje") != ARCA_RECHAZO_GLOBAL_LOTE_MENSAJE
        or not _is_exact_global_10005_errors(response.get("errores_arca"))
        or (
            operation_type == "procesar_lote"
            and response.get("en_progreso") is not False
        )
    ):
        return None
    lote = response.get("lote")
    if not isinstance(lote, dict):
        return None
    metadata = lote.get("metadata_json")
    if not isinstance(metadata, dict):
        return None
    marker = metadata.get("pf19c_rechazo_global")
    if not isinstance(marker, dict) or set(marker) != {
        "operacion_id",
        "categoria",
        "grupos_rechazo_ids",
        "grupos_no_enviados_ids",
        "errores_arca",
    }:
        return None
    rejection_ids = _strict_positive_id_list(marker.get("grupos_rechazo_ids"))
    not_sent_ids = _strict_positive_id_list(marker.get("grupos_no_enviados_ids"))
    if (
        marker.get("operacion_id") != operation_id
        or isinstance(marker.get("operacion_id"), bool)
        or marker.get("categoria") != ARCA_RECHAZO_GLOBAL_CATEGORIA
        or not _is_exact_global_10005_errors(marker.get("errores_arca"))
        or not rejection_ids
        or not_sent_ids is None
        or set(rejection_ids) & set(not_sent_ids)
    ):
        return None
    return frozenset(rejection_ids), frozenset(not_sent_ids)


def terminal_operation_response_is_valid(row: dict[str, Any]) -> bool:
    """Valida el DTO exacto que cada endpoint puede reproducir sin mutar."""
    response = _json_object_sqlite(row.get("response_json"))
    if response is None:
        return False
    tipo = str(row.get("tipo_operacion") or "")
    estado = str(row.get("estado") or "")
    lote_id = row.get("lote_id")
    if tipo == "emitir_comprobante":
        if lote_id is not None:
            return False
        try:
            parsed = EmitirComprobanteResponse.model_validate(response)
        except (TypeError, ValidationError, ValueError):
            return False
        if parsed.requiere_reconciliacion:
            return False
        if parsed.exito:
            return bool(
                estado == "finalizado"
                and parsed.comprobante_id
                and parsed.comprobante_id > 0
                and parsed.numero > 0
                and parsed.cae
                and parsed.cae_vencimiento
            )
        return bool(
            estado in (ESTADOS_OPERACION_TERMINALES - {"finalizado"})
            and parsed.comprobante_id is None
            and parsed.cae is None
            and parsed.cae_vencimiento is None
            and parsed.categoria_error
            not in {"duplicado_logico", "idempotencia_en_proceso"}
        )
    if tipo not in {"procesar_lote", "reintentar_fallidos_lote"}:
        return False
    if (
        lote_id is None
        or row.get("lote_encontrado") is None
        or int(row.get("lote_empresa_id") or 0) != int(row.get("empresa_id") or 0)
        or row.get("lote_estado") not in ESTADOS_LOTE_SEGUROS_OMITIBLES
    ):
        return False
    if "categoria_error" in response:
        categoria = response.get("categoria_error")
        mensaje = response.get("mensaje")
        errores = response.get("errores")
        status_code = response.get("status_code")
        return bool(
            estado in (ESTADOS_OPERACION_TERMINALES - {"finalizado"})
            and estado != "rechazado_arca"
            and isinstance(categoria, str)
            and categoria.strip()
            and categoria
            not in {
                "duplicado_logico_lote",
                "idempotencia_en_proceso",
                "post_arca_persistencia",
            }
            and (mensaje is None or isinstance(mensaje, str))
            and (
                errores is None
                or (
                    isinstance(errores, list)
                    and all(isinstance(item, str) for item in errores)
                )
            )
            and (
                status_code is None
                or (
                    isinstance(status_code, int)
                    and not isinstance(status_code, bool)
                    and 400 <= status_code <= 599
                )
            )
        )
    try:
        if tipo == "procesar_lote":
            parsed_lote = LoteProcesamientoResponse.model_validate(response)
            if parsed_lote.en_progreso:
                return False
        else:
            parsed_lote = LoteAccionResponse.model_validate(response)
    except (TypeError, ValidationError, ValueError):
        return False
    rechazo_global = _batch_global_rejection_context(
        response,
        operation_type=tipo,
        operation_id=int(row["id"]),
    )
    if estado == "rechazado_arca":
        return bool(
            rechazo_global is not None
            and int(parsed_lote.lote.id) == int(lote_id)
            and int(parsed_lote.lote.empresa_id) == int(row.get("empresa_id") or 0)
            and parsed_lote.lote.estado in ESTADOS_LOTE_SEGUROS_OMITIBLES
        )
    if rechazo_global is not None or parsed_lote.errores_arca:
        return False
    return bool(
        estado in {"finalizado", "fallido"}
        and int(parsed_lote.lote.id) == int(lote_id)
        and int(parsed_lote.lote.empresa_id) == int(row.get("empresa_id") or 0)
        and parsed_lote.lote.estado in ESTADOS_LOTE_SEGUROS_OMITIBLES
    )


def terminal_individual_success_matches_db(
    conn: sqlite3.Connection,
    row: dict[str, Any],
) -> bool:
    """Coteja un replay individual exitoso con el comprobante local incluido."""
    if row.get("tipo_operacion") != "emitir_comprobante":
        return True
    response = _json_object_sqlite(row.get("response_json"))
    if response is None:
        return False
    try:
        parsed = EmitirComprobanteResponse.model_validate(response)
    except (TypeError, ValidationError, ValueError):
        return False
    if not parsed.exito:
        return True
    comprobante = conn.execute(
        """
        SELECT c.id, c.empresa_id, c.punto_venta_id, c.tipo_comprobante, c.numero,
               c.fecha_emision, c.total, c.cae, c.cae_vencimiento,
               c.estado
        FROM comprobantes c
        WHERE c.id = ?
        """,
        (int(parsed.comprobante_id or 0),),
    ).fetchone()
    if comprobante is None:
        return False
    try:
        fecha_emision = date.fromisoformat(str(comprobante["fecha_emision"])[:10])
        cae_vencimiento = date.fromisoformat(str(comprobante["cae_vencimiento"])[:10])
    except (KeyError, TypeError, ValueError):
        return False
    return bool(
        int(comprobante["empresa_id"]) == int(row["empresa_id"])
        and comprobante["estado"] == "autorizado"
        and int(comprobante["tipo_comprobante"]) == parsed.tipo_comprobante
        and int(comprobante["numero"]) == parsed.numero
        and fecha_emision == parsed.fecha
        and Decimal(str(comprobante["total"])) == parsed.total
        and comprobante["cae"] == parsed.cae
        and cae_vencimiento == parsed.cae_vencimiento
    )


def terminal_batch_response_matches_db(
    conn: sqlite3.Connection,
    row: dict[str, Any],
) -> bool:
    """Coteja la identidad durable sin igualar campos mutables del lote."""
    if row.get("tipo_operacion") not in {
        "procesar_lote",
        "reintentar_fallidos_lote",
    }:
        return True
    response = _json_object_sqlite(row.get("response_json"))
    if response is None:
        return False
    if "categoria_error" in response:
        return bool(
            row.get("estado") != "rechazado_arca"
            and row.get("lote_encontrado") is not None
        )
    try:
        if row["tipo_operacion"] == "procesar_lote":
            parsed_response = LoteProcesamientoResponse.model_validate(response)
        else:
            parsed_response = LoteAccionResponse.model_validate(response)
    except (TypeError, ValidationError, ValueError):
        return False
    parsed_lote = parsed_response.lote
    rechazo_global = _batch_global_rejection_context(
        response,
        operation_type=str(row["tipo_operacion"]),
        operation_id=int(row["id"]),
    )
    if row.get("estado") == "rechazado_arca":
        if rechazo_global is None:
            return False
    elif rechazo_global is not None or parsed_response.errores_arca:
        return False
    return bool(
        row.get("lote_encontrado") is not None
        and int(parsed_lote.id) == int(row.get("lote_id") or 0)
        and int(parsed_lote.empresa_id) == int(row.get("empresa_id") or 0)
        and parsed_lote.estado in ESTADOS_LOTE_SEGUROS_OMITIBLES
        and row.get("lote_estado") in ESTADOS_LOTE_SEGUROS_OMITIBLES
    )


def individual_association_matches_response(
    conn: sqlite3.Connection,
    operation: dict[str, Any],
    associations: list[dict[str, Any]],
) -> bool:
    """Valida la cardinalidad e identidad histórica de una emisión moderna."""
    if operation.get("tipo_operacion") != "emitir_comprobante":
        return True
    if operation.get("rece_snapshot_hash") is None:
        return not associations
    if len(associations) != 1:
        return False
    response = _json_object_sqlite(operation.get("response_json"))
    if response is None:
        return False
    try:
        parsed = EmitirComprobanteResponse.model_validate(response)
        association = associations[0]
        if (
            int(association["empresa_id"]) != int(operation["empresa_id"])
            or int(association["punto_venta_numero"]) != parsed.punto_venta
        ):
            return False
        if not parsed.exito:
            return True
        receipt = conn.execute(
            "SELECT punto_venta_id FROM comprobantes WHERE id = ?",
            (int(parsed.comprobante_id or 0),),
        ).fetchone()
        return bool(
            receipt is not None
            and int(receipt["punto_venta_id"]) == int(association["punto_venta_id"])
        )
    except (KeyError, TypeError, ValidationError, ValueError):
        return False


def individual_operation_result_matches_attempts(
    operation: dict[str, Any],
    attempts: list[dict[str, Any]],
    guards: list[dict[str, Any]],
    associations: list[dict[str, Any]],
) -> bool:
    """Cruza el replay terminal individual con toda su evidencia de intentos."""
    if operation.get("tipo_operacion") != "emitir_comprobante":
        return True
    response = _json_object_sqlite(operation.get("response_json"))
    if response is None:
        return False
    try:
        parsed = EmitirComprobanteResponse.model_validate(response)
    except (TypeError, ValidationError, ValueError):
        return False

    authorized = [item for item in attempts if item["estado"] == "autorizado"]
    if not parsed.exito:
        return not authorized

    # Un replay legacy terminal puede no haber persistido intentos ni guardas.
    if operation.get("rece_snapshot_hash") is None and not attempts and not guards:
        return True
    if len(authorized) != 1:
        return False
    attempt = authorized[0]
    try:
        if operation.get("rece_snapshot_hash") is not None:
            if len(associations) != 1 or attempt["guarda_rece_id"] is None:
                return False
            association = associations[0]
            matching_guards = [
                guard
                for guard in guards
                if int(guard["id"]) == int(attempt["guarda_rece_id"])
            ]
            if len(matching_guards) != 1:
                return False
            guard = matching_guards[0]
            if (
                guard["fase"] != "cerrada_terminal"
                or attempt["ambiente"] != association["ambiente"]
                or int(attempt["punto_venta_id"]) != int(association["punto_venta_id"])
                or int(attempt["punto_venta_elegibilidad_revision_id"])
                != int(association["elegibilidad_revision_id"])
                or int(attempt["punto_venta_revision_fiscal"])
                != int(association["punto_venta_revision_fiscal"])
                or int(guard["empresa_id"]) != int(association["empresa_id"])
                or int(guard["punto_venta_id"]) != int(association["punto_venta_id"])
                or guard["ambiente"] != association["ambiente"]
                or int(guard["elegibilidad_revision_id"])
                != int(association["elegibilidad_revision_id"])
                or int(guard["punto_venta_revision_fiscal"])
                != int(association["punto_venta_revision_fiscal"])
            ):
                return False
        fecha = date.fromisoformat(str(attempt["fecha_emision"])[:10])
        cae_vencimiento = date.fromisoformat(str(attempt["cae_vencimiento"])[:10])
        return bool(
            int(attempt["comprobante_id"]) == int(parsed.comprobante_id or 0)
            and int(attempt["empresa_id"]) == int(operation["empresa_id"])
            and int(attempt["tipo_comprobante"]) == parsed.tipo_comprobante
            and int(attempt["punto_venta_numero"]) == parsed.punto_venta
            and int(attempt["numero_planificado"]) == parsed.numero
            and fecha == parsed.fecha
            and Decimal(str(attempt["total"])) == parsed.total
            and str(attempt["cae"]) == str(parsed.cae)
            and cae_vencimiento == parsed.cae_vencimiento
        )
    except (TypeError, ValueError):
        return False


def pf19c_global_rejection_matches_operation(
    attempt: dict[str, Any],
    operation: dict[str, Any] | None,
) -> bool:
    """Vincula un 10005 durable con el replay idempotente que lo publica."""
    if (
        attempt.get("estado") != "rechazado_arca"
        or attempt.get("categoria_error") != ARCA_RECHAZO_GLOBAL_CATEGORIA
        or not _is_exact_global_10005_errors(attempt.get("errores_arca_json"))
        or operation is None
        or int(operation.get("empresa_id") or 0) != int(attempt.get("empresa_id") or 0)
        or operation.get("estado") not in ESTADOS_OPERACION_TERMINALES
        or not terminal_operation_response_is_valid(operation)
    ):
        return False

    if operation.get("tipo_operacion") in {
        "procesar_lote",
        "reintentar_fallidos_lote",
    }:
        response_raw = _json_object_sqlite(operation.get("response_json"))
        if response_raw is None:
            return False
        contexto = _batch_global_rejection_context(
            response_raw,
            operation_type=str(operation["tipo_operacion"]),
            operation_id=int(operation["id"]),
        )
        try:
            rejection_ids = contexto[0] if contexto is not None else frozenset()
            return bool(
                operation.get("estado") == "rechazado_arca"
                and operation.get("lote_id") is not None
                and attempt.get("lote_id") is not None
                and int(operation["lote_id"]) == int(attempt["lote_id"])
                and attempt.get("grupo_id") is not None
                and int(attempt["grupo_id"]) in rejection_ids
            )
        except (KeyError, TypeError, ValueError):
            return False
    if operation.get("tipo_operacion") != "emitir_comprobante":
        return False
    response_raw = _json_object_sqlite(operation.get("response_json"))
    if response_raw is None:
        return False
    try:
        response = EmitirComprobanteResponse.model_validate(response_raw)
        fecha = date.fromisoformat(str(attempt["fecha_emision"])[:10])
        total = Decimal(str(attempt["total"])).quantize(Decimal("0.01"))
        numero = int(attempt["numero_planificado"])
    except (KeyError, TypeError, ValidationError, ValueError, DecimalException):
        return False
    return bool(
        _response_is_exact_global_10005(response)
        and response.tipo_comprobante == int(attempt["tipo_comprobante"])
        and response.punto_venta == int(attempt["punto_venta_numero"])
        and response.numero == numero
        and response.fecha == fecha
        and response.total.quantize(Decimal("0.01")) == total
    )


def journal_legacy_pf19_is_coherent(
    conn: sqlite3.Connection,
    journal: dict[str, Any],
    attempt: dict[str, Any] | None,
    operation: dict[str, Any] | None,
) -> bool:
    """Valida que el journal append-only cierre solo un candidato legacy exacto."""
    if (
        attempt is None
        or operation is None
        or journal.get("accion") != "cerrar_legacy_sin_autorizacion_verificada"
        or journal.get("resultado") != LEGACY_PF19_CATEGORIA
        or journal.get("ambiente_consultado")
        not in {"homologacion", "produccion", "ambos"}
        or attempt.get("estado") != "fallido_verificado"
        or attempt.get("categoria_error") != LEGACY_PF19_CATEGORIA
        or not _is_json_null_sqlite(attempt.get("errores_arca_json"))
        or operation.get("estado") not in ESTADOS_OPERACION_TERMINALES
        or not terminal_operation_response_is_valid(operation)
    ):
        return False
    consultas = _json_object_sqlite(journal.get("resultado_consultas_json"))
    backup = _json_object_sqlite(journal.get("backup_metadata_json"))
    ambiente = str(journal.get("ambiente_consultado") or "")
    ambientes_esperados = (
        {"homologacion", "produccion"} if ambiente == "ambos" else {ambiente}
    )
    if (
        consultas
        != {item: "ultimo_menor_al_planificado" for item in sorted(ambientes_esperados)}
        or backup is None
    ):
        return False
    try:
        BackupLegacyPF19.model_validate(
            {**backup, "sha256": journal.get("backup_sha256")}
        )
        _require_sha256(journal.get("plan_sha256"), label="journal.plan_sha256")
        _require_sha256(
            journal.get("terminal_response_sha256"),
            label="journal.terminal_response_sha256",
        )
    except (MigrationError, TypeError, ValidationError, ValueError):
        return False
    response_terminal = _json_object_sqlite(operation.get("response_json"))
    if response_terminal is None:
        return False
    response_sha256 = hashlib.sha256(
        json.dumps(
            response_terminal,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if journal.get("terminal_response_sha256") != response_sha256:
        return False
    try:
        same_company = (
            int(journal["empresa_id"]) == int(attempt["empresa_id"])
            and int(attempt["empresa_id"]) == int(operation["empresa_id"])
            and int(attempt["operacion_id"]) == int(operation["id"])
        )
    except (KeyError, TypeError, ValueError):
        return False
    if operation.get("tipo_operacion") == "emitir_comprobante":
        try:
            response = EmitirComprobanteResponse.model_validate(response_terminal)
            fecha = date.fromisoformat(str(attempt["fecha_emision"])[:10])
            total = Decimal(str(attempt["total"])).quantize(Decimal("0.01"))
        except (
            KeyError,
            TypeError,
            ValidationError,
            ValueError,
            DecimalException,
        ):
            return False
        if (
            operation.get("estado") != "fallido_verificado"
            or operation.get("lote_id") is not None
            or attempt.get("lote_id") is not None
            or attempt.get("grupo_id") is not None
            or response.exito
            or response.requiere_reconciliacion
            or response.categoria_error != LEGACY_PF19_CATEGORIA
            or response.errores_arca
            or response.errores
            or response.mensaje != LEGACY_PF19_MENSAJE
            or response.comprobante_id is not None
            or response.cae is not None
            or response.cae_vencimiento is not None
            or response.tipo_comprobante != int(attempt["tipo_comprobante"])
            or response.punto_venta != int(attempt["punto_venta_numero"])
            or response.numero != int(attempt["numero_planificado"])
            or response.fecha != fecha
            or response.total.quantize(Decimal("0.01")) != total
        ):
            return False
    elif operation.get("tipo_operacion") in {
        "procesar_lote",
        "reintentar_fallidos_lote",
    }:
        try:
            lote_row = conn.execute(
                "SELECT * FROM lotes_comprobantes WHERE id = ?",
                (int(operation["lote_id"]),),
            ).fetchone()
            if lote_row is None:
                return False
            lote_source = dict(lote_row)
            for field_name in (
                "metadata_json",
                "mapeo_usado_json",
                "headers_detectados_json",
            ):
                value = lote_source.get(field_name)
                if isinstance(value, str):
                    lote_source[field_name] = json.loads(value)
            lote_esperado = LoteComprobanteResponse.model_validate(lote_source)
            group_counts = {
                str(row["estado"]): int(row["cantidad"])
                for row in conn.execute(
                    """
                    SELECT estado, COUNT(*) AS cantidad
                    FROM lotes_comprobantes_grupos
                    WHERE lote_id = ?
                    GROUP BY estado
                    """,
                    (int(operation["lote_id"]),),
                )
            }
            row_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM lotes_comprobantes_filas WHERE lote_id = ?",
                    (int(operation["lote_id"]),),
                ).fetchone()[0]
            )
            if (
                lote_esperado.total_filas != row_count
                or lote_esperado.total_grupos != sum(group_counts.values())
                or lote_esperado.grupos_validos != group_counts.get("validado", 0)
                or lote_esperado.grupos_con_error != group_counts.get("con_error", 0)
                or lote_esperado.grupos_emitidos != group_counts.get("autorizado", 0)
                or lote_esperado.grupos_fallidos != group_counts.get("fallido", 0)
                or lote_esperado.grupos_reconciliados_externos
                != group_counts.get("autorizado_externo", 0)
                or lote_esperado.grupos_descartados != group_counts.get("descartado", 0)
            ):
                return False
            if operation["tipo_operacion"] == "procesar_lote":
                if set(response_terminal) != {
                    "lote",
                    "mensaje",
                    "en_progreso",
                    "errores_arca",
                }:
                    return False
                response_lote = LoteProcesamientoResponse.model_validate(
                    response_terminal
                )
                if response_lote.en_progreso:
                    return False
            else:
                if set(response_terminal) != {"lote", "mensaje", "errores_arca"}:
                    return False
                response_lote = LoteAccionResponse.model_validate(response_terminal)
            batch_coherente = bool(
                operation.get("estado") == "finalizado"
                and operation.get("lote_id") is not None
                and attempt.get("lote_id") is not None
                and int(operation["lote_id"]) == int(attempt["lote_id"])
                and attempt.get("grupo_id") is not None
                and journal.get("grupo_encontrado") is not None
                and int(journal["grupo_empresa_id"]) == int(journal["empresa_id"])
                and int(journal["grupo_lote_id"]) == int(operation["lote_id"])
                and journal.get("grupo_estado") == "fallido"
                and response_lote.mensaje == LEGACY_PF19_MENSAJE
                and not response_lote.errores_arca
                and int(response_lote.lote.id) == int(operation["lote_id"])
                and int(response_lote.lote.empresa_id) == int(journal["empresa_id"])
                and response_lote.lote.estado == "fallido"
                and response_lote.lote.model_dump(mode="json")
                == lote_esperado.model_dump(mode="json")
            )
        except (KeyError, TypeError, ValidationError, ValueError, json.JSONDecodeError):
            return False
        if not batch_coherente:
            return False
    else:
        return False
    return same_company


def _digest_asociaciones_rece(rows: list[dict[str, Any]]) -> str:
    """Reproduce el digest RECE v1 usando asociaciones y número de punto."""
    identities = {
        (int(row["empresa_id"]), int(row["punto_venta_id"]), str(row["ambiente"]))
        for row in rows
    }
    if not rows or len(identities) != len(rows):
        raise MigrationError(
            "Una operación terminal tiene asociaciones RECE vacías o duplicadas"
        )
    material = {
        "version": 1,
        "contextos": [
            {
                "empresa_id": int(row["empresa_id"]),
                "punto_venta_id": int(row["punto_venta_id"]),
                "punto_venta_numero": int(row["punto_venta_numero"]),
                "ambiente": str(row["ambiente"]),
                "elegibilidad_revision_id": int(row["elegibilidad_revision_id"]),
                "punto_venta_revision_fiscal": int(row["punto_venta_revision_fiscal"]),
            }
            for row in sorted(
                rows,
                key=lambda item: (
                    int(item["empresa_id"]),
                    int(item["punto_venta_id"]),
                    str(item["ambiente"]),
                ),
            )
        ],
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_rece_ledger_sqlite(conn: sqlite3.Connection) -> None:
    """Valida heads y ledger append-only antes de exportar la SQLite."""
    puntos = list(
        conn.execute(
            "SELECT id, empresa_id, revision_fiscal FROM puntos_venta ORDER BY id"
        )
    )
    total_heads = int(
        conn.execute(
            "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_actual"
        ).fetchone()[0]
    )
    if total_heads != len(puntos) * 2:
        raise MigrationError(
            "El ledger RECE fuente no tiene exactamente dos cabezas por punto"
        )

    revisiones_huerfanas = int(conn.execute("""
            SELECT COUNT(*)
            FROM puntos_venta_elegibilidad_rece_revisiones r
            LEFT JOIN puntos_venta p
              ON p.id = r.punto_venta_id AND p.empresa_id = r.empresa_id
            WHERE p.id IS NULL
            """).fetchone()[0])
    heads_huerfanas = int(conn.execute("""
            SELECT COUNT(*)
            FROM puntos_venta_elegibilidad_rece_actual h
            LEFT JOIN puntos_venta p
              ON p.id = h.punto_venta_id AND p.empresa_id = h.empresa_id
            LEFT JOIN puntos_venta_elegibilidad_rece_revisiones r
              ON r.id = h.revision_actual_id
             AND r.empresa_id = h.empresa_id
             AND r.punto_venta_id = h.punto_venta_id
             AND r.ambiente = h.ambiente
            WHERE p.id IS NULL OR r.id IS NULL
            """).fetchone()[0])
    if revisiones_huerfanas or heads_huerfanas:
        raise MigrationError(
            "El ledger RECE fuente contiene ownership o punteros huérfanos"
        )

    for punto in puntos:
        heads = list(
            conn.execute(
                """
                SELECT ambiente, revision_actual_id
                FROM puntos_venta_elegibilidad_rece_actual
                WHERE punto_venta_id = ? AND empresa_id = ?
                ORDER BY ambiente
                """,
                (int(punto["id"]), int(punto["empresa_id"])),
            )
        )
        if len(heads) != 2 or {str(head["ambiente"]) for head in heads} != (
            AMBIENTES_RECE
        ):
            raise MigrationError(
                "Un punto de venta no tiene las cabezas RECE producción/homologación"
            )
        for head in heads:
            revisiones = list(
                conn.execute(
                    """
                    SELECT id, revision, punto_revision_fiscal
                    FROM puntos_venta_elegibilidad_rece_revisiones
                    WHERE punto_venta_id = ? AND empresa_id = ? AND ambiente = ?
                    ORDER BY revision
                    """,
                    (
                        int(punto["id"]),
                        int(punto["empresa_id"]),
                        str(head["ambiente"]),
                    ),
                )
            )
            if not revisiones:
                raise MigrationError(
                    "Una cabeza RECE no conserva ninguna revisión de su ambiente"
                )
            numeros_revision = [int(row["revision"]) for row in revisiones]
            if numeros_revision != list(range(1, len(revisiones) + 1)):
                raise MigrationError(
                    "El ledger RECE fuente tiene un hueco en su secuencia append-only"
                )
            revisiones_fiscales = [
                int(row["punto_revision_fiscal"]) for row in revisiones
            ]
            if revisiones_fiscales != sorted(revisiones_fiscales):
                raise MigrationError(
                    "El ledger RECE fuente hace retroceder la revisión fiscal"
                )
            ultima = revisiones[-1]
            if int(head["revision_actual_id"]) != int(ultima["id"]):
                raise MigrationError(
                    "Una cabeza RECE no apunta a la revisión monotónica máxima"
                )
            revision_fiscal_head = int(ultima["punto_revision_fiscal"])
            revision_fiscal_punto = int(punto["revision_fiscal"])
            if (
                revision_fiscal_head <= 0
                or revision_fiscal_head > revision_fiscal_punto
            ):
                raise MigrationError(
                    "La cabeza RECE tiene una revisión fiscal imposible para el punto"
                )


def classify_safe_omissions(conn: sqlite3.Connection) -> dict[str, Any]:
    """Bloquea estados continuables o inciertos y resume omisiones seguras."""
    blockers: dict[str, int] = {}

    operaciones = [dict(row) for row in conn.execute("""
            SELECT o.id, o.empresa_id, o.idempotency_key, o.tipo_operacion,
                   o.payload_hash, o.estado, o.response_json,
                   o.rece_snapshot_hash, o.lote_id,
                   l.id AS lote_encontrado, l.empresa_id AS lote_empresa_id,
                   l.estado AS lote_estado
            FROM operaciones_idempotentes o
            LEFT JOIN lotes_comprobantes l
              ON l.id = o.lote_id AND l.empresa_id = o.empresa_id
            ORDER BY o.id
            """)]
    estados_operacion_desconocidos = sum(
        row["estado"] not in ESTADOS_OPERACION_CONOCIDOS for row in operaciones
    )
    operaciones_no_terminales = sum(
        row["estado"] in ESTADOS_OPERACION_CONOCIDOS
        and row["estado"] not in ESTADOS_OPERACION_TERMINALES
        for row in operaciones
    )
    operaciones_sin_respuesta = sum(
        row["estado"] in ESTADOS_OPERACION_TERMINALES
        and _json_object_sqlite(row["response_json"]) is None
        for row in operaciones
    )
    if estados_operacion_desconocidos:
        blockers["operaciones_estado_desconocido"] = estados_operacion_desconocidos
    if operaciones_no_terminales:
        blockers["operaciones_no_terminales"] = operaciones_no_terminales
    if operaciones_sin_respuesta:
        blockers["operaciones_terminales_sin_respuesta"] = operaciones_sin_respuesta
    operaciones_respuesta_invalida = sum(
        row["estado"] in ESTADOS_OPERACION_TERMINALES
        and not terminal_operation_response_is_valid(row)
        for row in operaciones
    )
    if operaciones_respuesta_invalida:
        blockers["operaciones_terminales_respuesta_invalida"] = (
            operaciones_respuesta_invalida
        )
    operaciones_exitosas_sin_comprobante = sum(
        row["estado"] in ESTADOS_OPERACION_TERMINALES
        and row["tipo_operacion"] == "emitir_comprobante"
        and (_json_object_sqlite(row["response_json"]) or {}).get("exito") is True
        and not terminal_individual_success_matches_db(conn, row)
        for row in operaciones
    )
    if operaciones_exitosas_sin_comprobante:
        blockers["operaciones_exitosas_sin_comprobante"] = (
            operaciones_exitosas_sin_comprobante
        )
    operaciones_lote_respuesta_incoherente = sum(
        row["estado"] in ESTADOS_OPERACION_TERMINALES
        and not terminal_batch_response_matches_db(conn, row)
        for row in operaciones
    )
    if operaciones_lote_respuesta_incoherente:
        blockers["operaciones_lote_respuesta_incoherente"] = (
            operaciones_lote_respuesta_incoherente
        )
    operaciones_identidad_invalida = sum(
        not isinstance(row["idempotency_key"], str)
        or not str(row["idempotency_key"]).strip()
        or len(str(row["idempotency_key"])) > 128
        or not isinstance(row["payload_hash"], str)
        or len(str(row["payload_hash"])) != 64
        for row in operaciones
    )
    if operaciones_identidad_invalida:
        blockers["operaciones_identidad_invalida"] = operaciones_identidad_invalida

    asociaciones = [dict(row) for row in conn.execute("""
            SELECT a.*,
                   o.id AS operacion_encontrada,
                   o.empresa_id AS operacion_empresa_id,
                   p.id AS punto_encontrado,
                   r.id AS revision_encontrada,
                   r.estado AS revision_estado,
                   r.fuente AS revision_fuente,
                   r.evidencia_tipo AS revision_evidencia_tipo,
                   r.revision AS revision_numero,
                   r.punto_venta_numero_snapshot AS punto_venta_numero,
                   r.punto_revision_fiscal AS revision_fiscal_snapshot
            FROM operaciones_idempotentes_elegibilidad_rece a
            LEFT JOIN operaciones_idempotentes o
              ON o.id = a.operacion_id
            LEFT JOIN puntos_venta p
              ON p.id = a.punto_venta_id AND p.empresa_id = a.empresa_id
            LEFT JOIN puntos_venta_elegibilidad_rece_revisiones r
              ON r.id = a.elegibilidad_revision_id
             AND r.empresa_id = a.empresa_id
             AND r.punto_venta_id = a.punto_venta_id
             AND r.ambiente = a.ambiente
            ORDER BY a.operacion_id, a.empresa_id, a.punto_venta_id, a.ambiente
            """)]
    asociaciones_por_operacion: dict[int, list[dict[str, Any]]] = {}
    asociaciones_invalidas = 0
    operaciones_con_asociacion_invalida: set[int] = set()
    for asociacion in asociaciones:
        operacion_id = int(asociacion["operacion_id"])
        asociaciones_por_operacion.setdefault(operacion_id, []).append(asociacion)
        if (
            asociacion["operacion_encontrada"] is None
            or int(asociacion["operacion_empresa_id"] or 0)
            != int(asociacion["empresa_id"])
            or asociacion["punto_encontrado"] is None
            or asociacion["punto_venta_numero"] is None
            or asociacion["revision_encontrada"] is None
            or asociacion["ambiente"] not in AMBIENTES_RECE
            or asociacion["revision_estado"] != "verificado_rece"
            or asociacion["revision_fuente"] != "constancia_arca_atestada"
            or asociacion["revision_evidencia_tipo"]
            != "rece_aplicativo_web_services_v1"
            or int(asociacion["revision_numero"] or 0) <= 0
            or not 1 <= int(asociacion["punto_venta_numero"] or 0) <= 99999
            or int(asociacion["punto_venta_revision_fiscal"] or 0) <= 0
            or int(asociacion["revision_fiscal_snapshot"] or 0)
            != int(asociacion["punto_venta_revision_fiscal"])
        ):
            asociaciones_invalidas += 1
            operaciones_con_asociacion_invalida.add(operacion_id)

    operaciones_digest_incoherente = 0
    ids_operaciones = {int(row["id"]) for row in operaciones}
    if any(
        operacion_id not in ids_operaciones
        for operacion_id in asociaciones_por_operacion
    ):
        asociaciones_invalidas += 1
    for operacion in operaciones:
        rows = asociaciones_por_operacion.get(int(operacion["id"]), [])
        digest = operacion["rece_snapshot_hash"]
        if digest is None:
            if rows:
                operaciones_digest_incoherente += 1
            continue
        if int(operacion["id"]) in operaciones_con_asociacion_invalida or not rows:
            operaciones_digest_incoherente += 1
            continue
        try:
            actual = _digest_asociaciones_rece(rows)
        except (KeyError, TypeError, ValueError, MigrationError):
            operaciones_digest_incoherente += 1
            continue
        if actual != str(digest):
            operaciones_digest_incoherente += 1
    if asociaciones_invalidas:
        blockers["asociaciones_rece_invalidas"] = asociaciones_invalidas
    if operaciones_digest_incoherente:
        blockers["operaciones_digest_rece_incoherente"] = operaciones_digest_incoherente
    operaciones_individuales_asociacion_incoherente = sum(
        not individual_association_matches_response(
            conn,
            operacion,
            asociaciones_por_operacion.get(int(operacion["id"]), []),
        )
        for operacion in operaciones
    )
    if operaciones_individuales_asociacion_incoherente:
        blockers["operaciones_individuales_asociacion_incoherente"] = (
            operaciones_individuales_asociacion_incoherente
        )

    intentos = [dict(row) for row in conn.execute("""
            SELECT id, estado, operacion_id, guarda_rece_id, comprobante_id,
                   empresa_id, lote_id, grupo_id, punto_venta_id, punto_venta_numero,
                   tipo_comprobante, ambiente,
                   punto_venta_elegibilidad_revision_id,
                   punto_venta_revision_fiscal,
                   numero_planificado, fecha_emision, total, cae,
                   cae_vencimiento, categoria_error, errores_arca_json
            FROM intentos_emision_fiscal
            ORDER BY id
            """)]
    intentos_desconocidos = sum(
        row["estado"] not in ESTADOS_INTENTO_CONOCIDOS for row in intentos
    )
    intentos_no_terminales = sum(
        row["estado"] in ESTADOS_INTENTO_CONOCIDOS
        and row["estado"] not in ESTADOS_INTENTO_TERMINALES
        for row in intentos
    )
    if intentos_desconocidos:
        blockers["intentos_estado_desconocido"] = intentos_desconocidos
    if intentos_no_terminales:
        blockers["intentos_no_terminales"] = intentos_no_terminales
    autorizados_incoherentes = int(conn.execute("""
            SELECT COUNT(*)
            FROM intentos_emision_fiscal i
            LEFT JOIN comprobantes c ON c.id = i.comprobante_id
            WHERE i.estado = 'autorizado'
              AND (
                c.id IS NULL OR c.estado <> 'autorizado'
                OR c.empresa_id <> i.empresa_id
                OR c.punto_venta_id <> i.punto_venta_id
                OR c.tipo_comprobante <> i.tipo_comprobante
                OR i.numero_planificado IS NULL
                OR c.numero <> i.numero_planificado
                OR c.fecha_emision <> i.fecha_emision
                OR c.total <> i.total
                OR c.cae IS NULL OR i.cae IS NULL OR c.cae <> i.cae
                OR c.cae_vencimiento IS NULL
                OR i.cae_vencimiento IS NULL
                OR c.cae_vencimiento <> i.cae_vencimiento
              )
            """).fetchone()[0])
    if autorizados_incoherentes:
        blockers["intentos_autorizados_sin_comprobante"] = autorizados_incoherentes
    intentos_fallidos_con_evidencia_positiva = sum(
        row["estado"] in {"fallido_verificado", "rechazado_arca"}
        and (
            row["comprobante_id"] is not None
            or row["cae"] is not None
            or row["cae_vencimiento"] is not None
        )
        for row in intentos
    )
    if intentos_fallidos_con_evidencia_positiva:
        blockers["intentos_fallidos_con_evidencia_positiva"] = (
            intentos_fallidos_con_evidencia_positiva
        )

    operaciones_por_id = {int(row["id"]): row for row in operaciones}
    intentos_rechazo_global_incoherentes = sum(
        not pf19c_global_rejection_matches_operation(
            intento,
            operaciones_por_id.get(int(intento["operacion_id"] or 0)),
        )
        for intento in intentos
        if intento["estado"] == "rechazado_arca"
        and (
            intento["categoria_error"] == ARCA_RECHAZO_GLOBAL_CATEGORIA
            or not _is_json_null_sqlite(intento["errores_arca_json"])
        )
    )
    if intentos_rechazo_global_incoherentes:
        blockers["intentos_rechazo_global_pf19c_incoherentes"] = (
            intentos_rechazo_global_incoherentes
        )
    legacy_con_errores_arca_estructurados = sum(
        intento["estado"] == "fallido_verificado"
        and intento["categoria_error"] == LEGACY_PF19_CATEGORIA
        and not _is_json_null_sqlite(intento["errores_arca_json"])
        for intento in intentos
    )
    if legacy_con_errores_arca_estructurados:
        blockers["intentos_legacy_con_errores_arca_estructurados"] = (
            legacy_con_errores_arca_estructurados
        )

    journals = [dict(row) for row in conn.execute("""
            SELECT j.*, i.id AS intento_encontrado, i.empresa_id AS intento_empresa_id,
                   i.estado AS intento_estado,
                   i.categoria_error AS intento_categoria_error,
                   i.errores_arca_json AS intento_errores_arca_json,
                   i.operacion_id AS intento_operacion_id,
                   i.lote_id AS intento_lote_id, i.grupo_id AS intento_grupo_id,
                   i.tipo_comprobante AS intento_tipo_comprobante,
                   i.punto_venta_numero AS intento_punto_venta_numero,
                   i.numero_planificado AS intento_numero_planificado,
                   i.fecha_emision AS intento_fecha_emision,
                   i.total AS intento_total,
                   o.id AS operacion_encontrada,
                   o.empresa_id AS operacion_empresa_id,
                   o.estado AS operacion_estado,
                   o.tipo_operacion AS operacion_tipo_operacion,
                   o.response_json AS operacion_response_json,
                   o.lote_id AS operacion_lote_id,
                   l.id AS operacion_lote_encontrado,
                   l.empresa_id AS operacion_lote_empresa_id,
                   l.estado AS operacion_lote_estado,
                   g.id AS grupo_encontrado, g.empresa_id AS grupo_empresa_id,
                   g.lote_id AS grupo_lote_id, g.estado AS grupo_estado,
                   u.id AS actor_encontrado, u.empresa_id AS actor_empresa_id
            FROM resoluciones_legacy_pf19_journal j
            LEFT JOIN intentos_emision_fiscal i
              ON i.id = j.intento_id AND i.empresa_id = j.empresa_id
            LEFT JOIN operaciones_idempotentes o
              ON o.id = i.operacion_id AND o.empresa_id = i.empresa_id
            LEFT JOIN lotes_comprobantes l
              ON l.id = o.lote_id AND l.empresa_id = o.empresa_id
            LEFT JOIN lotes_comprobantes_grupos g
              ON g.id = i.grupo_id AND g.empresa_id = i.empresa_id
            LEFT JOIN usuarios u ON u.id = j.actor_usuario_id
            ORDER BY j.id
            """)]
    journals_incoherentes = 0
    for journal in journals:
        intento = (
            {
                "id": journal["intento_encontrado"],
                "empresa_id": journal["intento_empresa_id"],
                "estado": journal["intento_estado"],
                "categoria_error": journal["intento_categoria_error"],
                "errores_arca_json": journal["intento_errores_arca_json"],
                "operacion_id": journal["intento_operacion_id"],
                "lote_id": journal["intento_lote_id"],
                "grupo_id": journal["intento_grupo_id"],
                "tipo_comprobante": journal["intento_tipo_comprobante"],
                "punto_venta_numero": journal["intento_punto_venta_numero"],
                "numero_planificado": journal["intento_numero_planificado"],
                "fecha_emision": journal["intento_fecha_emision"],
                "total": journal["intento_total"],
            }
            if journal["intento_encontrado"] is not None
            else None
        )
        operation = (
            {
                "id": journal["operacion_encontrada"],
                "empresa_id": journal["operacion_empresa_id"],
                "estado": journal["operacion_estado"],
                "tipo_operacion": journal["operacion_tipo_operacion"],
                "response_json": journal["operacion_response_json"],
                "lote_id": journal["operacion_lote_id"],
                "lote_encontrado": journal["operacion_lote_encontrado"],
                "lote_empresa_id": journal["operacion_lote_empresa_id"],
                "lote_estado": journal["operacion_lote_estado"],
            }
            if journal["operacion_encontrada"] is not None
            else None
        )
        if (
            journal["actor_encontrado"] is None
            or int(journal["actor_empresa_id"] or 0) != int(journal["empresa_id"] or 0)
            or not journal_legacy_pf19_is_coherent(conn, journal, intento, operation)
        ):
            journals_incoherentes += 1
    if journals_incoherentes:
        blockers["journals_legacy_pf19_incoherentes"] = journals_incoherentes

    guardas = [dict(row) for row in conn.execute("""
            SELECT id, operacion_id, fase, empresa_id, punto_venta_id,
                   ambiente, elegibilidad_revision_id,
                   punto_venta_revision_fiscal,
                   arca_iniciada_en, cerrada_en
            FROM puntos_venta_guardas_emision_rece
            ORDER BY id
            """)]
    guardas_desconocidas = sum(
        row["fase"] not in FASES_GUARDA_CONOCIDAS for row in guardas
    )
    guardas_no_terminales = sum(
        row["fase"] in FASES_GUARDA_CONOCIDAS
        and row["fase"] not in FASES_GUARDA_TERMINALES
        for row in guardas
    )
    guardas_terminales_incoherentes = sum(
        (
            row["fase"] == "cerrada_pre_arca"
            and (row["arca_iniciada_en"] is not None or row["cerrada_en"] is None)
        )
        or (
            row["fase"] == "cerrada_terminal"
            and (row["arca_iniciada_en"] is None or row["cerrada_en"] is None)
        )
        for row in guardas
    )
    intentos_por_guarda: dict[int, list[dict[str, Any]]] = {}
    for intento in intentos:
        if intento["guarda_rece_id"] is not None:
            intentos_por_guarda.setdefault(int(intento["guarda_rece_id"]), []).append(
                intento
            )
    guardas_por_id = {int(row["id"]): row for row in guardas}
    guardas_huerfanas = 0
    guardas_intentos_incoherentes = 0
    for guarda in guardas:
        guarda_id = int(guarda["id"])
        intentos_guarda = intentos_por_guarda.get(guarda_id, [])
        if not intentos_guarda:
            guardas_huerfanas += 1
            continue
        if any(
            int(intento["operacion_id"] or 0) != int(guarda["operacion_id"])
            for intento in intentos_guarda
        ):
            guardas_intentos_incoherentes += 1
            continue
        estados_guardados = {str(intento["estado"]) for intento in intentos_guarda}
        if guarda["fase"] == "cerrada_pre_arca":
            if estados_guardados != {"fallido_verificado"}:
                guardas_intentos_incoherentes += 1
        elif guarda["fase"] == "cerrada_terminal" and not estados_guardados <= {
            "autorizado",
            "rechazado_arca",
        }:
            guardas_intentos_incoherentes += 1
    intentos_guarda_huerfana = sum(
        int(intento["guarda_rece_id"]) not in guardas_por_id
        for intento in intentos
        if intento["guarda_rece_id"] is not None
    )
    if guardas_desconocidas:
        blockers["guardas_fase_desconocida"] = guardas_desconocidas
    if guardas_no_terminales:
        blockers["guardas_no_terminales"] = guardas_no_terminales
    if guardas_terminales_incoherentes:
        blockers["guardas_terminales_incoherentes"] = guardas_terminales_incoherentes
    if guardas_huerfanas:
        blockers["guardas_huerfanas_sin_intentos"] = guardas_huerfanas
    if guardas_intentos_incoherentes or intentos_guarda_huerfana:
        blockers["guardas_intentos_incoherentes"] = (
            guardas_intentos_incoherentes + intentos_guarda_huerfana
        )
    intentos_por_operacion: dict[int, list[dict[str, Any]]] = {}
    for intento in intentos:
        if intento["operacion_id"] is not None:
            intentos_por_operacion.setdefault(int(intento["operacion_id"]), []).append(
                intento
            )
    guardas_por_operacion: dict[int, list[dict[str, Any]]] = {}
    for guarda in guardas:
        guardas_por_operacion.setdefault(int(guarda["operacion_id"]), []).append(guarda)
    operaciones_individuales_resultado_incoherente = sum(
        not individual_operation_result_matches_attempts(
            operacion,
            intentos_por_operacion.get(int(operacion["id"]), []),
            guardas_por_operacion.get(int(operacion["id"]), []),
            asociaciones_por_operacion.get(int(operacion["id"]), []),
        )
        for operacion in operaciones
    )
    if operaciones_individuales_resultado_incoherente:
        blockers["operaciones_individuales_resultado_incoherente"] = (
            operaciones_individuales_resultado_incoherente
        )

    lotes = [
        dict(row)
        for row in conn.execute("SELECT id, estado FROM lotes_comprobantes ORDER BY id")
    ]
    lotes_bloqueantes = sum(
        row["estado"] not in ESTADOS_LOTE_SEGUROS_OMITIBLES for row in lotes
    )
    if lotes_bloqueantes:
        blockers["lotes_activos_inciertos_o_desconocidos"] = lotes_bloqueantes
    grupos = [dict(row) for row in conn.execute("""
            SELECT g.id, g.lote_id, g.empresa_id, g.estado,
                   g.tipo_comprobante, g.punto_venta_id,
                   g.punto_venta_numero, g.ambiente,
                   g.punto_venta_elegibilidad_revision_id,
                   g.punto_venta_revision_fiscal, g.total_estimado,
                   g.cae, g.numero_asignado, g.comprobante_id,
                   c.id AS comprobante_encontrado,
                   c.empresa_id AS comprobante_empresa_id,
                   c.punto_venta_id AS comprobante_punto_venta_id,
                   c.tipo_comprobante AS comprobante_tipo,
                   c.numero AS comprobante_numero,
                   c.total AS comprobante_total,
                   c.cae AS comprobante_cae,
                   c.estado AS comprobante_estado
            FROM lotes_comprobantes_grupos g
            LEFT JOIN comprobantes c ON c.id = g.comprobante_id
            ORDER BY g.id
            """)]
    grupos_bloqueantes = sum(
        row["estado"] not in ESTADOS_GRUPO_SEGUROS_OMITIBLES for row in grupos
    )
    if grupos_bloqueantes:
        blockers["grupos_activos_inciertos_o_desconocidos"] = grupos_bloqueantes
    grupos_evidencia_incoherente = 0
    for grupo in grupos:
        estado = str(grupo["estado"])
        if estado in {"autorizado", "autorizado_externo"}:
            try:
                snapshot_values = (
                    grupo["punto_venta_id"],
                    grupo["ambiente"],
                    grupo["punto_venta_elegibilidad_revision_id"],
                    grupo["punto_venta_revision_fiscal"],
                )
                snapshot_legacy = all(value is None for value in snapshot_values)
                snapshot_moderno = all(value is not None for value in snapshot_values)
                evidencia_valida = bool(
                    grupo["comprobante_id"] is not None
                    and grupo["comprobante_encontrado"] is not None
                    and grupo["comprobante_estado"] == "autorizado"
                    and int(grupo["comprobante_empresa_id"]) == int(grupo["empresa_id"])
                    and (
                        snapshot_legacy
                        or (
                            snapshot_moderno
                            and int(grupo["comprobante_punto_venta_id"])
                            == int(grupo["punto_venta_id"])
                        )
                    )
                    and grupo["tipo_comprobante"] is not None
                    and int(grupo["comprobante_tipo"]) == int(grupo["tipo_comprobante"])
                    and grupo["numero_asignado"] is not None
                    and int(grupo["comprobante_numero"])
                    == int(grupo["numero_asignado"])
                    and grupo["cae"] is not None
                    and str(grupo["comprobante_cae"]) == str(grupo["cae"])
                    and Decimal(str(grupo["comprobante_total"]))
                    == Decimal(str(grupo["total_estimado"]))
                )
            except (TypeError, ValueError):
                evidencia_valida = False
            if not evidencia_valida:
                grupos_evidencia_incoherente += 1
        elif (
            grupo["comprobante_id"] is not None
            or grupo["numero_asignado"] is not None
            or grupo["cae"] is not None
        ):
            grupos_evidencia_incoherente += 1
    if grupos_evidencia_incoherente:
        blockers["grupos_evidencia_fiscal_incoherente"] = grupos_evidencia_incoherente
    grupos_por_id = {int(row["id"]): row for row in grupos}
    operaciones_por_id = {int(row["id"]): row for row in operaciones}
    intentos_por_operacion: dict[int, list[dict[str, Any]]] = {}
    intentos_por_grupo_global: dict[int, list[dict[str, Any]]] = {}
    for intento in intentos:
        operacion_id = intento.get("operacion_id")
        if operacion_id is not None:
            intentos_por_operacion.setdefault(int(operacion_id), []).append(intento)
        grupo_id = intento.get("grupo_id")
        if grupo_id is not None:
            intentos_por_grupo_global.setdefault(int(grupo_id), []).append(intento)

    def grupo_pf19c_conserva_historia_terminal(
        grupo: dict[str, Any],
        operacion_rechazo: dict[str, Any],
    ) -> bool:
        """Acepta el rechazo original o una autorización batch posterior exacta."""
        try:
            if int(grupo["lote_id"]) != int(operacion_rechazo["lote_id"]) or int(
                grupo["empresa_id"]
            ) != int(operacion_rechazo["empresa_id"]):
                return False
            if grupo["estado"] == "fallido":
                return True
            if grupo["estado"] != "autorizado":
                return False
            supersesores = []
            for intento in intentos_por_grupo_global.get(int(grupo["id"]), []):
                sucesora_id = intento.get("operacion_id")
                if (
                    intento.get("estado") != "autorizado"
                    or intento.get("comprobante_id") is None
                    or sucesora_id is None
                    or int(sucesora_id) <= int(operacion_rechazo["id"])
                    or int(intento.get("lote_id") or 0) != int(grupo["lote_id"])
                    or int(intento.get("empresa_id") or 0) != int(grupo["empresa_id"])
                ):
                    continue
                sucesora = operaciones_por_id.get(int(sucesora_id))
                if (
                    sucesora is not None
                    and sucesora.get("tipo_operacion")
                    in {"procesar_lote", "reintentar_fallidos_lote"}
                    and int(sucesora.get("lote_id") or 0) == int(grupo["lote_id"])
                    and int(sucesora.get("empresa_id") or 0) == int(grupo["empresa_id"])
                    and sucesora.get("estado") == "finalizado"
                    and terminal_operation_response_is_valid(sucesora)
                ):
                    supersesores.append(int(intento["id"]))
            return len(supersesores) == 1
        except (KeyError, TypeError, ValueError):
            return False

    operaciones_batch_pf19c_grafo_incoherente = 0
    for operacion in operaciones:
        if operacion.get("tipo_operacion") not in {
            "procesar_lote",
            "reintentar_fallidos_lote",
        }:
            continue
        respuesta = _json_object_sqlite(operacion.get("response_json"))
        contexto = (
            _batch_global_rejection_context(
                respuesta,
                operation_type=str(operacion["tipo_operacion"]),
                operation_id=int(operacion["id"]),
            )
            if respuesta is not None
            else None
        )
        if operacion.get("estado") != "rechazado_arca" and contexto is None:
            continue
        if contexto is None or operacion.get("lote_id") is None:
            operaciones_batch_pf19c_grafo_incoherente += 1
            continue
        rechazo_ids, no_enviados_ids = contexto
        intentos_operacion = intentos_por_operacion.get(int(operacion["id"]), [])
        intentos_rechazo = [
            intento
            for intento in intentos_operacion
            if intento.get("grupo_id") is not None
            and intento.get("estado") == "rechazado_arca"
            and intento.get("categoria_error") == ARCA_RECHAZO_GLOBAL_CATEGORIA
            and _is_exact_global_10005_errors(intento.get("errores_arca_json"))
        ]
        grupos_intentos_rechazo = [
            int(intento["grupo_id"]) for intento in intentos_rechazo
        ]
        intentos_por_grupo: dict[int, list[dict[str, Any]]] = {}
        for intento in intentos_operacion:
            if intento.get("grupo_id") is not None:
                intentos_por_grupo.setdefault(int(intento["grupo_id"]), []).append(
                    intento
                )
        ids_contexto = rechazo_ids | no_enviados_ids
        grupos_contexto = [grupos_por_id.get(grupo_id) for grupo_id in ids_contexto]
        try:
            grafo_valido = bool(
                len(grupos_intentos_rechazo) == len(rechazo_ids)
                and set(grupos_intentos_rechazo) == set(rechazo_ids)
                and len(grupos_intentos_rechazo) == len(set(grupos_intentos_rechazo))
                and all(
                    len(intentos_por_grupo.get(grupo_id, [])) == 1
                    for grupo_id in rechazo_ids
                )
                and all(grupo is not None for grupo in grupos_contexto)
                and all(
                    grupo_pf19c_conserva_historia_terminal(grupo, operacion)
                    for grupo in grupos_contexto
                    if grupo is not None
                )
                and all(
                    intento.get("grupo_id") is None
                    or int(intento["grupo_id"]) not in no_enviados_ids
                    for intento in intentos_operacion
                )
            )
        except (KeyError, TypeError, ValueError):
            grafo_valido = False
        if not grafo_valido:
            operaciones_batch_pf19c_grafo_incoherente += 1
    if operaciones_batch_pf19c_grafo_incoherente:
        blockers["operaciones_batch_pf19c_grafo_incoherente"] = (
            operaciones_batch_pf19c_grafo_incoherente
        )
    filas = [dict(row) for row in conn.execute("""
            SELECT f.id, f.estado, f.grupo_id,
                   g.id AS grupo_encontrado, g.estado AS grupo_estado
            FROM lotes_comprobantes_filas f
            LEFT JOIN lotes_comprobantes_grupos g ON g.id = f.grupo_id
            ORDER BY f.id
            """)]
    filas_bloqueantes = sum(
        row["estado"] not in ESTADOS_FILA_SEGUROS_OMITIBLES for row in filas
    )
    if filas_bloqueantes:
        blockers["filas_activas_inciertas_o_desconocidas"] = filas_bloqueantes
    filas_grupo_incoherentes = sum(
        row["grupo_encontrado"] is None or row["estado"] != row["grupo_estado"]
        for row in filas
    )
    if filas_grupo_incoherentes:
        blockers["filas_estado_grupo_incoherente"] = filas_grupo_incoherentes

    if blockers:
        detail = ", ".join(f"{key}={value}" for key, value in sorted(blockers.items()))
        raise MigrationError(
            "La fuente no está quiescente o conserva evidencia fiscal incierta: "
            + detail
        )

    excluded_counts = count_tables(conn, EXCLUDED_TABLES)
    return {
        "blockers": 0,
        "excluded_counts": excluded_counts,
        "operaciones_terminales_preservadas": len(operaciones),
        "operaciones_lote_normalizado": sum(
            operacion["lote_id"] is not None for operacion in operaciones
        ),
        "asociaciones_rece_preservadas": len(asociaciones),
        "intentos_terminales_omitidos": len(intentos),
        "resoluciones_legacy_pf19_omitidas": len(journals),
        "guardas_terminales_omitidas": len(guardas),
        "lotes_seguros_omitidos": len(lotes),
        "grupos_seguros_omitidos": len(grupos),
        "filas_omitidas": len(filas),
        "eventos_lote_omitidos": int(
            conn.execute("SELECT COUNT(*) FROM lotes_comprobantes_eventos").fetchone()[
                0
            ]
        ),
        "eventos_sistema_omitidos": int(
            conn.execute("SELECT COUNT(*) FROM eventos_sistema").fetchone()[0]
        ),
        "exportaciones_omitidas": int(
            conn.execute(
                "SELECT COUNT(*) FROM exportaciones_almacenamiento"
            ).fetchone()[0]
        ),
    }


def validate_safe_omitted_counts(
    safe_omitted: dict[str, Any],
    *,
    included_counts: dict[str, int],
    excluded_counts: dict[str, int],
) -> None:
    """Reconcilia el resumen de omisiones con todos los conteos del snapshot."""
    if safe_omitted.get("blockers") != 0:
        raise MigrationError("El resumen de omisiones no quedó libre de bloqueos")
    if safe_omitted.get("excluded_counts") != excluded_counts:
        raise MigrationError(
            "El resumen de omisiones no coincide con las tablas excluidas"
        )
    mismatches = {
        table_name: {
            "esperado": excluded_counts[table_name],
            "observado": safe_omitted.get(summary_key),
        }
        for table_name, summary_key in vps_migration_v3.SAFE_OMITTED_COUNT_KEYS.items()
        if safe_omitted.get(summary_key) != excluded_counts[table_name]
    }
    if mismatches:
        raise MigrationError(
            "El resumen safe_omitted no reconcilia todos los conteos excluidos: "
            + ", ".join(
                f"{table}={values['observado']}/{values['esperado']}"
                for table, values in sorted(mismatches.items())
            )
        )
    if safe_omitted.get("operaciones_terminales_preservadas") != included_counts.get(
        "operaciones_idempotentes"
    ):
        raise MigrationError(
            "El resumen no reconcilia las operaciones idempotentes preservadas"
        )
    if safe_omitted.get("asociaciones_rece_preservadas") != included_counts.get(
        "operaciones_idempotentes_elegibilidad_rece"
    ):
        raise MigrationError(
            "El resumen no reconcilia las asociaciones RECE preservadas"
        )


def list_active_certificates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Devuelve certificados activos de la fuente SQLite."""
    rows = conn.execute("""
        SELECT c.id, c.archivo_crt, c.archivo_key, c.cuit,
               c.fecha_emision, c.fecha_vencimiento, c.empresa_id,
               e.cuit AS empresa_cuit
        FROM certificados c
        LEFT JOIN empresas e ON e.id = c.empresa_id
        WHERE c.activo = 1
        ORDER BY c.id
        """)
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
    plans: list[tuple[dict[str, Any], Path, Path]] = []
    destination_owners: dict[str, int] = {}
    for row in active_certs:
        cert_path = resolve_cert_source_path(str(row["archivo_crt"]), certs_dir)
        key_path = resolve_cert_source_path(str(row["archivo_key"]), certs_dir)
        cert_id = int(row["id"])
        for source_path in (cert_path, key_path):
            destination_key = source_path.name.casefold()
            previous_id = destination_owners.get(destination_key)
            if previous_id is not None:
                raise MigrationError(
                    "Dos certificados activos colisionan en el nombre destino "
                    f"{source_path.name}: IDs {previous_id} y {cert_id}"
                )
            destination_owners[destination_key] = cert_id
        plans.append((row, cert_path, key_path))

    for row, cert_path, key_path in plans:
        validate_active_certificate_material(
            row=row,
            cert_path=cert_path,
            key_path=key_path,
            source_key_password=source_key_password,
        )

    copied: dict[int, dict[str, str]] = {}
    for row, cert_path, key_path in plans:
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
        validate_active_certificate_material(
            row=row,
            cert_path=cert_dest,
            key_path=key_dest,
            source_key_password=target_key_password,
        )
        copied[int(row["id"])] = {
            "archivo_crt": cert_dest.name,
            "archivo_key": key_dest.name,
        }
    return copied


def validate_active_certificate_material(
    *,
    row: dict[str, Any],
    cert_path: Path,
    key_path: Path,
    source_key_password: str | None,
) -> None:
    """Valida vigencia, identidad y correspondencia criptográfica del par activo."""
    cert_id = int(row["id"])
    try:
        certificate = load_certificate(str(cert_path))
        password = source_key_password.encode("utf-8") if source_key_password else None
        private_key = load_private_key(str(key_path), password=password)
        _validate_active_certificate_objects(
            row=row,
            certificate=certificate,
            private_key=private_key,
        )
    except (
        ArcaCertificateError,
        AttributeError,
        KeyError,
        OSError,
        TypeError,
        UnsupportedAlgorithm,
        ValueError,
    ) as exc:
        raise MigrationError(
            f"El certificado activo ID {cert_id} no supera la validación criptográfica"
        ) from exc


def _validate_active_certificate_objects(
    *,
    row: dict[str, Any],
    certificate: Any,
    private_key: Any,
) -> None:
    """Valida el contrato fiscal común de un par X.509 ya cargado."""
    verify_certificate_validity(certificate)
    if (
        certificate.public_key().public_numbers()
        != private_key.public_key().public_numbers()
    ):
        raise ValueError("El certificado y la clave privada no forman un par")

    common_names = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    serial_numbers = certificate.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)
    common_name = common_names[0].value if common_names else ""
    serial_number = serial_numbers[0].value if serial_numbers else ""

    def extract_cuit(value: str) -> str | None:
        """Extrae un CUIT de 11 dígitos con la política runtime existente."""
        digits = "".join(character for character in value if character.isdigit())
        return digits if len(digits) == 11 else None

    subject_cuit = extract_cuit(common_name) or extract_cuit(serial_number)
    certificate_cuit = str(row.get("cuit") or "")
    company_cuit = str(row.get("empresa_cuit") or "")
    if (
        subject_cuit is None
        or not certificate_cuit.isdigit()
        or len(certificate_cuit) != 11
        or certificate_cuit != company_cuit
        or certificate_cuit != subject_cuit
    ):
        raise ValueError("El CUIT del certificado no coincide con su emisor")

    issued_on = date.fromisoformat(str(row["fecha_emision"])[:10])
    expires_on = date.fromisoformat(str(row["fecha_vencimiento"])[:10])
    if (
        certificate.not_valid_before_utc.date() != issued_on
        or certificate.not_valid_after_utc.date() != expires_on
    ):
        raise ValueError("La vigencia X.509 no coincide con la metadata")


def _load_encrypted_private_key_strict(path: Path, password: str) -> Any:
    """Carga una PEM solo si está cifrada con la contraseña destino exacta."""
    if not password:
        raise ValueError("La contraseña destino no puede estar vacía")
    return serialization.load_pem_private_key(
        path.read_bytes(),
        password=password.encode("utf-8"),
    )


def _active_certificate_rows_with_company(
    package_rows: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Cruza certificados activos hash-bound con el CUIT de su empresa."""
    companies = {
        int(row["id"]): row
        for row in package_rows.get("empresas", [])
        if row.get("id") is not None
    }
    active_rows: list[dict[str, Any]] = []
    for row in package_rows.get("certificados", []):
        if not bool(row.get("activo")):
            continue
        company = companies.get(int(row["empresa_id"]))
        if company is None:
            raise MigrationError(
                "Un certificado activo no pertenece a una empresa empaquetada"
            )
        active_rows.append(
            {
                **row,
                "empresa_cuit": company.get("cuit"),
            }
        )
    return active_rows


def _validate_packaged_active_certificate_pair(
    *,
    row: dict[str, Any],
    cert_path: Path,
    key_path: Path,
    target_password: str,
) -> None:
    """Valida un par activo empaquetado sin fallback a una clave en claro."""
    cert_id = int(row["id"])
    try:
        certificate = load_certificate(str(cert_path))
        private_key = _load_encrypted_private_key_strict(key_path, target_password)
        _validate_active_certificate_objects(
            row=row,
            certificate=certificate,
            private_key=private_key,
        )
    except (
        ArcaCertificateError,
        AttributeError,
        KeyError,
        OSError,
        TypeError,
        UnsupportedAlgorithm,
        ValueError,
    ) as exc:
        raise MigrationError(
            "El certificado activo empaquetado no supera la validación "
            f"criptográfica estricta (ID {cert_id})"
        ) from exc


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
    table = Base.metadata.tables[table_name]
    primary_key_columns = [column.name for column in table.primary_key.columns]
    if not primary_key_columns:
        raise MigrationError(
            f"La tabla incluida {table_name} no tiene clave primaria para ordenar."
        )
    order_by = ", ".join(f'"{column_name}"' for column_name in primary_key_columns)
    rows = conn.execute(f'SELECT * FROM "{table_name}" ORDER BY {order_by}')
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


def normalize_operation_rows(
    rows: list[dict[str, Any]],
    *,
    group_ids_by_lote: dict[int, list[int]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Desacopla lotes y atestigua su inventario de grupos omitido."""
    group_ids_by_lote = group_ids_by_lote or {}
    pairs = [
        _operation_lote_normalization_pair(
            row,
            group_ids_by_lote=group_ids_by_lote,
        )
        for row in rows
        if row.get("lote_id") is not None
    ]
    pairs.sort(key=lambda item: (item["operacion_id"], item["lote_id"]))
    canonical = json.dumps(
        pairs,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    normalized = [
        ({**row, "lote_id": None} if row.get("lote_id") is not None else dict(row))
        for row in rows
    ]
    return normalized, {
        "rule": OPERATION_LOTE_NORMALIZATION_RULE,
        "rows": len(pairs),
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "pairs": pairs,
    }


def _operation_lote_normalization_pair(
    row: dict[str, Any],
    *,
    group_ids_by_lote: dict[int, list[int]],
) -> dict[str, Any]:
    """Conserva inventario y roles PF-19C validados antes de omitir el lote."""
    lote_id = int(row["lote_id"])
    rejection_ids: list[int] = []
    not_sent_ids: list[int] = []
    response = _json_object_sqlite(row.get("response_json"))
    if response is not None:
        context = _batch_global_rejection_context(
            response,
            operation_type=str(row.get("tipo_operacion") or ""),
            operation_id=int(row["id"]),
        )
        if context is not None:
            rejection_ids = sorted(context[0])
            not_sent_ids = sorted(context[1])
    return {
        "operacion_id": int(row["id"]),
        "lote_id": lote_id,
        "grupo_ids": list(group_ids_by_lote.get(lote_id, [])),
        "grupos_rechazo_ids": rejection_ids,
        "grupos_no_enviados_ids": not_sent_ids,
    }


def build_idempotency_barrier(
    *,
    source_barrier: dict[str, Any],
    normalization: dict[str, Any],
    operation_rows: list[dict[str, Any]],
    association_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Atestigua la barrera SQLite y el grafo durable de replay preservado."""
    operations: list[dict[str, Any]] = []
    for row in sorted(operation_rows, key=lambda item: int(item["id"])):
        response = _canonical_json_object(
            row.get("response_json"),
            label=f"operacion {row.get('id')} response_json",
        )
        operations.append(
            {
                "id": row["id"],
                "empresa_id": row["empresa_id"],
                "idempotency_key": row["idempotency_key"],
                "tipo_operacion": row["tipo_operacion"],
                "payload_hash": row["payload_hash"],
                "estado": row["estado"],
                "response_json": response,
                "rece_snapshot_hash": row["rece_snapshot_hash"],
                "lote_id": row["lote_id"],
            }
        )
    associations = [
        {
            "id": row["id"],
            "operacion_id": row["operacion_id"],
            "empresa_id": row["empresa_id"],
            "punto_venta_id": row["punto_venta_id"],
            "ambiente": row["ambiente"],
            "elegibilidad_revision_id": row["elegibilidad_revision_id"],
            "punto_venta_revision_fiscal": row["punto_venta_revision_fiscal"],
        }
        for row in sorted(association_rows, key=lambda item: int(item["id"]))
    ]
    material = {
        "version": 1,
        "algorithm": vps_migration_v3.IDEMPOTENCY_BARRIER_ALGORITHM,
        "source_barrier": source_barrier,
        "normalization": normalization,
        "operations": operations,
        "associations": associations,
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return {
        "version": 1,
        "algorithm": vps_migration_v3.IDEMPOTENCY_BARRIER_ALGORITHM,
        "rows": len(operations),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _canonical_json_object(value: Any, *, label: str) -> dict[str, Any]:
    """Normaliza string/dict JSON a un objeto canónico sin claves duplicadas."""
    try:
        if isinstance(value, str):
            decoded = json.loads(
                value,
                object_pairs_hook=_json_object_without_duplicate_keys,
            )
        elif isinstance(value, dict):
            decoded = value
        else:
            raise TypeError("JSON no es string/dict")
        if not isinstance(decoded, dict):
            raise TypeError("JSON no es objeto")
        canonical = json.dumps(
            decoded,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
        result = json.loads(
            canonical,
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
    except MigrationError:
        raise
    except (TypeError, ValueError) as exc:
        raise MigrationError(f"JSON inválido en {label}") from exc
    if not isinstance(result, dict):
        raise MigrationError(f"JSON inválido en {label}")
    return result


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
        "CERTS_PATH=./certs",
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


def _require_exact_keys(
    value: Any,
    expected: set[str],
    *,
    label: str,
) -> dict[str, Any]:
    """Exige un objeto JSON sin campos faltantes ni extensiones implícitas."""
    if not isinstance(value, dict) or set(value) != expected:
        raise MigrationError(f"Shape inválido en {label} del manifest")
    return value


def _require_nonnegative_int(value: Any, *, label: str) -> int:
    """Valida un entero JSON no negativo sin aceptar booleanos."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MigrationError(f"Conteo inválido en {label} del manifest")
    return value


def _require_sha256(value: Any, *, label: str) -> str:
    """Valida un SHA-256 hexadecimal canónico en minúsculas."""
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise MigrationError(f"SHA-256 inválido en {label} del manifest")
    return value


def _require_canonical_package_path(value: Any, *, expected: str, label: str) -> str:
    """Exige un path relativo POSIX exacto, sin traversal ni normalización oculta."""
    if not isinstance(value, str) or value != expected or "\\" in value:
        raise MigrationError(f"Path no canónico en {label} del manifest")
    candidate = PurePosixPath(value)
    if (
        candidate.is_absolute()
        or str(candidate) != value
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise MigrationError(f"Path no canónico en {label} del manifest")
    return value


def _json_object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    """Construye un objeto JSON y rechaza claves repetidas antes de colapsarlas."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MigrationError(f"El JSON contiene una clave duplicada: {key}")
        result[key] = value
    return result


def _parse_manifest_jsonl_lines(
    lines: Iterable[str],
    *,
    table_name: str,
) -> list[dict[str, Any]]:
    """Parsea JSONL canónico y exige el schema histórico fijo de v3."""
    columns = vps_migration_v3.V3_COLUMNS[table_name]
    expected_columns = set(columns)
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        serialized = line.rstrip("\n")
        if not serialized or serialized.endswith("\r"):
            raise MigrationError(f"JSONL inválido en {table_name}, línea {line_number}")
        payload = json.loads(
            serialized,
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
        if not isinstance(payload, dict) or set(payload) != expected_columns:
            raise MigrationError(
                f"Schema JSONL inválido en {table_name}, línea {line_number}"
            )
        for column_name, column in columns.items():
            value = payload[column_name]
            if value is None:
                if column.primary_key or not column.nullable:
                    raise MigrationError(
                        f"NULL inválido en {table_name}.{column_name}, "
                        f"línea {line_number}"
                    )
                continue
            if column.kind == "boolean" and (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value not in {0, 1}
            ):
                raise MigrationError(
                    f"Boolean no canónico en {table_name}.{column_name}, "
                    f"línea {line_number}"
                )
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if serialized != canonical:
            raise MigrationError(
                f"JSONL no canónico en {table_name}, línea {line_number}"
            )
        try:
            vps_migration_v3.adapt_row(table_name, payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise MigrationError(
                f"Tipo JSONL inválido en {table_name}, línea {line_number}"
            ) from exc
        rows.append(payload)
    primary_key = vps_migration_v3.PRIMARY_KEYS[table_name]
    identities: list[tuple[Any, ...]] = []
    for row in rows:
        identity: list[Any] = []
        for column_name in primary_key:
            value = row[column_name]
            if value is None:
                raise MigrationError(
                    f"PK nula en el JSONL de {table_name}.{column_name}"
                )
            if columns[column_name].kind == "integer":
                value = _require_nonnegative_int(
                    value,
                    label=f"{table_name}.{column_name}",
                )
                if value <= 0:
                    raise MigrationError(
                        f"PK no positiva en el JSONL de {table_name}.{column_name}"
                    )
            identity.append(value)
        identities.append(tuple(identity))
    if identities != sorted(identities) or len(identities) != len(set(identities)):
        raise MigrationError(f"PK no canónica en el JSONL de {table_name}")
    return rows


def _read_manifest_jsonl_rows(
    file_path: Path,
    *,
    table_name: str,
) -> list[dict[str, Any]]:
    """Lee una vez el JSONL canónico y valida su schema modelado."""
    raw = file_path.read_bytes()
    text_content = raw.decode("utf-8")
    return _parse_manifest_jsonl_lines(
        text_content.splitlines(keepends=True),
        table_name=table_name,
    )


def _convert_v4_jsonl_value(
    *,
    table_name: str,
    column_name: str,
    value: Any,
    line_number: int,
) -> Any:
    """Valida un valor v4 sin coerciones ambiguas y devuelve su tipo destino."""
    column = _historical_v4_table(table_name).c[column_name]
    label = f"{table_name}.{column_name}, línea {line_number}"
    if value is None:
        if column.primary_key or not column.nullable:
            raise MigrationError(f"NULL inválido en {label}")
        return None
    if isinstance(column.type, (ExactAmount, ExactDecimal, ExactInteger)):
        if isinstance(value, bool) or not isinstance(value, str):
            raise MigrationError(f"Decimal A-01 no canónico en {label}")
        number = Decimal(value)
        if isinstance(column.type, ExactInteger):
            from app.core.fiscal_storage import scaled_integer

            integer = scaled_integer(number)
            if str(integer) != value:
                raise MigrationError(f"Entero A-01 no canónico en {label}")
            return integer
        if encode_decimal(number) != value:
            raise MigrationError(f"Decimal A-01 no canónico en {label}")
        return number
    if isinstance(column.type, Boolean):
        if not isinstance(value, int) or isinstance(value, bool) or value not in {0, 1}:
            raise MigrationError(f"Boolean no canónico en {label}")
        return bool(value)
    if isinstance(column.type, Integer):
        if not isinstance(value, int) or isinstance(value, bool):
            raise MigrationError(f"Entero no canónico en {label}")
        return value
    if isinstance(column.type, DateTime):
        if not isinstance(value, str):
            raise MigrationError(f"Timestamp no canónico en {label}")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if column.type.timezone:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
        elif parsed.tzinfo is not None:
            raise MigrationError(f"Timestamp local con zona inesperada en {label}")
        return parsed
    if isinstance(column.type, Date):
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise MigrationError(f"Fecha no canónica en {label}")
        return date.fromisoformat(value)
    if isinstance(column.type, Numeric):
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise MigrationError(f"Decimal no canónico en {label}")
        decimal_value = Decimal(str(value))
        if not decimal_value.is_finite():
            raise MigrationError(f"Decimal no finito en {label}")
        scale = column.type.scale
        precision = column.type.precision
        if scale is not None:
            quantum = Decimal(1).scaleb(-scale)
            if decimal_value != decimal_value.quantize(quantum):
                raise MigrationError(f"Decimal fuera de escala en {label}")
        if precision is not None:
            integer_digits = max(1, decimal_value.copy_abs().adjusted() + 1)
            if integer_digits > precision - int(scale or 0):
                raise MigrationError(f"Decimal fuera de precisión en {label}")
        return decimal_value
    if isinstance(column.type, JSON):
        if not isinstance(value, str):
            raise MigrationError(f"JSON SQLite no canónico en {label}")
        return json.loads(value, object_pairs_hook=_json_object_without_duplicate_keys)
    if isinstance(column.type, (String, Text)):
        if not isinstance(value, str):
            raise MigrationError(f"Texto no canónico en {label}")
        length = getattr(column.type, "length", None)
        if length is not None and len(value) > length:
            raise MigrationError(f"Texto fuera de longitud en {label}")
        return value
    raise MigrationError(f"Tipo v4 no soportado en {label}")


def _parse_manifest_jsonl_lines_v4(
    lines: Iterable[str],
    *,
    table_name: str,
    convert: bool = False,
) -> list[dict[str, Any]]:
    """Parsea JSONL v4 contra columnas congeladas y tipos estrictos del head."""
    try:
        expected_columns = _fiscal_package_format().V4_COLUMNS[table_name]
        target_table = _historical_v4_table(table_name)
    except KeyError as exc:
        raise MigrationError(f"Tabla v4 no modelada: {table_name}") from exc
    if tuple(target_table.columns.keys()) != expected_columns:
        raise MigrationError(
            f"El ORM vigente ya no representa el contrato v4 de {table_name}"
        )
    rows: list[dict[str, Any]] = []
    converted_rows: list[dict[str, Any]] = []
    expected_set = set(expected_columns)
    for line_number, line in enumerate(lines, start=1):
        serialized = line.rstrip("\n")
        if not serialized or serialized.endswith("\r"):
            raise MigrationError(f"JSONL inválido en {table_name}, línea {line_number}")
        payload = json.loads(
            serialized,
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
        if not isinstance(payload, dict) or set(payload) != expected_set:
            raise MigrationError(
                f"Schema JSONL inválido en {table_name}, línea {line_number}"
            )
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if serialized != canonical:
            raise MigrationError(
                f"JSONL no canónico en {table_name}, línea {line_number}"
            )
        converted_row = {
            column_name: _convert_v4_jsonl_value(
                table_name=table_name,
                column_name=column_name,
                value=payload[column_name],
                line_number=line_number,
            )
            for column_name in expected_columns
        }
        rows.append(payload)
        converted_rows.append(converted_row)
    primary_key = _fiscal_package_format().PRIMARY_KEYS[table_name]
    identities = [
        tuple(row[column_name] for column_name in primary_key) for row in rows
    ]
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for identity in identities
        for value in identity
    ):
        raise MigrationError(f"PK no positiva en el JSONL de {table_name}")
    if identities != sorted(identities) or len(identities) != len(set(identities)):
        raise MigrationError(f"PK no canónica en el JSONL de {table_name}")
    return converted_rows if convert else rows


def _read_manifest_jsonl_rows_v4(
    file_path: Path,
    *,
    table_name: str,
    convert: bool = False,
) -> list[dict[str, Any]]:
    raw = file_path.read_bytes()
    return _parse_manifest_jsonl_lines_v4(
        raw.decode("utf-8").splitlines(keepends=True),
        table_name=table_name,
        convert=convert,
    )


def _validate_normalization_pairs(value: Any) -> list[dict[str, Any]]:
    """Valida y canoniza la evidencia de pares lote_id retirada del JSONL."""
    if not isinstance(value, list):
        raise MigrationError("pairs inválido en la normalización lote_id")
    pairs: list[dict[str, Any]] = []
    for index, raw_pair in enumerate(value):
        pair = _require_exact_keys(
            raw_pair,
            {
                "operacion_id",
                "lote_id",
                "grupo_ids",
                "grupos_rechazo_ids",
                "grupos_no_enviados_ids",
            },
            label=f"normalizations.lote_id.pairs[{index}]",
        )
        operation_id = _require_nonnegative_int(
            pair["operacion_id"],
            label=f"normalizations.lote_id.pairs[{index}].operacion_id",
        )
        lote_id = _require_nonnegative_int(
            pair["lote_id"],
            label=f"normalizations.lote_id.pairs[{index}].lote_id",
        )
        if operation_id <= 0 or lote_id <= 0:
            raise MigrationError("La normalización lote_id contiene IDs no positivos")
        group_ids = _strict_positive_id_list(pair["grupo_ids"])
        rejection_ids = _strict_positive_id_list(pair["grupos_rechazo_ids"])
        not_sent_ids = _strict_positive_id_list(pair["grupos_no_enviados_ids"])
        if (
            group_ids is None
            or rejection_ids is None
            or not_sent_ids is None
            or set(rejection_ids) & set(not_sent_ids)
            or not (set(rejection_ids) | set(not_sent_ids)).issubset(set(group_ids))
        ):
            raise MigrationError(
                "La normalización lote_id contiene inventario o roles de grupos inválidos"
            )
        pairs.append(
            {
                "operacion_id": operation_id,
                "lote_id": lote_id,
                "grupo_ids": list(group_ids),
                "grupos_rechazo_ids": list(rejection_ids),
                "grupos_no_enviados_ids": list(not_sent_ids),
            }
        )
    expected_order = sorted(
        pairs,
        key=lambda item: (item["operacion_id"], item["lote_id"]),
    )
    operation_ids = [pair["operacion_id"] for pair in pairs]
    if pairs != expected_order or len(operation_ids) != len(set(operation_ids)):
        raise MigrationError("Los pares normalizados no son únicos y canónicos")
    return pairs


def _validate_operation_lote_normalization(
    *,
    normalization: dict[str, Any],
    pairs: list[dict[str, Any]],
    operation_rows: list[dict[str, Any]],
) -> None:
    """Cruza la evidencia de lote retirada con cada operación batch empaquetada."""
    if normalization["rows"] != len(pairs):
        raise MigrationError("rows no coincide con los pares normalizados")
    canonical = json.dumps(
        pairs,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if normalization["sha256"] != hashlib.sha256(canonical).hexdigest():
        raise MigrationError("El SHA-256 de los pares normalizados no verifica")

    operations_by_id = {int(row["id"]): row for row in operation_rows}
    pair_by_operation = {pair["operacion_id"]: pair for pair in pairs}
    expected_batch_ids = {
        int(row["id"])
        for row in operation_rows
        if row["tipo_operacion"] in {"procesar_lote", "reintentar_fallidos_lote"}
    }
    if set(pair_by_operation) != expected_batch_ids:
        raise MigrationError(
            "Los pares normalizados no coinciden con las operaciones batch"
        )
    for operation_id, pair in pair_by_operation.items():
        operation = operations_by_id.get(operation_id)
        if operation is None or operation["lote_id"] is not None:
            raise MigrationError("Una normalización lote_id no tiene operación válida")
        response = _json_object_sqlite(operation["response_json"])
        if response is None:
            raise MigrationError("Una operación batch no conserva respuesta durable")
        rejection_context = _batch_global_rejection_context(
            response,
            operation_type=str(operation["tipo_operacion"]),
            operation_id=operation_id,
        )
        if rejection_context is not None:
            if (
                sorted(rejection_context[0]) != pair["grupos_rechazo_ids"]
                or sorted(rejection_context[1]) != pair["grupos_no_enviados_ids"]
            ):
                raise MigrationError(
                    "El rechazo PF-19C no coincide con los roles de grupos fuente"
                )
        elif pair["grupos_rechazo_ids"] or pair["grupos_no_enviados_ids"]:
            raise MigrationError(
                "La normalización atribuye roles PF-19C a una operación no terminal"
            )
        lote_payload = response.get("lote")
        if lote_payload is not None:
            if not isinstance(lote_payload, dict):
                raise MigrationError("La respuesta batch tiene lote inválido")
            lote_response_id = lote_payload.get("id")
            if (
                not isinstance(lote_response_id, int)
                or isinstance(lote_response_id, bool)
                or lote_response_id != pair["lote_id"]
            ):
                raise MigrationError(
                    "El lote de replay no coincide con el par normalizado"
                )


def _validate_packaged_rece_associations(
    table_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Reconstruye ownership y digest RECE usando solo el contenido empaquetado."""
    operations = {int(row["id"]): row for row in table_rows["operaciones_idempotentes"]}
    points = {int(row["id"]): row for row in table_rows["puntos_venta"]}
    revisions = {
        int(row["id"]): row
        for row in table_rows["puntos_venta_elegibilidad_rece_revisiones"]
    }
    associations_by_operation: dict[int, list[dict[str, Any]]] = {}
    identities: set[tuple[int, int, str]] = set()
    for association in table_rows["operaciones_idempotentes_elegibilidad_rece"]:
        try:
            operation_id = int(association["operacion_id"])
            company_id = int(association["empresa_id"])
            point_id = int(association["punto_venta_id"])
            environment = str(association["ambiente"])
            revision_id = int(association["elegibilidad_revision_id"])
            fiscal_revision = int(association["punto_venta_revision_fiscal"])
            operation = operations[operation_id]
            point = points[point_id]
            revision = revisions[revision_id]
            identity = (operation_id, point_id, environment)
            if (
                identity in identities
                or environment not in AMBIENTES_RECE
                or int(operation["empresa_id"]) != company_id
                or int(point["empresa_id"]) != company_id
                or int(revision["empresa_id"]) != company_id
                or int(revision["punto_venta_id"]) != point_id
                or revision["ambiente"] != environment
                or revision["estado"] != "verificado_rece"
                or revision["fuente"] != "constancia_arca_atestada"
                or revision["evidencia_tipo"] != "rece_aplicativo_web_services_v1"
                or int(revision["revision"]) <= 0
                or not 1 <= int(revision["punto_venta_numero_snapshot"]) <= 99999
                or fiscal_revision <= 0
                or int(revision["punto_revision_fiscal"]) != fiscal_revision
            ):
                raise MigrationError("El paquete contiene asociaciones RECE inválidas")
        except (KeyError, TypeError, ValueError) as exc:
            raise MigrationError(
                "El paquete contiene asociaciones RECE inválidas"
            ) from exc
        identities.add(identity)
        associations_by_operation.setdefault(operation_id, []).append(
            {
                **association,
                "punto_venta_numero": int(revision["punto_venta_numero_snapshot"]),
            }
        )

    for operation_id, operation in operations.items():
        associations = associations_by_operation.get(operation_id, [])
        digest = operation["rece_snapshot_hash"]
        if digest is None:
            if associations:
                raise MigrationError(
                    "Una operación legacy conserva asociaciones RECE inesperadas"
                )
            continue
        _require_sha256(digest, label="operacion.rece_snapshot_hash")
        if not associations or _digest_asociaciones_rece(associations) != digest:
            raise MigrationError("El digest RECE empaquetado no verifica")
        if (
            operation["tipo_operacion"] == "emitir_comprobante"
            and len(associations) != 1
        ):
            raise MigrationError(
                "Una emisión individual moderna no tiene una asociación RECE exacta"
            )


def _validate_packaged_foreign_keys(
    table_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Valida en memoria las FKs entre tablas incluidas antes de tocar destino."""
    included = set(vps_migration_v3.INCLUDED_TABLES)
    referenced_keys: dict[tuple[str, tuple[str, ...]], set[tuple[Any, ...]]] = {}
    for table_name in vps_migration_v3.INCLUDED_TABLES:
        for constraint in vps_migration_v3.FOREIGN_KEYS.get(table_name, ()):
            referred_table = constraint.remote_table
            local_columns = constraint.local_columns
            remote_columns = constraint.remote_columns
            if referred_table not in included:
                for row in table_rows[table_name]:
                    values = tuple(row[column] for column in local_columns)
                    if any(value is not None for value in values):
                        raise MigrationError(
                            f"{table_name} conserva una FK a una tabla excluida"
                        )
                continue
            key = (referred_table, remote_columns)
            if key not in referenced_keys:
                referenced_keys[key] = {
                    tuple(row[column] for column in remote_columns)
                    for row in table_rows[referred_table]
                }
            for row in table_rows[table_name]:
                values = tuple(row[column] for column in local_columns)
                if all(value is None for value in values):
                    continue
                if any(value is None for value in values):
                    raise MigrationError(
                        f"{table_name} conserva una FK compuesta parcialmente nula"
                    )
                if values not in referenced_keys[key]:
                    raise MigrationError(
                        f"{table_name} conserva una FK incluida inexistente"
                    )


def _validate_packaged_v4_foreign_keys(
    table_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Valida todas las FKs vigentes del subgrafo v4, incluidas las diferidas."""
    included = set(_fiscal_package_format().INCLUDED_TABLES)
    key_cache: dict[tuple[str, tuple[str, ...]], set[tuple[Any, ...]]] = {}
    for table_name in _fiscal_package_format().INCLUDED_TABLES:
        table = Base.metadata.tables[table_name]
        for constraint in table.foreign_key_constraints:
            local_columns = tuple(
                element.parent.name for element in constraint.elements
            )
            remote_table = next(iter(constraint.elements)).column.table.name
            remote_columns = tuple(
                element.column.name for element in constraint.elements
            )
            if remote_table not in included:
                for row in table_rows[table_name]:
                    if any(
                        row[column_name] is not None for column_name in local_columns
                    ):
                        raise MigrationError(
                            f"{table_name} conserva una FK a {remote_table} fuera de v4"
                        )
                continue
            cache_key = (remote_table, remote_columns)
            if cache_key not in key_cache:
                key_cache[cache_key] = {
                    tuple(row[column_name] for column_name in remote_columns)
                    for row in table_rows[remote_table]
                }
            for row in table_rows[table_name]:
                values = tuple(row[column_name] for column_name in local_columns)
                if any(value is None for value in values):
                    continue
                if values not in key_cache[cache_key]:
                    raise MigrationError(f"{table_name} conserva una FK v4 inexistente")


def _validate_packaged_user_accesses(
    table_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Valida que la compatibilidad singular derive de la autoridad explícita."""
    users = {int(row["id"]): row for row in table_rows["usuarios"]}
    accesses: dict[int, list[int]] = {user_id: [] for user_id in users}
    identities: set[tuple[int, int]] = set()
    for row in table_rows["usuario_emisor_acceso"]:
        identity = (int(row["usuario_id"]), int(row["empresa_id"]))
        if identity in identities:
            raise MigrationError("El paquete duplica un acceso usuario-emisor")
        identities.add(identity)
        if row["origen"] not in {
            "migracion_legacy",
            "asignacion_admin",
            "creacion_propia",
        }:
            raise MigrationError("El paquete contiene un origen de acceso inválido")
        accesses.setdefault(identity[0], []).append(identity[1])

    for user_id, user in users.items():
        capability = user.get("puede_crear_editar_emisores")
        if capability not in {0, 1, False, True}:
            raise MigrationError("La capacidad multiemisor no es booleana")
        assigned = sorted(accesses.get(user_id, []))
        expected_legacy = assigned[0] if len(assigned) == 1 else None
        legacy = user.get("empresa_id")
        if legacy is not None:
            legacy = int(legacy)
        if legacy != expected_legacy:
            raise MigrationError(
                "usuarios.empresa_id no coincide con la asignación explícita"
            )


def validate_user_accesses_sqlite(conn: sqlite3.Connection) -> None:
    """Valida el contrato multiemisor antes de exportar una fuente privada."""
    rows = {
        "usuarios": [dict(row) for row in conn.execute("SELECT * FROM usuarios")],
        "usuario_emisor_acceso": [
            dict(row) for row in conn.execute("SELECT * FROM usuario_emisor_acceso")
        ],
    }
    _validate_packaged_user_accesses(rows)


def _validate_packaged_terminal_operations(
    *,
    table_rows: dict[str, list[dict[str, Any]]],
    normalization_pairs: list[dict[str, Any]],
) -> None:
    """Valida autoridad de replay, DTO y evidencia incluida de cada operación."""
    companies = {int(row["id"]) for row in table_rows["empresas"]}
    receipts = {int(row["id"]): row for row in table_rows["comprobantes"]}
    revisions = {
        int(row["id"]): row
        for row in table_rows["puntos_venta_elegibilidad_rece_revisiones"]
    }
    associations_by_operation: dict[int, list[dict[str, Any]]] = {}
    for association in table_rows["operaciones_idempotentes_elegibilidad_rece"]:
        associations_by_operation.setdefault(
            int(association["operacion_id"]), []
        ).append(association)
    pair_by_operation = {pair["operacion_id"]: pair for pair in normalization_pairs}
    identities: set[tuple[int, str]] = set()

    for row in table_rows["operaciones_idempotentes"]:
        try:
            operation_id = _require_nonnegative_int(row["id"], label="operacion.id")
            company_id = _require_nonnegative_int(
                row["empresa_id"], label="operacion.empresa_id"
            )
            key = row["idempotency_key"]
            operation_type = row["tipo_operacion"]
            state = row["estado"]
            if (
                operation_id <= 0
                or company_id <= 0
                or company_id not in companies
                or not isinstance(key, str)
                or not 1 <= len(key.strip()) <= 128
                or key != key.strip()
                or not isinstance(operation_type, str)
                or operation_type
                not in {
                    "emitir_comprobante",
                    "procesar_lote",
                    "reintentar_fallidos_lote",
                }
                or state not in ESTADOS_OPERACION_TERMINALES
                or row["lote_id"] is not None
            ):
                raise MigrationError("Operación terminal empaquetada inválida")
            _require_sha256(row["payload_hash"], label="operacion.payload_hash")
            identity = (company_id, key)
            if identity in identities:
                raise MigrationError("Identidad idempotente duplicada en el paquete")
            identities.add(identity)
            response = _json_object_sqlite(row["response_json"])
            if response is None:
                raise MigrationError("Operación terminal sin respuesta durable")

            if operation_type == "emitir_comprobante":
                if operation_id in pair_by_operation:
                    raise MigrationError("Una emisión individual conserva lote")
                parsed = vps_migration_v3.parse_individual_replay(response)
                if parsed.requiere_reconciliacion:
                    raise MigrationError("Replay individual incierto en el paquete")
                associations = associations_by_operation.get(operation_id, [])
                if row["rece_snapshot_hash"] is not None:
                    if len(associations) != 1:
                        raise MigrationError(
                            "Emisión moderna sin asociación RECE exacta"
                        )
                    revision = revisions[
                        int(associations[0]["elegibilidad_revision_id"])
                    ]
                    if (
                        int(revision["punto_venta_numero_snapshot"])
                        != parsed.punto_venta
                    ):
                        raise MigrationError(
                            "El DTO individual no coincide con el snapshot RECE"
                        )
                if parsed.exito:
                    if (
                        parsed.comprobante_id is None
                        or parsed.comprobante_id <= 0
                        or parsed.numero <= 0
                        or not parsed.cae
                        or not parsed.cae.strip()
                        or parsed.cae_vencimiento is None
                    ):
                        raise MigrationError(
                            "Replay individual exitoso sin evidencia fiscal completa"
                        )
                    receipt = receipts.get(int(parsed.comprobante_id or 0))
                    if receipt is None:
                        raise MigrationError(
                            "Replay individual exitoso sin comprobante incluido"
                        )
                    receipt_expiration = date.fromisoformat(
                        str(receipt["cae_vencimiento"])[:10]
                    )
                    if (
                        state != "finalizado"
                        or receipt["estado"] != "autorizado"
                        or int(receipt["empresa_id"]) != company_id
                        or int(receipt["tipo_comprobante"]) != parsed.tipo_comprobante
                        or int(receipt["numero"]) != parsed.numero
                        or date.fromisoformat(str(receipt["fecha_emision"])[:10])
                        != parsed.fecha
                        or Decimal(str(receipt["total"])) != parsed.total
                        or str(receipt["cae"]) != str(parsed.cae)
                        or receipt_expiration != parsed.cae_vencimiento
                        or (
                            associations
                            and int(receipt["punto_venta_id"])
                            != int(associations[0]["punto_venta_id"])
                        )
                    ):
                        raise MigrationError(
                            "Replay individual no coincide con su comprobante"
                        )
                elif (
                    state == "finalizado"
                    or parsed.comprobante_id is not None
                    or parsed.cae is not None
                    or parsed.cae_vencimiento is not None
                    or parsed.categoria_error
                    in {"duplicado_logico", "idempotencia_en_proceso"}
                ):
                    raise MigrationError("Replay individual negativo incoherente")
                if parsed.categoria_error == ARCA_RECHAZO_GLOBAL_CATEGORIA and (
                    state != "rechazado_arca"
                    or not _response_is_exact_global_10005(parsed)
                ):
                    raise MigrationError(
                        "Replay individual 10005 no conserva evidencia sanitaria exacta"
                    )
                continue

            pair = pair_by_operation.get(operation_id)
            if pair is None:
                raise MigrationError("Operación batch sin lote normalizado")
            if "categoria_error" in response:
                parsed_error = vps_migration_v3.parse_batch_error_replay(response)
                category = parsed_error.categoria_error
                status_code = parsed_error.status_code
                if (
                    state == "finalizado"
                    or state == "rechazado_arca"
                    or not category.strip()
                    or category
                    in {
                        "duplicado_logico_lote",
                        "idempotencia_en_proceso",
                        "post_arca_persistencia",
                    }
                    or (status_code is not None and not 400 <= status_code <= 599)
                ):
                    raise MigrationError("Replay batch negativo incoherente")
                continue
            if operation_type == "procesar_lote":
                if "en_progreso" not in response:
                    raise MigrationError("Replay procesar_lote sin estado durable")
                parsed_lote = vps_migration_v3.parse_batch_replay(
                    response,
                    operation_type=operation_type,
                )
                if parsed_lote.en_progreso:
                    raise MigrationError("Replay batch todavía en progreso")
            else:
                if "en_progreso" in response:
                    raise MigrationError("Replay de reintento tiene shape incorrecto")
                parsed_lote = vps_migration_v3.parse_batch_replay(
                    response,
                    operation_type=operation_type,
                )
            rechazo_global = _batch_global_rejection_context(
                response,
                operation_type=operation_type,
                operation_id=operation_id,
            )
            if state == "rechazado_arca":
                if rechazo_global is None:
                    raise MigrationError(
                        "Replay batch 10005 no conserva evidencia sanitaria exacta"
                    )
            elif rechazo_global is not None or parsed_lote.errores_arca:
                raise MigrationError(
                    "Replay batch conserva evidencia 10005 sin estado terminal exacto"
                )
            if (
                state not in {"finalizado", "fallido", "rechazado_arca"}
                or int(parsed_lote.lote.id) != pair["lote_id"]
                or int(parsed_lote.lote.empresa_id) != company_id
                or parsed_lote.lote.estado not in ESTADOS_LOTE_SEGUROS_OMITIBLES
            ):
                raise MigrationError("Replay batch no coincide con su lote histórico")
        except MigrationError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise MigrationError(
                "Operación terminal empaquetada semánticamente inválida"
            ) from exc


def _validate_count_map(
    value: Any,
    *,
    expected_keys: list[str],
    label: str,
) -> dict[str, int]:
    """Valida un mapa exacto de conteos no negativos."""
    counts = _require_exact_keys(value, set(expected_keys), label=label)
    return {
        key: _require_nonnegative_int(counts[key], label=f"{label}.{key}")
        for key in expected_keys
    }


def _validate_manifest_certificate_files(
    *,
    package_root: Path,
    certificate_files: Any,
    certificate_rows: list[dict[str, Any]],
    active_certificates: int,
    member_paths: list[str],
) -> None:
    """Reconcilia certificados activos, archivos declarados y directorio real."""
    if not isinstance(certificate_files, dict):
        raise MigrationError("Shape inválido en certificate_files del manifest")
    for filename in certificate_files:
        validate_certificate_filename(filename)
    casefold_names = [str(name).casefold() for name in certificate_files]
    if len(casefold_names) != len(set(casefold_names)):
        raise MigrationError("Hay nombres de certificados colisionados en el manifest")

    expected_names: set[str] = set()
    active_rows = []
    for row in certificate_rows:
        activo = row.get("activo")
        if (
            not isinstance(activo, int)
            or isinstance(activo, bool)
            or activo not in {0, 1}
        ):
            raise MigrationError(
                "certificados.activo debe ser un booleano SQLite canónico 0/1"
            )
        if activo == 0:
            continue
        active_rows.append(row)
        raw_crt = row.get("archivo_crt")
        raw_key = row.get("archivo_key")
        if not isinstance(raw_crt, str) or not isinstance(raw_key, str):
            raise MigrationError(
                "Un certificado activo no declara nombres CRT/KEY válidos"
            )
        crt_filename = validate_certificate_filename(raw_crt)
        key_filename = validate_certificate_filename(raw_key)
        if not crt_filename.endswith(".crt") or not key_filename.endswith(".key"):
            raise MigrationError(
                "Un certificado activo no usa extensiones .crt/.key canónicas"
            )
        if crt_filename.casefold() == key_filename.casefold():
            raise MigrationError("El CRT y la KEY activos deben ser archivos distintos")
        expected_names.update({crt_filename, key_filename})
    if len(active_rows) != active_certificates:
        raise MigrationError("active_certificates no coincide con certificados.jsonl")
    if len(expected_names) != active_certificates * 2:
        raise MigrationError(
            "Los certificados activos no tienen pares CRT/KEY exclusivos"
        )
    if set(certificate_files) != expected_names:
        raise MigrationError(
            "certificate_files no coincide exactamente con los certificados activos"
        )

    certs_dir = package_root / "certs"
    if not certs_dir.is_dir():
        raise MigrationError("Falta el directorio certs del paquete")
    actual_names = {path.name for path in certs_dir.iterdir() if path.is_file()}
    if actual_names != expected_names or any(
        not path.is_file() for path in certs_dir.iterdir()
    ):
        raise MigrationError("El directorio certs contiene archivos faltantes o extra")

    for filename, raw_info in certificate_files.items():
        validate_certificate_filename(filename)
        info = _require_exact_keys(
            raw_info,
            vps_migration_v3.CERTIFICATE_FILE_INFO_KEYS,
            label=f"certificate_files.{filename}",
        )
        expected_path = f"certs/{filename}"
        relative_path = _require_canonical_package_path(
            info["path"],
            expected=expected_path,
            label=f"certificate_files.{filename}.path",
        )
        member_paths.append(relative_path)
        file_path = resolve_package_member(package_root, relative_path)
        if not file_path.is_file():
            raise MigrationError(f"Falta archivo del paquete: {relative_path}")
        expected_bytes = _require_nonnegative_int(
            info["bytes"], label=f"certificate_files.{filename}.bytes"
        )
        expected_sha = _require_sha256(
            info["sha256"], label=f"certificate_files.{filename}.sha256"
        )
        if file_path.stat().st_size != expected_bytes:
            raise MigrationError(f"Tamaño inválido en {relative_path}")
        if sha256_file(file_path) != expected_sha:
            raise MigrationError(f"Checksum inválido en {relative_path}")


@_format_context
def load_and_verify_manifest(package_dir: Path) -> dict[str, Any]:
    """Despacha el loader estricto según la versión declarada del paquete."""
    package_root = package_dir.resolve()
    manifest_path = package_root / "manifest.json"
    try:
        raw_manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        raise MigrationError("No se pudo seleccionar el contrato del manifest") from exc
    if not isinstance(raw_manifest, dict):
        raise MigrationError("Shape inválido en top-level del manifest")
    contract = select_import_contract(raw_manifest)
    if contract.package_version == vps_migration_v3.PACKAGE_VERSION:
        return _load_and_verify_manifest_v3(package_root)
    if set(raw_manifest) == set(vps_migration_v3.MANIFEST_TOP_LEVEL_KEYS):
        raise MigrationError("Versión de paquete incompatible con el manifest v3")
    return _load_and_verify_manifest_v4(package_root)


def _load_and_verify_manifest_v3(package_dir: Path) -> dict[str, Any]:
    """Carga y valida integralmente el contrato inmutable del paquete v3."""
    try:
        package_root = package_dir.resolve()
        if not package_root.is_dir():
            raise MigrationError(f"No existe el paquete: {package_root}")
        manifest_path = package_root / "manifest.json"
        if not manifest_path.is_file():
            raise MigrationError(f"No existe manifest.json en {package_root}")
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
        if not isinstance(manifest, dict):
            raise MigrationError("Shape inválido en top-level del manifest")
        contract = select_import_contract(manifest)
        manifest = _require_exact_keys(
            manifest,
            vps_migration_v3.MANIFEST_TOP_LEVEL_KEYS,
            label="top-level",
        )
        if manifest["scope"] != vps_migration_v3.SCOPE:
            raise MigrationError("El paquete no corresponde al alcance esperado")
        if manifest["alembic_version"] != contract.alembic_head:
            raise MigrationError("El head Alembic del manifest no coincide con v3")
        created_at = datetime.fromisoformat(str(manifest["created_at"]))
        if (
            not isinstance(manifest["created_at"], str)
            or created_at.tzinfo is None
            or created_at.utcoffset() != timezone.utc.utcoffset(created_at)
            or manifest["created_at"] != created_at.isoformat()
        ):
            raise MigrationError("created_at debe ser un timestamp UTC canónico")
        if manifest["included_tables"] != list(contract.included_tables):
            raise MigrationError("included_tables no coincide con el contrato v3")
        if manifest["excluded_tables"] != list(contract.excluded_tables):
            raise MigrationError("excluded_tables no coincide con el contrato v3")
        if manifest["target_empty_tables"] != list(contract.target_empty_tables):
            raise MigrationError("target_empty_tables no coincide con el contrato v3")
        if manifest["required_env_keys"] != list(vps_migration_v3.REQUIRED_ENV_KEYS):
            raise MigrationError("required_env_keys no coincide con el contrato v3")
        if manifest["notes"] != list(vps_migration_v3.PACKAGE_NOTES):
            raise MigrationError("notes no coincide con el contrato v3")

        included_counts = _validate_count_map(
            manifest["included_counts"],
            expected_keys=list(contract.included_tables),
            label="included_counts",
        )
        excluded_counts = _validate_count_map(
            manifest["excluded_counts"],
            expected_keys=list(contract.excluded_tables),
            label="excluded_counts",
        )
        active_certificates = _require_nonnegative_int(
            manifest["active_certificates"], label="active_certificates"
        )

        safe_omitted = _require_exact_keys(
            manifest["safe_omitted"],
            vps_migration_v3.SAFE_OMITTED_KEYS,
            label="safe_omitted",
        )
        for key in vps_migration_v3.SAFE_OMITTED_KEYS - {"excluded_counts"}:
            _require_nonnegative_int(safe_omitted[key], label=f"safe_omitted.{key}")
        _validate_count_map(
            safe_omitted["excluded_counts"],
            expected_keys=list(contract.excluded_tables),
            label="safe_omitted.excluded_counts",
        )
        validate_safe_omitted_counts(
            safe_omitted,
            included_counts=included_counts,
            excluded_counts=excluded_counts,
        )

        normalizations = _require_exact_keys(
            manifest["normalizations"],
            {vps_migration_v3.OPERATION_LOTE_NORMALIZATION_KEY},
            label="normalizations",
        )
        normalization = _require_exact_keys(
            normalizations[vps_migration_v3.OPERATION_LOTE_NORMALIZATION_KEY],
            vps_migration_v3.NORMALIZATION_INFO_KEYS,
            label=(
                "normalizations." f"{vps_migration_v3.OPERATION_LOTE_NORMALIZATION_KEY}"
            ),
        )
        if normalization["rule"] != vps_migration_v3.OPERATION_LOTE_NORMALIZATION_RULE:
            raise MigrationError("Regla de normalización lote_id no soportada")
        normalization_rows = _require_nonnegative_int(
            normalization["rows"], label="normalizations.lote_id.rows"
        )
        _require_sha256(normalization["sha256"], label="normalizations.lote_id.sha256")
        normalization_pairs = _validate_normalization_pairs(normalization["pairs"])
        if normalization_rows != safe_omitted["operaciones_lote_normalizado"]:
            raise MigrationError("La normalización lote_id no reconcilia safe_omitted")

        source_barrier = _require_exact_keys(
            manifest["source_barrier"],
            vps_migration_v3.SOURCE_BARRIER_KEYS,
            label="source_barrier",
        )
        if (
            source_barrier["source_quiesced"] is not True
            or source_barrier["sqlite_transaction"] != "BEGIN IMMEDIATE"
        ):
            raise MigrationError("La barrera SQLite del manifest no es fail-closed")
        _require_nonnegative_int(
            source_barrier["data_version"], label="source_barrier.data_version"
        )

        data_files = _require_exact_keys(
            manifest["data_files"],
            set(contract.included_tables),
            label="data_files",
        )
        data_dir = package_root / "data"
        if not data_dir.is_dir():
            raise MigrationError("Falta el directorio data del paquete")
        expected_data_names = {f"{table}.jsonl" for table in contract.included_tables}
        actual_data_names = {path.name for path in data_dir.iterdir() if path.is_file()}
        if actual_data_names != expected_data_names or any(
            not path.is_file() for path in data_dir.iterdir()
        ):
            raise MigrationError(
                "El directorio data contiene archivos faltantes o extra"
            )

        member_paths: list[str] = []
        table_rows: dict[str, list[dict[str, Any]]] = {}
        for table_name in contract.included_tables:
            info = _require_exact_keys(
                data_files[table_name],
                vps_migration_v3.DATA_FILE_INFO_KEYS,
                label=f"data_files.{table_name}",
            )
            expected_path = f"data/{table_name}.jsonl"
            relative_path = _require_canonical_package_path(
                info["path"],
                expected=expected_path,
                label=f"data_files.{table_name}.path",
            )
            member_paths.append(relative_path)
            file_path = resolve_package_member(package_root, relative_path)
            if not file_path.is_file():
                raise MigrationError(f"Falta archivo del paquete: {relative_path}")
            expected_bytes = _require_nonnegative_int(
                info["bytes"], label=f"data_files.{table_name}.bytes"
            )
            expected_rows = _require_nonnegative_int(
                info["rows"], label=f"data_files.{table_name}.rows"
            )
            expected_sha = _require_sha256(
                info["sha256"], label=f"data_files.{table_name}.sha256"
            )
            if file_path.stat().st_size != expected_bytes:
                raise MigrationError(f"Tamaño inválido en {relative_path}")
            if sha256_file(file_path) != expected_sha:
                raise MigrationError(f"Checksum inválido en {relative_path}")
            rows = _read_manifest_jsonl_rows(file_path, table_name=table_name)
            if len(rows) != expected_rows or len(rows) != included_counts[table_name]:
                raise MigrationError(f"Conteo JSONL inválido en {table_name}")
            table_rows[table_name] = rows

        env_template = _require_exact_keys(
            manifest["env_template"],
            vps_migration_v3.ENV_TEMPLATE_INFO_KEYS,
            label="env_template",
        )
        env_relative_path = _require_canonical_package_path(
            env_template["path"],
            expected=vps_migration_v3.ENV_TEMPLATE_FILENAME,
            label="env_template.path",
        )
        member_paths.append(env_relative_path)
        env_path = resolve_package_member(package_root, env_relative_path)
        if not env_path.is_file():
            raise MigrationError("Falta la plantilla de entorno del paquete")
        if env_path.stat().st_size != _require_nonnegative_int(
            env_template["bytes"], label="env_template.bytes"
        ):
            raise MigrationError("Tamaño inválido en la plantilla de entorno")
        if sha256_file(env_path) != _require_sha256(
            env_template["sha256"], label="env_template.sha256"
        ):
            raise MigrationError("Checksum inválido en la plantilla de entorno")

        _validate_manifest_certificate_files(
            package_root=package_root,
            certificate_files=manifest["certificate_files"],
            certificate_rows=table_rows["certificados"],
            active_certificates=active_certificates,
            member_paths=member_paths,
        )
        path_casefold = [path.casefold() for path in member_paths]
        if len(path_casefold) != len(set(path_casefold)):
            raise MigrationError("El manifest contiene paths duplicados o colisionados")

        expected_root_entries = {
            "manifest.json",
            vps_migration_v3.ENV_TEMPLATE_FILENAME,
            "data",
            "certs",
        }
        if {path.name for path in package_root.iterdir()} != expected_root_entries:
            raise MigrationError("El paquete contiene miembros top-level inesperados")

        operation_rows = table_rows["operaciones_idempotentes"]
        _validate_operation_lote_normalization(
            normalization=normalization,
            pairs=normalization_pairs,
            operation_rows=operation_rows,
        )
        _validate_packaged_foreign_keys(table_rows)
        _validate_packaged_user_accesses(table_rows)
        _validate_packaged_rece_associations(table_rows)
        _validate_packaged_terminal_operations(
            table_rows=table_rows,
            normalization_pairs=normalization_pairs,
        )

        barrier = _require_exact_keys(
            manifest["idempotency_barrier"],
            vps_migration_v3.IDEMPOTENCY_BARRIER_KEYS,
            label="idempotency_barrier",
        )
        if (
            not isinstance(barrier["version"], int)
            or isinstance(barrier["version"], bool)
            or barrier["version"] != 1
            or barrier["algorithm"] != vps_migration_v3.IDEMPOTENCY_BARRIER_ALGORITHM
        ):
            raise MigrationError("Versión o algoritmo de barrera no soportado")
        _require_nonnegative_int(barrier["rows"], label="idempotency_barrier.rows")
        _require_sha256(barrier["sha256"], label="idempotency_barrier.sha256")
        expected_barrier = build_idempotency_barrier(
            source_barrier=source_barrier,
            normalization=normalization,
            operation_rows=operation_rows,
            association_rows=table_rows["operaciones_idempotentes_elegibilidad_rece"],
        )
        if barrier != expected_barrier:
            raise MigrationError("La barrera idempotente del manifest no verifica")
        return manifest
    except MigrationError:
        raise
    except (
        DecimalException,
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise MigrationError(
            "El manifest o sus archivos tienen JSON/schema inválido"
        ) from exc


def _load_and_verify_manifest_v4(package_dir: Path) -> dict[str, Any]:
    """Carga v4 y reconstruye clausura y barrera antes de tocar el destino."""
    try:
        package_root = package_dir.resolve()
        if not package_root.is_dir():
            raise MigrationError(f"No existe el paquete: {package_root}")
        manifest_path = package_root / "manifest.json"
        if not manifest_path.is_file():
            raise MigrationError(f"No existe manifest.json en {package_root}")
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicate_keys,
        )
        manifest = _require_exact_keys(
            manifest,
            set(_fiscal_package_format().MANIFEST_TOP_LEVEL_KEYS),
            label="top-level",
        )
        contract = select_import_contract(manifest)
        if contract.package_version != _fiscal_package_format().PACKAGE_VERSION:
            raise MigrationError("El manifest no corresponde al contrato v4")
        if manifest["scope"] != _fiscal_package_format().SCOPE:
            raise MigrationError("El paquete no corresponde al alcance esperado")
        if manifest["alembic_version"] != contract.alembic_head:
            raise MigrationError("El head Alembic del manifest no coincide con v4")
        created_at = datetime.fromisoformat(str(manifest["created_at"]))
        if (
            not isinstance(manifest["created_at"], str)
            or created_at.tzinfo is None
            or created_at.utcoffset() != timezone.utc.utcoffset(created_at)
            or manifest["created_at"] != created_at.isoformat()
        ):
            raise MigrationError("created_at debe ser un timestamp UTC canónico")

        expected_lists = {
            "complete_tables": contract.complete_tables,
            "filtered_tables": contract.filtered_tables,
            "regenerated_tables": contract.regenerated_tables,
            "included_tables": contract.included_tables,
            "excluded_tables": contract.excluded_tables,
            "target_empty_tables": contract.target_empty_tables,
        }
        for key, expected in expected_lists.items():
            if manifest[key] != list(expected):
                raise MigrationError(f"{key} no coincide con el contrato v4")
        if manifest["required_env_keys"] != list(vps_migration_v3.REQUIRED_ENV_KEYS):
            raise MigrationError("required_env_keys no coincide con el contrato v4")
        if manifest["notes"] != list(_fiscal_package_format().PACKAGE_NOTES):
            raise MigrationError("notes no coincide con el contrato v4")

        source_keys = list(
            contract.included_tables
            + contract.regenerated_tables
            + contract.excluded_tables
        )
        omitted_keys = list(contract.filtered_tables + contract.excluded_tables)
        source_counts = _validate_count_map(
            manifest["source_counts"],
            expected_keys=source_keys,
            label="source_counts",
        )
        included_counts = _validate_count_map(
            manifest["included_counts"],
            expected_keys=list(contract.included_tables),
            label="included_counts",
        )
        omitted_counts = _validate_count_map(
            manifest["omitted_counts"],
            expected_keys=omitted_keys,
            label="omitted_counts",
        )
        for table_name in contract.complete_tables:
            if source_counts[table_name] != included_counts[table_name]:
                raise MigrationError(f"La tabla completa {table_name} fue filtrada")
        for table_name in contract.filtered_tables:
            if source_counts[table_name] != (
                included_counts[table_name] + omitted_counts[table_name]
            ):
                raise MigrationError(f"La tabla filtrada {table_name} no reconcilia")
        for table_name in contract.excluded_tables:
            if source_counts[table_name] != omitted_counts[table_name]:
                raise MigrationError(f"La tabla excluida {table_name} no reconcilia")

        safe_omitted = _require_exact_keys(
            manifest["safe_omitted"],
            set(_fiscal_package_format().SAFE_OMITTED_KEYS),
            label="safe_omitted",
        )
        if (
            _require_nonnegative_int(
                safe_omitted["blockers"], label="safe_omitted.blockers"
            )
            != 0
        ):
            raise MigrationError("El paquete v4 declara bloqueos de seguridad")
        if (
            safe_omitted["source_counts"] != source_counts
            or safe_omitted["included_counts"] != included_counts
            or safe_omitted["omitted_counts"] != omitted_counts
        ):
            raise MigrationError("safe_omitted v4 no reconcilia los conteos")
        legacy_preflight = _require_exact_keys(
            safe_omitted["legacy_preflight"],
            set(vps_migration_v3.SAFE_OMITTED_KEYS),
            label="safe_omitted.legacy_preflight",
        )
        if (
            _require_nonnegative_int(
                legacy_preflight["blockers"],
                label="safe_omitted.legacy_preflight.blockers",
            )
            != 0
        ):
            raise MigrationError("La prevalidación legacy v4 declara bloqueos")
        _validate_count_map(
            legacy_preflight["excluded_counts"],
            expected_keys=list(vps_migration_v3.EXCLUDED_TABLES),
            label="safe_omitted.legacy_preflight.excluded_counts",
        )
        for key in vps_migration_v3.SAFE_OMITTED_KEYS - {
            "blockers",
            "excluded_counts",
        }:
            _require_nonnegative_int(
                legacy_preflight[key],
                label=f"safe_omitted.legacy_preflight.{key}",
            )

        normalizations = _require_exact_keys(
            manifest["normalizations"],
            {_fiscal_package_format().OPERATION_LOTE_NORMALIZATION_KEY},
            label="normalizations",
        )
        normalization = _require_exact_keys(
            normalizations[_fiscal_package_format().OPERATION_LOTE_NORMALIZATION_KEY],
            set(vps_migration_v3.NORMALIZATION_INFO_KEYS),
            label="normalizations.operaciones_idempotentes.lote_id",
        )
        if (
            normalization["rule"]
            != _fiscal_package_format().OPERATION_LOTE_NORMALIZATION_RULE
        ):
            raise MigrationError("Regla de normalización lote_id v4 no soportada")
        pairs = _validate_normalization_pairs(normalization["pairs"])
        if _require_nonnegative_int(
            normalization["rows"], label="normalizations.lote_id.rows"
        ) != len(pairs) or _require_sha256(
            normalization["sha256"], label="normalizations.lote_id.sha256"
        ) != _fiscal_package_format().canonical_sha256(
            pairs
        ):
            raise MigrationError("La normalización legacy v4 no verifica")

        closure = _require_exact_keys(
            manifest["closure"],
            set(_fiscal_package_format().CLOSURE_KEYS),
            label="closure",
        )
        if (
            _require_nonnegative_int(closure["version"], label="closure.version") != 1
            or closure["algorithm"] != _fiscal_package_format().CLOSURE_ALGORITHM
        ):
            raise MigrationError("Versión o algoritmo de clausura v4 no soportado")
        for key in (
            "operation_ids",
            "root_operation_ids",
            "preserved_lote_ids",
            "preserved_group_ids",
            "legacy_normalized_operation_ids",
            "attempt_ids",
            "guard_ids",
            "generation_ids",
            "block_ids",
            "member_ids",
        ):
            if _strict_positive_id_list(closure[key]) is None:
                raise MigrationError(f"Lista de IDs no canónica en closure.{key}")
        group_counts = closure["group_counts_by_lote"]
        if not isinstance(group_counts, dict) or set(group_counts) != {
            str(value) for value in closure["preserved_lote_ids"]
        }:
            raise MigrationError("group_counts_by_lote no coincide con los lotes")
        for lote_id, count in group_counts.items():
            if str(int(lote_id)) != lote_id or int(lote_id) <= 0:
                raise MigrationError("group_counts_by_lote contiene un lote inválido")
            _require_nonnegative_int(
                count, label=f"closure.group_counts_by_lote.{lote_id}"
            )
        closure_hash = _require_sha256(closure["sha256"], label="closure.sha256")
        closure_payload = {
            key: value for key, value in closure.items() if key != "sha256"
        }
        if closure_hash != _fiscal_package_format().canonical_sha256(closure_payload):
            raise MigrationError("El hash de clausura v4 no verifica")

        source_barrier = _require_exact_keys(
            manifest["source_barrier"],
            set(vps_migration_v3.SOURCE_BARRIER_KEYS),
            label="source_barrier",
        )
        if (
            source_barrier["source_quiesced"] is not True
            or source_barrier["sqlite_transaction"] != "BEGIN IMMEDIATE"
        ):
            raise MigrationError("La barrera SQLite del manifest no es fail-closed")
        _require_nonnegative_int(
            source_barrier["data_version"], label="source_barrier.data_version"
        )

        data_files = _require_exact_keys(
            manifest["data_files"], set(contract.included_tables), label="data_files"
        )
        data_dir = package_root / "data"
        if not data_dir.is_dir():
            raise MigrationError("Falta el directorio data del paquete")
        expected_data_names = {f"{table}.jsonl" for table in contract.included_tables}
        actual_data_names = {path.name for path in data_dir.iterdir() if path.is_file()}
        if actual_data_names != expected_data_names or any(
            not path.is_file() for path in data_dir.iterdir()
        ):
            raise MigrationError(
                "El directorio data contiene archivos faltantes o extra"
            )

        member_paths: list[str] = []
        table_rows: dict[str, list[dict[str, Any]]] = {}
        for table_name in contract.included_tables:
            info = _require_exact_keys(
                data_files[table_name],
                set(vps_migration_v3.DATA_FILE_INFO_KEYS),
                label=f"data_files.{table_name}",
            )
            relative_path = _require_canonical_package_path(
                info["path"],
                expected=f"data/{table_name}.jsonl",
                label=f"data_files.{table_name}.path",
            )
            member_paths.append(relative_path)
            file_path = resolve_package_member(package_root, relative_path)
            expected_bytes = _require_nonnegative_int(
                info["bytes"], label=f"data_files.{table_name}.bytes"
            )
            expected_rows = _require_nonnegative_int(
                info["rows"], label=f"data_files.{table_name}.rows"
            )
            expected_sha = _require_sha256(
                info["sha256"], label=f"data_files.{table_name}.sha256"
            )
            if (
                not file_path.is_file()
                or file_path.stat().st_size != expected_bytes
                or sha256_file(file_path) != expected_sha
            ):
                raise MigrationError(f"Archivo de datos inválido: {relative_path}")
            rows = _read_manifest_jsonl_rows_v4(file_path, table_name=table_name)
            if len(rows) != expected_rows or len(rows) != included_counts[table_name]:
                raise MigrationError(f"Conteo JSONL inválido en {table_name}")
            table_rows[table_name] = rows

        active_certificates = _require_nonnegative_int(
            manifest["active_certificates"], label="active_certificates"
        )
        env_template = _require_exact_keys(
            manifest["env_template"],
            set(vps_migration_v3.ENV_TEMPLATE_INFO_KEYS),
            label="env_template",
        )
        env_relative_path = _require_canonical_package_path(
            env_template["path"],
            expected=vps_migration_v3.ENV_TEMPLATE_FILENAME,
            label="env_template.path",
        )
        member_paths.append(env_relative_path)
        env_path = resolve_package_member(package_root, env_relative_path)
        if (
            not env_path.is_file()
            or env_path.stat().st_size
            != _require_nonnegative_int(
                env_template["bytes"], label="env_template.bytes"
            )
            or sha256_file(env_path)
            != _require_sha256(env_template["sha256"], label="env_template.sha256")
        ):
            raise MigrationError("La plantilla de entorno del paquete es inválida")
        _validate_manifest_certificate_files(
            package_root=package_root,
            certificate_files=manifest["certificate_files"],
            certificate_rows=table_rows["certificados"],
            active_certificates=active_certificates,
            member_paths=member_paths,
        )
        path_casefold = [path.casefold() for path in member_paths]
        if len(path_casefold) != len(set(path_casefold)):
            raise MigrationError("El manifest contiene paths duplicados o colisionados")
        if {path.name for path in package_root.iterdir()} != {
            "manifest.json",
            vps_migration_v3.ENV_TEMPLATE_FILENAME,
            "data",
            "certs",
        }:
            raise MigrationError("El paquete contiene miembros top-level inesperados")

        if source_counts[contract.regenerated_tables[0]] != (
            2 * included_counts["empresas"]
        ):
            raise MigrationError(
                "La coordinación fuente v4 no tiene cardinalidad exacta"
            )
        _validate_packaged_user_accesses(table_rows)
        validate_rece_ledger_rows(table_rows)
        _validate_packaged_rece_associations(table_rows)
        validate_v4_graph(table_rows, normalization=normalization, closure=closure)

        barrier = _require_exact_keys(
            manifest["idempotency_barrier"],
            set(_fiscal_package_format().BARRIER_KEYS),
            label="idempotency_barrier",
        )
        if (
            _require_nonnegative_int(
                barrier["version"], label="idempotency_barrier.version"
            )
            != 2
            or barrier["algorithm"] != _fiscal_package_format().BARRIER_ALGORITHM
        ):
            raise MigrationError("Versión o algoritmo de barrera v4 no soportado")
        _require_nonnegative_int(barrier["rows"], label="idempotency_barrier.rows")
        _require_sha256(barrier["sha256"], label="idempotency_barrier.sha256")
        expected_barrier = build_v4_idempotency_barrier(
            source_barrier=source_barrier,
            normalization=normalization,
            closure=closure,
            rows=table_rows,
        )
        if barrier != expected_barrier:
            raise MigrationError("La barrera idempotente v4 del manifest no verifica")
        return manifest
    except MigrationError:
        raise
    except (
        DecimalException,
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise MigrationError(
            "El manifest v4 o sus archivos tienen schema inválido"
        ) from exc


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
    try:
        lines = env_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise MigrationError(
            "No se pudo leer .env.production con UTF-8 válido"
        ) from exc
    values: dict[str, str] = {}
    for line in lines:
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
    package_dir: Path,
    manifest: dict[str, Any],
    target_password: str,
    package_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Valida cifrado, identidad y metadata de cada par activo del paquete."""
    for row in _active_certificate_rows_with_company(package_rows):
        crt_filename = validate_certificate_filename(str(row["archivo_crt"]))
        key_filename = validate_certificate_filename(str(row["archivo_key"]))
        try:
            crt_info = manifest["certificate_files"][crt_filename]
            key_info = manifest["certificate_files"][key_filename]
        except (KeyError, TypeError) as exc:
            raise MigrationError(
                "Un certificado activo no tiene su par declarado en el manifest"
            ) from exc
        _validate_packaged_active_certificate_pair(
            row=row,
            cert_path=resolve_package_member(package_dir, crt_info["path"]),
            key_path=resolve_package_member(package_dir, key_info["path"]),
            target_password=target_password,
        )


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


@_format_context
def ensure_target_database_ready(
    conn,
    manifest: dict[str, Any],
    contract: vps_migration_v3.ImportContract | None = None,
) -> None:
    """Valida que PostgreSQL esté migrada y sin datos operativos."""
    selected = contract or select_import_contract(manifest)
    validate_target_alembic_head(conn, manifest, selected)
    if selected.package_version == _fiscal_package_format().PACKAGE_VERSION:
        for table_name in selected.included_tables:
            validate_v4_target_table_contract(
                table_name,
                Base.metadata.tables[table_name],
            )
    target_empty_tables = (
        selected.target_empty_tables + selected.adapter_target_empty_tables
    )
    non_empty = {
        table_name: scalar_count(conn, table_name) for table_name in target_empty_tables
    }
    dirty = {table: count for table, count in non_empty.items() if count}
    if dirty:
        raise MigrationError(
            "La base destino no está limpia. Tablas con datos: "
            + ", ".join(f"{table}={count}" for table, count in dirty.items())
        )
    validate_canonical_target_seeds(conn)


def lock_target_tables_for_import(
    conn,
    contract: vps_migration_v3.ImportContract | None = None,
) -> None:
    """Serializa importadores y bloquea escrituras hasta confirmar postflight."""
    selected = contract or vps_migration_v3.V3_CONTRACT
    table_names = sorted(
        {
            "alembic_version",
            *selected.included_tables,
            *selected.excluded_tables,
            *selected.adapter_target_empty_tables,
            *selected.target_empty_tables,
        }
    )
    quoted = ", ".join(f'"{table_name}"' for table_name in table_names)
    conn.execute(text(f"LOCK TABLE {quoted} IN SHARE ROW EXCLUSIVE MODE"))


def _load_canonical_alembic_seed_config() -> dict[str, Any]:
    """Lee con AST el literal del seed versionado sin ejecutar la migración."""
    migration_path = (
        default_backend_dir()
        / "alembic"
        / "versions"
        / "a6b7c8d9e0f1_formatos_importacion.py"
    )
    try:
        module = ast.parse(migration_path.read_text(encoding="utf-8"))
        for statement in module.body:
            if not isinstance(statement, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name) and target.id == "FORMATO_BANCARIO_CONFIG"
                for target in statement.targets
            ):
                value = ast.literal_eval(statement.value)
                if isinstance(value, dict):
                    return value
    except (OSError, SyntaxError, ValueError) as exc:
        raise MigrationError("No se pudo leer el seed Alembic canónico") from exc
    raise MigrationError("La migración no declara FORMATO_BANCARIO_CONFIG")


def validate_canonical_target_seeds(conn) -> None:
    """Autoriza borrar solo el seed global exacto creado por Alembic."""
    tables = Base.metadata.tables
    formatos_table = tables["formatos_importacion"]
    versiones_table = tables["formatos_importacion_versiones"]
    campos_table = tables["formatos_importacion_campos"]
    reglas_table = tables["formatos_importacion_reglas"]
    formatos = list(
        conn.execute(select(formatos_table).order_by(formatos_table.c.id)).mappings()
    )
    versiones = list(
        conn.execute(select(versiones_table).order_by(versiones_table.c.id)).mappings()
    )
    campos = list(
        conn.execute(select(campos_table).order_by(campos_table.c.id)).mappings()
    )
    reglas = list(
        conn.execute(select(reglas_table).order_by(reglas_table.c.id)).mappings()
    )
    config = _load_canonical_alembic_seed_config()
    expected_headers = {
        "requeridos": ["Creditos", "Pto Vta"],
        "opcionales": [
            "Fecha",
            "Leyendas Adicionales1",
            "Leyendas Adicionales2",
        ],
    }
    if len(formatos) != 1 or len(versiones) != 1 or len(reglas) != 1:
        raise MigrationError("El destino no conserva el seed Alembic exacto")
    formato = formatos[0]
    version = versiones[0]
    regla = reglas[0]
    if not (
        formato["nombre"] == "Extracto bancario - creditos IVA exento"
        and formato["descripcion"]
        == (
            "Formato global para extractos donde Creditos es el importe, "
            "Leyendas Adicionales1 el receptor, Leyendas Adicionales2 el "
            "documento y Pto Vta el punto de venta."
        )
        and formato["alcance"] == "global"
        and formato["activo"] is True
        and formato["empresa_id"] is None
        and int(version["formato_id"]) == int(formato["id"])
        and int(version["version"]) == 1
        and version["estado"] == "vigente"
        and version["configuracion_json"] == config
        and version["headers_firma_json"] == expected_headers
        and int(regla["version_id"]) == int(version["id"])
        and regla["nombre"] == "Cada fila genera un comprobante"
        and regla["tipo"] == "agrupacion"
        and regla["configuracion_json"] == {"modo": "fila"}
        and int(regla["orden"]) == 1
        and regla["activo"] is True
    ):
        raise MigrationError("El seed global del destino fue modificado")

    expected_fields = []
    for field_name, field_config in config["campos"].items():
        expected_fields.append(
            {
                "campo_destino": field_name,
                "origen_tipo": field_config.get("origen", "header"),
                "encabezado": (field_config.get("encabezados") or [None])[0],
                "alias_json": field_config.get("encabezados"),
                "letra_columna": None,
                "indice_columna": None,
                "valor_constante_json": field_config.get("valor"),
                "requerido": bool(field_config.get("requerido", False)),
                "transformacion": field_config.get("transformacion"),
                "valor_default_json": field_config.get("default"),
            }
        )
    actual_fields = [
        {
            "campo_destino": row["campo_destino"],
            "origen_tipo": row["origen_tipo"],
            "encabezado": row["encabezado"],
            "alias_json": row["alias_json"],
            "letra_columna": row["letra_columna"],
            "indice_columna": row["indice_columna"],
            "valor_constante_json": row["valor_constante_json"],
            "requerido": row["requerido"],
            "transformacion": row["transformacion"],
            "valor_default_json": row["valor_default_json"],
        }
        for row in campos
        if int(row["version_id"]) == int(version["id"])
    ]
    if sorted(actual_fields, key=lambda row: row["campo_destino"]) != sorted(
        expected_fields,
        key=lambda row: row["campo_destino"],
    ):
        raise MigrationError("Los campos del seed Alembic fueron modificados")


def clear_seeded_included_tables(
    conn,
    contract: vps_migration_v3.ImportContract | None = None,
) -> None:
    """Limpia tablas incluidas para reemplazar seeds por datos del paquete."""
    selected = contract or vps_migration_v3.V3_CONTRACT
    for table_name in reversed(selected.seeded_included_tables):
        conn.execute(Base.metadata.tables[table_name].delete())


def read_database_rows(conn, table_name: str) -> list[dict[str, Any]]:
    """Lee el estado transaccional de una tabla incluida en orden estable."""
    table = Base.metadata.tables[table_name]
    statement = select(table)
    primary_key = _fiscal_package_format().PRIMARY_KEYS.get(
        table_name,
        vps_migration_v3.PRIMARY_KEYS.get(table_name, ()),
    )
    if primary_key:
        statement = statement.order_by(*(table.c[name] for name in primary_key))
    return [dict(row) for row in conn.execute(statement).mappings()]


def canonicalize_table_rows(
    table_name: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Canoniza tipos SQLite/PostgreSQL para comparar contenido sin coerciones."""
    table = Base.metadata.tables[table_name]
    canonical_rows: list[dict[str, Any]] = []
    for row in rows:
        canonical: dict[str, Any] = {}
        for column in table.columns:
            if (
                column.name == "cotizacion_busqueda"
                and _fiscal_package_format().PACKAGE_VERSION == 4
            ):
                if (
                    column.name in row
                    and row[column.name]
                    != _a01_destination_row(table_name, row)[column.name]
                ):
                    raise MigrationError("La clave auxiliar A-01 no verifica")
                continue
            value = row[column.name]
            if value is None:
                canonical[column.name] = None
            elif isinstance(column.type, Boolean):
                canonical[column.name] = bool(value)
            elif isinstance(column.type, DateTime):
                parsed = (
                    value
                    if isinstance(value, datetime)
                    else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                )
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone(timezone.utc)
                canonical[column.name] = parsed.isoformat()
            elif isinstance(column.type, Date):
                parsed_date = (
                    value
                    if isinstance(value, date)
                    else date.fromisoformat(str(value)[:10])
                )
                canonical[column.name] = parsed_date.isoformat()
            elif isinstance(column.type, (ExactDecimal, ExactAmount, ExactInteger)):
                canonical[column.name] = encode_decimal(Decimal(str(value)))
            elif isinstance(column.type, Numeric):
                canonical[column.name] = format(Decimal(str(value)).normalize(), "f")
            elif isinstance(column.type, JSON):
                json_value = json.loads(value) if isinstance(value, str) else value
                canonical[column.name] = json.dumps(
                    json_value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                    default=str,
                )
            else:
                canonical[column.name] = value
        canonical_rows.append(canonical)
    canonical_rows.sort(
        key=lambda row: json.dumps(
            row,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return canonical_rows


def validate_rece_ledger_rows(
    table_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Valida continuidad, ownership y cabeza máxima del ledger importado."""
    points = {int(row["id"]): row for row in table_rows["puntos_venta"]}
    revisions_by_identity: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
    revisions_by_id: dict[int, dict[str, Any]] = {}
    for revision in table_rows["puntos_venta_elegibilidad_rece_revisiones"]:
        try:
            point = points[int(revision["punto_venta_id"])]
            identity = (
                int(revision["empresa_id"]),
                int(revision["punto_venta_id"]),
                str(revision["ambiente"]),
            )
            if (
                int(point["empresa_id"]) != identity[0]
                or identity[2] not in AMBIENTES_RECE
                or int(revision["revision"]) <= 0
                or int(revision["punto_revision_fiscal"]) <= 0
                or int(revision["punto_revision_fiscal"])
                > int(point["revision_fiscal"])
            ):
                raise MigrationError(
                    "El ledger RECE importado tiene ownership inválido"
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise MigrationError("El ledger RECE importado es inválido") from exc
        revisions_by_identity.setdefault(identity, []).append(revision)
        revisions_by_id[int(revision["id"])] = revision

    heads_by_identity: dict[tuple[int, int, str], dict[str, Any]] = {}
    for head in table_rows["puntos_venta_elegibilidad_rece_actual"]:
        identity = (
            int(head["empresa_id"]),
            int(head["punto_venta_id"]),
            str(head["ambiente"]),
        )
        if identity in heads_by_identity:
            raise MigrationError("El ledger RECE importado duplica una cabeza")
        heads_by_identity[identity] = head

    expected_identities = {
        (int(point["empresa_id"]), point_id, environment)
        for point_id, point in points.items()
        for environment in sorted(AMBIENTES_RECE)
    }
    if (
        set(revisions_by_identity) != expected_identities
        or set(heads_by_identity) != expected_identities
    ):
        raise MigrationError("El ledger RECE no tiene dos ambientes por punto")
    for identity in expected_identities:
        revisions = sorted(
            revisions_by_identity[identity],
            key=lambda row: int(row["revision"]),
        )
        numbers = [int(row["revision"]) for row in revisions]
        if numbers != list(range(1, len(revisions) + 1)):
            raise MigrationError("El ledger RECE importado tiene huecos")
        fiscal_revisions = [int(row["punto_revision_fiscal"]) for row in revisions]
        if fiscal_revisions != sorted(fiscal_revisions):
            raise MigrationError("El ledger RECE importado retrocede fiscalmente")
        head = heads_by_identity[identity]
        pointed = revisions_by_id.get(int(head["revision_actual_id"]))
        if pointed is None or int(pointed["id"]) != int(revisions[-1]["id"]):
            raise MigrationError("La cabeza RECE no apunta a la revisión máxima")


@_format_context
def validate_target_alembic_head(
    conn,
    manifest: dict[str, Any],
    contract: vps_migration_v3.ImportContract | None = None,
) -> None:
    """Exige destino en el head vigente y paquete v3 en su head histórico."""
    selected = contract or select_import_contract(manifest)
    repo_head = get_repo_alembic_head()
    versions = list(
        conn.execute(
            text("SELECT version_num FROM alembic_version ORDER BY version_num")
        ).scalars()
    )
    if versions != [repo_head]:
        raise MigrationError(
            "Repo y destino no comparten un único head Alembic vigente"
        )
    if manifest["alembic_version"] != selected.alembic_head:
        raise MigrationError("El paquete v3 no conserva su head Alembic histórico")


def regenerate_v3_coordinators(conn) -> None:
    """Regenera ambos ambientes técnicos por empresa con revisión cero."""
    conn.execute(
        text(
            "INSERT INTO lotes_duplicados_coordinacion "
            "(empresa_id, ambiente, revision, updated_at) "
            "SELECT id, ambiente, 0, CURRENT_TIMESTAMP FROM empresas "
            "CROSS JOIN (VALUES ('homologacion'), ('produccion')) "
            "AS ambientes(ambiente)"
        )
    )


def validate_v3_coordinators(conn, company_rows: list[dict[str, Any]]) -> None:
    """Acredita que el destino regeneró sólo los coordinadores previstos."""
    rows = list(
        conn.execute(
            text(
                "SELECT empresa_id, ambiente, revision "
                "FROM lotes_duplicados_coordinacion "
                "ORDER BY empresa_id, ambiente"
            )
        ).mappings()
    )
    actual = [
        {
            "empresa_id": int(row["empresa_id"]),
            "ambiente": str(row["ambiente"]),
            "revision": int(row["revision"]),
        }
        for row in rows
    ]
    expected = sorted(
        vps_migration_v3.coordinator_plan(company_rows),
        key=lambda row: (row["empresa_id"], row["ambiente"]),
    )
    if actual != expected:
        raise MigrationError("Los coordinadores PF-13 regenerados no verifican")


@_format_context
def validate_imported_database(
    conn,
    manifest: dict[str, Any],
    package_rows: dict[str, list[dict[str, Any]]],
    contract: vps_migration_v3.ImportContract | None = None,
) -> None:
    """Ejecuta postflight exhaustivo sobre la transacción aún no confirmada."""
    selected = contract or select_import_contract(manifest)
    if selected.package_version == _fiscal_package_format().PACKAGE_VERSION:
        _validate_imported_database_v4(conn, manifest, package_rows, selected)
        return
    validate_target_alembic_head(conn, manifest, selected)
    actual_rows: dict[str, list[dict[str, Any]]] = {}
    for table_name in selected.included_tables:
        rows = read_database_rows(conn, table_name)
        if len(rows) != manifest["included_counts"][table_name]:
            raise MigrationError(
                f"Conteo inesperado en {table_name} durante postflight"
            )
        if canonicalize_table_rows(
            table_name,
            rows,
        ) != canonicalize_table_rows(table_name, package_rows[table_name]):
            raise MigrationError(
                f"El contenido importado de {table_name} difiere del paquete"
            )
        actual_rows[table_name] = rows
    for table_name in selected.excluded_tables:
        if scalar_count(conn, table_name) != 0:
            raise MigrationError(f"La tabla excluida {table_name} no quedó vacía")
    for table_name in selected.adapter_target_empty_tables[1:]:
        if scalar_count(conn, table_name) != 0:
            raise MigrationError(
                f"El adaptador v3 inventó evidencia PF-13 en {table_name}"
            )
    validate_v3_coordinators(conn, actual_rows["empresas"])

    normalization = manifest["normalizations"][OPERATION_LOTE_NORMALIZATION_KEY]
    pairs = _validate_normalization_pairs(normalization["pairs"])
    _validate_operation_lote_normalization(
        normalization=normalization,
        pairs=pairs,
        operation_rows=actual_rows["operaciones_idempotentes"],
    )
    _validate_packaged_foreign_keys(actual_rows)
    _validate_packaged_user_accesses(actual_rows)
    validate_rece_ledger_rows(actual_rows)
    _validate_packaged_rece_associations(actual_rows)
    _validate_packaged_terminal_operations(
        table_rows=actual_rows,
        normalization_pairs=pairs,
    )
    expected_barrier = build_idempotency_barrier(
        source_barrier=manifest["source_barrier"],
        normalization=normalization,
        operation_rows=actual_rows["operaciones_idempotentes"],
        association_rows=actual_rows["operaciones_idempotentes_elegibilidad_rece"],
    )
    if manifest["idempotency_barrier"] != expected_barrier:
        raise MigrationError("La barrera idempotente restaurada no verifica")


@_format_context
def _validate_imported_database_v4(
    conn,
    manifest: dict[str, Any],
    package_rows: dict[str, list[dict[str, Any]]],
    contract: _fiscal_package_format().ImportContract,
) -> None:
    """Acredita contenido y grafo v4 antes de confirmar la transacción."""
    validate_target_alembic_head(conn, manifest, contract)
    actual_rows: dict[str, list[dict[str, Any]]] = {}
    for table_name in contract.included_tables:
        rows = read_database_rows(conn, table_name)
        if len(rows) != manifest["included_counts"][table_name]:
            raise MigrationError(
                f"Conteo inesperado en {table_name} durante postflight v4"
            )
        if canonicalize_table_rows(table_name, rows) != canonicalize_table_rows(
            table_name, package_rows[table_name]
        ):
            raise MigrationError(
                f"El contenido importado de {table_name} difiere del paquete v4"
            )
        actual_rows[table_name] = rows
    for table_name in contract.excluded_tables:
        if scalar_count(conn, table_name) != 0:
            raise MigrationError(f"La tabla excluida {table_name} no quedó vacía")
    validate_v3_coordinators(conn, actual_rows["empresas"])
    normalization = manifest["normalizations"][
        _fiscal_package_format().OPERATION_LOTE_NORMALIZATION_KEY
    ]
    validate_v4_graph(
        actual_rows,
        normalization=normalization,
        closure=manifest["closure"],
    )
    expected_barrier = build_v4_idempotency_barrier(
        source_barrier=manifest["source_barrier"],
        normalization=normalization,
        closure=manifest["closure"],
        rows=actual_rows,
    )
    if manifest["idempotency_barrier"] != expected_barrier:
        raise MigrationError("La barrera idempotente restaurada v4 no verifica")


def _target_type_matches_v3(column_type: Any, spec: Any) -> bool:
    """Compara el tipo físico de destino con la definición histórica exacta."""
    if spec.kind == "integer":
        return isinstance(column_type, (Integer, ExactInteger))
    if spec.kind == "boolean":
        return isinstance(column_type, Boolean)
    if spec.kind == "date":
        return isinstance(column_type, Date) and not isinstance(column_type, DateTime)
    if spec.kind == "datetime":
        return isinstance(column_type, DateTime) and bool(column_type.timezone) == bool(
            spec.timezone
        )
    if spec.kind == "numeric":
        if isinstance(column_type, (ExactDecimal, ExactAmount)):
            return True
        if not isinstance(column_type, Numeric):
            return False
        if column_type.precision is None or column_type.scale is None:
            return True
        return (
            column_type.scale >= spec.scale
            and column_type.precision - column_type.scale >= spec.precision - spec.scale
        )
    if spec.kind == "json":
        return isinstance(column_type, JSON)
    if spec.kind == "text":
        return isinstance(column_type, Text)
    if spec.kind == "string":
        return (
            isinstance(column_type, String)
            and not isinstance(column_type, Text)
            and (column_type.length is None or column_type.length >= spec.length)
        )
    return False


def validate_v3_target_table_contract(table_name: str, target_table: Table) -> None:
    """Exige que el ORM destino pueda representar v3 sin pérdida ni coerción."""
    historical_columns = vps_migration_v3.V3_COLUMNS[table_name]
    expected_target_columns = {
        *historical_columns,
        *vps_migration_v3.TARGET_NULL_ADDITIONS.get(table_name, ()),
    }
    if set(target_table.columns.keys()) != expected_target_columns:
        raise MigrationError(
            f"El destino vigente de {table_name} no coincide con la "
            "adaptación v3 explícita"
        )
    for column_name, spec in historical_columns.items():
        target_column = target_table.c[column_name]
        if (
            bool(target_column.nullable) != spec.nullable
            or bool(target_column.primary_key) != spec.primary_key
            or not (
                _target_type_matches_v3(target_column.type, spec)
                or (
                    table_name == "comprobante_items"
                    and column_name == "codigo"
                    and isinstance(target_column.type, Text)
                )
            )
        ):
            raise MigrationError(
                f"El tipo físico de {table_name}.{column_name} no representa v3"
            )
    for column_name in vps_migration_v3.TARGET_NULL_ADDITIONS.get(table_name, ()):
        if not target_table.c[column_name].nullable:
            raise MigrationError(
                f"La columna adaptada {table_name}.{column_name} no admite NULL"
            )

    actual_foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(
                tuple(element.target_fullname.rsplit(".", 1))
                for element in constraint.elements
            ),
        ): (constraint.ondelete, constraint.onupdate)
        for constraint in target_table.foreign_key_constraints
    }
    for foreign_key in vps_migration_v3.FOREIGN_KEYS.get(table_name, ()):
        remote_identity = tuple(
            (foreign_key.remote_table, column_name)
            for column_name in foreign_key.remote_columns
        )
        actions = actual_foreign_keys.get((foreign_key.local_columns, remote_identity))
        if actions != (foreign_key.ondelete, foreign_key.onupdate):
            raise MigrationError(
                f"La FK física de {table_name}{foreign_key.local_columns} "
                "no representa v3"
            )


def validate_v4_target_table_contract(table_name: str, target_table: Table) -> None:
    """Impide importar v4 si el ORM vigente divergió de sus columnas congeladas."""
    try:
        expected_columns = _fiscal_package_format().V4_COLUMNS[table_name]
    except KeyError as exc:
        raise MigrationError(
            f"Tabla no declarada por el contrato v4: {table_name}"
        ) from exc
    actual_columns = tuple(
        name
        for name in target_table.columns.keys()
        if not (
            _fiscal_package_format().PACKAGE_VERSION == 4
            and table_name == "lotes_comprobantes_grupos"
            and name == "cotizacion_busqueda"
        )
    )
    if actual_columns != expected_columns:
        raise MigrationError(
            f"El destino vigente de {table_name} no coincide con el contrato v4"
        )


@_format_context
def read_package_rows(
    package_dir: Path, manifest: dict[str, Any], table_name: str
) -> list[dict[str, Any]]:
    """Precarga una tabla usando exclusivamente el contrato declarado."""
    contract = select_import_contract(manifest)
    if contract.package_version == vps_migration_v3.PACKAGE_VERSION:
        return _read_package_rows_v3(package_dir, manifest, table_name)
    if table_name not in contract.included_tables:
        raise MigrationError(f"La tabla {table_name} no pertenece al contrato v4")
    file_path = resolve_package_member(
        package_dir, manifest["data_files"][table_name]["path"]
    )
    info = manifest["data_files"][table_name]
    try:
        raw = file_path.read_bytes()
        if len(raw) != int(info["bytes"]) or hashlib.sha256(raw).hexdigest() != str(
            info["sha256"]
        ):
            raise MigrationError(
                f"El JSONL de {table_name} cambió después de verificar el paquete"
            )
        rows = _parse_manifest_jsonl_lines_v4(
            raw.decode("utf-8").splitlines(keepends=True),
            table_name=table_name,
            convert=True,
        )
        if len(rows) != int(info["rows"]):
            raise MigrationError(f"Conteo JSONL inválido en {table_name}")
        return rows
    except MigrationError:
        raise
    except (
        DecimalException,
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise MigrationError(
            f"No se pudo precargar el JSONL v4 verificado de {table_name}"
        ) from exc


def _read_package_rows_v3(
    package_dir: Path, manifest: dict[str, Any], table_name: str
) -> list[dict[str, Any]]:
    """Precarga una tabla desde una única lectura ligada al manifest."""
    contract = select_import_contract(manifest)
    if table_name not in contract.included_tables:
        raise MigrationError(f"La tabla {table_name} no pertenece al contrato v3")
    file_path = resolve_package_member(
        package_dir, manifest["data_files"][table_name]["path"]
    )
    info = manifest["data_files"][table_name]
    try:
        raw = file_path.read_bytes()
        if len(raw) != int(info["bytes"]) or hashlib.sha256(raw).hexdigest() != str(
            info["sha256"]
        ):
            raise MigrationError(
                f"El JSONL de {table_name} cambió después de verificar el paquete"
            )
        text_content = raw.decode("utf-8")
        raw_rows = _parse_manifest_jsonl_lines(
            text_content.splitlines(keepends=True),
            table_name=table_name,
        )
        if len(raw_rows) != int(info["rows"]):
            raise MigrationError(f"Conteo JSONL inválido en {table_name}")
    except MigrationError:
        raise
    except (
        DecimalException,
        KeyError,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise MigrationError(
            f"No se pudo precargar el JSONL verificado de {table_name}"
        ) from exc
    try:
        target_table = Base.metadata.tables[table_name]
        validate_v3_target_table_contract(table_name, target_table)
        return [vps_migration_v3.adapt_row(table_name, row) for row in raw_rows]
    except (KeyError, TypeError, ValueError) as exc:
        raise MigrationError(f"No se pudo adaptar el JSONL v3 de {table_name}") from exc


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
    if isinstance(column_type, (Numeric, ExactDecimal, ExactAmount)):
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
        conn.execute(
            table.insert(),
            [
                _a01_destination_row(table_name, row)
                for row in rows[start : start + 500]
            ],
        )


def restore_deferred_columns(
    conn,
    package_rows: dict[str, list[dict[str, Any]]],
    contract: _fiscal_package_format().ImportContract,
) -> None:
    """Restaura aristas cíclicas v4 exactamente antes del postflight."""
    for table_name, column_names in contract.deferred_columns.items():
        table = Base.metadata.tables[table_name]
        primary_key = _fiscal_package_format().PRIMARY_KEYS[table_name]
        for row in package_rows[table_name]:
            values = {
                column_name: row[column_name]
                for column_name in column_names
                if row[column_name] is not None
            }
            if not values:
                continue
            if "updated_at" in table.c:
                values["updated_at"] = row["updated_at"]
            condition = None
            for column_name in primary_key:
                predicate = table.c[column_name] == row[column_name]
                condition = predicate if condition is None else condition & predicate
            result = conn.execute(table.update().where(condition).values(**values))
            if result.rowcount != 1:
                raise MigrationError(
                    f"No se pudo restaurar una arista diferida de {table_name}"
                )


def reset_postgres_sequences(
    conn,
    contract: vps_migration_v3.ImportContract | None = None,
) -> None:
    """Reinicia secuencias transaccionalmente al próximo ID libre."""
    selected = contract or vps_migration_v3.V3_CONTRACT
    for table_name in selected.sequence_tables:
        table = Base.metadata.tables[table_name]
        seq = conn.execute(
            text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
            {"table_name": table_name},
        ).scalar()
        if not seq:
            raise MigrationError(f"Falta la secuencia de ID para {table_name}")
        max_id = conn.execute(select(func.max(table.c.id))).scalar()
        next_id = int(max_id or 0) + 1
        quoted_sequence = quote_postgres_sequence_name(str(seq))
        conn.execute(text(f"ALTER SEQUENCE {quoted_sequence} RESTART WITH {next_id}"))


def quote_postgres_sequence_name(sequence_name: str) -> str:
    """Cita un identificador de secuencia simple devuelto por PostgreSQL."""
    parts = sequence_name.split(".")
    if not 1 <= len(parts) <= 2 or any(
        not part
        or not (part[0].isalpha() or part[0] == "_")
        or any(not (character.isalnum() or character == "_") for character in part)
        for part in parts
    ):
        raise MigrationError("PostgreSQL devolvió un nombre de secuencia inválido")
    return ".".join(f'"{part}"' for part in parts)


def verify_postgres_sequences(
    conn,
    contract: vps_migration_v3.ImportContract | None = None,
) -> None:
    """Comprueba que el próximo nextval será MAX(id)+1 sin consumirlo."""
    selected = contract or vps_migration_v3.V3_CONTRACT
    for table_name in selected.sequence_tables:
        table = Base.metadata.tables[table_name]
        seq = conn.execute(
            text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
            {"table_name": table_name},
        ).scalar()
        if not seq:
            raise MigrationError(f"Falta la secuencia de ID para {table_name}")
        max_id = conn.execute(select(func.max(table.c.id))).scalar()
        expected_next = int(max_id or 0) + 1
        quoted_sequence = quote_postgres_sequence_name(str(seq))
        state = conn.execute(
            text(f"SELECT last_value, is_called FROM {quoted_sequence}")
        ).one()
        if int(state[0]) != expected_next or bool(state[1]):
            raise MigrationError(
                f"La secuencia de {table_name} no quedó en el próximo ID libre"
            )


def plan_certificate_restore(
    package_dir: Path,
    manifest: dict[str, Any],
    target_certs_dir: Path,
) -> CertificateRestorePlan:
    """Construye y valida un plan de certificados sin tocar el filesystem."""
    target = target_certs_dir.resolve()
    if target.exists() and not target.is_dir():
        raise MigrationError("CERTS_PATH existe pero no es un directorio")
    items: list[CertificateRestoreItem] = []
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
        if dest.exists() and (
            not dest.is_file() or sha256_file(dest) != info["sha256"]
        ):
            raise MigrationError(
                f"Ya existe un certificado destino distinto: {dest.name}"
            )
        items.append(
            CertificateRestoreItem(
                filename=safe_filename,
                source=source,
                destination=dest,
                sha256=str(info["sha256"]),
                existed=dest.exists(),
            )
        )
    return CertificateRestorePlan(target_dir=target, items=tuple(items))


def materialize_certificate_restore(
    plan: CertificateRestorePlan,
    journal: CertificateRestoreJournal,
) -> None:
    """Materializa archivos atómicos y registra solo los creados por el intento."""
    plan.target_dir.mkdir(parents=True, exist_ok=True)
    for item in plan.items:
        if item.existed:
            if (
                not item.destination.is_file()
                or sha256_file(item.destination) != item.sha256
            ):
                raise MigrationError(
                    f"Cambió un certificado preexistente: {item.filename}"
                )
            continue
        if item.destination.exists():
            if (
                item.destination.is_file()
                and sha256_file(item.destination) == item.sha256
            ):
                continue
            raise MigrationError(f"Apareció una colisión al restaurar: {item.filename}")
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".factuflow-vps-{item.filename}.",
            suffix=".tmp",
            dir=plan.target_dir,
        )
        temp_stat = os.fstat(descriptor)
        temp_identity = (int(temp_stat.st_dev), int(temp_stat.st_ino))
        temp_path = Path(temp_name)
        journal.temporary[temp_path] = temp_identity
        try:
            copied_sha256 = _copy_certificate_source_to_descriptor(
                item.source,
                descriptor,
            )
            if copied_sha256 != item.sha256:
                raise MigrationError(f"Cambió el certificado fuente: {item.filename}")
            if item.filename.endswith(".key") and hasattr(os, "fchmod"):
                os.fchmod(descriptor, 0o600)
            _validate_temporary_descriptor_path(
                descriptor,
                temp_path,
                temp_identity,
            )
            expected_identity = temp_identity
            try:
                os.link(temp_path, item.destination)
                target_stat = os.lstat(item.destination)
                target_identity = (
                    int(target_stat.st_dev),
                    int(target_stat.st_ino),
                )
                if target_identity != expected_identity:
                    raise MigrationError(
                        f"Cambió el destino al restaurar: {item.filename}"
                    )
                journal.identities[item.destination] = expected_identity
                journal.created.append(item)
            except FileExistsError as exc:
                raise MigrationError(
                    f"Apareció una colisión al restaurar: {item.filename}"
                ) from exc
            except BaseException:
                was_recorded = item in journal.created
                if not was_recorded:
                    journal.identities[item.destination] = expected_identity
                    journal.created.append(item)
                try:
                    target_stat = os.stat(item.destination, follow_symlinks=False)
                    target_identity = (
                        int(target_stat.st_dev),
                        int(target_stat.st_ino),
                    )
                    owned_publication = target_identity == expected_identity
                except OSError:
                    raise
                if owned_publication:
                    try:
                        item.destination.unlink()
                    except OSError:
                        pass
                    else:
                        journal.identities.pop(item.destination, None)
                        if item in journal.created:
                            journal.created.remove(item)
                elif not was_recorded:
                    journal.identities.pop(item.destination, None)
                    if item in journal.created:
                        journal.created.remove(item)
                raise
        finally:
            close_error: OSError | None = None
            try:
                os.close(descriptor)
            except OSError as exc:
                close_error = exc
            try:
                current_temp_stat = os.lstat(temp_path)
            except FileNotFoundError:
                journal.temporary.pop(temp_path, None)
            else:
                current_temp_identity = (
                    int(current_temp_stat.st_dev),
                    int(current_temp_stat.st_ino),
                )
                if current_temp_identity != temp_identity:
                    journal.temporary.pop(temp_path, None)
                    raise MigrationError("Cambió un archivo temporal de restauración")
                temp_path.unlink()
                journal.temporary.pop(temp_path, None)
            if close_error is not None:
                raise close_error


def _copy_certificate_source_to_descriptor(
    source: Path,
    descriptor: int,
) -> str:
    """Copia y digesta una fuente sin reabrir el pathname temporal."""
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    with open(source, "rb") as source_handle, os.fdopen(
        os.dup(descriptor),
        "wb",
    ) as target_handle:
        while True:
            chunk = source_handle.read(1024 * 1024)
            if not chunk:
                break
            target_handle.write(chunk)
            digest.update(chunk)
        target_handle.flush()
        os.fsync(target_handle.fileno())
    return digest.hexdigest()


def _validate_temporary_descriptor_path(
    descriptor: int,
    temp_path: Path,
    expected_identity: tuple[int, int],
) -> None:
    """Exige que el pathname temporal siga apuntando al descriptor regular."""
    descriptor_stat = os.fstat(descriptor)
    path_stat = os.lstat(temp_path)
    descriptor_identity = (
        int(descriptor_stat.st_dev),
        int(descriptor_stat.st_ino),
    )
    path_identity = (int(path_stat.st_dev), int(path_stat.st_ino))
    if (
        descriptor_identity != expected_identity
        or path_identity != expected_identity
        or not stat.S_ISREG(descriptor_stat.st_mode)
        or not stat.S_ISREG(path_stat.st_mode)
    ):
        raise MigrationError("Cambió un archivo temporal de restauración")


def cleanup_certificate_restore(journal: CertificateRestoreJournal) -> bool:
    """Limpia archivos propios y conserva en journal los que no pudo retirar."""
    remaining_temporary: dict[Path, tuple[int, int]] = {}
    for temp_path, expected_identity in journal.temporary.items():
        try:
            try:
                temp_stat = os.lstat(temp_path)
            except FileNotFoundError:
                continue
            if (
                int(temp_stat.st_dev),
                int(temp_stat.st_ino),
            ) != expected_identity or not stat.S_ISREG(temp_stat.st_mode):
                remaining_temporary[temp_path] = expected_identity
                continue
            temp_path.unlink()
        except OSError:
            remaining_temporary[temp_path] = expected_identity
    journal.temporary = remaining_temporary

    remaining: list[CertificateRestoreItem] = []
    for item in reversed(journal.created):
        try:
            try:
                target_stat = os.lstat(item.destination)
            except FileNotFoundError:
                journal.identities.pop(item.destination, None)
                continue
            expected_identity = journal.identities.get(item.destination)
            current_identity = (int(target_stat.st_dev), int(target_stat.st_ino))
            if not stat.S_ISREG(target_stat.st_mode):
                remaining.append(item)
                continue
            if expected_identity is not None:
                if expected_identity != current_identity:
                    remaining.append(item)
                    continue
            elif sha256_file(item.destination) != item.sha256:
                remaining.append(item)
                continue
            item.destination.unlink()
            journal.identities.pop(item.destination, None)
        except OSError:
            remaining.append(item)
    journal.created[:] = list(reversed(remaining))
    journal.identities = {
        item.destination: journal.identities[item.destination]
        for item in journal.created
        if item.destination in journal.identities
    }
    return not remaining and not remaining_temporary


def restore_certificate_files(
    package_dir: Path, manifest: dict[str, Any], target_certs_dir: Path
) -> list[Path]:
    """Compatibilidad: planifica y copia certificados devolviendo los creados."""
    plan = plan_certificate_restore(package_dir, manifest, target_certs_dir)
    journal = CertificateRestoreJournal(created=[])
    try:
        materialize_certificate_restore(plan, journal)
    except BaseException:
        cleanup_certificate_restore(journal)
        raise
    return [item.destination for item in journal.created]


def verify_restored_certificate_files(
    certs_dir: Path,
    manifest: dict[str, Any],
    target_password: str,
    package_rows: dict[str, list[dict[str, Any]]],
) -> None:
    """Verifica checksums y contrato criptográfico de los pares restaurados."""
    restored_paths: dict[str, Path] = {}
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
        restored_paths[safe_filename] = path

    for row in _active_certificate_rows_with_company(package_rows):
        crt_filename = validate_certificate_filename(str(row["archivo_crt"]))
        key_filename = validate_certificate_filename(str(row["archivo_key"]))
        try:
            cert_path = restored_paths[crt_filename]
            key_path = restored_paths[key_filename]
        except KeyError as exc:
            raise MigrationError(
                "Un certificado activo restaurado no conserva su par exacto"
            ) from exc
        _validate_packaged_active_certificate_pair(
            row=row,
            cert_path=cert_path,
            key_path=key_path,
            target_password=target_password,
        )


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
    export.add_argument(
        "--source-quiesced",
        action="store_true",
        help="Confirma que backend y worker están detenidos durante la exportación.",
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
                source_quiesced=args.source_quiesced,
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
