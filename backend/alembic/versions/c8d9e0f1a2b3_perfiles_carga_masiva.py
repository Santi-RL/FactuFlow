"""perfiles_carga_masiva

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-05-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabla de perfiles de carga masiva."""
    op.create_table(
        "perfiles_carga_masiva",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("configuracion_json", sa.JSON(), nullable=False),
        sa.Column(
            "es_predeterminado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "empresa_id",
            "nombre",
            name="uq_perfiles_carga_masiva_empresa_nombre",
        ),
    )
    op.create_index(
        op.f("ix_perfiles_carga_masiva_id"),
        "perfiles_carga_masiva",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_perfiles_carga_masiva_empresa_activo",
        "perfiles_carga_masiva",
        ["empresa_id", "activo"],
        unique=False,
    )


def downgrade() -> None:
    """Elimina la tabla de perfiles de carga masiva."""
    op.drop_index(
        "ix_perfiles_carga_masiva_empresa_activo",
        table_name="perfiles_carga_masiva",
    )
    op.drop_index(
        op.f("ix_perfiles_carga_masiva_id"),
        table_name="perfiles_carga_masiva",
    )
    op.drop_table("perfiles_carga_masiva")
