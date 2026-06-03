"""Agregar revocación de tokens por cambio de contraseña."""

from alembic import op
import sqlalchemy as sa


revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Agregar timestamp de último cambio de contraseña."""
    op.add_column(
        "usuarios",
        sa.Column("password_changed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Quitar timestamp de último cambio de contraseña."""
    op.drop_column("usuarios", "password_changed_at")
