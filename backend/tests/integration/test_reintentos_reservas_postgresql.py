"""La recuperación y una nueva reserva comparten coordinación en PostgreSQL."""

import asyncio

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.idempotencia_fiscal import OperacionIdempotente
from app.models.lote_comprobante import LoteComprobanteGrupo
from app.services.duplicados_lotes_service import DuplicadosLotesService
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url
from tests.test_duplicados_lotes_v2 import _crear_escenario_coordinacion


@pytest.mark.integration
@pytest.mark.asyncio
async def test_recuperacion_terminal_y_nuevo_owner_son_atomicos():
    url = require_disposable_postgres_url(purpose="recuperación de reservas terminales")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        empresa_id, lote_id, grupo_id, owners = await _crear_escenario_coordinacion(
            factory
        )
        async with factory() as db:
            await db.execute(
                update(OperacionIdempotente)
                .where(OperacionIdempotente.id == owners[0])
                .values(
                    estado="finalizado",
                    response_json={
                        "lote": {
                            "id": lote_id,
                            "empresa_id": empresa_id,
                            "estado": "fallido",
                        },
                        "en_progreso": False,
                    },
                )
            )
            await db.execute(
                update(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.id == grupo_id)
                .values(estado="fallido", duplicados_reserva_operacion_id=owners[0])
            )
            await db.commit()
        liberada = asyncio.Event()
        confirmar = asyncio.Event()
        esperando = asyncio.Event()

        async def recuperar():
            async with factory() as db:
                service = DuplicadosLotesService(db)
                await service.adquirir_coordinacion(
                    empresa_id=empresa_id, ambiente="homologacion"
                )
                await service.recuperar_reservas_terminales(
                    empresa_id=empresa_id, ambiente="homologacion"
                )
                liberada.set()
                await confirmar.wait()
                await db.commit()

        async def reservar():
            await liberada.wait()
            async with factory() as db:
                esperando.set()
                service = DuplicadosLotesService(db)
                await service.adquirir_coordinacion(
                    empresa_id=empresa_id, ambiente="homologacion"
                )
                await service.recuperar_reservas_terminales(
                    empresa_id=empresa_id, ambiente="homologacion"
                )
                result = await db.execute(
                    update(LoteComprobanteGrupo)
                    .where(
                        LoteComprobanteGrupo.id == grupo_id,
                        LoteComprobanteGrupo.duplicados_reserva_operacion_id.is_(None),
                    )
                    .values(duplicados_reserva_operacion_id=owners[1])
                )
                assert result.rowcount == 1
                await db.commit()

        primera = asyncio.create_task(recuperar())
        segunda = asyncio.create_task(reservar())
        try:
            await asyncio.wait_for(esperando.wait(), 5)
            await asyncio.sleep(0.05)
            assert not segunda.done()
            confirmar.set()
            await asyncio.wait_for(asyncio.gather(primera, segunda), 5)
        finally:
            confirmar.set()
            for task in (primera, segunda):
                if not task.done():
                    task.cancel()
            await asyncio.gather(primera, segunda, return_exceptions=True)
        async with factory() as db:
            service = DuplicadosLotesService(db)
            await service.adquirir_coordinacion(
                empresa_id=empresa_id, ambiente="homologacion"
            )
            await service.recuperar_reservas_terminales(
                empresa_id=empresa_id, ambiente="homologacion"
            )
            assert (
                await db.scalar(
                    select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                        LoteComprobanteGrupo.id == grupo_id
                    )
                )
                == owners[1]
            )
            await db.rollback()
    finally:
        await engine.dispose()
