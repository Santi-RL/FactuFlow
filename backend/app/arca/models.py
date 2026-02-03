"""Modelos Pydantic para requests y responses de ARCA."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ==================== WSAA Models ====================

class TicketAcceso(BaseModel):
    """Ticket de Acceso obtenido del WSAA."""
    
    token: str = Field(..., description="Token de autenticación")
    sign: str = Field(..., description="Firma digital")
    expiracion: datetime = Field(..., description="Fecha de expiración del ticket")
    servicio: str = Field(default="wsfe", description="Servicio para el que se solicitó el ticket")
    
    def is_expired(self) -> bool:
        """Verifica si el ticket está expirado."""
        return datetime.utcnow() >= self.expiracion


# ==================== WSFEv1 Models ====================

class IvaItem(BaseModel):
    """Item de IVA en un comprobante."""
    
    id: int = Field(..., description="ID de alícuota IVA (5=21%, 4=10.5%, 6=27%, 3=0%, 8=5%)")
    base_imp: float = Field(..., description="Base imponible", alias="BaseImp")
    importe: float = Field(..., description="Importe de IVA", alias="Importe")
    
    class Config:
        populate_by_name = True


class TributoItem(BaseModel):
    """Item de tributo adicional en un comprobante."""
    
    id: int = Field(..., description="ID del tributo")
    descripcion: str = Field(..., description="Descripción del tributo", alias="Desc")
    base_imp: float = Field(..., description="Base imponible", alias="BaseImp")
    alic: float = Field(..., description="Alícuota", alias="Alic")
    importe: float = Field(..., description="Importe del tributo", alias="Importe")
    
    class Config:
        populate_by_name = True


class ComprobanteRequest(BaseModel):
    """Request para solicitar CAE de un comprobante."""
    
    # Datos del comprobante
    punto_venta: int = Field(..., ge=1, le=99999, description="Punto de venta")
    tipo_cbte: int = Field(..., description="Tipo de comprobante (1=FA, 6=FB, 11=FC, etc.)")
    concepto: int = Field(default=1, description="Concepto (1=Productos, 2=Servicios, 3=Ambos)")
    
    # Cliente
    tipo_doc: int = Field(..., description="Tipo de documento (80=CUIT, 96=DNI, 99=Sin identificar)")
    nro_doc: int = Field(..., description="Número de documento")
    
    # Numeración
    cbte_desde: int = Field(..., description="Número de comprobante desde")
    cbte_hasta: int = Field(..., description="Número de comprobante hasta")
    
    # Fecha
    fecha_cbte: str = Field(..., description="Fecha del comprobante (YYYYMMDD)")
    fecha_vto_pago: Optional[str] = Field(None, description="Fecha de vencimiento de pago (YYYYMMDD)")
    fecha_serv_desde: Optional[str] = Field(None, description="Fecha desde servicio (YYYYMMDD)")
    fecha_serv_hasta: Optional[str] = Field(None, description="Fecha hasta servicio (YYYYMMDD)")
    
    # Importes
    imp_total: float = Field(..., description="Importe total")
    imp_neto: float = Field(..., description="Importe neto gravado")
    imp_iva: float = Field(default=0, description="Importe IVA")
    imp_op_ex: float = Field(default=0, description="Importe operaciones exentas")
    imp_tot_conc: float = Field(default=0, description="Importe total de conceptos no gravados")
    imp_trib: float = Field(default=0, description="Importe tributos")
    
    # Moneda
    moneda_id: str = Field(default="PES", description="ID de moneda (PES=Pesos, DOL=Dólares)")
    moneda_cotiz: float = Field(default=1, description="Cotización de moneda")
    
    # Observaciones
    observaciones: Optional[str] = Field(None, max_length=500, description="Observaciones")
    
    # Items adicionales
    iva: List[IvaItem] = Field(default_factory=list, description="Items de IVA")
    tributos: List[TributoItem] = Field(default_factory=list, description="Tributos adicionales")
    
    @field_validator("fecha_cbte", "fecha_vto_pago", "fecha_serv_desde", "fecha_serv_hasta")
    @classmethod
    def validate_date_format(cls, v: str | None) -> str | None:
        """Valida que las fechas estén en formato YYYYMMDD."""
        if v is None:
            return v
        
        if len(v) != 8 or not v.isdigit():
            raise ValueError(f"Fecha debe estar en formato YYYYMMDD, recibido: {v}")
        
        return v


class Observacion(BaseModel):
    """Observación devuelta por ARCA."""
    
    code: int = Field(..., description="Código de observación")
    msg: str = Field(..., description="Mensaje de observación")


class ErrorArca(BaseModel):
    """Error devuelto por ARCA."""
    
    code: int = Field(..., description="Código de error")
    msg: str = Field(..., description="Mensaje de error")


class CAEResponse(BaseModel):
    """Response de solicitud de CAE."""
    
    # CAE
    cae: Optional[str] = Field(None, description="Código de Autorización Electrónica")
    cae_vencimiento: Optional[str] = Field(None, description="Fecha de vencimiento del CAE (YYYYMMDD)")
    
    # Comprobante
    numero_comprobante: int = Field(..., description="Número de comprobante autorizado")
    tipo_cbte: int = Field(..., description="Tipo de comprobante")
    punto_venta: int = Field(..., description="Punto de venta")
    
    # Resultado
    resultado: str = Field(..., description="Resultado (A=Aprobado, R=Rechazado, P=Parcial)")
    
    # Mensajes
    observaciones: List[Observacion] = Field(default_factory=list, description="Observaciones")
    errores: List[ErrorArca] = Field(default_factory=list, description="Errores")
    
    @property
    def is_aprobado(self) -> bool:
        """Verifica si el comprobante fue aprobado."""
        return self.resultado == "A"
    
    @property
    def is_rechazado(self) -> bool:
        """Verifica si el comprobante fue rechazado."""
        return self.resultado == "R"


class ComprobanteResponse(BaseModel):
    """Response de consulta de comprobante."""
    
    # Identificación
    punto_venta: int
    tipo_cbte: int
    numero: int
    cuit_emisor: str
    
    # CAE
    cae: str
    cae_vencimiento: str
    
    # Fecha
    fecha_cbte: str
    fecha_proceso: str
    
    # Importes
    imp_total: float
    imp_neto: float
    imp_iva: float
    imp_op_ex: float
    imp_tot_conc: float
    imp_trib: float
    
    # Moneda
    moneda_id: str
    moneda_cotiz: float
    
    # Cliente
    tipo_doc: int
    nro_doc: int
    
    # Estado
    resultado: str


# ==================== Parámetros ARCA ====================

class TipoComprobante(BaseModel):
    """Tipo de comprobante."""
    
    id: int = Field(..., description="ID del tipo de comprobante")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(None, description="Fecha hasta", alias="FchHasta")
    
    class Config:
        populate_by_name = True


class TipoDocumento(BaseModel):
    """Tipo de documento."""
    
    id: int = Field(..., description="ID del tipo de documento")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(None, description="Fecha hasta", alias="FchHasta")
    
    class Config:
        populate_by_name = True


class TipoIva(BaseModel):
    """Tipo de IVA."""
    
    id: int = Field(..., description="ID de la alícuota de IVA")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(None, description="Fecha hasta", alias="FchHasta")
    
    class Config:
        populate_by_name = True


class TipoConcepto(BaseModel):
    """Tipo de concepto."""
    
    id: int = Field(..., description="ID del concepto")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(None, description="Fecha hasta", alias="FchHasta")
    
    class Config:
        populate_by_name = True


class TipoMoneda(BaseModel):
    """Tipo de moneda."""
    
    id: str = Field(..., description="ID de la moneda")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(None, description="Fecha hasta", alias="FchHasta")
    
    class Config:
        populate_by_name = True


class Cotizacion(BaseModel):
    """Cotización de moneda."""
    
    moneda_id: str = Field(..., description="ID de la moneda")
    cotizacion: float = Field(..., description="Cotización")
    fecha: str = Field(..., description="Fecha de la cotización")


class PuntoVenta(BaseModel):
    """Punto de venta habilitado."""
    
    numero: int = Field(..., description="Número de punto de venta")
    emision_tipo: str = Field(..., description="Tipo de emisión")
    bloqueado: str = Field(..., description="Estado de bloqueo")
    fecha_baja: Optional[str] = Field(None, description="Fecha de baja")
