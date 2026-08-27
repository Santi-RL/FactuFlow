"""Pruebas de la contención preautorización de PF-19A."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BloqueoPreautorizacionArca, settings
from app.models.certificado import Certificado
from app.models.comprobante import Comprobante
from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceActual,
    PuntoVentaElegibilidadReceRevision,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.schemas.lote_comprobante import (
    LoteComprobanteResponse,
    LoteProcesamientoResponse,
)
from app.services.contencion_fiscal_service import (
    CATEGORIA_BLOQUEO_PREAUTORIZACION,
    obtener_bloqueo_preautorizacion,
)
from app.services.facturacion_service import FacturacionService, FaseSolicitudArca
from app.services.elegibilidad_rece_service import (
    ContextoElegibilidadRece,
    ElegibilidadReceService,
)
from app.services.lote_comprobantes_service import (
    LoteComprobanteError,
    LoteComprobantesService,
)


class _FechaContencionFija(date):
    """Reloj determinista para la fecha fiscal de estos escenarios."""

    @classmethod
    def today(cls) -> date:
        """Devuelve la fecha explícita usada por los fixtures PF-19."""
        return cls(2026, 8, 8)


def _bloqueo(
    *,
    ambiente: str = "produccion",
    empresa_id: int = 1,
    punto_venta_id: int = 70,
    punto_venta: int = 7,
    tipo_comprobante: int = 6,
) -> BloqueoPreautorizacionArca:
    """Construye una regla sintética de contención exacta."""
    return BloqueoPreautorizacionArca(
        ambiente=ambiente,
        empresa_id=empresa_id,
        punto_venta_id=punto_venta_id,
        punto_venta=punto_venta,
        tipo_comprobante=tipo_comprobante,
        motivo="elegibilidad_no_verificada",
    )


def _request(
    *,
    empresa_id: int,
    punto_venta_id: int,
    tipo_comprobante: int = 6,
) -> EmitirComprobanteRequest:
    """Construye una emisión sintética con fecha fiscal explícita."""
    return EmitirComprobanteRequest(
        empresa_id=empresa_id,
        punto_venta_id=punto_venta_id,
        tipo_comprobante=tipo_comprobante,
        concepto=1,
        fecha_emision=date(2026, 8, 8),
        tipo_documento=96,
        numero_documento="12345678",
        razon_social="Cliente sintético",
        condicion_iva="Consumidor Final",
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Servicio sintético",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                iva_porcentaje=Decimal("21"),
            )
        ],
    )


async def _crear_contexto_rece_contenido(
    db: AsyncSession,
    *,
    empresa,
    punto: PuntoVenta,
) -> ContextoElegibilidadRece:
    """Crea una cabeza RECE moderna para alcanzar el gate PF-19 probado."""
    ahora = datetime(2026, 8, 9, 12, 0, 0)
    punto.revision_fiscal = 1
    revision = PuntoVentaElegibilidadReceRevision(
        empresa_id=empresa.id,
        punto_venta_id=punto.id,
        ambiente="produccion",
        revision=1,
        estado="verificado_rece",
        fuente="constancia_arca_atestada",
        evidencia_tipo="rece_aplicativo_web_services_v1",
        evidencia_sha256="a" * 64,
        clasificador_version="rece-v1-contencion-test",
        empresa_cuit_snapshot=empresa.cuit,
        punto_venta_numero_snapshot=punto.numero,
        punto_revision_fiscal=1,
        documento_emitido_en=date(2026, 8, 9),
        vigente_hasta=date(2099, 12, 31),
        observado_en=ahora,
        verificado_en=ahora,
        actor_usuario_id_snapshot=1,
        created_at=ahora,
    )
    db.add(revision)
    await db.flush()
    db.add(
        PuntoVentaElegibilidadReceActual(
            empresa_id=empresa.id,
            punto_venta_id=punto.id,
            ambiente="produccion",
            revision_actual_id=revision.id,
        )
    )
    await db.flush()
    return ContextoElegibilidadRece(
        empresa_id=empresa.id,
        punto_venta_id=punto.id,
        punto_venta_numero=punto.numero,
        ambiente="produccion",
        elegibilidad_revision_id=revision.id,
        punto_venta_revision_fiscal=1,
    )


async def _crear_operacion_rece_contenida(
    db: AsyncSession,
    *,
    empresa,
    punto: PuntoVenta,
    requests: list[EmitirComprobanteRequest],
    lote: LoteComprobante | None = None,
    grupos: list[LoteComprobanteGrupo] | None = None,
) -> tuple[OperacionIdempotente, ContextoElegibilidadRece, list[dict[str, object]]]:
    """Publica ownership RECE exacto sin habilitar ninguna solicitud de CAE."""
    contexto = await _crear_contexto_rece_contenido(
        db,
        empresa=empresa,
        punto=punto,
    )
    es_batch = lote is not None or len(requests) > 1
    operacion = OperacionIdempotente(
        empresa_id=empresa.id,
        idempotency_key=f"pf19-contenido-{contexto.elegibilidad_revision_id}-{int(es_batch)}",
        tipo_operacion="procesar_lote" if es_batch else "emitir_comprobante",
        payload_hash=f"{contexto.elegibilidad_revision_id:064d}",
        estado="en_proceso",
        rece_snapshot_hash=ElegibilidadReceService.calcular_digest_contextos(
            [contexto]
        ),
    )
    db.add(operacion)
    await db.flush()
    db.add(
        OperacionIdempotenteElegibilidadRece(
            operacion_id=operacion.id,
            empresa_id=empresa.id,
            punto_venta_id=punto.id,
            ambiente=contexto.ambiente,
            elegibilidad_revision_id=contexto.elegibilidad_revision_id,
            punto_venta_revision_fiscal=1,
        )
    )

    metadata: list[dict[str, object]] = []
    if es_batch:
        if lote is None:
            lote = LoteComprobante(
                empresa_id=empresa.id,
                nombre_archivo="pf19-contenido-rece.xlsx",
                archivo_hash="b" * 64,
                estado="procesando",
                procesamiento_async=False,
                modo_procesamiento="sincronico",
                total_filas=len(requests),
                total_grupos=len(requests),
                grupos_validos=len(requests),
            )
            db.add(lote)
            await db.flush()
        if grupos is None:
            grupos = []
            for indice, request in enumerate(requests, start=1):
                grupo = LoteComprobanteGrupo(
                    lote_id=lote.id,
                    empresa_id=empresa.id,
                    comprobante_ref=f"PF19-CONTENIDO-{indice:03d}",
                    orden=indice,
                    estado="validado",
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta_numero=punto.numero,
                    total_estimado=Decimal("121.00"),
                    payload_json=request.model_dump(mode="json"),
                )
                db.add(grupo)
                await db.flush()
                grupos.append(grupo)
        for indice, (request, grupo) in enumerate(
            zip(requests, grupos),
            start=1,
        ):
            grupo.empresa_id = empresa.id
            grupo.punto_venta_id = punto.id
            grupo.ambiente = contexto.ambiente
            grupo.punto_venta_elegibilidad_revision_id = (
                contexto.elegibilidad_revision_id
            )
            grupo.punto_venta_revision_fiscal = 1
            db.add(
                LoteComprobanteFila(
                    lote_id=lote.id,
                    grupo_id=grupo.id,
                    fila_excel=indice + 1,
                    comprobante_ref=grupo.comprobante_ref,
                    estado=grupo.estado,
                    datos_json={},
                    mensajes_json=["Validado sintético"],
                )
            )
            metadata.append(
                {
                    "operacion_id": operacion.id,
                    "contexto_rece": contexto,
                    "contextos_operacion": [contexto],
                    "lote_id": lote.id,
                    "grupo_id": grupo.id,
                    "usuario_id": None,
                }
            )
        operacion.lote_id = lote.id
        await db.flush()
        material_rece = await LoteComprobantesService(
            db
        ).calcular_material_idempotente_grupos(
            lote_id=lote.id,
            empresa_id=empresa.id,
            estados={"validado"},
        )
        metadata_lote = dict(lote.metadata_json or {})
        metadata_lote.update(
            {
                "operacion_idempotente_id": operacion.id,
                "confirmacion_duplicado_logico": False,
                "pf19b_rece_material": material_rece,
            }
        )
        lote.metadata_json = metadata_lote
        if lote.procesamiento_async and lote.modo_procesamiento == "background":
            await db.flush()
            operacion.response_json = LoteProcesamientoResponse(
                lote=LoteComprobanteResponse.model_validate(lote),
                mensaje="El lote está siendo procesado en segundo plano.",
                en_progreso=True,
            ).model_dump(mode="json")
    await db.commit()
    return operacion, contexto, metadata


@pytest.mark.parametrize(
    ("ambiente", "empresa_id", "punto_venta", "tipo_comprobante"),
    [
        ("homologacion", 1, 7, 6),
        ("produccion", 2, 7, 6),
        ("produccion", 1, 8, 6),
        ("produccion", 1, 7, 11),
    ],
)
def test_bloqueo_preautorizacion_no_se_propaga_entre_dimensiones(
    ambiente: str,
    empresa_id: int,
    punto_venta: int,
    tipo_comprobante: int,
) -> None:
    """Ambiente, emisor, punto y tipo forman una clave exacta sin comodines."""
    bloqueo = _bloqueo()

    assert (
        obtener_bloqueo_preautorizacion(
            ambiente=ambiente,
            empresa_id=empresa_id,
            punto_venta_id=70 if punto_venta == 7 else 80,
            punto_venta=punto_venta,
            tipo_comprobante=tipo_comprobante,
            bloqueos=[bloqueo],
        )
        is None
    )
    assert (
        obtener_bloqueo_preautorizacion(
            ambiente="produccion",
            empresa_id=1,
            punto_venta_id=70,
            punto_venta=7,
            tipo_comprobante=6,
            bloqueos=[bloqueo],
        )
        == bloqueo
    )


def test_bloqueo_preautorizacion_rechaza_campos_desconocidos() -> None:
    """La configuración fiscal no ignora propiedades inesperadas."""
    with pytest.raises(PydanticValidationError, match="extra_forbidden"):
        BloqueoPreautorizacionArca.model_validate(
            {
                "ambiente": "produccion",
                "empresa_id": 1,
                "punto_venta_id": 70,
                "punto_venta": 7,
                "tipo_comprobante": 6,
                "motivo": "elegibilidad_no_verificada",
                "comodin": True,
            }
        )


@pytest.mark.parametrize("valor", ["7", 7.0])
def test_bloqueo_preautorizacion_rechaza_numeros_coercionados(valor: object) -> None:
    """Los identificadores fiscales exigen enteros JSON, sin coerciones."""
    datos = _bloqueo().model_dump()
    datos["punto_venta"] = valor

    with pytest.raises(PydanticValidationError, match="int_type"):
        BloqueoPreautorizacionArca.model_validate(datos)


def test_bloqueo_preautorizacion_sobrevive_renumeracion_del_punto() -> None:
    """La identidad persistida evita eludir la guarda editando el número visible."""
    bloqueo = _bloqueo(punto_venta_id=70, punto_venta=7)

    assert (
        obtener_bloqueo_preautorizacion(
            ambiente="produccion",
            empresa_id=1,
            punto_venta_id=70,
            punto_venta=8,
            tipo_comprobante=6,
            bloqueos=[bloqueo],
        )
        == bloqueo
    )


def test_bloqueo_preautorizacion_sobrevive_recreacion_del_numero() -> None:
    """El número fiscal original sigue contenido aunque cambie la fila local."""
    bloqueo = _bloqueo(punto_venta_id=70, punto_venta=7)

    assert (
        obtener_bloqueo_preautorizacion(
            ambiente="produccion",
            empresa_id=1,
            punto_venta_id=71,
            punto_venta=7,
            tipo_comprobante=6,
            bloqueos=[bloqueo],
        )
        == bloqueo
    )
    assert (
        obtener_bloqueo_preautorizacion(
            ambiente="produccion",
            empresa_id=1,
            punto_venta_id=71,
            punto_venta=8,
            tipo_comprobante=6,
            bloqueos=[bloqueo],
        )
        is None
    )


def test_bloqueo_preautorizacion_resuelve_cruce_de_reglas_deterministicamente() -> None:
    """Prioriza coincidencia por ID sobre número sin depender del orden JSON."""
    bloqueo_por_id = _bloqueo(punto_venta_id=70, punto_venta=7)
    bloqueo_por_numero = _bloqueo(punto_venta_id=71, punto_venta=8)

    for bloqueos in (
        [bloqueo_por_id, bloqueo_por_numero],
        [bloqueo_por_numero, bloqueo_por_id],
    ):
        assert (
            obtener_bloqueo_preautorizacion(
                ambiente="produccion",
                empresa_id=1,
                punto_venta_id=70,
                punto_venta=8,
                tipo_comprobante=6,
                bloqueos=bloqueos,
            )
            == bloqueo_por_id
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("modo", ["individual", "batch"])
async def test_contencion_aborta_sin_arca_intentos_cae_ni_comprobantes(
    modo: str,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los núcleos directos terminan antes de clientes ARCA y persistencia."""
    monkeypatch.setattr("app.services.facturacion_service.date", _FechaContencionFija)
    punto = PuntoVenta(
        numero=7,
        nombre="Web Services sintético",
        sistema="Web Services",
        es_webservice=True,
        bloqueado=False,
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto)
    await db_session.commit()
    await db_session.refresh(punto)

    monkeypatch.setattr(settings, "arca_env", "produccion")
    monkeypatch.setattr(
        settings,
        "arca_bloqueos_preautorizacion",
        [
            _bloqueo(
                empresa_id=test_empresa.id,
                punto_venta_id=punto.id,
                punto_venta=punto.numero,
            )
        ],
    )

    def arca_no_debe_inicializarse(*_args, **_kwargs):
        raise AssertionError("La contención debe abortar antes de WSAA o WSFE")

    monkeypatch.setattr(
        "app.services.facturacion_service.WSAAClient",
        arca_no_debe_inicializarse,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        arca_no_debe_inicializarse,
    )

    request = _request(empresa_id=test_empresa.id, punto_venta_id=punto.id)
    fase = FaseSolicitudArca()
    service = FacturacionService(db_session)
    if modo == "individual":
        operacion, contexto, _ = await _crear_operacion_rece_contenida(
            db_session,
            empresa=test_empresa,
            punto=punto,
            requests=[request],
        )
        resultados = [
            await service.emitir_comprobante(
                request,
                operacion_id=operacion.id,
                contexto_rece=contexto,
                contextos_operacion=[contexto],
                fase_solicitud_arca=fase,
            )
        ]
    else:
        _, _, metadata = await _crear_operacion_rece_contenida(
            db_session,
            empresa=test_empresa,
            punto=punto,
            requests=[request, request.model_copy()],
        )
        resultados = await service.emitir_comprobantes_lote(
            [request, request.model_copy()],
            contextos=metadata,
            fase_solicitud_arca=fase,
        )

    assert resultados
    assert all(not resultado.exito for resultado in resultados)
    assert all(resultado.cae is None for resultado in resultados)
    assert all(resultado.numero == 0 for resultado in resultados)
    assert all(
        resultado.categoria_error == CATEGORIA_BLOQUEO_PREAUTORIZACION
        for resultado in resultados
    )
    assert all(not resultado.requiere_reconciliacion for resultado in resultados)
    assert fase.iniciada is False
    assert (
        await db_session.execute(select(IntentoEmisionFiscal))
    ).scalars().all() == []
    assert (await db_session.execute(select(Comprobante))).scalars().all() == []


@pytest.mark.asyncio
async def test_procesar_lote_bloquea_antes_de_capacidad_y_fecae(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La contención corta antes de WSAA, capacidad y cualquier FECAE."""
    punto = PuntoVenta(
        numero=7,
        nombre="Web Services batch sintético",
        sistema="Web Services",
        es_webservice=True,
        bloqueado=False,
        activo=True,
        empresa_id=test_empresa.id,
    )
    certificado = Certificado(
        nombre="Certificado PF-19A sintético",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 12, 31),
        archivo_crt="pf19-sintetico.crt",
        archivo_key="pf19-sintetico.key",
        activo=True,
        ambiente="produccion",
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto, certificado])
    await db_session.flush()

    request = _request(empresa_id=test_empresa.id, punto_venta_id=punto.id)
    lote = LoteComprobante(
        nombre_archivo="pf19-batch-sintetico.xlsx",
        archivo_hash="e" * 64,
        estado="validado",
        total_filas=2,
        total_grupos=2,
        grupos_validos=2,
        procesamiento_async=True,
        modo_procesamiento="background",
        metadata_json={
            "opciones_concepto": {"modo": "fijo", "valor": 1},
            "opciones_descripcion_item": {"modo": "archivo"},
        },
        empresa_id=test_empresa.id,
    )
    grupos = [
        LoteComprobanteGrupo(
            lote=lote,
            empresa_id=test_empresa.id,
            comprobante_ref=f"PF19-BATCH-{indice:03d}",
            orden=indice,
            estado="validado",
            tipo_comprobante=request.tipo_comprobante,
            punto_venta_numero=punto.numero,
            total_estimado=Decimal("121.00"),
            payload_json=request.model_dump(mode="json"),
            mensajes_json=["Validado sintético"],
        )
        for indice in (1, 2)
    ]
    db_session.add_all([lote, *grupos])
    await db_session.commit()

    monkeypatch.setattr(settings, "arca_env", "produccion")
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_max_registros", 0)
    monkeypatch.setattr(
        settings,
        "arca_bloqueos_preautorizacion",
        [
            _bloqueo(
                empresa_id=test_empresa.id,
                punto_venta_id=punto.id,
                punto_venta=punto.numero,
            )
        ],
    )
    await _crear_operacion_rece_contenida(
        db_session,
        empresa=test_empresa,
        punto=punto,
        requests=[request, request.model_copy()],
        lote=lote,
        grupos=grupos,
    )

    llamadas = {
        "wsaa_inicios": 0,
        "wsaa_login": 0,
        "wsfe_inicios": 0,
        "reg_x_req": 0,
        "fecae": 0,
    }

    class FakeWSAAClient:
        """Simula la autenticación previa permitida sin usar red."""

        def __init__(self, _ambiente) -> None:
            llamadas["wsaa_inicios"] += 1

        async def login(self, **_kwargs):
            llamadas["wsaa_login"] += 1
            return SimpleNamespace(token="token-sintetico", sign="firma-sintetica")

    class FakeWSFEv1Client:
        """Permite RegXReq y prohíbe cualquier solicitud de CAE."""

        def __init__(self, **_kwargs) -> None:
            llamadas["wsfe_inicios"] += 1

        async def fe_comp_tot_x_request(self) -> int:
            llamadas["reg_x_req"] += 1
            return 2

        async def fe_cae_solicitar(self, *_args, **_kwargs):
            llamadas["fecae"] += 1
            raise AssertionError("La contención no debe invocar FECAESolicitar")

        async def fe_cae_solicitar_lote(self, *_args, **_kwargs):
            llamadas["fecae"] += 1
            raise AssertionError("La contención no debe invocar FECAESolicitar batch")

    monkeypatch.setattr(
        "app.services.facturacion_service.requerir_material_certificado",
        lambda *_args: ("pf19-sintetico.crt", "pf19-sintetico.key"),
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.WSAAClient",
        FakeWSAAClient,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        FakeWSFEv1Client,
    )

    fase = FaseSolicitudArca()
    with pytest.raises(
        LoteComprobanteError,
        match="bloqueado preventivamente",
    ):
        await LoteComprobantesService(db_session).procesar_lote(
            lote.id,
            test_empresa.id,
            fase_solicitud_arca=fase,
        )

    assert llamadas == {
        "wsaa_inicios": 0,
        "wsaa_login": 0,
        "wsfe_inicios": 0,
        "reg_x_req": 0,
        "fecae": 0,
    }
    assert fase.iniciada is False
    assert (
        await db_session.execute(select(IntentoEmisionFiscal))
    ).scalars().all() == []
    assert (await db_session.execute(select(Comprobante))).scalars().all() == []
    for grupo in grupos:
        await db_session.refresh(grupo)
        assert grupo.estado == "validado"
        assert grupo.cae is None
        assert grupo.comprobante_id is None
        assert grupo.numero_asignado is None


@pytest.mark.asyncio
async def test_contencion_preserva_intento_stale_sin_consultar_arca(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un intento vencido contenido sigue incierto y no habilita replay."""
    punto = PuntoVenta(
        numero=7,
        nombre="Web Services stale sintético",
        sistema="Web Services",
        es_webservice=True,
        bloqueado=False,
        activo=True,
        empresa_id=test_empresa.id,
    )
    operacion = OperacionIdempotente(
        idempotency_key="pf19-stale-sintetica",
        tipo_operacion="emitir_comprobante",
        payload_hash="a" * 64,
        estado="en_proceso",
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto, operacion])
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=punto.numero,
        numero_planificado=1,
        fecha_emision=date(2026, 8, 8),
        total=Decimal("121.00"),
        payload_hash="b" * 64,
        huella_logica="c" * 64,
        estado="en_proceso",
        categoria_error="arca_respuesta_incierta",
        created_at=datetime.utcnow()
        - timedelta(minutes=settings.fiscal_attempt_stale_minutes + 1),
        operacion_id=operacion.id,
        empresa_id=test_empresa.id,
        punto_venta_id=punto.id,
    )
    db_session.add(intento)
    await db_session.commit()

    monkeypatch.setattr(settings, "arca_env", "produccion")
    monkeypatch.setattr(
        settings,
        "arca_bloqueos_preautorizacion",
        [
            _bloqueo(
                empresa_id=test_empresa.id,
                punto_venta_id=punto.id,
                punto_venta=punto.numero,
            )
        ],
    )

    def arca_no_debe_inicializarse(*_args, **_kwargs):
        raise AssertionError("Stale contenido no debe consultar WSAA ni WSFE")

    monkeypatch.setattr(
        "app.services.facturacion_service.WSAAClient",
        arca_no_debe_inicializarse,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        arca_no_debe_inicializarse,
    )

    resultado = await FacturacionService(
        db_session
    ).resolver_operacion_idempotente_incompleta(operacion.id)
    await db_session.refresh(intento)

    assert resultado is not None
    assert resultado.exito is False
    assert resultado.cae is None
    assert resultado.requiere_reconciliacion is True
    assert resultado.categoria_error == "arca_respuesta_incierta"
    assert intento.estado == "en_proceso"
    assert intento.comprobante_id is None
    assert (await db_session.execute(select(Comprobante))).scalars().all() == []


@pytest.mark.asyncio
async def test_contencion_impide_reencolar_lote_stale_sin_consultar_arca(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El preflight stale contenido termina reconciliable, nunca en cola."""
    punto = PuntoVenta(
        numero=7,
        nombre="Web Services lote stale sintético",
        sistema="Web Services",
        es_webservice=True,
        bloqueado=False,
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto)
    await db_session.flush()
    request = _request(empresa_id=test_empresa.id, punto_venta_id=punto.id)
    lote = LoteComprobante(
        nombre_archivo="pf19-stale-sintetico.xlsx",
        archivo_hash="d" * 64,
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        procesamiento_async=True,
        modo_procesamiento="background",
        empresa_id=test_empresa.id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        empresa_id=test_empresa.id,
        comprobante_ref="PF19-STALE-001",
        orden=1,
        estado="validado",
        tipo_comprobante=request.tipo_comprobante,
        punto_venta_numero=punto.numero,
        total_estimado=Decimal("121.00"),
        payload_json=request.model_dump(mode="json"),
        mensajes_json=["Validado sintético"],
    )
    db_session.add_all([lote, grupo])
    await db_session.commit()

    monkeypatch.setattr(settings, "arca_env", "produccion")
    monkeypatch.setattr(
        settings,
        "arca_bloqueos_preautorizacion",
        [
            _bloqueo(
                empresa_id=test_empresa.id,
                punto_venta_id=punto.id,
                punto_venta=punto.numero,
            )
        ],
    )
    await _crear_operacion_rece_contenida(
        db_session,
        empresa=test_empresa,
        punto=punto,
        requests=[request],
        lote=lote,
        grupos=[grupo],
    )
    lote.updated_at = datetime.utcnow() - timedelta(
        minutes=settings.batch_processing_stale_minutes + 1
    )
    await db_session.commit()

    def arca_no_debe_inicializarse(*_args, **_kwargs):
        raise AssertionError("Lote stale contenido no debe consultar WSAA ni WSFE")

    monkeypatch.setattr(
        "app.services.facturacion_service.WSAAClient",
        arca_no_debe_inicializarse,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        arca_no_debe_inicializarse,
    )

    resultado = await LoteComprobantesService(
        db_session
    ).bloquear_lote_procesando_stale(lote.id, test_empresa.id)
    await db_session.refresh(grupo)

    assert resultado.estado == "requiere_reconciliacion"
    assert resultado.metadata_json["bloqueo_operativo"]["preflight_error"] == (
        "snapshot_rece_legacy_u_obsoleto"
    )
    operacion_id = resultado.metadata_json["operacion_idempotente_id"]
    operacion = await db_session.get(OperacionIdempotente, operacion_id)
    assert operacion is not None
    assert operacion.estado == "requiere_reconciliacion"
    assert operacion.response_json["lote"]["estado"] == "requiere_reconciliacion"
    assert grupo.estado == "requiere_reconciliacion"
    assert grupo.cae is None
    assert grupo.comprobante_id is None
    assert (
        await db_session.execute(select(IntentoEmisionFiscal))
    ).scalars().all() == []
    assert (await db_session.execute(select(Comprobante))).scalars().all() == []
