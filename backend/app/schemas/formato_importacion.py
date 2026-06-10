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
    """Solicitud para crear una plantilla de importación."""

    nombre: str = Field(..., min_length=3, max_length=120)
    descripcion: Optional[str] = Field(None, max_length=1000)
    alcance: str = Field("emisor", pattern="^(global|emisor)$")
    configuracion_json: dict[str, Any]


class FormatoImportacionUpdate(BaseModel):
    """Solicitud para actualizar una plantilla con nueva versión."""

    nombre: Optional[str] = Field(None, min_length=3, max_length=120)
    descripcion: Optional[str] = Field(None, max_length=1000)
    alcance: Optional[str] = Field(None, pattern="^(global|emisor)$")
    configuracion_json: Optional[dict[str, Any]] = None


class FormatoImportacionClone(BaseModel):
    """Solicitud para clonar una plantilla existente."""

    nombre: Optional[str] = Field(None, min_length=3, max_length=120)
    alcance: str = Field("emisor", pattern="^(global|emisor)$")


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


class FormatoImportacionCampoCatalogoResponse(BaseModel):
    """Campo FactuFlow disponible para plantillas visuales."""

    codigo: str
    etiqueta: str
    grupo: str
    descripcion: str
    requerido_base: bool = False
    transformaciones: list[str] = Field(default_factory=list)
    origenes: list[str] = Field(default_factory=list)


class FormatoImportacionExcelColumnaResponse(BaseModel):
    """Columna detectada en un Excel de ejemplo."""

    indice: int
    letra: str
    encabezado: str


class FormatoImportacionExcelAnalisisResponse(BaseModel):
    """Resultado de analizar encabezados de un Excel de ejemplo."""

    hoja: str
    fila_encabezado: int
    columnas: list[FormatoImportacionExcelColumnaResponse]


class FormatoImportacionCompatibilidadRequest(BaseModel):
    """Entrada para evaluar plantilla, perfil y emisor."""

    configuracion_json: dict[str, Any]
    perfil_configuracion_json: Optional[dict[str, Any]] = None


class FormatoImportacionCompatibilidadMensaje(BaseModel):
    """Mensaje accionable de compatibilidad."""

    codigo: str
    campo: Optional[str] = None
    severidad: str
    mensaje: str


class FormatoImportacionCompatibilidadResponse(BaseModel):
    """Resultado de compatibilidad de una plantilla visual."""

    estado: str
    faltantes: list[FormatoImportacionCompatibilidadMensaje] = Field(
        default_factory=list
    )
    omitibles: list[FormatoImportacionCompatibilidadMensaje] = Field(
        default_factory=list
    )
    advertencias: list[FormatoImportacionCompatibilidadMensaje] = Field(
        default_factory=list
    )
    conflictos: list[FormatoImportacionCompatibilidadMensaje] = Field(
        default_factory=list
    )
