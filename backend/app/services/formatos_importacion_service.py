"""Servicios para formatos configurables de importación de Excel."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel
from openpyxl.utils.cell import column_index_from_string
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.arca.utils import clean_cuit, validate_cuit
from app.models.empresa import Empresa
from app.models.formato_importacion import (
    FormatoImportacion,
    FormatoImportacionCampo,
    FormatoImportacionRegla,
    FormatoImportacionVersion,
)


class FormatoImportacionError(Exception):
    """Error funcional al detectar o aplicar un formato de importación."""


@dataclass
class CandidatoFormato:
    """Resultado de detección de un formato contra encabezados de Excel."""

    formato_id: int | None
    formato_version_id: int | None
    nombre: str
    alcance: str
    version: int | None
    score: float
    confianza: str
    columnas_detectadas: list[str]
    columnas_faltantes: list[str]
    mensajes: list[str]


@dataclass
class ImportacionNormalizada:
    """Archivo externo convertido al contrato interno de lotes."""

    filas: list[dict[str, Any]]
    headers_detectados: list[str]
    mapeo_usado: dict[str, Any]
    formato: FormatoImportacion
    version: FormatoImportacionVersion


FORMATO_BANCARIO_CONFIG: dict[str, Any] = {
    "tipo": "extracto_bancario_creditos",
    "header_row": 1,
    "modo_agrupacion": "fila",
    "campos": {
        "fecha_origen": {
            "origen": "header",
            "encabezados": ["Fecha"],
            "transformacion": "fecha",
            "requerido": False,
        },
        "importe_total": {
            "origen": "header",
            "encabezados": [
                "Creditos",
                "Créditos",
                "Credito",
                "Crédito",
                "Importe Credito",
                "Importe Crédito",
                "Importe acreditado",
            ],
            "transformacion": "decimal",
            "requerido": True,
        },
        "cliente_razon_social": {
            "origen": "header",
            "encabezados": [
                "Leyendas Adicionales1",
                "Leyendas Adicionales 1",
                "Nombre",
                "Cliente",
                "Razon Social",
                "Razón Social",
            ],
            "transformacion": "texto",
            "requerido": False,
            "default": "",
        },
        "cliente_numero_documento": {
            "origen": "header",
            "encabezados": [
                "Leyendas Adicionales2",
                "Leyendas Adicionales 2",
                "CUIT",
                "Documento",
                "Numero Documento",
                "Número Documento",
            ],
            "transformacion": "documento",
            "requerido": False,
            "default": "",
        },
        "punto_venta_numero": {
            "origen": "header",
            "encabezados": [
                "Pto Vta",
                "Pto. Vta.",
                "Punto Venta",
                "Punto de Venta",
                "PV",
            ],
            "transformacion": "entero",
            "requerido": True,
        },
        "tipo_comprobante": {"origen": "constante", "valor": 11},
        "cliente_condicion_iva": {
            "origen": "constante",
            "valor": "Consumidor Final",
        },
        "item_cantidad": {"origen": "constante", "valor": 1},
        "item_unidad": {"origen": "constante", "valor": "unidad"},
        "item_iva_porcentaje": {"origen": "constante", "valor": 0},
        "item_descuento_porcentaje": {"origen": "constante", "valor": 0},
        "guardar_cliente": {"origen": "constante", "valor": False},
    },
}


class FormatosImportacionService:
    """Gestiona formatos reutilizables y aplica mapeos de Excel externos."""

    FORMATO_BANCARIO_NOMBRE = "Extracto bancario - creditos IVA exento"
    CONSUMIDOR_FINAL_IDENTIFICACION_MINIMA = Decimal("10000000")

    def __init__(self, db: AsyncSession):
        self.db = db

    async def asegurar_formatos_base(self) -> None:
        """Crea formatos globales base si la base aun no los tiene."""
        result = await self.db.execute(
            select(FormatoImportacion)
            .options(selectinload(FormatoImportacion.versiones))
            .where(
                FormatoImportacion.nombre == self.FORMATO_BANCARIO_NOMBRE,
                FormatoImportacion.alcance == "global",
            )
        )
        existente = result.scalar_one_or_none()
        if existente is not None:
            await self._actualizar_formato_base_si_corresponde(existente)
            return

        formato = FormatoImportacion(
            nombre=self.FORMATO_BANCARIO_NOMBRE,
            descripcion=(
                "Formato global para extractos donde Creditos es el importe, "
                "Leyendas Adicionales1 el receptor, Leyendas Adicionales2 el "
                "documento y Pto Vta el punto de venta."
            ),
            alcance="global",
            activo=True,
        )
        self.db.add(formato)
        await self.db.flush()
        await self._crear_version_formato_base(formato, version_numero=1)
        await self.db.commit()

    async def _actualizar_formato_base_si_corresponde(
        self, formato: FormatoImportacion
    ) -> None:
        """Versiona el formato global si todavia usa una regla fiscal antigua."""
        version_vigente = self._version_vigente(formato)
        if version_vigente is None:
            await self._crear_version_formato_base(formato, version_numero=1)
            await self.db.commit()
            return

        campos = version_vigente.configuracion_json.get("campos", {})
        concepto = campos.get("concepto")
        item_descripcion = campos.get("item_descripcion")
        if concepto is None and item_descripcion is None:
            return

        for version in formato.versiones:
            if version.estado == "vigente":
                version.estado = "reemplazada"
        proxima_version = max(version.version for version in formato.versiones) + 1
        await self._crear_version_formato_base(formato, version_numero=proxima_version)
        await self.db.commit()

    async def _crear_version_formato_base(
        self, formato: FormatoImportacion, version_numero: int
    ) -> FormatoImportacionVersion:
        """Crea una version vigente del formato bancario global."""
        version = FormatoImportacionVersion(
            formato_id=formato.id,
            version=version_numero,
            estado="vigente",
            configuracion_json=FORMATO_BANCARIO_CONFIG,
            headers_firma_json={
                "requeridos": ["Creditos", "Pto Vta"],
                "opcionales": [
                    "Fecha",
                    "Leyendas Adicionales1",
                    "Leyendas Adicionales2",
                ],
            },
        )
        self.db.add(version)
        await self.db.flush()
        self._agregar_campos_desde_config(version.id, FORMATO_BANCARIO_CONFIG)
        self.db.add(
            FormatoImportacionRegla(
                version_id=version.id,
                nombre="Cada fila genera un comprobante",
                tipo="agrupacion",
                configuracion_json={"modo": "fila"},
                orden=1,
                activo=True,
            )
        )
        return version

    async def listar_formatos(self, empresa_id: int) -> list[FormatoImportacion]:
        """Lista formatos globales y formatos particulares del emisor."""
        await self.asegurar_formatos_base()
        result = await self.db.execute(
            select(FormatoImportacion)
            .options(selectinload(FormatoImportacion.versiones))
            .where(
                FormatoImportacion.activo.is_(True),
                or_(
                    FormatoImportacion.alcance == "global",
                    FormatoImportacion.empresa_id == empresa_id,
                ),
            )
            .order_by(FormatoImportacion.alcance, FormatoImportacion.nombre)
        )
        return list(result.scalars().all())

    async def crear_formato(
        self,
        empresa_id: int,
        nombre: str,
        descripcion: str | None,
        configuracion: dict[str, Any],
    ) -> FormatoImportacion:
        """Crea un formato particular del emisor con versión inicial."""
        formato = FormatoImportacion(
            nombre=nombre,
            descripcion=descripcion,
            alcance="emisor",
            empresa_id=empresa_id,
            activo=True,
        )
        self.db.add(formato)
        await self.db.flush()
        version = FormatoImportacionVersion(
            formato_id=formato.id,
            version=1,
            estado="vigente",
            configuracion_json=configuracion,
            headers_firma_json=self._construir_firma_headers(configuracion),
        )
        self.db.add(version)
        await self.db.flush()
        self._agregar_campos_desde_config(version.id, configuracion)
        await self.db.commit()
        await self.db.refresh(formato)
        return formato

    async def obtener_version(
        self, version_id: int, empresa_id: int
    ) -> FormatoImportacionVersion:
        """Obtiene una versión accesible para el emisor activo."""
        await self.asegurar_formatos_base()
        result = await self.db.execute(
            select(FormatoImportacionVersion)
            .options(
                selectinload(FormatoImportacionVersion.formato),
                selectinload(FormatoImportacionVersion.campos),
                selectinload(FormatoImportacionVersion.reglas),
            )
            .where(FormatoImportacionVersion.id == version_id)
        )
        version = result.scalar_one_or_none()
        if version is None or not version.formato.activo:
            raise FormatoImportacionError("No se encontró el formato seleccionado")
        if (
            version.formato.alcance != "global"
            and version.formato.empresa_id != empresa_id
        ):
            raise FormatoImportacionError(
                "El formato seleccionado no pertenece al emisor activo"
            )
        return version

    async def detectar_formato(
        self,
        file_bytes: bytes,
        empresa_id: int,
        template_columns: list[str],
    ) -> tuple[list[str], list[CandidatoFormato]]:
        """Detecta candidatos por encabezados y cantidad de columnas."""
        headers = self.leer_headers(file_bytes)
        candidatos: list[CandidatoFormato] = []
        if self.es_plantilla_oficial(headers, template_columns):
            candidatos.append(
                CandidatoFormato(
                    formato_id=None,
                    formato_version_id=None,
                    nombre="Plantilla oficial FactuFlow",
                    alcance="sistema",
                    version=None,
                    score=1.0,
                    confianza="alta",
                    columnas_detectadas=template_columns,
                    columnas_faltantes=[],
                    mensajes=["El archivo coincide con la plantilla oficial."],
                )
            )

        formatos = await self.listar_formatos(empresa_id)
        for formato in formatos:
            version = self._version_vigente(formato)
            if version is None:
                continue
            candidatos.append(self._evaluar_formato(headers, formato, version))

        candidatos.sort(key=lambda item: item.score, reverse=True)
        return headers, candidatos

    async def importar_con_version(
        self,
        file_bytes: bytes,
        empresa: Empresa,
        version: FormatoImportacionVersion,
    ) -> ImportacionNormalizada:
        """Convierte un Excel externo al formato interno de lote."""
        sheet, headers = self._leer_sheet_y_headers(file_bytes, version)
        mapeo = self._resolver_mapeo(headers, version.configuracion_json)
        faltantes = [
            campo
            for campo, detalle in mapeo["campos"].items()
            if detalle.get("requerido") and not detalle.get("encontrado")
        ]
        if faltantes:
            raise FormatoImportacionError(
                "El archivo no tiene columnas requeridas para este formato: "
                + ", ".join(faltantes)
            )

        header_row = int(version.configuracion_json.get("header_row", 1))
        filas: list[dict[str, Any]] = []
        for fila_excel, row in enumerate(
            sheet.iter_rows(min_row=header_row + 1, values_only=True),
            start=header_row + 1,
        ):
            if all(cell in (None, "") for cell in row):
                continue
            valores = self._extraer_valores_configurados(row, mapeo)
            filas.append(self._armar_fila_canonica(valores, empresa, fila_excel))

        if not filas:
            raise FormatoImportacionError(
                "La plantilla no contiene filas para procesar"
            )

        return ImportacionNormalizada(
            filas=filas,
            headers_detectados=headers,
            mapeo_usado=mapeo,
            formato=version.formato,
            version=version,
        )

    def leer_headers(self, file_bytes: bytes) -> list[str]:
        """Lee los encabezados de la hoja más probable del Excel."""
        sheet, headers = self._leer_sheet_y_headers(file_bytes)
        return headers

    def es_plantilla_oficial(
        self, headers: list[str], template_columns: list[str]
    ) -> bool:
        """Indica si los encabezados coinciden con la plantilla oficial."""
        normalized = {self.normalizar_etiqueta(header) for header in headers}
        return all(
            self.normalizar_etiqueta(col) in normalized for col in template_columns
        )

    @classmethod
    def normalizar_etiqueta(cls, value: Any) -> str:
        """Normaliza encabezados para tolerar acentos, espacios y símbolos."""
        text = cls.reparar_texto(value)
        decomposed = unicodedata.normalize("NFKD", text)
        ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())

    @classmethod
    def reparar_texto(cls, value: Any) -> str:
        """Corrige texto comúnmente mojibakeado en encabezados de Excel."""
        text = str(value or "").strip()
        if "Ã" not in text and "Â" not in text:
            return text
        try:
            return text.encode("latin1").decode("utf-8")
        except UnicodeError:
            return text

    def _agregar_campos_desde_config(
        self, version_id: int, configuracion: dict[str, Any]
    ) -> None:
        """Persiste una copia relacional del mapeo para inspección futura."""
        for campo_destino, config in configuracion.get("campos", {}).items():
            encabezados = config.get("encabezados") or []
            self.db.add(
                FormatoImportacionCampo(
                    version_id=version_id,
                    campo_destino=campo_destino,
                    origen_tipo=config.get("origen", "header"),
                    encabezado=encabezados[0] if encabezados else None,
                    alias_json=encabezados or None,
                    letra_columna=config.get("letra_columna"),
                    indice_columna=config.get("indice_columna"),
                    valor_constante_json=config.get("valor"),
                    requerido=bool(config.get("requerido", False)),
                    transformacion=config.get("transformacion"),
                    valor_default_json=config.get("default"),
                )
            )

    def _construir_firma_headers(self, configuracion: dict[str, Any]) -> dict[str, Any]:
        """Construye una firma simple de encabezados esperados."""
        requeridos: list[str] = []
        opcionales: list[str] = []
        for config in configuracion.get("campos", {}).values():
            encabezados = config.get("encabezados") or []
            if not encabezados:
                continue
            if config.get("requerido"):
                requeridos.append(encabezados[0])
            else:
                opcionales.append(encabezados[0])
        return {"requeridos": requeridos, "opcionales": opcionales}

    def _version_vigente(
        self, formato: FormatoImportacion
    ) -> FormatoImportacionVersion | None:
        versiones = sorted(
            [version for version in formato.versiones if version.estado == "vigente"],
            key=lambda version: version.version,
            reverse=True,
        )
        return versiones[0] if versiones else None

    def _evaluar_formato(
        self,
        headers: list[str],
        formato: FormatoImportacion,
        version: FormatoImportacionVersion,
    ) -> CandidatoFormato:
        mapeo = self._resolver_mapeo(headers, version.configuracion_json)
        campos_header = [
            (campo, detalle)
            for campo, detalle in mapeo["campos"].items()
            if detalle.get("origen") in {"header", "columna"}
        ]
        required = [item for item in campos_header if item[1].get("requerido")]
        optional = [item for item in campos_header if not item[1].get("requerido")]
        matched_required = [item for item in required if item[1].get("encontrado")]
        matched_optional = [item for item in optional if item[1].get("encontrado")]
        missing_required = [
            item[0] for item in required if not item[1].get("encontrado")
        ]
        weight = max((len(required) * 2) + len(optional), 1)
        score = ((len(matched_required) * 2) + len(matched_optional)) / weight
        if missing_required:
            confianza = "baja"
        elif score >= 0.85:
            confianza = "alta"
        elif score >= 0.6:
            confianza = "media"
        else:
            confianza = "baja"

        mensajes = [
            "Coincide con las columnas requeridas."
            if not missing_required
            else "Faltan columnas requeridas."
        ]
        return CandidatoFormato(
            formato_id=formato.id,
            formato_version_id=version.id,
            nombre=formato.nombre,
            alcance=formato.alcance,
            version=version.version,
            score=round(score, 4),
            confianza=confianza,
            columnas_detectadas=[
                item[1]["header"] for item in campos_header if item[1].get("header")
            ],
            columnas_faltantes=missing_required,
            mensajes=mensajes,
        )

    def _leer_sheet_y_headers(
        self,
        file_bytes: bytes,
        version: FormatoImportacionVersion | None = None,
    ):
        workbook = load_workbook(BytesIO(file_bytes), data_only=True)
        sheet_name = None
        header_row = 1
        if version is not None:
            sheet_name = version.configuracion_json.get("sheet_name")
            header_row = int(version.configuracion_json.get("header_row", 1))

        if sheet_name and sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
        elif "Comprobantes" in workbook.sheetnames:
            sheet = workbook["Comprobantes"]
        else:
            sheet = workbook.active

        headers = [
            self.reparar_texto(cell.value)
            for cell in sheet[header_row]
            if self.reparar_texto(cell.value)
        ]
        if not headers:
            raise FormatoImportacionError(
                "No se detectaron encabezados en la primera fila del Excel"
            )
        return sheet, headers

    def _resolver_mapeo(
        self, headers: list[str], configuracion: dict[str, Any]
    ) -> dict[str, Any]:
        normalizados = {
            self.normalizar_etiqueta(header): {"header": header, "index": index}
            for index, header in enumerate(headers)
        }
        campos: dict[str, Any] = {}
        for campo_destino, config in configuracion.get("campos", {}).items():
            origen = config.get("origen", "header")
            detalle = {
                "origen": origen,
                "requerido": bool(config.get("requerido", False)),
                "transformacion": config.get("transformacion"),
                "default": config.get("default"),
                "valor": config.get("valor"),
                "encontrado": origen in {"constante", "empresa"},
                "header": None,
                "index": None,
            }
            if origen == "header":
                for alias in config.get("encabezados", []):
                    match = normalizados.get(self.normalizar_etiqueta(alias))
                    if match:
                        detalle.update(
                            {
                                "encontrado": True,
                                "header": match["header"],
                                "index": match["index"],
                            }
                        )
                        break
            elif origen == "columna":
                index = self._resolver_indice_columna(config)
                detalle.update({"encontrado": index is not None, "index": index})

            campos[campo_destino] = detalle
        return {
            "tipo": configuracion.get("tipo"),
            "modo_agrupacion": configuracion.get("modo_agrupacion", "fila"),
            "campos": campos,
        }

    def _resolver_indice_columna(self, config: dict[str, Any]) -> int | None:
        if config.get("indice_columna") is not None:
            return int(config["indice_columna"])
        if config.get("letra_columna"):
            return column_index_from_string(config["letra_columna"]) - 1
        return None

    def _extraer_valores_configurados(
        self, row: tuple[Any, ...], mapeo: dict[str, Any]
    ) -> dict[str, Any]:
        valores: dict[str, Any] = {}
        for campo, detalle in mapeo["campos"].items():
            if detalle["origen"] == "constante":
                valores[campo] = detalle.get("valor")
                continue
            if detalle["origen"] == "empresa":
                continue

            value = detalle.get("default", "")
            index = detalle.get("index")
            if index is not None and index < len(row):
                value = row[index]
            valores[campo] = self._aplicar_transformacion(
                value, detalle.get("transformacion")
            )
        return valores

    def _armar_fila_canonica(
        self,
        valores: dict[str, Any],
        empresa: Empresa,
        fila_excel: int,
    ) -> dict[str, Any]:
        documento = clean_cuit(valores.get("cliente_numero_documento", ""))
        importe_total = self._parse_decimal(valores.get("importe_total"))
        precio_unitario = self._parse_decimal(valores.get("item_precio_unitario"))
        total_receptor = importe_total or precio_unitario or Decimal("0")
        condicion_iva = str(
            valores.get("cliente_condicion_iva", "Consumidor Final") or ""
        ).strip()
        es_consumidor_final = condicion_iva.upper() in {"CF", "CONSUMIDOR FINAL"}
        if (
            es_consumidor_final
            and total_receptor < self.CONSUMIDOR_FINAL_IDENTIFICACION_MINIMA
        ):
            documento = ""
        item_precio_unitario = valores.get(
            "item_precio_unitario", valores.get("importe_total", "")
        )
        return {
            "comprobante_ref": f"FILA-{fila_excel:05d}",
            "empresa_cuit": empresa.cuit,
            "punto_venta_numero": valores.get("punto_venta_numero", ""),
            "tipo_comprobante": valores.get("tipo_comprobante", 11),
            "concepto": valores.get("concepto", ""),
            "fecha_origen": valores.get("fecha_origen", ""),
            "importe_total": valores.get("importe_total", ""),
            "cliente_tipo_documento": self._inferir_tipo_documento(documento),
            "cliente_numero_documento": documento,
            "cliente_razon_social": valores.get("cliente_razon_social", ""),
            "cliente_condicion_iva": condicion_iva or "Consumidor Final",
            "cliente_domicilio": valores.get("cliente_domicilio", ""),
            "fecha_servicio_desde": "",
            "fecha_servicio_hasta": "",
            "fecha_vto_pago": "",
            "item_codigo": valores.get("item_codigo", ""),
            "item_descripcion": valores.get("item_descripcion", ""),
            "item_cantidad": valores.get("item_cantidad", 1),
            "item_unidad": valores.get("item_unidad", "unidad"),
            "item_precio_unitario": item_precio_unitario,
            "item_descuento_porcentaje": valores.get("item_descuento_porcentaje", 0),
            "item_iva_porcentaje": valores.get("item_iva_porcentaje", 0),
            "observaciones": valores.get("observaciones", ""),
        }

    def _aplicar_transformacion(self, value: Any, transformacion: str | None) -> Any:
        if value in (None, ""):
            return ""
        if transformacion == "decimal":
            parsed = self._parse_decimal(value)
            return str(parsed) if parsed is not None else ""
        if transformacion == "entero":
            try:
                return int(Decimal(str(self._parse_decimal(value) or value)))
            except (InvalidOperation, ValueError):
                return value
        if transformacion == "documento":
            return clean_cuit(value)
        if transformacion == "fecha":
            return self._parse_date(value) or value
        if transformacion == "texto":
            return str(value).strip()
        return value

    def _parse_decimal(self, value: Any) -> Decimal | None:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("$", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None

    def _parse_date(self, value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, (int, float)) and 1 <= value <= 60000:
            try:
                return from_excel(value).date().isoformat()
            except (TypeError, ValueError):
                return None
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    def _inferir_tipo_documento(self, documento: str) -> str:
        if not documento:
            return ""
        if len(documento) == 11 and validate_cuit(documento):
            return "CUIT"
        if len(documento) in {7, 8}:
            return "DNI"
        return "CUIT" if len(documento) == 11 else ""
