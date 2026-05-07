"""Schemas para PuntoVenta."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PuntoVentaBase(BaseModel):
    """Base schema para PuntoVenta."""

    numero: int = Field(..., ge=1, le=99999)
    nombre: Optional[str] = Field(None, max_length=255)
    sistema: Optional[str] = Field(None, max_length=255)
    domicilio: Optional[str] = Field(None, max_length=500)
    nombre_fantasia: Optional[str] = Field(None, max_length=255)
    es_webservice: bool = False
    bloqueado: bool = False
    fecha_baja: Optional[str] = Field(None, max_length=20)
    fuente: Optional[str] = Field(None, max_length=50)


class PuntoVentaCreate(PuntoVentaBase):
    """Schema para crear PuntoVenta."""

    pass


class PuntoVentaUpdate(BaseModel):
    """Schema para actualizar PuntoVenta."""

    numero: Optional[int] = Field(None, ge=1, le=99999)
    nombre: Optional[str] = Field(None, max_length=255)
    sistema: Optional[str] = Field(None, max_length=255)
    domicilio: Optional[str] = Field(None, max_length=500)
    nombre_fantasia: Optional[str] = Field(None, max_length=255)
    es_webservice: Optional[bool] = None
    bloqueado: Optional[bool] = None
    fecha_baja: Optional[str] = Field(None, max_length=20)
    fuente: Optional[str] = Field(None, max_length=50)
    activo: Optional[bool] = None


class ImportarPuntosVentaResponse(BaseModel):
    """Resultado de importacion de constancia de puntos de venta."""

    total_constancia: int
    creados: int
    actualizados: int
    omitidos: int
    warnings: list[str] = []


class PuntoVentaResponse(PuntoVentaBase):
    """Schema de respuesta de PuntoVenta."""

    id: int
    empresa_id: int
    activo: bool
    usable_factuflow: bool
    created_at: datetime

    class Config:
        from_attributes = True
