"""integrity_constraints

Revision ID: c7f2e6d1a9b3
Revises: bd2afd21a840
Create Date: 2026-05-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7f2e6d1a9b3"
down_revision: Union[str, None] = "bd2afd21a840"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _crear_unique_si_no_existe(
    table_name: str, constraint_name: str, columns: list[str]
) -> None:
    """Crea un constraint único solo si el esquema actual no lo tiene."""
    inspector = sa.inspect(op.get_bind())
    existentes = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints(table_name)
    }
    if constraint_name in existentes:
        return

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.create_unique_constraint(constraint_name, columns)


def upgrade() -> None:
    _crear_unique_si_no_existe(
        "comprobantes",
        "uq_comprobantes_empresa_pv_tipo_numero",
        ["empresa_id", "punto_venta_id", "tipo_comprobante", "numero"],
    )
    _crear_unique_si_no_existe(
        "lotes_comprobantes",
        "uq_lotes_comprobantes_empresa_hash",
        ["empresa_id", "archivo_hash"],
    )
    _crear_unique_si_no_existe(
        "lotes_comprobantes_grupos",
        "uq_lotes_comprobantes_grupos_lote_ref",
        ["lote_id", "comprobante_ref"],
    )


def downgrade() -> None:
    # Los constraints ya existen en `bd2afd21a840_core_schema` para
    # instalaciones limpias. No se eliminan en downgrade para no romper ese
    # esquema base.
    pass
