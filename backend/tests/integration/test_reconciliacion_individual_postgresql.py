"""Dos conexiones recuperan la misma nota tras perder el proceso emisor."""

import asyncio
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.comprobante import Comprobante
from app.models.elegibilidad_rece import PuntoVentaGuardaEmisionRece
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.models.usuario import Usuario
from app.services.lecturas_historicas_service import proyectar_original
from app.services.reconciliacion_individual_service import (
    ReconciliacionIndividualService,
)
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url
from tests.test_reconciliacion_individual import (
    CAE_PRUEBA,
    autorizar_y_perder_respuesta,
)


@pytest.mark.integration
async def test_dos_sesiones_recuperan_un_unico_comprobante_post_cae(monkeypatch):
    url = require_disposable_postgres_url(purpose="recuperación individual concurrente")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    respondidas = asyncio.Event()
    tareas = []
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
                email="emisor@example.test",
                telefono="0000000000",
                inicio_actividades=date(2020, 1, 1),
            )
            operador = Usuario(
                email="operador@example.test",
                nombre="Operador sintético",
                hashed_password="sintetico",
                es_admin=True,
            )
            db.add_all((empresa, operador))
            await db.commit()
            empresa_id, usuario_id = empresa.id, operador.id
            operacion_id, clave, arca = await autorizar_y_perder_respuesta(
                db, empresa, monkeypatch
            )

        original = arca.fe_comp_consultar

        async def consulta_concurrente(**params):
            respuesta = await original(**params)
            if arca.consultas == 2:
                respondidas.set()
            await respondidas.wait()
            return respuesta

        monkeypatch.setattr(arca, "fe_comp_consultar", consulta_concurrente)

        async def verificar(*, por_clave):
            async with factory() as db:
                return await ReconciliacionIndividualService(db).verificar(
                    empresa_id=empresa_id,
                    usuario_id=usuario_id,
                    operacion_id=None if por_clave else operacion_id,
                    clave=clave if por_clave else None,
                )

        tareas = [
            asyncio.create_task(verificar(por_clave=por_clave))
            for por_clave in (True, False)
        ]
        primera, segunda = await asyncio.wait_for(asyncio.gather(*tareas), timeout=15)
        assert primera is not None and primera.exito
        assert primera == segunda
        assert primera.cae == CAE_PRUEBA
        assert len(arca.emitidos) == 1
        assert arca.consultas == 2
        async with factory() as db:
            assert await db.scalar(select(func.count(Comprobante.id))) == 1
            intento = await db.scalar(select(IntentoEmisionFiscal))
            guarda = await db.get(PuntoVentaGuardaEmisionRece, intento.guarda_rece_id)
            assert guarda.fase == "cerrada_terminal"
            comprobante = await db.get(Comprobante, primera.comprobante_id)
            assert (
                proyectar_original(comprobante, intento)
                .comprobantes_asociados[0]
                .numero
                == 17
            )
    finally:
        respondidas.set()
        for tarea in tareas:
            if not tarea.done():
                tarea.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)
        await engine.dispose()
