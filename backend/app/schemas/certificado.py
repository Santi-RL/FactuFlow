"""Schemas para Certificado."""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


class CertificadoBase(BaseModel):
    """Base schema para Certificado."""
    nombre: str = Field(..., min_length=1, max_length=255)
    cuit: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    fecha_emision: date
    fecha_vencimiento: date
    ambiente: str = Field(..., pattern=r"^(homologacion|produccion)$")


class CertificadoCreate(CertificadoBase):
    """Schema para crear Certificado."""
    archivo_crt: str
    archivo_key: str


class CertificadoUpdate(BaseModel):
    """Schema para actualizar Certificado."""
    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    activo: Optional[bool] = None


class CertificadoResponse(CertificadoBase):
    """Schema de respuesta de Certificado."""
    id: int
    empresa_id: int
    archivo_crt: str
    archivo_key: str
    activo: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
