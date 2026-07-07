"""Tests para el servicio de reportes."""

import pytest
from datetime import date
from decimal import Decimal

from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.punto_venta import PuntoVenta
from app.services.reportes_service import ReportesService


@pytest.fixture
def reportes_service():
    """Fixture para el servicio de reportes."""
    return ReportesService()


class TestReportesService:
    """Tests para ReportesService."""

    def test_get_letra_comprobante_a(self, reportes_service):
        """Debe retornar 'A' para comprobantes tipo A."""
        assert reportes_service._get_letra_comprobante(1) == "A"
        assert reportes_service._get_letra_comprobante(2) == "A"
        assert reportes_service._get_letra_comprobante(3) == "A"

    def test_get_letra_comprobante_b(self, reportes_service):
        """Debe retornar 'B' para comprobantes tipo B."""
        assert reportes_service._get_letra_comprobante(6) == "B"
        assert reportes_service._get_letra_comprobante(7) == "B"
        assert reportes_service._get_letra_comprobante(8) == "B"

    def test_get_letra_comprobante_c(self, reportes_service):
        """Debe retornar 'C' para comprobantes tipo C."""
        assert reportes_service._get_letra_comprobante(11) == "C"
        assert reportes_service._get_letra_comprobante(12) == "C"
        assert reportes_service._get_letra_comprobante(13) == "C"

    def test_get_nombre_tipo_comprobante(self, reportes_service):
        """Debe retornar el nombre correcto del tipo de comprobante."""
        assert reportes_service._get_nombre_tipo_comprobante(1) == "Factura A"
        assert reportes_service._get_nombre_tipo_comprobante(2) == "Nota Débito A"
        assert reportes_service._get_nombre_tipo_comprobante(3) == "Nota Crédito A"
        assert reportes_service._get_nombre_tipo_comprobante(6) == "Factura B"
        assert reportes_service._get_nombre_tipo_comprobante(7) == "Nota Débito B"
        assert reportes_service._get_nombre_tipo_comprobante(8) == "Nota Crédito B"

    def test_get_nombre_mes(self, reportes_service):
        """Debe retornar el nombre correcto del mes."""
        assert reportes_service._get_nombre_mes(1) == "Enero"
        assert reportes_service._get_nombre_mes(6) == "Junio"
        assert reportes_service._get_nombre_mes(12) == "Diciembre"

    @pytest.mark.asyncio
    async def test_obtener_comprobantes_por_periodo_empty(
        self, reportes_service, db_session
    ):
        """Debe retornar una lista vacía cuando no hay comprobantes."""
        desde = date(2026, 1, 1)
        hasta = date(2026, 1, 31)

        comprobantes = await reportes_service.obtener_comprobantes_por_periodo(
            db_session, empresa_id=999, desde=desde, hasta=hasta
        )

        assert isinstance(comprobantes, list)
        assert len(comprobantes) == 0

    @pytest.mark.asyncio
    async def test_generar_reporte_ventas_empty(self, reportes_service, db_session):
        """Debe retornar un reporte vacío cuando no hay comprobantes."""
        desde = date(2026, 1, 1)
        hasta = date(2026, 1, 31)

        reporte = await reportes_service.generar_reporte_ventas(
            db_session, empresa_id=999, desde=desde, hasta=hasta
        )

        assert "comprobantes" in reporte
        assert "resumen" in reporte
        assert len(reporte["comprobantes"]) == 0
        assert reporte["resumen"]["total_neto"] == 0.0
        assert reporte["resumen"]["cantidad_comprobantes"] == 0

    @pytest.mark.asyncio
    async def test_generar_reporte_iva_empty(self, reportes_service, db_session):
        """Debe retornar un reporte de IVA vacío cuando no hay comprobantes."""
        reporte = await reportes_service.generar_reporte_iva(
            db_session, empresa_id=999, periodo_mes=1, periodo_anio=2026
        )

        assert "comprobantes" in reporte
        assert "resumen" in reporte
        assert len(reporte["comprobantes"]) == 0
        assert reporte["resumen"]["total_iva"] == 0.0
        assert reporte["resumen"]["periodo"]["mes"] == 1
        assert reporte["resumen"]["periodo"]["anio"] == 2026
        assert reporte["resumen"]["periodo"]["nombre"] == "Enero"

    @pytest.mark.asyncio
    async def test_generar_reporte_iva_resta_notas_credito(
        self, reportes_service, db_session, test_empresa
    ):
        """El subdiario IVA debe restar notas de crédito autorizadas."""
        punto_venta = PuntoVenta(
            numero=1,
            nombre="Principal",
            activo=True,
            es_webservice=True,
            empresa_id=test_empresa.id,
        )
        db_session.add(punto_venta)
        await db_session.flush()
        db_session.add_all(
            [
                Comprobante(
                    tipo_comprobante=6,
                    concepto=1,
                    numero=1,
                    fecha_emision=date(2026, 5, 10),
                    subtotal=Decimal("1000.00"),
                    descuento=Decimal("0.00"),
                    iva_21=Decimal("210.00"),
                    iva_10_5=Decimal("0.00"),
                    iva_27=Decimal("0.00"),
                    otros_impuestos=Decimal("0.00"),
                    total=Decimal("1210.00"),
                    cae="12345678901234",
                    cae_vencimiento=date(2026, 5, 20),
                    estado="autorizado",
                    moneda="PES",
                    cotizacion=Decimal("1"),
                    empresa_id=test_empresa.id,
                    punto_venta_id=punto_venta.id,
                    receptor_tipo_documento=80,
                    receptor_numero_documento="20409378472",
                    receptor_razon_social="Cliente IVA SA",
                    receptor_condicion_iva="RI",
                ),
                Comprobante(
                    tipo_comprobante=8,
                    concepto=1,
                    numero=2,
                    fecha_emision=date(2026, 5, 11),
                    subtotal=Decimal("200.00"),
                    descuento=Decimal("0.00"),
                    iva_21=Decimal("42.00"),
                    iva_10_5=Decimal("0.00"),
                    iva_27=Decimal("0.00"),
                    otros_impuestos=Decimal("0.00"),
                    total=Decimal("242.00"),
                    cae="12345678901235",
                    cae_vencimiento=date(2026, 5, 20),
                    estado="autorizado",
                    moneda="PES",
                    cotizacion=Decimal("1"),
                    empresa_id=test_empresa.id,
                    punto_venta_id=punto_venta.id,
                    receptor_tipo_documento=80,
                    receptor_numero_documento="20409378472",
                    receptor_razon_social="Cliente IVA SA",
                    receptor_condicion_iva="RI",
                ),
            ]
        )
        await db_session.commit()

        reporte = await reportes_service.generar_reporte_iva(
            db_session,
            empresa_id=test_empresa.id,
            periodo_mes=5,
            periodo_anio=2026,
        )

        assert reporte["resumen"]["gravado_21"] == 800.0
        assert reporte["resumen"]["iva_21"] == 168.0
        assert reporte["resumen"]["total_iva"] == 168.0
        assert reporte["comprobantes"][1]["gravado_21"] == -200.0
        assert reporte["comprobantes"][1]["iva_21"] == -42.0

    @pytest.mark.asyncio
    async def test_generar_reporte_iva_incluye_tipo_c_sin_iva_como_exento(
        self, reportes_service, db_session, test_empresa
    ):
        """El subdiario IVA debe sumar comprobantes C con IVA cero como exentos."""
        punto_venta = PuntoVenta(
            numero=2,
            nombre="Punto C",
            activo=True,
            es_webservice=True,
            empresa_id=test_empresa.id,
        )
        db_session.add(punto_venta)
        await db_session.flush()
        db_session.add_all(
            [
                Comprobante(
                    tipo_comprobante=11,
                    concepto=1,
                    numero=10,
                    fecha_emision=date(2026, 5, 12),
                    subtotal=Decimal("1500.00"),
                    descuento=Decimal("0.00"),
                    iva_21=Decimal("0.00"),
                    iva_10_5=Decimal("0.00"),
                    iva_27=Decimal("0.00"),
                    otros_impuestos=Decimal("0.00"),
                    total=Decimal("1500.00"),
                    cae="22345678901234",
                    cae_vencimiento=date(2026, 5, 22),
                    estado="autorizado",
                    moneda="PES",
                    cotizacion=Decimal("1"),
                    empresa_id=test_empresa.id,
                    punto_venta_id=punto_venta.id,
                    receptor_tipo_documento=99,
                    receptor_numero_documento="0",
                    receptor_razon_social="A CONSUMIDOR FINAL",
                    receptor_condicion_iva="CF",
                ),
                Comprobante(
                    tipo_comprobante=13,
                    concepto=1,
                    numero=11,
                    fecha_emision=date(2026, 5, 13),
                    subtotal=Decimal("200.00"),
                    descuento=Decimal("0.00"),
                    iva_21=Decimal("0.00"),
                    iva_10_5=Decimal("0.00"),
                    iva_27=Decimal("0.00"),
                    otros_impuestos=Decimal("0.00"),
                    total=Decimal("200.00"),
                    cae="22345678901235",
                    cae_vencimiento=date(2026, 5, 22),
                    estado="autorizado",
                    moneda="PES",
                    cotizacion=Decimal("1"),
                    empresa_id=test_empresa.id,
                    punto_venta_id=punto_venta.id,
                    receptor_tipo_documento=99,
                    receptor_numero_documento="0",
                    receptor_razon_social="A CONSUMIDOR FINAL",
                    receptor_condicion_iva="CF",
                ),
            ]
        )
        await db_session.commit()

        reporte = await reportes_service.generar_reporte_iva(
            db_session,
            empresa_id=test_empresa.id,
            periodo_mes=5,
            periodo_anio=2026,
        )

        assert reporte["resumen"]["exento"] == 1300.0
        assert reporte["resumen"]["no_gravado"] == 0.0
        assert reporte["resumen"]["total_neto"] == 1300.0
        assert reporte["resumen"]["total_iva"] == 0.0
        assert reporte["comprobantes"][0]["tipo_letra"] == "C"
        assert reporte["comprobantes"][0]["tipo_nombre"] == "FC"
        assert reporte["comprobantes"][0]["exento"] == 1500.0
        assert reporte["comprobantes"][0]["no_gravado"] == 0.0
        assert reporte["comprobantes"][0]["total"] == 1500.0
        assert reporte["comprobantes"][1]["tipo_nombre"] == "NC"
        assert reporte["comprobantes"][1]["exento"] == -200.0
        assert reporte["comprobantes"][1]["total"] == -200.0

    @pytest.mark.asyncio
    async def test_generar_reporte_iva_incluye_items_iva_cero_no_gravados(
        self, reportes_service, db_session, test_empresa
    ):
        """El subdiario IVA debe incluir ítems A/B con IVA cero como no gravados."""
        punto_venta = PuntoVenta(
            numero=3,
            nombre="Punto B",
            activo=True,
            es_webservice=True,
            empresa_id=test_empresa.id,
        )
        db_session.add(punto_venta)
        await db_session.flush()
        factura = Comprobante(
            tipo_comprobante=6,
            concepto=1,
            numero=20,
            fecha_emision=date(2026, 5, 14),
            subtotal=Decimal("1000.00"),
            descuento=Decimal("0.00"),
            iva_21=Decimal("0.00"),
            iva_10_5=Decimal("0.00"),
            iva_27=Decimal("0.00"),
            otros_impuestos=Decimal("0.00"),
            total=Decimal("1000.00"),
            cae="32345678901234",
            cae_vencimiento=date(2026, 5, 24),
            estado="autorizado",
            moneda="PES",
            cotizacion=Decimal("1"),
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            receptor_tipo_documento=80,
            receptor_numero_documento="20409378472",
            receptor_razon_social="Cliente No Gravado SA",
            receptor_condicion_iva="RI",
        )
        nota_credito = Comprobante(
            tipo_comprobante=8,
            concepto=1,
            numero=21,
            fecha_emision=date(2026, 5, 15),
            subtotal=Decimal("200.00"),
            descuento=Decimal("0.00"),
            iva_21=Decimal("0.00"),
            iva_10_5=Decimal("0.00"),
            iva_27=Decimal("0.00"),
            otros_impuestos=Decimal("0.00"),
            total=Decimal("200.00"),
            cae="32345678901235",
            cae_vencimiento=date(2026, 5, 24),
            estado="autorizado",
            moneda="PES",
            cotizacion=Decimal("1"),
            empresa_id=test_empresa.id,
            punto_venta_id=punto_venta.id,
            receptor_tipo_documento=80,
            receptor_numero_documento="20409378472",
            receptor_razon_social="Cliente No Gravado SA",
            receptor_condicion_iva="RI",
        )
        db_session.add_all([factura, nota_credito])
        await db_session.flush()
        db_session.add_all(
            [
                ComprobanteItem(
                    descripcion="Operación sin IVA",
                    cantidad=Decimal("1.0000"),
                    unidad="unidad",
                    precio_unitario=Decimal("1000.0000"),
                    descuento_porcentaje=Decimal("0.00"),
                    iva_porcentaje=Decimal("0.00"),
                    subtotal=Decimal("1000.00"),
                    orden=1,
                    comprobante_id=factura.id,
                ),
                ComprobanteItem(
                    descripcion="Anulación sin IVA",
                    cantidad=Decimal("1.0000"),
                    unidad="unidad",
                    precio_unitario=Decimal("200.0000"),
                    descuento_porcentaje=Decimal("0.00"),
                    iva_porcentaje=Decimal("0.00"),
                    subtotal=Decimal("200.00"),
                    orden=1,
                    comprobante_id=nota_credito.id,
                ),
            ]
        )
        await db_session.commit()

        reporte = await reportes_service.generar_reporte_iva(
            db_session,
            empresa_id=test_empresa.id,
            periodo_mes=5,
            periodo_anio=2026,
        )

        assert reporte["resumen"]["no_gravado"] == 800.0
        assert reporte["resumen"]["exento"] == 0.0
        assert reporte["resumen"]["total_neto"] == 800.0
        assert reporte["resumen"]["total_iva"] == 0.0
        assert reporte["comprobantes"][0]["tipo_letra"] == "B"
        assert reporte["comprobantes"][0]["tipo_nombre"] == "FB"
        assert reporte["comprobantes"][0]["no_gravado"] == 1000.0
        assert reporte["comprobantes"][0]["exento"] == 0.0
        assert reporte["comprobantes"][1]["tipo_nombre"] == "NC"
        assert reporte["comprobantes"][1]["no_gravado"] == -200.0
        assert reporte["comprobantes"][1]["total"] == -200.0

    @pytest.mark.asyncio
    async def test_obtener_ranking_clientes_empty(self, reportes_service, db_session):
        """Debe retornar una lista vacía cuando no hay comprobantes."""
        desde = date(2026, 1, 1)
        hasta = date(2026, 1, 31)

        ranking = await reportes_service.obtener_ranking_clientes(
            db_session, empresa_id=999, desde=desde, hasta=hasta, limite=10
        )

        assert isinstance(ranking, list)
        assert len(ranking) == 0
