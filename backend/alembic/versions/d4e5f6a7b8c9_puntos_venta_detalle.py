"""puntos_venta_detalle

Revision ID: d4e5f6a7b8c9
Revises: c7f2e6d1a9b3
Create Date: 2026-05-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c7f2e6d1a9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.add_column(sa.Column("sistema", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("domicilio", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(
            sa.Column("nombre_fantasia", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "es_webservice", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column(
                "bloqueado", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column("fecha_baja", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(sa.Column("fuente", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.drop_column("fuente")
        batch_op.drop_column("fecha_baja")
        batch_op.drop_column("bloqueado")
        batch_op.drop_column("es_webservice")
        batch_op.drop_column("nombre_fantasia")
        batch_op.drop_column("domicilio")
        batch_op.drop_column("sistema")
