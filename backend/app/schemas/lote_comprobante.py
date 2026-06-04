"""Schemas para emisión masiva de comprobantes."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoteComprobanteFilaResponse(BaseModel):
    """Representa una fila validada del Excel."""

    id: int
    fila_excel: int
    comprobante_ref: str
    estado: str
    datos_json: dict[str, Any] | None = None
    mensajes_json: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class LoteComprobanteGrupoResponse(BaseModel):
    """Representa un comprobante agrupado dentro del lote."""

    id: int
    comprobante_ref: str
    orden: int
    estado: str
    tipo_comprobante: Optional[int] = None
    concepto: Optional[int] = None
    punto_venta_numero: Optional[int] = None
    cliente_documento: Optional[str] = None
    cliente_razon_social: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_servicio_desde: Optional[date] = None
    fecha_servicio_hasta: Optional[date] = None
    fecha_vto_pago: Optional[date] = None
    total_estimado: Decimal = Decimal("0")
    mensajes_json: list[str] = Field(default_factory=list)
    cae: Optional[str] = None
    numero_asignado: Optional[int] = None
    comprobante_id: Optional[int] = None

    class Config:
        from_attributes = True


class LoteComprobanteGrupoDetalleResponse(LoteComprobanteGrupoResponse):
    """Representa un comprobante agrupado con datos derivados para la UI."""

    descripcion_facturada: Optional[str] = None


class LoteComprobanteResponse(BaseModel):
    """Representa el estado general de un lote."""

    id: int
    nombre_archivo: str
    archivo_hash: str
    estado: str
    modo_procesamiento: str
    procesamiento_async: bool
    total_filas: int
    total_grupos: int
    grupos_validos: int
    grupos_con_error: int
    grupos_emitidos: int
    grupos_fallidos: int
    grupos_reconciliados_externos: int = 0
    grupos_descartados: int = 0
    mensaje_resumen: Optional[str] = None
    metadata_json: dict[str, Any] | None = None
    mapeo_usado_json: dict[str, Any] | None = None
    headers_detectados_json: list[str] | None = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    compactado_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    empresa_id: int
    usuario_id: Optional[int] = None
    formato_importacion_id: Optional[int] = None
    formato_importacion_version_id: Optional[int] = None

    class Config:
        from_attributes = True


class LoteComprobanteDetalleResponse(LoteComprobanteResponse):
    """Incluye el detalle de grupos y filas del lote."""

    grupos: list[LoteComprobanteGrupoResponse] = Field(default_factory=list)
    filas: list[LoteComprobanteFilaResponse] = Field(default_factory=list)


class LoteTotalesListosResponse(BaseModel):
    """Totales agregados de los comprobantes válidos del lote."""

    comprobantes: int = 0
    neto: float = 0
    iva21: float = 0
    iva105: float = 0
    total: float = 0
    valores_invalidos: int = 0


class LoteComprobanteResumenResponse(LoteComprobanteResponse):
    """Resumen operativo liviano para abrir lotes grandes."""

    confirmacion_fecha_fiscal: str = ""
    mensaje_confirmacion_fecha_fiscal: str = ""
    confirmacion_reintento_fallidos: str = ""
    mensaje_confirmacion_reintento_fallidos: str = ""
    confirmacion_duplicado_logico: str = ""
    mensaje_confirmacion_duplicado_logico: str = ""
    cantidad_duplicados_logicos: int = 0
    fechas_emision_validas: list[str] = Field(default_factory=list)
    puntos_venta_validos: list[int] = Field(default_factory=list)
    totales_listos_para_emitir: LoteTotalesListosResponse = Field(
        default_factory=LoteTotalesListosResponse
    )


class LoteComprobanteGruposPageResponse(BaseModel):
    """Página de comprobantes agrupados de un lote."""

    items: list[LoteComprobanteGrupoDetalleResponse] = Field(default_factory=list)
    page: int
    per_page: int
    total: int
    total_pages: int
    estado: Optional[str] = None


class LoteValidacionResponse(BaseModel):
    """Respuesta de validación o creación del lote."""

    lote: LoteComprobanteResponse
    puede_emitirse: bool
    requiere_background: bool
    mensaje: str


class LoteProcesamientoResponse(BaseModel):
    """Respuesta al iniciar o completar la emisión de un lote."""

    lote: LoteComprobanteResponse
    mensaje: str
    en_progreso: bool


class LoteGrupoIdsRequest(BaseModel):
    """Selección explícita de grupos de un lote."""

    model_config = ConfigDict(extra="forbid")

    grupo_ids: list[int] = Field(default_factory=list)


class LoteDescartarGruposRequest(BaseModel):
    """Request para descartar grupos pendientes."""

    model_config = ConfigDict(extra="forbid")

    grupo_ids: list[int] = Field(..., min_length=1)
    motivo: str = Field(..., min_length=3, max_length=500)


class LoteEliminarCompactarRequest(BaseModel):
    """Request con motivo obligatorio para acciones destructivas o compactación."""

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(..., min_length=3, max_length=500)


class LoteReconciliacionExternaItem(BaseModel):
    """Datos confirmados de un comprobante emitido fuera de FactuFlow."""

    model_config = ConfigDict(extra="forbid")

    grupo_id: int
    tipo_comprobante: int = Field(..., ge=1, le=999)
    punto_venta_numero: int = Field(..., ge=1, le=99999)
    numero: int = Field(..., ge=1)
    fecha_emision: date
    total: Decimal = Field(..., ge=0)
    cae: Optional[str] = Field(None, min_length=1, max_length=20)
    motivo: str = Field(..., min_length=3, max_length=500)


class LoteReconciliacionExternaRequest(BaseModel):
    """Request para reconciliar comprobantes emitidos en ARCA Web."""

    model_config = ConfigDict(extra="forbid")

    comprobantes: list[LoteReconciliacionExternaItem] = Field(..., min_length=1)


class LoteAccionResponse(BaseModel):
    """Respuesta genérica de una acción resolutiva de lote."""

    lote: LoteComprobanteResponse
    mensaje: str
