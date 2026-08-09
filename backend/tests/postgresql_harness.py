"""Guard central para pruebas PostgreSQL locales y de CI."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


POSTGRES_URL_ENV = "FACTUFLOW_TEST_POSTGRES_URL"
SCHEMA_RESET_ENV = "FACTUFLOW_TEST_POSTGRES_ALLOW_SCHEMA_RESET"
DISPOSABLE_DATABASE_NAME = "factuflow_integration_test"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def validate_disposable_postgres_url(
    configured_url: str,
    *,
    schema_reset_opt_in: str,
) -> str:
    """Valida sin conectar una URL PostgreSQL inequívocamente descartable."""
    if schema_reset_opt_in != "1":
        pytest.fail(
            f"{SCHEMA_RESET_ENV}=1 es obligatorio para usar el harness PostgreSQL"
        )

    raw_url = configured_url.strip()
    try:
        parsed = make_url(raw_url)
    except (ArgumentError, TypeError, ValueError):
        pytest.fail(f"{POSTGRES_URL_ENV} no contiene una URL válida")

    if parsed.get_backend_name() != "postgresql":
        pytest.fail(f"{POSTGRES_URL_ENV} debe apuntar a PostgreSQL")
    if parsed.drivername not in {"postgresql", "postgresql+asyncpg"}:
        pytest.fail(f"{POSTGRES_URL_ENV} solo admite postgresql o postgresql+asyncpg")
    if parsed.query:
        pytest.fail(
            f"{POSTGRES_URL_ENV} no admite parámetros query, sockets ni options"
        )
    if parsed.host not in LOOPBACK_HOSTS:
        pytest.fail(
            f"{POSTGRES_URL_ENV} debe usar un host loopback exacto "
            "(localhost, 127.0.0.1 o ::1)"
        )
    if parsed.database != DISPOSABLE_DATABASE_NAME:
        pytest.fail(
            f"{POSTGRES_URL_ENV} debe usar exactamente la base "
            f"{DISPOSABLE_DATABASE_NAME}"
        )

    normalized = parsed.set(drivername="postgresql+asyncpg")
    return normalized.render_as_string(hide_password=False)


def require_disposable_postgres_url(*, purpose: str) -> str:
    """Obtiene la URL descartable o salta cuando no fue configurada."""
    configured_url = os.getenv(POSTGRES_URL_ENV, "").strip()
    if not configured_url:
        pytest.skip(f"Requiere PostgreSQL desechable explícito para {purpose}")
    return validate_disposable_postgres_url(
        configured_url,
        schema_reset_opt_in=os.getenv(SCHEMA_RESET_ENV, ""),
    )
