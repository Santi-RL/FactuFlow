"""Fixtures de origen histórico: el ORM nuevo no define las bases v3/v4."""

from sqlalchemy import MetaData, Index

from app.core.database import Base
from app.core.fiscal_storage_legacy import LEGACY_COLUMNS


def legacy_metadata():
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    for table_name, columns in LEGACY_COLUMNS.items():
        table = metadata.tables[table_name]
        for name, old_type in columns.items():
            table.c[name].type = old_type
        if table_name == "lotes_comprobantes_grupos":
            for index in list(table.indexes):
                if "cotizacion_busqueda" in index.columns:
                    names = [
                        (
                            "cotizacion_duplicados"
                            if c.name == "cotizacion_busqueda"
                            else c.name
                        )
                        for c in index.columns
                    ]
                    table.indexes.remove(index)
                    Index(index.name, *(table.c[name] for name in names))
            table._columns.remove(table.c.cotizacion_busqueda)
    return metadata
