"""Migración y coordinación PF-13 sobre PostgreSQL descartable."""

import asyncio
import json
from copy import deepcopy
from contextlib import suppress
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.api.lotes_comprobantes import _resolver_remanente_legacy_aceptado
from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceRevision,
    PuntoVentaGuardaEmisionRece,
)
from app.models.empresa import Empresa, LoteDuplicadosCoordinacion
from app.models.idempotencia_fiscal import (
    IntentoEmisionFiscal,
    LoteDuplicadoCoincidencia,
    LoteDuplicadoCoincidenciaMiembro,
    LoteDuplicadoEvidencia,
    OperacionIdempotente,
)
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.services.duplicados_lotes_service import (
    DuplicadosLoteError,
    DuplicadosLotePreflightCambioError,
    DuplicadosLotesService,
)
from app.services import duplicados_lotes_service as duplicados_lotes_module
from app.services.lote_comprobantes_service import (
    LoteComprobanteError,
    LoteComprobantesService,
)
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url
from tests.test_duplicados_lotes_v2 import (
    _crear_escenario_admision_legacy,
    _crear_escenario_coordinacion,
    _crear_escenario_dos_lotes_coincidentes,
    _ejecutar_contencion_dos_lotes,
)


REVISION_ANTERIOR = "f4a5b6c7d8e9"
REVISION_DUPLICADOS_V2 = "a1b2c3d4e5f6"
TIMEOUT_SECONDS = 5


async def _cancelar_tarea(task: asyncio.Task) -> None:
    """Cancela y consume una tarea para no dejar trabajo pendiente en el loop."""
    if task.done():
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def _asignar_usuario_sintetico(
    session_factory,
    *,
    empresa_id: int,
    operacion_ids: list[int],
    sufijo: str,
) -> int:
    """Asigna un actor ficticio a operaciones que aceptarán evidencia."""
    async with session_factory() as session:
        usuario = Usuario(
            email=f"pf13-{sufijo}@example.invalid",
            hashed_password="hash-sintetico-no-utilizable",
            nombre="Operador sintético",
            empresa_id=empresa_id,
        )
        session.add(usuario)
        await session.flush()
        await session.execute(
            update(OperacionIdempotente)
            .where(OperacionIdempotente.id.in_(operacion_ids))
            .values(usuario_id=usuario.id)
        )
        await session.commit()
        return int(usuario.id)


async def _marcar_testigo_autorizado(
    session_factory,
    *,
    lote_id: int,
    grupo_id: int,
) -> None:
    """Convierte un lote previo sintético en antecedente autorizado."""
    async with session_factory() as session:
        await session.execute(
            update(LoteComprobanteGrupo)
            .where(LoteComprobanteGrupo.id == grupo_id)
            .values(estado="autorizado")
        )
        await session.execute(
            update(LoteComprobante)
            .where(LoteComprobante.id == lote_id)
            .values(
                estado="completado",
                grupos_validos=0,
                grupos_emitidos=1,
            )
        )
        await session.commit()


async def _crear_evidencia_aceptada(
    session_factory,
    monkeypatch,
    *,
    sufijo: str,
) -> dict[str, object]:
    """Crea dos lotes coincidentes y acepta la evidencia desde su operación raíz."""
    monkeypatch.setattr(settings, "arca_env", "homologacion")
    (
        empresa_id,
        lotes,
        grupos,
        operaciones,
    ) = await _crear_escenario_dos_lotes_coincidentes(session_factory)
    await _marcar_testigo_autorizado(
        session_factory,
        lote_id=lotes[1],
        grupo_id=grupos[1],
    )
    usuario_id = await _asignar_usuario_sintetico(
        session_factory,
        empresa_id=empresa_id,
        operacion_ids=operaciones,
        sufijo=sufijo,
    )
    async with session_factory() as session:
        service = DuplicadosLotesService(session)
        control, token, accepted = await service.evaluar_y_reservar(
            operacion_id=operaciones[0],
            lote_id=lotes[0],
            empresa_id=empresa_id,
            estados={"validado"},
            grupo_ids=None,
            aceptacion_recibida=None,
            solicitante_nombre="Operador sintético",
            reservar=True,
            ambiente="homologacion",
        )
        assert control["estado"] == "requiere_confirmacion"
        assert token is not None
        assert accepted is False
        control, same_token, accepted = await service.evaluar_y_reservar(
            operacion_id=operaciones[0],
            lote_id=lotes[0],
            empresa_id=empresa_id,
            estados={"validado"},
            grupo_ids=None,
            aceptacion_recibida=token,
            solicitante_nombre="Operador sintético",
            reservar=True,
            ambiente="homologacion",
        )
        assert same_token == token
        assert accepted is True
        operation = await session.get(OperacionIdempotente, operaciones[0])
        assert operation is not None
        generation_id = int(operation.duplicados_generacion_id)
    return {
        "empresa_id": empresa_id,
        "lotes": lotes,
        "grupos": grupos,
        "operaciones": operaciones,
        "usuario_id": usuario_id,
        "token": token,
        "generation_id": generation_id,
    }


async def _insertar_generacion(
    connection,
    *,
    operacion_id: int,
    empresa_id: int,
    lote_id: int,
    generacion: int,
    evidencia_id: str,
) -> int:
    """Inserta una generación sintética mínima y devuelve su identidad."""
    generation_id = await connection.scalar(
        text(
            """
            INSERT INTO lotes_duplicados_evidencias (
                operacion_id, empresa_id, ambiente, lote_id, generacion,
                formato, evidencia_id, snapshot_hash, control_snapshot_json,
                created_at
            ) VALUES (
                :operacion_id, :empresa_id, 'homologacion', :lote_id,
                :generacion, 'duplicados_relacion/1', :evidencia_id,
                :snapshot_hash, CAST(:snapshot AS json), now()
            )
            RETURNING id
            """
        ),
        {
            "operacion_id": operacion_id,
            "empresa_id": empresa_id,
            "lote_id": lote_id,
            "generacion": generacion,
            "evidencia_id": evidencia_id,
            "snapshot_hash": f"{generacion:064d}"[-64:],
            "snapshot": json.dumps({"generacion": generacion}),
        },
    )
    assert generation_id is not None
    return int(generation_id)


def _constraint_de_integrity_error(error: IntegrityError) -> str | None:
    """Extrae el constraint tanto del adaptador asyncpg como de psycopg."""
    candidates = (
        error.orig,
        getattr(error.orig, "__cause__", None),
        getattr(error.orig, "__context__", None),
    )
    for candidate in candidates:
        if candidate is None:
            continue
        constraint_name = getattr(candidate, "constraint_name", None)
        if constraint_name:
            return str(constraint_name)
        diagnostic = getattr(candidate, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if constraint_name:
            return str(constraint_name)
    return None


async def _esperar_integrity_error(
    connection,
    statement,
    params,
    *,
    constraint_name: str,
) -> None:
    """Aísla y atribuye una violación al constraint físico esperado."""
    savepoint = await connection.begin_nested()
    try:
        with pytest.raises(IntegrityError) as caught:
            await connection.execute(statement, params)
        assert _constraint_de_integrity_error(caught.value) == constraint_name
    finally:
        await savepoint.rollback()


async def _crear_intento_incierto(
    session_factory,
    *,
    operacion_id: int,
    grupo_id: int,
    generation_id: int,
) -> int:
    """Persiste un intento sintético completo ligado a una generación PF-13."""
    async with session_factory() as session:
        operation = await session.get(OperacionIdempotente, operacion_id)
        group = await session.get(LoteComprobanteGrupo, grupo_id)
        assert operation is not None
        assert group is not None
        operation.rece_snapshot_hash = "a" * 64
        snapshot = OperacionIdempotenteElegibilidadRece(
            operacion_id=operacion_id,
            empresa_id=int(group.empresa_id),
            punto_venta_id=int(group.punto_venta_id),
            ambiente=str(group.ambiente),
            elegibilidad_revision_id=int(group.punto_venta_elegibilidad_revision_id),
            punto_venta_revision_fiscal=int(group.punto_venta_revision_fiscal),
        )
        session.add(snapshot)
        await session.flush()
        guard = PuntoVentaGuardaEmisionRece(
            token=f"{operacion_id:064d}"[-64:],
            fase="requiere_reconciliacion",
            operacion_id=operacion_id,
            empresa_id=int(group.empresa_id),
            punto_venta_id=int(group.punto_venta_id),
            ambiente=str(group.ambiente),
            elegibilidad_revision_id=int(group.punto_venta_elegibilidad_revision_id),
            punto_venta_revision_fiscal=int(group.punto_venta_revision_fiscal),
            arca_iniciada_en=group.created_at,
        )
        session.add(guard)
        await session.flush()
        attempt = IntentoEmisionFiscal(
            operacion_id=operacion_id,
            empresa_id=int(group.empresa_id),
            usuario_id=operation.usuario_id,
            punto_venta_id=int(group.punto_venta_id),
            punto_venta_numero=int(group.punto_venta_numero),
            tipo_comprobante=int(group.tipo_comprobante),
            numero_planificado=900000 + grupo_id,
            fecha_emision=group.fecha_emision_normalizada,
            total=group.total_estimado,
            payload_hash="b" * 64,
            huella_logica="c" * 64,
            estado="requiere_reconciliacion",
            ambiente=str(group.ambiente),
            punto_venta_elegibilidad_revision_id=int(
                group.punto_venta_elegibilidad_revision_id
            ),
            punto_venta_revision_fiscal=int(group.punto_venta_revision_fiscal),
            guarda_rece_id=int(guard.id),
            lote_id=int(group.lote_id),
            grupo_id=grupo_id,
            duplicados_generacion_id=generation_id,
        )
        session.add(attempt)
        await session.commit()
        return int(attempt.id)


async def _crear_scope_adicional(
    session_factory,
    *,
    ambiente: str,
    semilla: int,
    empresa_id: int | None = None,
) -> tuple[int, int, int, int]:
    """Crea un scope independiente completo para probar locks no relacionados."""
    async with session_factory() as session:
        if empresa_id is None:
            empresa = Empresa(
                razon_social=f"Empresa sintética {semilla}",
                cuit=f"2099999{semilla:04d}",
                condicion_iva="RI",
                domicilio="Calle sintética 123",
                localidad="Ciudad de prueba",
                provincia="Buenos Aires",
                codigo_postal="1000",
                inicio_actividades=date(2020, 1, 1),
            )
            session.add(empresa)
            await session.flush()
            empresa_id = int(empresa.id)
            punto = PuntoVenta(
                empresa_id=empresa_id,
                numero=semilla,
                activo=True,
                es_webservice=True,
                revision_fiscal=1,
            )
            session.add(punto)
            await session.flush()
        else:
            punto = await session.scalar(
                select(PuntoVenta)
                .where(PuntoVenta.empresa_id == empresa_id)
                .order_by(PuntoVenta.id)
            )
            assert punto is not None
        revision = PuntoVentaElegibilidadReceRevision(
            empresa_id=empresa_id,
            punto_venta_id=int(punto.id),
            ambiente=ambiente,
            revision=1,
            estado="no_verificado",
            fuente="alta_manual",
            evidencia_tipo="sin_evidencia",
            punto_revision_fiscal=1,
        )
        session.add(revision)
        await session.flush()
        session.add(
            LoteDuplicadosCoordinacion(
                empresa_id=empresa_id,
                ambiente=ambiente,
                revision=0,
            )
        )
        lote = LoteComprobante(
            empresa_id=empresa_id,
            nombre_archivo=f"scope-{semilla}.xlsx",
            archivo_hash=f"{semilla:064x}"[-64:],
            estado="validado",
            total_filas=1,
            total_grupos=1,
            grupos_validos=1,
        )
        session.add(lote)
        await session.flush()
        group = LoteComprobanteGrupo(
            lote_id=int(lote.id),
            empresa_id=empresa_id,
            comprobante_ref=f"SCOPE-{semilla}",
            orden=1,
            estado="validado",
            tipo_comprobante=6,
            punto_venta_numero=int(punto.numero),
            total_estimado=Decimal("1210.00"),
            punto_venta_id=int(punto.id),
            ambiente=ambiente,
            punto_venta_elegibilidad_revision_id=int(revision.id),
            punto_venta_revision_fiscal=1,
            duplicados_version="duplicados_lotes/v2",
            duplicados_cobertura="completa",
            huella_fiscal_completa=f"{semilla + 100:064x}"[-64:],
            fecha_emision_normalizada=date(2026, 8, 9),
            moneda_duplicados="PES",
            cotizacion_duplicados="1",
            total_centavos=121000,
        )
        session.add(group)
        await session.flush()
        operation = OperacionIdempotente(
            empresa_id=empresa_id,
            idempotency_key=f"scope-{semilla}",
            tipo_operacion="procesar_lote",
            payload_hash=f"{semilla + 200:064x}"[-64:],
            estado="en_proceso",
            lote_id=int(lote.id),
        )
        session.add(operation)
        await session.commit()
        return empresa_id, int(lote.id), int(group.id), int(operation.id)


async def _catalogo_constraints_pf13(engine) -> dict[str, tuple[str, str, str]]:
    """Lee tipo, acción de borrado y definición de constraints PF-13."""
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT constraint_row.conname,
                           table_row.relname,
                           constraint_row.contype::text,
                           constraint_row.confdeltype::text,
                           pg_get_constraintdef(constraint_row.oid)
                    FROM pg_constraint AS constraint_row
                    JOIN pg_class AS table_row
                      ON table_row.oid = constraint_row.conrelid
                    JOIN pg_namespace AS namespace_row
                      ON namespace_row.oid = table_row.relnamespace
                    WHERE namespace_row.nspname = 'public'
                      AND table_row.relname IN (
                        'operaciones_idempotentes',
                        'intentos_emision_fiscal',
                        'lotes_duplicados_coordinacion',
                        'lotes_duplicados_evidencias',
                        'lotes_duplicados_coincidencias',
                        'lotes_duplicados_coincidencias_miembros'
                      )
                    """
                )
            )
        ).all()
    return {
        str(name): (str(table_name), str(constraint_type), str(definition))
        for name, table_name, constraint_type, _delete_action, definition in rows
    } | {
        f"{name}:delete": (str(table_name), str(delete_action), str(definition))
        for name, table_name, _constraint_type, delete_action, definition in rows
    }


async def _indices_pf13(engine) -> set[str]:
    """Devuelve los índices explícitos de las tablas compactas PF-13."""
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename IN (
                        'lotes_duplicados_evidencias',
                        'lotes_duplicados_coincidencias',
                        'lotes_duplicados_coincidencias_miembros',
                        'lotes_comprobantes_grupos'
                      )
                    """
                )
            )
        ).all()
    return {str(row[0]) for row in rows}


async def _snapshot_downgrade_pf13(
    session,
    *,
    operacion_id: int,
    grupo_id: int,
) -> dict[str, object]:
    """Proyecta canónicamente toda la evidencia que el downgrade debe preservar."""
    operation = (
        await session.execute(
            select(
                OperacionIdempotente.id,
                OperacionIdempotente.control_duplicados_json,
                OperacionIdempotente.duplicados_version,
                OperacionIdempotente.duplicados_generacion_id,
                OperacionIdempotente.operacion_raiz_id,
                OperacionIdempotente.solicitante_nombre_snapshot,
                OperacionIdempotente.solicitud_emision_at,
            ).where(OperacionIdempotente.id == operacion_id)
        )
    ).one()
    group = (
        await session.execute(
            select(
                LoteComprobanteGrupo.id,
                LoteComprobanteGrupo.duplicados_version,
                LoteComprobanteGrupo.duplicados_cobertura,
                LoteComprobanteGrupo.huella_fiscal_completa,
                LoteComprobanteGrupo.identidad_nombre_hash,
                LoteComprobanteGrupo.identidad_documento_hash,
                LoteComprobanteGrupo.identidad_nombre_original,
                LoteComprobanteGrupo.identidad_tipo_documento_original,
                LoteComprobanteGrupo.identidad_numero_documento_original,
                LoteComprobanteGrupo.fecha_emision_normalizada,
                LoteComprobanteGrupo.moneda_duplicados,
                LoteComprobanteGrupo.cotizacion_duplicados,
                LoteComprobanteGrupo.total_centavos,
                LoteComprobanteGrupo.duplicados_reserva_operacion_id,
            ).where(LoteComprobanteGrupo.id == grupo_id)
        )
    ).one()
    generations = list(
        (
            await session.execute(
                select(
                    LoteDuplicadoEvidencia.id,
                    LoteDuplicadoEvidencia.operacion_id,
                    LoteDuplicadoEvidencia.empresa_id,
                    LoteDuplicadoEvidencia.ambiente,
                    LoteDuplicadoEvidencia.lote_id,
                    LoteDuplicadoEvidencia.generacion,
                    LoteDuplicadoEvidencia.formato,
                    LoteDuplicadoEvidencia.evidencia_id,
                    LoteDuplicadoEvidencia.snapshot_hash,
                    LoteDuplicadoEvidencia.control_snapshot_json,
                    LoteDuplicadoEvidencia.aceptacion_id,
                    LoteDuplicadoEvidencia.aceptada_por_usuario_id,
                    LoteDuplicadoEvidencia.aceptada_por_nombre,
                    LoteDuplicadoEvidencia.aceptada_at,
                    LoteDuplicadoEvidencia.aceptacion_origen_generacion_id,
                    LoteDuplicadoEvidencia.created_at,
                )
                .where(LoteDuplicadoEvidencia.operacion_id == operacion_id)
                .order_by(LoteDuplicadoEvidencia.id)
            )
        ).all()
    )
    blocks = list(
        (
            await session.execute(
                select(
                    LoteDuplicadoCoincidencia.id,
                    LoteDuplicadoCoincidencia.generacion_id,
                    LoteDuplicadoCoincidencia.operacion_id,
                    LoteDuplicadoCoincidencia.empresa_id,
                    LoteDuplicadoCoincidencia.ambiente,
                    LoteDuplicadoCoincidencia.lote_id,
                    LoteDuplicadoCoincidencia.bloque_clave,
                    LoteDuplicadoCoincidencia.clase,
                    LoteDuplicadoCoincidencia.antecedente_clave,
                    LoteDuplicadoCoincidencia.snapshot_json,
                )
                .where(LoteDuplicadoCoincidencia.operacion_id == operacion_id)
                .order_by(LoteDuplicadoCoincidencia.id)
            )
        ).all()
    )
    generation_ids = [int(row.id) for row in generations]
    block_ids = [int(row.id) for row in blocks]
    members = list(
        (
            await session.execute(
                select(
                    LoteDuplicadoCoincidenciaMiembro.id,
                    LoteDuplicadoCoincidenciaMiembro.bloque_id,
                    LoteDuplicadoCoincidenciaMiembro.lado,
                    LoteDuplicadoCoincidenciaMiembro.miembro_clave,
                    LoteDuplicadoCoincidenciaMiembro.grupo_id,
                    LoteDuplicadoCoincidenciaMiembro.comprobante_id,
                    LoteDuplicadoCoincidenciaMiembro.nombre_hash,
                    LoteDuplicadoCoincidenciaMiembro.documento_hash,
                    LoteDuplicadoCoincidenciaMiembro.ordinal,
                    LoteDuplicadoCoincidenciaMiembro.relevancia,
                    LoteDuplicadoCoincidenciaMiembro.snapshot_json,
                )
                .where(LoteDuplicadoCoincidenciaMiembro.bloque_id.in_(block_ids))
                .order_by(LoteDuplicadoCoincidenciaMiembro.id)
            )
        ).all()
        if generation_ids and block_ids
        else []
    )
    return {
        "operation": tuple(operation),
        "group": tuple(group),
        "generations": [tuple(row) for row in generations],
        "blocks": [tuple(row) for row in blocks],
        "members": [tuple(row) for row in members],
    }


async def _crear_testigo_tardio(
    session_factory,
    *,
    empresa_id: int,
    grupo_modelo_id: int,
    ambiente: str = "homologacion",
) -> int:
    """Confirma un grupo sintético nuevo y avanza la revisión del scope."""
    async with session_factory() as session:
        model = await session.get(LoteComprobanteGrupo, grupo_modelo_id)
        assert model is not None
        lote = LoteComprobante(
            empresa_id=empresa_id,
            nombre_archivo="testigo-tardio.xlsx",
            archivo_hash="f" * 64,
            estado="completado",
            total_filas=1,
            total_grupos=1,
            grupos_validos=0,
            grupos_emitidos=1,
        )
        session.add(lote)
        await session.flush()
        group = LoteComprobanteGrupo(
            lote_id=int(lote.id),
            empresa_id=empresa_id,
            comprobante_ref="TESTIGO-TARDIO",
            orden=1,
            estado="autorizado",
            tipo_comprobante=int(model.tipo_comprobante),
            punto_venta_numero=int(model.punto_venta_numero),
            total_estimado=model.total_estimado,
            punto_venta_id=int(model.punto_venta_id),
            ambiente=str(model.ambiente),
            punto_venta_elegibilidad_revision_id=int(
                model.punto_venta_elegibilidad_revision_id
            ),
            punto_venta_revision_fiscal=int(model.punto_venta_revision_fiscal),
            duplicados_version=str(model.duplicados_version),
            duplicados_cobertura=str(model.duplicados_cobertura),
            huella_fiscal_completa=str(model.huella_fiscal_completa),
            identidad_nombre_hash=model.identidad_nombre_hash,
            identidad_documento_hash=model.identidad_documento_hash,
            fecha_emision_normalizada=model.fecha_emision_normalizada,
            moneda_duplicados=model.moneda_duplicados,
            cotizacion_duplicados=model.cotizacion_duplicados,
            total_centavos=model.total_centavos,
        )
        session.add(group)
        await session.flush()
        await session.execute(
            update(LoteDuplicadosCoordinacion)
            .where(
                LoteDuplicadosCoordinacion.empresa_id == empresa_id,
                LoteDuplicadosCoordinacion.ambiente == ambiente,
            )
            .values(
                revision=LoteDuplicadosCoordinacion.revision + 1,
            )
        )
        await session.commit()
        return int(group.id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_dos_lotes_perdedor_no_reserva_ni_bloquea_ganador(
    monkeypatch,
) -> None:
    database_url = require_disposable_postgres_url(
        purpose="contención PF-13 entre dos lotes"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        await _ejecutar_contencion_dos_lotes(session_factory, monkeypatch)
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_migra_y_serializa_reservas_con_for_update() -> None:
    """El segundo coordinador espera, revalida y no pisa la primera reserva."""
    database_url = require_disposable_postgres_url(
        purpose="migración y coordinación PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        (
            empresa_id,
            lote_id,
            grupo_id,
            operaciones,
        ) = await _crear_escenario_coordinacion(session_factory)
        async with session_factory() as session:
            await session.execute(
                update(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.id == grupo_id)
                .values(
                    total_centavos=999999999999,
                    cotizacion_duplicados="123456789.123456789123",
                )
            )
            await session.commit()

        entro_primera = asyncio.Event()
        liberar_primera = asyncio.Event()
        async with session_factory() as session_1, session_factory() as session_2:
            service_1 = DuplicadosLotesService(session_1)
            service_2 = DuplicadosLotesService(session_2)
            calcular_original = service_1.calcular_control

            async def calcular_bloqueado(**kwargs):
                entro_primera.set()
                await liberar_primera.wait()
                return await calcular_original(**kwargs)

            service_1.calcular_control = calcular_bloqueado
            primera = asyncio.create_task(
                service_1.evaluar_y_reservar(
                    operacion_id=operaciones[0],
                    lote_id=lote_id,
                    empresa_id=empresa_id,
                    estados={"validado"},
                    grupo_ids=None,
                    aceptacion_recibida=None,
                    solicitante_nombre="Primera persona",
                    reservar=True,
                    ambiente="homologacion",
                )
            )
            segunda = None
            try:
                await asyncio.wait_for(entro_primera.wait(), timeout=TIMEOUT_SECONDS)
                segunda = asyncio.create_task(
                    service_2.evaluar_y_reservar(
                        operacion_id=operaciones[1],
                        lote_id=lote_id,
                        empresa_id=empresa_id,
                        estados={"validado"},
                        grupo_ids=None,
                        aceptacion_recibida=None,
                        solicitante_nombre="Segunda persona",
                        reservar=True,
                        ambiente="homologacion",
                    )
                )
                done, _ = await asyncio.wait({segunda}, timeout=0.1)
                assert not done
                liberar_primera.set()
                await asyncio.wait_for(primera, timeout=TIMEOUT_SECONDS)
                with pytest.raises(DuplicadosLoteError, match="reservó"):
                    await asyncio.wait_for(segunda, timeout=TIMEOUT_SECONDS)
            finally:
                liberar_primera.set()
                await _cancelar_tarea(primera)
                if segunda is not None:
                    await _cancelar_tarea(segunda)

        async with session_factory() as verifier:
            grupo = await verifier.get(LoteComprobanteGrupo, grupo_id)
            revision = await verifier.scalar(
                select(LoteDuplicadosCoordinacion.revision).where(
                    LoteDuplicadosCoordinacion.empresa_id == empresa_id,
                    LoteDuplicadosCoordinacion.ambiente == "homologacion",
                )
            )
            assert grupo.duplicados_reserva_operacion_id == operaciones[0]
            assert grupo.total_centavos == 999999999999
            assert grupo.cotizacion_duplicados == "123456789.123456789123"
            assert revision == 1
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_admision_legacy_revalida_antecedente_precoordinador(
    monkeypatch,
) -> None:
    """Un antecedente durable nuevo bloquea antes de crear o reclamar."""
    database_url = require_disposable_postgres_url(
        purpose="revalidación de admisión legacy PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        monkeypatch.setattr(settings, "arca_env", "produccion")
        (
            empresa_id,
            lote_id,
            grupo_id,
            owner_id,
            _,
            payload_operacion,
            material_rece,
        ) = await _crear_escenario_admision_legacy(session_factory)
        async with session_factory() as preflight_session:
            owner_preleido = await DuplicadosLotesService(
                preflight_session
            ).obtener_propietario_legacy_aceptado(
                lote_id=lote_id,
                empresa_id=empresa_id,
            )
            assert owner_preleido is not None
            assert int(owner_preleido.id) == owner_id
            owner_snapshot = (
                owner_preleido.estado,
                owner_preleido.payload_hash,
                deepcopy(owner_preleido.response_json),
            )
            lote = await preflight_session.get(LoteComprobante, lote_id)
            assert lote is not None
            metadata_snapshot = deepcopy(lote.metadata_json)
            operaciones_antes = int(
                await preflight_session.scalar(
                    select(func.count())
                    .select_from(OperacionIdempotente)
                    .where(OperacionIdempotente.lote_id == lote_id)
                )
                or 0
            )
            await preflight_session.rollback()

        testigo_id = await _crear_testigo_tardio(
            session_factory,
            empresa_id=empresa_id,
            grupo_modelo_id=grupo_id,
            ambiente="produccion",
        )

        async with session_factory() as admission_session:
            with pytest.raises(HTTPException) as raised:
                await asyncio.wait_for(
                    _resolver_remanente_legacy_aceptado(
                        db=admission_session,
                        empresa_id=empresa_id,
                        usuario_id=None,
                        idempotency_key="admision-legacy-precoordinador-nueva",
                        tipo_operacion="procesar_lote",
                        payload=payload_operacion,
                        lote_id=lote_id,
                        material_rece=material_rece,
                        estados={"validado"},
                        grupo_ids=None,
                        aceptacion_recibida=None,
                        solicitante_nombre="Operador A",
                        propietario_inicial_id=owner_id,
                    ),
                    timeout=TIMEOUT_SECONDS,
                )
            assert raised.value.status_code == 409
            assert (
                raised.value.detail["categoria_error"]
                == "duplicado_legacy_no_reconfirmable"
            )

        async with session_factory() as verifier:
            owner = await verifier.get(OperacionIdempotente, owner_id)
            lote = await verifier.get(LoteComprobante, lote_id)
            testigo = await verifier.get(LoteComprobanteGrupo, testigo_id)
            assert owner is not None
            assert lote is not None
            assert testigo is not None
            assert testigo.estado == "autorizado"
            assert (
                owner.estado,
                owner.payload_hash,
                owner.response_json,
            ) == owner_snapshot
            assert owner.duplicados_version is None
            assert owner.duplicados_generacion_id is None
            assert owner.control_duplicados_json is None
            assert lote.metadata_json == metadata_snapshot
            assert (
                int(
                    await verifier.scalar(
                        select(func.count())
                        .select_from(OperacionIdempotente)
                        .where(OperacionIdempotente.lote_id == lote_id)
                    )
                    or 0
                )
                == operaciones_antes
            )
            assert (
                await verifier.scalar(
                    select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                        LoteComprobanteGrupo.id == grupo_id
                    )
                )
                is None
            )
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(LoteDuplicadoEvidencia)
                )
                == 0
            )
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(IntentoEmisionFiscal)
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_admision_legacy_reserva_y_competidora_revalida(
    monkeypatch,
) -> None:
    """La competidora espera la raíz completa y luego observa su reserva."""
    database_url = require_disposable_postgres_url(
        purpose="contención de admisión legacy PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        monkeypatch.setattr(settings, "arca_env", "produccion")
        (
            empresa_id,
            lote_id,
            grupo_id,
            owner_id,
            competidora_id,
            payload_operacion,
            material_rece,
        ) = await _crear_escenario_admision_legacy(session_factory)
        entro_admision = asyncio.Event()
        liberar_admision = asyncio.Event()
        competidora_llego_al_coordinador = asyncio.Event()
        evaluar_original = DuplicadosLotesService.evaluar_y_reservar_bajo_coordinacion
        backend_ids = {}

        def observar_coordinador(
            connection,
            _cursor,
            statement,
            _parameters,
            _context,
            _executemany,
        ) -> None:
            sql = " ".join(statement.lower().split())
            if "lotes_duplicados_coordinacion" not in sql or "for update" not in sql:
                return
            driver_connection = connection.connection.driver_connection
            backend_pid = driver_connection.get_server_pid()
            if "a" not in backend_ids:
                backend_ids["a"] = backend_pid
            elif backend_pid != backend_ids["a"] and "b" not in backend_ids:
                backend_ids["b"] = backend_pid
                competidora_llego_al_coordinador.set()

        async def evaluar_bloqueado(self, **kwargs):
            if kwargs["operacion_id"] == owner_id:
                entro_admision.set()
                await liberar_admision.wait()
            return await evaluar_original(self, **kwargs)

        monkeypatch.setattr(
            DuplicadosLotesService,
            "evaluar_y_reservar_bajo_coordinacion",
            evaluar_bloqueado,
        )
        event.listen(engine.sync_engine, "before_cursor_execute", observar_coordinador)
        try:
            async with session_factory() as session_a, session_factory() as session_b:
                admision = asyncio.create_task(
                    _resolver_remanente_legacy_aceptado(
                        db=session_a,
                        empresa_id=empresa_id,
                        usuario_id=None,
                        idempotency_key="admision-legacy-owner",
                        tipo_operacion="procesar_lote",
                        payload=payload_operacion,
                        lote_id=lote_id,
                        material_rece=material_rece,
                        estados={"validado"},
                        grupo_ids=None,
                        aceptacion_recibida=None,
                        solicitante_nombre="Operador A",
                        propietario_inicial_id=owner_id,
                    )
                )
                competidora = None
                try:
                    await asyncio.wait_for(
                        entro_admision.wait(), timeout=TIMEOUT_SECONDS
                    )
                    async with session_factory() as before_commit:
                        owner_previo = await before_commit.get(
                            OperacionIdempotente, owner_id
                        )
                        reserva_previa = await before_commit.scalar(
                            select(
                                LoteComprobanteGrupo.duplicados_reserva_operacion_id
                            ).where(LoteComprobanteGrupo.id == grupo_id)
                        )
                        assert owner_previo is not None
                        assert owner_previo.estado == "interrumpida_pre_arca"
                        assert owner_previo.duplicados_version is None
                        assert reserva_previa is None
                    competidora = asyncio.create_task(
                        DuplicadosLotesService(session_b).evaluar_y_reservar(
                            operacion_id=competidora_id,
                            lote_id=lote_id,
                            empresa_id=empresa_id,
                            estados={"validado"},
                            grupo_ids=None,
                            aceptacion_recibida=None,
                            solicitante_nombre="Operador B",
                            reservar=True,
                            ambiente="produccion",
                        )
                    )
                    await asyncio.wait_for(
                        competidora_llego_al_coordinador.wait(),
                        timeout=TIMEOUT_SECONDS,
                    )
                    backend_a = backend_ids["a"]
                    backend_b = backend_ids["b"]
                    assert backend_a != backend_b
                    bloqueo_observado = False
                    for _ in range(50):
                        async with session_factory() as observer:
                            blockers = await observer.scalar(
                                text("SELECT pg_blocking_pids(:pid)"),
                                {"pid": backend_b},
                            )
                        if backend_a in (blockers or []):
                            bloqueo_observado = True
                            break
                        await asyncio.sleep(0.02)
                    assert bloqueo_observado is True
                    assert not competidora.done()
                    liberar_admision.set()
                    resultado = await asyncio.wait_for(
                        admision, timeout=TIMEOUT_SECONDS
                    )
                    assert resultado[2] is False
                    assert resultado[4] is True
                    with pytest.raises(DuplicadosLoteError, match="reservó"):
                        await asyncio.wait_for(competidora, timeout=TIMEOUT_SECONDS)
                finally:
                    liberar_admision.set()
                    await _cancelar_tarea(admision)
                    if competidora is not None:
                        await _cancelar_tarea(competidora)
        finally:
            event.remove(
                engine.sync_engine, "before_cursor_execute", observar_coordinador
            )

        async with session_factory() as verifier:
            owner = await verifier.get(OperacionIdempotente, owner_id)
            assert owner is not None
            assert owner.estado == "en_proceso"
            assert owner.duplicados_version == "duplicados_lotes/v2"
            assert owner.duplicados_generacion_id is not None
            assert (
                await verifier.scalar(
                    select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                        LoteComprobanteGrupo.id == grupo_id
                    )
                )
                == owner_id
            )
            assert (
                await verifier.scalar(
                    select(func.count())
                    .select_from(LoteDuplicadoEvidencia)
                    .where(LoteDuplicadoEvidencia.operacion_id == owner_id)
                )
                == 1
            )
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(IntentoEmisionFiscal)
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("modo", ["create", "claim"])
async def test_postgresql_admision_legacy_revierte_create_o_claim(
    monkeypatch,
    modo: str,
) -> None:
    """El fallo previo a reserva revierte insert o CAS sin compensación."""
    database_url = require_disposable_postgres_url(
        purpose=f"rollback de admisión legacy PF-13: {modo}"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        monkeypatch.setattr(settings, "arca_env", "produccion")
        (
            empresa_id,
            lote_id,
            grupo_id,
            owner_id,
            _,
            payload_operacion,
            material_rece,
        ) = await _crear_escenario_admision_legacy(session_factory)
        async with session_factory() as snapshot_session:
            owner = await snapshot_session.get(OperacionIdempotente, owner_id)
            lote = await snapshot_session.get(LoteComprobante, lote_id)
            assert owner is not None
            assert lote is not None
            owner_snapshot = (
                owner.estado,
                owner.payload_hash,
                deepcopy(owner.response_json),
                owner.duplicados_version,
                owner.duplicados_generacion_id,
                deepcopy(owner.control_duplicados_json),
            )
            metadata_snapshot = deepcopy(lote.metadata_json)
            operaciones_antes = int(
                await snapshot_session.scalar(
                    select(func.count())
                    .select_from(OperacionIdempotente)
                    .where(OperacionIdempotente.lote_id == lote_id)
                )
                or 0
            )
        idempotency_key = (
            "admision-legacy-owner"
            if modo == "claim"
            else "admision-legacy-create-nueva"
        )
        etapa_observada = False

        async def fallar_antes_de_reservar(self, **kwargs):
            nonlocal etapa_observada
            operacion = await self.db.get(
                OperacionIdempotente,
                int(kwargs["operacion_id"]),
                populate_existing=True,
            )
            assert operacion is not None
            assert operacion.estado == "en_proceso"
            assert (int(operacion.id) == owner_id) is (modo == "claim")
            etapa_observada = True
            raise DuplicadosLoteError(
                "Fallo sintético antes de reservar.",
                "duplicados_fallo_sintetico",
            )

        monkeypatch.setattr(
            DuplicadosLotesService,
            "evaluar_y_reservar_bajo_coordinacion",
            fallar_antes_de_reservar,
        )
        async with session_factory() as admission_session:
            with pytest.raises(HTTPException) as raised:
                await asyncio.wait_for(
                    _resolver_remanente_legacy_aceptado(
                        db=admission_session,
                        empresa_id=empresa_id,
                        usuario_id=None,
                        idempotency_key=idempotency_key,
                        tipo_operacion="procesar_lote",
                        payload=payload_operacion,
                        lote_id=lote_id,
                        material_rece=material_rece,
                        estados={"validado"},
                        grupo_ids=None,
                        aceptacion_recibida=None,
                        solicitante_nombre="Operador A",
                        propietario_inicial_id=owner_id,
                    ),
                    timeout=TIMEOUT_SECONDS,
                )
            assert raised.value.status_code == 409
            assert (
                raised.value.detail["categoria_error"] == "duplicados_fallo_sintetico"
            )
        assert etapa_observada is True

        async with session_factory() as verifier:
            owner = await verifier.get(OperacionIdempotente, owner_id)
            lote = await verifier.get(LoteComprobante, lote_id)
            assert owner is not None
            assert lote is not None
            assert (
                owner.estado,
                owner.payload_hash,
                owner.response_json,
                owner.duplicados_version,
                owner.duplicados_generacion_id,
                owner.control_duplicados_json,
            ) == owner_snapshot
            assert lote.metadata_json == metadata_snapshot
            assert (
                int(
                    await verifier.scalar(
                        select(func.count())
                        .select_from(OperacionIdempotente)
                        .where(OperacionIdempotente.lote_id == lote_id)
                    )
                    or 0
                )
                == operaciones_antes
            )
            assert (
                await verifier.scalar(
                    select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                        LoteComprobanteGrupo.id == grupo_id
                    )
                )
                is None
            )
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(LoteDuplicadoEvidencia)
                )
                == 0
            )
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(IntentoEmisionFiscal)
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_downgrade_vacio_y_reupgrade() -> None:
    """El rollback físico sólo funciona sin evidencia y vuelve a migrar."""
    database_url = require_disposable_postgres_url(purpose="downgrade vacío PF-13")
    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_ANTERIOR, database_url)
    _run_alembic("upgrade", REVISION_DUPLICADOS_V2, database_url)
    _run_alembic("downgrade", REVISION_ANTERIOR, database_url)
    _run_alembic("upgrade", REVISION_DUPLICADOS_V2, database_url)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_schema_compacto_impone_scope_y_delete_actions() -> None:
    """PostgreSQL aplica checks, scopes compuestos y acciones de borrado PF-13."""
    database_url = require_disposable_postgres_url(
        purpose="contratos físicos compactos PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        (
            empresa_id,
            lote_id,
            grupo_id,
            operaciones,
        ) = await _crear_escenario_coordinacion(session_factory)
        usuario_id = await _asignar_usuario_sintetico(
            session_factory,
            empresa_id=empresa_id,
            operacion_ids=operaciones,
            sufijo="schema-fisico",
        )
        catalog = await _catalogo_constraints_pf13(engine)
        expected_named = {
            "ck_lotes_duplicados_coordinacion_ambiente",
            "ck_lotes_duplicados_evidencias_formato",
            "ck_lotes_duplicados_evidencias_snapshot_hash",
            "ck_lotes_duplicados_evidencias_generacion",
            "ck_lotes_duplicados_evidencias_aceptacion",
            "uq_lotes_duplicados_evidencias_operacion_generacion",
            "uq_lotes_duplicados_evidencias_scope",
            "ck_lotes_duplicados_coincidencias_clase",
            "fk_lotes_duplicados_coincidencias_generacion_scope",
            "uq_lotes_duplicados_coincidencias_bloque",
            "ck_lotes_duplicados_miembros_lado",
            "ck_lotes_duplicados_miembros_ordinal",
            "ck_lotes_duplicados_miembros_relevancia",
            "ck_lotes_duplicados_miembros_entidad",
            "uq_lotes_duplicados_miembros_clave",
            "uq_lotes_duplicados_miembros_ordinal",
            "fk_operaciones_idempotentes_duplicados_generacion",
            "fk_intento_duplicados_generacion_scope",
        }
        assert expected_named <= set(catalog)
        assert (
            catalog["fk_lotes_duplicados_coincidencias_generacion_scope:delete"][1]
            == "c"
        )
        assert (
            catalog["fk_operaciones_idempotentes_duplicados_generacion:delete"][1]
            == "n"
        )
        assert catalog["fk_intento_duplicados_generacion_scope:delete"][1] == "r"
        delete_definitions = [
            (action, definition)
            for name, (_table, action, definition) in catalog.items()
            if name.endswith(":delete")
        ]
        expected_fk_fragments = (
            ("c", "FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE"),
            (
                "c",
                "FOREIGN KEY (operacion_id) REFERENCES "
                "operaciones_idempotentes(id) ON DELETE CASCADE",
            ),
            (
                "r",
                "FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE RESTRICT",
            ),
            (
                "c",
                "FOREIGN KEY (lote_id) REFERENCES "
                "lotes_comprobantes(id) ON DELETE CASCADE",
            ),
            (
                "r",
                "FOREIGN KEY (aceptada_por_usuario_id) REFERENCES "
                "usuarios(id) ON DELETE RESTRICT",
            ),
            (
                "r",
                "FOREIGN KEY (aceptacion_origen_generacion_id) REFERENCES "
                "lotes_duplicados_evidencias(id) ON DELETE RESTRICT",
            ),
            (
                "c",
                "FOREIGN KEY (generacion_id, operacion_id, empresa_id, lote_id, "
                "ambiente) REFERENCES lotes_duplicados_evidencias(id, "
                "operacion_id, empresa_id, lote_id, ambiente) ON DELETE CASCADE",
            ),
            (
                "c",
                "FOREIGN KEY (bloque_id) REFERENCES "
                "lotes_duplicados_coincidencias(id) ON DELETE CASCADE",
            ),
            (
                "n",
                "FOREIGN KEY (duplicados_generacion_id) REFERENCES "
                "lotes_duplicados_evidencias(id) ON DELETE SET NULL",
            ),
            (
                "r",
                "FOREIGN KEY (duplicados_generacion_id, operacion_id, empresa_id, "
                "lote_id, ambiente) REFERENCES lotes_duplicados_evidencias(id, "
                "operacion_id, empresa_id, lote_id, ambiente) ON DELETE RESTRICT",
            ),
        )
        for expected_action, expected_definition in expected_fk_fragments:
            assert any(
                action == expected_action and definition == expected_definition
                for action, definition in delete_definitions
            )
        acceptance_origin_constraint = next(
            name
            for name, (table_name, constraint_type, definition) in catalog.items()
            if not name.endswith(":delete")
            and table_name == "lotes_duplicados_evidencias"
            and constraint_type == "f"
            and "FOREIGN KEY (aceptacion_origen_generacion_id)" in definition
        )
        assert {
            "ix_lotes_duplicados_evidencias_consulta",
            "ix_lotes_duplicados_coincidencias_generacion_clase",
            "ix_lotes_duplicados_miembros_pagina",
            "ix_lotes_duplicados_miembros_nombre",
            "ix_lotes_grupos_dup_huella_lote",
            "ix_lotes_grupos_dup_nombre",
            "ix_lotes_grupos_dup_documento",
            "ix_lotes_grupos_dup_reserva",
        } <= await _indices_pf13(engine)

        async with engine.begin() as connection:
            generation_id = await _insertar_generacion(
                connection,
                operacion_id=operaciones[0],
                empresa_id=empresa_id,
                lote_id=lote_id,
                generacion=1,
                evidencia_id="v2.fisico.principal",
            )
            foreign_generation_id = await _insertar_generacion(
                connection,
                operacion_id=operaciones[1],
                empresa_id=empresa_id,
                lote_id=lote_id,
                generacion=1,
                evidencia_id="v2.fisico.ajena",
            )
            nullable_generation_id = await _insertar_generacion(
                connection,
                operacion_id=operaciones[1],
                empresa_id=empresa_id,
                lote_id=lote_id,
                generacion=2,
                evidencia_id="v2.fisico.set-null",
            )
            acceptance_origin_id = await connection.scalar(
                text(
                    """
                    INSERT INTO lotes_duplicados_evidencias (
                        operacion_id, empresa_id, ambiente, lote_id, generacion,
                        formato, evidencia_id, snapshot_hash,
                        control_snapshot_json, aceptacion_id,
                        aceptada_por_usuario_id, aceptada_por_nombre,
                        aceptada_at, created_at
                    ) VALUES (
                        :operation_id, :company_id, 'homologacion', :batch_id,
                        3, 'duplicados_relacion/1', 'v2.fisico.origen',
                        :snapshot_hash, CAST('{}' AS json), 'token-origen',
                        :user_id, 'Actor sintético', now(), now()
                    )
                    RETURNING id
                    """
                ),
                {
                    "operation_id": operaciones[1],
                    "company_id": empresa_id,
                    "batch_id": lote_id,
                    "snapshot_hash": "3" * 64,
                    "user_id": usuario_id,
                },
            )
            assert acceptance_origin_id is not None
            acceptance_child_id = await connection.scalar(
                text(
                    """
                    INSERT INTO lotes_duplicados_evidencias (
                        operacion_id, empresa_id, ambiente, lote_id, generacion,
                        formato, evidencia_id, snapshot_hash,
                        control_snapshot_json, aceptacion_id,
                        aceptada_por_usuario_id, aceptada_por_nombre,
                        aceptada_at, aceptacion_origen_generacion_id, created_at
                    ) VALUES (
                        :operation_id, :company_id, 'homologacion', :batch_id,
                        4, 'duplicados_relacion/1', 'v2.fisico.heredada',
                        :snapshot_hash, CAST('{}' AS json), 'token-origen',
                        :user_id, 'Actor sintético', now(), :origin_id, now()
                    )
                    RETURNING id
                    """
                ),
                {
                    "operation_id": operaciones[1],
                    "company_id": empresa_id,
                    "batch_id": lote_id,
                    "snapshot_hash": "4" * 64,
                    "user_id": usuario_id,
                    "origin_id": int(acceptance_origin_id),
                },
            )
            assert acceptance_child_id is not None
            block_id = await connection.scalar(
                text(
                    """
                    INSERT INTO lotes_duplicados_coincidencias (
                        generacion_id, operacion_id, empresa_id, ambiente,
                        lote_id, bloque_clave, clase, snapshot_json
                    ) VALUES (
                        :generation_id, :operation_id, :company_id,
                        'homologacion', :batch_id, 'bloque-principal',
                        'completa', CAST(:snapshot AS json)
                    )
                    RETURNING id
                    """
                ),
                {
                    "generation_id": generation_id,
                    "operation_id": operaciones[0],
                    "company_id": empresa_id,
                    "batch_id": lote_id,
                    "snapshot": json.dumps({"origen": "sintetico"}),
                },
            )
            assert block_id is not None
            cascade_block_id = await connection.scalar(
                text(
                    """
                    INSERT INTO lotes_duplicados_coincidencias (
                        generacion_id, operacion_id, empresa_id, ambiente,
                        lote_id, bloque_clave, clase, snapshot_json
                    ) VALUES (
                        :generation_id, :operation_id, :company_id,
                        'homologacion', :batch_id, 'bloque-cascade',
                        'completa', CAST('{}' AS json)
                    )
                    RETURNING id
                    """
                ),
                {
                    "generation_id": foreign_generation_id,
                    "operation_id": operaciones[1],
                    "company_id": empresa_id,
                    "batch_id": lote_id,
                },
            )
            assert cascade_block_id is not None
            cascade_member_id = await connection.scalar(
                text(
                    """
                    INSERT INTO lotes_duplicados_coincidencias_miembros (
                        bloque_id, lado, miembro_clave, grupo_id, ordinal,
                        relevancia, snapshot_json
                    ) VALUES (
                        :block_id, 'actual', 'miembro-cascade', :group_id,
                        0, 'actual', CAST('{}' AS json)
                    )
                    RETURNING id
                    """
                ),
                {
                    "block_id": int(cascade_block_id),
                    "group_id": grupo_id,
                },
            )
            assert cascade_member_id is not None
            for side, key, ordinal, relevance in (
                ("actual", "grupo-actual", 0, "actual"),
                ("anterior", "grupo-anterior", 0, "autorizado"),
            ):
                await connection.execute(
                    text(
                        """
                        INSERT INTO lotes_duplicados_coincidencias_miembros (
                            bloque_id, lado, miembro_clave, grupo_id, ordinal,
                            relevancia, snapshot_json
                        ) VALUES (
                            :block_id, :side, :key, :group_id, :ordinal,
                            :relevance, CAST(:snapshot AS json)
                        )
                        """
                    ),
                    {
                        "block_id": int(block_id),
                        "side": side,
                        "key": key,
                        "group_id": grupo_id,
                        "ordinal": ordinal,
                        "relevance": relevance,
                        "snapshot": json.dumps({"lado": side}),
                    },
                )
            await connection.execute(
                text(
                    """
                    UPDATE operaciones_idempotentes
                    SET duplicados_generacion_id = :generation_id
                    WHERE id = :operation_id
                    """
                ),
                {
                    "generation_id": generation_id,
                    "operation_id": operaciones[0],
                },
            )
            await connection.execute(
                text(
                    """
                    UPDATE operaciones_idempotentes
                    SET duplicados_generacion_id = :generation_id
                    WHERE id = :operation_id
                    """
                ),
                {
                    "generation_id": nullable_generation_id,
                    "operation_id": operaciones[1],
                },
            )

        attempt_id = await _crear_intento_incierto(
            session_factory,
            operacion_id=operaciones[0],
            grupo_id=grupo_id,
            generation_id=generation_id,
        )

        async with engine.begin() as connection:
            await _esperar_integrity_error(
                connection,
                text(
                    """
                    INSERT INTO lotes_duplicados_coincidencias (
                        generacion_id, operacion_id, empresa_id, ambiente,
                        lote_id, bloque_clave, clase, snapshot_json
                    ) VALUES (
                        :generation_id, :wrong_operation_id, :company_id,
                        'homologacion', :batch_id, 'scope-invalido',
                        'completa', CAST(:snapshot AS json)
                    )
                    """
                ),
                {
                    "generation_id": generation_id,
                    "wrong_operation_id": operaciones[1],
                    "company_id": empresa_id,
                    "batch_id": lote_id,
                    "snapshot": "{}",
                },
                constraint_name="fk_lotes_duplicados_coincidencias_generacion_scope",
            )
            await _esperar_integrity_error(
                connection,
                text(
                    """
                    UPDATE intentos_emision_fiscal
                    SET duplicados_generacion_id = :foreign_generation_id
                    WHERE id = :attempt_id
                    """
                ),
                {
                    "foreign_generation_id": foreign_generation_id,
                    "attempt_id": attempt_id,
                },
                constraint_name="fk_intento_duplicados_generacion_scope",
            )
            await _esperar_integrity_error(
                connection,
                text(
                    """
                    INSERT INTO lotes_duplicados_evidencias (
                        operacion_id, empresa_id, ambiente, lote_id, generacion,
                        formato, evidencia_id, snapshot_hash,
                        control_snapshot_json, aceptacion_id,
                        aceptada_por_nombre, created_at
                    ) VALUES (
                        :operation_id, :company_id, 'homologacion', :batch_id,
                        99, 'duplicados_relacion/1', 'v2.aceptacion-incompleta',
                        :snapshot_hash, CAST('{}' AS json), 'token-incompleto',
                        'Actor incompleto', now()
                    )
                    """
                ),
                {
                    "operation_id": operaciones[0],
                    "company_id": empresa_id,
                    "batch_id": lote_id,
                    "snapshot_hash": "9" * 64,
                },
                constraint_name="ck_lotes_duplicados_evidencias_aceptacion",
            )
            invalid_member = text(
                """
                INSERT INTO lotes_duplicados_coincidencias_miembros (
                    bloque_id, lado, miembro_clave, grupo_id, comprobante_id,
                    ordinal, relevancia, snapshot_json
                ) VALUES (
                    :block_id, 'actual', :key, :group_id, :voucher_id,
                    :ordinal, 'actual', CAST('{}' AS json)
                )
                """
            )
            for key, group_value, voucher_value, ordinal in (
                ("sin-entidad", None, None, 10),
                ("dos-entidades", grupo_id, 1, 11),
            ):
                await _esperar_integrity_error(
                    connection,
                    invalid_member,
                    {
                        "block_id": int(block_id),
                        "key": key,
                        "group_id": group_value,
                        "voucher_id": voucher_value,
                        "ordinal": ordinal,
                    },
                    constraint_name="ck_lotes_duplicados_miembros_entidad",
                )
            duplicate_member = text(
                """
                INSERT INTO lotes_duplicados_coincidencias_miembros (
                    bloque_id, lado, miembro_clave, grupo_id, ordinal,
                    relevancia, snapshot_json
                ) VALUES (
                    :block_id, :side, :key, :group_id, :ordinal,
                    :relevance, CAST('{}' AS json)
                )
                """
            )
            await _esperar_integrity_error(
                connection,
                duplicate_member,
                {
                    "block_id": int(block_id),
                    "side": "actual",
                    "key": "grupo-actual",
                    "group_id": grupo_id,
                    "ordinal": 12,
                    "relevance": "actual",
                },
                constraint_name="uq_lotes_duplicados_miembros_clave",
            )
            await _esperar_integrity_error(
                connection,
                duplicate_member,
                {
                    "block_id": int(block_id),
                    "side": "actual",
                    "key": "ordinal-repetido",
                    "group_id": grupo_id,
                    "ordinal": 0,
                    "relevance": "actual",
                },
                constraint_name="uq_lotes_duplicados_miembros_ordinal",
            )
            await _esperar_integrity_error(
                connection,
                text("DELETE FROM lotes_duplicados_evidencias WHERE id = :id"),
                {"id": generation_id},
                constraint_name="fk_intento_duplicados_generacion_scope",
            )
            await _esperar_integrity_error(
                connection,
                text("DELETE FROM lotes_duplicados_evidencias WHERE id = :id"),
                {"id": int(acceptance_origin_id)},
                constraint_name=acceptance_origin_constraint,
            )
            await connection.execute(
                text("DELETE FROM lotes_duplicados_evidencias WHERE id = :id"),
                {"id": foreign_generation_id},
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM lotes_duplicados_coincidencias "
                        "WHERE id = :id"
                    ),
                    {"id": int(cascade_block_id)},
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM "
                        "lotes_duplicados_coincidencias_miembros WHERE id = :id"
                    ),
                    {"id": int(cascade_member_id)},
                )
                == 0
            )
            await connection.execute(
                text("DELETE FROM lotes_duplicados_evidencias WHERE id = :id"),
                {"id": nullable_generation_id},
            )

        async with session_factory() as verifier:
            operation_pointer = await verifier.scalar(
                select(OperacionIdempotente.duplicados_generacion_id).where(
                    OperacionIdempotente.id == operaciones[1]
                )
            )
            attempt_generation = await verifier.scalar(
                select(IntentoEmisionFiscal.duplicados_generacion_id).where(
                    IntentoEmisionFiscal.id == attempt_id
                )
            )
            assert operation_pointer is None
            assert attempt_generation == generation_id
            assert await verifier.get(LoteDuplicadoEvidencia, generation_id) is not None
            assert (
                await verifier.scalar(
                    select(OperacionIdempotente.duplicados_generacion_id).where(
                        OperacionIdempotente.id == operaciones[0]
                    )
                )
                == generation_id
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_downgrade_con_evidencia_preserva_revision_y_datos(
    monkeypatch,
) -> None:
    """La guardia de downgrade falla antes de borrar evidencia v2 durable."""
    database_url = require_disposable_postgres_url(
        purpose="downgrade fail-closed PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        scenario = await _crear_evidencia_aceptada(
            session_factory,
            monkeypatch,
            sufijo="downgrade",
        )
        generation_id = int(scenario["generation_id"])
        operation_id = int(scenario["operaciones"][0])
        group_id = int(scenario["grupos"][0])
        await engine.dispose()
        _run_alembic("downgrade", REVISION_DUPLICADOS_V2, database_url)
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=False,
        )
        async with session_factory() as verifier:
            before = await _snapshot_downgrade_pf13(
                verifier,
                operacion_id=operation_id,
                grupo_id=group_id,
            )
        assert len(before["generations"]) >= 1
        assert len(before["blocks"]) >= 1
        assert len(before["members"]) >= 2
        assert before["operation"][3] == generation_id
        assert before["group"][-1] == operation_id
        constraints_before = set(await _catalogo_constraints_pf13(engine))
        indices_before = await _indices_pf13(engine)
        await engine.dispose()

        output = _run_alembic(
            "downgrade",
            REVISION_ANTERIOR,
            database_url,
            expected_success=False,
        )
        assert "existe evidencia de duplicados v2" in output

        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
            autoflush=False,
        )
        async with session_factory() as verifier:
            version = await verifier.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            after = await _snapshot_downgrade_pf13(
                verifier,
                operacion_id=operation_id,
                grupo_id=group_id,
            )
        assert version == REVISION_DUPLICADOS_V2
        assert after == before
        assert set(await _catalogo_constraints_pf13(engine)) == constraints_before
        assert await _indices_pf13(engine) == indices_before
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_falla_post_publicacion_revierte_toda_la_raiz(
    monkeypatch,
) -> None:
    """Una falla tras publicar y flush revierte coordinación, relación y reserva."""
    database_url = require_disposable_postgres_url(purpose="rollback atómico PF-13")
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        monkeypatch.setattr(settings, "arca_env", "homologacion")
        (
            empresa_id,
            lotes,
            grupos,
            operaciones,
        ) = await _crear_escenario_dos_lotes_coincidentes(session_factory)
        await _marcar_testigo_autorizado(
            session_factory,
            lote_id=lotes[1],
            grupo_id=grupos[1],
        )
        await _asignar_usuario_sintetico(
            session_factory,
            empresa_id=empresa_id,
            operacion_ids=operaciones,
            sufijo="rollback",
        )
        async with session_factory() as failing_session:
            service = DuplicadosLotesService(failing_session)
            publish_original = service._publicar_generacion

            async def publicar_y_fallar(**kwargs):
                await publish_original(**kwargs)
                await failing_session.flush()
                raise RuntimeError("falla sintética posterior a publicación y flush")

            service._publicar_generacion = publicar_y_fallar
            with pytest.raises(RuntimeError, match="posterior a publicación"):
                await asyncio.wait_for(
                    service.evaluar_y_reservar(
                        operacion_id=operaciones[0],
                        lote_id=lotes[0],
                        empresa_id=empresa_id,
                        estados={"validado"},
                        grupo_ids=None,
                        aceptacion_recibida=None,
                        solicitante_nombre="Operador sintético",
                        reservar=True,
                        ambiente="homologacion",
                    ),
                    timeout=TIMEOUT_SECONDS,
                )
            assert not failing_session.in_transaction()
            async with engine.begin() as verification_connection:
                await verification_connection.execute(
                    text("SET LOCAL lock_timeout = '2s'")
                )
                observed_revision = await verification_connection.scalar(
                    select(LoteDuplicadosCoordinacion.revision)
                    .where(
                        LoteDuplicadosCoordinacion.empresa_id == empresa_id,
                        LoteDuplicadosCoordinacion.ambiente == "homologacion",
                    )
                    .with_for_update()
                )
                assert observed_revision == 0
                assert (
                    await verification_connection.scalar(
                        text("SELECT count(*) FROM lotes_duplicados_evidencias")
                    )
                    == 0
                )
                assert (
                    await verification_connection.scalar(
                        text(
                            "SELECT count(*) FROM lotes_comprobantes_grupos "
                            "WHERE duplicados_reserva_operacion_id IS NOT NULL"
                        )
                    )
                    == 0
                )
                operation_state = (
                    await verification_connection.execute(
                        text(
                            "SELECT control_duplicados_json, "
                            "duplicados_generacion_id, duplicados_version "
                            "FROM operaciones_idempotentes WHERE id = :id"
                        ),
                        {"id": operaciones[0]},
                    )
                ).one()
                assert tuple(operation_state) == (None, None, None)

        async with session_factory() as verifier:
            operation = await verifier.get(OperacionIdempotente, operaciones[0])
            revision = await verifier.scalar(
                select(LoteDuplicadosCoordinacion.revision).where(
                    LoteDuplicadosCoordinacion.empresa_id == empresa_id,
                    LoteDuplicadosCoordinacion.ambiente == "homologacion",
                )
            )
            owners = list(
                (
                    await verifier.scalars(
                        select(
                            LoteComprobanteGrupo.duplicados_reserva_operacion_id
                        ).where(LoteComprobanteGrupo.id.in_(grupos))
                    )
                ).all()
            )
            assert operation is not None
            assert operation.control_duplicados_json is None
            assert operation.duplicados_generacion_id is None
            assert operation.duplicados_version is None
            assert revision == 0
            assert owners == [None, None]
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(LoteDuplicadoEvidencia)
                )
                == 0
            )
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(LoteDuplicadoCoincidencia)
                )
                == 0
            )
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(LoteDuplicadoCoincidenciaMiembro)
                )
                == 0
            )

        async with session_factory() as recovery_session:
            recovery = DuplicadosLotesService(recovery_session)
            _, token, accepted = await asyncio.wait_for(
                recovery.evaluar_y_reservar(
                    operacion_id=operaciones[0],
                    lote_id=lotes[0],
                    empresa_id=empresa_id,
                    estados={"validado"},
                    grupo_ids=None,
                    aceptacion_recibida=None,
                    solicitante_nombre="Operador sintético",
                    reservar=True,
                    ambiente="homologacion",
                ),
                timeout=TIMEOUT_SECONDS,
            )
            assert token is not None
            assert accepted is False
            _, same_token, accepted = await asyncio.wait_for(
                recovery.evaluar_y_reservar(
                    operacion_id=operaciones[0],
                    lote_id=lotes[0],
                    empresa_id=empresa_id,
                    estados={"validado"},
                    grupo_ids=None,
                    aceptacion_recibida=token,
                    solicitante_nombre="Operador sintético",
                    reservar=True,
                    ambiente="homologacion",
                ),
                timeout=TIMEOUT_SECONDS,
            )
            assert same_token == token
            assert accepted is True
        async with session_factory() as verifier:
            assert (
                await verifier.scalar(
                    select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                        LoteComprobanteGrupo.id == grupos[0]
                    )
                )
                == operaciones[0]
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_testigo_tardio_invalida_aceptacion_en_preflight(
    monkeypatch,
) -> None:
    """Un commit tardío no hereda la aceptación previa ni alcanza un intento fiscal."""
    database_url = require_disposable_postgres_url(
        purpose="testigo tardío y aceptación PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        scenario = await _crear_evidencia_aceptada(
            session_factory,
            monkeypatch,
            sufijo="testigo-tardio",
        )
        empresa_id = int(scenario["empresa_id"])
        lote_id = int(scenario["lotes"][0])
        operation_id = int(scenario["operaciones"][0])
        old_generation_id = int(scenario["generation_id"])
        old_token = str(scenario["token"])
        late_group_id = await _crear_testigo_tardio(
            session_factory,
            empresa_id=empresa_id,
            grupo_modelo_id=int(scenario["grupos"][1]),
        )

        async with session_factory() as preflight_session:
            with pytest.raises(DuplicadosLotePreflightCambioError):
                await asyncio.wait_for(
                    DuplicadosLotesService(preflight_session).revalidar_operacion_lote(
                        operacion_id=operation_id,
                        lote_id=lote_id,
                        empresa_id=empresa_id,
                    ),
                    timeout=TIMEOUT_SECONDS,
                )
            await preflight_session.rollback()

        async with session_factory() as refresh_session:
            control, new_token, accepted = await asyncio.wait_for(
                DuplicadosLotesService(refresh_session).evaluar_y_reservar(
                    operacion_id=operation_id,
                    lote_id=lote_id,
                    empresa_id=empresa_id,
                    estados={"validado"},
                    grupo_ids=None,
                    aceptacion_recibida=old_token,
                    solicitante_nombre="Operador sintético",
                    reservar=False,
                    ambiente="homologacion",
                ),
                timeout=TIMEOUT_SECONDS,
            )
            assert control["estado"] == "requiere_confirmacion"
            assert new_token is not None
            assert new_token != old_token
            assert accepted is False

        async with session_factory() as verifier:
            operation = await verifier.get(OperacionIdempotente, operation_id)
            old_generation = await verifier.get(
                LoteDuplicadoEvidencia, old_generation_id
            )
            assert operation is not None
            assert old_generation is not None
            new_generation = await verifier.get(
                LoteDuplicadoEvidencia,
                int(operation.duplicados_generacion_id),
            )
            assert new_generation is not None
            assert int(new_generation.id) != old_generation_id
            assert old_generation.aceptada_at is not None
            assert new_generation.aceptacion_id == new_token
            assert new_generation.aceptada_por_usuario_id is None
            assert new_generation.aceptada_por_nombre is None
            assert new_generation.aceptada_at is None
            assert new_generation.aceptacion_origen_generacion_id is None
            late_member = await verifier.scalar(
                select(LoteDuplicadoCoincidenciaMiembro.id)
                .join(
                    LoteDuplicadoCoincidencia,
                    LoteDuplicadoCoincidencia.id
                    == LoteDuplicadoCoincidenciaMiembro.bloque_id,
                )
                .where(
                    LoteDuplicadoCoincidencia.generacion_id == new_generation.id,
                    LoteDuplicadoCoincidenciaMiembro.grupo_id == late_group_id,
                    LoteDuplicadoCoincidenciaMiembro.lado == "anterior",
                )
            )
            assert late_member is not None
            assert (
                await verifier.scalar(
                    select(func.count())
                    .select_from(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.operacion_id == operation_id)
                )
                == 0
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_incierto_conserva_owner_y_retry_no_lo_transfiere(
    monkeypatch,
) -> None:
    """Un intento incierto conserva su generación y su reserva ante otra key."""
    database_url = require_disposable_postgres_url(
        purpose="incertidumbre y retry PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        monkeypatch.setattr(settings, "arca_env", "homologacion")
        (
            empresa_id,
            lote_id,
            grupo_id,
            operaciones,
        ) = await _crear_escenario_coordinacion(session_factory)
        async with session_factory() as owner_session:
            control, token, accepted = await DuplicadosLotesService(
                owner_session
            ).evaluar_y_reservar(
                operacion_id=operaciones[0],
                lote_id=lote_id,
                empresa_id=empresa_id,
                estados={"validado"},
                grupo_ids=None,
                aceptacion_recibida=None,
                solicitante_nombre="Primera persona",
                reservar=True,
                ambiente="homologacion",
            )
            assert control["bloqueo_operacion_ajena"] is None
            assert token is None
            assert accepted is False
            operation = await owner_session.get(OperacionIdempotente, operaciones[0])
            assert operation is not None
            generation_id = int(operation.duplicados_generacion_id)
        attempt_id = await _crear_intento_incierto(
            session_factory,
            operacion_id=operaciones[0],
            grupo_id=grupo_id,
            generation_id=generation_id,
        )
        async with session_factory() as setup_session:
            await setup_session.execute(
                update(OperacionIdempotente)
                .where(OperacionIdempotente.id == operaciones[1])
                .values(
                    tipo_operacion="reintentar_fallidos_lote",
                    operacion_raiz_id=operaciones[0],
                )
            )
            await setup_session.commit()

        async with session_factory() as competitor_session:
            with pytest.raises(DuplicadosLoteError) as caught:
                await asyncio.wait_for(
                    DuplicadosLotesService(competitor_session).evaluar_y_reservar(
                        operacion_id=operaciones[1],
                        lote_id=lote_id,
                        empresa_id=empresa_id,
                        estados={"validado"},
                        grupo_ids=[grupo_id],
                        aceptacion_recibida=None,
                        solicitante_nombre="Segunda persona",
                        reservar=True,
                        ambiente="homologacion",
                    ),
                    timeout=TIMEOUT_SECONDS,
                )
            assert caught.value.categoria == "duplicado_operacion_en_curso"
            await competitor_session.rollback()

        async with session_factory() as verifier:
            group = await verifier.get(LoteComprobanteGrupo, grupo_id)
            attempt = await verifier.get(IntentoEmisionFiscal, attempt_id)
            root_operation = await verifier.get(OperacionIdempotente, operaciones[0])
            retry_operation = await verifier.get(OperacionIdempotente, operaciones[1])
            assert group is not None
            assert attempt is not None
            assert root_operation is not None
            assert retry_operation is not None
            assert group.duplicados_reserva_operacion_id == operaciones[0]
            assert root_operation.duplicados_generacion_id == generation_id
            assert retry_operation.duplicados_generacion_id is None
            assert attempt.estado == "requiere_reconciliacion"
            assert attempt.duplicados_generacion_id == generation_id
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(IntentoEmisionFiscal)
                )
                == 1
            )

        async with session_factory() as replay_session:
            replay, _, _ = await asyncio.wait_for(
                DuplicadosLotesService(replay_session).evaluar_y_reservar(
                    operacion_id=operaciones[0],
                    lote_id=lote_id,
                    empresa_id=empresa_id,
                    estados={"validado"},
                    grupo_ids=[grupo_id],
                    aceptacion_recibida=None,
                    solicitante_nombre="Primera persona",
                    reservar=True,
                    ambiente="homologacion",
                ),
                timeout=TIMEOUT_SECONDS,
            )
            assert replay["bloqueo_operacion_ajena"] is None
        async with session_factory() as verifier:
            root_generation_id = await verifier.scalar(
                select(OperacionIdempotente.duplicados_generacion_id).where(
                    OperacionIdempotente.id == operaciones[0]
                )
            )
            assert (
                await verifier.scalar(
                    select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                        LoteComprobanteGrupo.id == grupo_id
                    )
                )
                == operaciones[0]
            )
            assert (
                await verifier.scalar(
                    select(IntentoEmisionFiscal.duplicados_generacion_id).where(
                        IntentoEmisionFiscal.id == attempt_id
                    )
                )
                == generation_id
            )
            assert root_generation_id == generation_id
            assert (
                await verifier.scalar(
                    select(func.count())
                    .select_from(LoteDuplicadoEvidencia)
                    .where(LoteDuplicadoEvidencia.operacion_id == operaciones[0])
                )
                == 1
            )
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_incertidumbre_integral_bloquea_retry_y_envio(
    monkeypatch,
) -> None:
    """El cierre incierto real inmoviliza todo antes de otro intento fiscal."""
    database_url = require_disposable_postgres_url(
        purpose="incertidumbre integral y bloqueo de retry PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        monkeypatch.setattr(settings, "arca_env", "homologacion")
        (
            empresa_id,
            lote_id,
            grupo_id,
            operaciones,
        ) = await _crear_escenario_coordinacion(session_factory)
        async with session_factory() as owner_session:
            await DuplicadosLotesService(owner_session).evaluar_y_reservar(
                operacion_id=operaciones[0],
                lote_id=lote_id,
                empresa_id=empresa_id,
                estados={"validado"},
                grupo_ids=[grupo_id],
                aceptacion_recibida=None,
                solicitante_nombre="Persona propietaria",
                reservar=True,
                ambiente="homologacion",
            )
            operation = await owner_session.get(OperacionIdempotente, operaciones[0])
            assert operation is not None
            generation_id = int(operation.duplicados_generacion_id)

        attempt_id = await _crear_intento_incierto(
            session_factory,
            operacion_id=operaciones[0],
            grupo_id=grupo_id,
            generation_id=generation_id,
        )
        async with session_factory() as closure_session:
            service = LoteComprobantesService(closure_session)
            closure_session.add(
                LoteComprobanteFila(
                    lote_id=lote_id,
                    grupo_id=grupo_id,
                    fila_excel=2,
                    comprobante_ref="SINTETICO-1",
                    estado="validado",
                    datos_json={},
                    mensajes_json=["Fila fiscal sintética validada."],
                )
            )
            await closure_session.flush()
            material_rece = await service.calcular_material_idempotente_grupos(
                lote_id=lote_id,
                empresa_id=empresa_id,
                estados={"validado"},
                grupo_ids=[grupo_id],
            )
            lote = await closure_session.get(LoteComprobante, lote_id)
            assert lote is not None
            lote.metadata_json = {
                "operacion_idempotente_id": operaciones[0],
                "pf19b_rece_material": material_rece,
            }
            await closure_session.commit()
            await service._cerrar_lote_por_incertidumbre_post_arca(
                lote_id=lote_id,
                empresa_id=empresa_id,
                operacion_id=operaciones[0],
                grupos_seleccionados_ids={grupo_id},
                grupos_inmovilizados_ids={grupo_id},
            )
            await closure_session.commit()

        async with session_factory() as setup_retry_session:
            await setup_retry_session.execute(
                update(OperacionIdempotente)
                .where(OperacionIdempotente.id == operaciones[1])
                .values(
                    tipo_operacion="reintentar_fallidos_lote",
                    operacion_raiz_id=operaciones[0],
                )
            )
            await setup_retry_session.commit()

        emisiones = 0

        async def fail_emitir(*_args, **_kwargs):
            nonlocal emisiones
            emisiones += 1
            raise AssertionError("Un retry incierto no debe alcanzar ARCA")

        async with session_factory() as retry_session:
            retry_service = LoteComprobantesService(retry_session)
            retry_service.facturacion_service._emitir_comprobante_locked = fail_emitir
            with pytest.raises(LoteComprobanteError, match="reconciliación técnica"):
                await retry_service.reintentar_grupos_fallidos(
                    lote_id=lote_id,
                    empresa_id=empresa_id,
                    usuario_id=None,
                    grupo_ids=[grupo_id],
                    operacion_id=operaciones[1],
                    material_rece_confirmado=material_rece,
                )
            await retry_session.rollback()

        async with session_factory() as verifier:
            lote = await verifier.get(LoteComprobante, lote_id)
            group = await verifier.get(LoteComprobanteGrupo, grupo_id)
            root_operation = await verifier.get(OperacionIdempotente, operaciones[0])
            retry_operation = await verifier.get(OperacionIdempotente, operaciones[1])
            attempt = await verifier.get(IntentoEmisionFiscal, attempt_id)
            row = await verifier.scalar(
                select(LoteComprobanteFila).where(
                    LoteComprobanteFila.grupo_id == grupo_id
                )
            )
            assert lote is not None
            assert group is not None
            assert root_operation is not None
            assert retry_operation is not None
            assert attempt is not None
            assert row is not None
            guard = await verifier.get(
                PuntoVentaGuardaEmisionRece, int(attempt.guarda_rece_id)
            )
            generation = await verifier.get(LoteDuplicadoEvidencia, generation_id)
            assert guard is not None
            assert generation is not None
            assert lote.estado == "requiere_reconciliacion"
            assert lote.metadata_json["operacion_idempotente_id"] == operaciones[0]
            assert lote.metadata_json["pf19b_rece_material"] == material_rece
            assert group.estado == "requiere_reconciliacion"
            assert group.duplicados_reserva_operacion_id == operaciones[0]
            assert row.estado == "requiere_reconciliacion"
            assert root_operation.estado == "requiere_reconciliacion"
            assert root_operation.duplicados_generacion_id == generation_id
            assert retry_operation.estado == "en_proceso"
            assert retry_operation.operacion_raiz_id == operaciones[0]
            assert retry_operation.duplicados_generacion_id is None
            assert attempt.estado == "requiere_reconciliacion"
            assert attempt.operacion_id == operaciones[0]
            assert attempt.duplicados_generacion_id == generation_id
            assert guard.fase == "requiere_reconciliacion"
            assert guard.operacion_id == operaciones[0]
            assert generation.operacion_id == operaciones[0]
            assert generation.lote_id == lote_id
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(IntentoEmisionFiscal)
                )
                == 1
            )
            assert (
                await verifier.scalar(
                    select(func.count()).select_from(LoteDuplicadoEvidencia)
                )
                == 1
            )
            assert emisiones == 0
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("scope_kind", ["otro_ambiente", "otra_empresa"])
async def test_postgresql_pf13_scope_independiente_no_espera_lock_ajeno(
    scope_kind: str,
) -> None:
    """Otro ambiente o emisor completa mientras el coordinador base sigue tomado."""
    database_url = require_disposable_postgres_url(
        purpose=f"independencia de scope PF-13: {scope_kind}"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        base_empresa_id, _, base_group_id, _ = await _crear_escenario_coordinacion(
            session_factory
        )
        if scope_kind == "otro_ambiente":
            secondary = await _crear_scope_adicional(
                session_factory,
                ambiente="produccion",
                semilla=21,
                empresa_id=base_empresa_id,
            )
            secondary_environment = "produccion"
        else:
            secondary = await _crear_scope_adicional(
                session_factory,
                ambiente="homologacion",
                semilla=22,
            )
            secondary_environment = "homologacion"
        (
            secondary_empresa,
            secondary_lote,
            secondary_group,
            secondary_operation,
        ) = secondary
        first_connection = await engine.connect()
        first_transaction = await first_connection.begin()
        task = None
        try:
            await first_connection.execute(
                select(LoteDuplicadosCoordinacion)
                .where(
                    LoteDuplicadosCoordinacion.empresa_id == base_empresa_id,
                    LoteDuplicadosCoordinacion.ambiente == "homologacion",
                )
                .with_for_update()
            )

            async def evaluar_scope_secundario() -> None:
                async with session_factory() as second_session:
                    control, token, accepted = await DuplicadosLotesService(
                        second_session
                    ).evaluar_y_reservar(
                        operacion_id=secondary_operation,
                        lote_id=secondary_lote,
                        empresa_id=secondary_empresa,
                        estados={"validado"},
                        grupo_ids=None,
                        aceptacion_recibida=None,
                        solicitante_nombre="Scope independiente",
                        reservar=True,
                        ambiente=secondary_environment,
                    )
                    assert control["bloqueo_operacion_ajena"] is None
                    assert token is None
                    assert accepted is False

            task = asyncio.create_task(evaluar_scope_secundario())
            await asyncio.wait_for(task, timeout=TIMEOUT_SECONDS)

            async with session_factory() as verifier:
                base_revision = await verifier.scalar(
                    select(LoteDuplicadosCoordinacion.revision).where(
                        LoteDuplicadosCoordinacion.empresa_id == base_empresa_id,
                        LoteDuplicadosCoordinacion.ambiente == "homologacion",
                    )
                )
                secondary_revision = await verifier.scalar(
                    select(LoteDuplicadosCoordinacion.revision).where(
                        LoteDuplicadosCoordinacion.empresa_id == secondary_empresa,
                        LoteDuplicadosCoordinacion.ambiente == secondary_environment,
                    )
                )
                base_owner = await verifier.scalar(
                    select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                        LoteComprobanteGrupo.id == base_group_id
                    )
                )
                secondary_owner = await verifier.scalar(
                    select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                        LoteComprobanteGrupo.id == secondary_group
                    )
                )
                assert base_revision == 0
                assert secondary_revision == 1
                assert base_owner is None
                assert secondary_owner == secondary_operation
        finally:
            if task is not None:
                await _cancelar_tarea(task)
            if first_transaction.is_active:
                await first_transaction.rollback()
            await first_connection.close()
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("historical_lote_count", [8, 16])
async def test_postgresql_pf13_historia_pagina_operaciones_en_ventanas(
    historical_lote_count: int,
    monkeypatch,
) -> None:
    database_url = require_disposable_postgres_url(purpose="ventanas históricas PF-13")
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, autoflush=False
    )
    try:
        (
            empresa_id,
            lotes,
            grupos,
            _operations,
        ) = await _crear_escenario_dos_lotes_coincidentes(session_factory)
        await _marcar_testigo_autorizado(
            session_factory, lote_id=lotes[1], grupo_id=grupos[1]
        )
        async with session_factory() as session:
            previous = await session.get(LoteComprobanteGrupo, grupos[1])
            assert previous is not None
            selection = DuplicadosLotesService._seleccion_material([previous])
            root_one = OperacionIdempotente(
                empresa_id=empresa_id,
                idempotency_key="pf13-pg-window-root-1",
                tipo_operacion="procesar_lote",
                payload_hash="1" * 64,
                estado="finalizado",
                lote_id=lotes[1],
                duplicados_version="duplicados_lotes/v2",
                control_duplicados_json={"seleccion_original": selection},
            )
            root_two = OperacionIdempotente(
                empresa_id=empresa_id,
                idempotency_key="pf13-pg-window-root-2",
                tipo_operacion="procesar_lote",
                payload_hash="2" * 64,
                estado="finalizado",
                lote_id=lotes[1],
                duplicados_version="duplicados_lotes/v2",
                control_duplicados_json={"seleccion_original": selection},
            )
            session.add_all([root_one, root_two])
            await session.flush()
            session.add(
                OperacionIdempotente(
                    empresa_id=empresa_id,
                    idempotency_key="pf13-pg-window-continuation",
                    tipo_operacion="procesar_lote",
                    payload_hash="3" * 64,
                    estado="finalizado",
                    lote_id=lotes[1],
                    operacion_raiz_id=int(root_one.id),
                    duplicados_version="duplicados_lotes/v2",
                    control_duplicados_json={"seleccion_original": selection},
                )
            )
            current = await session.get(LoteComprobanteGrupo, grupos[0])
            assert current is not None
            for index in range(historical_lote_count - 1):
                extra_lote = LoteComprobante(
                    empresa_id=empresa_id,
                    nombre_archivo=(
                        f"pf13-pg-window-{historical_lote_count}-extra-{index}.xlsx"
                    ),
                    archivo_hash=f"{historical_lote_count * 100 + index:064d}",
                    estado="completado",
                    total_grupos=1,
                    grupos_emitidos=1,
                )
                session.add(extra_lote)
                await session.flush()
                session.add(
                    LoteComprobanteGrupo(
                        lote_id=int(extra_lote.id),
                        empresa_id=empresa_id,
                        comprobante_ref=f"EXTRA-{index}",
                        orden=0,
                        estado="autorizado",
                        tipo_comprobante=current.tipo_comprobante,
                        punto_venta_id=current.punto_venta_id,
                        punto_venta_numero=current.punto_venta_numero,
                        ambiente=current.ambiente,
                        punto_venta_elegibilidad_revision_id=(
                            current.punto_venta_elegibilidad_revision_id
                        ),
                        punto_venta_revision_fiscal=(
                            current.punto_venta_revision_fiscal
                        ),
                        fecha_emision_normalizada=(current.fecha_emision_normalizada),
                        moneda_duplicados=current.moneda_duplicados,
                        cotizacion_duplicados=current.cotizacion_duplicados,
                        total_estimado=current.total_estimado,
                        total_centavos=current.total_centavos,
                        duplicados_version=current.duplicados_version,
                        duplicados_cobertura=current.duplicados_cobertura,
                        huella_fiscal_completa=current.huella_fiscal_completa,
                        identidad_nombre_hash=current.identidad_nombre_hash,
                        identidad_documento_hash=current.identidad_documento_hash,
                    )
                )
            await session.commit()
            service = DuplicadosLotesService(session)
            baseline = await service.calcular_control(
                lote_id=lotes[0],
                empresa_id=empresa_id,
                estados={"validado"},
                incluir_interno=True,
            )
            monkeypatch.setattr(duplicados_lotes_module, "HISTORICAL_READ_WINDOW", 1)
            session.expunge_all()
            peaks = {
                LoteComprobante: 0,
                LoteComprobanteGrupo: 0,
                OperacionIdempotente: 0,
                IntentoEmisionFiscal: 0,
            }

            def observe_load(sync_session, _instance):
                for model in peaks:
                    peaks[model] = max(
                        peaks[model],
                        sum(
                            isinstance(item, model)
                            for item in sync_session.identity_map.values()
                        ),
                    )

            event.listen(session.sync_session, "loaded_as_persistent", observe_load)
            try:
                windowed = await service.calcular_control(
                    lote_id=lotes[0],
                    empresa_id=empresa_id,
                    estados={"validado"},
                    incluir_interno=True,
                )
            finally:
                event.remove(session.sync_session, "loaded_as_persistent", observe_load)
            assert service._publicable(windowed) == service._publicable(baseline)
            assert service._relacion_canonica(windowed, snapshot=True) == (
                service._relacion_canonica(baseline, snapshot=True)
            )
            assert windowed["evidencia_id"] == baseline["evidencia_id"]
            assert (
                len(
                    [
                        item
                        for item in windowed["antecedentes_resumen"]
                        if item["lote_id"] == lotes[1]
                    ]
                )
                == 2
            )
            assert peaks[OperacionIdempotente] == 0
            assert peaks[IntentoEmisionFiscal] == 0
            assert peaks[LoteComprobante] <= 2
            assert peaks[LoteComprobanteGrupo] <= 4
            baseline_page = await service._pagina_relacion_viva(
                baseline, offset=0, limit=100
            )
            windowed_page = await service._pagina_relacion_viva(
                windowed, offset=0, limit=100
            )
            assert windowed_page == baseline_page
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf13_pagina_viva_acota_cursor_heap_y_binds(
    monkeypatch,
) -> None:
    database_url = require_disposable_postgres_url(
        purpose="paginación viva acotada PF-13"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, autoflush=False
    )
    try:
        (
            empresa_id,
            lotes,
            _groups,
            operations,
        ) = await _crear_escenario_dos_lotes_coincidentes(session_factory)
        async with session_factory() as session:
            service = DuplicadosLotesService(session)

            def member(group_id: int, side: str) -> dict:
                return {
                    "lado": side,
                    "miembro_clave": f"{side}-{group_id}",
                    "grupo_id": group_id,
                    "comprobante_id": None,
                    "nombre_hash": None if group_id % 7 == 0 else f"n-{group_id % 5}",
                    "documento_hash": "d" * 64,
                    "ordinal": None,
                    "relevancia": "actual" if side == "actual" else "autorizado",
                    "snapshot": {
                        "decision": {"grupo_id": group_id},
                        "presentacion": {
                            "grupo_id": group_id if side == "actual" else None,
                            "grupo_anterior_id": group_id
                            if side == "anterior"
                            else None,
                            "lote_anterior_id": 90 if side == "anterior" else None,
                            "comprobante_ref": f"G-{group_id}",
                            "comprobante_anterior_ref": f"A-{group_id}",
                            "importe": "1.00",
                            "moneda": "PES",
                            "cotizacion": "1",
                            "estado_grupo_anterior": "autorizado",
                            "operacion_anterior_ref": None,
                            "solicitantes": [],
                            "solicitud_emision_at": None,
                            "solicitud_arca_at": None,
                            "resultado_fiscal_at": None,
                            "hora_confiable": False,
                        },
                    },
                }

            members = [member(1000 + index, "actual") for index in range(121)]
            members.extend(member(2000 + index, "anterior") for index in range(122))
            block = {
                "bloque_clave": "pg-buffer-profundo",
                "clase": "parcial_documento",
                "antecedente_clave": "pg-raiz",
                "snapshot": {
                    "origen": "lote",
                    "tipo_coincidencia": "historica_parcial_receptor",
                    "campos_coincidentes": ["documento"],
                    "lote_anterior_id": 90,
                    "multiplicidad_total": None,
                },
                "miembros": {
                    (item["lado"], item["miembro_clave"]): item for item in members
                },
            }
            control = {"_bloques": {block["bloque_clave"]: block}}
            generation = LoteDuplicadoEvidencia(
                operacion_id=operations[0],
                empresa_id=empresa_id,
                ambiente="homologacion",
                lote_id=lotes[0],
                generacion=1,
                formato="duplicados_relacion/1",
                evidencia_id="v2.pg-buffer-profundo",
                snapshot_hash="4" * 64,
                control_snapshot_json={
                    "manifiesto": {"bloques": 1, "miembros": len(members)}
                },
            )
            session.add(generation)
            await session.flush()
            await service._insertar_relacion(generation=generation, control=control)
            active = 0
            max_active = 0
            max_heap = 0
            bind_counts = []
            original_stream = session.stream
            original_push = duplicados_lotes_module.heapq.heappush

            class Cursor:
                def __init__(self, result):
                    nonlocal active, max_active
                    self.result = result
                    active += 1
                    max_active = max(max_active, active)

                def mappings(self):
                    return self.result.mappings()

                async def close(self):
                    nonlocal active
                    await self.result.close()
                    active -= 1

            async def observe_stream(statement, *args, **kwargs):
                return Cursor(await original_stream(statement, *args, **kwargs))

            def observe_push(heap, item):
                nonlocal max_heap
                original_push(heap, item)
                max_heap = max(max_heap, len(heap))

            def observe_binds(_conn, _cursor, statement, parameters, _context, _many):
                if "pg_buffer_profundo" in statement or "pg-buffer-profundo" in str(
                    parameters
                ):
                    bind_counts.append(len(parameters))

            event.listen(engine.sync_engine, "before_cursor_execute", observe_binds)
            monkeypatch.setattr(session, "stream", observe_stream)
            monkeypatch.setattr(duplicados_lotes_module.heapq, "heappush", observe_push)
            try:
                items, total = await service._pagina_relacion_viva(
                    control,
                    offset=service._total_bloque_compacto(block) - 3,
                    limit=3,
                )
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", observe_binds)
            assert total > 10000
            assert len(items) == 3
            assert active == 0
            assert max_active == 1
            assert max_heap <= service._live_member_buffer()
            assert bind_counts
            assert max(bind_counts) <= duplicados_lotes_module.READ_PARAMETER_BUFFER
            durable_items, durable_total = await service._pagina_generacion(
                generation,
                offset=service._total_bloque_compacto(block) - 3,
                limit=3,
            )
            assert durable_total == total
            assert durable_items == items
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("tampering", ["bloque", "miembro"])
async def test_postgresql_pf13_get_valida_integridad_antes_de_pagina(
    tampering: str,
    monkeypatch,
) -> None:
    database_url = require_disposable_postgres_url(
        purpose=f"integridad GET durable PF-13: {tampering}"
    )
    await _reset_schema(database_url)
    _run_alembic("upgrade", "head", database_url)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, autoflush=False
    )
    try:
        scenario = await _crear_evidencia_aceptada(
            session_factory, monkeypatch, sufijo=f"get-{tampering}"
        )
        async with session_factory() as session:
            generation = await session.get(
                LoteDuplicadoEvidencia, scenario["generation_id"]
            )
            assert generation is not None
            service = DuplicadosLotesService(session)
            healthy = await service.obtener_detalle(
                lote_id=scenario["lotes"][0],
                empresa_id=scenario["empresa_id"],
                evidencia_id=generation.evidencia_id,
                page=1,
                per_page=10,
            )
            assert healthy[2] >= 1
            block = await session.scalar(
                select(LoteDuplicadoCoincidencia)
                .where(LoteDuplicadoCoincidencia.generacion_id == generation.id)
                .limit(1)
            )
            assert block is not None
            if tampering == "bloque":
                block.snapshot_json = {**block.snapshot_json, "alterado": True}
            else:
                member_row = await session.scalar(
                    select(LoteDuplicadoCoincidenciaMiembro)
                    .where(LoteDuplicadoCoincidenciaMiembro.bloque_id == block.id)
                    .limit(1)
                )
                assert member_row is not None
                member_row.snapshot_json = {
                    **member_row.snapshot_json,
                    "alterado": True,
                }
            await session.flush()
            page_calls = 0

            async def prohibit_page(*_args, **_kwargs):
                nonlocal page_calls
                page_calls += 1
                raise AssertionError("no debe paginar evidencia corrupta")

            monkeypatch.setattr(service, "_pagina_generacion", prohibit_page)
            with pytest.raises(DuplicadosLoteError):
                await service.obtener_detalle(
                    lote_id=scenario["lotes"][0],
                    empresa_id=scenario["empresa_id"],
                    evidencia_id=generation.evidencia_id,
                    page=1,
                    per_page=10,
                )
            assert page_calls == 0
    finally:
        await engine.dispose()
