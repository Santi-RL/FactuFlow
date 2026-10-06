"""A-01: persistencia decimal fiel y capacidad auxiliar de duplicados.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from collections import Counter
from decimal import Decimal

from alembic import op
import sqlalchemy as sa

from app.core.fiscal_storage import (
    ExactAmount,
    ExactDecimal,
    ExactInteger,
    decimal_search_key,
    encode_decimal,
    scaled_integer,
)
from app.core.fiscal_storage_legacy import (
    LEGACY_COLUMNS,
    VARIABLE_COLUMNS,
    legacy_read,
    legacy_roundtrip,
)

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _new_type(name):
    if name in {"codigo", "cotizacion_duplicados"}:
        return sa.Text()
    if name == "total_centavos":
        return ExactInteger()
    return ExactDecimal() if name in VARIABLE_COLUMNS else ExactAmount()


def _value(raw, name, old_type, dialect, upgrade):
    if raw is None:
        return None
    if upgrade:
        value = legacy_read(raw, old_type, dialect)
    elif isinstance(old_type, (sa.Numeric, sa.Integer)):
        value = Decimal(raw)
    else:
        value = raw
    if isinstance(old_type, sa.Numeric):
        encode_decimal(value)
    if name == "cotizacion_duplicados":
        decimal_search_key(Decimal(value))
    if name == "total_centavos":
        scaled_integer(value)
    return value


def _rows(bind, table_name):
    # Lectura DBAPI sin modelos actuales ni procesadores del destino.
    return bind.exec_driver_sql(f'SELECT * FROM "{table_name}"').mappings()


def _preflight(bind, upgrade):
    conflicts = Counter()
    for table_name, columns in LEGACY_COLUMNS.items():
        for row in _rows(bind, table_name):
            for name, old_type in columns.items():
                try:
                    value = _value(row[name], name, old_type, bind.dialect, upgrade)
                    if not upgrade and not legacy_roundtrip(
                        value, old_type, bind.dialect
                    ):
                        raise ValueError("No conserva el round-trip histórico")
                except (ValueError, ArithmeticError, TypeError, OverflowError):
                    conflicts[f"{table_name}.{name}"] += 1
    if conflicts:
        counts = ", ".join(
            f"{name}={count}" for name, count in sorted(conflicts.items())
        )
        raise RuntimeError(
            f"A-01: preflight incompatible, sin modificar datos: {counts}"
        )


def _sqlite_rebuild(bind, upgrade):
    if bind.exec_driver_sql("PRAGMA foreign_keys").scalar() != 0:
        raise RuntimeError("A-01 requiere la frontera SQLite atómica de Alembic")
    metadata = sa.MetaData()
    metadata.reflect(bind)
    for table_name, columns in LEGACY_COLUMNS.items():
        source = metadata.tables[table_name]
        target = source.to_metadata(metadata, name=f"_a01_{table_name}")
        indexes = list(target.indexes)
        target.indexes.clear()
        for name, old_type in columns.items():
            target.c[name].type = _new_type(name) if upgrade else old_type
        if table_name == "lotes_comprobantes_grupos":
            if upgrade:
                target.append_column(sa.Column("cotizacion_busqueda", sa.String(64)))
            else:
                target._columns.remove(target.c.cotizacion_busqueda)
        target.create(bind)
        names = [column.name for column in target.columns]
        quoted = ", ".join(f'"{name}"' for name in names)
        placeholders = ", ".join("?" for _ in names)
        statement = f'INSERT INTO "{target.name}" ({quoted}) VALUES ({placeholders})'
        batch = []
        for row in _rows(bind, table_name):
            values = dict(row)
            for name, old_type in columns.items():
                value = _value(row[name], name, old_type, bind.dialect, upgrade)
                if value is not None and isinstance(old_type, sa.Numeric):
                    value = encode_decimal(value) if upgrade else float(value)
                elif value is not None and name == "total_centavos":
                    value = (
                        str(scaled_integer(value)) if upgrade else scaled_integer(value)
                    )
                values[name] = value
            if upgrade and table_name == "lotes_comprobantes_grupos":
                quotation = values["cotizacion_duplicados"]
                values["cotizacion_busqueda"] = (
                    decimal_search_key(Decimal(quotation))
                    if quotation is not None
                    else None
                )
            batch.append(tuple(values[name] for name in names))
            if len(batch) == 250:
                bind.exec_driver_sql(statement, batch)
                batch = []
        if batch:
            bind.exec_driver_sql(statement, batch)
        bind.exec_driver_sql(f'DROP TABLE "{table_name}"')
        bind.exec_driver_sql(f'ALTER TABLE "{target.name}" RENAME TO "{table_name}"')
        for index in indexes:
            column_names = [column.name for column in index.columns]
            if index.name in {
                "ix_lotes_grupos_dup_nombre",
                "ix_lotes_grupos_dup_documento",
            }:
                column_names = [
                    (
                        ("cotizacion_busqueda" if upgrade else "cotizacion_duplicados")
                        if name in {"cotizacion_duplicados", "cotizacion_busqueda"}
                        else name
                    )
                    for name in column_names
                ]
            quoted_columns = ", ".join(f'"{name}"' for name in column_names)
            where = index.dialect_options["sqlite"].get("where")
            predicate = f" WHERE {where}" if where is not None else ""
            bind.exec_driver_sql(
                f'CREATE {"UNIQUE " if index.unique else ""}INDEX "{index.name}" '
                f'ON "{table_name}" ({quoted_columns}){predicate}'
            )
    if bind.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
        raise RuntimeError("A-01: el grafo de claves foráneas no verifica")


def _postgres_alter(bind, upgrade):
    for index in ("ix_lotes_grupos_dup_nombre", "ix_lotes_grupos_dup_documento"):
        op.drop_index(index, table_name="lotes_comprobantes_grupos")
    if upgrade:
        op.add_column(
            "lotes_comprobantes_grupos", sa.Column("cotizacion_busqueda", sa.String(64))
        )
    for table_name, columns in LEGACY_COLUMNS.items():
        for name, old_type in columns.items():
            target_type = _new_type(name) if upgrade else old_type
            physical = target_type.compile(dialect=bind.dialect)
            op.alter_column(
                table_name,
                name,
                type_=target_type,
                postgresql_using=f'"{name}"::{physical}',
            )
        if upgrade:
            for row in _rows(bind, table_name):
                updates = {}
                for name in VARIABLE_COLUMNS.intersection(columns):
                    updates[name] = encode_decimal(Decimal(row[name]))
                if table_name == "lotes_comprobantes_grupos":
                    value = row["cotizacion_duplicados"]
                    updates["cotizacion_busqueda"] = (
                        decimal_search_key(Decimal(value))
                        if value is not None
                        else None
                    )
                if updates:
                    assignment = ", ".join(f'"{name}"=:{name}' for name in updates)
                    bind.execute(
                        sa.text(f'UPDATE "{table_name}" SET {assignment} WHERE id=:id'),
                        {**updates, "id": row["id"]},
                    )
    if not upgrade:
        op.drop_column("lotes_comprobantes_grupos", "cotizacion_busqueda")
    for suffix in ("nombre", "documento"):
        op.create_index(
            f"ix_lotes_grupos_dup_{suffix}",
            "lotes_comprobantes_grupos",
            [
                "empresa_id",
                "ambiente",
                "tipo_comprobante",
                "punto_venta_numero",
                "fecha_emision_normalizada",
                "moneda_duplicados",
                "cotizacion_busqueda" if upgrade else "cotizacion_duplicados",
                "total_centavos",
                f"identidad_{suffix}_hash",
            ],
        )


def _migrate(upgrade):
    bind = op.get_bind()
    _preflight(bind, upgrade)
    if bind.dialect.name == "sqlite":
        _sqlite_rebuild(bind, upgrade)
    elif bind.dialect.name == "postgresql":
        _postgres_alter(bind, upgrade)
    else:
        raise RuntimeError("A-01 sólo admite SQLite y PostgreSQL")


def upgrade():
    _migrate(True)


def downgrade():
    _migrate(False)
