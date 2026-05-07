"""Worker persistente para procesar lotes de comprobantes."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.lote_comprobante import LoteComprobante
from app.services.lote_comprobantes_service import LoteComprobantesService

logger = logging.getLogger(__name__)


class LoteWorker:
    """Procesa lotes en cola y reanuda lotes interrumpidos."""

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
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(LoteComprobante.id, LoteComprobante.empresa_id)
                .where(LoteComprobante.estado.in_(("en_cola", "procesando")))
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
