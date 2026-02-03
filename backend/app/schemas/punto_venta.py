"""Schemas para PuntoVenta."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PuntoVentaBase(BaseModel):
    """Base schema para PuntoVenta."""
    numero: int = Field(..., ge=1, le=99999)
    nombre: Optional[str] = Field(None, max_length=255)


class PuntoVentaCreate(PuntoVentaBase):
    """Schema para crear PuntoVenta."""
    pass


class PuntoVentaUpdate(BaseModel):
    """Schema para actualizar PuntoVenta."""
    numero: Optional[int] = Field(None, ge=1, le=99999)
    nombre: Optional[str] = Field(None, max_length=255)
    activo: Optional[bool] = None


class PuntoVentaResponse(PuntoVentaBase):
    """Schema de respuesta de PuntoVenta."""
    id: int
    empresa_id: int
    activo: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
