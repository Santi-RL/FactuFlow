"""Tests del servicio de facturación."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import (
    ComprobanteAsociadoCreate,
    EmitirComprobanteRequest,
    ItemComprobanteCreate,
)
from app.services.facturacion_service import FacturacionService, ValidationError


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
