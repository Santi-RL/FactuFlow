"""Tests del servicio de facturación."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import JSON, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.arca.exceptions import ArcaCertificateError, ArcaServiceError
from app.arca.models import CAEResponse
from app.core.config import settings
from app.core.database import Base, _habilitar_foreign_keys_sqlite
from app.models.certificado import Certificado
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.empresa import Empresa
from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceActual,
    PuntoVentaElegibilidadReceRevision,
    PuntoVentaGuardaEmisionRece,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.schemas.comprobante import (
    ComprobanteAsociadoCreate,
    EmitirComprobanteRequest,
    EmitirComprobanteResponse,
    ItemComprobanteCreate,
)
from app.services.facturacion_service import (
    ERROR_INTERNO_EMISION_PUBLICO,
    FacturacionService,
    FaseSolicitudArca,
    ValidationError,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.elegibilidad_rece_service import (
    ContextoElegibilidadRece,
    ElegibilidadReceError,
    ElegibilidadReceService,
)
from app.services.lote_comprobantes_service import LoteComprobantesService


FECHA_FISCAL_PRUEBA = date(2026, 8, 9)


class _FechaFacturacionFija(date):
    """Reloj de fecha determinista para validar la ventana fiscal."""

    @classmethod
    def today(cls) -> date:
        """Devuelve la fecha fiscal explícita de estos escenarios."""
        return cls(
            FECHA_FISCAL_PRUEBA.year,
            FECHA_FISCAL_PRUEBA.month,
            FECHA_FISCAL_PRUEBA.day,
        )


@pytest.fixture(autouse=True)
def _usar_ambiente_arca_productivo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fija el ambiente requerido por una acreditación RECE positiva."""
    monkeypatch.setattr(settings, "arca_env", "produccion")


def _fijar_reloj_facturacion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fija `date.today()` del servicio sin alterar la fecha del request."""
    monkeypatch.setattr(
        "app.services.facturacion_service.date",
        _FechaFacturacionFija,
    )


def _crear_error_db_temporal(
    error_type: type[Exception],
) -> SQLAlchemyTimeoutError | OperationalError:
    """Construye errores transitorios de SQLAlchemy sin datos sensibles reales."""
    if error_type is SQLAlchemyTimeoutError:
        return SQLAlchemyTimeoutError()
    return OperationalError(
        "SELECT dato_fiscal FROM comprobantes",
        {"empresa_id": 1},
        RuntimeError("base temporalmente no disponible"),
    )


async def _crear_cabeza_rece_sintetica(
    db: AsyncSession,
    *,
    empresa: Empresa,
    punto_venta: PuntoVenta,
) -> ContextoElegibilidadRece:
    """Crea una revisión RECE positiva y su cabeza vigente para pruebas."""
    ambiente = "produccion"
    ahora = datetime(2026, 8, 9, 12, 0)
    punto_venta.revision_fiscal = 1
    revision = PuntoVentaElegibilidadReceRevision(
        empresa_id=empresa.id,
        punto_venta_id=punto_venta.id,
        ambiente=ambiente,
        revision=1,
        estado="verificado_rece",
        fuente="constancia_arca_atestada",
        evidencia_tipo="rece_aplicativo_web_services_v1",
        evidencia_sha256="a" * 64,
        clasificador_version="rece-v1-test",
        empresa_cuit_snapshot=empresa.cuit,
        punto_venta_numero_snapshot=punto_venta.numero,
        punto_revision_fiscal=1,
        documento_emitido_en=FECHA_FISCAL_PRUEBA,
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
            punto_venta_id=punto_venta.id,
            ambiente=ambiente,
            revision_actual_id=revision.id,
        )
    )
    await db.flush()
    return ContextoElegibilidadRece(
        empresa_id=empresa.id,
        punto_venta_id=punto_venta.id,
        punto_venta_numero=punto_venta.numero,
        ambiente=ambiente,
        elegibilidad_revision_id=revision.id,
        punto_venta_revision_fiscal=1,
    )


async def _crear_operacion_rece_sintetica(
    db: AsyncSession,
    *,
    empresa: Empresa,
    punto_venta: PuntoVenta,
    requests: list[EmitirComprobanteRequest],
    batch: bool,
) -> tuple[OperacionIdempotente, ContextoElegibilidadRece, list[dict[str, object]],]:
    """Crea evidencia positiva y membresía durable solo para pruebas felices."""
    contexto = await _crear_cabeza_rece_sintetica(
        db,
        empresa=empresa,
        punto_venta=punto_venta,
    )
    ambiente = contexto.ambiente
    revision_id = contexto.elegibilidad_revision_id
    huella = f"{revision_id:064d}"
    operacion = OperacionIdempotente(
        empresa_id=empresa.id,
        idempotency_key=f"rece-test-{revision_id}-{int(batch)}",
        tipo_operacion=("procesar_lote" if batch else "emitir_comprobante"),
        payload_hash=huella,
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
            punto_venta_id=punto_venta.id,
            ambiente=ambiente,
            elegibilidad_revision_id=revision_id,
            punto_venta_revision_fiscal=1,
        )
    )

    metadata: list[dict[str, object]] = []
    if batch:
        lote = LoteComprobante(
            empresa_id=empresa.id,
            nombre_archivo=f"rece-{revision_id}.xlsx",
            archivo_hash=f"{revision_id + 1:064d}",
            estado="procesando",
            procesamiento_async=False,
            modo_procesamiento="sincronico",
        )
        db.add(lote)
        await db.flush()
        for indice, request in enumerate(requests, start=1):
            grupo = LoteComprobanteGrupo(
                lote_id=lote.id,
                empresa_id=empresa.id,
                comprobante_ref=f"RECE-{revision_id}-{indice}",
                estado="validado",
                tipo_comprobante=request.tipo_comprobante,
                punto_venta_numero=punto_venta.numero,
                total_estimado=Decimal("1000"),
                payload_json=request.model_dump(mode="json"),
                punto_venta_id=punto_venta.id,
                ambiente=ambiente,
                punto_venta_elegibilidad_revision_id=revision_id,
                punto_venta_revision_fiscal=1,
            )
            db.add(grupo)
            await db.flush()
            db.add(
                LoteComprobanteFila(
                    lote_id=lote.id,
                    grupo_id=grupo.id,
                    fila_excel=indice + 1,
                    comprobante_ref=grupo.comprobante_ref,
                    estado="validado",
                    datos_json={},
                    mensajes_json=["Validado sintético."],
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
        material_rece = await LoteComprobantesService(
            db
        ).calcular_material_idempotente_grupos(
            lote_id=lote.id,
            empresa_id=empresa.id,
            estados={"validado"},
        )
        lote.metadata_json = {
            "operacion_idempotente_id": operacion.id,
            "pf19b_rece_material": material_rece,
        }
    await db.commit()
    return operacion, contexto, metadata


@pytest.mark.asyncio
async def test_validar_datos_productos_rechaza_fechas_servicio(
    db_session: AsyncSession,
) -> None:
    """Productos no admite fechas de servicio que puedan llegar a WSFE."""
    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 5, 20),
        fecha_servicio_desde=date(2026, 5, 1),
        tipo_documento=96,
        numero_documento="12345678",
        razon_social="Cliente Demo",
        condicion_iva="Consumidor Final",
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                iva_porcentaje=Decimal("21"),
            )
        ],
    )

    with pytest.raises(
        ValidationError,
        match="Las fechas de servicio no corresponden",
    ):
        await service._validar_datos(request)


class FakeWSFEClient:
    """Cliente WSFE mínimo para probar validaciones internas."""

    def __init__(self, puntos: list[SimpleNamespace]) -> None:
        """Inicializa el cliente con puntos de venta simulados."""
        self._puntos = puntos

    async def fe_param_get_ptos_venta(self) -> list[SimpleNamespace]:
        """Devuelve puntos de venta simulados como lo haría ARCA."""
        return self._puntos


@pytest.mark.asyncio
async def test_obtener_ticket_rechaza_material_incompleto_antes_de_wsaa(
    db_session: AsyncSession,
    tmp_path,
    monkeypatch,
):
    """La emisión debe fallar sin llamar WSAA ni exponer rutas locales."""
    monkeypatch.setattr(settings, "certs_path", str(tmp_path))
    (tmp_path / "presente.crt").write_text("CRT", encoding="ascii")

    def fail_wsaa_constructor(*args, **kwargs):
        raise AssertionError("WSAAClient no debe construirse sin clave privada")

    monkeypatch.setattr(
        "app.services.facturacion_service.WSAAClient",
        fail_wsaa_constructor,
    )
    service = FacturacionService(db_session)
    empresa = SimpleNamespace(cuit="30700000001")
    certificado = SimpleNamespace(
        archivo_crt="presente.crt",
        archivo_key="faltante.key",
    )

    with pytest.raises(ArcaCertificateError) as exc_info:
        await service._obtener_ticket_acceso(empresa, certificado)

    detail = str(exc_info.value)
    assert "archivos locales" in detail
    assert str(tmp_path) not in detail
    assert "faltante.key" not in detail


@pytest.mark.asyncio
async def test_guardar_comprobante_masivo_no_crea_cliente(
    db_session: AsyncSession,
    test_empresa,
):
    """La emisión masiva puede guardar snapshot sin crear cliente persistente."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()

    service = FacturacionService(db_session)
    request = service.normalizar_receptor(
        EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=1,
            fecha_emision=date.today(),
            tipo_documento=99,
            numero_documento="",
            razon_social="",
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Cuota mensual",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000"),
                    iva_porcentaje=Decimal("21"),
                )
            ],
        )
    )
    totales = service._calcular_totales(request.items)
    resultado_arca = SimpleNamespace(
        cae="12345678901234",
        cae_vencimiento=date(2026, 5, 15).strftime("%Y%m%d"),
    )

    comprobante = await service._guardar_comprobante(
        request=request,
        numero=1,
        totales=totales,
        resultado_arca=resultado_arca,
        punto_venta=punto_venta,
    )

    clientes = (await db_session.execute(select(Cliente))).scalars().all()
    assert clientes == []
    assert comprobante.cliente_id is None
    assert comprobante.receptor_tipo_documento == 99
    assert comprobante.receptor_numero_documento == "0"
    assert comprobante.receptor_razon_social == "A CONSUMIDOR FINAL"
    assert comprobante.receptor_condicion_iva == "CF"
    assert comprobante.fecha_emision == date.today()
    assert comprobante.concepto == 1


@pytest.mark.asyncio
async def test_guardar_comprobante_persiste_fechas_de_servicio(
    db_session: AsyncSession,
    test_empresa,
):
    """La emision debe conservar periodo de servicio y vencimiento de pago."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()

    service = FacturacionService(db_session)
    request = service.normalizar_receptor(
        EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=2,
            fecha_emision=date(2026, 4, 30),
            fecha_servicio_desde=date(2026, 4, 1),
            fecha_servicio_hasta=date(2026, 4, 30),
            fecha_vto_pago=date(2026, 4, 30),
            tipo_documento=99,
            numero_documento="0",
            razon_social="CLIENTE DE PRUEBA -",
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Abono mensual",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("21600"),
                    iva_porcentaje=Decimal("21"),
                )
            ],
        )
    )
    totales = service._calcular_totales(request.items)
    resultado_arca = SimpleNamespace(
        cae="99999999999999",
        cae_vencimiento=date(2026, 5, 10).strftime("%Y%m%d"),
    )

    comprobante = await service._guardar_comprobante(
        request=request,
        numero=1001,
        totales=totales,
        resultado_arca=resultado_arca,
        punto_venta=punto_venta,
    )

    assert comprobante.fecha_servicio_desde == date(2026, 4, 1)
    assert comprobante.fecha_servicio_hasta == date(2026, 4, 30)
    assert comprobante.fecha_vto_pago == date(2026, 4, 30)
    assert comprobante.fecha_vencimiento == date(2026, 4, 30)


@pytest.mark.asyncio
async def test_validar_punto_venta_habilitado_acepta_bloqueado_n(
    db_session: AsyncSession,
):
    """La validación interpreta `Bloqueado=N` de ARCA como punto habilitado."""
    service = FacturacionService(db_session)
    wsfe_client = FakeWSFEClient(
        [SimpleNamespace(numero=13, bloqueado="N", emision_tipo="CAE - Exento")]
    )

    await service._validar_punto_venta_habilitado(wsfe_client, 13)


@pytest.mark.asyncio
async def test_validar_punto_venta_habilitado_rechaza_bloqueado_s(
    db_session: AsyncSession,
):
    """La validación rechaza `Bloqueado=S` de ARCA como punto no habilitado."""
    service = FacturacionService(db_session)
    wsfe_client = FakeWSFEClient(
        [SimpleNamespace(numero=13, bloqueado="S", emision_tipo="CAE - Exento")]
    )

    with pytest.raises(ValidationError):
        await service._validar_punto_venta_habilitado(wsfe_client, 13)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ultimo_arca", "estado_esperado", "proximo_esperado"),
    [
        (76, "alineada", 77),
        (80, "arca_adelantada", 81),
        (75, "local_adelantada", None),
    ],
)
async def test_verificar_numeracion_segura_para_emision_consulta_arca(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    ultimo_arca: int,
    estado_esperado: str,
    proximo_esperado: int | None,
):
    """El preflight acepta historia externa, pero no historia local adelantada."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    certificado = Certificado(
        nombre="Certificado Test",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=76,
        fecha_emision=date(2026, 7, 1),
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("0.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1000.00"),
        cae="12345678901234",
        cae_vencimiento=date(2026, 7, 10),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta=punto_venta,
    )
    db_session.add_all([punto_venta, certificado, comprobante])
    await db_session.commit()
    await db_session.refresh(punto_venta)
    await _crear_cabeza_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
    )

    class FakePreflightWSFEClient:
        """Cliente WSFE simulado para el preflight de numeración."""

        consultas_ultimo: list[tuple[int, int]] = []

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_param_get_ptos_venta(self):
            """Devuelve el punto de venta como habilitado en ARCA."""
            return [SimpleNamespace(numero=1, bloqueado="N")]

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Devuelve el último número ARCA parametrizado."""
            self.consultas_ultimo.append((punto_venta_numero, tipo))
            return ultimo_arca

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        FakePreflightWSFEClient,
    )
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)

    service = FacturacionService(db_session)
    if proximo_esperado is None:
        with pytest.raises(ValidationError, match="local está adelantada"):
            await service.verificar_numeracion_segura_para_emision(
                empresa_id=test_empresa.id,
                punto_venta_id=punto_venta.id,
                tipo_comprobante=6,
            )
    else:
        resultado = await service.verificar_numeracion_segura_para_emision(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
        )

        assert resultado == {
            "empresa_id": test_empresa.id,
            "punto_venta_id": punto_venta.id,
            "punto_venta_numero": 1,
            "tipo_comprobante": 6,
            "ultimo_local": 76,
            "ultimo_arca": ultimo_arca,
            "proximo_local": 77,
            "proximo_arca": ultimo_arca + 1,
            "proximo_numero": proximo_esperado,
            "estado": estado_esperado,
        }
    assert FakePreflightWSFEClient.consultas_ultimo == [(1, 6)]


def test_armar_request_arca_factura_c_no_informa_objeto_iva(
    db_session: AsyncSession,
):
    """Factura C no debe enviar el bloque `Iva` aunque la alícuota sea 0."""
    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=11,
        concepto=2,
        fecha_emision=date.today(),
        fecha_servicio_desde=date.today(),
        fecha_servicio_hasta=date.today(),
        fecha_vto_pago=date.today(),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Cuota mensual",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("66500"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    totales = service._calcular_totales(request.items)

    comprobante_arca = service._armar_request_arca(request, 1, totales, 13)

    assert comprobante_arca.tipo_cbte == 11
    assert comprobante_arca.imp_iva == 0
    assert comprobante_arca.iva == []


def test_armar_request_arca_factura_b_sin_iva_informa_alicuota_cero(
    db_session: AsyncSession,
):
    """Otros comprobantes sin IVA siguen informando la alícuota 0."""
    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date.today(),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    totales = service._calcular_totales(request.items)

    comprobante_arca = service._armar_request_arca(request, 1, totales, 6)

    assert [iva.id for iva in comprobante_arca.iva] == [3]


def test_armar_request_arca_informa_comprobante_asociado(
    db_session: AsyncSession,
):
    """Las notas de crédito informan comprobantes asociados a WSFE."""
    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=13,
        concepto=2,
        fecha_emision=date.today(),
        fecha_servicio_desde=date.today(),
        fecha_servicio_hasta=date.today(),
        fecha_vto_pago=date.today(),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        comprobantes_asociados=[
            ComprobanteAsociadoCreate(
                tipo_comprobante=11,
                punto_venta=13,
                numero=1645,
                fecha=date(2026, 4, 30),
                cuit="30123456789",
            )
        ],
        items=[
            ItemComprobanteCreate(
                descripcion="Anulación por duplicado",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("59500"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    totales = service._calcular_totales(request.items)

    comprobante_arca = service._armar_request_arca(request, 1, totales, 13)

    assert comprobante_arca.cbtes_asoc[0].tipo == 11
    assert comprobante_arca.cbtes_asoc[0].punto_venta == 13
    assert comprobante_arca.cbtes_asoc[0].numero == 1645
    assert comprobante_arca.cbtes_asoc[0].fecha_cbte == "20260430"


@pytest.mark.asyncio
async def test_validar_datos_rechaza_factura_c_con_iva(
    db_session: AsyncSession,
):
    """Factura C no puede emitirse con ítems gravados con IVA."""
    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=11,
        concepto=1,
        fecha_emision=date.today(),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("21"),
            )
        ],
    )

    with pytest.raises(ValidationError, match="comprobantes tipo C"):
        await service._validar_datos(request)


@pytest.mark.asyncio
async def test_validar_datos_rechaza_punto_venta_de_otro_emisor(
    db_session: AsyncSession,
    test_empresa,
):
    """La emisión no puede usar puntos de venta de otro emisor."""
    otro_emisor = Empresa(
        razon_social="Otro Emisor S.A.",
        cuit="20987654321",
        condicion_iva="RI",
        domicilio="Calle Externa 123",
        localidad="Buenos Aires",
        provincia="Buenos Aires",
        codigo_postal="1000",
        email="otro@empresa.com",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(otro_emisor)
    await db_session.flush()

    punto_venta_ajeno = PuntoVenta(
        numero=9,
        nombre="PV ajeno",
        activo=True,
        es_webservice=True,
        empresa_id=otro_emisor.id,
    )
    db_session.add(punto_venta_ajeno)
    await db_session.flush()

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta_ajeno.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date.today(),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )

    with pytest.raises(ValidationError, match="Punto de venta.*empresa activa"):
        await service._validar_datos(request)


@pytest.mark.asyncio
async def test_validar_datos_rechaza_cliente_de_otro_emisor(
    db_session: AsyncSession,
    test_empresa,
):
    """La emisión no puede vincular clientes de otro emisor."""
    otro_emisor = Empresa(
        razon_social="Emisor Cliente Ajeno S.A.",
        cuit="20999888777",
        condicion_iva="RI",
        domicilio="Calle Cliente 123",
        localidad="Buenos Aires",
        provincia="Buenos Aires",
        codigo_postal="1000",
        email="cliente-ajeno@empresa.com",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(otro_emisor)
    await db_session.flush()

    punto_venta = PuntoVenta(
        numero=1,
        nombre="PV propio",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    cliente_ajeno = Cliente(
        razon_social="Cliente Ajeno",
        tipo_documento="DNI",
        numero_documento="12345678",
        condicion_iva="CF",
        empresa_id=otro_emisor.id,
    )
    db_session.add_all([punto_venta, cliente_ajeno])
    await db_session.flush()

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        cliente_id=cliente_ajeno.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date.today(),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )

    with pytest.raises(ValidationError, match="Cliente.*empresa activa"):
        await service._validar_datos(request)


@pytest.mark.asyncio
async def test_batch_revierte_aprobado_si_falla_cerrar_rechazado_post_arca(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un fallo post-ARCA vuelve incierto todo el sublote, sin éxito fantasma."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
        revision_fiscal=1,
    )
    certificado = Certificado(
        nombre="Certificado Test",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_venta, certificado])
    await db_session.commit()

    def crear_request(nombre: str) -> EmitirComprobanteRequest:
        """Construye un comprobante sintético del mismo sublote."""
        return EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=1,
            fecha_emision=date(2026, 8, 8),
            tipo_documento=99,
            numero_documento="0",
            razon_social=nombre,
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Producto",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000"),
                    iva_porcentaje=Decimal("0"),
                )
            ],
        )

    requests = [crear_request("Cliente aprobado"), crear_request("Cliente rechazado")]
    _operacion, _contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=requests,
        batch=True,
    )

    class FakeWSFEClient:
        """Devuelve un aprobado seguido de un rechazo ARCA."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Informa que el rango comienza en uno."""
            return 0

        async def fe_cae_solicitar_lote(self, arca_requests):
            """Responde resultados mixtos en el mismo orden solicitado."""
            primero, segundo = arca_requests
            return [
                CAEResponse(
                    cae="12345678901231",
                    cae_vencimiento="20260818",
                    numero_comprobante=primero.cbte_desde,
                    tipo_cbte=primero.tipo_cbte,
                    punto_venta=primero.punto_venta,
                    resultado="A",
                ),
                CAEResponse(
                    cae=None,
                    cae_vencimiento=None,
                    numero_comprobante=segundo.cbte_desde,
                    tipo_cbte=segundo.tipo_cbte,
                    punto_venta=segundo.punto_venta,
                    resultado="R",
                    errores=[{"code": 10016, "msg": "Rechazo sintético"}],
                ),
            ]

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    original_actualizar = IdempotenciaFiscalService.actualizar_intento_desde_respuesta
    fallo_inyectado = False

    async def fallar_una_vez_al_cerrar_rechazado(
        self,
        intento,
        response,
        **kwargs,
    ):
        nonlocal fallo_inyectado
        if response.categoria_error == "arca_no_aprobado" and not fallo_inyectado:
            fallo_inyectado = True
            raise RuntimeError("fallo sintético de persistencia")
        return await original_actualizar(self, intento, response, **kwargs)

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "actualizar_intento_desde_respuesta",
        fallar_una_vez_al_cerrar_rechazado,
    )

    resultados = await FacturacionService(db_session).emitir_comprobantes_lote(
        requests,
        max_registros=2,
        contextos=metadata,
    )

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        comprobantes = (await observador.execute(select(Comprobante))).scalars().all()
        intentos = (
            (
                await observador.execute(
                    select(IntentoEmisionFiscal).order_by(
                        IntentoEmisionFiscal.numero_planificado
                    )
                )
            )
            .scalars()
            .all()
        )
        guarda = (
            await observador.execute(select(PuntoVentaGuardaEmisionRece))
        ).scalar_one()

    assert fallo_inyectado is True
    assert comprobantes == []
    assert len(resultados) == 2
    assert all(resultado.exito is False for resultado in resultados)
    assert all(resultado.requiere_reconciliacion is True for resultado in resultados)
    assert {resultado.categoria_error for resultado in resultados} == {
        "post_arca_persistencia"
    }
    assert [intento.estado for intento in intentos] == [
        "requiere_reconciliacion",
        "requiere_reconciliacion",
    ]
    assert guarda.fase == "requiere_reconciliacion"


@pytest.mark.asyncio
async def test_dos_sublotes_recuperan_segunda_guarda_pre_arca_sin_segundo_fecae(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un FECAE previo no impide cerrar la guarda actual que nunca cruzó el CAS."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
        revision_fiscal=1,
    )
    certificado = Certificado(
        nombre="Certificado Test",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_venta, certificado])
    await db_session.commit()

    def crear_request(nombre: str) -> EmitirComprobanteRequest:
        """Construye una emisión individual perteneciente al mismo lote."""
        return EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=1,
            fecha_emision=date(2026, 8, 8),
            tipo_documento=99,
            numero_documento="0",
            razon_social=nombre,
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Producto",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000"),
                    iva_porcentaje=Decimal("0"),
                )
            ],
        )

    requests = [
        crear_request("Primer chunk"),
        crear_request("Segundo chunk").model_copy(
            update={"confirmacion_duplicado_logico": True}
        ),
    ]
    operacion, contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=requests,
        batch=True,
    )
    operacion_id = operacion.id
    empresa_id = test_empresa.id

    class FakeWSFEClient:
        """Autoriza solo la primera guarda; la segunda no llega a FECAE."""

        consultas_numeracion = 0
        llamadas_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma real sin abrir red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene estable cada doble preflight de numeración."""
            FakeWSFEClient.consultas_numeracion += 1
            return 0 if FakeWSFEClient.consultas_numeracion <= 2 else 1

        async def fe_cae_solicitar(self, arca_request):
            """Autoriza la única solicitud que puede cruzar el CAS."""
            FakeWSFEClient.llamadas_fecae += 1
            return CAEResponse(
                cae="12345678901231",
                cae_vencimiento="20260818",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    original_marcar_arca = ElegibilidadReceService.marcar_arca_iniciada
    guardas_evaluadas = 0

    async def fallar_segundo_cas(self, **kwargs):
        nonlocal guardas_evaluadas
        guardas_evaluadas += 1
        if guardas_evaluadas == 2:
            raise SQLAlchemyTimeoutError()
        return await original_marcar_arca(self, **kwargs)

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    monkeypatch.setattr(
        ElegibilidadReceService,
        "marcar_arca_iniciada",
        fallar_segundo_cas,
    )

    service = FacturacionService(db_session)
    fase = FaseSolicitudArca()
    primero = await service.emitir_comprobante(
        requests[0],
        operacion_id=operacion_id,
        lote_id=int(metadata[0]["lote_id"]),
        grupo_id=int(metadata[0]["grupo_id"]),
        contexto_rece=contexto,
        contextos_operacion=[contexto],
        fase_solicitud_arca=fase,
    )
    assert primero.exito is True

    with pytest.raises(SQLAlchemyTimeoutError):
        await service.emitir_comprobante(
            requests[1],
            operacion_id=operacion_id,
            lote_id=int(metadata[1]["lote_id"]),
            grupo_id=int(metadata[1]["grupo_id"]),
            contexto_rece=contexto,
            contextos_operacion=[contexto],
            fase_solicitud_arca=fase,
        )

    assert FakeWSFEClient.llamadas_fecae == 1
    assert fase.iniciada is True
    assert fase.guarda_actual_iniciada is False
    assert fase.guarda_rece_id is not None
    assert fase.guarda_rece_token is not None
    lote_id = int(metadata[0]["lote_id"])
    resultado_recovery = await LoteComprobantesService(
        db_session
    ).recuperar_lote_interrumpido_pre_arca(
        lote_id=lote_id,
        empresa_id=empresa_id,
        operacion_id=operacion_id,
        estado_reanudable="validado",
        estados_claim={"validado"},
        mensaje_seguro="No debe reencolar.",
        guarda_rece_id=fase.guarda_rece_id,
        guarda_rece_token=fase.guarda_rece_token,
    )
    assert resultado_recovery == "requiere_reconciliacion"

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        guardas = (
            (
                await observador.execute(
                    select(PuntoVentaGuardaEmisionRece).order_by(
                        PuntoVentaGuardaEmisionRece.id
                    )
                )
            )
            .scalars()
            .all()
        )
        intentos = (
            (
                await observador.execute(
                    select(IntentoEmisionFiscal).order_by(IntentoEmisionFiscal.id)
                )
            )
            .scalars()
            .all()
        )
        operacion_actual = await observador.get(OperacionIdempotente, operacion_id)
        lote_actual = await observador.get(LoteComprobante, lote_id)
        grupos = (
            (
                await observador.execute(
                    select(LoteComprobanteGrupo).order_by(LoteComprobanteGrupo.id)
                )
            )
            .scalars()
            .all()
        )

    assert [guarda.fase for guarda in guardas] == [
        "cerrada_terminal",
        "cerrada_pre_arca",
    ]
    assert [intento.estado for intento in intentos] == [
        "autorizado",
        "fallido_verificado",
    ]
    assert operacion_actual.estado == "requiere_reconciliacion"
    assert lote_actual.estado == "requiere_reconciliacion"
    assert [grupo.estado for grupo in grupos] == [
        "validado",
        "requiere_reconciliacion",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("batch", [False, True], ids=["individual", "batch"])
async def test_fecae_observa_guarda_e_intentos_commiteados_en_otra_conexion(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    batch: bool,
) -> None:
    """FECAE solo comienza cuando otra conexión ya ve toda la frontera durable."""
    db_path = tmp_path / f"rece-observable-{int(batch)}.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)
    SessionArchivo = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with SessionArchivo() as db:
            empresa = Empresa(
                razon_social="Empresa RECE observable",
                cuit="20123456789",
                condicion_iva="Responsable Inscripto",
                domicilio="Domicilio sintético 123",
                localidad="Ciudad de prueba",
                provincia="Buenos Aires",
                codigo_postal="1000",
                inicio_actividades=date(2020, 1, 1),
            )
            db.add(empresa)
            await db.flush()
            usuario = Usuario(
                email="rece-observable@example.test",
                hashed_password="hash-sintetico",
                nombre="Usuario RECE",
                empresa_id=empresa.id,
            )
            punto = PuntoVenta(
                numero=1,
                nombre="Principal observable",
                activo=True,
                es_webservice=True,
                empresa_id=empresa.id,
                revision_fiscal=1,
            )
            certificado = Certificado(
                nombre="Certificado observable",
                cuit=empresa.cuit,
                fecha_emision=date(2026, 1, 1),
                fecha_vencimiento=date(2027, 1, 1),
                archivo_crt="observable.crt",
                archivo_key="observable.key",
                activo=True,
                ambiente=settings.arca_env,
                empresa_id=empresa.id,
            )
            db.add_all([usuario, punto, certificado])
            await db.commit()
            assert usuario.id == 1

            cantidad = 2 if batch else 1
            requests = [
                EmitirComprobanteRequest(
                    empresa_id=empresa.id,
                    punto_venta_id=punto.id,
                    tipo_comprobante=6,
                    concepto=1,
                    fecha_emision=date(2026, 8, 8),
                    tipo_documento=99,
                    numero_documento="0",
                    razon_social=f"Receptor observable {indice}",
                    condicion_iva="Consumidor Final",
                    guardar_cliente=False,
                    moneda="PES",
                    cotizacion=Decimal("1"),
                    confirmacion_duplicado_logico=indice > 1,
                    items=[
                        ItemComprobanteCreate(
                            descripcion=f"Servicio observable {indice}",
                            cantidad=Decimal("1"),
                            unidad="unidad",
                            precio_unitario=Decimal("1000"),
                            iva_porcentaje=Decimal("0"),
                        )
                    ],
                )
                for indice in range(1, cantidad + 1)
            ]
            operacion, contexto, metadata = await _crear_operacion_rece_sintetica(
                db,
                empresa=empresa,
                punto_venta=punto,
                requests=requests,
                batch=batch,
            )
            operacion_id = int(operacion.id)
            observaciones_fecae = 0

            class FakeWSFEClient:
                """Inspecciona la base desde otra conexión al entrar a FECAE."""

                def __init__(self, *args, **kwargs) -> None:
                    """Acepta la firma productiva sin abrir red."""

                async def fe_comp_ultimo_autorizado(
                    self,
                    punto_venta_numero,
                    tipo,
                ):
                    """Mantiene alineada la numeración en ambos preflights."""
                    return 0

                async def _observar_frontera(self) -> None:
                    """Comprueba el commit desde una conexión SQLite distinta."""
                    nonlocal observaciones_fecae
                    async with SessionArchivo() as observador:
                        operacion_visible = await observador.get(
                            OperacionIdempotente,
                            operacion_id,
                        )
                        asociaciones = list(
                            (
                                await observador.scalars(
                                    select(OperacionIdempotenteElegibilidadRece).where(
                                        OperacionIdempotenteElegibilidadRece.operacion_id
                                        == operacion_id
                                    )
                                )
                            ).all()
                        )
                        guardas = list(
                            (
                                await observador.scalars(
                                    select(PuntoVentaGuardaEmisionRece).where(
                                        PuntoVentaGuardaEmisionRece.operacion_id
                                        == operacion_id
                                    )
                                )
                            ).all()
                        )
                        intentos = list(
                            (
                                await observador.scalars(
                                    select(IntentoEmisionFiscal).where(
                                        IntentoEmisionFiscal.operacion_id
                                        == operacion_id
                                    )
                                )
                            ).all()
                        )
                        assert operacion_visible is not None
                        assert operacion_visible.rece_snapshot_hash == (
                            ElegibilidadReceService.calcular_digest_contextos(
                                [contexto]
                            )
                        )
                        assert len(asociaciones) == 1
                        assert asociaciones[0].elegibilidad_revision_id == (
                            contexto.elegibilidad_revision_id
                        )
                        assert len(guardas) == 1
                        assert guardas[0].fase == "arca_iniciada"
                        assert guardas[0].arca_iniciada_en is not None
                        assert len(intentos) == cantidad
                        assert {intento.guarda_rece_id for intento in intentos} == {
                            guardas[0].id
                        }
                        assert {intento.estado for intento in intentos} == {
                            "en_proceso"
                        }
                    observaciones_fecae += 1

                async def fe_cae_solicitar(self, arca_request):
                    """Observa y autoriza la emisión individual."""
                    await self._observar_frontera()
                    return CAEResponse(
                        cae="12345678901231",
                        cae_vencimiento="20260818",
                        numero_comprobante=arca_request.cbte_desde,
                        tipo_cbte=arca_request.tipo_cbte,
                        punto_venta=arca_request.punto_venta,
                        resultado="A",
                    )

                async def fe_cae_solicitar_lote(self, arca_requests):
                    """Observa una vez y autoriza todos los intentos del batch."""
                    await self._observar_frontera()
                    return [
                        CAEResponse(
                            cae=f"1234567890123{indice}",
                            cae_vencimiento="20260818",
                            numero_comprobante=arca_request.cbte_desde,
                            tipo_cbte=arca_request.tipo_cbte,
                            punto_venta=arca_request.punto_venta,
                            resultado="A",
                        )
                        for indice, arca_request in enumerate(arca_requests, start=1)
                    ]

            async def fake_ticket(self, empresa, certificado):
                return SimpleNamespace(token="token", sign="sign")

            async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
                return None

            monkeypatch.setattr(
                "app.services.facturacion_service.WSFEv1Client",
                FakeWSFEClient,
            )
            monkeypatch.setattr(
                FacturacionService,
                "_obtener_ticket_acceso",
                fake_ticket,
            )
            monkeypatch.setattr(
                FacturacionService,
                "_validar_punto_venta_habilitado",
                fake_validar_punto,
            )

            service = FacturacionService(db)
            if batch:
                resultados = await service.emitir_comprobantes_lote(
                    requests,
                    max_registros=cantidad,
                    contextos=metadata,
                )
                assert all(resultado.exito for resultado in resultados)
            else:
                resultado = await service.emitir_comprobante(
                    requests[0],
                    operacion_id=operacion_id,
                    contexto_rece=contexto,
                    contextos_operacion=[contexto],
                )
                assert resultado.exito is True
            assert observaciones_fecae == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("punto_fallo", ["cas", "guardar"])
async def test_emitir_rehidrata_grafo_rece_despues_de_rollback(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    punto_fallo: str,
) -> None:
    """CAS y persistencia post-CAE recargan intento y guarda tras rollback."""
    llamadas_fecae = 0

    class FakeWSFEClient:
        """Mantiene numeración estable y hace observable la frontera FECAE."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma productiva sin abrir red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene el próximo número fiscal en uno."""
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Autoriza solo el caso cuyo fallo ocurre al guardar localmente."""
            nonlocal llamadas_fecae
            llamadas_fecae += 1
            return CAEResponse(
                cae="12345678901234",
                cae_vencimiento="20260818",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    async def fake_ticket(self, empresa, certificado):
        """Evita WSAA real en el oracle de persistencia."""
        return SimpleNamespace(token="token", sign="sign")

    async def fake_certificado(self, empresa_id):
        """Devuelve material sintético sin leer archivos locales."""
        return SimpleNamespace(id=1, ambiente=settings.arca_env)

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        """Aísla el test de la lectura de parámetros WSFE."""

    punto_venta = PuntoVenta(
        numero=93,
        nombre=f"Rollback RECE {punto_fallo}",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 8, 9),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        items=[
            ItemComprobanteCreate(
                descripcion="Servicio sintético",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=False,
    )
    operacion_id = int(operacion.id)

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        fake_certificado,
    )
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    if punto_fallo == "cas":

        async def rollback_y_rechazar_cas(self, **kwargs):
            """Expira el grafo como un CAS que perdió ownership."""
            await self.db.rollback()
            raise ElegibilidadReceError("El snapshot cambió antes de ARCA.")

        monkeypatch.setattr(
            ElegibilidadReceService,
            "marcar_arca_iniciada",
            rollback_y_rechazar_cas,
        )
    else:

        async def rollback_y_fallar_guardado(self, *args, **kwargs):
            """Expira el grafo después de un CAE ya autorizado."""
            await self.db.rollback()
            raise RuntimeError("fallo sintético post-ARCA")

        monkeypatch.setattr(
            FacturacionService,
            "_guardar_comprobante",
            rollback_y_fallar_guardado,
        )

    resultado = await FacturacionService(db_session).emitir_comprobante(
        request,
        operacion_id=operacion_id,
        contexto_rece=contexto,
        contextos_operacion=[contexto],
    )

    guardas = list(
        (
            await db_session.scalars(
                select(PuntoVentaGuardaEmisionRece).where(
                    PuntoVentaGuardaEmisionRece.operacion_id == operacion_id
                )
            )
        ).all()
    )
    intentos = list(
        (
            await db_session.scalars(
                select(IntentoEmisionFiscal).where(
                    IntentoEmisionFiscal.operacion_id == operacion_id
                )
            )
        ).all()
    )
    assert len(guardas) == 1
    assert len(intentos) == 1
    assert resultado.exito is False
    if punto_fallo == "cas":
        assert llamadas_fecae == 0
        assert resultado.requiere_reconciliacion is False
        assert guardas[0].fase == "cerrada_pre_arca"
        assert intentos[0].estado == "fallido_verificado"
    else:
        assert llamadas_fecae == 1
        assert resultado.requiere_reconciliacion is True
        assert guardas[0].fase == "requiere_reconciliacion"
        assert intentos[0].estado == "requiere_reconciliacion"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyTimeoutError, OperationalError],
    ids=["timeout", "operational"],
)
async def test_emitir_comprobante_propaga_db_temporal_antes_de_arca(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    """Una indisponibilidad local pre-ARCA propaga sin solicitar CAE."""
    llamadas_fecae = 0

    class FakeWSFEClient:
        """Cliente que registra cualquier solicitud fiscal inesperada."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_cae_solicitar(self, _arca_request):
            """Registra una llamada que nunca debería ocurrir."""
            nonlocal llamadas_fecae
            llamadas_fecae += 1
            raise AssertionError("No debe solicitar CAE con la base indisponible")

    async def fail_validar(self, request):
        raise _crear_error_db_temporal(error_type)

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fail_validar)
    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 7, 11),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )

    with pytest.raises(error_type):
        await service.emitir_comprobante(request)

    assert llamadas_fecae == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyTimeoutError, OperationalError],
    ids=["timeout", "operational"],
)
@pytest.mark.parametrize(
    "rollback_falla",
    [False, True],
    ids=["rollback-ok", "rollback-db-falla"],
)
async def test_emitir_comprobante_post_arca_requiere_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    rollback_falla: bool,
):
    """Si falla la persistencia posterior a CAE, la respuesta no es reintentable."""

    class FakeWSFEClient:
        """Cliente WSFE simulado con CAE autorizado."""

        llamadas_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene estable el próximo número reservado en la prueba."""
            return 76

        async def fe_cae_solicitar(self, _arca_request):
            """Devuelve un CAE autorizado simulado."""
            type(self).llamadas_fecae += 1
            return SimpleNamespace(
                cae="12345678901234",
                cae_vencimiento="20260526",
            )

    async def fake_validar_datos(self, request):
        return None

    async def fake_tomar_lock(self, *args, **kwargs):
        return None

    async def fake_obtener_empresa(self, empresa_id):
        return SimpleNamespace(id=empresa_id, cuit=test_empresa.cuit)

    async def fake_obtener_certificado_activo(self, empresa_id):
        return SimpleNamespace(
            archivo_crt="empresa-test.crt",
            archivo_key="empresa-test.key",
        )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    async def fake_obtener_proximo(self, *args, **kwargs):
        return 77

    async def fail_guardar(self, *args, **kwargs):
        raise _crear_error_db_temporal(error_type)

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_tomar_lock_numeracion", fake_tomar_lock)
    monkeypatch.setattr(FacturacionService, "_obtener_empresa", fake_obtener_empresa)

    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        fake_obtener_certificado_activo,
    )
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    monkeypatch.setattr(
        FacturacionService, "_obtener_proximo_numero", fake_obtener_proximo
    )
    monkeypatch.setattr(FacturacionService, "_guardar_comprobante", fail_guardar)
    original_rollback = None
    if rollback_falla:
        original_rollback = AsyncSession.rollback

        async def fail_rollback(session):
            if session is db_session:
                raise _crear_error_db_temporal(error_type)
            return await original_rollback(session)

        monkeypatch.setattr(AsyncSession, "rollback", fail_rollback)

    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.commit()
    await db_session.refresh(punto_venta)

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=FECHA_FISCAL_PRUEBA,
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=False,
    )
    operacion_id = int(operacion.id)

    try:
        resultado = await service.emitir_comprobante(
            request,
            operacion_id=operacion_id,
            contexto_rece=contexto,
            contextos_operacion=[contexto],
        )
    finally:
        if original_rollback is not None:
            monkeypatch.setattr(AsyncSession, "rollback", original_rollback)

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        operacion_actual = await observador.get(
            OperacionIdempotente,
            operacion_id,
        )
        intentos = (
            (
                await observador.execute(
                    select(IntentoEmisionFiscal).where(
                        IntentoEmisionFiscal.operacion_id == operacion_id
                    )
                )
            )
            .scalars()
            .all()
        )
        guardas = (
            (
                await observador.execute(
                    select(PuntoVentaGuardaEmisionRece).where(
                        PuntoVentaGuardaEmisionRece.operacion_id == operacion_id
                    )
                )
            )
            .scalars()
            .all()
        )
        comprobantes = (
            (
                await observador.execute(
                    select(Comprobante).where(Comprobante.empresa_id == test_empresa.id)
                )
            )
            .scalars()
            .all()
        )

    assert FakeWSFEClient.llamadas_fecae == 1
    assert comprobantes == []
    assert operacion_actual is not None
    assert operacion_actual.estado == "requiere_reconciliacion"
    assert len(intentos) == 1
    assert intentos[0].estado == "requiere_reconciliacion"
    assert len(guardas) == 1
    assert guardas[0].fase == "requiere_reconciliacion"
    assert resultado.exito is False
    assert resultado.requiere_reconciliacion is True
    assert resultado.categoria_error == "post_arca_persistencia"
    assert resultado.cae == "12345678901234"
    assert resultado.numero == 77
    assert resultado.punto_venta == 1
    assert resultado.total == Decimal("1000.00")
    respuesta_json = resultado.model_dump_json()
    assert "secreto" not in respuesta_json
    assert "privada.key" not in respuesta_json

    operacion_publicable = await db_session.get(
        OperacionIdempotente,
        operacion_id,
        populate_existing=True,
    )
    assert operacion_publicable is not None
    await IdempotenciaFiscalService(db_session).guardar_resultado_operacion_sync(
        operacion_publicable,
        response_json=resultado,
        estado="requiere_reconciliacion",
    )
    with pytest.raises(SQLAlchemyTimeoutError):
        await IdempotenciaFiscalService(db_session).guardar_resultado_operacion_sync(
            operacion_publicable,
            response_json={"resultado": "adulterado"},
            estado="finalizado",
        )
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        operacion_publicada = await observador.get(
            OperacionIdempotente,
            operacion_id,
        )
    assert operacion_publicada is not None
    assert operacion_publicada.estado == "requiere_reconciliacion"
    assert operacion_publicada.response_json["categoria_error"] == (
        "post_arca_persistencia"
    )


@pytest.mark.asyncio
async def test_persistir_reconciliacion_rechaza_intento_y_guarda_de_otra_operacion(
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """Un grafo cruzado revierte sin inmovilizar evidencia de otra operación."""
    punto_venta = PuntoVenta(
        numero=41,
        nombre="Punto reconciliación",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.commit()
    await db_session.refresh(punto_venta)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=FECHA_FISCAL_PRUEBA,
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Servicio reconciliación",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=False,
    )
    elegibilidad = ElegibilidadReceService(db_session)
    guarda = await elegibilidad.crear_guarda_pre_arca(
        operacion_id=operacion.id,
        contexto=contexto,
        contextos_operacion=[contexto],
    )
    intento = await IdempotenciaFiscalService(db_session).crear_intento_emision(
        request=request,
        punto_venta=punto_venta,
        numero_planificado=1,
        total=Decimal("1000"),
        operacion_id=operacion.id,
        usuario_id=None,
        lote_id=None,
        grupo_id=None,
        contexto_rece=contexto,
        guarda_rece_id=guarda.id,
        commit=False,
    )
    await db_session.commit()
    await elegibilidad.marcar_arca_iniciada(
        guarda=guarda,
        contexto=contexto,
        tipo_comprobante=request.tipo_comprobante,
    )
    operacion_id = int(operacion.id)
    intento_id = int(intento.id)
    guarda_id = int(guarda.id)
    guarda_ajena = SimpleNamespace(
        id=guarda_id,
        operacion_id=operacion_id + 1,
    )
    respuesta = EmitirComprobanteResponse(
        exito=False,
        tipo_comprobante=request.tipo_comprobante,
        punto_venta=punto_venta.numero,
        numero=1,
        fecha=request.fecha_emision,
        total=Decimal("1000"),
        mensaje="El resultado requiere reconciliación.",
        errores=["No reintentes hasta reconciliar."],
        requiere_reconciliacion=True,
        categoria_error="post_arca_persistencia",
    )

    with pytest.raises(SQLAlchemyTimeoutError):
        await FacturacionService(db_session)._persistir_intento_y_guarda_rece(
            idempotencia=IdempotenciaFiscalService(db_session),
            intento=intento,
            respuesta=respuesta,
            guarda=guarda_ajena,
            fase="reconciliacion",
            commit=True,
            contexto="grafo_cruzado",
        )

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as observador:
        operacion_actual = await observador.get(
            OperacionIdempotente,
            operacion_id,
        )
        intento_actual = await observador.get(IntentoEmisionFiscal, intento_id)
        guarda_actual = await observador.get(
            PuntoVentaGuardaEmisionRece,
            guarda_id,
        )
    assert operacion_actual is not None
    assert operacion_actual.estado == "en_proceso"
    assert intento_actual is not None
    assert intento_actual.estado == "en_proceso"
    assert guarda_actual is not None
    assert guarda_actual.fase == "arca_iniciada"


@pytest.mark.asyncio
@pytest.mark.parametrize("modo", ["individual", "batch"])
async def test_excepcion_inesperada_post_arca_requiere_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    modo: str,
) -> None:
    """Individual y batch bloquean reintentos ante una excepción post-ARCA."""

    class FakeWSFEClient:
        """Cliente WSFE que falla después de cruzar la frontera fiscal."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene estable el próximo número reservado en la prueba."""
            return 76

        async def fe_cae_solicitar(self, _arca_request):
            """Simula un fallo inesperado durante la solicitud individual."""
            raise RuntimeError("secreto privada.key")

        async def fe_cae_solicitar_lote(self, _arca_requests):
            """Simula un fallo inesperado durante la solicitud batch."""
            raise RuntimeError("secreto privada.key")

    async def fake_validar_datos(self, request):
        """Acepta el request de prueba."""

    async def fake_tomar_lock(self, *args, **kwargs):
        """Evita locks dependientes del motor de base."""

    async def fake_obtener_empresa(self, empresa_id):
        """Devuelve el emisor de prueba."""
        return SimpleNamespace(id=empresa_id, cuit=test_empresa.cuit)

    async def fake_obtener_certificado_activo(self, empresa_id):
        """Devuelve material de certificado simulado."""
        return SimpleNamespace(
            archivo_crt="empresa-test.crt",
            archivo_key="empresa-test.key",
        )

    async def fake_ticket(self, empresa, certificado):
        """Devuelve credenciales WSAA simuladas."""
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        """Acepta el punto de venta de prueba."""

    async def fake_obtener_proximo(self, *args, **kwargs):
        """Reserva un número fiscal conocido."""
        return 77

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_tomar_lock_numeracion", fake_tomar_lock)
    monkeypatch.setattr(FacturacionService, "_obtener_empresa", fake_obtener_empresa)
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        fake_obtener_certificado_activo,
    )
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_proximo_numero",
        fake_obtener_proximo,
    )

    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.commit()
    await db_session.refresh(punto_venta)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 7, 13),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    operacion, contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=modo == "batch",
    )
    operacion_id = int(operacion.id)

    service = FacturacionService(db_session)
    if modo == "individual":
        resultado = await service.emitir_comprobante(
            request,
            operacion_id=operacion_id,
            contexto_rece=contexto,
            contextos_operacion=[contexto],
        )
    else:
        resultado = (
            await service.emitir_comprobantes_lote(
                [request],
                contextos=metadata,
            )
        )[0]

    intento = await db_session.scalar(select(IntentoEmisionFiscal))
    assert resultado.exito is False
    assert resultado.requiere_reconciliacion is True
    assert resultado.categoria_error == "arca_respuesta_incierta"
    assert resultado.numero == 77
    assert resultado.punto_venta == 1
    assert intento is not None
    assert intento.estado == "requiere_reconciliacion"
    respuesta_json = resultado.model_dump_json()
    assert "secreto" not in respuesta_json
    assert "privada.key" not in respuesta_json


@pytest.mark.asyncio
async def test_emitir_comprobante_sanea_error_interno_del_servicio(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los catches internos no deben devolver excepciones arbitrarias."""

    async def fail_validar(self, request):
        raise RuntimeError("detalle interno secreto; ruta C:\\certs\\privada.key")

    monkeypatch.setattr(FacturacionService, "_validar_datos", fail_validar)
    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 7, 9),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )

    fase_compartida = FaseSolicitudArca(iniciada=True)
    individual = await service.emitir_comprobante(
        request,
        fase_solicitud_arca=fase_compartida,
    )
    batch = (
        await service.emitir_comprobantes_lote(
            [request],
            contextos=[{}],
            fase_solicitud_arca=fase_compartida,
        )
    )[0]

    for resultado in (individual, batch):
        respuesta_json = resultado.model_dump_json()
        assert resultado.exito is False
        assert resultado.requiere_reconciliacion is False
        assert "secreto" not in respuesta_json
        assert "privada.key" not in respuesta_json
        assert "logs privados" in respuesta_json


@pytest.mark.asyncio
async def test_emitir_comprobante_commit_false_no_confirma_transaccion_externa(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """La emisión `commit=False` no debe confirmar comprobante ni intento final."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    certificado = Certificado(
        nombre="Certificado Test",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_venta, certificado])
    await db_session.commit()
    await db_session.refresh(punto_venta)

    class FakeWSFEClient:
        """Cliente WSFE simulado con CAE autorizado."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Simula que ARCA no tiene comprobantes previos."""
            return 0

        async def fe_cae_solicitar(self, arca_request):
            """Devuelve un CAE aprobado para el comprobante solicitado."""
            return CAEResponse(
                cae="12345678901234",
                cae_vencimiento="20260610",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )

    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=FECHA_FISCAL_PRUEBA,
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    _fijar_reloj_facturacion(monkeypatch)
    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=False,
    )
    operacion_id = int(operacion.id)

    service = FacturacionService(db_session)
    resultado = await service.emitir_comprobante(
        request,
        commit=False,
        operacion_id=operacion_id,
        contexto_rece=contexto,
        contextos_operacion=[contexto],
    )

    assert resultado.exito is True

    await db_session.rollback()

    comprobantes = (await db_session.execute(select(Comprobante))).scalars().all()
    intentos = (await db_session.execute(select(IntentoEmisionFiscal))).scalars().all()

    assert comprobantes == []
    assert len(intentos) == 1
    assert intentos[0].estado == "en_proceso"
    assert intentos[0].comprobante_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("modo", ["individual", "batch"])
@pytest.mark.parametrize("fallar_cierre", [False, True])
async def test_rechazo_arca_exige_cierre_durable_o_propaga_error_sanitizado(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    modo: str,
    fallar_cierre: bool,
):
    """Un rechazo solo se devuelve si su cierre durable pudo persistirse."""

    class FakeWSFEClient:
        """Cliente WSFE simulado con rechazo explícito sin CAE."""

        llamadas_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_cae_solicitar(self, _arca_request):
            """Devuelve una respuesta no aprobada."""
            type(self).llamadas_fecae += 1
            return self._respuesta_no_aprobada()

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Simula que ARCA no tiene comprobantes previos."""
            return 76

        async def fe_cae_solicitar_lote(self, arca_requests):
            """Devuelve un rechazo por cada solicitud batch."""
            type(self).llamadas_fecae += 1
            return [self._respuesta_no_aprobada() for _ in arca_requests]

        @staticmethod
        def _respuesta_no_aprobada():
            """Construye un rechazo fiscal sin CAE."""
            return CAEResponse(
                cae=None,
                cae_vencimiento=None,
                numero_comprobante=77,
                tipo_cbte=6,
                punto_venta=1,
                resultado="R",
                errores=[
                    {
                        "code": 10016,
                        "msg": "El número debe ser consecutivo al último autorizado",
                    }
                ],
            )

    async def fake_validar_datos(self, request):
        return None

    async def fake_tomar_lock(self, *args, **kwargs):
        return None

    async def fake_obtener_empresa(self, empresa_id):
        return SimpleNamespace(id=empresa_id, cuit=test_empresa.cuit)

    async def fake_obtener_certificado_activo(self, empresa_id):
        return SimpleNamespace(
            archivo_crt="empresa-test.crt",
            archivo_key="empresa-test.key",
        )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    async def fake_obtener_proximo(self, *args, **kwargs):
        return 77

    async def fail_guardar(self, *args, **kwargs):
        raise AssertionError("No debe guardar una respuesta sin aprobación")

    async def fallar_actualizacion_intento(self, intento, response, **kwargs):
        raise RuntimeError("secreto privada.key")

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_tomar_lock_numeracion", fake_tomar_lock)
    monkeypatch.setattr(FacturacionService, "_obtener_empresa", fake_obtener_empresa)

    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        fake_obtener_certificado_activo,
    )
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    monkeypatch.setattr(
        FacturacionService, "_obtener_proximo_numero", fake_obtener_proximo
    )
    monkeypatch.setattr(FacturacionService, "_guardar_comprobante", fail_guardar)
    if fallar_cierre:
        monkeypatch.setattr(
            IdempotenciaFiscalService,
            "actualizar_intento_desde_respuesta",
            fallar_actualizacion_intento,
        )
    if modo == "batch" and fallar_cierre:
        respuesta_original = FacturacionService._respuesta_si_arca_no_autorizo
        llamadas_clasificacion = 0

        def fallar_primera_clasificacion(self, *args, **kwargs):
            """Fuerza el fallback amplio y luego permite clasificar el R."""
            nonlocal llamadas_clasificacion
            llamadas_clasificacion += 1
            if llamadas_clasificacion == 1:
                raise RuntimeError("fallo inesperado post-ARCA")
            return respuesta_original(self, *args, **kwargs)

        monkeypatch.setattr(
            FacturacionService,
            "_respuesta_si_arca_no_autorizo",
            fallar_primera_clasificacion,
        )

    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.commit()
    await db_session.refresh(punto_venta)

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=FECHA_FISCAL_PRUEBA,
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    operacion, contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=modo == "batch",
    )
    operacion_id = int(operacion.id)

    async def emitir() -> object:
        """Ejecuta el camino individual o batch con el mismo grafo RECE."""
        if modo == "individual":
            return await service.emitir_comprobante(
                request,
                operacion_id=operacion_id,
                contexto_rece=contexto,
                contextos_operacion=[contexto],
            )
        return (
            await service.emitir_comprobantes_lote(
                [request],
                max_registros=1,
                contextos=metadata,
            )
        )[0]

    if fallar_cierre:
        with pytest.raises(SQLAlchemyTimeoutError) as exc_info:
            await emitir()
        error_publico = str(exc_info.value)
        assert "secreto" not in error_publico
        assert "privada.key" not in error_publico
        resultado = None
    else:
        resultado = await emitir()
    comprobantes = (await db_session.execute(select(Comprobante))).scalars().all()
    intentos = (await db_session.execute(select(IntentoEmisionFiscal))).scalars().all()
    guardas = (
        (await db_session.execute(select(PuntoVentaGuardaEmisionRece))).scalars().all()
    )
    operacion_actual = await db_session.get(OperacionIdempotente, operacion_id)

    assert FakeWSFEClient.llamadas_fecae == 1
    assert comprobantes == []
    assert len(intentos) == 1
    assert len(guardas) == 1
    assert operacion_actual is not None
    if fallar_cierre:
        assert resultado is None
        assert intentos[0].estado == "en_proceso"
        assert guardas[0].fase == "arca_iniciada"
        assert operacion_actual.estado == "en_proceso"
        assert operacion_actual.response_json is None
    else:
        assert resultado is not None
        assert resultado.exito is False
        assert resultado.requiere_reconciliacion is False
        assert resultado.categoria_error == "arca_no_aprobado"
        assert resultado.cae is None
        assert intentos[0].estado == "rechazado_arca"
        assert guardas[0].fase == "cerrada_terminal"
        respuesta_json = resultado.model_dump_json()
        assert "secreto" not in respuesta_json
        assert "privada.key" not in respuesta_json
        assert "10016" in respuesta_json


@pytest.mark.asyncio
async def test_emitir_comprobantes_lote_usa_un_request_arca_y_persiste_numeracion(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Un sublote homogéneo debe solicitar CAE una vez y guardar números consecutivos."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    certificado = Certificado(
        nombre="Certificado Test",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_venta, certificado])
    await db_session.commit()
    await db_session.refresh(punto_venta)

    class FakeWSFEClient:
        """Cliente WSFE simulado para emisión batch."""

        arca_requests = []
        consultas_numeracion = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Simula que ARCA no tiene comprobantes previos."""
            FakeWSFEClient.consultas_numeracion += 1
            return 0

        async def fe_cae_solicitar_lote(self, arca_requests):
            """Captura el sublote y devuelve CAE aprobados fuera de orden."""
            FakeWSFEClient.arca_requests.append(arca_requests)
            respuestas = [
                CAEResponse(
                    cae=f"1234567890123{arca_request.cbte_desde}",
                    cae_vencimiento="20260610",
                    numero_comprobante=arca_request.cbte_desde,
                    tipo_cbte=arca_request.tipo_cbte,
                    punto_venta=arca_request.punto_venta,
                    resultado="A",
                )
                for arca_request in arca_requests
            ]
            return list(reversed(respuestas))

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )

    def request_cliente(nombre: str) -> EmitirComprobanteRequest:
        return EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=1,
            fecha_emision=FECHA_FISCAL_PRUEBA,
            tipo_documento=99,
            numero_documento="0",
            razon_social=nombre,
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Producto",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000"),
                    iva_porcentaje=Decimal("0"),
                )
            ],
        )

    _fijar_reloj_facturacion(monkeypatch)
    requests = [request_cliente("Cliente Uno"), request_cliente("Cliente Dos")]
    _operacion, _contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=requests,
        batch=True,
    )
    service = FacturacionService(db_session)
    resultados = await service.emitir_comprobantes_lote(
        requests,
        max_registros=2,
        contextos=metadata,
    )
    comprobantes = (
        (await db_session.execute(select(Comprobante).order_by(Comprobante.numero)))
        .scalars()
        .all()
    )

    assert [resultado.exito for resultado in resultados] == [True, True]
    assert [resultado.numero for resultado in resultados] == [1, 2]
    assert [resultado.cae for resultado in resultados] == [
        "12345678901231",
        "12345678901232",
    ]
    assert [comprobante.cae for comprobante in comprobantes] == [
        "12345678901231",
        "12345678901232",
    ]
    assert len(FakeWSFEClient.arca_requests) == 1
    assert FakeWSFEClient.consultas_numeracion == 2
    assert [request.cbte_desde for request in FakeWSFEClient.arca_requests[0]] == [
        1,
        2,
    ]
    assert [comprobante.numero for comprobante in comprobantes] == [1, 2]


async def _preparar_escenario_numeracion_batch(
    db_session: AsyncSession,
    test_empresa: Empresa,
    monkeypatch: pytest.MonkeyPatch,
    wsfe_client_class: type,
) -> tuple[
    FacturacionService,
    list[EmitirComprobanteRequest],
    list[dict[str, object]],
]:
    """Configura un sublote homogéneo con datos fiscales sintéticos."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    certificado = Certificado(
        nombre="Certificado Test",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_venta, certificado])
    await db_session.commit()
    await db_session.refresh(punto_venta)

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_datos(
        self: FacturacionService, request: EmitirComprobanteRequest
    ) -> None:
        """Aísla la fecha explícita del test respecto del reloj de ejecución."""

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    monkeypatch.setattr(
        "app.services.facturacion_service.WSFEv1Client",
        wsfe_client_class,
    )
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )

    def request_cliente(nombre: str) -> EmitirComprobanteRequest:
        return EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=1,
            fecha_emision=date(2026, 7, 29),
            tipo_documento=99,
            numero_documento="0",
            razon_social=nombre,
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Producto",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000"),
                    iva_porcentaje=Decimal("0"),
                )
            ],
        )

    requests = [
        request_cliente("Cliente Uno"),
        request_cliente("Cliente Dos"),
    ]
    _operacion, _contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=requests,
        batch=True,
    )
    return FacturacionService(db_session), requests, metadata


@pytest.mark.asyncio
async def test_emitir_comprobantes_lote_usa_historia_externa_como_inicio_del_rango(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """La historia externa legítima debe iniciar el rango en último ARCA más uno."""

    class FakeWSFEClient:
        """Cliente WSFE con historia externa estable."""

        consultas_numeracion = 0
        numeros_solicitados: list[int] = []

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Informa cinco comprobantes previos ajenos a FactuFlow."""
            FakeWSFEClient.consultas_numeracion += 1
            return 5

        async def fe_cae_solicitar_lote(self, arca_requests):
            """Autoriza el rango reservado por el servicio."""
            FakeWSFEClient.numeros_solicitados = [
                request.cbte_desde for request in arca_requests
            ]
            return [
                CAEResponse(
                    cae=f"1234567890123{request.cbte_desde}",
                    cae_vencimiento="20260808",
                    numero_comprobante=request.cbte_desde,
                    tipo_cbte=request.tipo_cbte,
                    punto_venta=request.punto_venta,
                    resultado="A",
                )
                for request in arca_requests
            ]

    service, requests, metadata = await _preparar_escenario_numeracion_batch(
        db_session,
        test_empresa,
        monkeypatch,
        FakeWSFEClient,
    )

    resultados = await service.emitir_comprobantes_lote(
        requests,
        max_registros=2,
        contextos=metadata,
    )

    intentos = (
        (
            await db_session.execute(
                select(IntentoEmisionFiscal).order_by(
                    IntentoEmisionFiscal.numero_planificado
                )
            )
        )
        .scalars()
        .all()
    )
    assert [resultado.numero for resultado in resultados] == [6, 7]
    assert [resultado.exito for resultado in resultados] == [True, True]
    assert FakeWSFEClient.consultas_numeracion == 2
    assert FakeWSFEClient.numeros_solicitados == [6, 7]
    assert [intento.numero_planificado for intento in intentos] == [6, 7]
    assert [intento.estado for intento in intentos] == ["autorizado", "autorizado"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("segundo_preflight", "categoria_error"),
    [
        ("avanza", "numeracion_arca_cambio_pre_arca"),
        ("falla", "preflight_arca_no_disponible"),
    ],
)
async def test_emitir_comprobantes_lote_aborta_todo_el_rango_antes_de_arca(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    segundo_preflight: str,
    categoria_error: str,
):
    """Un segundo preflight inestable debe cerrar el rango sin solicitar CAE."""

    class FakeWSFEClient:
        """Cliente WSFE que cambia o falla después de crear las reservas."""

        consultas_numeracion = 0
        llamadas_lote = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Mantiene el primer diagnóstico y desestabiliza el segundo."""
            FakeWSFEClient.consultas_numeracion += 1
            if FakeWSFEClient.consultas_numeracion == 1:
                return 0
            if segundo_preflight == "avanza":
                return 1
            raise ArcaServiceError("preflight simulado no disponible")

        async def fe_cae_solicitar_lote(self, arca_requests):
            """Falla la prueba si el servicio cruza la frontera ARCA."""
            FakeWSFEClient.llamadas_lote += 1
            raise AssertionError("No debe solicitar CAE con un rango obsoleto")

    service, requests, metadata = await _preparar_escenario_numeracion_batch(
        db_session,
        test_empresa,
        monkeypatch,
        FakeWSFEClient,
    )
    fase_solicitud_arca = FaseSolicitudArca()

    resultados = await service.emitir_comprobantes_lote(
        requests,
        max_registros=2,
        contextos=metadata,
        fase_solicitud_arca=fase_solicitud_arca,
    )

    intentos = (
        (
            await db_session.execute(
                select(IntentoEmisionFiscal).order_by(
                    IntentoEmisionFiscal.numero_planificado
                )
            )
        )
        .scalars()
        .all()
    )
    comprobantes = (await db_session.execute(select(Comprobante))).scalars().all()
    assert FakeWSFEClient.consultas_numeracion == 2
    assert FakeWSFEClient.llamadas_lote == 0
    assert fase_solicitud_arca.iniciada is False
    assert [resultado.numero for resultado in resultados] == [1, 2]
    assert [resultado.exito for resultado in resultados] == [False, False]
    assert {resultado.categoria_error for resultado in resultados} == {categoria_error}
    assert all(not resultado.requiere_reconciliacion for resultado in resultados)
    assert [intento.numero_planificado for intento in intentos] == [1, 2]
    assert [intento.estado for intento in intentos] == [
        "fallido_verificado",
        "fallido_verificado",
    ]
    assert {intento.categoria_error for intento in intentos} == {categoria_error}
    assert comprobantes == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [RuntimeError, SQLAlchemyTimeoutError, OperationalError],
    ids=["runtime", "timeout", "operational"],
)
async def test_emitir_comprobantes_lote_distingue_db_temporal_en_reserva_pre_arca(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
):
    """Una falla local revierte la preparación y las fallas DB se propagan."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    certificado = Certificado(
        nombre="Certificado Test",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_venta, certificado])
    await db_session.commit()
    await db_session.refresh(punto_venta)

    class FakeWSFEClient:
        """Cliente WSFE que no debe recibir el sublote si falla la reserva."""

        llamadas_lote = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Simula que ARCA no tiene comprobantes previos."""
            return 0

        async def fe_cae_solicitar_lote(self, arca_requests):
            """Falla la prueba si el código contacta ARCA."""
            FakeWSFEClient.llamadas_lote += 1
            raise AssertionError("No debe contactar ARCA si falló la reserva local")

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    async def fake_validar_datos(self, request):
        return None

    original_crear = IdempotenciaFiscalService.crear_intento_emision
    llamadas_reserva = 0

    async def crear_una_reserva_y_fallar(self, **kwargs):
        nonlocal llamadas_reserva
        llamadas_reserva += 1
        if llamadas_reserva == 1:
            return await original_crear(self, **kwargs)
        if error_type is RuntimeError:
            raise RuntimeError("reserva local fallida")
        raise _crear_error_db_temporal(error_type)

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "crear_intento_emision",
        crear_una_reserva_y_fallar,
    )

    def request_cliente(nombre: str) -> EmitirComprobanteRequest:
        return EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=1,
            fecha_emision=date(2026, 7, 6),
            tipo_documento=99,
            numero_documento="0",
            razon_social=nombre,
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Producto",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000"),
                    iva_porcentaje=Decimal("0"),
                )
            ],
        )

    service = FacturacionService(db_session)
    requests = [request_cliente("Cliente Uno"), request_cliente("Cliente Dos")]
    operacion_inicial, _contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=requests,
        batch=True,
    )
    operacion_id = int(operacion_inicial.id)
    if error_type is RuntimeError:
        resultados = await service.emitir_comprobantes_lote(
            requests,
            max_registros=2,
            contextos=metadata,
        )
    else:
        with pytest.raises(error_type):
            await service.emitir_comprobantes_lote(
                requests,
                max_registros=2,
                contextos=metadata,
            )
        resultados = []
    intentos = (await db_session.execute(select(IntentoEmisionFiscal))).scalars().all()
    guardas = (
        (await db_session.execute(select(PuntoVentaGuardaEmisionRece))).scalars().all()
    )
    comprobantes = (await db_session.execute(select(Comprobante))).scalars().all()
    operacion = await db_session.get(
        OperacionIdempotente,
        operacion_id,
        populate_existing=True,
    )
    operacion_con_respuesta_sql_null = await db_session.scalar(
        select(OperacionIdempotente.id).where(
            OperacionIdempotente.id == operacion_id,
            OperacionIdempotente.response_json.is_(None),
        )
    )

    assert FakeWSFEClient.llamadas_lote == 0
    assert llamadas_reserva == 2
    assert intentos == []
    assert guardas == []
    assert comprobantes == []
    assert operacion is not None
    assert operacion.estado == "en_proceso"
    assert operacion.response_json is None
    assert operacion_con_respuesta_sql_null == operacion_id
    if error_type is RuntimeError:
        assert [resultado.exito for resultado in resultados] == [False, False]
        assert [resultado.numero for resultado in resultados] == [1, 2]
        assert all(
            resultado.requiere_reconciliacion is False for resultado in resultados
        )
        assert {resultado.categoria_error for resultado in resultados} == {
            "pre_arca_reserva_fallida"
        }
        assert {resultado.mensaje for resultado in resultados} == {
            "FactuFlow revirtió la preparación local antes de solicitar CAE"
        }
        assert all(
            resultado.errores
            == [
                (
                    "No se solicitó CAE; la transacción local se revirtió por "
                    "completo y no quedó una reserva fiscal durable."
                ),
                ERROR_INTERNO_EMISION_PUBLICO,
            ]
            for resultado in resultados
        )
        assert all(
            "reserva local fallida"
            not in " ".join([resultado.mensaje, *resultado.errores])
            for resultado in resultados
        )
    else:
        assert resultados == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type",
    [SQLAlchemyTimeoutError, OperationalError],
    ids=["timeout", "operational"],
)
async def test_emitir_comprobantes_lote_reconcilia_si_falla_cierre_intento_post_arca(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
):
    """Si falla cerrar el intento tras guardar CAE, no devuelve éxito reintentable."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    certificado = Certificado(
        nombre="Certificado Test",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2027, 1, 1),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente=settings.arca_env,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_venta, certificado])
    await db_session.commit()
    await db_session.refresh(punto_venta)

    class FakeWSFEClient:
        """Cliente WSFE simulado para emisión batch autorizada."""

        llamadas_fecae = 0

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Simula que ARCA no tiene comprobantes previos."""
            return 0

        async def fe_cae_solicitar_lote(self, arca_requests):
            """Devuelve CAE aprobados para todo el sublote."""
            type(self).llamadas_fecae += 1
            return [
                CAEResponse(
                    cae=f"1234567890123{arca_request.cbte_desde}",
                    cae_vencimiento="20260610",
                    numero_comprobante=arca_request.cbte_desde,
                    tipo_cbte=arca_request.tipo_cbte,
                    punto_venta=arca_request.punto_venta,
                    resultado="A",
                )
                for arca_request in arca_requests
            ]

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    async def fake_validar_datos(self, request):
        return None

    original_actualizar = IdempotenciaFiscalService.actualizar_intento_desde_respuesta
    fallos_cierre = 0

    async def fallar_cierre_exitoso(self, intento, response, **kwargs):
        nonlocal fallos_cierre
        if response.exito:
            fallos_cierre += 1
            raise _crear_error_db_temporal(error_type)
        return await original_actualizar(self, intento, response, **kwargs)

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "actualizar_intento_desde_respuesta",
        fallar_cierre_exitoso,
    )

    def request_cliente(nombre: str) -> EmitirComprobanteRequest:
        return EmitirComprobanteRequest(
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            tipo_comprobante=6,
            concepto=1,
            fecha_emision=date(2026, 7, 6),
            tipo_documento=99,
            numero_documento="0",
            razon_social=nombre,
            condicion_iva="Consumidor Final",
            guardar_cliente=False,
            moneda="PES",
            cotizacion=Decimal("1"),
            items=[
                ItemComprobanteCreate(
                    descripcion="Producto",
                    cantidad=Decimal("1"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000"),
                    iva_porcentaje=Decimal("0"),
                )
            ],
        )

    requests = [request_cliente("Cliente Uno"), request_cliente("Cliente Dos")]
    operacion_inicial, _contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=requests,
        batch=True,
    )
    operacion_id = int(operacion_inicial.id)
    service = FacturacionService(db_session)
    resultados = await service.emitir_comprobantes_lote(
        requests,
        max_registros=2,
        contextos=metadata,
    )
    comprobantes = (
        (await db_session.execute(select(Comprobante).order_by(Comprobante.numero)))
        .scalars()
        .all()
    )
    intentos = (
        (
            await db_session.execute(
                select(IntentoEmisionFiscal).order_by(
                    IntentoEmisionFiscal.numero_planificado
                )
            )
        )
        .scalars()
        .all()
    )
    guardas = (
        (await db_session.execute(select(PuntoVentaGuardaEmisionRece))).scalars().all()
    )
    operacion = await db_session.get(
        OperacionIdempotente,
        operacion_id,
        populate_existing=True,
    )

    assert FakeWSFEClient.llamadas_fecae == 1
    assert fallos_cierre == 1
    assert [resultado.exito for resultado in resultados] == [False, False]
    assert all(resultado.requiere_reconciliacion is True for resultado in resultados)
    assert [resultado.cae for resultado in resultados] == [
        "12345678901231",
        "12345678901232",
    ]
    assert {resultado.categoria_error for resultado in resultados} == {
        "post_arca_persistencia"
    }
    respuestas_json = " ".join(resultado.model_dump_json() for resultado in resultados)
    assert "secreto" not in respuestas_json
    assert "privada.key" not in respuestas_json
    assert comprobantes == []
    assert [intento.estado for intento in intentos] == [
        "requiere_reconciliacion",
        "requiere_reconciliacion",
    ]
    assert len(guardas) == 1
    assert guardas[0].fase == "requiere_reconciliacion"
    assert operacion is not None
    assert operacion.estado == "requiere_reconciliacion"


@pytest.mark.asyncio
async def test_emitir_comprobante_usa_siguiente_arca_si_historia_local_es_parcial(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """La historia externa no bloquea si el número ARCA sigue estable."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    db_session.add(
        Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=76,
            fecha_emision=date(2026, 7, 27),
            subtotal=Decimal("1000.00"),
            descuento=Decimal("0.00"),
            iva_21=Decimal("0.00"),
            iva_10_5=Decimal("0.00"),
            iva_27=Decimal("0.00"),
            otros_impuestos=Decimal("0.00"),
            total=Decimal("1000.00"),
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            estado="autorizado",
            moneda="PES",
            cotizacion=Decimal("1"),
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
        )
    )
    await db_session.commit()
    numeros_consultados: list[int] = []
    numeros_solicitados: list[int] = []

    class FakeWSFEClient:
        """Cliente WSFE simulado con ARCA adelantada."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Devuelve un último comprobante que no existe localmente."""
            numeros_consultados.append(punto_venta_numero)
            return 77

        async def fe_cae_solicitar(self, arca_request):
            """Autoriza el siguiente número confirmado por ARCA."""
            numeros_solicitados.append(arca_request.cbte_desde)
            return CAEResponse(
                cae="12345678901235",
                cae_vencimiento="20260806",
                numero_comprobante=arca_request.cbte_desde,
                tipo_cbte=arca_request.tipo_cbte,
                punto_venta=arca_request.punto_venta,
                resultado="A",
            )

    async def fake_validar_datos(self, request):
        return None

    async def fake_tomar_lock(self, *args, **kwargs):
        return None

    async def fake_obtener_empresa(self, empresa_id):
        return SimpleNamespace(id=empresa_id, cuit=test_empresa.cuit)

    async def fake_obtener_certificado_activo(self, empresa_id):
        return SimpleNamespace(
            archivo_crt="empresa-test.crt",
            archivo_key="empresa-test.key",
        )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_tomar_lock_numeracion", fake_tomar_lock)
    monkeypatch.setattr(FacturacionService, "_obtener_empresa", fake_obtener_empresa)
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        fake_obtener_certificado_activo,
    )
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 7, 27),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )

    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=False,
    )
    operacion_id = int(operacion.id)
    resultado = await service.emitir_comprobante(
        request,
        operacion_id=operacion_id,
        contexto_rece=contexto,
        contextos_operacion=[contexto],
    )

    assert resultado.exito is True
    assert resultado.requiere_reconciliacion is False
    assert resultado.numero == 78
    assert numeros_consultados == [1, 1]
    assert numeros_solicitados == [78]

    comprobantes = (
        (await db_session.execute(select(Comprobante).order_by(Comprobante.numero)))
        .scalars()
        .all()
    )
    assert [comprobante.numero for comprobante in comprobantes] == [76, 78]


@pytest.mark.asyncio
async def test_emitir_comprobante_aborta_si_arca_avanza_despues_de_reservar(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Un avance externo tras reservar debe abortar antes de solicitar CAE."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    db_session.add(
        Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=76,
            fecha_emision=date(2026, 7, 27),
            subtotal=Decimal("1000.00"),
            descuento=Decimal("0.00"),
            iva_21=Decimal("0.00"),
            iva_10_5=Decimal("0.00"),
            iva_27=Decimal("0.00"),
            otros_impuestos=Decimal("0.00"),
            total=Decimal("1000.00"),
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            estado="autorizado",
            moneda="PES",
            cotizacion=Decimal("1"),
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
        )
    )
    await db_session.commit()
    numeros_consultados: list[int] = []
    numeros_solicitados: list[int] = []
    ultimos_arca = iter([77, 78])

    class FakeWSFEClient:
        """Cliente WSFE simulado con ARCA adelantada."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Devuelve un último comprobante que no existe localmente."""
            numeros_consultados.append(punto_venta_numero)
            return next(ultimos_arca)

        async def fe_cae_solicitar(self, arca_request):
            """No debe invocarse si cambió el siguiente número de ARCA."""
            numeros_solicitados.append(arca_request.cbte_desde)
            raise AssertionError("No debe solicitar CAE con una reserva obsoleta")

    async def fake_validar_datos(self, request):
        return None

    async def fake_tomar_lock(self, *args, **kwargs):
        return None

    async def fake_obtener_empresa(self, empresa_id):
        return SimpleNamespace(id=empresa_id, cuit=test_empresa.cuit)

    async def fake_obtener_certificado_activo(self, empresa_id):
        return SimpleNamespace(
            archivo_crt="empresa-test.crt",
            archivo_key="empresa-test.key",
        )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_tomar_lock_numeracion", fake_tomar_lock)
    monkeypatch.setattr(FacturacionService, "_obtener_empresa", fake_obtener_empresa)
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        fake_obtener_certificado_activo,
    )
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 7, 27),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )

    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=False,
    )
    operacion_id = int(operacion.id)
    resultado = await service.emitir_comprobante(
        request,
        operacion_id=operacion_id,
        contexto_rece=contexto,
        contextos_operacion=[contexto],
    )

    assert resultado.exito is False
    assert resultado.requiere_reconciliacion is False
    assert resultado.categoria_error == "numeracion_arca_cambio_pre_arca"
    assert resultado.numero == 78
    assert numeros_consultados == [1, 1]
    assert numeros_solicitados == []

    intentos = (await db_session.execute(select(IntentoEmisionFiscal))).scalars().all()
    assert len(intentos) == 1
    assert intentos[0].numero_planificado == 78
    assert intentos[0].estado == "fallido_verificado"

    comprobantes = (
        (await db_session.execute(select(Comprobante).order_by(Comprobante.numero)))
        .scalars()
        .all()
    )
    assert [comprobante.numero for comprobante in comprobantes] == [76]


@pytest.mark.asyncio
async def test_emitir_comprobante_cierra_intento_si_falla_segundo_preflight(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Un error del segundo preflight es terminal porque FECAE no comenzó."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    db_session.add(
        Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=76,
            fecha_emision=date(2026, 7, 27),
            subtotal=Decimal("1000.00"),
            descuento=Decimal("0.00"),
            iva_21=Decimal("0.00"),
            iva_10_5=Decimal("0.00"),
            iva_27=Decimal("0.00"),
            otros_impuestos=Decimal("0.00"),
            total=Decimal("1000.00"),
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            estado="autorizado",
            moneda="PES",
            cotizacion=Decimal("1"),
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
        )
    )
    await db_session.commit()
    numeros_consultados: list[int] = []
    numeros_solicitados: list[int] = []

    class FakeWSFEClient:
        """Cliente WSFE simulado con ARCA adelantada."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Devuelve un último comprobante que no existe localmente."""
            numeros_consultados.append(punto_venta_numero)
            if len(numeros_consultados) == 2:
                raise ArcaServiceError("ARCA no disponible")
            return 77

        async def fe_cae_solicitar(self, arca_request):
            """No debe invocarse si cambió el siguiente número de ARCA."""
            numeros_solicitados.append(arca_request.cbte_desde)
            raise AssertionError("No debe solicitar CAE con una reserva obsoleta")

    async def fake_validar_datos(self, request):
        return None

    async def fake_tomar_lock(self, *args, **kwargs):
        return None

    async def fake_obtener_empresa(self, empresa_id):
        return SimpleNamespace(id=empresa_id, cuit=test_empresa.cuit)

    async def fake_obtener_certificado_activo(self, empresa_id):
        return SimpleNamespace(
            archivo_crt="empresa-test.crt",
            archivo_key="empresa-test.key",
        )

    async def fake_ticket(self, empresa, certificado):
        return SimpleNamespace(token="token", sign="sign")

    async def fake_validar_punto(self, wsfe_client, punto_venta_numero):
        return None

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_tomar_lock_numeracion", fake_tomar_lock)
    monkeypatch.setattr(FacturacionService, "_obtener_empresa", fake_obtener_empresa)
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        fake_obtener_certificado_activo,
    )
    monkeypatch.setattr(FacturacionService, "_obtener_ticket_acceso", fake_ticket)
    monkeypatch.setattr(
        FacturacionService,
        "_validar_punto_venta_habilitado",
        fake_validar_punto,
    )

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 7, 27),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        items=[
            ItemComprobanteCreate(
                descripcion="Producto",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )

    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=False,
    )
    operacion_id = int(operacion.id)
    resultado = await service.emitir_comprobante(
        request,
        operacion_id=operacion_id,
        contexto_rece=contexto,
        contextos_operacion=[contexto],
    )

    assert resultado.exito is False
    assert resultado.requiere_reconciliacion is False
    assert resultado.categoria_error == "preflight_arca_no_disponible"
    assert resultado.numero == 78
    assert numeros_consultados == [1, 1]
    assert numeros_solicitados == []

    intentos = (await db_session.execute(select(IntentoEmisionFiscal))).scalars().all()
    assert len(intentos) == 1
    assert intentos[0].numero_planificado == 78
    assert intentos[0].estado == "fallido_verificado"

    comprobantes = (
        (await db_session.execute(select(Comprobante).order_by(Comprobante.numero)))
        .scalars()
        .all()
    )
    assert [comprobante.numero for comprobante in comprobantes] == [76]


@pytest.mark.asyncio
async def test_diagnostico_bloquea_si_factuflow_esta_adelantado(
    db_session: AsyncSession,
    test_empresa,
):
    """Una numeración local posterior a ARCA no ofrece candidato de emisión."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    db_session.add(
        Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=2,
            fecha_emision=date(2026, 7, 27),
            subtotal=Decimal("1000.00"),
            descuento=Decimal("0.00"),
            iva_21=Decimal("0.00"),
            iva_10_5=Decimal("0.00"),
            iva_27=Decimal("0.00"),
            otros_impuestos=Decimal("0.00"),
            total=Decimal("1000.00"),
            cae="12345678901234",
            cae_vencimiento=date(2026, 8, 6),
            estado="autorizado",
            moneda="PES",
            cotizacion=Decimal("1"),
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
        )
    )
    await db_session.commit()

    class FakeWSFEClient:
        """Simula que ARCA no registra comprobantes para la clave fiscal."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Devuelve una numeración anterior a la historia local."""
            return 0

    service = FacturacionService(db_session)
    diagnostico = await service._obtener_diagnostico_numeracion(
        test_empresa.id,
        punto_venta.id,
        6,
        FakeWSFEClient(),
        punto_venta.numero,
    )

    assert diagnostico.estado == "local_adelantada"
    assert diagnostico.ultimo_local == 2
    assert diagnostico.ultimo_arca == 0
    assert diagnostico.proximo_numero is None
    assert diagnostico.emision_habilitada is False

    with pytest.raises(ValidationError, match="local está adelantada"):
        await service._obtener_proximo_numero(
            test_empresa.id,
            punto_venta.id,
            6,
            FakeWSFEClient(),
            punto_venta.numero,
        )


@pytest.mark.asyncio
async def test_intento_stale_consulta_arca_antes_de_liberar_numero(
    db_session: AsyncSession,
    test_empresa,
):
    """Un intento vencido solo libera numeración si ARCA confirma que no existe."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        punto_venta_numero=punto_venta.numero,
        tipo_comprobante=6,
        numero_planificado=1,
        fecha_emision=date(2026, 4, 30),
        total=Decimal("1000.00"),
        receptor_tipo_documento=99,
        receptor_numero_documento="0",
        receptor_razon_social="A CONSUMIDOR FINAL",
        payload_hash="payload-stale",
        huella_logica="huella-stale",
        estado="en_proceso",
        created_at=datetime.utcnow()
        - timedelta(minutes=settings.fiscal_attempt_stale_minutes + 1),
    )
    db_session.add(intento)
    await db_session.commit()

    class FakeWSFEClient:
        """Cliente WSFE que confirma ausencia del comprobante planificado."""

        def __init__(self) -> None:
            """Inicializa contador de consultas."""
            self.consultas: list[tuple[int, int, int]] = []

        async def fe_comp_consultar(self, punto_venta, tipo_cbte, numero):
            """Simula una respuesta explícita de comprobante inexistente."""
            self.consultas.append((punto_venta, tipo_cbte, numero))
            raise ArcaServiceError("Comprobante inexistente", codigo="10016")

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """ARCA no tiene comprobantes autorizados todavía."""
            return 0

    wsfe_client = FakeWSFEClient()
    service = FacturacionService(db_session)

    proximo = await service._obtener_proximo_numero(
        test_empresa.id,
        punto_venta.id,
        6,
        wsfe_client,
        punto_venta.numero,
    )

    await db_session.refresh(intento)
    assert proximo == 1
    assert wsfe_client.consultas == [(1, 6, 1)]
    assert intento.estado == "fallido_verificado"
    assert intento.categoria_error == "arca_no_registrado"


@pytest.mark.asyncio
async def test_intento_stale_legacy_admite_json_null_sin_snapshot_rece(
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """JSON null histórico no se confunde con ownership PF-19B moderno."""
    punto_venta = PuntoVenta(
        numero=91,
        nombre="Legacy JSON null",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    operacion = OperacionIdempotente(
        empresa_id=test_empresa.id,
        idempotency_key="idem-stale-legacy-json-null",
        tipo_operacion="emitir_comprobante",
        payload_hash="payload-stale-legacy-json-null",
        estado="en_proceso",
        response_json=JSON.NULL,
    )
    db_session.add(operacion)
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        operacion_id=operacion.id,
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        punto_venta_numero=punto_venta.numero,
        tipo_comprobante=6,
        numero_planificado=1,
        fecha_emision=date(2026, 8, 1),
        total=Decimal("1000.00"),
        receptor_tipo_documento=99,
        receptor_numero_documento="0",
        receptor_razon_social="A CONSUMIDOR FINAL",
        payload_hash="payload-intento-stale-legacy-json-null",
        huella_logica="huella-intento-stale-legacy-json-null",
        estado="en_proceso",
    )
    db_session.add(intento)
    await db_session.commit()

    class FakeWSFEClient:
        """Prueba por lectura segura que ARCA no conserva el comprobante."""

        llamadas = 0

        async def fe_comp_consultar(self, punto_venta, tipo_cbte, numero):
            """Devuelve ausencia explícita sin solicitar un CAE."""
            FakeWSFEClient.llamadas += 1
            raise ArcaServiceError("Comprobante inexistente", codigo="10016")

    resultado = await FacturacionService(db_session)._reconciliar_intento_stale(
        intento=intento,
        wsfe_client=FakeWSFEClient(),
        punto_venta_numero=punto_venta.numero,
    )

    await db_session.refresh(intento)
    assert resultado is None
    assert FakeWSFEClient.llamadas == 1
    assert intento.estado == "fallido_verificado"
    assert intento.categoria_error == "arca_no_registrado"


@pytest.mark.asyncio
async def test_intento_stale_legacy_se_bloquea_por_guarda_huerfana_operacion(
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """Una guarda de la operación bloquea stale aunque el intento no la referencie."""
    punto_venta = PuntoVenta(
        numero=92,
        nombre="Legacy con guarda huérfana",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=date(2026, 8, 1),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        items=[
            ItemComprobanteCreate(
                descripcion="Servicio sintético",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    operacion, contexto, _ = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto_venta,
        requests=[request],
        batch=False,
    )
    operacion.rece_snapshot_hash = None
    intento = IntentoEmisionFiscal(
        operacion_id=operacion.id,
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        punto_venta_numero=punto_venta.numero,
        tipo_comprobante=6,
        numero_planificado=1,
        fecha_emision=request.fecha_emision,
        total=Decimal("1000.00"),
        receptor_tipo_documento=99,
        receptor_numero_documento="0",
        receptor_razon_social="A CONSUMIDOR FINAL",
        payload_hash="payload-stale-guarda-huerfana",
        huella_logica="huella-stale-guarda-huerfana",
        estado="en_proceso",
    )
    guarda = PuntoVentaGuardaEmisionRece(
        token="b" * 64,
        fase="pre_arca",
        operacion_id=operacion.id,
        empresa_id=contexto.empresa_id,
        punto_venta_id=contexto.punto_venta_id,
        ambiente=contexto.ambiente,
        elegibilidad_revision_id=contexto.elegibilidad_revision_id,
        punto_venta_revision_fiscal=contexto.punto_venta_revision_fiscal,
    )
    db_session.add_all([intento, guarda])
    await db_session.commit()

    class FakeWSFEClient:
        """Explota si el stale cruza la guarda durable hacia ARCA."""

        llamadas_fecomp = 0
        llamadas_fecae = 0

        async def fe_comp_consultar(self, punto_venta, tipo_cbte, numero):
            """Registra una consulta FEComp indebida."""
            FakeWSFEClient.llamadas_fecomp += 1
            raise AssertionError(
                "No debe consultar ARCA con una guarda de la operación"
            )

        async def fe_cae_solicitar(self, arca_request):
            """Registra una solicitud FECAE indebida."""
            FakeWSFEClient.llamadas_fecae += 1
            raise AssertionError("No debe solicitar CAE desde reconciliación stale")

    resultado = await FacturacionService(db_session)._reconciliar_intento_stale(
        intento=intento,
        wsfe_client=FakeWSFEClient(),
        punto_venta_numero=punto_venta.numero,
    )

    await db_session.refresh(intento)
    await db_session.refresh(guarda)
    assert resultado is intento
    assert FakeWSFEClient.llamadas_fecomp == 0
    assert FakeWSFEClient.llamadas_fecae == 0
    assert intento.estado == "en_proceso"
    assert intento.guarda_rece_id is None
    assert guarda.fase == "pre_arca"


@pytest.mark.asyncio
async def test_intento_stale_moderno_no_sobrescribe_terminal_desde_orm_obsoleto(
    tmp_path,
) -> None:
    """Un ORM obsoleto no consulta ARCA ni pisa evidencia RECE terminal."""
    db_path = tmp_path / "rece-stale-terminal.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    event.listen(engine.sync_engine, "connect", _habilitar_foreign_keys_sqlite)
    SessionArchivo = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with SessionArchivo() as preparacion:
            empresa = Empresa(
                razon_social="Empresa stale RECE",
                cuit="20123456789",
                condicion_iva="Responsable Inscripto",
                domicilio="Domicilio sintético 123",
                localidad="Ciudad de prueba",
                provincia="Buenos Aires",
                codigo_postal="1000",
                inicio_actividades=date(2020, 1, 1),
            )
            preparacion.add(empresa)
            await preparacion.flush()
            usuario = Usuario(
                email="rece-stale@example.test",
                hashed_password="hash-sintetico",
                nombre="Usuario RECE stale",
                empresa_id=empresa.id,
            )
            punto = PuntoVenta(
                numero=93,
                nombre="Punto stale RECE",
                activo=True,
                es_webservice=True,
                empresa_id=empresa.id,
                revision_fiscal=1,
            )
            preparacion.add_all([usuario, punto])
            await preparacion.commit()
            assert usuario.id == 1

            request = EmitirComprobanteRequest(
                empresa_id=empresa.id,
                punto_venta_id=punto.id,
                tipo_comprobante=6,
                concepto=1,
                fecha_emision=date(2026, 8, 1),
                tipo_documento=99,
                numero_documento="0",
                razon_social="A CONSUMIDOR FINAL",
                condicion_iva="Consumidor Final",
                guardar_cliente=False,
                moneda="PES",
                cotizacion=Decimal("1"),
                items=[
                    ItemComprobanteCreate(
                        descripcion="Servicio stale RECE",
                        cantidad=Decimal("1"),
                        unidad="unidad",
                        precio_unitario=Decimal("1000"),
                        iva_porcentaje=Decimal("0"),
                    )
                ],
            )
            operacion, contexto, _ = await _crear_operacion_rece_sintetica(
                preparacion,
                empresa=empresa,
                punto_venta=punto,
                requests=[request],
                batch=False,
            )
            guarda = await ElegibilidadReceService(preparacion).crear_guarda_pre_arca(
                operacion_id=operacion.id,
                contexto=contexto,
                contextos_operacion=[contexto],
            )
            intento = await IdempotenciaFiscalService(
                preparacion
            ).crear_intento_emision(
                request=request,
                punto_venta=punto,
                numero_planificado=1,
                total=Decimal("1000"),
                operacion_id=operacion.id,
                usuario_id=usuario.id,
                lote_id=None,
                grupo_id=None,
                contexto_rece=contexto,
                guarda_rece_id=guarda.id,
                commit=False,
            )
            intento.created_at = datetime.utcnow() - timedelta(
                minutes=settings.fiscal_attempt_stale_minutes + 1
            )
            await preparacion.commit()
            intento_id = int(intento.id)
            guarda_id = int(guarda.id)

        async with SessionArchivo() as sesion_stale:
            intento_obsoleto = await sesion_stale.get(
                IntentoEmisionFiscal,
                intento_id,
            )
            assert intento_obsoleto is not None
            assert intento_obsoleto.estado == "en_proceso"
            await sesion_stale.commit()

            async with SessionArchivo() as terminalizador:
                intento_terminal = await terminalizador.get(
                    IntentoEmisionFiscal,
                    intento_id,
                )
                guarda_terminal = await terminalizador.get(
                    PuntoVentaGuardaEmisionRece,
                    guarda_id,
                )
                assert intento_terminal is not None
                assert guarda_terminal is not None
                ahora = datetime.utcnow()
                intento_terminal.estado = "rechazado_arca"
                intento_terminal.categoria_error = "arca_no_aprobado"
                intento_terminal.mensaje = "Rechazo terminal sintético."
                guarda_terminal.fase = "cerrada_terminal"
                guarda_terminal.arca_iniciada_en = ahora
                guarda_terminal.cerrada_en = ahora
                await terminalizador.commit()

            class FakeWSFEClient:
                """Explota si el ORM obsoleto cruza la frontera hacia ARCA."""

                llamadas_fecomp = 0
                llamadas_fecae = 0

                async def fe_comp_consultar(self, punto_venta, tipo_cbte, numero):
                    """Registra una consulta FEComp indebida."""
                    FakeWSFEClient.llamadas_fecomp += 1
                    raise AssertionError(
                        "No debe consultar ARCA con evidencia terminal"
                    )

                async def fe_cae_solicitar(self, arca_request):
                    """Registra una solicitud FECAE indebida."""
                    FakeWSFEClient.llamadas_fecae += 1
                    raise AssertionError("La reconciliación stale nunca solicita CAE")

            resultado = await FacturacionService(
                sesion_stale
            )._reconciliar_intento_stale(
                intento=intento_obsoleto,
                wsfe_client=FakeWSFEClient(),
                punto_venta_numero=93,
            )

            assert resultado is intento_obsoleto
            assert FakeWSFEClient.llamadas_fecomp == 0
            assert FakeWSFEClient.llamadas_fecae == 0

        async with SessionArchivo() as observador:
            intento_visible = await observador.get(IntentoEmisionFiscal, intento_id)
            guarda_visible = await observador.get(
                PuntoVentaGuardaEmisionRece,
                guarda_id,
            )
            assert intento_visible is not None
            assert guarda_visible is not None
            assert intento_visible.estado == "rechazado_arca"
            assert intento_visible.categoria_error == "arca_no_aprobado"
            assert intento_visible.mensaje == "Rechazo terminal sintético."
            assert guarda_visible.fase == "cerrada_terminal"
            assert guarda_visible.arca_iniciada_en is not None
            assert guarda_visible.cerrada_en is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_intento_stale_no_libera_numero_con_error_arca_ambiguo(
    db_session: AsyncSession,
    test_empresa,
):
    """Un error ARCA ambiguo no debe liberar una numeración incierta."""
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        punto_venta_numero=punto_venta.numero,
        tipo_comprobante=6,
        numero_planificado=1,
        fecha_emision=date.today(),
        total=Decimal("1000.00"),
        receptor_tipo_documento=99,
        receptor_numero_documento="0",
        receptor_razon_social="A CONSUMIDOR FINAL",
        payload_hash="payload-stale-ambiguo",
        huella_logica="huella-stale-ambiguo",
        estado="en_proceso",
        created_at=datetime.utcnow()
        - timedelta(minutes=settings.fiscal_attempt_stale_minutes + 1),
    )
    db_session.add(intento)
    await db_session.commit()

    class FakeWSFEClient:
        """Cliente WSFE con error no concluyente."""

        async def fe_comp_consultar(self, punto_venta, tipo_cbte, numero):
            """Simula un error que no prueba inexistencia fiscal."""
            raise ArcaServiceError("El token no existe o está vencido")

    service = FacturacionService(db_session)
    with pytest.raises(ValidationError, match="pendiente de reconciliación"):
        await service._obtener_proximo_numero(
            test_empresa.id,
            punto_venta.id,
            6,
            FakeWSFEClient(),
            punto_venta.numero,
        )

    await db_session.refresh(intento)
    assert intento.estado == "requiere_reconciliacion"
    assert intento.categoria_error == "arca_consulta_incierta"


@pytest.mark.asyncio
async def test_intento_stale_autorizado_preserva_cae_con_payload_no_canonico(
    db_session: AsyncSession,
    test_empresa,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Una autorización conocida no se pierde ni reconstruye con payload inválido."""
    fecha_fiscal = date(2026, 8, 5)
    cae_sintetico = "12345678901234"
    punto_venta = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    lote = LoteComprobante(
        nombre_archivo="lote-payload-no-canonico.xlsx",
        archivo_hash="a" * 64,
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([punto_venta, lote])
    await db_session.flush()
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=fecha_fiscal,
        confirmacion_fecha_fiscal=True,
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        items=[
            ItemComprobanteCreate(
                descripcion="Servicio",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("1000"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    payload = request.model_dump(mode="json")
    payload["instruccion_fiscal_desconocida"] = "valor-sintetico"
    grupo = LoteComprobanteGrupo(
        lote_id=lote.id,
        empresa_id=test_empresa.id,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=punto_venta.numero,
        cliente_documento="0",
        cliente_razon_social="A CONSUMIDOR FINAL",
        total_estimado=Decimal("1000.00"),
        payload_json=payload,
    )
    db_session.add(grupo)
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        punto_venta_numero=punto_venta.numero,
        tipo_comprobante=6,
        numero_planificado=1,
        fecha_emision=fecha_fiscal,
        total=Decimal("1000.00"),
        receptor_tipo_documento=99,
        receptor_numero_documento="0",
        receptor_razon_social="A CONSUMIDOR FINAL",
        payload_hash="payload-stale-autorizado-no-canonico",
        huella_logica="huella-stale-autorizado-no-canonico",
        estado="en_proceso",
        lote_id=lote.id,
        grupo_id=grupo.id,
    )
    db_session.add(intento)
    await db_session.commit()

    class FakeWSFEClient:
        """Cliente WSFE que confirma una autorización sintética."""

        async def fe_comp_consultar(self, punto_venta, tipo_cbte, numero):
            """Devuelve el comprobante planificado como autorizado."""
            return SimpleNamespace(
                resultado="A",
                cae=cae_sintetico,
                cae_vencimiento="20260819",
                cuit_emisor=test_empresa.cuit,
                tipo_cbte=tipo_cbte,
                punto_venta=punto_venta,
                numero=numero,
                fecha_cbte="20260805",
                imp_total="1000.00",
                tipo_doc=99,
                nro_doc="0",
            )

    service = FacturacionService(db_session)

    reconciliado = await service._reconciliar_intento_stale(
        intento=intento,
        wsfe_client=FakeWSFEClient(),
        punto_venta_numero=punto_venta.numero,
    )

    await db_session.refresh(intento)
    await db_session.refresh(grupo)
    assert reconciliado is intento
    assert intento.estado == "requiere_reconciliacion"
    assert intento.categoria_error == "arca_autorizado_sin_payload_local"
    assert intento.cae == cae_sintetico
    assert intento.cae_vencimiento == date(2026, 8, 19)
    assert intento.comprobante_id is None
    assert grupo.estado == "validado"
    assert grupo.numero_asignado is None
    assert grupo.cae is None
    assert grupo.comprobante_id is None
    assert "no cumple el contrato vigente" in caplog.text
    assert "valor-sintetico" not in caplog.text


@pytest.mark.asyncio
async def test_duplicado_logico_nota_usa_huella_autorizada_con_asociado(
    db_session: AsyncSession,
    test_empresa,
):
    """Una nota ya emitida con asociado debe detectarse antes de llamar a ARCA."""
    punto_venta = PuntoVenta(
        numero=13,
        nombre="Notas C",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    fecha_emision = date(2026, 6, 1)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        tipo_comprobante=13,
        concepto=2,
        fecha_emision=fecha_emision,
        fecha_servicio_desde=fecha_emision,
        fecha_servicio_hasta=fecha_emision,
        fecha_vto_pago=date(2026, 6, 10),
        tipo_documento=99,
        numero_documento="0",
        razon_social="A CONSUMIDOR FINAL",
        condicion_iva="Consumidor Final",
        guardar_cliente=False,
        moneda="PES",
        cotizacion=Decimal("1"),
        comprobantes_asociados=[
            ComprobanteAsociadoCreate(
                tipo_comprobante=11,
                punto_venta=13,
                numero=1645,
                fecha=date(2026, 4, 30),
                cuit=test_empresa.cuit,
            )
        ],
        items=[
            ItemComprobanteCreate(
                descripcion="Anulación por duplicado",
                cantidad=Decimal("1"),
                unidad="unidad",
                precio_unitario=Decimal("59500"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )
    total = Decimal("59500.00")
    huella = IdempotenciaFiscalService.calcular_huella_logica(
        request=request,
        punto_venta_numero=punto_venta.numero,
        total=total,
    )
    comprobante = Comprobante(
        tipo_comprobante=request.tipo_comprobante,
        concepto=request.concepto,
        numero=27,
        fecha_emision=request.fecha_emision,
        fecha_servicio_desde=request.fecha_servicio_desde,
        fecha_servicio_hasta=request.fecha_servicio_hasta,
        fecha_vto_pago=request.fecha_vto_pago,
        fecha_vencimiento=request.fecha_vto_pago,
        subtotal=total,
        descuento=Decimal("0.00"),
        iva_21=Decimal("0.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=total,
        cae="12345678901234",
        cae_vencimiento=date(2026, 6, 11),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva="CF",
    )
    db_session.add(comprobante)
    await db_session.flush()
    db_session.add(
        ComprobanteItem(
            descripcion="Anulación por duplicado",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("59500"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("0"),
            subtotal=total,
            orden=0,
            comprobante_id=comprobante.id,
        )
    )
    db_session.add(
        IntentoEmisionFiscal(
            empresa_id=test_empresa.id,
            usuario_id=None,
            punto_venta_id=punto_venta.id,
            punto_venta_numero=punto_venta.numero,
            tipo_comprobante=request.tipo_comprobante,
            numero_planificado=comprobante.numero,
            fecha_emision=request.fecha_emision,
            total=total,
            receptor_tipo_documento=request.tipo_documento,
            receptor_numero_documento=request.numero_documento,
            receptor_razon_social=request.razon_social,
            payload_hash="payload-nota-asociada",
            huella_logica=huella,
            estado="autorizado",
            cae=comprobante.cae,
            cae_vencimiento=comprobante.cae_vencimiento,
            comprobante_id=comprobante.id,
        )
    )
    await db_session.commit()

    duplicado = await IdempotenciaFiscalService(db_session).buscar_duplicado_logico(
        request=request,
        punto_venta=punto_venta,
        total=total,
    )

    assert duplicado is not None
    assert duplicado.id == comprobante.id


@pytest.mark.asyncio
async def test_confirmacion_duplicado_toma_operacion_solo_una_vez(
    db_session: AsyncSession,
    test_empresa,
):
    """Solo un retry confirmado puede continuar una operación pausada."""
    operacion = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=None,
        idempotency_key="idem-duplicado-cas",
        tipo_operacion="emitir_comprobante",
        payload_hash="payload-duplicado-cas",
        estado="requiere_confirmacion_duplicado",
        response_json={
            "mensaje": "Duplicado probable",
            "categoria_error": "duplicado_logico",
        },
    )
    db_session.add(operacion)
    await db_session.commit()
    await db_session.refresh(operacion)

    service = IdempotenciaFiscalService(db_session)
    operacion, tomada = await service.marcar_operacion_en_proceso(operacion)
    assert tomada is True
    assert operacion.estado == "en_proceso"
    assert operacion.response_json is None
    assert (
        await db_session.scalar(
            select(OperacionIdempotente.id).where(
                OperacionIdempotente.id == operacion.id,
                OperacionIdempotente.response_json.is_(None),
            )
        )
        == operacion.id
    )

    operacion, tomada = await service.marcar_operacion_en_proceso(operacion)
    assert tomada is False
    assert operacion.estado == "en_proceso"
    assert operacion.response_json is None


@pytest.mark.asyncio
async def test_operacion_interrumpida_pre_arca_se_reclama_por_cas_una_sola_vez(
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """Solo un replay puede reclamar una interrupción demostrablemente pre-ARCA."""
    operacion = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=None,
        idempotency_key="idem-interrumpida-pre-arca-cas",
        tipo_operacion="emitir_comprobante",
        payload_hash="payload-interrumpida-pre-arca-cas",
        estado="en_proceso",
    )
    db_session.add(operacion)
    await db_session.commit()
    await db_session.refresh(operacion)

    service = IdempotenciaFiscalService(db_session)
    interrumpida = await service.marcar_operacion_interrumpida_pre_arca(operacion.id)
    await db_session.refresh(operacion)

    assert interrumpida is True
    assert operacion.estado == "interrumpida_pre_arca"
    assert operacion.response_json is None

    operacion, primer_claim = await service.reclamar_operacion_interrumpida_pre_arca(
        operacion
    )
    operacion, segundo_claim = await service.reclamar_operacion_interrumpida_pre_arca(
        operacion
    )

    assert primer_claim is True
    assert segundo_claim is False
    assert operacion.estado == "en_proceso"
    assert operacion.response_json is None


@pytest.mark.asyncio
async def test_operacion_pre_arca_no_se_interrumpe_con_respuesta_estado_o_intento(
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """La liberación exige estado activo, respuesta nula y cero intentos propios."""
    punto_venta = PuntoVenta(
        numero=987,
        nombre="PV intento pre-ARCA",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.flush()
    con_respuesta = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=None,
        idempotency_key="idem-pre-arca-con-respuesta",
        tipo_operacion="emitir_comprobante",
        payload_hash="payload-pre-arca-con-respuesta",
        estado="en_proceso",
        response_json={"mensaje": "respuesta durable"},
    )
    estado_invalido = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=None,
        idempotency_key="idem-pre-arca-finalizada",
        tipo_operacion="emitir_comprobante",
        payload_hash="payload-pre-arca-finalizada",
        estado="finalizado",
    )
    con_intento = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=None,
        idempotency_key="idem-pre-arca-con-intento",
        tipo_operacion="emitir_comprobante",
        payload_hash="payload-pre-arca-con-intento",
        estado="en_proceso",
    )
    db_session.add_all([con_respuesta, estado_invalido, con_intento])
    await db_session.flush()
    db_session.add(
        IntentoEmisionFiscal(
            operacion_id=con_intento.id,
            empresa_id=test_empresa.id,
            usuario_id=None,
            punto_venta_id=punto_venta.id,
            punto_venta_numero=punto_venta.numero,
            tipo_comprobante=6,
            numero_planificado=1,
            fecha_emision=date(2026, 7, 11),
            total=Decimal("1000.00"),
            receptor_tipo_documento=99,
            receptor_numero_documento="0",
            receptor_razon_social="A CONSUMIDOR FINAL",
            payload_hash="payload-intento-pre-arca",
            huella_logica="huella-intento-pre-arca",
            estado="en_proceso",
        )
    )
    await db_session.commit()

    service = IdempotenciaFiscalService(db_session)
    resultados = [
        await service.marcar_operacion_interrumpida_pre_arca(operacion.id)
        for operacion in (con_respuesta, estado_invalido, con_intento)
    ]
    ids = [con_respuesta.id, estado_invalido.id, con_intento.id]
    db_session.expire_all()

    assert resultados == [False, False, False]
    estados = [
        (await db_session.get(OperacionIdempotente, operacion_id)).estado
        for operacion_id in ids
    ]
    assert estados == ["en_proceso", "finalizado", "en_proceso"]


@pytest.mark.asyncio
async def test_operacion_incompleta_sin_intentos_no_continua_si_no_esta_stale(
    db_session: AsyncSession,
    test_empresa,
):
    """Un replay temprano sin intento fiscal no debe entrar de nuevo a ARCA."""
    operacion = OperacionIdempotente(
        empresa_id=test_empresa.id,
        usuario_id=None,
        idempotency_key="idem-sin-intento",
        tipo_operacion="emitir_comprobante",
        payload_hash="payload-sin-intento",
        estado="en_proceso",
        response_json=None,
    )
    db_session.add(operacion)
    await db_session.commit()
    await db_session.refresh(operacion)

    service = FacturacionService(db_session)
    respuesta = await service.resolver_operacion_idempotente_incompleta(operacion.id)

    assert respuesta is not None
    assert respuesta.exito is False
    assert respuesta.categoria_error == "idempotencia_en_proceso"
