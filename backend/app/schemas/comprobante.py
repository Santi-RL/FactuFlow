"""Schemas de Comprobante - Facturas, Notas de Crédito y Débito."""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

# ==================== Items ====================


class ItemComprobanteBase(BaseModel):
    """Schema base de Item de Comprobante."""

    codigo: Optional[str] = None
    descripcion: str = Field(..., min_length=1, max_length=500)
    cantidad: Decimal = Field(..., gt=0)
    unidad: str = Field(default="unidades", max_length=50)
    precio_unitario: Decimal = Field(..., ge=0)
    descuento_porcentaje: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    iva_porcentaje: Decimal = Field(..., ge=0)  # 21, 10.5, 27, 0
    orden: int = Field(default=0, ge=0)


class ItemComprobanteCreate(ItemComprobanteBase):
    """Schema para crear Item de Comprobante."""

    pass


class ItemComprobanteResponse(ItemComprobanteBase):
    """Schema de respuesta de Item de Comprobante."""

    id: int
    subtotal: Decimal
    comprobante_id: int

    class Config:
        from_attributes = True


# ==================== Comprobante ====================


class ComprobanteBase(BaseModel):
    """Schema base de Comprobante."""

    tipo_comprobante: int = Field(..., ge=1, le=999)
    observaciones: Optional[str] = Field(None, max_length=500)
    moneda: str = Field(default="PES", max_length=3)
    cotizacion: Decimal = Field(default=Decimal("1"), gt=0)


class EmitirComprobanteRequest(ComprobanteBase):
    """
    Request para emitir un comprobante.

    Incluye todos los datos necesarios para generar
    el comprobante y solicitar el CAE a ARCA.
    """

    empresa_id: int
    punto_venta_id: int
    concepto: int = Field(default=1, ge=1, le=3)  # 1=Productos, 2=Servicios, 3=Ambos

    # Cliente/Receptor
    cliente_id: Optional[int] = None  # Si es cliente guardado
    tipo_documento: int = Field(..., ge=1)  # 80=CUIT, 96=DNI, etc.
    numero_documento: str = Field(..., min_length=1, max_length=20)
    razon_social: str = Field(..., min_length=1, max_length=200)
    condicion_iva: str = Field(..., max_length=50)
    domicilio: Optional[str] = Field(None, max_length=200)

    # Items
    items: List[ItemComprobanteCreate] = Field(..., min_length=1)

    # Servicios (si concepto = 2 o 3)
    fecha_servicio_desde: Optional[date] = None
    fecha_servicio_hasta: Optional[date] = None
    fecha_vto_pago: Optional[date] = None

    @field_validator("items")
    @classmethod
    def validate_items(cls, v):
        if not v or len(v) == 0:
            raise ValueError("Debe incluir al menos un ítem")
        return v

    @field_validator("fecha_servicio_hasta")
    @classmethod
    def validate_fecha_servicio(cls, v, info):
        if v and info.data.get("fecha_servicio_desde"):
            if v < info.data["fecha_servicio_desde"]:
                raise ValueError("La fecha hasta no puede ser menor a la fecha desde")
        return v


class EmitirComprobanteResponse(BaseModel):
    """Respuesta al emitir un comprobante."""

    exito: bool
    comprobante_id: Optional[int] = None
    tipo_comprobante: int
    punto_venta: int
    numero: int
    fecha: date
    cae: Optional[str] = None
    cae_vencimiento: Optional[date] = None
    total: Decimal
    mensaje: str
    errores: List[str] = Field(default_factory=list)


class ComprobanteResponse(ComprobanteBase):
    """Schema de respuesta de Comprobante."""

    id: int
    numero: int
    fecha_emision: date
    fecha_vencimiento: Optional[date] = None
    subtotal: Decimal
    descuento: Decimal
    iva_21: Decimal
    iva_10_5: Decimal
    iva_27: Decimal
    otros_impuestos: Decimal
    total: Decimal
    cae: Optional[str] = None
    cae_vencimiento: Optional[date] = None
    estado: str

    # Relaciones
    empresa_id: int
    punto_venta_id: int
    cliente_id: int

    class Config:
        from_attributes = True


class ComprobanteDetalleResponse(ComprobanteResponse):
    """Schema de respuesta de Comprobante con detalles completos."""

    items: List[ItemComprobanteResponse] = Field(default_factory=list)

    # Datos del cliente
    cliente_nombre: Optional[str] = None
    cliente_cuit: Optional[str] = None

    # Datos del punto de venta
    punto_venta_numero: Optional[int] = None

    class Config:
        from_attributes = True


class ComprobanteListResponse(BaseModel):
    """Schema para listado de comprobantes."""

    id: int
    tipo_comprobante: int
    numero: int
    fecha_emision: date
    total: Decimal
    estado: str
    cae: Optional[str] = None

    # Datos básicos del cliente
    cliente_nombre: str
    cliente_documento: str

    # Datos del punto de venta
    punto_venta_numero: int

    class Config:
        from_attributes = True


class PaginatedComprobantesResponse(BaseModel):
    """Respuesta paginada de comprobantes."""

    items: List[ComprobanteListResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ProximoNumeroResponse(BaseModel):
    """Respuesta con el próximo número de comprobante."""

    punto_venta: int
    tipo_comprobante: int
    proximo_numero: int
