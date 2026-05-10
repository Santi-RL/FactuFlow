"""Schemas para perfiles de carga masiva por emisor."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PerfilCargaMasivaBase(BaseModel):
    """Datos editables de un perfil de carga masiva."""

    nombre: str = Field(..., min_length=3, max_length=120)
    descripcion: Optional[str] = Field(None, max_length=1000)
    configuracion_json: dict[str, Any]
    es_predeterminado: bool = False
    activo: bool = True


class PerfilCargaMasivaCreate(PerfilCargaMasivaBase):
    """Solicitud para crear un perfil de carga masiva."""


class PerfilCargaMasivaUpdate(BaseModel):
    """Solicitud para actualizar un perfil de carga masiva."""

    nombre: Optional[str] = Field(None, min_length=3, max_length=120)
    descripcion: Optional[str] = Field(None, max_length=1000)
    configuracion_json: Optional[dict[str, Any]] = None
    es_predeterminado: Optional[bool] = None
    activo: Optional[bool] = None


class PerfilCargaMasivaResponse(PerfilCargaMasivaBase):
    """Perfil de carga masiva disponible para el emisor activo."""

    id: int
    empresa_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
