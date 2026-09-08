"""Pruebas de coordinación transaccional de duplicados de lotes v2."""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.lotes_comprobantes import (
    _evaluar_control_duplicados_operacion,
    _resolver_remanente_legacy_aceptado,
)
from app.core.config import settings
from app.core.database import Base, _habilitar_foreign_keys_sqlite
from app.models.empresa import Empresa, LoteDuplicadosCoordinacion
from app.models.elegibilidad_rece import (
    PuntoVentaElegibilidadReceActual,
    PuntoVentaElegibilidadReceRevision,
)
from app.models.idempotencia_fiscal import OperacionIdempotente
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta
from app.services.duplicados_lotes_service import (
    DuplicadosLoteError,
    DuplicadosLotesService,
)
from app.services.elegibilidad_rece_service import (
    ContextoElegibilidadRece,
    ElegibilidadReceService,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService


def test_distribucion_parcial_documento_evitas_barrido_cartesiano() -> None:
    accesos = 0

    class MiembroInstrumentado:
        def __init__(self, identificador: int, nombre_hash: str | None) -> None:
            self.id = identificador
            self._nombre_hash = nombre_hash

        @property
        def identidad_nombre_hash(self) -> str | None:
            nonlocal accesos
            accesos += 1
            return self._nombre_hash

    actuales = [MiembroInstrumentado(indice, "nombre-común") for indice in range(200)]
    anteriores = [
        MiembroInstrumentado(1000 + indice, "nombre-común") for indice in range(200)
    ]

    assert (
        DuplicadosLotesService._miembros_con_contraparte(
            actuales,
            anteriores,
            excluir_mismo_nombre_no_nulo=True,
        )
        == []
    )
    assert (
        DuplicadosLotesService._miembros_con_contraparte(
            anteriores,
            actuales,
            excluir_mismo_nombre_no_nulo=True,
        )
        == []
    )
    assert accesos == 2 * (len(actuales) + len(anteriores))

    fuente = [
        MiembroInstrumentado(2001, "igual"),
        MiembroInstrumentado(2002, None),
        MiembroInstrumentado(2003, "distinto"),
    ]
    contrapartes = [MiembroInstrumentado(3001, "igual")]
    assert [
        item.id
        for item in DuplicadosLotesService._miembros_con_contraparte(
            fuente,
            contrapartes,
            excluir_mismo_nombre_no_nulo=True,
        )
    ] == [2002, 2003]


def test_bloqueo_agrupa_por_operacion_y_estado_sin_duplicar_grupos() -> None:
    def member(
        group_id: int,
        relevance: str,
        operation_id: int,
    ) -> dict:
        return {
            "lado": "anterior",
            "miembro_clave": f"g-{group_id}",
            "grupo_id": group_id,
            "relevancia": relevance,
            "snapshot": {
                "decision": {
                    "reserva_operacion_id": (
                        operation_id if relevance == "reservado" else None
                    ),
                    "procedencia_operacion_id": (
                        operation_id if relevance == "incierto" else None
                    ),
                },
                "presentacion": {"detectado_at": "2026-09-06T10:00:00Z"},
            },
        }

    blocks = {
        "a": {
            "bloque_clave": "a",
            "antecedente_clave": "raiz-a",
            "miembros": {("anterior", "g-1"): member(1, "incierto", 10)},
        },
        "b": {
            "bloque_clave": "b",
            "antecedente_clave": "raiz-a",
            "miembros": {
                ("anterior", "g-1"): member(1, "incierto", 10),
                ("anterior", "g-2"): member(2, "reservado", 20),
            },
        },
        "c": {
            "bloque_clave": "c",
            "antecedente_clave": "raiz-b",
            "miembros": {("anterior", "g-3"): member(3, "reservado", 30)},
        },
    }

    selected = DuplicadosLotesService._bloqueo_desde_relacion({"_bloques": blocks})

    assert selected == {
        "referencia": "op-10",
        "estado": "incierta",
        "cantidad_afectada": 1,
        "detectado_at": "2026-09-06T10:00:00Z",
    }
    reserved = DuplicadosLotesService._bloqueo_desde_relacion(
        {"_bloques": {key: value for key, value in blocks.items() if key != "a"}}
    )
    assert reserved["referencia"] == "op-10"
    blocks["b"]["miembros"].pop(("anterior", "g-1"))
    reserved = DuplicadosLotesService._bloqueo_desde_relacion(
        {"_bloques": {key: value for key, value in blocks.items() if key != "a"}}
    )
    assert reserved["referencia"] == "op-20"
    assert reserved["cantidad_afectada"] == 1


@pytest.mark.asyncio
async def test_fuente_aceptacion_ordena_created_at_utc_consciente_y_sqlite_naive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = {
        "datos_hash": "datos",
        "seleccion_hash": "seleccion",
        "seleccion_original": [{"grupo_id": 1}],
    }
    aware = SimpleNamespace(
        id=10,
        operacion_id=1,
        formato="duplicados_relacion/1",
        created_at=datetime(2026, 9, 6, 12, tzinfo=timezone.utc),
        control_snapshot_json=snapshot,
    )
    reloaded_naive = SimpleNamespace(
        id=11,
        operacion_id=1,
        formato="duplicados_relacion/1",
        created_at=datetime(2026, 9, 6, 13),
        control_snapshot_json=snapshot,
    )

    class Result:
        def __init__(self, values):
            self.values = values

        def scalars(self):
            return self.values

    class FakeSession:
        def __init__(self):
            self.calls = 0

        async def execute(self, _statement):
            self.calls += 1
            return Result([1] if self.calls == 1 else [aware, reloaded_naive])

    service = DuplicadosLotesService(FakeSession())

    async def validate(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "_validar_integridad_generacion", validate)
    operation = SimpleNamespace(
        id=1,
        operacion_raiz_id=None,
        empresa_id=1,
        lote_id=1,
    )

    selected = await service._fuente_aceptacion_heredable(
        operation=operation,
        evidencia_id="v2.utc",
        control_snapshot=snapshot,
        ambiente="homologacion",
    )

    assert selected is reloaded_naive


async def _crear_escenario_coordinacion(session_factory):
    async with session_factory() as session:
        empresa = Empresa(
            razon_social="Empresa sintética",
            cuit="20999999991",
            condicion_iva="RI",
            domicilio="Calle sintética 123",
            localidad="Ciudad de prueba",
            provincia="Buenos Aires",
            codigo_postal="1000",
            email="sintetico@example.invalid",
            telefono="00000000",
            inicio_actividades=date(2020, 1, 1),
        )
        session.add(empresa)
        await session.flush()
        punto = PuntoVenta(
            empresa_id=empresa.id,
            numero=1,
            activo=True,
            es_webservice=True,
            revision_fiscal=1,
        )
        session.add(punto)
        await session.flush()
        revision = PuntoVentaElegibilidadReceRevision(
            empresa_id=empresa.id,
            punto_venta_id=punto.id,
            ambiente="homologacion",
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
                empresa_id=empresa.id,
                ambiente="homologacion",
                revision=0,
            )
        )
        lote = LoteComprobante(
            empresa_id=empresa.id,
            nombre_archivo="coordinacion-sintetica.xlsx",
            archivo_hash="c" * 64,
            estado="validado",
            total_filas=1,
            total_grupos=1,
            grupos_validos=1,
        )
        session.add(lote)
        await session.flush()
        grupo = LoteComprobanteGrupo(
            lote_id=lote.id,
            empresa_id=empresa.id,
            comprobante_ref="SINTETICO-1",
            orden=1,
            estado="validado",
            tipo_comprobante=6,
            punto_venta_numero=1,
            total_estimado=Decimal("1210.00"),
            punto_venta_id=punto.id,
            ambiente="homologacion",
            punto_venta_elegibilidad_revision_id=revision.id,
            punto_venta_revision_fiscal=1,
            duplicados_version="duplicados_lotes/v2",
            duplicados_cobertura="completa",
            huella_fiscal_completa="d" * 64,
            fecha_emision_normalizada=date(2026, 8, 9),
            moneda_duplicados="PES",
            cotizacion_duplicados="1",
            total_centavos=121000,
        )
        session.add(grupo)
        await session.flush()
        operaciones = [
            OperacionIdempotente(
                empresa_id=empresa.id,
                idempotency_key=f"coordinacion-{indice}",
                tipo_operacion="procesar_lote",
                payload_hash=f"{indice:064d}",
                estado="en_proceso",
                lote_id=lote.id,
            )
            for indice in (1, 2)
        ]
        session.add_all(operaciones)
        await session.commit()
        return (
            int(empresa.id),
            int(lote.id),
            int(grupo.id),
            [int(operacion.id) for operacion in operaciones],
        )


async def _crear_escenario_dos_lotes_coincidentes(session_factory):
    empresa_id, lote_id, grupo_id, operaciones = await _crear_escenario_coordinacion(
        session_factory
    )
    async with session_factory() as session:
        original = await session.get(LoteComprobanteGrupo, grupo_id)
        assert original is not None
        lote = LoteComprobante(
            empresa_id=empresa_id,
            nombre_archivo="coordinacion-sintetica-segunda.xlsx",
            archivo_hash="e" * 64,
            estado="validado",
            total_filas=1,
            total_grupos=1,
            grupos_validos=1,
        )
        session.add(lote)
        await session.flush()
        grupo = LoteComprobanteGrupo(
            lote_id=lote.id,
            empresa_id=empresa_id,
            comprobante_ref="SINTETICO-2",
            orden=1,
            estado="validado",
            tipo_comprobante=6,
            punto_venta_numero=1,
            total_estimado=Decimal("1210.00"),
            punto_venta_id=original.punto_venta_id,
            ambiente="homologacion",
            punto_venta_elegibilidad_revision_id=(
                original.punto_venta_elegibilidad_revision_id
            ),
            punto_venta_revision_fiscal=original.punto_venta_revision_fiscal,
            duplicados_version="duplicados_lotes/v2",
            duplicados_cobertura="completa",
            huella_fiscal_completa="d" * 64,
            fecha_emision_normalizada=date(2026, 8, 9),
            moneda_duplicados="PES",
            cotizacion_duplicados="1",
            total_centavos=121000,
        )
        session.add(grupo)
        await session.flush()
        await session.execute(
            update(OperacionIdempotente)
            .where(OperacionIdempotente.id == operaciones[1])
            .values(lote_id=lote.id)
        )
        await session.commit()
        return (
            empresa_id,
            [lote_id, int(lote.id)],
            [grupo_id, int(grupo.id)],
            operaciones,
        )


async def _ejecutar_contencion_dos_lotes(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "arca_env", "homologacion")
    (
        empresa_id,
        lotes,
        grupos,
        operaciones,
    ) = await _crear_escenario_dos_lotes_coincidentes(session_factory)
    entro_primera = asyncio.Event()
    liberar_primera = asyncio.Event()
    async with session_factory() as session_1, session_factory() as session_2:
        service_1 = DuplicadosLotesService(session_1)
        calcular_original = service_1.calcular_control

        async def calcular_bloqueado(**kwargs):
            entro_primera.set()
            await liberar_primera.wait()
            return await calcular_original(**kwargs)

        service_1.calcular_control = calcular_bloqueado
        primera = asyncio.create_task(
            service_1.evaluar_y_reservar(
                operacion_id=operaciones[0],
                lote_id=lotes[0],
                empresa_id=empresa_id,
                estados={"validado"},
                grupo_ids=None,
                aceptacion_recibida=None,
                solicitante_nombre="Primera persona",
                reservar=True,
                ambiente="homologacion",
            )
        )
        await asyncio.wait_for(entro_primera.wait(), timeout=5)
        segunda = asyncio.create_task(
            _evaluar_control_duplicados_operacion(
                db=session_2,
                operacion_id=operaciones[1],
                lote_id=lotes[1],
                empresa_id=empresa_id,
                estados={"validado"},
                grupo_ids=None,
                aceptacion_recibida=None,
                solicitante_nombre="Segunda persona",
            )
        )
        await asyncio.sleep(0.1)
        assert not segunda.done()
        liberar_primera.set()
        control_ganador, _, _ = await asyncio.wait_for(primera, timeout=5)
        assert control_ganador["bloqueo_operacion_ajena"] is None
        with pytest.raises(HTTPException) as error:
            await asyncio.wait_for(segunda, timeout=5)
        assert error.value.status_code == 409
        assert error.value.detail["categoria_error"] == "duplicado_operacion_en_curso"

    async with session_factory() as verifier:
        reservas = list(
            (
                await verifier.execute(
                    select(
                        LoteComprobanteGrupo.id,
                        LoteComprobanteGrupo.estado,
                        LoteComprobanteGrupo.duplicados_reserva_operacion_id,
                    )
                    .where(LoteComprobanteGrupo.id.in_(grupos))
                    .order_by(LoteComprobanteGrupo.id)
                )
            ).all()
        )
        assert reservas == [
            (grupos[0], "validado", operaciones[0]),
            (grupos[1], "validado", None),
        ]

    async with session_factory() as winner_session:
        control, _, _ = await DuplicadosLotesService(winner_session).evaluar_y_reservar(
            operacion_id=operaciones[0],
            lote_id=lotes[0],
            empresa_id=empresa_id,
            estados={"validado"},
            grupo_ids=None,
            aceptacion_recibida=None,
            solicitante_nombre="Primera persona",
            reservar=True,
            ambiente="homologacion",
        )
        assert control["bloqueo_operacion_ajena"] is None


@pytest.mark.asyncio
async def test_sqlite_dos_lotes_perdedor_no_reserva_ni_bloquea_ganador(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "duplicados-dos-lotes.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        await _ejecutar_contencion_dos_lotes(session_factory, monkeypatch)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_begin_immediate_serializa_y_revalida_reserva(tmp_path):
    """Dos conexiones reales no pueden reservar la misma selección en paralelo."""
    database_path = tmp_path / "duplicados-coordinacion.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    empresa_id, lote_id, grupo_id, operaciones = await _crear_escenario_coordinacion(
        session_factory
    )
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
        await entro_primera.wait()
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
        await asyncio.sleep(0.1)
        assert not segunda.done()
        liberar_primera.set()
        await primera
        with pytest.raises(DuplicadosLoteError, match="reservó"):
            await segunda

    async with session_factory() as verifier:
        reserva = await verifier.scalar(
            select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                LoteComprobanteGrupo.id == grupo_id
            )
        )
        revision = await verifier.scalar(
            select(LoteDuplicadosCoordinacion.revision).where(
                LoteDuplicadosCoordinacion.empresa_id == empresa_id,
                LoteDuplicadosCoordinacion.ambiente == "homologacion",
            )
        )
        assert reserva == operaciones[0]
        assert revision == 1

    await engine.dispose()


async def _crear_escenario_admision_legacy(session_factory):
    async with session_factory() as session:
        empresa = Empresa(
            razon_social="Empresa admisión legacy",
            cuit="20999999991",
            condicion_iva="RI",
            domicilio="Calle sintética 123",
            localidad="Ciudad de prueba",
            provincia="Buenos Aires",
            codigo_postal="1000",
            email="admision@example.invalid",
            telefono="00000000",
            inicio_actividades=date(2020, 1, 1),
        )
        session.add(empresa)
        await session.flush()
        punto = PuntoVenta(
            empresa_id=empresa.id,
            numero=1,
            activo=True,
            es_webservice=True,
            revision_fiscal=1,
            ultima_comprobacion_arca_en=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(punto)
        await session.flush()
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)
        revision = PuntoVentaElegibilidadReceRevision(
            empresa_id=empresa.id,
            punto_venta_id=punto.id,
            ambiente="produccion",
            revision=1,
            estado="verificado_rece",
            fuente="constancia_arca_atestada",
            evidencia_tipo="rece_aplicativo_web_services_v1",
            evidencia_sha256="a" * 64,
            clasificador_version="rece-v1-admision-test",
            empresa_cuit_snapshot=empresa.cuit,
            punto_venta_numero_snapshot=punto.numero,
            punto_revision_fiscal=1,
            documento_emitido_en=date(2026, 9, 7),
            vigente_hasta=date(2099, 12, 31),
            observado_en=ahora,
            verificado_en=ahora,
            actor_usuario_id_snapshot=1,
            created_at=ahora,
        )
        session.add(revision)
        await session.flush()
        session.add(
            PuntoVentaElegibilidadReceActual(
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
                ambiente="produccion",
                revision_actual_id=revision.id,
            )
        )
        lote = LoteComprobante(
            empresa_id=empresa.id,
            nombre_archivo="admision-legacy-sintetica.xlsx",
            archivo_hash="b" * 64,
            estado="validado",
            total_filas=1,
            total_grupos=1,
            grupos_validos=1,
        )
        session.add(lote)
        await session.flush()
        payload_grupo = {
            "empresa_id": int(empresa.id),
            "punto_venta_id": int(punto.id),
            "tipo_comprobante": 6,
        }
        grupo = LoteComprobanteGrupo(
            lote_id=lote.id,
            empresa_id=empresa.id,
            comprobante_ref="ADMISION-1",
            orden=1,
            estado="validado",
            tipo_comprobante=6,
            punto_venta_numero=1,
            total_estimado=Decimal("1210.00"),
            punto_venta_id=punto.id,
            ambiente="produccion",
            punto_venta_elegibilidad_revision_id=revision.id,
            punto_venta_revision_fiscal=1,
            payload_json=payload_grupo,
            duplicados_version="duplicados_lotes/v2",
            duplicados_cobertura="completa",
            huella_fiscal_completa="c" * 64,
            fecha_emision_normalizada=date(2026, 9, 7),
            moneda_duplicados="PES",
            cotizacion_duplicados="1",
            total_centavos=121000,
        )
        session.add(grupo)
        await session.flush()
        material_rece = {
            "grupos": [
                {
                    "grupo_id": int(grupo.id),
                    "empresa_id": int(empresa.id),
                    "punto_venta_id": int(punto.id),
                    "punto_venta_numero": 1,
                    "ambiente": "produccion",
                    "elegibilidad_revision_id": int(revision.id),
                    "punto_venta_revision_fiscal": 1,
                    "tipo_comprobante": 6,
                    "payload_hash": hashlib.sha256(
                        json.dumps(
                            payload_grupo,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                }
            ]
        }
        payload_operacion = {"lote_id": int(lote.id), "prueba": "admision"}
        payload_hash = IdempotenciaFiscalService.calcular_payload_hash(
            payload_operacion
        )
        owner = OperacionIdempotente(
            empresa_id=empresa.id,
            idempotency_key="admision-legacy-owner",
            tipo_operacion="procesar_lote",
            payload_hash=payload_hash,
            estado="en_proceso",
            lote_id=lote.id,
        )
        competidora = OperacionIdempotente(
            empresa_id=empresa.id,
            idempotency_key="admision-legacy-competidora",
            tipo_operacion="procesar_lote",
            payload_hash="d" * 64,
            estado="en_proceso",
            lote_id=lote.id,
        )
        session.add_all([owner, competidora])
        await session.flush()
        contexto = ContextoElegibilidadRece(
            empresa_id=int(empresa.id),
            punto_venta_id=int(punto.id),
            punto_venta_numero=1,
            ambiente="produccion",
            elegibilidad_revision_id=int(revision.id),
            punto_venta_revision_fiscal=1,
        )
        await ElegibilidadReceService(session).agregar_snapshots_a_operacion(
            owner,
            [contexto],
        )
        owner.estado = "interrumpida_pre_arca"
        lote.metadata_json = {
            "operacion_idempotente_id": int(owner.id),
            "confirmacion_duplicado_logico": True,
            "pf19b_rece_material": material_rece,
        }
        session.add(
            LoteDuplicadosCoordinacion(
                empresa_id=empresa.id,
                ambiente="produccion",
                revision=0,
            )
        )
        await session.commit()
        return (
            int(empresa.id),
            int(lote.id),
            int(grupo.id),
            int(owner.id),
            int(competidora.id),
            payload_operacion,
            material_rece,
        )


@pytest.mark.asyncio
async def test_admision_legacy_ganadora_reserva_y_competidora_revalida(
    tmp_path, monkeypatch
):
    """A conserva coordinador hasta reservar; B espera y observa esa reserva."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    database_path = tmp_path / "admision-legacy-contencion.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
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
    evaluar_original = DuplicadosLotesService.evaluar_y_reservar_bajo_coordinacion

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
            await asyncio.wait_for(entro_admision.wait(), timeout=5)
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
            await asyncio.sleep(0.1)
            assert not competidora.done()
            liberar_admision.set()
            resultado_a = await asyncio.wait_for(admision, timeout=5)
            assert resultado_a is not None
            with pytest.raises(DuplicadosLoteError, match="reservó"):
                await asyncio.wait_for(competidora, timeout=5)
        async with session_factory() as verifier:
            reserva = await verifier.scalar(
                select(LoteComprobanteGrupo.duplicados_reserva_operacion_id).where(
                    LoteComprobanteGrupo.id == grupo_id
                )
            )
            owner_version = await verifier.scalar(
                select(OperacionIdempotente.duplicados_version).where(
                    OperacionIdempotente.id == owner_id
                )
            )
            assert reserva == owner_id
            assert owner_version == "duplicados_lotes/v2"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_coordinador_revierte_revision_y_control_si_falla_a_mitad(tmp_path):
    """Un fallo interno no deja evidencia, revisión ni reserva parcial."""
    database_path = tmp_path / "duplicados-rollback.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    empresa_id, lote_id, grupo_id, operaciones = await _crear_escenario_coordinacion(
        session_factory
    )
    async with session_factory() as session:
        service = DuplicadosLotesService(session)
        calcular_original = service.calcular_control

        async def fallar_despues_del_control(**kwargs):
            await calcular_original(**kwargs)
            raise RuntimeError("fallo sintético a mitad de coordinación")

        service.calcular_control = fallar_despues_del_control
        with pytest.raises(RuntimeError, match="fallo sintético"):
            await service.evaluar_y_reservar(
                operacion_id=operaciones[0],
                lote_id=lote_id,
                empresa_id=empresa_id,
                estados={"validado"},
                grupo_ids=None,
                aceptacion_recibida=None,
                solicitante_nombre="Persona sintética",
                reservar=True,
                ambiente="homologacion",
            )

    async with session_factory() as verifier:
        operacion = await verifier.get(OperacionIdempotente, operaciones[0])
        grupo = await verifier.get(LoteComprobanteGrupo, grupo_id)
        revision = await verifier.scalar(
            select(LoteDuplicadosCoordinacion.revision).where(
                LoteDuplicadosCoordinacion.empresa_id == empresa_id,
                LoteDuplicadosCoordinacion.ambiente == "homologacion",
            )
        )
        assert operacion.control_duplicados_json is None
        assert grupo.duplicados_reserva_operacion_id is None
        assert revision == 0

    await engine.dispose()
