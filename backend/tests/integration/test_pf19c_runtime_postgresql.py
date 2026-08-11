"""Integración PostgreSQL acotada para atomicidad y CAS runtime de PF-19C."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import null, select, text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceRevision,
    PuntoVentaGuardaEmisionRece,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta
from app.schemas.lote_comprobante import (
    LoteComprobanteResponse,
    LoteProcesamientoResponse,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.lote_comprobantes_service import LoteComprobantesService
from app.services.lote_comprobantes_service import LoteComprobanteConflictoError
from tests.integration.test_integridad_fiscal_postgresql import (
    REVISION_INTEGRIDAD_FISCAL,
    _crear_contexto_sintetico,
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url


ERROR_ARCA_10005 = {
    "codigo": 10005,
    "alcance": "global",
    "mensaje": "El punto de venta no está dado de alta como RECE en ARCA.",
}
TIMEOUT_PRUEBA_SEGUNDOS = 20


async def _preparar_pf19c(database_url: str) -> AsyncEngine:
    """Aplica el historial real sobre un emisor legacy sintético."""
    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_INTEGRIDAD_FISCAL, database_url)
    engine_legacy = create_async_engine(database_url)
    try:
        await _crear_contexto_sintetico(engine_legacy)
    finally:
        await engine_legacy.dispose()
    _run_alembic("upgrade", "head", database_url)
    return create_async_engine(database_url, pool_size=8, max_overflow=0)


async def _configurar_timeouts(session: AsyncSession) -> None:
    """Acota esperas de locks y statements en cada transacción del test."""
    await session.execute(text("SET LOCAL lock_timeout = '5s'"))
    await session.execute(text("SET LOCAL statement_timeout = '10s'"))


def _material_rece(grupos: list[LoteComprobanteGrupo]) -> dict[str, object]:
    """Construye el material exacto que valida el runtime productivo."""
    items = [
        {
            "grupo_id": int(grupo.id),
            "empresa_id": int(grupo.empresa_id),
            "punto_venta_id": int(grupo.punto_venta_id),
            "punto_venta_numero": int(grupo.punto_venta_numero),
            "ambiente": str(grupo.ambiente),
            "elegibilidad_revision_id": int(grupo.punto_venta_elegibilidad_revision_id),
            "punto_venta_revision_fiscal": int(grupo.punto_venta_revision_fiscal),
            "tipo_comprobante": int(grupo.tipo_comprobante),
            "payload_hash": hashlib.sha256(
                json.dumps(
                    grupo.payload_json or {},
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
            ).hexdigest(),
        }
        for grupo in grupos
    ]
    return {
        "grupo_ids": [item["grupo_id"] for item in items],
        "grupos_hash": hashlib.sha256(
            json.dumps(
                items,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "grupos": items,
    }


def _nuevo_lote(*, sufijo: str, background: bool) -> LoteComprobante:
    """Crea un lote sintético con campos públicos completos."""
    return LoteComprobante(
        nombre_archivo=f"pf19c-{sufijo}.xlsx",
        archivo_hash=hashlib.sha256(sufijo.encode("utf-8")).hexdigest(),
        estado="en_cola" if background else "procesando",
        modo_procesamiento="background" if background else "sincronico",
        procesamiento_async=background,
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        grupos_con_error=0,
        grupos_emitidos=0,
        grupos_fallidos=0,
        grupos_reconciliados_externos=0,
        grupos_descartados=0,
        empresa_id=1,
    )


def _nuevo_grupo(
    lote: LoteComprobante,
    *,
    orden: int,
    revision_id: int,
) -> LoteComprobanteGrupo:
    """Crea un grupo fiscal con snapshot RECE y payload inmutables."""
    return LoteComprobanteGrupo(
        comprobante_ref=f"PF19C-{lote.nombre_archivo}-{orden}",
        orden=orden,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=41,
        total_estimado=Decimal("121.00"),
        payload_json={"fecha_emision": "2026-08-09", "orden": orden},
        mensajes_json=[],
        lote_id=lote.id,
        empresa_id=1,
        punto_venta_id=1,
        ambiente="produccion",
        punto_venta_elegibilidad_revision_id=revision_id,
        punto_venta_revision_fiscal=1,
    )


async def _sembrar_grafos(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """Persiste grafos independientes para rollback, sync y worker."""
    async with session_factory() as session:
        await _configurar_timeouts(session)
        revision_id = await session.scalar(
            select(PuntoVentaElegibilidadReceRevision.id).where(
                PuntoVentaElegibilidadReceRevision.empresa_id == 1,
                PuntoVentaElegibilidadReceRevision.punto_venta_id == 1,
                PuntoVentaElegibilidadReceRevision.ambiente == "produccion",
            )
        )
        punto = await session.get(PuntoVenta, 1)
        assert revision_id is not None
        assert punto is not None
        punto.revision_fiscal = 1

        lote_rollback = _nuevo_lote(sufijo="rollback", background=False)
        lote_rollback.total_filas = 2
        lote_rollback.total_grupos = 2
        lote_rollback.grupos_validos = 2
        lote_sync = _nuevo_lote(sufijo="sync", background=False)
        lote_worker = _nuevo_lote(sufijo="worker", background=True)
        session.add_all([lote_rollback, lote_sync, lote_worker])
        await session.flush()

        grupos_rollback = [
            _nuevo_grupo(lote_rollback, orden=orden, revision_id=int(revision_id))
            for orden in (1, 2)
        ]
        grupo_sync = _nuevo_grupo(
            lote_sync,
            orden=1,
            revision_id=int(revision_id),
        )
        grupo_worker = _nuevo_grupo(
            lote_worker,
            orden=1,
            revision_id=int(revision_id),
        )
        session.add_all([*grupos_rollback, grupo_sync, grupo_worker])
        await session.flush()

        operacion_rollback = OperacionIdempotente(
            idempotency_key="pf19c-pg-rollback",
            tipo_operacion="procesar_lote",
            payload_hash="1" * 64,
            estado="en_proceso",
            response_json=null(),
            rece_snapshot_hash="2" * 64,
            lote_id=lote_rollback.id,
            empresa_id=1,
        )
        operacion_sync = OperacionIdempotente(
            idempotency_key="pf19c-pg-sync",
            tipo_operacion="procesar_lote",
            payload_hash="3" * 64,
            estado="en_proceso",
            response_json=null(),
            rece_snapshot_hash="4" * 64,
            lote_id=lote_sync.id,
            empresa_id=1,
        )
        operacion_worker = OperacionIdempotente(
            idempotency_key="pf19c-pg-worker",
            tipo_operacion="procesar_lote",
            payload_hash="5" * 64,
            estado="en_proceso",
            response_json=null(),
            rece_snapshot_hash="6" * 64,
            lote_id=lote_worker.id,
            empresa_id=1,
        )
        session.add_all([operacion_rollback, operacion_sync, operacion_worker])
        await session.flush()
        operaciones_sin_respuesta = set(
            (
                await session.scalars(
                    select(OperacionIdempotente.id).where(
                        OperacionIdempotente.id.in_(
                            {
                                operacion_rollback.id,
                                operacion_sync.id,
                                operacion_worker.id,
                            }
                        ),
                        OperacionIdempotente.response_json.is_(None),
                    )
                )
            ).all()
        )
        assert operaciones_sin_respuesta == {
            operacion_rollback.id,
            operacion_sync.id,
            operacion_worker.id,
        }

        for lote, operacion, grupos in (
            (lote_rollback, operacion_rollback, grupos_rollback),
            (lote_sync, operacion_sync, [grupo_sync]),
            (lote_worker, operacion_worker, [grupo_worker]),
        ):
            lote.metadata_json = {
                "operacion_idempotente_id": int(operacion.id),
                "pf19b_rece_material": _material_rece(grupos),
            }

        snapshot = OperacionIdempotenteElegibilidadRece(
            operacion_id=operacion_rollback.id,
            empresa_id=1,
            punto_venta_id=1,
            ambiente="produccion",
            elegibilidad_revision_id=revision_id,
            punto_venta_revision_fiscal=1,
        )
        session.add(snapshot)
        await session.flush()
        guarda = PuntoVentaGuardaEmisionRece(
            token="a" * 64,
            fase="arca_iniciada",
            operacion_id=operacion_rollback.id,
            empresa_id=1,
            punto_venta_id=1,
            ambiente="produccion",
            elegibilidad_revision_id=revision_id,
            punto_venta_revision_fiscal=1,
            arca_iniciada_en=datetime.utcnow(),
        )
        session.add(guarda)
        await session.flush()
        intento = IntentoEmisionFiscal(
            tipo_comprobante=6,
            punto_venta_numero=41,
            numero_planificado=1,
            fecha_emision=date(2026, 8, 9),
            total=Decimal("121.00"),
            payload_hash="7" * 64,
            huella_logica="8" * 64,
            estado="en_proceso",
            ambiente="produccion",
            punto_venta_elegibilidad_revision_id=revision_id,
            punto_venta_revision_fiscal=1,
            guarda_rece_id=guarda.id,
            operacion_id=operacion_rollback.id,
            empresa_id=1,
            punto_venta_id=1,
            lote_id=lote_rollback.id,
            grupo_id=grupos_rollback[0].id,
        )
        session.add(intento)
        await session.flush()

        progreso_worker = LoteProcesamientoResponse(
            lote=LoteComprobanteResponse.model_validate(lote_worker),
            mensaje="El lote quedó en cola.",
            en_progreso=True,
        ).model_dump(mode="json")
        operacion_worker.response_json = progreso_worker
        lote_worker.estado = "con_errores"
        lote_worker.mensaje_resumen = "ARCA rechazó el requerimiento completo."
        metadata_worker = dict(lote_worker.metadata_json)
        metadata_worker["pf19c_rechazo_global"] = {
            "operacion_id": int(operacion_worker.id),
            "categoria": "arca_rechazo_global_excluyente",
            "grupos_rechazo_ids": [int(grupo_worker.id)],
            "grupos_no_enviados_ids": [],
            "errores_arca": [ERROR_ARCA_10005],
        }
        lote_worker.metadata_json = metadata_worker
        grupo_worker.estado = "fallido"

        lote_sync.estado = "con_errores"
        lote_sync.mensaje_resumen = "ARCA rechazó el requerimiento completo."
        metadata_sync = dict(lote_sync.metadata_json)
        metadata_sync["pf19c_rechazo_global"] = {
            "operacion_id": int(operacion_sync.id),
            "categoria": "arca_rechazo_global_excluyente",
            "grupos_rechazo_ids": [int(grupo_sync.id)],
            "grupos_no_enviados_ids": [],
            "errores_arca": [ERROR_ARCA_10005],
        }
        lote_sync.metadata_json = metadata_sync
        grupo_sync.estado = "fallido"

        await session.commit()
        return {
            "lote_rollback": int(lote_rollback.id),
            "grupo_enviado": int(grupos_rollback[0].id),
            "grupo_remanente": int(grupos_rollback[1].id),
            "operacion_rollback": int(operacion_rollback.id),
            "guarda_rollback": int(guarda.id),
            "intento_rollback": int(intento.id),
            "lote_sync": int(lote_sync.id),
            "operacion_sync": int(operacion_sync.id),
            "lote_worker": int(lote_worker.id),
            "operacion_worker": int(operacion_worker.id),
        }


async def _leer_baseline_rollback(
    session_factory: async_sessionmaker[AsyncSession],
    ids: dict[str, int],
) -> tuple[str, str, str, list[str], bool]:
    """Lee el grafo desde una transacción observadora independiente."""
    async with session_factory() as session:
        await _configurar_timeouts(session)
        operacion = await session.get(
            OperacionIdempotente,
            ids["operacion_rollback"],
        )
        intento = await session.get(IntentoEmisionFiscal, ids["intento_rollback"])
        guarda = await session.get(
            PuntoVentaGuardaEmisionRece,
            ids["guarda_rollback"],
        )
        grupos = list(
            (
                await session.scalars(
                    select(LoteComprobanteGrupo)
                    .where(LoteComprobanteGrupo.lote_id == ids["lote_rollback"])
                    .order_by(LoteComprobanteGrupo.orden)
                )
            ).all()
        )
        lote = await session.get(LoteComprobante, ids["lote_rollback"])
        assert operacion is not None
        assert intento is not None
        assert guarda is not None
        assert lote is not None
        return (
            str(operacion.estado),
            str(intento.estado),
            str(guarda.fase),
            [str(grupo.estado) for grupo in grupos],
            "pf19c_rechazo_global" in (lote.metadata_json or {}),
        )


async def _probar_rollback_conjunto(
    session_factory: async_sessionmaker[AsyncSession],
    ids: dict[str, int],
) -> None:
    """Verifica que el cierre diferido no publique un grafo parcial."""
    async with session_factory() as writer:
        await _configurar_timeouts(writer)
        intento = await writer.get(IntentoEmisionFiscal, ids["intento_rollback"])
        guarda = await writer.get(
            PuntoVentaGuardaEmisionRece,
            ids["guarda_rollback"],
        )
        grupo_enviado = await writer.get(
            LoteComprobanteGrupo,
            ids["grupo_enviado"],
        )
        assert intento is not None
        assert guarda is not None
        assert grupo_enviado is not None
        ahora = datetime.utcnow()
        intento.estado = "rechazado_arca"
        intento.categoria_error = "arca_rechazo_global_excluyente"
        intento.mensaje = "ARCA rechazó el requerimiento completo."
        intento.errores_arca_json = [ERROR_ARCA_10005]
        guarda.fase = "cerrada_terminal"
        guarda.cerrada_en = ahora
        grupo_enviado.estado = "fallido"
        await writer.flush()

        lote_terminal = await LoteComprobantesService(
            writer
        )._cerrar_lote_por_rechazo_global(
            lote_id=ids["lote_rollback"],
            empresa_id=1,
            operacion_id=ids["operacion_rollback"],
            grupos_seleccionados_ids={
                ids["grupo_enviado"],
                ids["grupo_remanente"],
            },
            grupos_procesados_ids={ids["grupo_enviado"]},
            grupos_rechazo_ids={ids["grupo_enviado"]},
        )
        assert LoteComprobantesService.errores_arca_publicables_desde_metadata(
            lote_terminal.metadata_json,
            operacion_id=ids["operacion_rollback"],
        )

        baseline = await asyncio.wait_for(
            _leer_baseline_rollback(session_factory, ids),
            timeout=TIMEOUT_PRUEBA_SEGUNDOS,
        )
        assert baseline == (
            "en_proceso",
            "en_proceso",
            "arca_iniciada",
            ["validado", "validado"],
            False,
        )
        await writer.rollback()

    posterior = await asyncio.wait_for(
        _leer_baseline_rollback(session_factory, ids),
        timeout=TIMEOUT_PRUEBA_SEGUNDOS,
    )
    assert posterior == baseline


async def _respuesta_terminal_lote(
    session: AsyncSession,
    lote_id: int,
    operacion_id: int,
) -> LoteProcesamientoResponse:
    """Serializa el resultado terminal canónico de un lote sembrado."""
    lote = await session.get(LoteComprobante, lote_id)
    assert lote is not None
    return LoteProcesamientoResponse(
        lote=LoteComprobanteResponse.model_validate(lote),
        mensaje=lote.mensaje_resumen or "Lote procesado",
        en_progreso=False,
        errores_arca=(
            LoteComprobantesService.errores_arca_publicables_desde_metadata(
                lote.metadata_json,
                operacion_id=operacion_id,
            )
        ),
    )


async def _competir_publicacion_sync(
    session_factory: async_sessionmaker[AsyncSession],
    ids: dict[str, int],
) -> None:
    """Hace competir dos cierres sync y exige un único ganador con replay."""
    llamadas_fecae = 0

    async def solicitar_fecae_simulada(
        session: AsyncSession,
    ) -> LoteProcesamientoResponse:
        """Representa la única respuesta FECAE ya obtenida, sin abrir red."""
        nonlocal llamadas_fecae
        llamadas_fecae += 1
        return await _respuesta_terminal_lote(
            session,
            ids["lote_sync"],
            ids["operacion_sync"],
        )

    async with session_factory() as session:
        await _configurar_timeouts(session)
        respuesta = await solicitar_fecae_simulada(session)
        respuesta_json = respuesta.model_dump(mode="json")

    barrera = asyncio.Barrier(2)

    async def publicar() -> tuple[str, dict[str, object]]:
        async with session_factory() as session:
            await _configurar_timeouts(session)
            operacion = await session.get(
                OperacionIdempotente,
                ids["operacion_sync"],
            )
            assert operacion is not None
            await asyncio.wait_for(
                barrera.wait(),
                timeout=TIMEOUT_PRUEBA_SEGUNDOS,
            )
            try:
                await IdempotenciaFiscalService(
                    session
                ).guardar_resultado_operacion_sync(
                    operacion,
                    response_json=respuesta,
                    estado="rechazado_arca",
                )
            except SQLAlchemyTimeoutError:
                await session.rollback()
                ganadora = await session.get(
                    OperacionIdempotente,
                    ids["operacion_sync"],
                    populate_existing=True,
                )
                assert ganadora is not None
                replay = LoteProcesamientoResponse.model_validate(
                    ganadora.response_json
                )
                return "replay", replay.model_dump(mode="json")
            return "ganador", respuesta_json

    resultados = await asyncio.wait_for(
        asyncio.gather(publicar(), publicar()),
        timeout=TIMEOUT_PRUEBA_SEGUNDOS,
    )
    assert sorted(resultado[0] for resultado in resultados) == ["ganador", "replay"]
    assert resultados[0][1] == resultados[1][1] == respuesta_json
    assert llamadas_fecae == 1


async def _competir_publicacion_worker(
    session_factory: async_sessionmaker[AsyncSession],
    ids: dict[str, int],
) -> None:
    """Hace competir dos workers y reconstruye el replay del ganador."""
    llamadas_fecae = 0
    barrera = asyncio.Barrier(2)

    async def solicitar_fecae_simulada() -> None:
        """Registra la única frontera FECAE previa a las publicaciones worker."""
        nonlocal llamadas_fecae
        llamadas_fecae += 1

    await solicitar_fecae_simulada()

    async def publicar() -> tuple[str, dict[str, object]]:
        async with session_factory() as session:
            await _configurar_timeouts(session)
            lote = await session.get(LoteComprobante, ids["lote_worker"])
            assert lote is not None
            await asyncio.wait_for(
                barrera.wait(),
                timeout=TIMEOUT_PRUEBA_SEGUNDOS,
            )
            try:
                await LoteComprobantesService(
                    session
                )._guardar_respuesta_operacion_background(
                    lote,
                    ids["operacion_worker"],
                )
                await session.commit()
            except LoteComprobanteConflictoError:
                await session.rollback()
                ganadora = await session.get(
                    OperacionIdempotente,
                    ids["operacion_worker"],
                    populate_existing=True,
                )
                assert ganadora is not None
                replay = LoteProcesamientoResponse.model_validate(
                    ganadora.response_json
                )
                return "replay", replay.model_dump(mode="json")
            operacion = await session.get(
                OperacionIdempotente,
                ids["operacion_worker"],
                populate_existing=True,
            )
            assert operacion is not None
            return "ganador", dict(operacion.response_json)

    resultados = await asyncio.wait_for(
        asyncio.gather(publicar(), publicar()),
        timeout=TIMEOUT_PRUEBA_SEGUNDOS,
    )
    assert sorted(resultado[0] for resultado in resultados) == ["ganador", "replay"]
    assert resultados[0][1] == resultados[1][1]
    assert resultados[0][1]["errores_arca"] == [ERROR_ARCA_10005]
    assert llamadas_fecae == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19c_atomicidad_cas_y_replay_sin_segunda_fecae() -> None:
    """Ejercita locks reales, CAS sync/worker y rollback conjunto PF-19C."""
    database_url = require_disposable_postgres_url(purpose="runtime PF-19C")
    engine = await _preparar_pf19c(database_url)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        ids = await asyncio.wait_for(
            _sembrar_grafos(session_factory),
            timeout=TIMEOUT_PRUEBA_SEGUNDOS,
        )
        await asyncio.wait_for(
            _probar_rollback_conjunto(session_factory, ids),
            timeout=TIMEOUT_PRUEBA_SEGUNDOS,
        )
        await asyncio.wait_for(
            _competir_publicacion_sync(session_factory, ids),
            timeout=TIMEOUT_PRUEBA_SEGUNDOS,
        )
        await asyncio.wait_for(
            _competir_publicacion_worker(session_factory, ids),
            timeout=TIMEOUT_PRUEBA_SEGUNDOS,
        )
    except PydanticValidationError as exc:
        pytest.fail(f"El replay PF-19C perdió su contrato tipado: {exc}")
    finally:
        await engine.dispose()
