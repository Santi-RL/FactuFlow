"""Contrato inmutable del paquete de migración PF-13 versión 4."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.scripts import vps_migration_v3

PACKAGE_VERSION = 4
ALEMBIC_HEAD = "a1b2c3d4e5f6"
SCOPE = "operacion_futura_con_comprobantes"
RELATION_FORMAT = "duplicados_relacion/1"
BARRIER_ALGORITHM = "sha256-json-c14n-v2"
CLOSURE_ALGORITHM = "sha256-json-c14n-v1"
OPERATION_LOTE_NORMALIZATION_KEY = "operaciones_idempotentes.lote_id"
OPERATION_LOTE_NORMALIZATION_RULE = (
    "set_null_only_legacy_omitted_lotes_with_group_inventory_sha256_v3"
)
PACKAGE_NOTES = (
    "Conserva lotes y grupos comparables PF-13 con su subgrafo fiscal; "
    "excluye filas, eventos, archivos temporales y evidencia descargable.",
    "Las claves privadas se re-cifraron con ARCA_PRIVATE_KEY_PASSWORD destino.",
    "La SQLite local debe conservarse como evidencia histórica privada.",
)

COMPLETE_TABLES = vps_migration_v3.INCLUDED_TABLES
FILTERED_TABLES = (
    "lotes_comprobantes",
    "lotes_comprobantes_grupos",
    "puntos_venta_guardas_emision_rece",
    "lotes_duplicados_evidencias",
    "lotes_duplicados_coincidencias",
    "lotes_duplicados_coincidencias_miembros",
    "intentos_emision_fiscal",
)
REGENERATED_TABLES = ("lotes_duplicados_coordinacion",)
EXCLUDED_TABLES = (
    "resoluciones_legacy_pf19_journal",
    "lotes_comprobantes_filas",
    "lotes_comprobantes_eventos",
    "eventos_sistema",
    "exportaciones_almacenamiento",
)
INCLUDED_TABLES = COMPLETE_TABLES + FILTERED_TABLES
SEEDED_INCLUDED_TABLES = vps_migration_v3.SEEDED_INCLUDED_TABLES
OPERATIONAL_COMPLETE_TABLES = tuple(
    table_name
    for table_name in COMPLETE_TABLES
    if table_name not in SEEDED_INCLUDED_TABLES
)
TARGET_EMPTY_TABLES = (
    OPERATIONAL_COMPLETE_TABLES + FILTERED_TABLES + REGENERATED_TABLES + EXCLUDED_TABLES
)
SEQUENCE_TABLES = vps_migration_v3.SEQUENCE_TABLES + FILTERED_TABLES

INSERT_ORDER = (
    "empresas",
    "usuarios",
    "usuario_emisor_acceso",
    "clientes",
    "puntos_venta",
    "puntos_venta_elegibilidad_rece_revisiones",
    "puntos_venta_elegibilidad_rece_actual",
    "certificados",
    "formatos_importacion",
    "formatos_importacion_versiones",
    "formatos_importacion_campos",
    "formatos_importacion_reglas",
    "perfiles_carga_masiva",
    "comprobantes",
    "comprobante_items",
    "lotes_comprobantes",
    "lotes_comprobantes_grupos",
    "operaciones_idempotentes",
    "operaciones_idempotentes_elegibilidad_rece",
    "puntos_venta_guardas_emision_rece",
    "lotes_duplicados_evidencias",
    "lotes_duplicados_coincidencias",
    "lotes_duplicados_coincidencias_miembros",
    "intentos_emision_fiscal",
)
DEFERRED_COLUMNS = {
    "lotes_comprobantes_grupos": ("duplicados_reserva_operacion_id",),
    "operaciones_idempotentes": (
        "operacion_raiz_id",
        "duplicados_generacion_id",
    ),
    "lotes_duplicados_evidencias": ("aceptacion_origen_generacion_id",),
}

V4_COLUMNS: dict[str, tuple[str, ...]] = {
    table_name: tuple(columns)
    for table_name, columns in (
        (table_name, vps_migration_v3.V3_COLUMNS[table_name])
        for table_name in COMPLETE_TABLES
    )
}
V4_COLUMNS["operaciones_idempotentes"] = (
    "id",
    "idempotency_key",
    "tipo_operacion",
    "payload_hash",
    "estado",
    "response_json",
    "error_json",
    "control_duplicados_json",
    "duplicados_version",
    "duplicados_generacion_id",
    "operacion_raiz_id",
    "solicitante_nombre_snapshot",
    "solicitud_emision_at",
    "rece_snapshot_hash",
    "lote_id",
    "created_at",
    "updated_at",
    "empresa_id",
    "usuario_id",
)
V4_COLUMNS.update(
    {
        "lotes_comprobantes": (
            "id",
            "nombre_archivo",
            "archivo_hash",
            "estado",
            "modo_procesamiento",
            "procesamiento_async",
            "total_filas",
            "total_grupos",
            "grupos_validos",
            "grupos_con_error",
            "grupos_emitidos",
            "grupos_fallidos",
            "grupos_reconciliados_externos",
            "grupos_descartados",
            "mensaje_resumen",
            "metadata_json",
            "mapeo_usado_json",
            "headers_detectados_json",
            "started_at",
            "finished_at",
            "compactado_at",
            "created_at",
            "updated_at",
            "empresa_id",
            "usuario_id",
            "formato_importacion_id",
            "formato_importacion_version_id",
        ),
        "lotes_comprobantes_grupos": (
            "id",
            "comprobante_ref",
            "orden",
            "estado",
            "tipo_comprobante",
            "punto_venta_numero",
            "cliente_documento",
            "cliente_razon_social",
            "total_estimado",
            "payload_json",
            "duplicados_version",
            "duplicados_cobertura",
            "huella_fiscal_completa",
            "identidad_nombre_hash",
            "identidad_documento_hash",
            "identidad_nombre_original",
            "identidad_tipo_documento_original",
            "identidad_numero_documento_original",
            "fecha_emision_normalizada",
            "moneda_duplicados",
            "cotizacion_duplicados",
            "total_centavos",
            "duplicados_reserva_operacion_id",
            "mensajes_json",
            "cae",
            "numero_asignado",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            "punto_venta_elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            "comprobante_id",
            "created_at",
            "updated_at",
            "lote_id",
        ),
        "puntos_venta_guardas_emision_rece": (
            "id",
            "token",
            "fase",
            "operacion_id",
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            "elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            "arca_iniciada_en",
            "cerrada_en",
            "created_at",
            "updated_at",
        ),
        "lotes_duplicados_evidencias": (
            "id",
            "operacion_id",
            "empresa_id",
            "ambiente",
            "lote_id",
            "generacion",
            "formato",
            "evidencia_id",
            "snapshot_hash",
            "control_snapshot_json",
            "aceptacion_id",
            "aceptada_por_usuario_id",
            "aceptada_por_nombre",
            "aceptada_at",
            "aceptacion_origen_generacion_id",
            "created_at",
        ),
        "lotes_duplicados_coincidencias": (
            "id",
            "generacion_id",
            "operacion_id",
            "empresa_id",
            "ambiente",
            "lote_id",
            "bloque_clave",
            "clase",
            "antecedente_clave",
            "snapshot_json",
        ),
        "lotes_duplicados_coincidencias_miembros": (
            "id",
            "bloque_id",
            "lado",
            "miembro_clave",
            "grupo_id",
            "comprobante_id",
            "nombre_hash",
            "documento_hash",
            "ordinal",
            "relevancia",
            "snapshot_json",
        ),
        "intentos_emision_fiscal": (
            "id",
            "tipo_comprobante",
            "punto_venta_numero",
            "numero_planificado",
            "fecha_emision",
            "total",
            "receptor_tipo_documento",
            "receptor_numero_documento",
            "receptor_razon_social",
            "payload_hash",
            "huella_logica",
            "cae",
            "cae_vencimiento",
            "estado",
            "categoria_error",
            "mensaje",
            "errores_arca_json",
            "solicitante_nombre_snapshot",
            "solicitud_arca_at",
            "resultado_fiscal_at",
            "ambiente",
            "punto_venta_elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            "guarda_rece_id",
            "created_at",
            "updated_at",
            "operacion_id",
            "empresa_id",
            "usuario_id",
            "punto_venta_id",
            "comprobante_id",
            "lote_id",
            "grupo_id",
            "duplicados_generacion_id",
        ),
    }
)

PRIMARY_KEYS = {
    table_name: (
        ("usuario_id", "empresa_id")
        if table_name == "usuario_emisor_acceso"
        else ("id",)
    )
    for table_name in INCLUDED_TABLES
}

MANIFEST_TOP_LEVEL_KEYS = frozenset(
    {
        "package_version",
        "created_at",
        "scope",
        "alembic_version",
        "complete_tables",
        "filtered_tables",
        "regenerated_tables",
        "excluded_tables",
        "included_tables",
        "target_empty_tables",
        "source_counts",
        "included_counts",
        "omitted_counts",
        "active_certificates",
        "safe_omitted",
        "normalizations",
        "closure",
        "source_barrier",
        "idempotency_barrier",
        "data_files",
        "certificate_files",
        "env_template",
        "required_env_keys",
        "notes",
    }
)
CLOSURE_KEYS = frozenset(
    {
        "version",
        "algorithm",
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
        "group_counts_by_lote",
        "sha256",
    }
)
BARRIER_KEYS = frozenset({"version", "algorithm", "rows", "sha256"})
SAFE_OMITTED_KEYS = frozenset(
    {
        "blockers",
        "legacy_preflight",
        "source_counts",
        "included_counts",
        "omitted_counts",
    }
)


@dataclass(frozen=True)
class ImportContract:
    package_version: int
    alembic_head: str
    complete_tables: tuple[str, ...]
    filtered_tables: tuple[str, ...]
    regenerated_tables: tuple[str, ...]
    included_tables: tuple[str, ...]
    excluded_tables: tuple[str, ...]
    target_empty_tables: tuple[str, ...]
    seeded_included_tables: tuple[str, ...]
    adapter_target_empty_tables: tuple[str, ...]
    sequence_tables: tuple[str, ...]
    insert_order: tuple[str, ...]
    deferred_columns: dict[str, tuple[str, ...]]


V4_CONTRACT = ImportContract(
    package_version=PACKAGE_VERSION,
    alembic_head=ALEMBIC_HEAD,
    complete_tables=COMPLETE_TABLES,
    filtered_tables=FILTERED_TABLES,
    regenerated_tables=REGENERATED_TABLES,
    included_tables=INCLUDED_TABLES,
    excluded_tables=EXCLUDED_TABLES,
    target_empty_tables=TARGET_EMPTY_TABLES,
    seeded_included_tables=SEEDED_INCLUDED_TABLES,
    adapter_target_empty_tables=(),
    sequence_tables=SEQUENCE_TABLES,
    insert_order=INSERT_ORDER,
    deferred_columns=DEFERRED_COLUMNS,
)


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
