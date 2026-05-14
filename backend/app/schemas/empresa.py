"""Schemas para Empresa."""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.provincias import normalizar_provincia_argentina


class EmpresaBase(BaseModel):
    """Base schema para Empresa."""

    razon_social: str = Field(..., min_length=1, max_length=255)
    cuit: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    condicion_iva: str = Field(..., pattern=r"^(RI|Monotributo|Exento)$")
    ingresos_brutos: Optional[str] = Field(None, max_length=50)
    domicilio: str = Field(..., min_length=1, max_length=255)
    localidad: str = Field(..., min_length=1, max_length=100)
    provincia: str = Field(..., min_length=1, max_length=100)
    codigo_postal: str = Field(..., min_length=1, max_length=10)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=50)
    inicio_actividades: date
    logo: Optional[str] = None

    @field_validator("provincia", mode="before")
    @classmethod
    def validar_provincia(cls, value: str) -> str:
        """Validar y normalizar provincia argentina."""
        provincia = normalizar_provincia_argentina(value)
        if not provincia:
            raise ValueError("La provincia debe ser una provincia argentina valida")
        return provincia


class EmpresaCreate(EmpresaBase):
    """Schema para crear Empresa."""

    pass


class EmpresaUpdate(BaseModel):
    """Schema para actualizar Empresa."""

    razon_social: Optional[str] = Field(None, min_length=1, max_length=255)
    cuit: Optional[str] = Field(None, min_length=11, max_length=11, pattern=r"^\d{11}$")
    condicion_iva: Optional[str] = Field(None, pattern=r"^(RI|Monotributo|Exento)$")
    ingresos_brutos: Optional[str] = Field(None, max_length=50)
    domicilio: Optional[str] = Field(None, min_length=1, max_length=255)
    localidad: Optional[str] = Field(None, min_length=1, max_length=100)
    provincia: Optional[str] = Field(None, min_length=1, max_length=100)
    codigo_postal: Optional[str] = Field(None, min_length=1, max_length=10)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=50)
    inicio_actividades: Optional[date] = None
    logo: Optional[str] = None

    @field_validator("provincia", mode="before")
    @classmethod
    def validar_provincia(cls, value: Optional[str]) -> Optional[str]:
        """Validar y normalizar provincia argentina cuando se informa."""
        if value is None:
            return None
        provincia = normalizar_provincia_argentina(value)
        if not provincia:
            raise ValueError("La provincia debe ser una provincia argentina valida")
        return provincia


class EmpresaResponse(EmpresaBase):
    """Schema de respuesta de Empresa."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConstanciaArcaResponse(BaseModel):
    """Datos detectados desde una constancia de inscripcion ARCA."""

    razon_social: Optional[str] = None
    cuit: Optional[str] = None
    condicion_iva: Optional[str] = None
    domicilio: Optional[str] = None
    localidad: Optional[str] = None
    provincia: Optional[str] = None
    codigo_postal: Optional[str] = None
    inicio_actividades: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
