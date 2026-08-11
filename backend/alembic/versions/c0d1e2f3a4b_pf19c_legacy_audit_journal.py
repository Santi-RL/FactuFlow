"""pf19c_legacy_audit_journal

Revision ID: c0d1e2f3a4b
Revises: b9c0d1e2f3a4
Create Date: 2026-08-09
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c0d1e2f3a4b"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega evidencia estructurada y el journal legacy sin reinterpretar datos."""
    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.add_column(sa.Column("errores_arca_json", sa.JSON(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_intentos_emision_fiscal_id_empresa",
            ["id", "empresa_id"],
        )

    op.create_table(
        "resoluciones_legacy_pf19_journal",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=80), nullable=False),
        sa.Column("plan_sha256", sa.String(length=64), nullable=False),
        sa.Column("terminal_response_sha256", sa.String(length=64), nullable=False),
        sa.Column("actor_usuario_id", sa.Integer(), nullable=False),
        sa.Column("ambiente_consultado", sa.String(length=20), nullable=False),
        sa.Column("resultado", sa.String(length=80), nullable=False),
        sa.Column("resultado_consultas_json", sa.JSON(), nullable=False),
        sa.Column("backup_metadata_json", sa.JSON(), nullable=False),
        sa.Column("backup_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("intento_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["intento_id", "empresa_id"],
            [
                "intentos_emision_fiscal.id",
                "intentos_emision_fiscal.empresa_id",
            ],
            name="fk_resoluciones_legacy_pf19_journal_intento_empresa",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_usuario_id"], ["usuarios.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(plan_sha256) = 64",
            name="ck_resoluciones_legacy_pf19_journal_plan_sha256",
        ),
        sa.CheckConstraint(
            "length(terminal_response_sha256) = 64",
            name="ck_resoluciones_legacy_pf19_journal_terminal_response_sha256",
        ),
        sa.CheckConstraint(
            "length(backup_sha256) = 64",
            name="ck_resoluciones_legacy_pf19_journal_backup_sha256",
        ),
        sa.CheckConstraint(
            "ambiente_consultado IN ('homologacion', 'produccion', 'ambos')",
            name="ck_resoluciones_legacy_pf19_journal_ambiente",
        ),
        sa.CheckConstraint(
            "accion = 'cerrar_legacy_sin_autorizacion_verificada'",
            name="ck_resoluciones_legacy_pf19_journal_accion",
        ),
        sa.CheckConstraint(
            "resultado = 'legacy_sin_autorizacion_verificada'",
            name="ck_resoluciones_legacy_pf19_journal_resultado",
        ),
        sa.UniqueConstraint(
            "intento_id", name="uq_resoluciones_legacy_pf19_journal_intento"
        ),
    )
    op.create_index(
        "ix_resoluciones_legacy_pf19_journal_empresa_intento",
        "resoluciones_legacy_pf19_journal",
        ["empresa_id", "intento_id"],
        unique=False,
    )
    _crear_proteccion_append_only()


def downgrade() -> None:
    """Retira PF-19C solo cuando no existe evidencia administrativa aceptada."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "LOCK TABLE intentos_emision_fiscal, "
                "resoluciones_legacy_pf19_journal IN ACCESS EXCLUSIVE MODE"
            )
        )
    cantidad = bind.execute(
        sa.text("SELECT COUNT(*) FROM resoluciones_legacy_pf19_journal")
    ).scalar_one()
    if int(cantidad) != 0:
        raise RuntimeError(
            "PF-19C bloqueó el downgrade para no eliminar journal administrativo."
        )
    evidencia_estructurada = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM intentos_emision_fiscal "
            "WHERE errores_arca_json IS NOT NULL "
            "AND CAST(errores_arca_json AS VARCHAR) <> 'null'"
        )
    ).scalar_one()
    if int(evidencia_estructurada) != 0:
        raise RuntimeError(
            "PF-19C bloqueó el downgrade para no eliminar evidencia ARCA estructurada."
        )
    _eliminar_proteccion_append_only()
    op.drop_index(
        "ix_resoluciones_legacy_pf19_journal_empresa_intento",
        table_name="resoluciones_legacy_pf19_journal",
    )
    op.drop_table("resoluciones_legacy_pf19_journal")
    with op.batch_alter_table("intentos_emision_fiscal") as batch_op:
        batch_op.drop_column("errores_arca_json")
        batch_op.drop_constraint(
            "uq_intentos_emision_fiscal_id_empresa", type_="unique"
        )


def _crear_proteccion_append_only() -> None:
    """Bloquea UPDATE y DELETE del journal con DDL nativo por dialecto."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION impedir_mutacion_resoluciones_legacy_pf19_journal()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'El journal PF-19C es append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for evento in ("UPDATE", "DELETE"):
            op.execute(
                "CREATE TRIGGER tr_resoluciones_legacy_pf19_journal_"
                f"{evento.lower()} BEFORE {evento} ON resoluciones_legacy_pf19_journal "
                "FOR EACH ROW EXECUTE FUNCTION "
                "impedir_mutacion_resoluciones_legacy_pf19_journal()"
            )
        return
    if bind.dialect.name == "sqlite":
        for evento in ("UPDATE", "DELETE"):
            op.execute(
                "CREATE TRIGGER tr_resoluciones_legacy_pf19_journal_"
                f"{evento.lower()} BEFORE {evento} ON resoluciones_legacy_pf19_journal "
                "BEGIN SELECT RAISE(ABORT, 'El journal PF-19C es append-only'); END"
            )
        return
    raise RuntimeError("PF-19C solo admite PostgreSQL o SQLite")


def _eliminar_proteccion_append_only() -> None:
    """Retira triggers solo durante un downgrade sin evidencia aceptada."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for evento in ("update", "delete"):
            op.execute(
                "DROP TRIGGER IF EXISTS tr_resoluciones_legacy_pf19_journal_"
                f"{evento} ON resoluciones_legacy_pf19_journal"
            )
        op.execute(
            "DROP FUNCTION IF EXISTS impedir_mutacion_resoluciones_legacy_pf19_journal()"
        )
        return
    if bind.dialect.name == "sqlite":
        for evento in ("update", "delete"):
            op.execute(
                "DROP TRIGGER IF EXISTS tr_resoluciones_legacy_pf19_journal_" + evento
            )
        return
    raise RuntimeError("PF-19C solo admite PostgreSQL o SQLite")
