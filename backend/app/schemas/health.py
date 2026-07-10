"""Esquemas seguros para diagnósticos administrativos de salud."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _HealthAllowlistModel(BaseModel):
    """Ignora cualquier dato interno no declarado en el contrato público."""

    model_config = ConfigDict(extra="ignore")


class DatabasePoolRoleStatusResponse(_HealthAllowlistModel):
    """Expone métricas sanitizadas de un pool de conexiones."""

    pool_size: int | None = None
    max_overflow: int | None = None
    capacity: int | None = None
    checked_out: int | None = None
    checked_in: int | None = None
    overflow: int | None = None
    high_water_mark: int | None = None
    acquisition_count: int | None = None
    timeout_count: int | None = None
    last_wait_ms: float | None = None
    max_wait_ms: float | None = None


class DatabasePoolsStatusResponse(_HealthAllowlistModel):
    """Describe la separación y ocupación de los pools API y worker."""

    separation_required: bool
    separated: bool
    api: DatabasePoolRoleStatusResponse
    worker: DatabasePoolRoleStatusResponse


class LoteWorkerRuntimeStatusResponse(_HealthAllowlistModel):
    """Describe el estado runtime no sensible del worker de lotes."""

    estado: Literal["deshabilitado", "detenido", "esperando", "ocupado"]
    habilitado: bool
    ejecutando: bool
    ocupado: bool
    ciclo_iniciado_at: datetime | None = None
    ciclo_finalizado_at: datetime | None = None
    ultima_duracion_ms: float | None = None
    ultimo_resultado: Literal["exitoso", "error"] | None = None
    ultimo_exito_at: datetime | None = None
    ultimo_error_at: datetime | None = None
    stale_detectados_ultimo_ciclo: int = 0
    lotes_en_cola_ultimo_ciclo: int = 0
    lotes_procesados_ultimo_ciclo: int = 0


class LoteWorkerHealthResponse(_HealthAllowlistModel):
    """Respuesta administrativa combinada del worker y sus pools."""

    status: Literal["healthy", "degraded", "disabled"]
    worker: LoteWorkerRuntimeStatusResponse
    pools: DatabasePoolsStatusResponse
