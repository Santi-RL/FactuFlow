"""Servicio para generación de PDFs de comprobantes."""

import base64
import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import qrcode
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from app.models.comprobante import Comprobante
from app.models.empresa import Empresa

# URL oficial heredada del QR ARCA.
ARCA_QR_BASE_URL = "https://www.afip.gob.ar/fe/qr/?p="


class PDFService:
    """Servicio para generación de PDFs de comprobantes."""

    def __init__(self):
        """Inicializa el servicio de PDF con el entorno de templates."""
        template_path = Path(__file__).parent.parent / "templates" / "pdf"
        self.env = Environment(loader=FileSystemLoader(str(template_path)))
        self.env.filters["fecha_ar"] = self._format_fecha_ar
        self.env.filters["importe_ar"] = self._format_importe_ar
        self.env.filters["cantidad_ar"] = self._format_cantidad_ar
        self.env.filters["cuit_ar"] = self._format_cuit_ar

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
        cliente = self._get_receptor_pdf(comprobante)
        receptor_display = self._get_receptor_display(cliente)
        datos = {
            "comprobante": comprobante,
            "empresa": empresa,
            "cliente": cliente,
            "items": self._preparar_items_pdf(comprobante.items),
            "qr_base64": qr_base64,
            "letra": self._get_letra_comprobante(comprobante.tipo_comprobante),
            "tipo_nombre": self._get_nombre_comprobante(comprobante.tipo_comprobante),
            "tipo_codigo": self._get_codigo_comprobante(comprobante.tipo_comprobante),
            "concepto_nombre": self._get_nombre_concepto(comprobante.concepto),
            "punto_venta_str": f"{comprobante.punto_venta.numero:04d}",
            "numero_str": f"{comprobante.numero:08d}",
            "empresa_cuit": "".join(filter(str.isdigit, empresa.cuit or "")),
            "receptor_documento": receptor_display["documento"],
            "receptor_nombre": receptor_display["nombre"],
            "receptor_condicion_iva": receptor_display["condicion_iva"],
            "receptor_domicilio": receptor_display["domicilio"],
            "tipo_documento_nombre": self._get_nombre_tipo_documento(
                cliente.tipo_documento
            ),
            "ingresos_brutos": getattr(empresa, "ingresos_brutos", None),
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

    def _preparar_items_pdf(self, items: list[Any]) -> list[SimpleNamespace]:
        """Prepara filas de detalle con datos calculados para el PDF."""
        filas = []
        for item in items:
            cantidad = Decimal(str(getattr(item, "cantidad", 0) or 0))
            precio_unitario = Decimal(str(getattr(item, "precio_unitario", 0) or 0))
            descuento_porcentaje = Decimal(
                str(getattr(item, "descuento_porcentaje", 0) or 0)
            )
            importe_bonificacion = (
                cantidad * precio_unitario * descuento_porcentaje / Decimal("100")
            )
            filas.append(
                SimpleNamespace(
                    codigo=getattr(item, "codigo", None),
                    descripcion=getattr(item, "descripcion", ""),
                    cantidad=cantidad,
                    unidad=getattr(item, "unidad", "unidades"),
                    precio_unitario=precio_unitario,
                    descuento_porcentaje=descuento_porcentaje,
                    importe_bonificacion=importe_bonificacion,
                    subtotal=getattr(item, "subtotal", Decimal("0")),
                )
            )
        return filas

    def _get_receptor_display(self, cliente: Any) -> dict[str, str]:
        """Normaliza los datos visibles del receptor para evitar datos técnicos."""
        tipo_documento = getattr(cliente, "tipo_documento", "") or ""
        numero_documento = getattr(cliente, "numero_documento", "") or ""
        razon_social = getattr(cliente, "razon_social", "") or ""
        condicion_iva = getattr(cliente, "condicion_iva", "") or ""
        domicilio = getattr(cliente, "domicilio", "") or ""
        localidad = getattr(cliente, "localidad", "") or ""

        es_consumidor_final = self._es_consumidor_final(
            tipo_documento, numero_documento, razon_social, condicion_iva
        )
        documento = "-"
        if not self._es_documento_consumidor_final(tipo_documento, numero_documento):
            documento = numero_documento or "-"
        domicilio_visible = domicilio
        if domicilio_visible and localidad:
            domicilio_visible = f"{domicilio_visible}, {localidad}"
        nombre_visible = ""
        if not self._es_razon_social_consumidor_final(razon_social):
            nombre_visible = razon_social

        return {
            "documento": documento,
            "nombre": nombre_visible,
            "condicion_iva": (
                "Consumidor Final"
                if es_consumidor_final
                else self._normalizar_condicion_iva(condicion_iva)
            ),
            "domicilio": domicilio_visible,
        }

    def _es_consumidor_final(
        self,
        tipo_documento: str,
        numero_documento: str,
        razon_social: str,
        condicion_iva: str,
    ) -> bool:
        """Detecta consumidores finales para no exponer el documento técnico 0."""
        numero_normalizado = str(numero_documento).replace("-", "").strip()
        condicion_normalizada = str(condicion_iva).strip().lower()
        return (
            self._es_documento_consumidor_final(tipo_documento, numero_documento)
            or self._es_razon_social_consumidor_final(razon_social)
            or (
                condicion_normalizada in {"cf", "consumidor final"}
                and numero_normalizado in {"", "0"}
            )
        )

    def _es_documento_consumidor_final(
        self, tipo_documento: str, numero_documento: str
    ) -> bool:
        """Detecta el documento técnico usado por ARCA para consumidor final."""
        tipo_normalizado = str(tipo_documento).strip().lower()
        numero_normalizado = str(numero_documento).replace("-", "").strip()
        return tipo_normalizado in {
            "consumidor final",
            "otro",
            "99",
            "",
        } and numero_normalizado in {"", "0"}

    def _es_razon_social_consumidor_final(self, razon_social: str) -> bool:
        """Detecta nombres genéricos que no aportan datos reales del receptor."""
        razon_normalizada = str(razon_social).strip().lower()
        return razon_normalizada in {"", "a consumidor final", "consumidor final"}

    def _normalizar_condicion_iva(self, condicion_iva: str) -> str:
        """Convierte abreviaturas frecuentes de condición IVA a texto legible."""
        normalizada = condicion_iva.strip()
        if normalizada.upper() == "CF":
            return "Consumidor Final"
        return normalizada

    def _generar_qr_arca(self, comprobante: Comprobante) -> str:
        """
        Genera el código QR según especificación de ARCA.

        Args:
            comprobante: Comprobante para generar el QR

        Returns:
            Imagen QR en base64 para embeber en HTML
        """
        url_qr = self._generar_qr_url_arca(comprobante)

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

    def _generar_qr_url_arca(self, comprobante: Comprobante) -> str:
        """Genera la URL completa del QR con payload ARCA en Base64."""
        datos_qr = self._generar_qr_payload_arca(comprobante)
        json_str = json.dumps(datos_qr, separators=(",", ":"), ensure_ascii=False)
        base64_data = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
        return f"{ARCA_QR_BASE_URL}{base64_data}"

    def _generar_qr_payload_arca(self, comprobante: Comprobante) -> dict[str, Any]:
        """Arma el payload JSON requerido por la especificación QR de ARCA."""
        receptor_tipo_documento = self._get_snapshot_int(
            comprobante, "receptor_tipo_documento"
        )
        receptor_numero_documento = self._get_snapshot_str(
            comprobante, "receptor_numero_documento"
        )
        return {
            "ver": 1,
            "fecha": comprobante.fecha_emision.strftime("%Y-%m-%d"),
            "cuit": int(comprobante.empresa.cuit.replace("-", "")),
            "ptoVta": comprobante.punto_venta.numero,
            "tipoCmp": comprobante.tipo_comprobante,
            "nroCmp": comprobante.numero,
            "importe": float(comprobante.total),
            "moneda": comprobante.moneda,
            "ctz": float(comprobante.cotizacion),
            "tipoDocRec": receptor_tipo_documento
            or self._get_tipo_documento_codigo(comprobante.cliente.tipo_documento),
            "nroDocRec": int(
                (
                    receptor_numero_documento or comprobante.cliente.numero_documento
                ).replace("-", "")
                or "0"
            ),
            "tipoCodAut": "E",  # E = CAE
            "codAut": int(comprobante.cae) if comprobante.cae else 0,
        }

    def _get_receptor_pdf(self, comprobante: Comprobante):
        """Devuelve un objeto simple con el snapshot del receptor para el PDF."""
        receptor_razon_social = self._get_snapshot_str(
            comprobante, "receptor_razon_social"
        )
        if receptor_razon_social:
            tipo_documento = self._get_nombre_tipo_documento_codigo(
                self._get_snapshot_int(comprobante, "receptor_tipo_documento")
            )
            return type(
                "ReceptorPDF",
                (),
                {
                    "razon_social": receptor_razon_social,
                    "tipo_documento": tipo_documento,
                    "numero_documento": (
                        self._get_snapshot_str(comprobante, "receptor_numero_documento")
                        or "0"
                    ),
                    "condicion_iva": (
                        self._get_snapshot_str(comprobante, "receptor_condicion_iva")
                        or "CF"
                    ),
                    "domicilio": self._get_snapshot_str(
                        comprobante, "receptor_domicilio"
                    ),
                    "localidad": None,
                },
            )()
        return comprobante.cliente

    def _get_snapshot_str(self, comprobante: Comprobante, attr: str) -> str | None:
        """Lee atributos snapshot evitando mocks o descriptores no resueltos."""
        value = getattr(comprobante, attr, None)
        return value if isinstance(value, str) else None

    def _get_snapshot_int(self, comprobante: Comprobante, attr: str) -> int | None:
        """Lee atributos snapshot numéricos evitando mocks o descriptores."""
        value = getattr(comprobante, attr, None)
        return value if isinstance(value, int) else None

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

    def _get_codigo_comprobante(self, tipo: int) -> str:
        """Obtiene el código de comprobante con tres dígitos."""
        return f"{tipo:03d}"

    def _get_nombre_concepto(self, concepto: int) -> str:
        """Obtiene la descripción del concepto fiscal ARCA."""
        nombres = {
            1: "Productos",
            2: "Servicios",
            3: "Productos y servicios",
        }
        return nombres.get(concepto, "Sin especificar")

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

    def _get_nombre_tipo_documento_codigo(self, tipo_documento: int | None) -> str:
        """Convierte código ARCA de documento a etiqueta legible."""
        nombres = {
            80: "CUIT",
            86: "CUIL",
            96: "DNI",
            89: "LE",
            90: "LC",
            94: "Pasaporte",
            99: "Consumidor Final",
        }
        return nombres.get(tipo_documento or 99, "Consumidor Final")

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

    def _format_fecha_ar(self, value: date | None) -> str:
        """Formatea fechas para PDF en formato argentino."""
        if value is None:
            return "-"
        return value.strftime("%d/%m/%Y")

    def _format_importe_ar(self, value: Decimal | float | int | None) -> str:
        """Formatea importes para PDF con separadores locales."""
        if value is None:
            value = Decimal("0")
        number = Decimal(str(value))
        formatted = f"{number:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    def _format_cantidad_ar(self, value: Decimal | float | int | None) -> str:
        """Formatea cantidades del detalle del comprobante."""
        if value is None:
            value = Decimal("0")
        number = Decimal(str(value)).normalize()
        formatted = f"{number:f}"
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted.replace(".", ",")

    def _format_cuit_ar(self, value: str | None) -> str:
        """Formatea CUIT de 11 dígitos para lectura humana."""
        digits = "".join(filter(str.isdigit, value or ""))
        if len(digits) != 11:
            return value or "-"
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"


# Instancia global del servicio
pdf_service = PDFService()
