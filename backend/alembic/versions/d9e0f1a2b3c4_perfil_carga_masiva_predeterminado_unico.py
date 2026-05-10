"""perfil_carga_masiva_predeterminado_unico

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-05-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Asegura un único perfil de carga masiva predeterminado activo por emisor."""
    op.create_index(
        "uq_perfiles_carga_masiva_predeterminado_activo",
        "perfiles_carga_masiva",
        ["empresa_id"],
        unique=True,
        sqlite_where=sa.text("es_predeterminado = 1 AND activo = 1"),
        postgresql_where=sa.text("es_predeterminado IS TRUE AND activo IS TRUE"),
    )


def downgrade() -> None:
    """Elimina el índice único de perfil de carga masiva predeterminado activo."""
    op.drop_index(
        "uq_perfiles_carga_masiva_predeterminado_activo",
        table_name="perfiles_carga_masiva",
    )
