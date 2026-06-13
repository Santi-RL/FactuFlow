"""Worker persistente para procesar lotes de comprobantes."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.lote_comprobante import LoteComprobante
from app.services.lote_comprobantes_service import LoteComprobantesService

logger = logging.getLogger(__name__)


class LoteWorker:
    """Procesa lotes en cola y bloquea lotes interrumpidos."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        """Ejecuta el loop del worker hasta recibir señal de cierre."""
        logger.info("Worker de lotes iniciado")
        while not self._stop_event.is_set():
            try:
                await self.procesar_pendientes()
            except Exception:
                logger.exception("Falló el ciclo del worker de lotes")

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

    async def procesar_pendientes(self) -> None:
        """Procesa lotes pendientes en orden de carga."""
        stale_before = datetime.utcnow() - timedelta(
            minutes=settings.batch_processing_stale_minutes
        )
        async with AsyncSessionLocal() as db:
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

        for lote_id, empresa_id in stale_lotes:
            async with AsyncSessionLocal() as db:
                service = LoteComprobantesService(db)
                try:
                    logger.warning(
                        "Worker bloqueando lote stale %s para reconciliación",
                        lote_id,
                    )
                    await service.bloquear_lote_procesando_stale(lote_id, empresa_id)
                except Exception:
                    logger.exception(
                        "No se pudo bloquear lote stale %s para reconciliación",
                        lote_id,
                    )
                    logger.warning(
                        "Worker pospone lotes en cola hasta resolver el bloqueo stale"
                    )
                    return

        if stale_lotes:
            async with AsyncSessionLocal() as db:
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
                    "Worker pospone lotes en cola hasta bloquear todos los lotes stale"
                )
                return

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(LoteComprobante.id, LoteComprobante.empresa_id)
                .where(LoteComprobante.estado == "en_cola")
                .order_by(LoteComprobante.created_at)
                .limit(settings.batch_worker_batch_size)
            )
            pendientes = result.all()

        for lote_id, empresa_id in pendientes:
            async with AsyncSessionLocal() as db:
                service = LoteComprobantesService(db)
                try:
                    logger.info("Worker procesando lote %s", lote_id)
                    await service.procesar_lote(lote_id, empresa_id, reanudar=True)
                except Exception:
                    logger.exception("No se pudo procesar lote %s", lote_id)


def ensure_lote_worker_running(app: FastAPI) -> None:
    """Inicia el worker si no existe o si terminó."""
    if not settings.batch_worker_enabled:
        return

    task = getattr(app.state, "lote_worker_task", None)
    if task is not None and not task.done():
        return

    worker = LoteWorker()
    app.state.lote_worker = worker
    app.state.lote_worker_task = asyncio.create_task(worker.run())


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
