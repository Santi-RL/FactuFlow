"""Schemas para PuntoVenta."""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def rechazar_nulos_en_campos_no_nulos(self) -> "PuntoVentaUpdate":
        """Rechaza nulos explícitos que la base no puede representar."""
        for campo in {"numero", "es_webservice", "bloqueado", "activo"}:
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"El campo {campo} no puede ser nulo")
        return self


class ImportarPuntosVentaResponse(BaseModel):
    """Resultado de importacion de constancia de puntos de venta."""

    total_constancia: int
    creados: int
    actualizados: int
    omitidos: int
    desactivados_ausentes: int = 0
    verificados_rece: int = 0
    pendientes_comprobacion: int = 0
    no_verificados_rece: int = 0
    listos_para_emitir: int = 0
    no_disponibles_factuflow: int = 0
    requieren_revision: int = 0
    documento_emitido_en: date | None = None
    vigente_hasta: date | None = None
    warnings: list[str] = Field(default_factory=list)


class SincronizarPuntosVentaResponse(BaseModel):
    """Resultado de una sincronización técnica transaccional con WSFE."""

    total_arca: int
    nuevos: int
    existentes: int
    actualizados: int
    desactivados_ausentes: int
    comprobado_en: datetime


class ElegibilidadReceResponse(BaseModel):
    """Estado efectivo RECE visible, sin material probatorio privado."""

    ambiente: Literal["homologacion", "produccion"]
    estado: Literal["verificado_rece", "no_rece", "no_verificado"]
    estado_efectivo: Literal["verificado_rece", "no_rece", "no_verificado"]
    fuente: str | None = None
    revision_id: int | None = None
    revision: int | None = None
    punto_revision_fiscal: int | None = None
    verificado_en: datetime | None = None
    vigente_hasta: date | None = None
    motivo: str | None = None


class PuntoVentaResponse(PuntoVentaBase):
    """Schema de respuesta de PuntoVenta."""

    id: int
    empresa_id: int
    activo: bool
    usable_factuflow: bool
    puede_intentar_emision: bool
    seleccionable_para_emision: bool
    ultima_comprobacion_arca_en: datetime | None = None
    comprobacion_arca_desactualizada: bool
    revision_fiscal: int
    elegibilidad_rece: ElegibilidadReceResponse
    created_at: datetime

    class Config:
        from_attributes = True
