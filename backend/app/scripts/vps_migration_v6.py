"""Formato de traslado v6: evidencia fiscal previa; v3/v4/v5 congelados."""

from dataclasses import replace

from app.scripts import vps_migration_v5
from app.scripts.vps_migration_v5 import *  # noqa: F403

PACKAGE_VERSION = 6
ALEMBIC_HEAD = "c3d4e5f6a7b8"
PACKAGE_NOTES = vps_migration_v5.PACKAGE_NOTES + (
    "Conserva la evidencia previa del intento sin enriquecer antecedentes.",
)
V4_COLUMNS = dict(vps_migration_v5.V4_COLUMNS)
_columns = list(V4_COLUMNS["intentos_emision_fiscal"])
_position = _columns.index("huella_logica") + 1
_columns[_position:_position] = (
    "evidencia_version",
    "evidencia_json",
    "evidencia_hash",
)
V4_COLUMNS["intentos_emision_fiscal"] = tuple(_columns)
V4_CONTRACT = replace(
    vps_migration_v5.V4_CONTRACT,
    package_version=PACKAGE_VERSION,
    alembic_head=ALEMBIC_HEAD,
)
