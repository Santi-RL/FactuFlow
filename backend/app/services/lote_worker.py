"""Worker persistente para procesar lotes de comprobantes."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import Literal, TypedDict

from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import settings
from app.core.database import WorkerSessionLocal, acquire_database_connection
from app.models.lote_comprobante import LoteComprobante
from app.services.lote_comprobantes_service import LoteComprobantesService

logger = logging.getLogger(__name__)


class LoteWorkerRuntimeStatus(TypedDict):
    """Contrato interno seguro del estado runtime del worker."""

    estado: Literal["deshabilitado", "detenido", "esperando", "ocupado"]
    habilitado: bool
    ejecutando: bool
    ocupado: bool
    ciclo_iniciado_at: datetime | None
    ciclo_finalizado_at: datetime | None
    ultima_duracion_ms: float | None
    ultimo_resultado: Literal["exitoso", "error"] | None
    ultimo_exito_at: datetime | None
    ultimo_error_at: datetime | None
    stale_detectados_ultimo_ciclo: int
    lotes_en_cola_ultimo_ciclo: int
    lotes_procesados_ultimo_ciclo: int


@dataclass(frozen=True)
class ResultadoCicloLoteWorker:
    """Resume conteos no sensibles del último ciclo del worker."""

    stale_detectados: int = 0
    lotes_en_cola_detectados: int = 0
    lotes_procesados: int = 0
    tuvo_error: bool = False


@dataclass
class _EstadoRuntimeLoteWorker:
    """Mantiene métricas efímeras sin escribir entidades fiscales."""

    ocupado: bool = False
    ciclo_iniciado_at: datetime | None = None
    ciclo_finalizado_at: datetime | None = None
    ultima_duracion_ms: float | None = None
    ultimo_resultado: Literal["exitoso", "error"] | None = None
    ultimo_exito_at: datetime | None = None
    ultimo_error_at: datetime | None = None
    stale_detectados_ultimo_ciclo: int = 0
    lotes_en_cola_ultimo_ciclo: int = 0
    lotes_procesados_ultimo_ciclo: int = 0
    inicio_monotonic: float | None = None


class LoteWorker:
    """Procesa lotes en cola y bloquea lotes interrumpidos."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._runtime = _EstadoRuntimeLoteWorker()

    async def run(self) -> None:
        """Ejecuta el loop del worker hasta recibir señal de cierre."""
        logger.info("Worker de lotes iniciado")
        while not self._stop_event.is_set():
            try:
                await self.procesar_pendientes()
            except Exception as exc:
                logger.error(
                    "Falló el ciclo del worker de lotes tipo_error=%s",
                    type(exc).__name__,
                )

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=settings.batch_worker_poll_seconds,
                )
            except asyncio.TimeoutError:
                continue

        logger.info("Worker de lotes detenido")

    def stop(self) -> None:
        """Solicita la detención del worker."""
        self._stop_event.set()

    async def procesar_pendientes(self) -> ResultadoCicloLoteWorker:
        """Procesa un ciclo secuencial e instrumenta solo memoria del proceso."""
        self._iniciar_ciclo()
        try:
            resultado = await self._procesar_pendientes()
        except asyncio.CancelledError:
            self._finalizar_ciclo(ResultadoCicloLoteWorker(tuvo_error=True))
            raise
        except Exception:
            self._finalizar_ciclo(ResultadoCicloLoteWorker(tuvo_error=True))
            raise

        self._finalizar_ciclo(resultado)
        return resultado

    async def _procesar_pendientes(self) -> ResultadoCicloLoteWorker:
        """Ejecuta el orden fiscal stale primero y luego cola, sin paralelismo."""
        stale_before = datetime.utcnow() - timedelta(
            minutes=settings.batch_processing_stale_minutes
        )
        async with WorkerSessionLocal() as db:
            await acquire_database_connection(db, "worker")
            result_stale = await db.execute(
                select(LoteComprobante.id, LoteComprobante.empresa_id)
                .where(
                    LoteComprobante.estado == "procesando",
                    LoteComprobante.updated_at < stale_before,
                )
                .order_by(LoteComprobante.updated_at)
                .limit(settings.batch_worker_batch_size)
            )
            stale_lotes = result_stale.all()

        stale_detectados = len(stale_lotes)
        for lote_id, empresa_id in stale_lotes:
            async with WorkerSessionLocal() as db:
                await acquire_database_connection(db, "worker")
                service = LoteComprobantesService(db)
                try:
                    logger.warning(
                        "Worker bloqueando lote stale lote_id=%s para reconciliación",
                        lote_id,
                    )
                    await service.bloquear_lote_procesando_stale(lote_id, empresa_id)
                except Exception as exc:
                    logger.error(
                        "No se pudo bloquear lote stale lote_id=%s tipo_error=%s",
                        lote_id,
                        type(exc).__name__,
                    )
                    logger.warning(
                        "Worker pospone la cola hasta resolver el bloqueo stale"
                    )
                    return ResultadoCicloLoteWorker(
                        stale_detectados=stale_detectados,
                        tuvo_error=True,
                    )

        if stale_lotes:
            async with WorkerSessionLocal() as db:
                await acquire_database_connection(db, "worker")
                stale_restante = (
                    await db.execute(
                        select(LoteComprobante.id)
                        .where(
                            LoteComprobante.estado == "procesando",
                            LoteComprobante.updated_at < stale_before,
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()
            if stale_restante is not None:
                logger.warning(
                    "Worker pospone la cola hasta bloquear todos los lotes stale"
                )
                return ResultadoCicloLoteWorker(
                    stale_detectados=stale_detectados,
                )

        async with WorkerSessionLocal() as db:
            await acquire_database_connection(db, "worker")
            result = await db.execute(
                select(LoteComprobante.id, LoteComprobante.empresa_id)
                .where(LoteComprobante.estado == "en_cola")
                .order_by(LoteComprobante.created_at)
                .limit(settings.batch_worker_batch_size)
            )
            pendientes = result.all()

        lotes_procesados = 0
        tuvo_error = False
        for lote_id, empresa_id in pendientes:
            async with WorkerSessionLocal() as db:
                await acquire_database_connection(db, "worker")
                service = LoteComprobantesService(db)
                try:
                    logger.info("Worker procesando lote_id=%s", lote_id)
                    await service.procesar_lote(lote_id, empresa_id, reanudar=True)
                    lotes_procesados += 1
                except Exception as exc:
                    tuvo_error = True
                    logger.error(
                        "No se pudo procesar lote_id=%s tipo_error=%s",
                        lote_id,
                        type(exc).__name__,
                    )

        return ResultadoCicloLoteWorker(
            stale_detectados=stale_detectados,
            lotes_en_cola_detectados=len(pendientes),
            lotes_procesados=lotes_procesados,
            tuvo_error=tuvo_error,
        )

    def _iniciar_ciclo(self) -> None:
        """Inicia medición efímera sin tocar la base."""
        self._runtime.ocupado = True
        self._runtime.ciclo_iniciado_at = datetime.utcnow()
        self._runtime.inicio_monotonic = perf_counter()

    def _finalizar_ciclo(self, resultado: ResultadoCicloLoteWorker) -> None:
        """Cierra la medición sin conservar mensajes de excepción."""
        finalizado_at = datetime.utcnow()
        inicio_monotonic = self._runtime.inicio_monotonic
        self._runtime.ocupado = False
        self._runtime.ciclo_finalizado_at = finalizado_at
        self._runtime.ultima_duracion_ms = (
            round((perf_counter() - inicio_monotonic) * 1000, 3)
            if inicio_monotonic is not None
            else None
        )
        self._runtime.ultimo_resultado = "error" if resultado.tuvo_error else "exitoso"
        if resultado.tuvo_error:
            self._runtime.ultimo_error_at = finalizado_at
        else:
            self._runtime.ultimo_exito_at = finalizado_at
        self._runtime.stale_detectados_ultimo_ciclo = resultado.stale_detectados
        self._runtime.lotes_en_cola_ultimo_ciclo = resultado.lotes_en_cola_detectados
        self._runtime.lotes_procesados_ultimo_ciclo = resultado.lotes_procesados
        self._runtime.inicio_monotonic = None

    def obtener_estado_runtime(
        self,
        *,
        habilitado: bool,
        ejecutando: bool,
    ) -> LoteWorkerRuntimeStatus:
        """Devuelve una copia allowlist del estado runtime del worker."""
        if not habilitado:
            estado: Literal[
                "deshabilitado", "detenido", "esperando", "ocupado"
            ] = "deshabilitado"
        elif not ejecutando:
            estado = "detenido"
        elif self._runtime.ocupado:
            estado = "ocupado"
        else:
            estado = "esperando"

        return {
            "estado": estado,
            "habilitado": habilitado,
            "ejecutando": ejecutando,
            "ocupado": self._runtime.ocupado,
            "ciclo_iniciado_at": self._runtime.ciclo_iniciado_at,
            "ciclo_finalizado_at": self._runtime.ciclo_finalizado_at,
            "ultima_duracion_ms": self._runtime.ultima_duracion_ms,
            "ultimo_resultado": self._runtime.ultimo_resultado,
            "ultimo_exito_at": self._runtime.ultimo_exito_at,
            "ultimo_error_at": self._runtime.ultimo_error_at,
            "stale_detectados_ultimo_ciclo": (
                self._runtime.stale_detectados_ultimo_ciclo
            ),
            "lotes_en_cola_ultimo_ciclo": (self._runtime.lotes_en_cola_ultimo_ciclo),
            "lotes_procesados_ultimo_ciclo": (
                self._runtime.lotes_procesados_ultimo_ciclo
            ),
        }


def _estado_runtime_vacio(
    *,
    habilitado: bool,
    ejecutando: bool,
) -> LoteWorkerRuntimeStatus:
    """Construye el estado seguro cuando aún no existe una instancia."""
    estado: Literal["deshabilitado", "detenido", "esperando", "ocupado"]
    estado = "detenido" if habilitado else "deshabilitado"
    return {
        "estado": estado,
        "habilitado": habilitado,
        "ejecutando": ejecutando,
        "ocupado": False,
        "ciclo_iniciado_at": None,
        "ciclo_finalizado_at": None,
        "ultima_duracion_ms": None,
        "ultimo_resultado": None,
        "ultimo_exito_at": None,
        "ultimo_error_at": None,
        "stale_detectados_ultimo_ciclo": 0,
        "lotes_en_cola_ultimo_ciclo": 0,
        "lotes_procesados_ultimo_ciclo": 0,
    }


def get_lote_worker_status(app: FastAPI) -> LoteWorkerRuntimeStatus:
    """Expone solo métricas runtime allowlist, sin datos fiscales ni errores."""
    habilitado = bool(settings.batch_worker_enabled)
    worker = getattr(app.state, "lote_worker", None)
    task = getattr(app.state, "lote_worker_task", None)
    ejecutando = task is not None and not task.done()
    if not isinstance(worker, LoteWorker):
        return _estado_runtime_vacio(
            habilitado=habilitado,
            ejecutando=ejecutando,
        )
    return worker.obtener_estado_runtime(
        habilitado=habilitado,
        ejecutando=ejecutando,
    )


def ensure_lote_worker_running(app: FastAPI) -> bool:
    """Inicia el worker si corresponde e informa si quedó disponible."""
    if not settings.batch_worker_enabled:
        return False

    task = getattr(app.state, "lote_worker_task", None)
    if task is not None and not task.done():
        return True

    worker = LoteWorker()
    app.state.lote_worker = worker
    app.state.lote_worker_task = asyncio.create_task(worker.run())
    return True


async def stop_lote_worker(app: FastAPI) -> None:
    """Detiene el worker de lotes en el cierre de la app."""
    worker = getattr(app.state, "lote_worker", None)
    task = getattr(app.state, "lote_worker_task", None)

    if worker is None or task is None:
        return

    worker.stop()
    try:
        await asyncio.wait_for(task, timeout=10)
    except asyncio.TimeoutError:
        task.cancel()
