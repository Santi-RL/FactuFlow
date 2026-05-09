"""comprobante_concepto

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-05-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega trazabilidad del concepto fiscal emitido."""
    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.add_column(sa.Column("concepto", sa.Integer(), nullable=True))

    op.execute("UPDATE comprobantes SET concepto = 1 WHERE concepto IS NULL")

    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.alter_column("concepto", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    """Quita la columna de concepto fiscal."""
    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.drop_column("concepto")
