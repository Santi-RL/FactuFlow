"""Tests para el servicio de PDF."""

import pytest
from unittest.mock import Mock, patch
from datetime import date

from app.services.pdf_service import PDFService
from app.models.comprobante import Comprobante
from app.models.empresa import Empresa
from app.models.cliente import Cliente
from app.models.punto_venta import PuntoVenta


@pytest.fixture
def pdf_service():
    """Fixture para el servicio de PDF."""
    return PDFService()


@pytest.fixture
def empresa_mock():
    """Fixture para una empresa mock."""
    empresa = Mock(spec=Empresa)
    empresa.id = 1
    empresa.razon_social = "Mi Empresa SRL"
    empresa.cuit = "30-12345678-9"
    empresa.condicion_iva = "Responsable Inscripto"
    empresa.domicilio = "Av. Corrientes 1234"
    empresa.localidad = "CABA"
    empresa.provincia = "Buenos Aires"
    empresa.inicio_actividades = date(2020, 1, 1)
    empresa.logo = None
    return empresa


@pytest.fixture
def cliente_mock():
    """Fixture para un cliente mock."""
    cliente = Mock(spec=Cliente)
    cliente.id = 1
    cliente.razon_social = "Cliente Ejemplo S.A."
    cliente.tipo_documento = "CUIT"
    cliente.numero_documento = "20-98765432-1"
    cliente.condicion_iva = "Responsable Inscripto"
    cliente.domicilio = "Av. Santa Fe 5678"
    cliente.localidad = "CABA"
    return cliente


@pytest.fixture
def punto_venta_mock():
    """Fixture para un punto de venta mock."""
    punto_venta = Mock(spec=PuntoVenta)
    punto_venta.id = 1
    punto_venta.numero = 1
    return punto_venta


@pytest.fixture
def comprobante_mock(empresa_mock, cliente_mock, punto_venta_mock):
    """Fixture para un comprobante mock."""
    comprobante = Mock(spec=Comprobante)
    comprobante.id = 1
    comprobante.tipo_comprobante = 6  # Factura B
    comprobante.numero = 127
    comprobante.fecha_emision = date(2026, 2, 3)
    comprobante.subtotal = 75000.00
    comprobante.iva_21 = 15750.00
    comprobante.iva_10_5 = 0
    comprobante.iva_27 = 0
    comprobante.total = 90750.00
    comprobante.cae = "74123456789012"
    comprobante.cae_vencimiento = date(2026, 2, 13)
    comprobante.moneda = "PES"
    comprobante.cotizacion = 1
    comprobante.observaciones = None
    comprobante.empresa = empresa_mock
    comprobante.cliente = cliente_mock
    comprobante.punto_venta = punto_venta_mock
    comprobante.items = []
    return comprobante


class TestPDFService:
    """Tests para PDFService."""

    def test_get_letra_comprobante_a(self, pdf_service):
        """Debe retornar 'A' para facturas tipo A."""
        assert pdf_service._get_letra_comprobante(1) == "A"
        assert pdf_service._get_letra_comprobante(2) == "A"
        assert pdf_service._get_letra_comprobante(3) == "A"

    def test_get_letra_comprobante_b(self, pdf_service):
        """Debe retornar 'B' para facturas tipo B."""
        assert pdf_service._get_letra_comprobante(6) == "B"
        assert pdf_service._get_letra_comprobante(7) == "B"
        assert pdf_service._get_letra_comprobante(8) == "B"

    def test_get_letra_comprobante_c(self, pdf_service):
        """Debe retornar 'C' para facturas tipo C."""
        assert pdf_service._get_letra_comprobante(11) == "C"
        assert pdf_service._get_letra_comprobante(12) == "C"
        assert pdf_service._get_letra_comprobante(13) == "C"

    def test_get_nombre_comprobante(self, pdf_service):
        """Debe retornar el nombre del tipo de comprobante."""
        assert pdf_service._get_nombre_comprobante(1) == "FACTURA"
        assert pdf_service._get_nombre_comprobante(2) == "NOTA DE DÉBITO"
        assert pdf_service._get_nombre_comprobante(3) == "NOTA DE CRÉDITO"
        assert pdf_service._get_nombre_comprobante(6) == "FACTURA"

    def test_get_tipo_documento_codigo(self, pdf_service):
        """Debe retornar el código correcto para cada tipo de documento."""
        assert pdf_service._get_tipo_documento_codigo("CUIT") == 80
        assert pdf_service._get_tipo_documento_codigo("CUIL") == 86
        assert pdf_service._get_tipo_documento_codigo("DNI") == 96
        assert pdf_service._get_tipo_documento_codigo("Otro") == 99

    def test_generar_qr_arca(self, pdf_service, comprobante_mock):
        """Debe generar un código QR válido."""
        qr_base64 = pdf_service._generar_qr_arca(comprobante_mock)

        assert qr_base64.startswith("data:image/png;base64,")
        assert len(qr_base64) > 100  # El QR debe tener contenido

    @pytest.mark.asyncio
    async def test_generar_pdf_comprobante(
        self, pdf_service, comprobante_mock, empresa_mock
    ):
        """Debe generar un PDF válido."""
        # Este test requiere que weasyprint esté instalado y configurado
        pdf_bytes = await pdf_service.generar_pdf_comprobante(
            comprobante_mock, empresa_mock
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # Verificar que sea un PDF válido (comienza con %PDF)
        assert pdf_bytes[:4] == b"%PDF"
