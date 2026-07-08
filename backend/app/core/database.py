"""Configuración de SQLAlchemy async para la base de datos."""

from typing import AsyncGenerator
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Convertir DATABASE_URL a formato async si es SQLite
database_url = settings.database_url
if database_url.startswith("sqlite:///"):
    database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _habilitar_foreign_keys_sqlite(dbapi_connection, _connection_record) -> None:
    """Activa la aplicación de claves foráneas en cada conexión SQLite."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


# Crear engine async
engine = create_async_engine(
    database_url,
    echo=settings.app_debug,
    future=True,
)

if database_url.startswith("sqlite+aiosqlite:"):
    event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)

# Crear session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Base declarativa para los modelos
class Base(DeclarativeBase):
    """Base class para todos los modelos SQLAlchemy."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obtener sesión de base de datos.

    Yields:
        AsyncSession: Sesión de base de datos
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
