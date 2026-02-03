"""Schemas para Cliente."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class ClienteBase(BaseModel):
    """Base schema para Cliente."""
    razon_social: str = Field(..., min_length=1, max_length=255)
    tipo_documento: str = Field(..., pattern=r"^(CUIT|CUIL|DNI|LE|LC|Pasaporte|CI)$")
    numero_documento: str = Field(..., min_length=1, max_length=20)
    condicion_iva: str = Field(..., pattern=r"^(RI|Monotributo|CF|Exento)$")
    domicilio: Optional[str] = Field(None, max_length=255)
    localidad: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=100)
    codigo_postal: Optional[str] = Field(None, max_length=10)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=50)
    notas: Optional[str] = Field(None, max_length=500)


class ClienteCreate(ClienteBase):
    """Schema para crear Cliente."""
    pass


class ClienteUpdate(BaseModel):
    """Schema para actualizar Cliente."""
    razon_social: Optional[str] = Field(None, min_length=1, max_length=255)
    tipo_documento: Optional[str] = Field(None, pattern=r"^(CUIT|CUIL|DNI|LE|LC|Pasaporte|CI)$")
    numero_documento: Optional[str] = Field(None, min_length=1, max_length=20)
    condicion_iva: Optional[str] = Field(None, pattern=r"^(RI|Monotributo|CF|Exento)$")
    domicilio: Optional[str] = Field(None, max_length=255)
    localidad: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=100)
    codigo_postal: Optional[str] = Field(None, max_length=10)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=50)
    notas: Optional[str] = Field(None, max_length=500)
    activo: Optional[bool] = None


class ClienteResponse(ClienteBase):
    """Schema de respuesta de Cliente."""
    id: int
    empresa_id: int
    activo: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ClienteList(BaseModel):
    """Schema para listado paginado de Clientes."""
    items: list[ClienteResponse]
    total: int
    page: int
    per_page: int
    pages: int
