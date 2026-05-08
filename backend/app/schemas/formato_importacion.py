"""Schemas para formatos de importación."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FormatoImportacionVersionResponse(BaseModel):
    """Versión vigente de un formato de importación."""

    id: int
    version: int
    estado: str
    configuracion_json: dict[str, Any]
    headers_firma_json: dict[str, Any] | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class FormatoImportacionResponse(BaseModel):
    """Formato disponible para el emisor activo."""

    id: int
    nombre: str
    descripcion: Optional[str] = None
    alcance: str
    activo: bool
    empresa_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    version_vigente: Optional[FormatoImportacionVersionResponse] = None

    class Config:
        from_attributes = True


class FormatoImportacionCreate(BaseModel):
    """Solicitud para crear un formato particular del emisor."""

    nombre: str = Field(..., min_length=3, max_length=120)
    descripcion: Optional[str] = Field(None, max_length=1000)
    configuracion_json: dict[str, Any]


class FormatoImportacionCandidatoResponse(BaseModel):
    """Candidato detectado para interpretar un Excel."""

    formato_id: Optional[int] = None
    formato_version_id: Optional[int] = None
    nombre: str
    alcance: str
    version: Optional[int] = None
    score: float
    confianza: str
    columnas_detectadas: list[str] = Field(default_factory=list)
    columnas_faltantes: list[str] = Field(default_factory=list)
    mensajes: list[str] = Field(default_factory=list)


class FormatoImportacionDeteccionResponse(BaseModel):
    """Resultado de detectar formatos posibles para un Excel."""

    headers_detectados: list[str]
    candidatos: list[FormatoImportacionCandidatoResponse]
    formato_sugerido_version_id: Optional[int] = None
    requiere_confirmacion: bool = True
