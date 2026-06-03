"""Schemas del gestor de almacenamiento."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EstadoAlmacenamiento = Literal["correcto", "necesita_atencion", "critico"]


class AlmacenamientoCategoriaResponse(BaseModel):
    """Uso resumido de una categoría de almacenamiento."""

    clave: str
    nombre: str
    bytes_usados: int = 0
    bytes_recuperables: int = 0
    items: int = 0
    estado: EstadoAlmacenamiento = "correcto"
    descripcion: str = ""


class AlmacenamientoEmisorResponse(BaseModel):
    """Uso lógico seguro asociado a un emisor."""

    empresa_id: int
    etiqueta: str
    lotes: int = 0
    filas_persistidas: int = 0
    filas_compactables: int = 0
    comprobantes: int = 0
    bytes_estimados: int = 0
    bytes_recuperables: int = 0


class AlmacenamientoResumenResponse(BaseModel):
    """Resumen general del almacenamiento visible para administradores."""

    generated_at: datetime
    estado: EstadoAlmacenamiento
    total_bytes_usados: int = 0
    total_bytes_recuperables: int = 0
    storage_limit_bytes: int | None = None
    disk_total_bytes: int | None = None
    disk_used_bytes: int | None = None
    disk_free_bytes: int | None = None
    categorias: list[AlmacenamientoCategoriaResponse] = Field(default_factory=list)
    emisores: list[AlmacenamientoEmisorResponse] = Field(default_factory=list)


class AlmacenamientoItemResponse(BaseModel):
    """Elemento seleccionable para exportación o limpieza."""

    id: str
    nombre: str
    categoria: str
    bytes_usados: int = 0
    bytes_recuperables: int = 0
    descripcion: str = ""
    created_at: datetime | None = None


class LoteCompactableResponse(BaseModel):
    """Lote cerrado cuyo detalle de filas puede compactarse."""

    id: int
    empresa_id: int
    etiqueta_emisor: str
    estado: str
    total_filas: int
    total_grupos: int
    filas_persistidas: int
    bytes_recuperables: int
    created_at: datetime
    finished_at: datetime | None = None


class CrearExportacionAlmacenamientoRequest(BaseModel):
    """Selección de recursos para crear un ZIP de resguardo."""

    model_config = ConfigDict(extra="forbid")

    lote_ids: list[int] = Field(default_factory=list)
    log_ids: list[str] = Field(default_factory=list)
    temporal_ids: list[str] = Field(default_factory=list)


class ExportacionAlmacenamientoResponse(BaseModel):
    """Metadatos de una exportación preparada para descargar."""

    token: str
    estado: str
    archivo_nombre: str
    checksum_sha256: str
    size_bytes: int
    created_at: datetime
    downloaded_at: datetime | None = None
    released_at: datetime | None = None
    manifest: dict


class ConfirmarLiberacionRequest(BaseModel):
    """Confirmación manual posterior a la descarga del resguardo."""

    model_config = ConfigDict(extra="forbid")

    confirmacion: str = Field(..., min_length=1, max_length=50)


class ConfirmarDescargaExportacionRequest(BaseModel):
    """Confirmación explícita de que el ZIP llegó al cliente."""

    model_config = ConfigDict(extra="forbid")

    checksum_sha256: str = Field(..., min_length=64, max_length=64)
    download_token: str = Field(..., min_length=16, max_length=128)


class LimpiarArchivosAlmacenamientoRequest(BaseModel):
    """Selección explícita de archivos administrados a limpiar."""

    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(..., min_length=1)


class AccionAlmacenamientoResponse(BaseModel):
    """Resultado de una acción de mantenimiento."""

    mensaje: str
    bytes_afectados: int = 0
    items_afectados: int = 0
