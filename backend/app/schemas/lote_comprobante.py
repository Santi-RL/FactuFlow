"""Schemas para emisión masiva de comprobantes."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


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
    punto_venta_numero: Optional[int] = None
    cliente_documento: Optional[str] = None
    cliente_razon_social: Optional[str] = None
    total_estimado: Decimal = Decimal("0")
    mensajes_json: list[str] = Field(default_factory=list)
    cae: Optional[str] = None
    numero_asignado: Optional[int] = None
    comprobante_id: Optional[int] = None

    class Config:
        from_attributes = True


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
    mensaje_resumen: Optional[str] = None
    metadata_json: dict[str, Any] | None = None
    mapeo_usado_json: dict[str, Any] | None = None
    headers_detectados_json: list[str] | None = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
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
