"""Configuración y observabilidad segura de SQLAlchemy async."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from typing import Any, AsyncGenerator, Literal, TypedDict

from sqlalchemy import event
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import Pool

from app.core.config import settings

logger = logging.getLogger(__name__)

PoolRole = Literal["api", "worker"]
_CHECKOUT_STARTED_KEY = "factuflow_checkout_started"
_CHECKOUT_ROLE_KEY = "factuflow_checkout_role"
_metrics_lock = Lock()


class DatabasePoolRoleStatus(TypedDict):
    """Estado sanitizado de un pool para un rol de la aplicación."""

    pool_size: int | None
    max_overflow: int | None
    capacity: int | None
    checked_out: int | None
    checked_in: int | None
    overflow: int | None
    high_water_mark: int
    acquisition_count: int
    timeout_count: int
    last_wait_ms: float | None
    max_wait_ms: float


class DatabasePoolStatus(TypedDict):
    """Estado sanitizado de los pools de base de datos."""

    separation_required: bool
    separated: bool
    api: DatabasePoolRoleStatus
    worker: DatabasePoolRoleStatus


@dataclass
class _RoleMetrics:
    """Contadores locales de adquisición por rol."""

    high_water_mark: int = 0
    acquisition_count: int = 0
    timeout_count: int = 0
    last_wait_ms: float | None = None
    max_wait_ms: float = 0.0


@dataclass
class _CheckoutContext:
    """Describe la primera adquisición real esperada por una sesión."""

    role: PoolRole
    started_at: float
    acquisition_recorded: bool = False


_checkout_context: ContextVar[_CheckoutContext | None] = ContextVar(
    "database_checkout_context",
    default=None,
)


_role_metrics: dict[PoolRole, _RoleMetrics] = {
    "api": _RoleMetrics(),
    "worker": _RoleMetrics(),
}


def _normalize_database_url(value: str) -> str:
    """Convierte URLs síncronas conocidas a sus drivers async."""
    if value.startswith("sqlite:///"):
        return value.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


def _is_postgresql_url(value: str) -> bool:
    """Indica si la URL normalizada corresponde a PostgreSQL."""
    return value.startswith("postgresql+")


def _habilitar_foreign_keys_sqlite(
    dbapi_connection: Any, _connection_record: Any
) -> None:
    """Activa la aplicación de claves foráneas en cada conexión SQLite."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _pool_counter(pool: Pool, method_name: str) -> int | None:
    """Lee un contador público de pool cuando el tipo lo ofrece."""
    counter = getattr(pool, method_name, None)
    if not callable(counter):
        return None
    try:
        return int(counter())
    except (TypeError, ValueError):
        return None


def _normalized_overflow(pool: Pool) -> int | None:
    """Devuelve solo conexiones de overflow efectivamente abiertas."""
    overflow = _pool_counter(pool, "overflow")
    if overflow is None:
        return None
    return max(0, overflow)


def _record_high_water(role: PoolRole, checked_out: int | None) -> tuple[int, bool]:
    """Actualiza el máximo de conexiones simultáneas observado."""
    if checked_out is None:
        with _metrics_lock:
            return _role_metrics[role].high_water_mark, False

    with _metrics_lock:
        metrics = _role_metrics[role]
        previous = metrics.high_water_mark
        metrics.high_water_mark = max(previous, checked_out)
        return metrics.high_water_mark, metrics.high_water_mark > previous


def _record_acquisition(
    role: PoolRole,
    wait_ms: float,
    *,
    timed_out: bool,
) -> _RoleMetrics:
    """Registra una adquisición o timeout sin datos de conexión."""
    with _metrics_lock:
        metrics = _role_metrics[role]
        if timed_out:
            metrics.timeout_count += 1
        else:
            metrics.acquisition_count += 1
        metrics.last_wait_ms = wait_ms
        metrics.max_wait_ms = max(metrics.max_wait_ms, wait_ms)
        return _RoleMetrics(
            high_water_mark=metrics.high_water_mark,
            acquisition_count=metrics.acquisition_count,
            timeout_count=metrics.timeout_count,
            last_wait_ms=metrics.last_wait_ms,
            max_wait_ms=metrics.max_wait_ms,
        )


def _copy_role_metrics(role: PoolRole) -> _RoleMetrics:
    """Obtiene una copia consistente de las métricas del rol."""
    with _metrics_lock:
        metrics = _role_metrics[role]
        return _RoleMetrics(
            high_water_mark=metrics.high_water_mark,
            acquisition_count=metrics.acquisition_count,
            timeout_count=metrics.timeout_count,
            last_wait_ms=metrics.last_wait_ms,
            max_wait_ms=metrics.max_wait_ms,
        )


def _register_pool_observability(
    async_engine: AsyncEngine,
    fallback_role: PoolRole,
    capacity: int | None,
) -> None:
    """Registra eventos pasivos y sanitizados sobre un engine async."""
    pool = async_engine.pool

    def on_checkout(
        _dbapi_connection: Any,
        connection_record: Any,
        _connection_proxy: Any,
    ) -> None:
        context = _checkout_context.get()
        role = context.role if context is not None else fallback_role
        checkout_at = perf_counter()
        connection_record.info[_CHECKOUT_STARTED_KEY] = checkout_at
        connection_record.info[_CHECKOUT_ROLE_KEY] = role
        checked_out = _pool_counter(pool, "checkedout")
        if context is not None and not context.acquisition_recorded:
            wait_ms = max(0.0, (checkout_at - context.started_at) * 1000)
            metrics = _record_acquisition(role, wait_ms, timed_out=False)
            context.acquisition_recorded = True
            logger.debug(
                "event=database_pool_acquire role=%s wait_ms=%.2f "
                "checked_out=%s capacity=%s acquisition_count=%s",
                role,
                wait_ms,
                checked_out,
                capacity,
                metrics.acquisition_count,
            )
        high_water_mark, changed = _record_high_water(role, checked_out)
        logger.debug(
            "event=database_pool_checkout role=%s checked_out=%s "
            "overflow=%s high_water_mark=%s",
            role,
            checked_out,
            _normalized_overflow(pool),
            high_water_mark,
        )
        if changed:
            logger.info(
                "event=database_pool_high_water role=%s checked_out=%s "
                "capacity=%s high_water_mark=%s",
                role,
                checked_out,
                capacity,
                high_water_mark,
            )

    def on_checkin(_dbapi_connection: Any, connection_record: Any) -> None:
        started = connection_record.info.pop(_CHECKOUT_STARTED_KEY, None)
        role = connection_record.info.pop(_CHECKOUT_ROLE_KEY, fallback_role)
        if role not in {"api", "worker"}:
            role = fallback_role
        if not isinstance(started, (int, float)):
            return

        held_ms = max(0.0, (perf_counter() - started) * 1000)
        checked_out = _pool_counter(pool, "checkedout")
        logger.debug(
            "event=database_pool_checkin role=%s checked_out=%s "
            "overflow=%s held_ms=%.2f",
            role,
            checked_out,
            _normalized_overflow(pool),
            held_ms,
        )
        if held_ms >= settings.database_pool_hold_warning_seconds * 1000:
            logger.warning(
                "event=database_connection_held role=%s held_ms=%.2f "
                "warning_ms=%.2f checked_out=%s",
                role,
                held_ms,
                settings.database_pool_hold_warning_seconds * 1000,
                checked_out,
            )

    event.listen(async_engine.sync_engine, "checkout", on_checkout)
    event.listen(async_engine.sync_engine, "checkin", on_checkin)


def _create_database_engines(
    database_url_value: str,
) -> tuple[AsyncEngine, AsyncEngine]:
    """Crea engines separados en PostgreSQL y uno compartido en SQLite."""
    normalized_url = _normalize_database_url(database_url_value)
    common_kwargs: dict[str, Any] = {
        "echo": settings.app_debug,
        "future": True,
    }

    if _is_postgresql_url(normalized_url):
        api_engine = create_async_engine(
            normalized_url,
            **common_kwargs,
            pool_pre_ping=True,
            pool_size=settings.database_api_pool_size,
            max_overflow=settings.database_api_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
        )
        batch_worker_engine = create_async_engine(
            normalized_url,
            **common_kwargs,
            pool_pre_ping=True,
            pool_size=settings.database_worker_pool_size,
            max_overflow=0,
            pool_timeout=settings.database_pool_timeout_seconds,
        )
        _register_pool_observability(
            api_engine,
            "api",
            settings.database_api_pool_size + settings.database_api_max_overflow,
        )
        _register_pool_observability(
            batch_worker_engine,
            "worker",
            settings.database_worker_pool_size,
        )
        return api_engine, batch_worker_engine

    api_engine = create_async_engine(normalized_url, **common_kwargs)
    if normalized_url.startswith("sqlite+aiosqlite:"):
        event.listen(
            api_engine.sync_engine,
            "connect",
            _habilitar_foreign_keys_sqlite,
        )
    _register_pool_observability(api_engine, "api", None)
    return api_engine, api_engine


def _create_session_factory(
    bind: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Crea una fábrica homogénea de sesiones async."""
    return async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


database_url = _normalize_database_url(settings.database_url)
engine, worker_engine = _create_database_engines(database_url)
AsyncSessionLocal = _create_session_factory(engine)
WorkerSessionLocal = (
    AsyncSessionLocal
    if worker_engine is engine
    else _create_session_factory(worker_engine)
)


class Base(DeclarativeBase):
    """Clase base para todos los modelos SQLAlchemy."""

    pass


def _pool_limits(role: PoolRole) -> tuple[int | None, int | None]:
    """Devuelve límites configurados solo para pools PostgreSQL."""
    if not _is_postgresql_url(database_url):
        return None, None
    if role == "worker":
        return settings.database_worker_pool_size, 0
    return settings.database_api_pool_size, settings.database_api_max_overflow


def _pool_status(role: PoolRole, async_engine: AsyncEngine) -> DatabasePoolRoleStatus:
    """Construye un snapshot sanitizado para un engine."""
    pool_size, max_overflow = _pool_limits(role)
    capacity = (
        pool_size + max_overflow
        if pool_size is not None and max_overflow is not None
        else None
    )
    metrics = _copy_role_metrics(role)
    return {
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "capacity": capacity,
        "checked_out": _pool_counter(async_engine.pool, "checkedout"),
        "checked_in": _pool_counter(async_engine.pool, "checkedin"),
        "overflow": _normalized_overflow(async_engine.pool),
        "high_water_mark": metrics.high_water_mark,
        "acquisition_count": metrics.acquisition_count,
        "timeout_count": metrics.timeout_count,
        "last_wait_ms": metrics.last_wait_ms,
        "max_wait_ms": metrics.max_wait_ms,
    }


def get_database_pool_status() -> DatabasePoolStatus:
    """Devuelve estado seguro de pools sin URL, credenciales ni datos fiscales."""
    return {
        "separation_required": _is_postgresql_url(database_url),
        "separated": worker_engine is not engine,
        "api": _pool_status("api", engine),
        "worker": _pool_status("worker", worker_engine),
    }


def _record_pool_timeout(role: PoolRole, wait_ms: float) -> None:
    """Registra un timeout del pool sin conservar detalles de conexión."""
    metrics = _record_acquisition(role, wait_ms, timed_out=True)
    status = get_database_pool_status()[role]
    logger.warning(
        "event=database_pool_timeout role=%s wait_ms=%.2f "
        "checked_out=%s capacity=%s high_water_mark=%s timeout_count=%s",
        role,
        wait_ms,
        status["checked_out"],
        status["capacity"],
        metrics.high_water_mark,
        metrics.timeout_count,
    )


async def acquire_database_connection(
    session: AsyncSession,
    role: Literal["api", "worker"],
) -> None:
    """Preadquiere una conexión del worker y registra espera o timeout."""
    context = _CheckoutContext(role=role, started_at=perf_counter())
    token = _checkout_context.set(context)
    try:
        await session.connection()
    except SQLAlchemyTimeoutError:
        wait_ms = max(0.0, (perf_counter() - context.started_at) * 1000)
        _record_pool_timeout(role, wait_ms)
        raise
    else:
        if not context.acquisition_recorded:
            wait_ms = max(0.0, (perf_counter() - context.started_at) * 1000)
            metrics = _record_acquisition(role, wait_ms, timed_out=False)
            context.acquisition_recorded = True
            status = get_database_pool_status()[role]
            logger.debug(
                "event=database_pool_acquire role=%s wait_ms=%.2f "
                "checked_out=%s capacity=%s acquisition_count=%s",
                role,
                wait_ms,
                status["checked_out"],
                status["capacity"],
                metrics.acquisition_count,
            )
    finally:
        _checkout_context.reset(token)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Entrega una sesión API lazy con commit o rollback al finalizar."""
    context = _CheckoutContext(role="api", started_at=perf_counter())
    token = _checkout_context.set(context)
    try:
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except SQLAlchemyTimeoutError:
                wait_ms = (
                    settings.database_pool_timeout_seconds * 1000
                    if context.acquisition_recorded
                    else max(0.0, (perf_counter() - context.started_at) * 1000)
                )
                _record_pool_timeout("api", wait_ms)
                await session.rollback()
                raise
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    finally:
        _checkout_context.reset(token)


async def dispose_database_engines() -> None:
    """Libera los pools API y worker sin disponer dos veces SQLite compartido."""
    if worker_engine is not engine:
        await worker_engine.dispose()
    await engine.dispose()
