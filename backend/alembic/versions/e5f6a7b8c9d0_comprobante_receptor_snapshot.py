"""comprobante_receptor_snapshot

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.add_column(
            sa.Column("receptor_tipo_documento", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("receptor_numero_documento", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("receptor_razon_social", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("receptor_condicion_iva", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("receptor_domicilio", sa.String(length=255), nullable=True)
        )
        batch_op.alter_column("cliente_id", existing_type=sa.Integer(), nullable=True)

    op.execute(
        """
        UPDATE comprobantes
        SET
            receptor_tipo_documento = CASE (
                SELECT clientes.tipo_documento
                FROM clientes
                WHERE clientes.id = comprobantes.cliente_id
            )
                WHEN 'CUIT' THEN 80
                WHEN 'CUIL' THEN 86
                WHEN 'DNI' THEN 96
                WHEN 'LE' THEN 89
                WHEN 'LC' THEN 90
                WHEN 'Pasaporte' THEN 94
                ELSE 99
            END,
            receptor_numero_documento = (
                SELECT clientes.numero_documento
                FROM clientes
                WHERE clientes.id = comprobantes.cliente_id
            ),
            receptor_razon_social = (
                SELECT clientes.razon_social
                FROM clientes
                WHERE clientes.id = comprobantes.cliente_id
            ),
            receptor_condicion_iva = (
                SELECT clientes.condicion_iva
                FROM clientes
                WHERE clientes.id = comprobantes.cliente_id
            ),
            receptor_domicilio = (
                SELECT clientes.domicilio
                FROM clientes
                WHERE clientes.id = comprobantes.cliente_id
            )
        WHERE cliente_id IS NOT NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.drop_column("receptor_domicilio")
        batch_op.drop_column("receptor_condicion_iva")
        batch_op.drop_column("receptor_razon_social")
        batch_op.drop_column("receptor_numero_documento")
        batch_op.drop_column("receptor_tipo_documento")
