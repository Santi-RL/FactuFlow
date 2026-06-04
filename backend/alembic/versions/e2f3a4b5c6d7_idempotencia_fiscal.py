"""idempotencia_fiscal

Revision ID: e2f3a4b5c6d7
Revises: d0e1f2a3b4c5
Create Date: 2026-06-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _verificar_puntos_venta_sin_duplicados() -> None:
    """Bloquea la migración si existen puntos de venta duplicados por emisor."""
    conn = op.get_bind()
    duplicados = conn.execute(
        sa.text(
            """
            SELECT empresa_id, numero, COUNT(*) AS cantidad
            FROM puntos_venta
            GROUP BY empresa_id, numero
            HAVING COUNT(*) > 1
            ORDER BY empresa_id, numero
            """
        )
    ).fetchall()
    if not duplicados:
        return

    detalle = ", ".join(
        f"empresa_id={row.empresa_id} numero={row.numero} cantidad={row.cantidad}"
        for row in duplicados[:10]
    )
    raise RuntimeError(
        "No se puede crear el constraint uq_puntos_venta_empresa_numero porque "
        "existen puntos de venta duplicados por emisor. Unificá o corregí esos "
        f"registros antes de migrar. Duplicados detectados: {detalle}."
    )


def upgrade() -> None:
    """Agrega idempotencia fiscal durable e intentos de emisión."""
    op.create_table(
        "operaciones_idempotentes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("tipo_operacion", sa.String(length=50), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("estado", sa.String(length=40), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column("lote_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["lote_id"], ["lotes_comprobantes.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "empresa_id",
            "idempotency_key",
            name="uq_operaciones_idempotentes_empresa_key",
        ),
    )
    op.create_index(
        op.f("ix_operaciones_idempotentes_id"),
        "operaciones_idempotentes",
        ["id"],
    )
    op.create_index(
        "ix_operaciones_idempotentes_empresa_estado",
        "operaciones_idempotentes",
        ["empresa_id", "estado"],
    )
    op.create_index(
        "ix_operaciones_idempotentes_key",
        "operaciones_idempotentes",
        ["empresa_id", "idempotency_key"],
    )

    op.create_table(
        "intentos_emision_fiscal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo_comprobante", sa.Integer(), nullable=False),
        sa.Column("punto_venta_numero", sa.Integer(), nullable=False),
        sa.Column("numero_planificado", sa.Integer(), nullable=True),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("receptor_tipo_documento", sa.Integer(), nullable=True),
        sa.Column("receptor_numero_documento", sa.String(length=20), nullable=True),
        sa.Column("receptor_razon_social", sa.String(length=255), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("huella_logica", sa.String(length=64), nullable=False),
        sa.Column("cae", sa.String(length=14), nullable=True),
        sa.Column("cae_vencimiento", sa.Date(), nullable=True),
        sa.Column("estado", sa.String(length=40), nullable=False),
        sa.Column("categoria_error", sa.String(length=80), nullable=True),
        sa.Column("mensaje", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("operacion_id", sa.Integer(), nullable=True),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("punto_venta_id", sa.Integer(), nullable=False),
        sa.Column("comprobante_id", sa.Integer(), nullable=True),
        sa.Column("lote_id", sa.Integer(), nullable=True),
        sa.Column("grupo_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["comprobante_id"], ["comprobantes.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["grupo_id"], ["lotes_comprobantes_grupos.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["lote_id"], ["lotes_comprobantes.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["operacion_id"], ["operaciones_idempotentes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["punto_venta_id"], ["puntos_venta.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_intentos_emision_fiscal_id"),
        "intentos_emision_fiscal",
        ["id"],
    )
    op.create_index(
        "ix_intentos_emision_fiscal_lote_grupo",
        "intentos_emision_fiscal",
        ["lote_id", "grupo_id"],
    )
    op.create_index(
        "ix_intentos_emision_fiscal_operacion",
        "intentos_emision_fiscal",
        ["operacion_id", "estado"],
    )
    op.create_index(
        "uq_intentos_emision_fiscal_reserva_activa",
        "intentos_emision_fiscal",
        ["empresa_id", "punto_venta_id", "tipo_comprobante", "numero_planificado"],
        unique=True,
        sqlite_where=sa.text(
            "numero_planificado IS NOT NULL AND estado IN "
            "('en_proceso', 'autorizado', 'requiere_reconciliacion')"
        ),
        postgresql_where=sa.text(
            "numero_planificado IS NOT NULL AND estado IN "
            "('en_proceso', 'autorizado', 'requiere_reconciliacion')"
        ),
    )

    _verificar_puntos_venta_sin_duplicados()
    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.create_unique_constraint(
            "uq_puntos_venta_empresa_numero",
            ["empresa_id", "numero"],
        )
    op.create_index(
        "ix_puntos_venta_empresa_numero",
        "puntos_venta",
        ["empresa_id", "numero"],
    )


def downgrade() -> None:
    """Revierte idempotencia fiscal durable e intentos de emisión."""
    op.drop_index("ix_puntos_venta_empresa_numero", table_name="puntos_venta")
    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.drop_constraint(
            "uq_puntos_venta_empresa_numero",
            type_="unique",
        )

    op.drop_index(
        "uq_intentos_emision_fiscal_reserva_activa",
        table_name="intentos_emision_fiscal",
    )
    op.drop_index(
        "ix_intentos_emision_fiscal_operacion",
        table_name="intentos_emision_fiscal",
    )
    op.drop_index(
        "ix_intentos_emision_fiscal_lote_grupo",
        table_name="intentos_emision_fiscal",
    )
    op.drop_index(
        op.f("ix_intentos_emision_fiscal_id"),
        table_name="intentos_emision_fiscal",
    )
    op.drop_table("intentos_emision_fiscal")

    op.drop_index(
        "ix_operaciones_idempotentes_key",
        table_name="operaciones_idempotentes",
    )
    op.drop_index(
        "ix_operaciones_idempotentes_empresa_estado",
        table_name="operaciones_idempotentes",
    )
    op.drop_index(
        op.f("ix_operaciones_idempotentes_id"),
        table_name="operaciones_idempotentes",
    )
    op.drop_table("operaciones_idempotentes")
