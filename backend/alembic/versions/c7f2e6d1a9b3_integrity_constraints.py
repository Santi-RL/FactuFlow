"""integrity_constraints

Revision ID: c7f2e6d1a9b3
Revises: bd2afd21a840
Create Date: 2026-05-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7f2e6d1a9b3"
down_revision: Union[str, None] = "bd2afd21a840"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.create_unique_constraint(
            "uq_comprobantes_empresa_pv_tipo_numero",
            ["empresa_id", "punto_venta_id", "tipo_comprobante", "numero"],
        )

    with op.batch_alter_table("lotes_comprobantes") as batch_op:
        batch_op.create_unique_constraint(
            "uq_lotes_comprobantes_empresa_hash",
            ["empresa_id", "archivo_hash"],
        )

    with op.batch_alter_table("lotes_comprobantes_grupos") as batch_op:
        batch_op.create_unique_constraint(
            "uq_lotes_comprobantes_grupos_lote_ref",
            ["lote_id", "comprobante_ref"],
        )


def downgrade() -> None:
    with op.batch_alter_table("lotes_comprobantes_grupos") as batch_op:
        batch_op.drop_constraint(
            "uq_lotes_comprobantes_grupos_lote_ref",
            type_="unique",
        )

    with op.batch_alter_table("lotes_comprobantes") as batch_op:
        batch_op.drop_constraint(
            "uq_lotes_comprobantes_empresa_hash",
            type_="unique",
        )

    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.drop_constraint(
            "uq_comprobantes_empresa_pv_tipo_numero",
            type_="unique",
        )
