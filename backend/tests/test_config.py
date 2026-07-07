"""Tests de configuración de la aplicación."""

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_SECRET_KEY, Settings


@pytest.fixture(autouse=True)
def limpiar_entorno_settings(monkeypatch):
    """Evita que variables reales del entorno alteren estos tests."""
    for key in ("APP_ENV", "APP_SECRET_KEY"):
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
