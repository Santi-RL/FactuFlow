"""pdv_acreditacion_durable

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b
Create Date: 2026-08-28
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c0d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COHERENCIA_DURABLE = (
    "((estado = 'verificado_rece' "
    "AND ambiente = 'produccion' "
    "AND fuente = 'constancia_arca_atestada' "
    "AND evidencia_tipo = 'rece_aplicativo_web_services_v1' "
    "AND evidencia_sha256 IS NOT NULL "
    "AND clasificador_version IS NOT NULL "
    "AND empresa_cuit_snapshot IS NOT NULL "
    "AND punto_venta_numero_snapshot IS NOT NULL "
    "AND documento_emitido_en IS NOT NULL "
    "AND verificado_en IS NOT NULL "
    "AND actor_usuario_id_snapshot IS NOT NULL) "
    "OR (estado <> 'verificado_rece' "
    "AND vigente_hasta IS NULL "
    "AND verificado_en IS NULL))"
)

_COHERENCIA_CON_VIGENCIA = (
    "((estado = 'verificado_rece' "
    "AND ambiente = 'produccion' "
    "AND fuente = 'constancia_arca_atestada' "
    "AND evidencia_tipo = 'rece_aplicativo_web_services_v1' "
    "AND evidencia_sha256 IS NOT NULL "
    "AND clasificador_version IS NOT NULL "
    "AND empresa_cuit_snapshot IS NOT NULL "
    "AND punto_venta_numero_snapshot IS NOT NULL "
    "AND documento_emitido_en IS NOT NULL "
    "AND vigente_hasta IS NOT NULL "
    "AND verificado_en IS NOT NULL "
    "AND actor_usuario_id_snapshot IS NOT NULL) "
    "OR (estado <> 'verificado_rece' "
    "AND vigente_hasta IS NULL "
    "AND verificado_en IS NULL))"
)


def upgrade() -> None:
    """Separa acreditación durable de la frescura técnica consultada a ARCA."""
    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.add_column(
            sa.Column("ultima_comprobacion_arca_en", sa.DateTime(), nullable=True)
        )

    with op.batch_alter_table("puntos_venta_elegibilidad_rece_revisiones") as batch_op:
        batch_op.drop_constraint(
            "ck_pv_rece_revision_verificada_coherente",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_pv_rece_revision_verificada_coherente",
            _COHERENCIA_DURABLE,
        )


def downgrade() -> None:
    """Restaura el contrato temporal anterior de forma fail-closed."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE puntos_venta_elegibilidad_rece_revisiones "
            "SET vigente_hasta = documento_emitido_en + 7 "
            "WHERE estado = 'verificado_rece' AND vigente_hasta IS NULL"
        )
    else:
        op.execute(
            "UPDATE puntos_venta_elegibilidad_rece_revisiones "
            "SET vigente_hasta = date(documento_emitido_en, '+7 day') "
            "WHERE estado = 'verificado_rece' AND vigente_hasta IS NULL"
        )

    with op.batch_alter_table("puntos_venta_elegibilidad_rece_revisiones") as batch_op:
        batch_op.drop_constraint(
            "ck_pv_rece_revision_verificada_coherente",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_pv_rece_revision_verificada_coherente",
            _COHERENCIA_CON_VIGENCIA,
        )

    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.drop_column("ultima_comprobacion_arca_en")
