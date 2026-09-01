"""operadores_multiemisor

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-09-01
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Expande la asignación singular a accesos explícitos por emisor."""
    bind = op.get_bind()
    legacy_invalidos = bind.scalar(
        sa.text(
            "SELECT COUNT(*) FROM usuarios u "
            "LEFT JOIN empresas e ON e.id = u.empresa_id "
            "WHERE u.empresa_id IS NOT NULL AND e.id IS NULL"
        )
    )
    if int(legacy_invalidos or 0) > 0:
        raise RuntimeError(
            "PF-06 bloqueó la migración porque existen usuarios con un emisor "
            "legacy inexistente. Repará esas referencias antes de continuar."
        )

    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.add_column(
            sa.Column(
                "puede_crear_editar_emisores",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.create_table(
        "usuario_emisor_acceso",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("otorgado_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("origen", sa.String(length=30), nullable=False),
        sa.Column(
            "otorgado_en",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "origen IN ('migracion_legacy', 'asignacion_admin', 'creacion_propia')",
            name="ck_usuario_emisor_acceso_origen",
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["otorgado_por_usuario_id"], ["usuarios.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("usuario_id", "empresa_id"),
    )
    op.create_index(
        "ix_usuario_emisor_acceso_empresa",
        "usuario_emisor_acceso",
        ["empresa_id", "usuario_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            "INSERT INTO usuario_emisor_acceso "
            "(usuario_id, empresa_id, otorgado_por_usuario_id, origen, otorgado_en) "
            "SELECT id, empresa_id, NULL, 'migracion_legacy', CURRENT_TIMESTAMP "
            "FROM usuarios WHERE empresa_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    """Contrae a un acceso por usuario conservando el más antiguo."""
    bind = op.get_bind()
    accesos = bind.execute(
        sa.text(
            "SELECT usuario_id, empresa_id, otorgado_en "
            "FROM usuario_emisor_acceso "
            "ORDER BY usuario_id, otorgado_en, empresa_id"
        )
    ).mappings()

    elegido_por_usuario: dict[int, int] = {}
    total_accesos = 0
    for acceso in accesos:
        total_accesos += 1
        elegido_por_usuario.setdefault(
            int(acceso["usuario_id"]), int(acceso["empresa_id"])
        )

    bind.execute(sa.text("UPDATE usuarios SET empresa_id = NULL"))
    for usuario_id, empresa_id in elegido_por_usuario.items():
        bind.execute(
            sa.text(
                "UPDATE usuarios SET empresa_id = :empresa_id WHERE id = :usuario_id"
            ),
            {"usuario_id": usuario_id, "empresa_id": empresa_id},
        )

    descartados = total_accesos - len(elegido_por_usuario)
    inspector = sa.inspect(bind)
    if "eventos_sistema" in inspector.get_table_names():
        bind.execute(
            sa.text(
                "INSERT INTO eventos_sistema "
                "(accion, categoria, estado, descripcion, bytes_afectados, "
                "metadata_json, created_at, usuario_id, empresa_id) "
                "VALUES ('downgrade_operadores_multiemisor', 'migracion', "
                "'exitoso', :descripcion, 0, NULL, CURRENT_TIMESTAMP, NULL, NULL)"
            ),
            {
                "descripcion": (
                    "El downgrade conservó el acceso más antiguo por usuario y "
                    f"descartó {descartados} asignaciones adicionales."
                )
            },
        )

    op.drop_index(
        "ix_usuario_emisor_acceso_empresa", table_name="usuario_emisor_acceso"
    )
    op.drop_table("usuario_emisor_acceso")
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_column("puede_crear_editar_emisores")
