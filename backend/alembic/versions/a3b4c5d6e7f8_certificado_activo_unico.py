"""Certificado activo unico por emisor y ambiente.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Desactiva duplicados y garantiza un certificado activo por ambiente."""
    dialect = op.get_context().dialect.name
    active_clause = "activo IS TRUE" if dialect == "postgresql" else "activo = 1"

    op.execute(
        sa.text(
            f"""
            UPDATE certificados
            SET activo = FALSE
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY empresa_id, ambiente
                            ORDER BY fecha_vencimiento DESC, created_at DESC, id DESC
                        ) AS rn
                    FROM certificados
                    WHERE {active_clause}
                ) ranked
                WHERE rn > 1
            )
            """
        )
    )

    op.create_index(
        "ux_certificados_activo_empresa_ambiente",
        "certificados",
        ["empresa_id", "ambiente"],
        unique=True,
        sqlite_where=sa.text("activo = 1"),
        postgresql_where=sa.text("activo IS TRUE"),
    )


def downgrade() -> None:
    """Elimina el indice parcial de certificado activo unico."""
    op.drop_index("ux_certificados_activo_empresa_ambiente", table_name="certificados")
