"""Locks de recuperación legacy con dos sesiones PostgreSQL desechables."""

import asyncio
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.comprobante import Comprobante
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.services.facturacion_service import FacturacionService
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url
from tests.test_reconciliacion_legacy import crear_escenario_legacy


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_tardio", [False, True])
async def test_legacy_consultas_concurrentes_conservan_un_unico_resultado(
    terminal_tardio,
):
    url = require_disposable_postgres_url(purpose="locks de reconciliación legacy")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    tareas = []
    consultas_listas = asyncio.Event()
    responder = asyncio.Event()
    cantidad = 0
    try:
        async with factory() as db:
            empresa = Empresa(
                razon_social="Emisor sintético",
                cuit="20123456789",
                condicion_iva="RI",
                domicilio="Sintético",
                localidad="Sintética",
                provincia="Buenos Aires",
                codigo_postal="1000",
                email="sintetico@example.test",
                telefono="0000000000",
                inicio_actividades=date(2020, 1, 1),
            )
            db.add(empresa)
            await db.commit()
            escenario = await crear_escenario_legacy(db, empresa)
            intento_id = escenario.intento.id
            consulta = escenario.consulta

        class WSFE:
            async def fe_comp_consultar(self, **kwargs):
                nonlocal cantidad
                cantidad += 1
                if cantidad == (1 if terminal_tardio else 2):
                    consultas_listas.set()
                await responder.wait()
                return consulta

            async def fe_cae_solicitar(self, *args, **kwargs):
                raise AssertionError("La reconciliación no solicita CAE")

        async def recuperar():
            async with factory() as db:
                intento = await db.get(IntentoEmisionFiscal, intento_id)
                await FacturacionService(db)._reconciliar_intento_stale(
                    intento=intento, wsfe_client=WSFE(), punto_venta_numero=1
                )

        tareas = [
            asyncio.create_task(recuperar()) for _ in range(1 if terminal_tardio else 2)
        ]
        await asyncio.wait_for(consultas_listas.wait(), 10)
        if terminal_tardio:
            async with factory() as db:
                intento = await db.get(IntentoEmisionFiscal, intento_id)
                intento.estado = "requiere_reconciliacion"
                intento.cae = "11111111111111"
                intento.mensaje = "Resolución concurrente sintética."
                await db.commit()
        responder.set()
        await asyncio.wait_for(asyncio.gather(*tareas), 10)
        async with factory() as db:
            intento = await db.get(IntentoEmisionFiscal, intento_id)
            cantidad_local = await db.scalar(
                select(func.count()).select_from(Comprobante)
            )
            if terminal_tardio:
                assert cantidad_local == 0
                assert intento.estado == "requiere_reconciliacion"
                assert intento.cae == "11111111111111"
                assert intento.mensaje == "Resolución concurrente sintética."
            else:
                assert cantidad_local == 1
                assert intento.estado == "autorizado"
                assert intento.cae == "00000000000000"
                assert intento.comprobante_id is not None
    finally:
        responder.set()
        for tarea in tareas:
            if not tarea.done():
                tarea.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)
        await engine.dispose()
