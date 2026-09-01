"""Integración PostgreSQL desechable para elegibilidad RECE PF-19B."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.empresas import update_empresa
from app.models.punto_venta import PuntoVenta
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.core.config import settings
from app.schemas.empresa import EmpresaUpdate
from app.services.constancia_puntos_venta_service import SENAL_RECE_EXACTA
from app.services.elegibilidad_rece_service import (
    AtestacionPuntoRece,
    ElegibilidadReceError,
    ElegibilidadReceService,
)

from tests.integration.test_integridad_fiscal_postgresql import (
    _alembic_version,
    _crear_contexto_sintetico,
    _insertar_intento,
    _postgres_url,
    _reset_schema,
    _run_alembic,
)


REVISION_ANTERIOR = "a8b9c0d1e2f3"
REVISION_ELEGIBILIDAD_RECE = "b9c0d1e2f3a4"
REVISION_ACREDITACION_DURABLE = "d1e2f3a4b5c6"
REVISION_AUTORIDAD_WSFE = "e3f4a5b6c7d8"
REVISION_MULTIEMISOR = "f4a5b6c7d8e9"
FECHA_SINTETICA = date(2026, 8, 9)


async def _preparar_pf19b(
    database_url: str,
    *,
    intento_legacy: bool = False,
    revision_objetivo: str = REVISION_MULTIEMISOR,
) -> AsyncEngine:
    """Resetea la base y aplica PF-19B hasta la revisión solicitada o el head."""
    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_ANTERIOR, database_url)
    engine = create_async_engine(database_url)
    await _crear_contexto_sintetico(engine)
    if intento_legacy:
        await _insertar_intento(engine, 1, "fallido_verificado", None)
    await engine.dispose()
    _run_alembic("upgrade", REVISION_ELEGIBILIDAD_RECE, database_url)
    if revision_objetivo != REVISION_ELEGIBILIDAD_RECE:
        _run_alembic("upgrade", revision_objetivo, database_url)
    return create_async_engine(database_url)


async def _ledger_rows(engine: AsyncEngine) -> list[tuple[object, ...]]:
    """Lee el ledger inicial RECE sin exponer datos operativos."""
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT r.ambiente, r.estado, r.fuente, r.evidencia_tipo,
                       r.revision, r.punto_revision_fiscal,
                       a.revision_actual_id = r.id AS es_cabeza
                FROM puntos_venta_elegibilidad_rece_revisiones r
                JOIN puntos_venta_elegibilidad_rece_actual a
                  ON a.empresa_id = r.empresa_id
                 AND a.punto_venta_id = r.punto_venta_id
                 AND a.ambiente = r.ambiente
                ORDER BY r.ambiente, r.revision
                """
            )
        )
        return [tuple(row) for row in result]


async def _insertar_contexto_operativo_pf19b(engine: AsyncEngine) -> dict[str, int]:
    """Crea operaciones, lotes, grupo y guarda sintéticos coherentes."""
    async with engine.begin() as connection:
        revision_rows = await connection.execute(
            text(
                """
                SELECT id, ambiente
                FROM puntos_venta_elegibilidad_rece_revisiones
                WHERE empresa_id = 1 AND punto_venta_id = 1
                """
            )
        )
        revisions = {str(row.ambiente): int(row.id) for row in revision_rows}
        for operation_id in (10, 11, 12):
            await connection.execute(
                text(
                    """
                    INSERT INTO operaciones_idempotentes (
                        id, idempotency_key, tipo_operacion, payload_hash,
                        estado, rece_snapshot_hash, empresa_id,
                        created_at, updated_at
                    ) VALUES (
                        :id, :key, 'emitir_comprobante', :payload_hash,
                        'en_proceso', :snapshot_hash, 1, now(), now()
                    )
                    """
                ),
                {
                    "id": operation_id,
                    "key": f"pf19b-pg-{operation_id}",
                    "payload_hash": f"{operation_id:064d}",
                    "snapshot_hash": f"{operation_id + 20:064d}",
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO operaciones_idempotentes_elegibilidad_rece (
                        id, operacion_id, empresa_id, punto_venta_id,
                        ambiente, elegibilidad_revision_id,
                        punto_venta_revision_fiscal, created_at
                    ) VALUES (
                        :id, :operation_id, 1, 1, 'produccion',
                        :revision_id, 1, now()
                    )
                    """
                ),
                {
                    "id": operation_id + 10,
                    "operation_id": operation_id,
                    "revision_id": revisions["produccion"],
                },
            )

        for lote_id in (50, 51):
            await connection.execute(
                text(
                    """
                    INSERT INTO lotes_comprobantes (
                        id, nombre_archivo, archivo_hash, estado,
                        modo_procesamiento, procesamiento_async, total_filas,
                        total_grupos, grupos_validos, grupos_con_error,
                        grupos_emitidos, grupos_fallidos,
                        grupos_reconciliados_externos, grupos_descartados,
                        empresa_id, created_at, updated_at
                    ) VALUES (
                        :id, :filename, :file_hash, 'validado', 'sincronico',
                        false, 1, 1, 1, 0, 0, 0, 0, 0, 1, now(), now()
                    )
                    """
                ),
                {
                    "id": lote_id,
                    "filename": f"pf19b-{lote_id}.xlsx",
                    "file_hash": f"{lote_id:064d}",
                },
            )
        await connection.execute(
            text(
                """
                INSERT INTO lotes_comprobantes_grupos (
                    id, comprobante_ref, orden, estado, tipo_comprobante,
                    punto_venta_numero, total_estimado, lote_id, empresa_id,
                    punto_venta_id, ambiente,
                    punto_venta_elegibilidad_revision_id,
                    punto_venta_revision_fiscal, created_at, updated_at
                ) VALUES (
                    60, 'PF19B-PG-GRUPO', 1, 'validado', 6, 41, 121,
                    50, 1, 1, 'produccion', :revision_id, 1, now(), now()
                )
                """
            ),
            {"revision_id": revisions["produccion"]},
        )
        await connection.execute(
            text(
                """
                INSERT INTO puntos_venta_guardas_emision_rece (
                    id, token, fase, operacion_id, empresa_id,
                    punto_venta_id, ambiente, elegibilidad_revision_id,
                    punto_venta_revision_fiscal, cerrada_en, created_at, updated_at
                ) VALUES (
                    30, :token, 'cerrada_pre_arca', 10, 1, 1,
                    'produccion', :revision_id, 1, now(), now(), now()
                )
                """
            ),
            {
                "token": "6" * 64,
                "revision_id": revisions["produccion"],
            },
        )
    return revisions


def _attempt_params(
    *,
    row_id: int,
    revision_id: int,
    lote_id: int | None,
    grupo_id: int | None,
) -> dict[str, object]:
    """Construye un intento moderno para probar la FK fiscal exacta."""
    return {
        "id": row_id,
        "tipo_comprobante": 6,
        "punto_venta_numero": 41,
        "numero_planificado": 1000 + row_id,
        "fecha_emision": FECHA_SINTETICA,
        "total": Decimal("121.00"),
        "payload_hash": f"{row_id:064d}",
        "huella_logica": f"{row_id + 1:064d}",
        "estado": "en_proceso",
        "operacion_id": 10,
        "empresa_id": 1,
        "punto_venta_id": 1,
        "lote_id": lote_id,
        "grupo_id": grupo_id,
        "ambiente": "produccion",
        "revision_id": revision_id,
        "revision_fiscal": 1,
        "guarda_id": 30,
    }


INTENTO_PF19B_INSERT = text(
    """
    INSERT INTO intentos_emision_fiscal (
        id, tipo_comprobante, punto_venta_numero, numero_planificado,
        fecha_emision, total, payload_hash, huella_logica, estado,
        operacion_id, empresa_id, punto_venta_id, lote_id, grupo_id,
        ambiente, punto_venta_elegibilidad_revision_id,
        punto_venta_revision_fiscal, guarda_rece_id, created_at, updated_at
    ) VALUES (
        :id, :tipo_comprobante, :punto_venta_numero, :numero_planificado,
        :fecha_emision, :total, :payload_hash, :huella_logica, :estado,
        :operacion_id, :empresa_id, :punto_venta_id, :lote_id, :grupo_id,
        :ambiente, :revision_id, :revision_fiscal, :guarda_id, now(), now()
    )
    """
)


async def _constraint_columns(
    engine: AsyncEngine,
    constraint_name: str,
    *,
    referred: bool = False,
) -> list[str]:
    """Lee en orden las columnas locales o referidas de una constraint PG."""
    relation_column = "confrelid" if referred else "conrelid"
    key_column = "confkey" if referred else "conkey"
    async with engine.connect() as connection:
        value = await connection.scalar(
            text(
                f"""
                SELECT array_agg(attribute.attname ORDER BY key.ordinality)
                FROM pg_constraint constraint_row
                CROSS JOIN LATERAL unnest(constraint_row.{key_column})
                    WITH ORDINALITY AS key(attnum, ordinality)
                JOIN pg_attribute attribute
                  ON attribute.attrelid = constraint_row.{relation_column}
                 AND attribute.attnum = key.attnum
                WHERE constraint_row.conname = :constraint_name
                GROUP BY constraint_row.oid
                """
            ),
            {"constraint_name": constraint_name},
        )
    assert value is not None
    return [str(item) for item in value]


async def _assert_attempt_rejected(
    engine: AsyncEngine,
    params: dict[str, object],
) -> None:
    """Exige que PostgreSQL revierta un intento fiscal incoherente."""
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(INTENTO_PF19B_INSERT, params)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19b_backfill_downgrade_reupgrade() -> None:
    """PF-19B crea dos cabezas legacy y revierte/reinstala sin residuos."""
    database_url = _postgres_url()
    engine = await _preparar_pf19b(
        database_url,
        intento_legacy=True,
        revision_objetivo=REVISION_ELEGIBILIDAD_RECE,
    )
    expected_ledger = [
        (
            "homologacion",
            "no_verificado",
            "migracion_legacy",
            "sin_evidencia",
            1,
            1,
            True,
        ),
        (
            "produccion",
            "no_verificado",
            "migracion_legacy",
            "sin_evidencia",
            1,
            1,
            True,
        ),
    ]
    assert await _ledger_rows(engine) == expected_ledger
    async with engine.connect() as connection:
        legacy_snapshot = await connection.execute(
            text(
                """
                SELECT ambiente, punto_venta_elegibilidad_revision_id,
                       punto_venta_revision_fiscal, guarda_rece_id
                FROM intentos_emision_fiscal WHERE id = 1
                """
            )
        )
        assert tuple(legacy_snapshot.one()) == (None, None, None, None)
    await engine.dispose()

    _run_alembic("downgrade", REVISION_ANTERIOR, database_url)
    engine = create_async_engine(database_url)
    assert await _alembic_version(engine) == REVISION_ANTERIOR
    async with engine.connect() as connection:
        removed = await connection.execute(
            text(
                """
                SELECT to_regclass('public.puntos_venta_elegibilidad_rece_revisiones'),
                       to_regclass('public.puntos_venta_elegibilidad_rece_actual'),
                       to_regclass('public.puntos_venta_guardas_emision_rece')
                """
            )
        )
        assert tuple(removed.one()) == (None, None, None)
    await engine.dispose()

    _run_alembic("upgrade", REVISION_ELEGIBILIDAD_RECE, database_url)
    engine = create_async_engine(database_url)
    assert await _alembic_version(engine) == REVISION_ELEGIBILIDAD_RECE
    assert await _ledger_rows(engine) == expected_ledger
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19b_upgrade_vacio() -> None:
    """Una instalación sin emisores llega al head sin inventar ledger."""
    database_url = _postgres_url()
    await _reset_schema(database_url)
    _run_alembic("upgrade", REVISION_ELEGIBILIDAD_RECE, database_url)
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        counts = await connection.execute(
            text(
                """
                SELECT
                  (SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_revisiones),
                  (SELECT COUNT(*) FROM puntos_venta_elegibilidad_rece_actual),
                  (SELECT COUNT(*) FROM puntos_venta_guardas_emision_rece)
                """
            )
        )
        assert tuple(counts.one()) == (0, 0, 0)
    assert await _alembic_version(engine) == REVISION_ELEGIBILIDAD_RECE
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19b_escritor_real_serializa_revision_y_cabeza() -> None:
    """Dos sesiones reales dejan un único ganador, ledger contiguo y head máximo."""
    database_url = _postgres_url()
    engine = await _preparar_pf19b(database_url)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with session_factory() as first_session, session_factory() as second_session:
            first_point = await first_session.get(PuntoVenta, 1)
            second_point = await second_session.get(PuntoVenta, 1)
            assert first_point is not None
            assert second_point is not None
            assert first_point.revision_fiscal == second_point.revision_fiscal == 1

            async def mutate(
                session: AsyncSession,
                point: PuntoVenta,
                numero: int,
            ) -> bool | ElegibilidadReceError:
                """Ejecuta el escritor real sin el lock local para aislar PostgreSQL."""
                try:
                    return await ElegibilidadReceService(session).aplicar_cambios_punto(
                        point,
                        {"numero": numero},
                        fuente="edicion",
                        _lock_adquirido=True,
                    )
                except ElegibilidadReceError as exc:
                    return exc

            outcomes = await asyncio.gather(
                mutate(first_session, first_point, 42),
                mutate(second_session, second_point, 43),
            )

        assert sum(outcome is True for outcome in outcomes) == 1
        conflicts = [
            outcome
            for outcome in outcomes
            if isinstance(outcome, ElegibilidadReceError)
        ]
        assert len(conflicts) == 1
        assert conflicts[0].categoria == "conflicto_revision_fiscal"

        async with engine.connect() as connection:
            revision_fiscal = await connection.scalar(
                text("SELECT revision_fiscal FROM puntos_venta WHERE id = 1")
            )
            ledger = await connection.execute(
                text(
                    """
                    SELECT r.ambiente, r.revision,
                           a.revision_actual_id = r.id AS es_cabeza
                    FROM puntos_venta_elegibilidad_rece_revisiones r
                    JOIN puntos_venta_elegibilidad_rece_actual a
                      ON a.empresa_id = r.empresa_id
                     AND a.punto_venta_id = r.punto_venta_id
                     AND a.ambiente = r.ambiente
                    WHERE r.punto_venta_id = 1
                    ORDER BY r.ambiente, r.revision
                    """
                )
            )
            assert revision_fiscal == 2
            assert [tuple(row) for row in ledger] == [
                ("homologacion", 1, False),
                ("homologacion", 2, True),
                ("produccion", 1, False),
                ("produccion", 2, True),
            ]
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19b_atestaciones_solapadas_respetan_orden_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dos atestaciones invertidas terminan sin deadlock ni ledger parcial."""
    database_url = _postgres_url()
    engine = await _preparar_pf19b(database_url)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    @asynccontextmanager
    async def sin_lock_local(*_args: object, **_kwargs: object):
        """Aísla el orden de locks PostgreSQL, sin el serializador del proceso."""
        yield

    monkeypatch.setattr(settings, "arca_env", "produccion")
    monkeypatch.setattr(
        ElegibilidadReceService,
        "bloqueo_local_punto",
        sin_lock_local,
    )
    try:
        async with session_factory() as setup_session:
            await setup_session.execute(
                text(
                    """
                    INSERT INTO usuarios (
                        id, email, hashed_password, nombre, activo, es_admin,
                        empresa_id, created_at, updated_at
                    ) VALUES
                        (1, 'admin-uno@example.invalid', 'hash', 'Admin Uno',
                         true, true, 1, now(), now()),
                        (2, 'admin-dos@example.invalid', 'hash', 'Admin Dos',
                         true, true, 1, now(), now())
                    """
                )
            )
            segundo = PuntoVenta(
                id=2,
                numero=42,
                nombre="Punto sintético dos",
                es_webservice=True,
                bloqueado=False,
                activo=True,
                empresa_id=1,
            )
            setup_session.add(segundo)
            await ElegibilidadReceService(
                setup_session,
                hoy=FECHA_SINTETICA,
            ).crear_contextos_iniciales_no_verificados(
                segundo,
                creado_por_usuario_id=1,
            )
            await setup_session.commit()

        async with session_factory() as first_session, session_factory() as second_session:
            puntos_primera = {
                int(punto.id): punto
                for punto in (
                    await first_session.execute(
                        select(PuntoVenta).where(PuntoVenta.id.in_([1, 2]))
                    )
                ).scalars()
            }
            puntos_segunda = {
                int(punto.id): punto
                for punto in (
                    await second_session.execute(
                        select(PuntoVenta).where(PuntoVenta.id.in_([1, 2]))
                    )
                ).scalars()
            }
            assert set(puntos_primera) == set(puntos_segunda) == {1, 2}
            await first_session.execute(text("SET LOCAL lock_timeout = '5s'"))
            await second_session.execute(text("SET LOCAL lock_timeout = '5s'"))

            async def atestiguar(
                session: AsyncSession,
                puntos: dict[int, PuntoVenta],
                *,
                presente_id: int,
                actor_id: int,
                evidencia: str,
            ) -> dict[int, str] | ElegibilidadReceError:
                """Ejecuta el productor real con particiones presente/ausente inversas."""
                ausente_id = 1 if presente_id == 2 else 2
                try:
                    return await ElegibilidadReceService(
                        session,
                        hoy=FECHA_SINTETICA,
                    ).atestiguar_constancia_productiva(
                        [
                            AtestacionPuntoRece(
                                punto_venta=puntos[presente_id],
                                cambios={
                                    "sistema": SENAL_RECE_EXACTA,
                                    "activo": True,
                                },
                                sistema_constancia=SENAL_RECE_EXACTA,
                            )
                        ],
                        invalidaciones_ausentes=[
                            (puntos[ausente_id], {"activo": False})
                        ],
                        empresa_id=1,
                        empresa_cuit="20000000001",
                        evidencia_sha256=evidencia,
                        documento_emitido_en=FECHA_SINTETICA,
                        actor_usuario_id=actor_id,
                    )
                except ElegibilidadReceError as exc:
                    return exc

            outcomes = await asyncio.wait_for(
                asyncio.gather(
                    atestiguar(
                        first_session,
                        puntos_primera,
                        presente_id=1,
                        actor_id=1,
                        evidencia="a" * 64,
                    ),
                    atestiguar(
                        second_session,
                        puntos_segunda,
                        presente_id=2,
                        actor_id=2,
                        evidencia="b" * 64,
                    ),
                ),
                timeout=15,
            )

        assert sum(isinstance(outcome, dict) for outcome in outcomes) == 1
        conflicts = [
            outcome
            for outcome in outcomes
            if isinstance(outcome, ElegibilidadReceError)
        ]
        assert len(conflicts) == 1
        assert conflicts[0].categoria == "conflicto_revision_fiscal"
        async with engine.connect() as connection:
            puntos = await connection.execute(
                text(
                    """
                    SELECT id, revision_fiscal
                    FROM puntos_venta
                    ORDER BY id
                    """
                )
            )
            assert [tuple(row) for row in puntos] == [(1, 2), (2, 2)]
            ledger = await connection.execute(
                text(
                    """
                    SELECT punto_venta_id, ambiente, array_agg(revision ORDER BY revision)
                    FROM puntos_venta_elegibilidad_rece_revisiones
                    GROUP BY punto_venta_id, ambiente
                    ORDER BY punto_venta_id, ambiente
                    """
                )
            )
            assert [tuple(row) for row in ledger] == [
                (1, "homologacion", [1, 2]),
                (1, "produccion", [1, 2]),
                (2, "homologacion", [1, 2]),
                (2, "produccion", [1, 2]),
            ]
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("ganador", ["update", "atestacion"])
async def test_postgresql_pf19b_serializa_cuit_y_atestacion(
    ganador: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CUIT y atestación compiten sin publicar evidencia de otra identidad."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    database_url = _postgres_url()
    engine = await _preparar_pf19b(database_url)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    cuit_original = "20300000001"
    cuit_nuevo = "20300000002"
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO empresas (
                        id, razon_social, cuit, condicion_iva, domicilio,
                        localidad, provincia, codigo_postal,
                        inicio_actividades, created_at, updated_at
                    ) VALUES (
                        2, 'Emisor carrera CUIT', :cuit, 'RI',
                        'Domicilio sintético', 'Localidad sintética',
                        'Provincia sintética', '1000', '2020-01-01',
                        now(), now()
                    )
                    """
                ),
                {"cuit": cuit_original},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO usuarios (
                        id, email, hashed_password, nombre, activo,
                        es_admin, empresa_id, created_at, updated_at
                    ) VALUES (
                        20, 'admin-cuit@example.invalid', 'hash',
                        'Admin carrera CUIT', true, true, 2, now(), now()
                    )
                    """
                )
            )

        async with (
            session_factory() as atestacion_session,
            session_factory() as update_session,
        ):
            await atestacion_session.execute(text("SET LOCAL lock_timeout = '5s'"))
            await update_session.execute(text("SET LOCAL lock_timeout = '5s'"))
            admin = await update_session.get(Usuario, 20)
            assert admin is not None
            intento_lock_actor = asyncio.Event()
            intento_lock_empresa = asyncio.Event()
            empresa_bloqueada = asyncio.Event()
            liberar_atestacion = asyncio.Event()
            update_iniciado = asyncio.Event()

            class ServicioAtestacionConBarrera(ElegibilidadReceService):
                """Instrumenta el lock del emisor sin crear hijos previamente."""

                barrera_aplicada = False

                async def _exigir_actor_admin(self, actor_usuario_id: int) -> None:
                    intento_lock_actor.set()
                    await super()._exigir_actor_admin(actor_usuario_id)

                async def _exigir_empresa_cuit_actual(
                    self,
                    *,
                    empresa_id: int,
                    empresa_cuit: str,
                ) -> None:
                    intento_lock_empresa.set()
                    await super()._exigir_empresa_cuit_actual(
                        empresa_id=empresa_id,
                        empresa_cuit=empresa_cuit,
                    )
                    if ganador == "atestacion" and not self.barrera_aplicada:
                        self.barrera_aplicada = True
                        empresa_bloqueada.set()
                        await liberar_atestacion.wait()

            async def editar_cuit() -> Empresa | HTTPException:
                """Ejecuta el endpoint real y devuelve un conflicto funcional."""
                update_iniciado.set()
                try:
                    return await update_empresa(
                        empresa_id=2,
                        empresa_data=EmpresaUpdate(cuit=cuit_nuevo),
                        db=update_session,
                        current_user=admin,
                    )
                except HTTPException as exc:
                    return exc

            async def atestiguar() -> dict[int, str] | ElegibilidadReceError:
                """Crea el primer hijo solo dentro de la frontera bloqueada."""
                servicio = ServicioAtestacionConBarrera(
                    atestacion_session,
                    hoy=FECHA_SINTETICA,
                )
                punto = PuntoVenta(
                    id=20,
                    numero=42,
                    nombre="Punto carrera CUIT",
                    sistema=SENAL_RECE_EXACTA,
                    es_webservice=True,
                    bloqueado=False,
                    activo=True,
                    empresa_id=2,
                )
                try:
                    async with servicio.bloquear_frontera_atestacion_productiva(
                        empresa_id=2,
                        empresa_cuit=cuit_original,
                        actor_usuario_id=20,
                    ):
                        atestacion_session.add(punto)
                        await servicio.crear_contextos_iniciales_no_verificados(
                            punto,
                            creado_por_usuario_id=20,
                        )
                        return await servicio.atestiguar_constancia_productiva(
                            [
                                AtestacionPuntoRece(
                                    punto_venta=punto,
                                    cambios={
                                        "sistema": SENAL_RECE_EXACTA,
                                        "activo": True,
                                    },
                                    sistema_constancia=SENAL_RECE_EXACTA,
                                )
                            ],
                            empresa_id=2,
                            empresa_cuit=cuit_original,
                            evidencia_sha256="c" * 64,
                            documento_emitido_en=FECHA_SINTETICA,
                            actor_usuario_id=20,
                        )
                except ElegibilidadReceError as exc:
                    await atestacion_session.rollback()
                    return exc

            if ganador == "update":
                await asyncio.wait_for(
                    update_session.execute(
                        select(Usuario)
                        .where(Usuario.id == 20)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    ),
                    timeout=5,
                )
                await asyncio.wait_for(
                    update_session.execute(
                        select(Empresa)
                        .where(Empresa.id == 2)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    ),
                    timeout=5,
                )
                tarea_atestacion = asyncio.create_task(atestiguar())
                await asyncio.wait_for(intento_lock_actor.wait(), timeout=5)
                assert not any(
                    isinstance(objeto, PuntoVenta) for objeto in atestacion_session.new
                )
                terminadas, _pendientes = await asyncio.wait(
                    {tarea_atestacion},
                    timeout=0.1,
                )
                assert not terminadas
                resultado_update = await asyncio.wait_for(editar_cuit(), timeout=5)
                resultado_atestacion = await asyncio.wait_for(
                    tarea_atestacion,
                    timeout=10,
                )
                assert isinstance(resultado_update, Empresa)
                assert isinstance(resultado_atestacion, ElegibilidadReceError)
            else:
                tarea_atestacion = asyncio.create_task(atestiguar())
                await asyncio.wait_for(empresa_bloqueada.wait(), timeout=5)
                tarea_update = asyncio.create_task(editar_cuit())
                await asyncio.wait_for(update_iniciado.wait(), timeout=5)
                terminadas, _pendientes = await asyncio.wait(
                    {tarea_update},
                    timeout=0.1,
                )
                liberar_atestacion.set()
                assert not terminadas
                resultado_atestacion, resultado_update = await asyncio.wait_for(
                    asyncio.gather(tarea_atestacion, tarea_update),
                    timeout=10,
                )
                assert isinstance(resultado_atestacion, dict)
                assert isinstance(resultado_update, HTTPException)
                assert resultado_update.status_code == 409

        async with engine.connect() as connection:
            cuit_actual = await connection.scalar(
                text("SELECT cuit FROM empresas WHERE id = 2")
            )
            punto_count = await connection.scalar(
                text("SELECT COUNT(*) FROM puntos_venta WHERE empresa_id = 2")
            )
            verificadas = await connection.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM puntos_venta_elegibilidad_rece_revisiones
                    WHERE empresa_id = 2 AND estado = 'verificado_rece'
                    """
                )
            )
        if ganador == "update":
            assert (cuit_actual, punto_count, verificadas) == (cuit_nuevo, 0, 0)
        else:
            assert (cuit_actual, punto_count, verificadas) == (cuit_original, 1, 1)
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("campo_degradado", ["activo", "es_admin"])
@pytest.mark.parametrize("ganador", ["degradacion", "atestacion"])
async def test_postgresql_pf19b_serializa_actor_y_atestacion(
    campo_degradado: str,
    ganador: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La autoridad del actor queda definida bajo lock antes de acreditar RECE."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    database_url = _postgres_url()
    engine = await _preparar_pf19b(database_url)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO usuarios (
                        id, email, hashed_password, nombre, activo,
                        es_admin, empresa_id, created_at, updated_at
                    ) VALUES (
                        30, 'admin-actor@example.invalid', 'hash',
                        'Admin carrera actor', true, true, 1, now(), now()
                    )
                    """
                )
            )

        async with (
            session_factory() as atestacion_session,
            session_factory() as degradacion_session,
        ):
            await atestacion_session.execute(text("SET LOCAL lock_timeout = '5s'"))
            await degradacion_session.execute(text("SET LOCAL lock_timeout = '5s'"))
            punto = await atestacion_session.get(PuntoVenta, 1)
            assert punto is not None
            intento_lock_actor = asyncio.Event()
            actor_bloqueado = asyncio.Event()
            liberar_atestacion = asyncio.Event()
            degradacion_iniciada = asyncio.Event()

            class ServicioActorConBarrera(ElegibilidadReceService):
                """Pausa una única vez después de revalidar al actor bajo lock."""

                barrera_aplicada = False

                async def _exigir_actor_admin(self, actor_usuario_id: int) -> None:
                    intento_lock_actor.set()
                    await super()._exigir_actor_admin(actor_usuario_id)
                    if ganador == "atestacion" and not self.barrera_aplicada:
                        self.barrera_aplicada = True
                        actor_bloqueado.set()
                        await liberar_atestacion.wait()

            async def atestiguar() -> dict[int, str] | ElegibilidadReceError:
                """Ejecuta la atestación real y captura solo el conflicto funcional."""
                try:
                    return await ServicioActorConBarrera(
                        atestacion_session,
                        hoy=FECHA_SINTETICA,
                    ).atestiguar_constancia_productiva(
                        [
                            AtestacionPuntoRece(
                                punto_venta=punto,
                                cambios={
                                    "sistema": SENAL_RECE_EXACTA,
                                    "activo": True,
                                },
                                sistema_constancia=SENAL_RECE_EXACTA,
                            )
                        ],
                        empresa_id=1,
                        empresa_cuit="20000000001",
                        evidencia_sha256="d" * 64,
                        documento_emitido_en=FECHA_SINTETICA,
                        actor_usuario_id=30,
                    )
                except ElegibilidadReceError as exc:
                    await atestacion_session.rollback()
                    return exc

            async def degradar_actor() -> None:
                """Retira una capacidad y confirma la transacción competidora."""
                degradacion_iniciada.set()
                await degradacion_session.execute(
                    update(Usuario)
                    .where(Usuario.id == 30)
                    .values(**{campo_degradado: False})
                )
                await degradacion_session.commit()

            if ganador == "degradacion":
                await asyncio.wait_for(
                    degradacion_session.execute(
                        update(Usuario)
                        .where(Usuario.id == 30)
                        .values(**{campo_degradado: False})
                    ),
                    timeout=5,
                )
                tarea_atestacion = asyncio.create_task(atestiguar())
                await asyncio.wait_for(intento_lock_actor.wait(), timeout=5)
                terminadas, _pendientes = await asyncio.wait(
                    {tarea_atestacion},
                    timeout=0.1,
                )
                assert not terminadas
                await degradacion_session.commit()
                resultado_atestacion = await asyncio.wait_for(
                    tarea_atestacion,
                    timeout=10,
                )
                assert isinstance(resultado_atestacion, ElegibilidadReceError)
            else:
                tarea_atestacion = asyncio.create_task(atestiguar())
                await asyncio.wait_for(actor_bloqueado.wait(), timeout=5)
                tarea_degradacion = asyncio.create_task(degradar_actor())
                await asyncio.wait_for(degradacion_iniciada.wait(), timeout=5)
                terminadas, _pendientes = await asyncio.wait(
                    {tarea_degradacion},
                    timeout=0.1,
                )
                liberar_atestacion.set()
                assert not terminadas
                resultado_atestacion, _resultado_degradacion = await asyncio.wait_for(
                    asyncio.gather(tarea_atestacion, tarea_degradacion),
                    timeout=10,
                )
                assert isinstance(resultado_atestacion, dict)

        async with engine.connect() as connection:
            actor = (
                await connection.execute(
                    text("SELECT activo, es_admin FROM usuarios WHERE id = 30")
                )
            ).one()
            verificadas = await connection.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM puntos_venta_elegibilidad_rece_revisiones
                    WHERE empresa_id = 1
                      AND punto_venta_id = 1
                      AND estado = 'verificado_rece'
                    """
                )
            )
            total_revisiones = await connection.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM puntos_venta_elegibilidad_rece_revisiones
                    WHERE empresa_id = 1 AND punto_venta_id = 1
                    """
                )
            )
            revision_fiscal = await connection.scalar(
                text("SELECT revision_fiscal FROM puntos_venta WHERE id = 1")
            )
        assert actor.activo is (campo_degradado != "activo")
        assert actor.es_admin is (campo_degradado != "es_admin")
        if ganador == "degradacion":
            assert (verificadas, total_revisiones, revision_fiscal) == (0, 2, 1)
        else:
            assert (verificadas, total_revisiones, revision_fiscal) == (1, 4, 2)
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19b_downgrade_bloquea_evidencia_runtime() -> None:
    """Un cambio fiscal real impide retirar PF-19B y conserva todo el ledger."""
    database_url = _postgres_url()
    engine = await _preparar_pf19b(database_url)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with session_factory() as session:
            point = await session.get(PuntoVenta, 1)
            assert point is not None
            changed = await ElegibilidadReceService(session).aplicar_cambios_punto(
                point,
                {"numero": 42},
                fuente="edicion",
            )
            assert changed is True
        ledger_before = await _ledger_rows(engine)
        async with engine.connect() as connection:
            point_before = tuple(
                (
                    await connection.execute(
                        text(
                            "SELECT numero, revision_fiscal "
                            "FROM puntos_venta WHERE id = 1"
                        )
                    )
                ).one()
            )
        assert point_before == (42, 2)
        assert len(ledger_before) == 4
        assert sum(row[2] == "edicion" for row in ledger_before) == 2
    finally:
        await engine.dispose()

    output = _run_alembic(
        "downgrade",
        REVISION_ANTERIOR,
        database_url,
        expected_success=False,
    )
    assert "PF-19B bloqueó el downgrade" in output

    engine = create_async_engine(database_url)
    try:
        # PostgreSQL revierte toda la orden de downgrade cuando PF-19B bloquea;
        # por eso también conserva las migraciones posteriores que la precedían.
        assert await _alembic_version(engine) == REVISION_MULTIEMISOR
        assert await _ledger_rows(engine) == ledger_before
        async with engine.connect() as connection:
            point_after = tuple(
                (
                    await connection.execute(
                        text(
                            "SELECT numero, revision_fiscal "
                            "FROM puntos_venta WHERE id = 1"
                        )
                    )
                ).one()
            )
        assert point_after == point_before
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_pf19b_fk_exacta_checks_y_guarda_concurrente() -> None:
    """PostgreSQL impone el snapshot de nueve campos y una única guarda activa."""
    database_url = _postgres_url()
    engine = await _preparar_pf19b(database_url)
    revisions = await _insertar_contexto_operativo_pf19b(engine)

    expected_columns = [
        "grupo_id",
        "lote_id",
        "empresa_id",
        "punto_venta_id",
        "punto_venta_numero",
        "ambiente",
        "punto_venta_elegibilidad_revision_id",
        "punto_venta_revision_fiscal",
        "tipo_comprobante",
    ]
    assert (
        await _constraint_columns(
            engine,
            "fk_intento_grupo_snapshot_rece_exacto",
        )
        == expected_columns
    )
    assert await _constraint_columns(
        engine,
        "fk_intento_grupo_snapshot_rece_exacto",
        referred=True,
    ) == [
        "id",
        "lote_id",
        "empresa_id",
        "punto_venta_id",
        "punto_venta_numero",
        "ambiente",
        "punto_venta_elegibilidad_revision_id",
        "punto_venta_revision_fiscal",
        "tipo_comprobante",
    ]

    await _insertar_intento(engine, 2, "fallido_verificado", None)
    async with engine.begin() as connection:
        await connection.execute(
            INTENTO_PF19B_INSERT,
            _attempt_params(
                row_id=40,
                revision_id=revisions["produccion"],
                lote_id=None,
                grupo_id=None,
            ),
        )
        await connection.execute(
            INTENTO_PF19B_INSERT,
            _attempt_params(
                row_id=41,
                revision_id=revisions["produccion"],
                lote_id=50,
                grupo_id=60,
            ),
        )

    base = _attempt_params(
        row_id=100,
        revision_id=revisions["produccion"],
        lote_id=50,
        grupo_id=60,
    )
    mutations: list[dict[str, object]] = [
        {"lote_id": 51},
        {"punto_venta_numero": 42},
        {"tipo_comprobante": 1},
        {"ambiente": "homologacion"},
        {"revision_id": revisions["homologacion"]},
        {"revision_fiscal": 2},
        {"grupo_id": None},
        {"operacion_id": None},
        {"guarda_id": None},
    ]
    for mutation in mutations:
        await _assert_attempt_rejected(engine, {**base, **mutation})

    for mutation in ({"ambiente": None}, {"punto_venta_revision_fiscal": None}):
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                assignments = ", ".join(f"{column} = :{column}" for column in mutation)
                await connection.execute(
                    text(
                        "UPDATE lotes_comprobantes_grupos "
                        f"SET {assignments} WHERE id = 60"
                    ),
                    mutation,
                )

    first_connection = await engine.connect()
    second_connection = await engine.connect()
    first_transaction = await first_connection.begin()
    second_transaction = await second_connection.begin()
    try:
        guard_sql = text(
            """
            INSERT INTO puntos_venta_guardas_emision_rece (
                id, token, fase, operacion_id, empresa_id, punto_venta_id,
                ambiente, elegibilidad_revision_id,
                punto_venta_revision_fiscal, created_at, updated_at
            ) VALUES (
                :id, :token, 'pre_arca', :operation_id, 1, 1,
                'produccion', :revision_id, 1, now(), now()
            )
            """
        )
        await first_connection.execute(
            guard_sql,
            {
                "id": 31,
                "token": "7" * 64,
                "operation_id": 11,
                "revision_id": revisions["produccion"],
            },
        )
        await second_connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        competing = asyncio.create_task(
            second_connection.execute(
                guard_sql,
                {
                    "id": 32,
                    "token": "8" * 64,
                    "operation_id": 12,
                    "revision_id": revisions["produccion"],
                },
            )
        )
        await asyncio.sleep(0.2)
        assert not competing.done()
        await first_transaction.commit()
        with pytest.raises(IntegrityError):
            await asyncio.wait_for(competing, timeout=6)
    finally:
        if first_transaction.is_active:
            await first_transaction.rollback()
        if second_transaction.is_active:
            await second_transaction.rollback()
        await first_connection.close()
        await second_connection.close()
        await engine.dispose()
