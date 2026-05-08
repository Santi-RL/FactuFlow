"""Configuración de la aplicación usando Pydantic Settings."""

import os
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env
    )

    # App
    app_name: str = "FactuFlow"
    app_version: str = "0.2.0-mvp"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")

    # Security
    secret_key: str = Field(
        default="cambiar-esto-en-produccion-usar-secrets-token_urlsafe",
        alias="APP_SECRET_KEY",
    )
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = Field(
        default=1440, alias="JWT_EXPIRATION_MINUTES"
    )  # 24 horas

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/factuflow.db", alias="DATABASE_URL"
    )

    # CORS - can be string or list
    cors_origins: str | List[str] = Field(
        default="http://localhost:8080,http://127.0.0.1:8080", alias="CORS_ORIGINS"
    )

    # ARCA
    arca_env: str = Field(default="homologacion", alias="ARCA_ENV")
    certs_path: str = Field(default="./certs", alias="CERTS_PATH")
    arca_token_cache_path: str = Field(
        default="./data/arca_token_cache.json", alias="ARCA_TOKEN_CACHE_PATH"
    )
    batch_sync_limit: int = Field(default=100, alias="BATCH_SYNC_LIMIT")
    batch_max_rows: int = Field(default=20000, alias="BATCH_MAX_ROWS")
    batch_max_groups: int = Field(default=5000, alias="BATCH_MAX_GROUPS")
    batch_worker_enabled: bool = Field(default=True, alias="BATCH_WORKER_ENABLED")
    batch_worker_poll_seconds: int = Field(default=5, alias="BATCH_WORKER_POLL_SECONDS")
    batch_worker_batch_size: int = Field(default=1, alias="BATCH_WORKER_BATCH_SIZE")

    @field_validator("certs_path", mode="before")
    @classmethod
    def parse_certs_path(cls, v, _info):
        """Parse certs path, con fallback legacy a AFIP_CERTS_PATH."""
        if v is None or v == "./certs":
            afip_path = os.getenv("AFIP_CERTS_PATH")
            if afip_path:
                return afip_path
        return v

    @field_validator("arca_env", mode="before")
    @classmethod
    def parse_arca_env(cls, v, _info):
        """Permite usar ARCA_ENV y mantiene compatibilidad con AFIP_ENV."""
        if not v:
            legacy = os.getenv("AFIP_ENV")
            if legacy:
                return legacy
        return v or "homologacion"

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: Optional[str] = Field(default=None, alias="LOG_FILE")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from string to list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


settings = Settings()
