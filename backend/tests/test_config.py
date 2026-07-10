"""Tests de configuración de la aplicación."""

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_SECRET_KEY, Settings


POOL_ENV_KEYS = (
    "DATABASE_API_POOL_SIZE",
    "DATABASE_API_MAX_OVERFLOW",
    "DATABASE_WORKER_POOL_SIZE",
    "DATABASE_POOL_TIMEOUT_SECONDS",
    "DATABASE_POOL_HOLD_WARNING_SECONDS",
)


@pytest.fixture(autouse=True)
def limpiar_entorno_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita que variables reales del entorno alteren estos tests."""
    for key in ("APP_ENV", "APP_SECRET_KEY", *POOL_ENV_KEYS):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize(
    "secret",
    [
        None,
        "",
        DEFAULT_SECRET_KEY,
        "generar-con-python-secrets-token_urlsafe-32",
        "clave-corta",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ],
)
def test_settings_rechaza_secret_inseguro_en_produccion(monkeypatch, secret):
    """Producción no debe iniciar con un secret JWT público o débil."""
    monkeypatch.setenv("APP_ENV", "production")
    if secret is None:
        monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("APP_SECRET_KEY", secret)

    with pytest.raises(ValidationError, match="APP_SECRET_KEY"):
        Settings(_env_file=None)


def test_settings_acepta_secret_seguro_en_produccion(monkeypatch):
    """Producción debe aceptar una clave larga no placeholder."""
    secret = "test-secret-token-urlsafe-32-chars-minimo-2026"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", secret)

    settings = Settings(_env_file=None)

    assert settings.app_env == "production"
    assert settings.secret_key == secret


def test_settings_mantiene_fallback_de_desarrollo(monkeypatch):
    """Desarrollo conserva el fallback para no romper setups locales."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.secret_key == DEFAULT_SECRET_KEY


def test_settings_usa_limites_pool_seguros_por_defecto() -> None:
    """Los defaults deben reservar cuatro conexiones API y una del worker."""
    configured = Settings(_env_file=None)

    assert configured.database_api_pool_size == 4
    assert configured.database_api_max_overflow == 0
    assert configured.database_worker_pool_size == 1
    assert configured.database_pool_timeout_seconds == 5
    assert configured.database_pool_hold_warning_seconds == 10


def test_settings_parsea_limites_pool_validos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los límites admitidos deben poder ajustarse por entorno."""
    monkeypatch.setenv("DATABASE_API_POOL_SIZE", "2")
    monkeypatch.setenv("DATABASE_API_MAX_OVERFLOW", "0")
    monkeypatch.setenv("DATABASE_WORKER_POOL_SIZE", "1")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("DATABASE_POOL_HOLD_WARNING_SECONDS", "3600")

    configured = Settings(_env_file=None)

    assert configured.database_api_pool_size == 2
    assert configured.database_api_max_overflow == 0
    assert configured.database_worker_pool_size == 1
    assert configured.database_pool_timeout_seconds == 60
    assert configured.database_pool_hold_warning_seconds == 3600


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DATABASE_API_POOL_SIZE", "0"),
        ("DATABASE_API_POOL_SIZE", "5"),
        ("DATABASE_API_MAX_OVERFLOW", "-1"),
        ("DATABASE_API_MAX_OVERFLOW", "1"),
        ("DATABASE_WORKER_POOL_SIZE", "0"),
        ("DATABASE_WORKER_POOL_SIZE", "2"),
        ("DATABASE_POOL_TIMEOUT_SECONDS", "0"),
        ("DATABASE_POOL_TIMEOUT_SECONDS", "61"),
        ("DATABASE_POOL_HOLD_WARNING_SECONDS", "0"),
        ("DATABASE_POOL_HOLD_WARNING_SECONDS", "3601"),
    ],
)
def test_settings_rechaza_limites_pool_inseguros(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    value: str,
) -> None:
    """Un pool inválido no debe permitir que la aplicación inicie."""
    monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
