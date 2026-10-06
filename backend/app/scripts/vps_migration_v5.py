"""Formato A-01 versión 5; v3/v4 conservan sus contratos y barreras originales."""

from dataclasses import replace

from app.core.fiscal_storage import ExactAmount, ExactDecimal, ExactInteger
from app.core.fiscal_storage_legacy import A01_HEAD, LEGACY_COLUMNS, VARIABLE_COLUMNS
from app.scripts.vps_migration_v4 import (  # noqa: F401
    BARRIER_ALGORITHM,
    BARRIER_KEYS,
    CLOSURE_ALGORITHM,
    CLOSURE_KEYS,
    COMPLETE_TABLES,
    DEFERRED_COLUMNS,
    EXCLUDED_TABLES,
    FILTERED_TABLES,
    INCLUDED_TABLES,
    INSERT_ORDER,
    MANIFEST_TOP_LEVEL_KEYS,
    OPERATIONAL_COMPLETE_TABLES,
    OPERATION_LOTE_NORMALIZATION_KEY,
    OPERATION_LOTE_NORMALIZATION_RULE,
    PRIMARY_KEYS,
    REGENERATED_TABLES,
    RELATION_FORMAT,
    SAFE_OMITTED_KEYS,
    SCOPE,
    SEEDED_INCLUDED_TABLES,
    SEQUENCE_TABLES,
    TARGET_EMPTY_TABLES,
    canonical_sha256,
)
from app.scripts import vps_migration_v4

PACKAGE_VERSION = 5
ALEMBIC_HEAD = A01_HEAD
PACKAGE_NOTES = vps_migration_v4.PACKAGE_NOTES + (
    "Conserva decimales A-01 exactos y la clave auxiliar de cotización.",
)
V4_COLUMNS = dict(vps_migration_v4.V4_COLUMNS)
group_columns = list(V4_COLUMNS["lotes_comprobantes_grupos"])
group_columns.insert(group_columns.index("total_centavos"), "cotizacion_busqueda")
V4_COLUMNS["lotes_comprobantes_grupos"] = tuple(group_columns)
V4_CONTRACT = replace(
    vps_migration_v4.V4_CONTRACT,
    package_version=PACKAGE_VERSION,
    alembic_head=ALEMBIC_HEAD,
)
DECIMAL_TYPES = {
    (table_name, name): (
        ExactInteger()
        if name == "total_centavos"
        else ExactDecimal() if name in VARIABLE_COLUMNS else ExactAmount()
    )
    for table_name, columns in LEGACY_COLUMNS.items()
    for name, old_type in columns.items()
    if name not in {"codigo", "cotizacion_duplicados"}
}
