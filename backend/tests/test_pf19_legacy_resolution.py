"""Pruebas focalizadas del cierre administrativo legacy PF-19C."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import io
from pathlib import Path

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.scripts.pf19_legacy_resolution as pf19_cli
from app.core.database import Base, _habilitar_foreign_keys_sqlite
from app.models.empresa import Empresa
from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceRevision,
    PuntoVentaGuardaEmisionRece,
)
from app.models.idempotencia_fiscal import (
    IntentoEmisionFiscal,
    OperacionIdempotente,
    ResolucionLegacyPF19Journal,
)
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.schemas.comprobante import EmitirComprobanteResponse
from app.schemas.lote_comprobante import LoteAccionResponse, LoteProcesamientoResponse
from app.services.resolucion_legacy_pf19_service import (
    AdaptadorWSFEDiferidoLegacyPF19,
    BackupLegacyPF19,
    ConsultaComprobanteLegacyPF19,
    SolicitudApplyLegacyPF19,
    SolicitudPlanLegacyPF19,
    aplicar_resolucion_legacy_pf19,
    planificar_resolucion_legacy_pf19,
)


FIRMA_10005 = (
    "Error del servicio ARCA: ARCA devolvió errores globales al solicitar CAE: "
    "[10005] El punto de venta debe ser RECE"
)


class _ConsultasMenores:
    """Doble que solo confirma último autorizado menor en ambos ambientes."""

    def __init__(self) -> None:
        self.ambientes: list[str] = []

    async def ultimo_autorizado(self, ambiente: str, _punto: int, _tipo: int) -> int:
        self.ambientes.append(ambiente)
        return 0

    async def consultar(self, *_args: object) -> ConsultaComprobanteLegacyPF19:
        raise AssertionError(
            "No debe consultar el comprobante cuando el último es menor"
        )


class _ConsultasSinCambio:
    """Doble que fuerza una salida conservadora sin persistir un journal."""

    def __init__(self, *, falla: bool = False) -> None:
        self.llamadas = 0
        self.falla = falla

    async def ultimo_autorizado(self, _ambiente: str, _punto: int, _tipo: int) -> int:
        self.llamadas += 1
        if self.falla:
            raise RuntimeError("transporte sintético")
        return 1

    async def consultar(self, *_args: object) -> ConsultaComprobanteLegacyPF19:
        self.llamadas += 1
        return ConsultaComprobanteLegacyPF19(
            existe=True,
            autorizado=True,
            identidad_exacta=True,
        )


class _ConsultasUltimoInvalido:
    """Doble que devuelve valores fuera del contrato entero no negativo."""

    def __init__(self, valor: object) -> None:
        self.valor = valor

    async def ultimo_autorizado(self, *_args: object) -> object:
        return self.valor

    async def consultar(self, *_args: object) -> ConsultaComprobanteLegacyPF19:
        raise AssertionError("No debe consultar con último inválido")


class _ConsultasDualSegundo:
    """Confirma el primer ambiente y fuerza ambigüedad en el segundo."""

    def __init__(self, caso: str) -> None:
        self.caso = caso
        self.ambientes: list[str] = []

    async def ultimo_autorizado(self, ambiente: str, *_args: object) -> int:
        self.ambientes.append(ambiente)
        if ambiente == "homologacion":
            return 0
        if self.caso == "error":
            raise RuntimeError("error sintético")
        return 1

    async def consultar(self, *_args: object) -> ConsultaComprobanteLegacyPF19:
        return ConsultaComprobanteLegacyPF19(
            existe=True,
            autorizado=self.caso == "autorizado",
            identidad_exacta=True,
        )


class _FactoryProhibida:
    """Cuenta factories diferidas que nunca deben abrir WSAA/WSFE."""

    def __init__(self) -> None:
        self.llamadas = 0

    async def __call__(self, _ambiente: str) -> object:
        self.llamadas += 1
        raise AssertionError("No debe materializar un cliente ARCA")


async def _engine(tmp_path: Path) -> AsyncEngine:
    """Crea una base SQLite temporal aislada para el servicio legacy."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{(tmp_path / 'pf19c.db').as_posix()}",
        poolclass=StaticPool,
    )
    event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


async def _sembrar(
    engine: AsyncEngine,
    *,
    tipo_operacion: str = "emitir_comprobante",
    ambiente: str | None = None,
) -> tuple[int, int, int]:
    """Siembra un candidato individual legacy sin ambiente durable."""
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        empresa = Empresa(
            razon_social="Empresa sintética",
            cuit="20123456789",
            condicion_iva="RI",
            domicilio="Calle 1",
            localidad="Ciudad",
            provincia="Buenos Aires",
            codigo_postal="1000",
            inicio_actividades=date(2020, 1, 1),
        )
        punto = PuntoVenta(
            numero=4,
            es_webservice=True,
            revision_fiscal=1,
            empresa=empresa,
        )
        admin = Usuario(
            email="admin-pf19c@example.test",
            hashed_password="hash",
            nombre="Admin",
            activo=True,
            es_admin=True,
            empresa=empresa,
        )
        session.add_all([empresa, punto, admin])
        await session.flush()
        revision = None
        if ambiente is not None:
            observado_en = datetime(2026, 8, 8, 12, 0, 0)
            revision = PuntoVentaElegibilidadReceRevision(
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
                ambiente=ambiente,
                revision=1,
                estado="verificado_rece",
                fuente="constancia_arca_atestada",
                evidencia_tipo="rece_aplicativo_web_services_v1",
                evidencia_sha256="f" * 64,
                clasificador_version="rece-v1-test",
                empresa_cuit_snapshot=empresa.cuit,
                punto_venta_numero_snapshot=punto.numero,
                punto_revision_fiscal=1,
                documento_emitido_en=date(2026, 8, 8),
                vigente_hasta=date(2026, 8, 15),
                observado_en=observado_en,
                verificado_en=observado_en,
                creado_por_usuario_id=admin.id,
                actor_usuario_id_snapshot=admin.id,
                created_at=observado_en,
            )
            session.add(revision)
            await session.flush()
        operacion = OperacionIdempotente(
            idempotency_key="pf19c-test",
            tipo_operacion=tipo_operacion,
            payload_hash="a" * 64,
            estado="requiere_reconciliacion",
            response_json={"errores": [FIRMA_10005]},
            rece_snapshot_hash="e" * 64 if ambiente is not None else None,
            empresa_id=empresa.id,
            usuario_id=admin.id,
        )
        session.add(operacion)
        await session.flush()
        guarda = None
        if revision is not None and ambiente is not None:
            session.add(
                OperacionIdempotenteElegibilidadRece(
                    operacion_id=operacion.id,
                    empresa_id=empresa.id,
                    punto_venta_id=punto.id,
                    ambiente=ambiente,
                    elegibilidad_revision_id=revision.id,
                    punto_venta_revision_fiscal=1,
                )
            )
            await session.flush()
            guarda = PuntoVentaGuardaEmisionRece(
                token="9" * 64,
                fase="requiere_reconciliacion",
                operacion_id=operacion.id,
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
                ambiente=ambiente,
                elegibilidad_revision_id=revision.id,
                punto_venta_revision_fiscal=1,
                arca_iniciada_en=datetime(2026, 8, 8, 12, 1, 0),
            )
            session.add(guarda)
            await session.flush()
        lote = None
        grupo = None
        if tipo_operacion != "emitir_comprobante":
            lote = LoteComprobante(
                nombre_archivo="legacy.xlsx",
                archivo_hash="e" * 64,
                estado="requiere_reconciliacion",
                modo_procesamiento="sincronico",
                procesamiento_async=False,
                total_filas=1,
                total_grupos=1,
                empresa_id=empresa.id,
            )
            session.add(lote)
            await session.flush()
            operacion.lote_id = lote.id
            grupo = LoteComprobanteGrupo(
                comprobante_ref="legacy-1",
                orden=1,
                estado="requiere_reconciliacion",
                tipo_comprobante=6,
                punto_venta_numero=4,
                total_estimado=Decimal("121.00"),
                mensajes_json=[FIRMA_10005],
                empresa_id=empresa.id,
                lote_id=lote.id,
            )
            session.add(grupo)
            await session.flush()
            session.add(
                LoteComprobanteFila(
                    fila_excel=2,
                    comprobante_ref="legacy-1",
                    estado="requiere_reconciliacion",
                    lote_id=lote.id,
                    grupo_id=grupo.id,
                )
            )
        intento = IntentoEmisionFiscal(
            tipo_comprobante=6,
            punto_venta_numero=4,
            numero_planificado=1,
            fecha_emision=date(2026, 8, 8),
            total=Decimal("121.00"),
            payload_hash="b" * 64,
            huella_logica="c" * 64,
            estado="requiere_reconciliacion",
            categoria_error="arca_batch_sin_respuesta",
            operacion_id=operacion.id,
            empresa_id=empresa.id,
            punto_venta_id=punto.id,
            lote_id=lote.id if lote is not None else None,
            grupo_id=grupo.id if grupo is not None else None,
            ambiente=ambiente,
            punto_venta_elegibilidad_revision_id=(
                revision.id if revision is not None else None
            ),
            punto_venta_revision_fiscal=1 if revision is not None else None,
            guarda_rece_id=guarda.id if guarda is not None else None,
        )
        session.add(intento)
        await session.commit()
        return intento.id, empresa.id, admin.id


def _solicitud_apply(plan, admin_id: int) -> SolicitudApplyLegacyPF19:
    """Construye una confirmación completa y sintética para las pruebas."""
    return SolicitudApplyLegacyPF19(
        plan=plan,
        actor_usuario_id=admin_id,
        confirmacion="APLICAR_CIERRE_LEGACY_PF19",
        ventana_mantenimiento_confirmada=True,
        backup=BackupLegacyPF19(
            identificador="backup-pf19c",
            timestamp="2026-08-09T00:00:00Z",
            proposito="cierre legacy pf19c",
            referencia_codigo="test",
            sha256="d" * 64,
        ),
    )


@pytest.mark.parametrize(
    ("campo", "valor"),
    (
        ("identificador", " C:/backup.db "),
        ("timestamp", "2026-08-09T00:00:00"),
        ("referencia_codigo", "postgresql://host/base"),
        ("proposito", "token=secreto"),
        ("identificador", "127.0.0.1"),
        ("referencia_codigo", "postgresql-localhost-admin"),
        ("proposito", "cierre legacy genérico"),
    ),
)
def test_backup_rechaza_metadatos_no_sanitizados(campo: str, valor: str) -> None:
    """Rutas, DSN, credenciales y timestamps sin UTC no forman una solicitud."""
    datos = {
        "identificador": "backup-pf19c",
        "timestamp": "2026-08-09T00:00:00Z",
        "proposito": "cierre legacy pf19c",
        "referencia_codigo": "commit-test",
        "sha256": "d" * 64,
    }
    datos[campo] = valor
    with pytest.raises(Exception):
        BackupLegacyPF19(**datos)


def test_cli_no_expone_selector_manual_de_ambiente() -> None:
    """La CLI deriva ambientes del intento y no ofrece un override administrativo."""
    parser = pf19_cli.construir_parser()
    opciones = {
        opcion
        for accion in parser._actions
        for opcion in getattr(accion, "option_strings", ())
    }
    assert "--ambiente" not in opciones
    assert "--ambiente-consultado" not in opciones


def test_cli_sanitiza_errores_internos(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """La salida privada no imprime secretos provenientes de fallos internos."""

    async def fallar(_args: object) -> dict[str, object]:
        raise RuntimeError("token=valor-que-no-debe-salir")

    monkeypatch.setattr(pf19_cli, "ejecutar_y_disponer", fallar)
    codigo = pf19_cli.main(
        [
            "plan",
            "--intento-id",
            "1",
            "--empresa-id",
            "1",
            "--punto-venta",
            "4",
            "--tipo-comprobante",
            "6",
        ]
    )
    salida = capsys.readouterr()
    assert codigo == 2
    assert "valor-que-no-debe-salir" not in salida.err
    assert "error interno" in salida.err


def _plan_cli_json(sentinel: str) -> str:
    """Construye un plan sintético cuyo contenido simula evidencia privada."""
    return pf19_cli.PlanLegacyPF19(
        accion="cerrar_legacy_sin_autorizacion_verificada",
        intento_id=1,
        empresa_id=1,
        punto_venta=4,
        tipo_comprobante=6,
        numero_planificado=1,
        ambientes_consultados=("homologacion", "produccion"),
        estado_intento="requiere_reconciliacion",
        categoria_error="arca_batch_sin_respuesta",
        version_intento="version-sintetica",
        precondiciones={"evidencia_privada": sentinel},
        plan_sha256="a" * 64,
    ).model_dump_json()


def _argumentos_cli_apply(plan_file: str) -> list[str]:
    """Devuelve los flags completos del apply sin incluir contenido fiscal."""
    return [
        "apply",
        "--intento-id",
        "1",
        "--empresa-id",
        "1",
        "--punto-venta",
        "4",
        "--tipo-comprobante",
        "6",
        "--plan-file",
        plan_file,
        "--actor-usuario-id",
        "1",
        "--confirmar",
        "--ventana-mantenimiento-confirmada",
        "--backup-identificador",
        "backup-pf19c",
        "--backup-timestamp",
        "2026-08-09T00:00:00Z",
        "--backup-proposito",
        "cierre legacy pf19c",
        "--backup-referencia-codigo",
        "test",
        "--backup-sha256",
        "d" * 64,
    ]


class _SesionCli:
    """Contexto mínimo que prueba que el plan se valida antes de abrir la base."""

    async def __aenter__(self) -> object:
        """Devuelve un marcador no persistente para el doble de apply."""
        return object()

    async def __aexit__(self, *_args: object) -> bool:
        """No suprime excepciones de la prueba."""
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize("origen", ("stdin", "archivo"))
async def test_cli_apply_lee_plan_privado_fuera_de_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    origen: str,
) -> None:
    """Apply recibe el plan por stdin/archivo y nunca por los argumentos del proceso."""
    sentinel = "CUIT-PRIVADO-20123456789-CAE-NO-IMPRIMIR"
    contenido = _plan_cli_json(sentinel).encode("utf-8")
    if origen == "stdin":
        plan_file = "-"
        monkeypatch.setattr(
            pf19_cli.sys,
            "stdin",
            io.TextIOWrapper(io.BytesIO(contenido), encoding="utf-8"),
        )
    else:
        archivo = tmp_path / "plan-privado.json"
        archivo.write_bytes(contenido)
        archivo.chmod(0o600)
        plan_file = str(archivo)
    argumentos = _argumentos_cli_apply(plan_file)
    monkeypatch.setattr(pf19_cli.sys, "argv", ["pf19-legacy", *argumentos])
    capturado: dict[str, object] = {}

    async def aplicar_falso(
        _session: object,
        solicitud: SolicitudApplyLegacyPF19,
        _adaptador: object,
    ) -> dict[str, object]:
        capturado["solicitud"] = solicitud
        return {"resultado": "cerrado_sintetico"}

    monkeypatch.setattr(pf19_cli, "AsyncSessionLocal", lambda: _SesionCli())
    monkeypatch.setattr(pf19_cli, "aplicar_resolucion_legacy_pf19", aplicar_falso)

    resultado = await pf19_cli.ejecutar(
        pf19_cli.construir_parser().parse_args(argumentos)
    )

    solicitud = capturado["solicitud"]
    assert isinstance(solicitud, SolicitudApplyLegacyPF19)
    assert solicitud.plan.precondiciones["evidencia_privada"] == sentinel
    assert sentinel not in pf19_cli.sys.argv
    assert resultado == {"resultado": "cerrado_sintetico"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "contenido",
    (b"{", b"x" * (pf19_cli.MAX_PLAN_BYTES + 1)),
    ids=("json_invalido", "demasiado_grande"),
)
async def test_cli_apply_aborta_plan_invalido_antes_de_cliente_o_mutacion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    contenido: bytes,
) -> None:
    """Un plan inválido o sobredimensionado no abre sesión ni alcanza apply."""
    archivo = tmp_path / "plan-invalido.json"
    archivo.write_bytes(contenido)
    archivo.chmod(0o600)
    intentos: list[str] = []

    def no_abrir_sesion() -> object:
        intentos.append("sesion")
        raise AssertionError("No debe abrir base antes de validar el plan")

    async def no_aplicar(*_args: object) -> dict[str, object]:
        intentos.append("apply")
        raise AssertionError("No debe mutar antes de validar el plan")

    monkeypatch.setattr(pf19_cli, "AsyncSessionLocal", no_abrir_sesion)
    monkeypatch.setattr(pf19_cli, "aplicar_resolucion_legacy_pf19", no_aplicar)
    args = pf19_cli.construir_parser().parse_args(_argumentos_cli_apply(str(archivo)))

    with pytest.raises(Exception, match="plan privado|tamaño permitido"):
        await pf19_cli.ejecutar(args)
    assert intentos == []


def test_cli_rechaza_plan_json_sin_reflejar_su_contenido(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """La opción retirada corta la ejecución sin imprimir la evidencia recibida."""
    sentinel = "CUIT-PRIVADO-20123456789-CAE-NO-IMPRIMIR"
    with pytest.raises(SystemExit) as salida:
        pf19_cli.construir_parser().parse_args(["plan", "--plan-json", sentinel])
    capturado = capsys.readouterr()
    assert salida.value.code == 2
    assert sentinel not in capturado.err


@pytest.mark.parametrize("campo", ("existe", "autorizado", "identidad_exacta"))
def test_consulta_externa_exige_flags_bool_exactos(campo: str) -> None:
    """Enteros truthy no atraviesan la frontera de FECompConsultar."""
    datos = {"existe": True, "autorizado": False, "identidad_exacta": True}
    datos[campo] = 1
    with pytest.raises(Exception, match="flags de consulta inválidos"):
        ConsultaComprobanteLegacyPF19(**datos)


@pytest.mark.asyncio
async def test_plan_restaura_query_only_y_permite_escritura_con_pool_unico(
    tmp_path: Path,
) -> None:
    """Plan read-only restaura el PRAGMA exacto antes de devolver la conexión."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(engine)
    await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    async with engine.connect() as connection:
        assert (
            int((await connection.execute(text("PRAGMA query_only"))).scalar_one()) == 0
        )
        await connection.rollback()
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        actor = await session.get(Usuario, admin_id)
        assert actor is not None
        actor.nombre = "Admin luego del plan"
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_revalida_backup_interno_antes_de_factory(
    tmp_path: Path,
) -> None:
    """Un objeto interno construido sin validar tampoco alcanza la frontera ARCA."""
    engine = await _engine(tmp_path)
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
    backup_invalido = BackupLegacyPF19.model_construct(
        identificador="C:/backup.db",
        timestamp="2026-08-09T00:00:00Z",
        proposito="cierre legacy pf19c",
        referencia_codigo="test",
        sha256="d" * 64,
    )
    solicitud = SolicitudApplyLegacyPF19(
        plan=plan,
        actor_usuario_id=admin_id,
        confirmacion="APLICAR_CIERRE_LEGACY_PF19",
        ventana_mantenimiento_confirmada=True,
        backup=backup_invalido,
    )
    factory = _FactoryProhibida()
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        with pytest.raises(Exception, match="backup legacy no son válidos"):
            await aplicar_resolucion_legacy_pf19(
                session,
                solicitud,
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.estado == "requiere_reconciliacion"
    await engine.dispose()


@pytest.mark.asyncio
async def test_plan_dual_y_apply_cierra_unicamente_con_ausencia_en_ambos(
    tmp_path: Path,
) -> None:
    """Legacy sin ambiente exige ambos últimos menores y deja journal único."""
    engine = await _engine(tmp_path)
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
    assert plan.ambientes_consultados == ("homologacion", "produccion")

    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    consultas = _ConsultasMenores()
    async with fabrica() as session:
        resultado = await aplicar_resolucion_legacy_pf19(
            session,
            SolicitudApplyLegacyPF19(
                plan=plan,
                actor_usuario_id=admin_id,
                confirmacion="APLICAR_CIERRE_LEGACY_PF19",
                ventana_mantenimiento_confirmada=True,
                backup=BackupLegacyPF19(
                    identificador="backup-pf19c",
                    timestamp="2026-08-09T00:00:00Z",
                    proposito="cierre legacy pf19c",
                    referencia_codigo="test",
                    sha256="d" * 64,
                ),
            ),
            consultas,
        )
        assert resultado["resultado"] == "cerrado"
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None
        assert intento.estado == "fallido_verificado"
        assert intento.categoria_error == "legacy_sin_autorizacion_verificada"
        journals = (
            (await session.execute(select(ResolucionLegacyPF19Journal))).scalars().all()
        )
        assert len(journals) == 1
        assert journals[0].actor_usuario_id == admin_id
        operacion = await session.get(OperacionIdempotente, intento.operacion_id)
        assert operacion is not None
        replay = EmitirComprobanteResponse.model_validate(operacion.response_json)
        assert replay.exito is False
        assert replay.categoria_error == "legacy_sin_autorizacion_verificada"
        assert operacion.estado == "fallido_verificado"
    assert consultas.ambientes == ["homologacion", "produccion"]

    async with fabrica() as session:
        replay_consultas = _ConsultasMenores()
        replay = await aplicar_resolucion_legacy_pf19(
            session,
            SolicitudApplyLegacyPF19(
                plan=plan,
                actor_usuario_id=admin_id,
                confirmacion="APLICAR_CIERRE_LEGACY_PF19",
                ventana_mantenimiento_confirmada=True,
                backup=BackupLegacyPF19(
                    identificador="backup-pf19c",
                    timestamp="2026-08-09T00:00:00Z",
                    proposito="cierre legacy pf19c",
                    referencia_codigo="test",
                    sha256="d" * 64,
                ),
            ),
            replay_consultas,
        )
        assert replay["resultado"] == "replay_idempotente"
        assert replay_consultas.ambientes == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_ambiente_durable_consulta_unicamente_el_ambiente_exacto(
    tmp_path: Path,
) -> None:
    """Un ambiente durable no se amplía ni queda sujeto a elección manual."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(
        engine,
        ambiente="produccion",
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    plan = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    assert plan.ambientes_consultados == ("produccion",)
    consultas = _ConsultasMenores()
    async with fabrica() as session:
        resultado = await aplicar_resolucion_legacy_pf19(
            session, _solicitud_apply(plan, admin_id), consultas
        )
    assert resultado["resultado"] == "cerrado"
    assert consultas.ambientes == ["produccion"]
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("caso", ("autorizado", "no_terminal", "error"))
async def test_dual_segundo_ambiente_ambiguo_no_cierra(
    tmp_path: Path,
    caso: str,
) -> None:
    """Ambos ambientes deben probar último menor; cualquier ambigüedad conserva estado."""
    engine = await _engine(tmp_path)
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
    consultas = _ConsultasDualSegundo(caso)
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        resultado = await aplicar_resolucion_legacy_pf19(
            session, _solicitud_apply(plan, admin_id), consultas
        )
        assert resultado["resultado"] == "sin_cambio"
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.estado == "requiere_reconciliacion"
        assert (
            await session.execute(select(ResolucionLegacyPF19Journal))
        ).scalars().all() == []
    assert consultas.ambientes == ["homologacion", "produccion"]
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("valor", (True, -1, 1.5))
async def test_ultimo_autorizado_invalido_no_cierra(
    tmp_path: Path,
    valor: object,
) -> None:
    """El puerto exige un int exacto y no negativo."""
    engine = await _engine(tmp_path)
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
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        resultado = await aplicar_resolucion_legacy_pf19(
            session, _solicitud_apply(plan, admin_id), _ConsultasUltimoInvalido(valor)
        )
        assert resultado["motivo"] == "ultimo_autorizado_invalido"
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.estado == "requiere_reconciliacion"
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("falla", [False, True])
async def test_apply_ambiguo_no_crea_journal_ni_mutacion(
    tmp_path: Path,
    falla: bool,
) -> None:
    """Un último mayor o un error externo dejan el intento tal como estaba."""
    engine = await _engine(tmp_path)
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
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        consultas = _ConsultasSinCambio(falla=falla)
        resultado = await aplicar_resolucion_legacy_pf19(
            session,
            _solicitud_apply(plan, admin_id),
            consultas,
        )
        assert resultado["resultado"] == "sin_cambio"
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None
        assert intento.estado == "requiere_reconciliacion"
        assert (
            await session.execute(select(ResolucionLegacyPF19Journal))
        ).scalars().all() == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_plan_alterado_no_consulta_ni_muta(tmp_path: Path) -> None:
    """Un digest distinto aborta antes de la primera llamada externa."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(engine)
    plan_original = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    plan = plan_original.model_copy(update={"plan_sha256": "0" * 64})
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        factory = _FactoryProhibida()
        with pytest.raises(Exception, match="no coincide con su SHA-256"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None
        assert intento.estado == "requiere_reconciliacion"
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tipo_operacion", "modelo_replay"),
    (
        ("procesar_lote", LoteProcesamientoResponse),
        ("reintentar_fallidos_lote", LoteAccionResponse),
    ),
)
async def test_apply_lote_publica_replay_dto_y_estado_terminal(
    tmp_path: Path,
    tipo_operacion: str,
    modelo_replay: type[LoteProcesamientoResponse] | type[LoteAccionResponse],
) -> None:
    """Los cierres legacy de lote conservan el DTO que reusan las APIs."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(
        engine,
        tipo_operacion=tipo_operacion,
    )
    plan = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        resultado = await aplicar_resolucion_legacy_pf19(
            session,
            _solicitud_apply(plan, admin_id),
            _ConsultasMenores(),
        )
        assert resultado["resultado"] == "cerrado"
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.operacion_id is not None
        operacion = await session.get(OperacionIdempotente, intento.operacion_id)
        assert operacion is not None
        assert operacion.estado == "finalizado"
        replay = modelo_replay.model_validate(operacion.response_json)
        assert replay.lote.estado == "fallido"
        assert replay.lote.grupos_fallidos == 1
        grupo = (
            await session.execute(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == operacion.lote_id
                )
            )
        ).scalar_one()
        assert grupo.mensajes_json == ["legacy_sin_autorizacion_verificada"]
    factory = _FactoryProhibida()
    async with fabrica() as session:
        replay = await aplicar_resolucion_legacy_pf19(
            session,
            _solicitud_apply(plan, admin_id),
            AdaptadorWSFEDiferidoLegacyPF19(factory),
        )
        assert replay["resultado"] == "replay_idempotente"
        assert factory.llamadas == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_cas_loser_no_consulta_ni_mutacion(tmp_path: Path) -> None:
    """Una operación modificada entre plan y apply aborta antes de consultar ARCA."""
    engine = await _engine(tmp_path)
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
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.operacion_id is not None
        operacion = await session.get(OperacionIdempotente, intento.operacion_id)
        assert operacion is not None
        operacion.response_json = {"errores": ["estado cambiado"]}
        await session.commit()
    async with fabrica() as session:
        factory = _FactoryProhibida()
        with pytest.raises(Exception, match="no cumple las precondiciones"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None
        assert intento.estado == "requiere_reconciliacion"
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cambio", "valor"),
    (
        ("numero_planificado", 99),
        ("ambientes_consultados", ("produccion",)),
    ),
)
async def test_apply_rechaza_contenido_plan_adulterado_antes_de_consultar(
    tmp_path: Path,
    cambio: str,
    valor: object,
) -> None:
    """Número o ambientes adulterados no llegan a locks ni a la frontera externa."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(engine)
    original = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    adulterado = original.model_copy(update={cambio: valor})
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        factory = _FactoryProhibida()
        with pytest.raises(Exception, match="no coincide con su SHA-256"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(adulterado, admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.estado == "requiere_reconciliacion"
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(("activo", "es_admin"), ((False, True), (True, False)))
async def test_apply_exige_admin_activo_sin_consultar(
    tmp_path: Path,
    activo: bool,
    es_admin: bool,
) -> None:
    """Actores inactivos o no administradores abortan con cero consultas."""
    engine = await _engine(tmp_path)
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
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        actor = await session.get(Usuario, admin_id)
        assert actor is not None
        actor.activo = activo
        actor.es_admin = es_admin
        await session.commit()
    async with fabrica() as session:
        factory = _FactoryProhibida()
        with pytest.raises(Exception, match="administrador activo"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_rechaza_admin_de_otro_emisor_sin_factory(
    tmp_path: Path,
) -> None:
    """Un administrador válido de otra empresa no tiene autoridad sobre el plan."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, _admin_id = await _sembrar(engine)
    plan = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        otra_empresa = Empresa(
            razon_social="Otro emisor sintético",
            cuit="20987654321",
            condicion_iva="RI",
            domicilio="Calle 2",
            localidad="Ciudad",
            provincia="Buenos Aires",
            codigo_postal="1001",
            inicio_actividades=date(2021, 1, 1),
        )
        otro_admin = Usuario(
            email="otro-admin-pf19c@example.test",
            hashed_password="hash",
            nombre="Otro Admin",
            activo=True,
            es_admin=True,
            empresa=otra_empresa,
        )
        session.add_all([otra_empresa, otro_admin])
        await session.commit()
        otro_admin_id = otro_admin.id
    factory = _FactoryProhibida()
    async with fabrica() as session:
        with pytest.raises(Exception, match="mismo emisor"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, otro_admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.estado == "requiere_reconciliacion"
        assert (
            await session.execute(select(ResolucionLegacyPF19Journal))
        ).scalars().all() == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_rollback_inyectado_revierte_grafo_y_journal(
    tmp_path: Path,
) -> None:
    """Un fallo de commit posterior al cierre revierte grafo, respuesta y journal."""
    engine = await _engine(tmp_path)
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

    def fallar(_session: object) -> None:
        raise RuntimeError("fallo inyectado")

    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        event.listen(session.sync_session, "before_commit", fallar, once=True)
        with pytest.raises(RuntimeError, match="fallo inyectado"):
            await aplicar_resolucion_legacy_pf19(
                session, _solicitud_apply(plan, admin_id), _ConsultasMenores()
            )
    async with fabrica() as session:
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.estado == "requiere_reconciliacion"
        assert intento.operacion_id is not None
        operacion = await session.get(OperacionIdempotente, intento.operacion_id)
        assert operacion is not None
        assert operacion.estado == "requiere_reconciliacion"
        assert operacion.response_json == {"errores": [FIRMA_10005]}
        assert (
            await session.execute(select(ResolucionLegacyPF19Journal))
        ).scalars().all() == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_replay_journal_divergente_aborta_sin_consultar(tmp_path: Path) -> None:
    """Un commit confirmado pero grafo alterado no se acepta como replay sano."""
    engine = await _engine(tmp_path)
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
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        await aplicar_resolucion_legacy_pf19(
            session, _solicitud_apply(plan, admin_id), _ConsultasMenores()
        )
    async with fabrica() as session:
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.operacion_id is not None
        operacion = await session.get(OperacionIdempotente, intento.operacion_id)
        assert operacion is not None
        operacion.response_json = {"divergente": True}
        await session.commit()
    async with fabrica() as session:
        consultas = _ConsultasMenores()
        with pytest.raises(Exception, match="respuesta terminal exacta"):
            await aplicar_resolucion_legacy_pf19(
                session, _solicitud_apply(plan, admin_id), consultas
            )
        assert consultas.ambientes == []
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutacion", ("cae", "identidad", "evidencia", "journal"))
async def test_replay_rechaza_identidad_o_journal_terminal_divergente(
    tmp_path: Path,
    mutacion: str,
) -> None:
    """Replay no confía solo en estado/categoría cuando cambió evidencia durable."""
    engine = await _engine(tmp_path)
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
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        await aplicar_resolucion_legacy_pf19(
            session,
            _solicitud_apply(plan, admin_id),
            _ConsultasMenores(),
        )
    async with fabrica() as session:
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None
        if mutacion == "cae":
            intento.cae = "1" * 14
        elif mutacion == "identidad":
            intento.numero_planificado = 99
        elif mutacion == "evidencia":
            intento.errores_arca_json = []
        else:
            journal = (
                await session.execute(select(ResolucionLegacyPF19Journal))
            ).scalar_one()
            journal.resultado_consultas_json = {}
        await session.commit()
    factory = _FactoryProhibida()
    async with fabrica() as session:
        with pytest.raises(Exception, match="diverge|identidad fiscal"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_apply_batch_preserva_intento_terminal_sibling(tmp_path: Path) -> None:
    """Batch cierra un objetivo incierto sin reescribir intentos históricos terminales."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(
        engine,
        tipo_operacion="procesar_lote",
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None
        sibling = IntentoEmisionFiscal(
            tipo_comprobante=intento.tipo_comprobante,
            punto_venta_numero=intento.punto_venta_numero,
            numero_planificado=2,
            fecha_emision=intento.fecha_emision,
            total=intento.total,
            payload_hash="4" * 64,
            huella_logica="5" * 64,
            estado="fallido_verificado",
            categoria_error="sibling_terminal_sintetico",
            operacion_id=intento.operacion_id,
            empresa_id=intento.empresa_id,
            punto_venta_id=intento.punto_venta_id,
            lote_id=intento.lote_id,
            grupo_id=intento.grupo_id,
        )
        session.add(sibling)
        await session.commit()
        sibling_id = sibling.id
    plan = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    async with fabrica() as session:
        resultado = await aplicar_resolucion_legacy_pf19(
            session,
            _solicitud_apply(plan, admin_id),
            _ConsultasMenores(),
        )
        assert resultado["resultado"] == "cerrado"
        sibling = await session.get(IntentoEmisionFiscal, sibling_id)
        assert sibling is not None
        assert sibling.estado == "fallido_verificado"
        assert sibling.categoria_error == "sibling_terminal_sintetico"
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutacion", ("grupo_cae", "fila_datos"))
async def test_replay_batch_rechaza_evidencia_terminal_divergente(
    tmp_path: Path,
    mutacion: str,
) -> None:
    """El replay batch autentica evidencia fiscal del grupo y contenido de filas."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(
        engine,
        tipo_operacion="procesar_lote",
    )
    plan = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        await aplicar_resolucion_legacy_pf19(
            session,
            _solicitud_apply(plan, admin_id),
            _ConsultasMenores(),
        )
    async with fabrica() as session:
        if mutacion == "grupo_cae":
            grupo = (await session.execute(select(LoteComprobanteGrupo))).scalar_one()
            grupo.cae = "2" * 14
        else:
            fila = (await session.execute(select(LoteComprobanteFila))).scalar_one()
            fila.datos_json = {"divergente": True}
        await session.commit()
    factory = _FactoryProhibida()
    async with fabrica() as session:
        with pytest.raises(Exception, match="grupo objetivo|fila objetivo"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_replay_batch_rechaza_lote_y_dto_coordinadamente_mutados(
    tmp_path: Path,
) -> None:
    """El journal ancla el DTO terminal aunque lote y response cambien juntos."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(
        engine,
        tipo_operacion="procesar_lote",
    )
    plan = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        await aplicar_resolucion_legacy_pf19(
            session,
            _solicitud_apply(plan, admin_id),
            _ConsultasMenores(),
        )
    async with fabrica() as session:
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.operacion_id is not None
        operacion = await session.get(OperacionIdempotente, intento.operacion_id)
        lote = await session.get(LoteComprobante, intento.lote_id)
        assert operacion is not None and lote is not None
        lote.total_filas = 999
        response_mutado = deepcopy(operacion.response_json)
        response_mutado["lote"]["total_filas"] = 999
        operacion.response_json = response_mutado
        await session.commit()
    factory = _FactoryProhibida()
    async with fabrica() as session:
        with pytest.raises(Exception, match="respuesta terminal exacta"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_cambio_de_contenido_fila_aborta_antes_de_factory(tmp_path: Path) -> None:
    """Mensajes/datos de fila forman parte de la versión aunque no exista updated_at."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(
        engine,
        tipo_operacion="procesar_lote",
    )
    plan = await planificar_resolucion_legacy_pf19(
        engine,
        SolicitudPlanLegacyPF19(
            intento_id=intento_id,
            empresa_id=empresa_id,
            punto_venta=4,
            tipo_comprobante=6,
        ),
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        fila = (await session.execute(select(LoteComprobanteFila))).scalar_one()
        fila.mensajes_json = ["contenido modificado"]
        await session.commit()
    factory = _FactoryProhibida()
    async with fabrica() as session:
        with pytest.raises(Exception, match="plan legacy cambió"):
            await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, admin_id),
                AdaptadorWSFEDiferidoLegacyPF19(factory),
            )
        assert factory.llamadas == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_commit_ambiguo_se_resuelve_por_replay_sin_factory(
    tmp_path: Path,
) -> None:
    """Si el caller pierde la respuesta post-commit, el retry confirma un único journal."""
    engine = await _engine(tmp_path)
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
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def aplicar_y_perder_respuesta() -> None:
        async with fabrica() as session:
            resultado = await aplicar_resolucion_legacy_pf19(
                session,
                _solicitud_apply(plan, admin_id),
                _ConsultasMenores(),
            )
            assert resultado["resultado"] == "cerrado"
        raise ConnectionError("respuesta post-commit perdida")

    with pytest.raises(ConnectionError, match="post-commit"):
        await aplicar_y_perder_respuesta()
    factory = _FactoryProhibida()
    async with fabrica() as session:
        replay = await aplicar_resolucion_legacy_pf19(
            session,
            _solicitud_apply(plan, admin_id),
            AdaptadorWSFEDiferidoLegacyPF19(factory),
        )
        assert replay["resultado"] == "replay_idempotente"
        assert factory.llamadas == 0
        cantidad = await session.scalar(
            select(func.count()).select_from(ResolucionLegacyPF19Journal)
        )
        assert int(cantidad or 0) == 1
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tipo_operacion", "mensaje"),
    (
        ("emitir_comprobante", "forma de lote inconsistente"),
        ("procesar_lote", "lote y grupo exactos"),
    ),
)
async def test_plan_rechaza_forma_de_operacion_inconsistente(
    tmp_path: Path,
    tipo_operacion: str,
    mensaje: str,
) -> None:
    """Individual y batch exigen referencias de grafo exactas antes de consultar."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, _admin_id = await _sembrar(
        engine,
        tipo_operacion=tipo_operacion,
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None and intento.operacion_id is not None
        operacion = await session.get(OperacionIdempotente, intento.operacion_id)
        assert operacion is not None
        otro_lote = LoteComprobante(
            nombre_archivo="otro-legacy.xlsx",
            archivo_hash="7" * 64,
            estado="requiere_reconciliacion",
            modo_procesamiento="sincronico",
            procesamiento_async=False,
            total_filas=1,
            total_grupos=1,
            empresa_id=empresa_id,
        )
        session.add(otro_lote)
        await session.flush()
        operacion.lote_id = otro_lote.id
        await session.commit()
    with pytest.raises(Exception, match=mensaje):
        await planificar_resolucion_legacy_pf19(
            engine,
            SolicitudPlanLegacyPF19(
                intento_id=intento_id,
                empresa_id=empresa_id,
                punto_venta=4,
                tipo_comprobante=6,
            ),
        )
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("estado_fila", ("autorizado", "descartado"))
async def test_plan_no_toca_fila_terminal_del_grupo_objetivo(
    tmp_path: Path,
    estado_fila: str,
) -> None:
    """Una fila ya terminal nunca vuelve a clasificarse como cierre legacy."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, _admin_id = await _sembrar(
        engine,
        tipo_operacion="procesar_lote",
    )
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        fila = (await session.execute(select(LoteComprobanteFila))).scalar_one()
        fila.estado = estado_fila
        await session.commit()
    with pytest.raises(Exception, match="filas legacy"):
        await planificar_resolucion_legacy_pf19(
            engine,
            SolicitudPlanLegacyPF19(
                intento_id=intento_id,
                empresa_id=empresa_id,
                punto_venta=4,
                tipo_comprobante=6,
            ),
        )
    async with fabrica() as session:
        fila = (await session.execute(select(LoteComprobanteFila))).scalar_one()
        assert fila.estado == estado_fila
    await engine.dispose()


@pytest.mark.asyncio
async def test_plan_individual_exige_unico_intento_de_operacion(tmp_path: Path) -> None:
    """Aun un sibling terminal impide reescribir una operación individual compartida."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, _admin_id = await _sembrar(engine)
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        intento = await session.get(IntentoEmisionFiscal, intento_id)
        assert intento is not None
        session.add(
            IntentoEmisionFiscal(
                tipo_comprobante=intento.tipo_comprobante,
                punto_venta_numero=intento.punto_venta_numero,
                numero_planificado=2,
                fecha_emision=intento.fecha_emision,
                total=intento.total,
                payload_hash="8" * 64,
                huella_logica="6" * 64,
                estado="fallido_verificado",
                categoria_error="sintetico_terminal",
                operacion_id=intento.operacion_id,
                empresa_id=intento.empresa_id,
                punto_venta_id=intento.punto_venta_id,
            )
        )
        await session.commit()
    with pytest.raises(Exception, match="exclusivamente al intento"):
        await planificar_resolucion_legacy_pf19(
            engine,
            SolicitudPlanLegacyPF19(
                intento_id=intento_id,
                empresa_id=empresa_id,
                punto_venta=4,
                tipo_comprobante=6,
            ),
        )
    await engine.dispose()


@pytest.mark.asyncio
async def test_journal_fk_compuesto_rechaza_intento_de_otro_emisor(
    tmp_path: Path,
) -> None:
    """El journal no puede asociar un intento a una empresa existente distinta."""
    engine = await _engine(tmp_path)
    intento_id, _empresa_id, admin_id = await _sembrar(engine)
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        otra_empresa = Empresa(
            razon_social="Emisor FK sintético",
            cuit="20333444556",
            condicion_iva="RI",
            domicilio="Calle 3",
            localidad="Ciudad",
            provincia="Buenos Aires",
            codigo_postal="1002",
            inicio_actividades=date(2022, 1, 1),
        )
        session.add(otra_empresa)
        await session.flush()
        session.add(
            ResolucionLegacyPF19Journal(
                accion="cerrar_legacy_sin_autorizacion_verificada",
                plan_sha256="a" * 64,
                terminal_response_sha256="c" * 64,
                actor_usuario_id=admin_id,
                ambiente_consultado="ambos",
                resultado="legacy_sin_autorizacion_verificada",
                resultado_consultas_json={},
                backup_metadata_json={},
                backup_sha256="b" * 64,
                intento_id=intento_id,
                empresa_id=otra_empresa.id,
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("campo", "valor"),
    (
        ("plan_sha256", "a" * 63),
        ("terminal_response_sha256", "c" * 63),
        ("backup_sha256", "b" * 63),
        ("ambiente_consultado", "manual"),
        ("accion", "otra_accion"),
        ("resultado", "otro_resultado"),
    ),
)
async def test_journal_checks_rechazan_valores_fuera_de_contrato(
    tmp_path: Path,
    campo: str,
    valor: str,
) -> None:
    """Allowlist y longitudes se aplican también en la base portable."""
    engine = await _engine(tmp_path)
    intento_id, empresa_id, admin_id = await _sembrar(engine)
    datos = {
        "accion": "cerrar_legacy_sin_autorizacion_verificada",
        "plan_sha256": "a" * 64,
        "terminal_response_sha256": "c" * 64,
        "actor_usuario_id": admin_id,
        "ambiente_consultado": "ambos",
        "resultado": "legacy_sin_autorizacion_verificada",
        "resultado_consultas_json": {},
        "backup_metadata_json": {},
        "backup_sha256": "b" * 64,
        "intento_id": intento_id,
        "empresa_id": empresa_id,
    }
    datos[campo] = valor
    fabrica = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as session:
        session.add(ResolucionLegacyPF19Journal(**datos))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    await engine.dispose()
