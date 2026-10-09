"""Tests para el servicio de PDF."""

import base64
import json
import pytest
from unittest.mock import Mock
from datetime import date
from types import SimpleNamespace
from io import BytesIO
from decimal import Decimal, localcontext

from pypdf import PdfReader
from weasyprint import HTML
from weasyprint.urls import URLFetcher, URLFetchingError

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
    empresa.ingresos_brutos = "CM 12345678"
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
    comprobante.fecha_servicio_desde = date(2026, 2, 1)
    comprobante.fecha_servicio_hasta = date(2026, 2, 28)
    comprobante.fecha_vto_pago = date(2026, 2, 28)
    comprobante.subtotal = 75000.00
    comprobante.descuento = 0
    comprobante.iva_21 = 15750.00
    comprobante.iva_10_5 = 0
    comprobante.iva_27 = 0
    comprobante.otros_impuestos = 0
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

    @pytest.mark.parametrize(
        "tipo,numero,etiqueta",
        [
            (80, "20409378472", "CUIT"),
            (86, "20409378472", "CUIL"),
            (96, "12345678", "DNI"),
        ],
    )
    async def test_pf13_pdf_y_qr_conservan_cf_identificado(
        self, pdf_service, comprobante_mock, empresa_mock, tipo, numero, etiqueta
    ):
        comprobante_mock.receptor_razon_social = "Receptor sintético"
        comprobante_mock.receptor_tipo_documento = tipo
        comprobante_mock.receptor_numero_documento = numero
        comprobante_mock.receptor_condicion_iva = "CF"
        comprobante_mock.receptor_domicilio = ""
        url = pdf_service._generar_qr_url_arca(comprobante_mock)
        qr = json.loads(base64.b64decode(url.split("?p=")[1]))
        assert qr["tipoDocRec"] == tipo
        assert qr["nroDocRec"] == int(numero)
        pdf = await pdf_service.generar_pdf_comprobante(comprobante_mock, empresa_mock)
        texto = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
        assert "Receptor sintético" in texto
        assert "Consumidor Final" in texto
        assert (etiqueta if tipo == 80 else "Doc.:") in texto
        assert numero in texto
        assert "Cliente Ejemplo S.A." not in texto

    @pytest.mark.parametrize("value", ["1.2300E200000", "1.2300E-200000"])
    def test_exponente_pdf_conserva_ceros_del_exponente(self, pdf_service, value):
        number = Decimal(value)
        assert pdf_service._format_cantidad_ar(number) == str(number).replace(".", ",")

    async def test_pdf_y_qr_preservan_decimales_ampliados(
        self, pdf_service, comprobante_mock, empresa_mock
    ):
        comprobante_mock.total = Decimal("9007199254740992.01")
        comprobante_mock.cotizacion = Decimal("1.1234567890123456789012345678")
        comprobante_mock.items = [
            SimpleNamespace(
                codigo="S" * 101,
                descripcion="Detalle sintético ampliado",
                cantidad=Decimal("1.00005"),
                unidad="unidades",
                precio_unitario=Decimal("0.1234567890123456789012345678"),
                descuento_porcentaje=Decimal("0.00123"),
                subtotal=Decimal("0.12"),
            )
        ]
        url = pdf_service._generar_qr_url_arca(comprobante_mock)
        payload = json.loads(base64.b64decode(url.split("?p=")[1]), parse_float=Decimal)
        assert payload["importe"] == comprobante_mock.total
        assert payload["ctz"] == comprobante_mock.cotizacion
        with localcontext() as context:
            context.prec = 8
            assert (
                pdf_service._format_cantidad_ar(
                    comprobante_mock.items[0].precio_unitario
                )
                == "0,1234567890123456789012345678"
            )
        pdf = await pdf_service.generar_pdf_comprobante(comprobante_mock, empresa_mock)
        rendered = "\n".join(
            page.extract_text() for page in PdfReader(BytesIO(pdf)).pages
        )
        assert "1,00005" in rendered
        assert "0,1234567890123456789012345678" in rendered
        assert "0,00123" in rendered
        assert "9.007.199.254.740.992,01" in rendered

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

    def test_template_escapa_html_por_defecto(self, pdf_service):
        """Debe escapar datos libres antes de renderizarlos como HTML."""
        template = pdf_service.env.from_string("{{ valor }}")

        assert template.render(valor="<script>alert(1)</script>") == (
            "&lt;script&gt;alert(1)&lt;/script&gt;"
        )

    @pytest.mark.asyncio
    async def test_factura_html_escapa_datos_fiscales_controlados(
        self, monkeypatch, pdf_service, comprobante_mock, empresa_mock, cliente_mock
    ):
        """Debe impedir que datos libres inyecten HTML/CSS activo en el PDF."""
        rendered = {}

        class CapturingHTML:
            def __init__(self, **kwargs):
                rendered.update(kwargs)

            def write_pdf(self, stylesheets=None):
                rendered["stylesheets"] = stylesheets
                return b"%PDF-test"

        monkeypatch.setattr("app.services.pdf_service.HTML", CapturingHTML)
        empresa_mock.razon_social = "<b>Empresa falsa</b>"
        cliente_mock.razon_social = "<b>Cliente falso</b>"
        comprobante_mock.items = [
            SimpleNamespace(
                codigo="<b>SKU</b>",
                descripcion="<style>.cae{display:none}</style><h1>Texto falso</h1>",
                cantidad=1,
                unidad='<img src="https://attacker.test/recurso.png">',
                precio_unitario=100,
                descuento_porcentaje=0,
                subtotal=100,
            )
        ]

        pdf_bytes = await pdf_service.generar_pdf_comprobante(
            comprobante_mock, empresa_mock
        )

        html = rendered["string"]
        assert pdf_bytes == b"%PDF-test"
        assert "&lt;b&gt;Empresa falsa&lt;/b&gt;" in html
        assert "&lt;b&gt;Cliente falso&lt;/b&gt;" in html
        assert "&lt;style&gt;.cae{display:none}&lt;/style&gt;" in html
        assert "&lt;h1&gt;Texto falso&lt;/h1&gt;" in html
        assert "&lt;img src=&#34;https://attacker.test/recurso.png&#34;&gt;" in html
        assert "<b>Empresa falsa</b>" not in html
        assert "<b>Cliente falso</b>" not in html
        assert "<style>.cae{display:none}</style>" not in html
        assert "<h1>Texto falso</h1>" not in html
        assert '<img src="https://attacker.test/recurso.png">' not in html

    def test_fetch_recurso_pdf_rechaza_urls_externas(self, pdf_service):
        """Debe bloquear fetches externos durante el render de PDFs fiscales."""
        with pytest.raises(ValueError, match="Recurso externo no permitido"):
            pdf_service._fetch_recurso_pdf("https://attacker.test/recurso.png")

    @pytest.mark.parametrize("resource", ["../privado.txt", "file:///etc/passwd"])
    def test_fetch_recurso_pdf_rechaza_archivos_fuera_de_templates(
        self, pdf_service, resource
    ):
        """Las rutas relativas y absolutas conservan el aislamiento de archivos."""
        with pytest.raises(ValueError, match="fuera del directorio permitido"):
            pdf_service._fetch_recurso_pdf(resource)

    def test_stylesheet_parametro_respeta_fetcher_original(
        self, pdf_service, monkeypatch
    ):
        """La regresión de WeasyPrint no permite red mediante stylesheets externos."""
        from unittest.mock import Mock

        acceso = Mock(side_effect=AssertionError("No debe llegar al fetch de red"))
        monkeypatch.setattr(URLFetcher, "fetch", acceso)
        with pytest.raises(URLFetchingError, match="Recurso externo no permitido"):
            HTML(
                string="<p>Documento sintético</p>",
                url_fetcher=pdf_service._url_fetcher,
            ).write_pdf(stylesheets=["https://attacker.test/estilos.css"])
        acceso.assert_not_called()

    def test_generar_qr_arca(self, pdf_service, comprobante_mock):
        """Debe generar un código QR válido."""
        qr_base64 = pdf_service._generar_qr_arca(comprobante_mock)

        assert qr_base64.startswith("data:image/png;base64,")
        assert len(qr_base64) > 100  # El QR debe tener contenido

    def test_generar_qr_payload_arca(self, pdf_service, comprobante_mock):
        """Debe armar el payload requerido por la especificación QR de ARCA."""
        payload = pdf_service._generar_qr_payload_arca(comprobante_mock)

        assert payload == {
            "ver": 1,
            "fecha": "2026-02-03",
            "cuit": 30123456789,
            "ptoVta": 1,
            "tipoCmp": 6,
            "nroCmp": 127,
            "importe": 90750.0,
            "moneda": "PES",
            "ctz": 1.0,
            "tipoDocRec": 80,
            "nroDocRec": 20987654321,
            "tipoCodAut": "E",
            "codAut": 74123456789012,
        }

    def test_generar_qr_url_arca_codifica_payload_base64(
        self, pdf_service, comprobante_mock
    ):
        """Debe codificar el JSON del comprobante en Base64 dentro de la URL."""
        url = pdf_service._generar_qr_url_arca(comprobante_mock)
        encoded = url.split("?p=", maxsplit=1)[1]
        decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))

        assert url.startswith("https://www.afip.gob.ar/fe/qr/?p=")
        assert decoded["ver"] == 1
        assert decoded["fecha"] == "2026-02-03"
        assert decoded["tipoCodAut"] == "E"
        assert decoded["codAut"] == 74123456789012

    def test_receptor_consumidor_final_con_nombre_muestra_razon_social(
        self, pdf_service
    ):
        """Debe ocultar el documento tecnico 0 sin borrar una razon social real."""
        receptor = SimpleNamespace(
            tipo_documento=99,
            numero_documento="0",
            razon_social="CLIENTE DE PRUEBA -",
            condicion_iva="CF",
            domicilio="",
            localidad="",
        )

        display = pdf_service._get_receptor_display(receptor)

        assert display == {
            "documento": "-",
            "nombre": "CLIENTE DE PRUEBA -",
            "condicion_iva": "Consumidor Final",
            "domicilio": "",
        }

    def test_receptor_consumidor_final_generico_no_muestra_nombre_tecnico(
        self, pdf_service
    ):
        """Debe evitar datos repetidos cuando el receptor es generico."""
        receptor = SimpleNamespace(
            tipo_documento=99,
            numero_documento="0",
            razon_social="A CONSUMIDOR FINAL",
            condicion_iva="CF",
            domicilio="",
            localidad="",
        )

        display = pdf_service._get_receptor_display(receptor)

        assert display == {
            "documento": "-",
            "nombre": "",
            "condicion_iva": "Consumidor Final",
            "domicilio": "",
        }

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
        document = PdfReader(BytesIO(pdf_bytes))
        assert len(document.pages) == 1
        texto = document.pages[0].extract_text()
        assert "03/02/2026" in texto
        assert "90.750,00" in texto
        assert comprobante_mock.cae in texto
        assert "PES" in texto
        assert "Cotización conservada" in texto

    async def test_pdf_divisa_conserva_moneda_y_cotizacion(
        self, pdf_service, comprobante_mock, empresa_mock
    ):
        comprobante_mock.moneda = "DOL"
        comprobante_mock.cotizacion = Decimal("1500.123456")
        contenido = await pdf_service.generar_pdf_comprobante(
            comprobante_mock, empresa_mock
        )
        documento = PdfReader(BytesIO(contenido))
        assert len(documento.pages) == 1
        texto = documento.pages[0].extract_text()
        assert "DOL" in texto and "1500,123456" in texto
        assert "90.750,00" in texto
