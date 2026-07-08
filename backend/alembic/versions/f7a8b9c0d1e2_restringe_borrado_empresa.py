"""restringe_borrado_empresa

Revision ID: f7a8b9c0d1e2
Revises: e2f3a4b5c6d7
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}

EMPRESA_FKS_UPGRADE = (
    ("usuarios", "SET NULL"),
    ("certificados", "RESTRICT"),
    ("clientes", "RESTRICT"),
    ("puntos_venta", "RESTRICT"),
    ("comprobantes", "RESTRICT"),
    ("lotes_comprobantes", "RESTRICT"),
    ("formatos_importacion", "RESTRICT"),
    ("perfiles_carga_masiva", "RESTRICT"),
    ("operaciones_idempotentes", "RESTRICT"),
    ("intentos_emision_fiscal", "RESTRICT"),
)

EMPRESA_FKS_DOWNGRADE = tuple(
    (table_name, "CASCADE") for table_name, _ in EMPRESA_FKS_UPGRADE
)


def _empresa_fk_name(table_name: str) -> str:
    """Obtiene el nombre real o convencional del FK a empresas.id."""
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("referred_table") == "empresas" and foreign_key.get(
            "constrained_columns"
        ) == ["empresa_id"]:
            name = foreign_key.get("name")
            if name:
                return name
    return f"fk_{table_name}_empresa_id_empresas"


def _replace_empresa_fk(table_name: str, ondelete: str) -> None:
    """Recrea el FK empresa_id -> empresas.id con la política indicada."""
    fk_name = _empresa_fk_name(table_name)
    with op.batch_alter_table(
        table_name,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.create_foreign_key(
            fk_name,
            "empresas",
            ["empresa_id"],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    """Impide borrar emisores arrastrando historial fiscal u operativo."""
    for table_name, ondelete in EMPRESA_FKS_UPGRADE:
        _replace_empresa_fk(table_name, ondelete)


def downgrade() -> None:
    """Restaura las políticas de borrado previas."""
    for table_name, ondelete in EMPRESA_FKS_DOWNGRADE:
        _replace_empresa_fk(table_name, ondelete)
