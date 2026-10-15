"""PF-04/PF-02: evidencia previa inmutable, sin completar antecedentes."""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

_COLUMNS = ("evidencia_version", "evidencia_json", "evidencia_hash")
_CHECK = (
    "(evidencia_version IS NULL AND evidencia_json IS NULL AND evidencia_hash IS NULL) OR "
    "(evidencia_version IS NOT NULL AND evidencia_json IS NOT NULL AND evidencia_hash IS NOT NULL "
    "AND evidencia_version = 'solicitud_fiscal/1' AND length(evidencia_hash) = 64 AND "
    + "".join("replace(" for _ in range(16))
    + "evidencia_hash"
    + "".join(f", '{char}', '')" for char in "0123456789abcdef")
    + " = '')"
)


def upgrade():
    with op.batch_alter_table("intentos_emision_fiscal") as batch:
        batch.add_column(sa.Column("evidencia_version", sa.String(30), nullable=True))
        batch.add_column(sa.Column("evidencia_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("evidencia_hash", sa.String(64), nullable=True))
        batch.create_check_constraint("ck_intentos_emision_fiscal_evidencia", _CHECK)


def downgrade():
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            "SELECT 1 FROM intentos_emision_fiscal WHERE "
            + " OR ".join(f"{name} IS NOT NULL" for name in _COLUMNS)
            + " LIMIT 1"
        )
    ).first():
        raise RuntimeError(
            "El downgrade eliminaría evidencia fiscal; conservá el esquema ampliado"
        )
    with op.batch_alter_table("intentos_emision_fiscal") as batch:
        batch.drop_constraint("ck_intentos_emision_fiscal_evidencia", type_="check")
        for name in _COLUMNS:
            batch.drop_column(name)
