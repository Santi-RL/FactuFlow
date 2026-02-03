"""Configuración de la aplicación usando Pydantic Settings."""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Configuración global de la aplicación."""
    
    # App
    app_name: str = "FactuFlow"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    
    # Security
    secret_key: str = Field(
        default="cambiar-esto-en-produccion-usar-secrets-token_urlsafe",
        alias="APP_SECRET_KEY"
    )
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = Field(default=1440, alias="JWT_EXPIRATION_MINUTES")  # 24 horas
    
    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/factuflow.db",
        alias="DATABASE_URL"
    )
    
    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:8080", "http://127.0.0.1:8080"],
        alias="CORS_ORIGINS"
    )
    
    # AFIP
    afip_env: str = Field(default="homologacion", alias="AFIP_ENV")
    afip_certs_path: str = Field(default="./certs", alias="AFIP_CERTS_PATH")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    class Config:
        """Configuración de Pydantic Settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Allow parsing comma-separated values for lists
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name == "cors_origins":
                return [origin.strip() for origin in raw_val.split(",")]
            return raw_val


settings = Settings()
