"""almacenamiento_eventos

Revision ID: d0e1f2a3b4c5
Revises: c5d6e7f8a9b0
Create Date: 2026-06-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega auditoría y exportaciones del gestor de almacenamiento."""
    op.create_table(
        "eventos_sistema",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=80), nullable=False),
        sa.Column("categoria", sa.String(length=50), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("bytes_afectados", sa.BigInteger(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("empresa_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eventos_sistema_id"), "eventos_sistema", ["id"])
    op.create_index(
        "ix_eventos_sistema_categoria_created",
        "eventos_sistema",
        ["categoria", "created_at"],
    )

    op.create_table(
        "exportaciones_almacenamiento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("categoria", sa.String(length=50), nullable=False),
        sa.Column("archivo_nombre", sa.String(length=255), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("seleccion_json", sa.JSON(), nullable=True),
        sa.Column("manifest_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_exportaciones_almacenamiento_id"),
        "exportaciones_almacenamiento",
        ["id"],
    )
    op.create_index(
        op.f("ix_exportaciones_almacenamiento_token"),
        "exportaciones_almacenamiento",
        ["token"],
        unique=True,
    )


def downgrade() -> None:
    """Revierte auditoría y exportaciones del gestor de almacenamiento."""
    op.drop_index(
        op.f("ix_exportaciones_almacenamiento_token"),
        table_name="exportaciones_almacenamiento",
    )
    op.drop_index(
        op.f("ix_exportaciones_almacenamiento_id"),
        table_name="exportaciones_almacenamiento",
    )
    op.drop_table("exportaciones_almacenamiento")

    op.drop_index(
        "ix_eventos_sistema_categoria_created",
        table_name="eventos_sistema",
    )
    op.drop_index(op.f("ix_eventos_sistema_id"), table_name="eventos_sistema")
    op.drop_table("eventos_sistema")
