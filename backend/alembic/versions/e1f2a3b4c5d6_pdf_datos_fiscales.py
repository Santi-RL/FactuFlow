"""pdf_datos_fiscales

Revision ID: e1f2a3b4c5d6
Revises: d9e0f1a2b3c4
Create Date: 2026-05-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("empresas") as batch_op:
        batch_op.add_column(
            sa.Column("ingresos_brutos", sa.String(length=50), nullable=True)
        )

    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.add_column(sa.Column("fecha_servicio_desde", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("fecha_servicio_hasta", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("fecha_vto_pago", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.drop_column("fecha_vto_pago")
        batch_op.drop_column("fecha_servicio_hasta")
        batch_op.drop_column("fecha_servicio_desde")

    with op.batch_alter_table("empresas") as batch_op:
        batch_op.drop_column("ingresos_brutos")
