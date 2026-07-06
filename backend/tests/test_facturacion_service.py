"""Tests del servicio de facturación."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.arca.exceptions import ArcaServiceError
from app.arca.models import CAEResponse
from app.core.config import settings
from app.models.certificado import Certificado
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import (
    ComprobanteAsociadoCreate,
    EmitirComprobanteRequest,
    ItemComprobanteCreate,
)
from app.services.facturacion_service import FacturacionService, ValidationError
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService


class FakeWSFEClient:
    """Cliente WSFE mínimo para probar validaciones internas."""

    def __init__(self, puntos: list[SimpleNamespace]) -> None:
        """Inicializa el cliente con puntos de venta simulados."""
        self._puntos = puntos

    async def fe_param_get_ptos_venta(self) -> list[SimpleNamespace]:
        """Devuelve puntos de venta simulados como lo haría ARCA."""
        return self._puntos


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
async def test_emitir_comprobante_post_arca_requiere_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Si falla la persistencia posterior a CAE, la respuesta no es reintentable."""

    class FakeWSFEClient:
        """Cliente WSFE simulado con CAE autorizado."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_cae_solicitar(self, _arca_request):
            """Devuelve un CAE autorizado simulado."""
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

    async def fake_obtener_punto_venta(self, punto_venta_id, empresa_id=None):
        return SimpleNamespace(id=punto_venta_id, numero=1)

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
        raise RuntimeError("base no disponible")

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_tomar_lock_numeracion", fake_tomar_lock)
    monkeypatch.setattr(FacturacionService, "_obtener_empresa", fake_obtener_empresa)
    monkeypatch.setattr(
        FacturacionService, "_obtener_punto_venta", fake_obtener_punto_venta
    )
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

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
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

    resultado = await service.emitir_comprobante(request)

    assert resultado.exito is False
    assert resultado.requiere_reconciliacion is True
    assert resultado.categoria_error == "post_arca_persistencia"
    assert resultado.cae == "12345678901234"
    assert resultado.numero == 77
    assert resultado.punto_venta == 1
    assert resultado.total == Decimal("1000.00")


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

    service = FacturacionService(db_session)
    resultado = await service.emitir_comprobante(request, commit=False)

    assert resultado.exito is True

    await db_session.rollback()

    comprobantes = (await db_session.execute(select(Comprobante))).scalars().all()
    intentos = (await db_session.execute(select(IntentoEmisionFiscal))).scalars().all()

    assert comprobantes == []
    assert len(intentos) == 1
    assert intentos[0].estado == "en_proceso"
    assert intentos[0].comprobante_id is None


@pytest.mark.asyncio
async def test_emitir_comprobante_no_persiste_respuesta_arca_no_aprobada(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Una respuesta WSFE no aprobada no debe persistirse como autorizada."""

    class FakeWSFEClient:
        """Cliente WSFE simulado con resultado parcial sin CAE."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_cae_solicitar(self, _arca_request):
            """Devuelve una respuesta no aprobada."""
            return CAEResponse(
                cae=None,
                cae_vencimiento=None,
                numero_comprobante=77,
                tipo_cbte=6,
                punto_venta=1,
                resultado="P",
            )

    async def fake_validar_datos(self, request):
        return None

    async def fake_tomar_lock(self, *args, **kwargs):
        return None

    async def fake_obtener_empresa(self, empresa_id):
        return SimpleNamespace(id=empresa_id, cuit=test_empresa.cuit)

    async def fake_obtener_punto_venta(self, punto_venta_id, empresa_id=None):
        return SimpleNamespace(id=punto_venta_id, numero=1)

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

    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", FakeWSFEClient)
    monkeypatch.setattr(FacturacionService, "_validar_datos", fake_validar_datos)
    monkeypatch.setattr(FacturacionService, "_tomar_lock_numeracion", fake_tomar_lock)
    monkeypatch.setattr(FacturacionService, "_obtener_empresa", fake_obtener_empresa)
    monkeypatch.setattr(
        FacturacionService, "_obtener_punto_venta", fake_obtener_punto_venta
    )
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

    service = FacturacionService(db_session)
    request = EmitirComprobanteRequest(
        empresa_id=test_empresa.id,
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

    resultado = await service.emitir_comprobante(request)
    comprobantes = (await db_session.execute(select(Comprobante))).scalars().all()

    assert resultado.exito is False
    assert resultado.requiere_reconciliacion is False
    assert resultado.categoria_error == "arca_no_aprobado"
    assert resultado.cae is None
    assert comprobantes == []


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

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Simula que ARCA no tiene comprobantes previos."""
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
            fecha_emision=date.today(),
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
    resultados = await service.emitir_comprobantes_lote(
        [request_cliente("Cliente Uno"), request_cliente("Cliente Dos")],
        max_registros=2,
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
    assert [request.cbte_desde for request in FakeWSFEClient.arca_requests[0]] == [
        1,
        2,
    ]
    assert [comprobante.numero for comprobante in comprobantes] == [1, 2]


@pytest.mark.asyncio
async def test_emitir_comprobantes_lote_cierra_intentos_si_falla_reserva_pre_arca(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Si falla una reserva local pre-ARCA, no deja intentos en proceso."""
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
        raise RuntimeError("reserva local fallida")

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
    resultados = await service.emitir_comprobantes_lote(
        [request_cliente("Cliente Uno"), request_cliente("Cliente Dos")],
        max_registros=2,
    )
    intentos = (await db_session.execute(select(IntentoEmisionFiscal))).scalars().all()

    assert FakeWSFEClient.llamadas_lote == 0
    assert llamadas_reserva == 2
    assert [resultado.exito for resultado in resultados] == [False, False]
    assert [resultado.numero for resultado in resultados] == [1, 2]
    assert all(resultado.requiere_reconciliacion is False for resultado in resultados)
    assert {resultado.categoria_error for resultado in resultados} == {
        "pre_arca_reserva_fallida"
    }
    assert len(intentos) == 1
    assert intentos[0].estado == "fallido_verificado"
    assert intentos[0].numero_planificado == 1
    assert intentos[0].categoria_error == "pre_arca_reserva_fallida"
    assert "no llegó a enviar" in intentos[0].mensaje


@pytest.mark.asyncio
async def test_emitir_comprobante_requiere_reconciliacion_si_arca_esta_adelantada(
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Si ARCA tiene números ausentes localmente, no debe pedir otro CAE."""
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
            fecha_emision=date.today(),
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
    cae_solicitado = False

    class FakeWSFEClient:
        """Cliente WSFE simulado con ARCA adelantada."""

        def __init__(self, *args, **kwargs) -> None:
            """Acepta la firma del cliente real sin usar red."""

        async def fe_comp_ultimo_autorizado(self, punto_venta_numero, tipo):
            """Devuelve un último comprobante que no existe localmente."""
            return 77

        async def fe_cae_solicitar(self, _arca_request):
            """No debe llamarse cuando falta reconciliar numeración."""
            nonlocal cae_solicitado
            cae_solicitado = True
            raise AssertionError("No debe solicitar CAE con numeración desfasada")

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

    resultado = await service.emitir_comprobante(request)

    assert resultado.exito is False
    assert resultado.requiere_reconciliacion is True
    assert resultado.categoria_error == "numeracion_arca_adelantada"
    assert resultado.numero == 77
    assert cae_solicitado is False


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

    operacion, tomada = await service.marcar_operacion_en_proceso(operacion)
    assert tomada is False
    assert operacion.estado == "en_proceso"
    assert operacion.response_json is None


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
