"""Integración PostgreSQL desechable para el journal legacy PF-19C."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.idempotencia_fiscal import (
    IntentoEmisionFiscal,
    ResolucionLegacyPF19Journal,
)
from app.services.resolucion_legacy_pf19_service import (
    ConsultaComprobanteLegacyPF19,
    SolicitudPlanLegacyPF19,
    aplicar_resolucion_legacy_pf19,
    planificar_resolucion_legacy_pf19,
)

from tests.integration.test_integridad_fiscal_postgresql import (
    _alembic_version,
    _crear_contexto_sintetico,
    _insertar_intento,
    _postgres_url,
    _reset_schema,
    _run_alembic,
)
from tests.test_pf19_legacy_resolution import _sembrar, _solicitud_apply


REVISION_ELEGIBILIDAD_RECE = "b9c0d1e2f3a4"
REVISION_PF19C_LEGACY = "c0d1e2f3a4b"
REVISION_MULTIEMISOR = "f4a5b6c7d8e9"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19c_constraints_append_only_y_roundtrip() -> None:
    """PostgreSQL instala FK/checks/triggers y soporta downgrade vacío exacto."""
    database_url = _postgres_url()
    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_PF19C_LEGACY, database_url)
    _run_alembic("downgrade", REVISION_ELEGIBILIDAD_RECE, database_url)
    engine = create_async_engine(database_url)
    try:
        assert await _alembic_version(engine) == REVISION_ELEGIBILIDAD_RECE
        async with engine.connect() as connection:
            journal_table = await connection.scalar(
                text("SELECT to_regclass('public.resoluciones_legacy_pf19_journal')")
            )
            errores_column = await connection.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'intentos_emision_fiscal'
                      AND column_name = 'errores_arca_json'
                    """
                )
            )
        assert journal_table is None
        assert int(errores_column or 0) == 0
    finally:
        await engine.dispose()
    _run_alembic("upgrade", REVISION_PF19C_LEGACY, database_url)
    engine = create_async_engine(database_url)
    try:
        assert await _alembic_version(engine) == REVISION_PF19C_LEGACY
        async with engine.connect() as connection:
            constraints = {
                str(row[0])
                for row in await connection.execute(
                    text(
                        """
                        SELECT conname
                        FROM pg_constraint
                        WHERE conrelid IN (
                            'intentos_emision_fiscal'::regclass,
                            'resoluciones_legacy_pf19_journal'::regclass
                        )
                        """
                    )
                )
            }
            triggers = {
                str(row[0])
                for row in await connection.execute(
                    text(
                        """
                        SELECT tgname
                        FROM pg_trigger
                        WHERE tgrelid = 'resoluciones_legacy_pf19_journal'::regclass
                          AND NOT tgisinternal
                        """
                    )
                )
            }
        assert {
            "uq_intentos_emision_fiscal_id_empresa",
            "fk_resoluciones_legacy_pf19_journal_intento_empresa",
            "uq_resoluciones_legacy_pf19_journal_intento",
            "ck_resoluciones_legacy_pf19_journal_plan_sha256",
            "ck_resoluciones_legacy_pf19_journal_terminal_response_sha256",
            "ck_resoluciones_legacy_pf19_journal_backup_sha256",
            "ck_resoluciones_legacy_pf19_journal_ambiente",
            "ck_resoluciones_legacy_pf19_journal_accion",
            "ck_resoluciones_legacy_pf19_journal_resultado",
        } <= constraints
        assert triggers == {
            "tr_resoluciones_legacy_pf19_journal_update",
            "tr_resoluciones_legacy_pf19_journal_delete",
        }

        await _crear_contexto_sintetico(engine)
        await _insertar_intento(engine, 1, "fallido_verificado", 1)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO usuarios (
                        id, email, hashed_password, nombre, activo, es_admin,
                        empresa_id, created_at, updated_at
                    ) VALUES (
                        1, 'admin-pf19c@example.test', 'hash', 'Admin PF19C',
                        true, true, 1, now(), now()
                    )
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO empresas (
                        id, razon_social, cuit, condicion_iva, domicilio,
                        localidad, provincia, codigo_postal, inicio_actividades,
                        created_at, updated_at
                    ) VALUES (
                        2, 'Otro emisor sintético', '20000000002', 'RI',
                        'Domicilio 2', 'Localidad 2', 'Provincia 2', '1001',
                        DATE '2020-01-01', now(), now()
                    )
                    """
                )
            )

        journal_insert = text(
            """
            INSERT INTO resoluciones_legacy_pf19_journal (
                id, accion, plan_sha256, terminal_response_sha256, actor_usuario_id,
                ambiente_consultado, resultado, resultado_consultas_json,
                backup_metadata_json, backup_sha256, created_at,
                intento_id, empresa_id
            ) VALUES (
                :id, 'cerrar_legacy_sin_autorizacion_verificada', :plan_sha,
                :terminal_response_sha, 1, 'ambos',
                'legacy_sin_autorizacion_verificada',
                CAST('{}' AS json), CAST('{}' AS json), :backup_sha,
                now(), 1, :empresa_id
            )
            """
        )
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    journal_insert,
                    {
                        "id": 1,
                        "plan_sha": "a" * 64,
                        "terminal_response_sha": "c" * 64,
                        "backup_sha": "b" * 64,
                        "empresa_id": 2,
                    },
                )
        async with engine.begin() as connection:
            await connection.execute(
                journal_insert,
                {
                    "id": 2,
                    "plan_sha": "a" * 64,
                    "terminal_response_sha": "c" * 64,
                    "backup_sha": "b" * 64,
                    "empresa_id": 1,
                },
            )
        with pytest.raises(DBAPIError, match="append-only"):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE resoluciones_legacy_pf19_journal "
                        "SET resultado = resultado WHERE id = 2"
                    )
                )
        with pytest.raises(DBAPIError, match="append-only"):
            async with engine.begin() as connection:
                await connection.execute(
                    text("DELETE FROM resoluciones_legacy_pf19_journal WHERE id = 2")
                )
    finally:
        await engine.dispose()

    output_journal = _run_alembic(
        "downgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
        expected_success=False,
    )
    assert "no eliminar journal administrativo" in output_journal

    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_PF19C_LEGACY, database_url)
    engine = create_async_engine(database_url)
    try:
        await _crear_contexto_sintetico(engine)
        await _insertar_intento(engine, 1, "fallido_verificado", 1)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE intentos_emision_fiscal "
                    "SET errores_arca_json = CAST('[]' AS json) WHERE id = 1"
                )
            )
    finally:
        await engine.dispose()
    output_evidencia = _run_alembic(
        "downgrade",
        REVISION_ELEGIBILIDAD_RECE,
        database_url,
        expected_success=False,
    )
    assert "no eliminar evidencia ARCA estructurada" in output_evidencia

    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_PF19C_LEGACY, database_url)


class _ConsultasBloqueadas:
    """Detiene la primera consulta para forzar una segunda sesión contendiente."""

    def __init__(self) -> None:
        self.iniciada = asyncio.Event()
        self.liberar = asyncio.Event()
        self.llamadas = 0

    async def ultimo_autorizado(self, *_args: object) -> int:
        self.llamadas += 1
        if self.llamadas == 1:
            self.iniciada.set()
            await self.liberar.wait()
        return 0

    async def consultar(self, *_args: object) -> ConsultaComprobanteLegacyPF19:
        raise AssertionError("No corresponde FECompConsultar con último menor")


class _ConsultasProhibidas:
    """Cuenta cualquier consulta indebida del contendiente que debe hacer replay."""

    def __init__(self) -> None:
        self.llamadas = 0

    async def ultimo_autorizado(self, *_args: object) -> int:
        self.llamadas += 1
        raise AssertionError("El contendiente no debe consultar ARCA")

    async def consultar(self, *_args: object) -> ConsultaComprobanteLegacyPF19:
        self.llamadas += 1
        raise AssertionError("El contendiente no debe consultar ARCA")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19c_dos_apply_dejan_un_cierre_y_un_replay() -> None:
    """Locks y journal serializan dos apply sin doble consulta ni doble mutación."""
    database_url = _postgres_url()
    await _reset_schema(database_url)
    # Este escenario usa el ORM y los servicios actuales; los recorridos
    # históricos de migración de este archivo conservan sus revisiones exactas.
    _run_alembic("upgrade", REVISION_MULTIEMISOR, database_url)
    engine = create_async_engine(database_url)
    try:
        intento_id, empresa_id, admin_id = await _sembrar(engine)
        plan = await planificar_resolucion_legacy_pf19(
            engine,
            SolicitudPlanLegacyPF19(
                intento_id=intento_id,
                empresa_id=empresa_id,
                punto_venta=4,
                tipo_comprobante=6,
            ),
        )
        fabrica = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        primera_consulta = _ConsultasBloqueadas()
        segunda_consulta = _ConsultasProhibidas()

        async def ejecutar(consultas: object) -> dict[str, object]:
            async with fabrica() as session:
                return await aplicar_resolucion_legacy_pf19(
                    session,
                    _solicitud_apply(plan, admin_id),
                    consultas,
                )

        primera = asyncio.create_task(ejecutar(primera_consulta))
        await asyncio.wait_for(primera_consulta.iniciada.wait(), timeout=10)
        segunda = asyncio.create_task(ejecutar(segunda_consulta))
        await asyncio.sleep(0.1)
        assert segunda_consulta.llamadas == 0
        primera_consulta.liberar.set()
        resultados = await asyncio.wait_for(
            asyncio.gather(primera, segunda),
            timeout=20,
        )
        assert {resultado["resultado"] for resultado in resultados} == {
            "cerrado",
            "replay_idempotente",
        }
        assert primera_consulta.llamadas == 2
        assert segunda_consulta.llamadas == 0
        async with fabrica() as session:
            intento = await session.get(IntentoEmisionFiscal, intento_id)
            assert intento is not None
            assert intento.estado == "fallido_verificado"
            cantidad_journal = await session.scalar(
                select(func.count()).select_from(ResolucionLegacyPF19Journal)
            )
            assert int(cantidad_journal or 0) == 1
    finally:
        await engine.dispose()
