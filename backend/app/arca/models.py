"""Modelos Pydantic para requests y responses de ARCA."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from pydantic import (
    ConfigDict,
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.arca.utils import format_date_arca

# ==================== WSAA Models ====================


class TicketAcceso(BaseModel):
    """Ticket de Acceso obtenido del WSAA."""

    token: str = Field(..., description="Token de autenticación")
    sign: str = Field(..., description="Firma digital")
    expiracion: datetime = Field(..., description="Fecha de expiración del ticket")
    servicio: str = Field(
        default="wsfe", description="Servicio para el que se solicitó el ticket"
    )

    def is_expired(self) -> bool:
        """Verifica si el ticket está expirado."""
        now = datetime.now(timezone.utc)
        expiration = self.expiracion
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        return now >= expiration


# ==================== WSFEv1 Models ====================


class IvaItem(BaseModel):
    """Item de IVA en un comprobante."""

    id: int = Field(
        ..., description="ID de alícuota IVA (5=21%, 4=10.5%, 6=27%, 3=0%, 8=5%)"
    )
    base_imp: Decimal = Field(..., description="Base imponible", alias="BaseImp")
    importe: Decimal = Field(..., description="Importe de IVA", alias="Importe")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=False)


class TributoItem(BaseModel):
    """Item de tributo adicional en un comprobante."""

    id: int = Field(..., description="ID del tributo")
    descripcion: str = Field(..., description="Descripción del tributo", alias="Desc")
    base_imp: Decimal = Field(..., description="Base imponible", alias="BaseImp")
    alic: Decimal = Field(..., description="Alícuota", alias="Alic")
    importe: Decimal = Field(..., description="Importe del tributo", alias="Importe")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=False)


class CbteAsocItem(BaseModel):
    """Comprobante asociado informado a WSFE."""

    tipo: int = Field(..., description="Tipo de comprobante asociado")
    punto_venta: int = Field(..., description="Punto de venta asociado")
    numero: int = Field(..., description="Número del comprobante asociado")
    cuit: Optional[str] = Field(None, description="CUIT del emisor asociado")
    fecha_cbte: Optional[str] = Field(
        None, description="Fecha del comprobante asociado (YYYYMMDD)"
    )

    @field_validator("fecha_cbte", mode="before")
    @classmethod
    def validate_fecha_cbte(cls, v: date | datetime | str | None) -> str | None:
        """Valida y normaliza la fecha del comprobante asociado."""
        if v in (None, ""):
            return None
        return format_date_arca(v)


class ComprobanteRequest(BaseModel):
    """Request para solicitar CAE de un comprobante."""

    # Datos del comprobante
    punto_venta: int = Field(..., ge=1, le=99999, description="Punto de venta")
    tipo_cbte: int = Field(
        ..., description="Tipo de comprobante (1=FA, 6=FB, 11=FC, etc.)"
    )
    concepto: int = Field(
        ..., description="Concepto (1=Productos, 2=Servicios, 3=Ambos)"
    )

    # Cliente
    tipo_doc: int = Field(
        ..., description="Tipo de documento (80=CUIT, 96=DNI, 99=Sin identificar)"
    )
    nro_doc: int = Field(..., description="Número de documento")

    # Numeración
    cbte_desde: int = Field(..., description="Número de comprobante desde")
    cbte_hasta: int = Field(..., description="Número de comprobante hasta")

    # Fecha
    fecha_cbte: str = Field(..., description="Fecha del comprobante (YYYYMMDD)")
    fecha_vto_pago: Optional[str] = Field(
        None, description="Fecha de vencimiento de pago (YYYYMMDD)"
    )
    fecha_serv_desde: Optional[str] = Field(
        None, description="Fecha desde servicio (YYYYMMDD)"
    )
    fecha_serv_hasta: Optional[str] = Field(
        None, description="Fecha hasta servicio (YYYYMMDD)"
    )

    # Importes
    imp_total: Decimal = Field(..., description="Importe total")
    imp_neto: Decimal = Field(..., description="Importe neto gravado")
    imp_iva: Decimal = Field(default=Decimal("0"), description="Importe IVA")
    imp_op_ex: Decimal = Field(
        default=Decimal("0"), description="Importe operaciones exentas"
    )
    imp_tot_conc: Decimal = Field(
        default=Decimal("0"), description="Importe total de conceptos no gravados"
    )
    imp_trib: Decimal = Field(default=Decimal("0"), description="Importe tributos")

    # Moneda
    moneda_id: str = Field(
        default="PES", description="ID de moneda (PES=Pesos, DOL=Dólares)"
    )
    moneda_cotiz: Decimal = Field(
        default=Decimal("1"), description="Cotización de moneda"
    )
    condicion_iva_receptor_id: Optional[int] = Field(
        None, description="ID de condición frente al IVA del receptor"
    )

    # Observaciones
    observaciones: Optional[str] = Field(
        None, max_length=500, description="Observaciones"
    )

    # Items adicionales
    iva: List[IvaItem] = Field(default_factory=list, description="Items de IVA")
    tributos: List[TributoItem] = Field(
        default_factory=list, description="Tributos adicionales"
    )
    cbtes_asoc: List[CbteAsocItem] = Field(
        default_factory=list, description="Comprobantes asociados"
    )

    @field_validator("fecha_cbte", mode="before")
    @classmethod
    def validate_fecha_cbte(cls, v: date | datetime | str) -> str:
        """Valida y normaliza la fecha fiscal del comprobante."""
        return format_date_arca(v)

    @field_validator(
        "fecha_vto_pago", "fecha_serv_desde", "fecha_serv_hasta", mode="before"
    )
    @classmethod
    def validate_optional_date_format(
        cls, v: date | datetime | str | None
    ) -> str | None:
        """Valida y normaliza fechas fiscales opcionales."""
        if v in (None, ""):
            return None
        return format_date_arca(v)

    @model_validator(mode="after")
    def validate_fechas_servicio(self) -> "ComprobanteRequest":
        """Exige fechas de servicio para comprobantes de servicios o mixtos."""
        if self.concepto in {2, 3}:
            faltantes = [
                nombre
                for nombre in (
                    "fecha_serv_desde",
                    "fecha_serv_hasta",
                    "fecha_vto_pago",
                )
                if not getattr(self, nombre)
            ]
            if faltantes:
                raise ValueError(
                    "Los comprobantes de servicios o mixtos requieren fechas "
                    f"de servicio y vencimiento: {', '.join(faltantes)}"
                )
        return self


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
    cae_vencimiento: Optional[str] = Field(
        None, description="Fecha de vencimiento del CAE (YYYYMMDD)"
    )

    # Comprobante
    numero_comprobante: int = Field(..., description="Número de comprobante autorizado")
    tipo_cbte: int = Field(..., description="Tipo de comprobante")
    punto_venta: int = Field(..., description="Punto de venta")

    # Resultado
    resultado: str = Field(
        ..., description="Resultado (A=Aprobado, R=Rechazado, P=Parcial)"
    )
    requiere_reconciliacion: bool = Field(
        default=False, description="Respuesta correlacionada pero contradictoria"
    )

    # Mensajes
    observaciones: List[Observacion] = Field(
        default_factory=list, description="Observaciones"
    )
    errores: List[ErrorArca] = Field(default_factory=list, description="Errores")

    @property
    def is_aprobado(self) -> bool:
        """Verifica si el comprobante fue aprobado."""
        return self.resultado == "A" and not self.requiere_reconciliacion

    @property
    def is_rechazado(self) -> bool:
        """Verifica si el comprobante fue rechazado."""
        return self.resultado == "R" and not self.requiere_reconciliacion


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
    fecha_cbte: Optional[str] = None
    fecha_proceso: Optional[str] = None

    # Importes
    imp_total: Optional[Decimal] = None
    imp_neto: Optional[Decimal] = None
    imp_iva: Optional[Decimal] = None
    imp_op_ex: Optional[Decimal] = None
    imp_tot_conc: Optional[Decimal] = None
    imp_trib: Optional[Decimal] = None

    # Moneda
    moneda_id: Optional[str] = None
    moneda_cotiz: Optional[Decimal] = None

    # Cliente
    tipo_doc: Optional[int] = None
    nro_doc: Optional[int] = None

    # Estado
    resultado: str

    # None conserva la cobertura desconocida de respuestas antiguas.
    concepto: Optional[int] = None
    emision_tipo: Optional[str] = None
    cbte_desde: Optional[int] = None
    cbte_hasta: Optional[int] = None
    condicion_iva_receptor_id: Optional[int] = None
    fecha_serv_desde: Optional[str] = None
    fecha_serv_hasta: Optional[str] = None
    fecha_vto_pago: Optional[str] = None
    iva: Optional[List[IvaItem]] = None
    tributos: Optional[List[TributoItem]] = None
    cbtes_asoc: Optional[List[CbteAsocItem]] = None
    adicionales_presentes: List[str] = Field(default_factory=list)
    campos_invalidos: List[str] = Field(default_factory=list)

    model_config = ConfigDict(allow_inf_nan=False)

    @property
    def datos_basicos_completos(self) -> bool:
        """Preserva el contrato de consumidores que no admiten consulta parcial."""
        return not self.campos_invalidos and all(
            getattr(self, campo) is not None
            for campo in (
                "fecha_cbte",
                "fecha_proceso",
                "imp_total",
                "imp_neto",
                "imp_iva",
                "imp_op_ex",
                "imp_tot_conc",
                "imp_trib",
                "moneda_id",
                "moneda_cotiz",
                "tipo_doc",
                "nro_doc",
            )
        )

    @field_serializer(
        "imp_total",
        "imp_neto",
        "imp_iva",
        "imp_op_ex",
        "imp_tot_conc",
        "imp_trib",
        "moneda_cotiz",
        when_used="json",
    )
    def serializar_numero_consulta(self, valor: Optional[Decimal]) -> Optional[float]:
        """Mantiene el contrato HTTP numérico; se compara el Decimal original."""
        return float(valor) if valor is not None else None


# ==================== Parámetros ARCA ====================


class TipoComprobante(BaseModel):
    """Tipo de comprobante."""

    id: int = Field(..., description="ID del tipo de comprobante")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(
        None, description="Fecha hasta", alias="FchHasta"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=False)


class TipoDocumento(BaseModel):
    """Tipo de documento."""

    id: int = Field(..., description="ID del tipo de documento")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(
        None, description="Fecha hasta", alias="FchHasta"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=False)


class TipoIva(BaseModel):
    """Tipo de IVA."""

    id: int = Field(..., description="ID de la alícuota de IVA")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(
        None, description="Fecha hasta", alias="FchHasta"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=False)


class TipoConcepto(BaseModel):
    """Tipo de concepto."""

    id: int = Field(..., description="ID del concepto")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(
        None, description="Fecha hasta", alias="FchHasta"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=False)


class TipoMoneda(BaseModel):
    """Tipo de moneda."""

    id: str = Field(..., description="ID de la moneda")
    descripcion: str = Field(..., description="Descripción", alias="Desc")
    fecha_desde: str = Field(..., description="Fecha desde", alias="FchDesde")
    fecha_hasta: Optional[str] = Field(
        None, description="Fecha hasta", alias="FchHasta"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=False)


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
