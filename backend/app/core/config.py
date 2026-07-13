"""Configuración de la aplicación usando Pydantic Settings."""

import os
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SECRET_KEY = "cambiar-esto-en-produccion-usar-secrets-token_urlsafe"
INSECURE_PRODUCTION_SECRET_KEYS = {
    DEFAULT_SECRET_KEY,
    "generar-con-python-secrets-token_urlsafe-32",
}
MIN_PRODUCTION_SECRET_LENGTH = 32
PRODUCTION_ENV_NAMES = {"production", "prod", "produccion"}


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
    app_version: str = "0.2.2"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")

    # Security
    secret_key: str = Field(
        default=DEFAULT_SECRET_KEY,
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
    database_api_pool_size: int = Field(
        default=4,
        ge=1,
        le=4,
        alias="DATABASE_API_POOL_SIZE",
    )
    database_api_max_overflow: int = Field(
        default=0,
        ge=0,
        le=0,
        alias="DATABASE_API_MAX_OVERFLOW",
    )
    database_worker_pool_size: int = Field(
        default=1,
        ge=1,
        le=1,
        alias="DATABASE_WORKER_POOL_SIZE",
    )
    database_pool_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        le=60,
        alias="DATABASE_POOL_TIMEOUT_SECONDS",
    )
    database_pool_hold_warning_seconds: float = Field(
        default=10.0,
        gt=0,
        le=3600,
        alias="DATABASE_POOL_HOLD_WARNING_SECONDS",
    )

    # CORS - can be string or list
    cors_origins: str | List[str] = Field(
        default="http://localhost:8080,http://127.0.0.1:8080", alias="CORS_ORIGINS"
    )

    # ARCA
    arca_env: str = Field(default="homologacion", alias="ARCA_ENV")
    certs_path: str = Field(default="./certs", alias="CERTS_PATH")
    arca_private_key_password: Optional[str] = Field(
        default=None, alias="ARCA_PRIVATE_KEY_PASSWORD"
    )
    arca_token_cache_path: str = Field(
        default="./data/arca_token_cache.json", alias="ARCA_TOKEN_CACHE_PATH"
    )
    certificate_max_upload_bytes: int = Field(
        default=64 * 1024, alias="CERTIFICATE_MAX_UPLOAD_BYTES"
    )
    batch_sync_limit: int = Field(default=100, alias="BATCH_SYNC_LIMIT")
    batch_max_upload_bytes: int = Field(
        default=10 * 1024 * 1024, alias="BATCH_MAX_UPLOAD_BYTES"
    )
    batch_max_rows: int = Field(default=20000, alias="BATCH_MAX_ROWS")
    batch_max_groups: int = Field(default=5000, alias="BATCH_MAX_GROUPS")
    batch_worker_enabled: bool = Field(default=True, alias="BATCH_WORKER_ENABLED")
    batch_worker_poll_seconds: int = Field(default=5, alias="BATCH_WORKER_POLL_SECONDS")
    batch_worker_batch_size: int = Field(default=1, alias="BATCH_WORKER_BATCH_SIZE")
    batch_processing_stale_minutes: int = Field(
        default=120, alias="BATCH_PROCESSING_STALE_MINUTES"
    )
    fiscal_attempt_stale_minutes: int = Field(
        default=120, alias="FISCAL_ATTEMPT_STALE_MINUTES"
    )
    arca_fecaesolicitar_batch_enabled: bool = Field(
        default=True, alias="ARCA_FECAESOLICITAR_BATCH_ENABLED"
    )
    arca_fecaesolicitar_batch_max_registros: int = Field(
        default=0, alias="ARCA_FECAESOLICITAR_BATCH_MAX_REGISTROS"
    )
    storage_limit_bytes: Optional[int] = Field(
        default=None, alias="STORAGE_LIMIT_BYTES"
    )
    storage_tmp_path: str = Field(default="./data/tmp", alias="STORAGE_TMP_PATH")
    storage_log_retention_days: int = Field(
        default=30, alias="STORAGE_LOG_RETENTION_DAYS"
    )
    storage_enable_cleanup: bool = Field(default=True, alias="STORAGE_ENABLE_CLEANUP")

    @model_validator(mode="after")
    def validate_production_secret_key(self) -> "Settings":
        """Rechaza secretos JWT inseguros en entornos productivos."""
        if self.app_env.strip().lower() not in PRODUCTION_ENV_NAMES:
            return self

        secret = self.secret_key.strip()
        if (
            not secret
            or secret in INSECURE_PRODUCTION_SECRET_KEYS
            or len(secret) < MIN_PRODUCTION_SECRET_LENGTH
            or len(set(secret)) < 8
        ):
            raise ValueError(
                "APP_SECRET_KEY debe configurarse en producción con una clave "
                "secreta segura generada con secrets.token_urlsafe(32)"
            )
        return self

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
