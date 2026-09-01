"""pf19d_autoridad_wsfe

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
Create Date: 2026-08-31
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_EVIDENCIAS_PF19D = (
    "'sin_evidencia', 'rece_aplicativo_web_services_v1', "
    "'wsfe_param_get_ptos_venta_v1'"
)

_COHERENCIA_PF19D = (
    "(((estado = 'verificado_rece' "
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
    "OR (estado = 'verificado_rece' "
    "AND fuente = 'sincronizacion_wsfe' "
    "AND evidencia_tipo = 'wsfe_param_get_ptos_venta_v1' "
    "AND evidencia_sha256 IS NULL "
    "AND clasificador_version IS NOT NULL "
    "AND empresa_cuit_snapshot IS NOT NULL "
    "AND punto_venta_numero_snapshot IS NOT NULL "
    "AND documento_emitido_en IS NULL "
    "AND vigente_hasta IS NULL "
    "AND verificado_en IS NOT NULL "
    "AND actor_usuario_id_snapshot IS NOT NULL)) "
    "OR (estado <> 'verificado_rece' "
    "AND vigente_hasta IS NULL "
    "AND verificado_en IS NULL))"
)

_COHERENCIA_ANTERIOR = (
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


def upgrade() -> None:
    """Agrega preferencia/procedencia y habilita evidencia WSFE autenticada."""
    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.add_column(
            sa.Column(
                "usar_en_factuflow",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("domicilio_fuente", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(
            sa.Column("nombre_fantasia_fuente", sa.String(length=30), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_puntos_venta_domicilio_fuente",
            "domicilio_fuente IS NULL OR "
            "domicilio_fuente IN ('manual', 'constancia_arca')",
        )
        batch_op.create_check_constraint(
            "ck_puntos_venta_nombre_fantasia_fuente",
            "nombre_fantasia_fuente IS NULL OR "
            "nombre_fantasia_fuente IN ('manual', 'constancia_arca')",
        )

    puntos = sa.table(
        "puntos_venta",
        sa.column("es_webservice", sa.Boolean()),
        sa.column("usar_en_factuflow", sa.Boolean()),
        sa.column("domicilio", sa.String()),
        sa.column("domicilio_fuente", sa.String()),
        sa.column("nombre_fantasia", sa.String()),
        sa.column("nombre_fantasia_fuente", sa.String()),
        sa.column("fuente", sa.String()),
    )
    op.execute(puntos.update().values(usar_en_factuflow=puntos.c.es_webservice))
    op.execute(
        puntos.update()
        .where(puntos.c.domicilio.is_not(None))
        .values(
            domicilio_fuente=sa.case(
                (puntos.c.fuente == "constancia_arca", "constancia_arca"),
                else_="manual",
            )
        )
    )
    op.execute(
        puntos.update()
        .where(puntos.c.nombre_fantasia.is_not(None))
        .values(
            nombre_fantasia_fuente=sa.case(
                (puntos.c.fuente == "constancia_arca", "constancia_arca"),
                else_="manual",
            )
        )
    )

    with op.batch_alter_table("puntos_venta_elegibilidad_rece_revisiones") as batch_op:
        batch_op.drop_constraint("ck_pv_rece_revision_evidencia_tipo", type_="check")
        batch_op.drop_constraint(
            "ck_pv_rece_revision_verificada_coherente", type_="check"
        )
        batch_op.drop_constraint(
            "ck_pv_rece_revision_fuente_no_promueve", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_pv_rece_revision_evidencia_tipo",
            f"evidencia_tipo IN ({_EVIDENCIAS_PF19D})",
        )
        batch_op.create_check_constraint(
            "ck_pv_rece_revision_verificada_coherente", _COHERENCIA_PF19D
        )
        batch_op.create_check_constraint(
            "ck_pv_rece_revision_fuente_no_promueve",
            "fuente NOT IN ('migracion_legacy', 'alta_manual', 'edicion') "
            "OR estado <> 'verificado_rece'",
        )


def downgrade() -> None:
    """Retira PF-19D sólo si no existe evidencia WSFE creada en runtime."""
    bind = op.get_bind()
    total_wsfe = bind.scalar(
        sa.text(
            "SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_revisiones "
            "WHERE evidencia_tipo = 'wsfe_param_get_ptos_venta_v1'"
        )
    )
    if int(total_wsfe or 0) > 0:
        raise RuntimeError(
            "PF-19D bloqueó el downgrade porque existen revisiones WSFE. "
            "Conservá el esquema o restaurá un backup anterior al release."
        )

    with op.batch_alter_table("puntos_venta_elegibilidad_rece_revisiones") as batch_op:
        batch_op.drop_constraint("ck_pv_rece_revision_evidencia_tipo", type_="check")
        batch_op.drop_constraint(
            "ck_pv_rece_revision_verificada_coherente", type_="check"
        )
        batch_op.drop_constraint(
            "ck_pv_rece_revision_fuente_no_promueve", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_pv_rece_revision_evidencia_tipo",
            "evidencia_tipo IN ('sin_evidencia', " "'rece_aplicativo_web_services_v1')",
        )
        batch_op.create_check_constraint(
            "ck_pv_rece_revision_verificada_coherente", _COHERENCIA_ANTERIOR
        )
        batch_op.create_check_constraint(
            "ck_pv_rece_revision_fuente_no_promueve",
            "fuente NOT IN ('migracion_legacy', 'alta_manual', "
            "'sincronizacion_wsfe', 'edicion') OR estado <> 'verificado_rece'",
        )

    with op.batch_alter_table("puntos_venta") as batch_op:
        batch_op.drop_constraint(
            "ck_puntos_venta_nombre_fantasia_fuente", type_="check"
        )
        batch_op.drop_constraint("ck_puntos_venta_domicilio_fuente", type_="check")
        batch_op.drop_column("nombre_fantasia_fuente")
        batch_op.drop_column("domicilio_fuente")
        batch_op.drop_column("usar_en_factuflow")
