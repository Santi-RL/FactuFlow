"""Tests para el servicio de reportes."""

import pytest
from datetime import date
from decimal import Decimal

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
    async def test_obtener_ranking_clientes_empty(self, reportes_service, db_session):
        """Debe retornar una lista vacía cuando no hay comprobantes."""
        desde = date(2026, 1, 1)
        hasta = date(2026, 1, 31)

        ranking = await reportes_service.obtener_ranking_clientes(
            db_session, empresa_id=999, desde=desde, hasta=hasta, limite=10
        )

        assert isinstance(ranking, list)
        assert len(ranking) == 0
