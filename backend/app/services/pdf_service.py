"""Servicio para generación de PDFs de comprobantes."""

import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Optional

import qrcode
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from app.models.comprobante import Comprobante
from app.models.empresa import Empresa

# Constante para URL del QR de AFIP (ARCA)
ARCA_QR_BASE_URL = "https://www.afip.gob.ar/fe/qr/?p="


class PDFService:
    """Servicio para generación de PDFs de comprobantes."""

    def __init__(self):
        """Inicializa el servicio de PDF con el entorno de templates."""
        template_path = Path(__file__).parent.parent / "templates" / "pdf"
        self.env = Environment(loader=FileSystemLoader(str(template_path)))

    async def generar_pdf_comprobante(
        self, comprobante: Comprobante, empresa: Empresa
    ) -> bytes:
        """
        Genera el PDF de un comprobante.

        Args:
            comprobante: Comprobante a generar
            empresa: Empresa emisora

        Returns:
            Bytes del PDF generado
        """
        # 1. Generar código QR
        qr_base64 = self._generar_qr_arca(comprobante)

        # 2. Preparar datos para el template
        datos = {
            "comprobante": comprobante,
            "empresa": empresa,
            "cliente": comprobante.cliente,
            "items": comprobante.items,
            "qr_base64": qr_base64,
            "letra": self._get_letra_comprobante(comprobante.tipo_comprobante),
            "tipo_nombre": self._get_nombre_comprobante(comprobante.tipo_comprobante),
            "punto_venta_str": f"{comprobante.punto_venta.numero:04d}",
            "numero_str": f"{comprobante.numero:08d}",
            "tipo_documento_nombre": self._get_nombre_tipo_documento(
                comprobante.cliente.tipo_documento
            ),
        }

        # 3. Renderizar HTML
        template = self.env.get_template("factura.html")
        html_content = template.render(**datos)

        # 4. Convertir a PDF
        css_path = Path(__file__).parent.parent / "templates" / "pdf" / "styles.css"
        stylesheets = []
        if css_path.exists():
            stylesheets.append(CSS(filename=str(css_path)))

        pdf = HTML(string=html_content).write_pdf(stylesheets=stylesheets)

        return pdf

    def _generar_qr_arca(self, comprobante: Comprobante) -> str:
        """
        Genera el código QR según especificación de ARCA.

        Args:
            comprobante: Comprobante para generar el QR

        Returns:
            Imagen QR en base64 para embeber en HTML
        """
        # Armar JSON según especificación ARCA
        datos_qr = {
            "ver": 1,
            "fecha": comprobante.fecha_emision.strftime("%Y-%m-%d"),
            "cuit": int(comprobante.empresa.cuit.replace("-", "")),
            "ptoVta": comprobante.punto_venta.numero,
            "tipoCmp": comprobante.tipo_comprobante,
            "nroCmp": comprobante.numero,
            "importe": float(comprobante.total),
            "moneda": comprobante.moneda,
            "ctz": float(comprobante.cotizacion),
            "tipoDocRec": self._get_tipo_documento_codigo(
                comprobante.cliente.tipo_documento
            ),
            "nroDocRec": int(comprobante.cliente.numero_documento.replace("-", "")),
            "tipoCodAut": "E",  # E = CAE
            "codAut": int(comprobante.cae) if comprobante.cae else 0,
        }

        # Encodear en base64
        json_str = json.dumps(datos_qr)
        base64_data = base64.b64encode(json_str.encode()).decode()

        # URL del QR
        url_qr = f"{ARCA_QR_BASE_URL}{base64_data}"

        # Generar imagen QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(url_qr)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convertir a base64
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"

    def _get_letra_comprobante(self, tipo: int) -> str:
        """
        Obtiene la letra del comprobante (A, B, C).

        Args:
            tipo: Código del tipo de comprobante

        Returns:
            Letra del comprobante
        """
        if tipo in [1, 2, 3]:
            return "A"
        elif tipo in [6, 7, 8]:
            return "B"
        elif tipo in [11, 12, 13]:
            return "C"
        return ""

    def _get_nombre_comprobante(self, tipo: int) -> str:
        """
        Obtiene el nombre del tipo de comprobante.

        Args:
            tipo: Código del tipo de comprobante

        Returns:
            Nombre del comprobante
        """
        nombres = {
            1: "FACTURA",
            2: "NOTA DE DÉBITO",
            3: "NOTA DE CRÉDITO",
            6: "FACTURA",
            7: "NOTA DE DÉBITO",
            8: "NOTA DE CRÉDITO",
            11: "FACTURA",
            12: "NOTA DE DÉBITO",
            13: "NOTA DE CRÉDITO",
        }
        return nombres.get(tipo, "COMPROBANTE")

    def _get_tipo_documento_codigo(self, tipo_documento: str) -> int:
        """
        Convierte el tipo de documento a código ARCA.

        Args:
            tipo_documento: Tipo de documento (CUIT, CUIL, DNI, etc.)

        Returns:
            Código numérico según ARCA
        """
        codigos = {
            "CUIT": 80,
            "CUIL": 86,
            "DNI": 96,
            "LE": 89,
            "LC": 90,
            "CI": 91,
            "Pasaporte": 94,
        }
        return codigos.get(tipo_documento, 99)  # 99 = Otro

    def _get_nombre_tipo_documento(self, tipo_documento: str) -> str:
        """
        Obtiene el nombre completo del tipo de documento.

        Args:
            tipo_documento: Tipo de documento

        Returns:
            Nombre completo del tipo de documento
        """
        nombres = {
            "CUIT": "CUIT",
            "CUIL": "CUIL",
            "DNI": "DNI",
            "LE": "Libreta de Enrolamiento",
            "LC": "Libreta Cívica",
            "CI": "Cédula de Identidad",
            "Pasaporte": "Pasaporte",
        }
        return nombres.get(tipo_documento, tipo_documento)


# Instancia global del servicio
pdf_service = PDFService()
