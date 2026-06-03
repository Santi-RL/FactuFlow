"""lotes_resolucion_y_compactacion

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-06-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega resolución operativa de lotes y origen de comprobantes."""
    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "origen_emision",
                sa.String(length=30),
                nullable=False,
                server_default="factuflow",
            )
        )

    with op.batch_alter_table("lotes_comprobantes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "grupos_reconciliados_externos",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "grupos_descartados",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("compactado_at", sa.DateTime(), nullable=True))

    op.create_index(
        "uq_lotes_comprobantes_grupos_comprobante_id",
        "lotes_comprobantes_grupos",
        ["comprobante_id"],
        unique=True,
        sqlite_where=sa.text("comprobante_id IS NOT NULL"),
        postgresql_where=sa.text("comprobante_id IS NOT NULL"),
    )

    op.create_table(
        "lotes_comprobantes_eventos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=50), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("lote_id", sa.Integer(), nullable=True),
        sa.Column("grupo_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["grupo_id"],
            ["lotes_comprobantes_grupos.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lote_id"], ["lotes_comprobantes.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lotes_comprobantes_eventos_id"),
        "lotes_comprobantes_eventos",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_lotes_comprobantes_eventos_lote",
        "lotes_comprobantes_eventos",
        ["lote_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Revierte resolución operativa de lotes y origen de comprobantes."""
    op.drop_index(
        "uq_lotes_comprobantes_grupos_comprobante_id",
        table_name="lotes_comprobantes_grupos",
    )

    op.drop_index(
        "ix_lotes_comprobantes_eventos_lote",
        table_name="lotes_comprobantes_eventos",
    )
    op.drop_index(
        op.f("ix_lotes_comprobantes_eventos_id"),
        table_name="lotes_comprobantes_eventos",
    )
    op.drop_table("lotes_comprobantes_eventos")

    with op.batch_alter_table("lotes_comprobantes") as batch_op:
        batch_op.drop_column("compactado_at")
        batch_op.drop_column("grupos_descartados")
        batch_op.drop_column("grupos_reconciliados_externos")

    with op.batch_alter_table("comprobantes") as batch_op:
        batch_op.drop_column("origen_emision")
