"""Extracción de puntos de venta desde constancias ARCA."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
import re
import unicodedata

from pypdf import PdfReader


CLASIFICADOR_RECE_VERSION = "rece_constancia_v2"
SENAL_RECE_EXACTA = "RECE para aplicativo y web services"
SENALES_RECE_EXACTAS = (
    SENAL_RECE_EXACTA,
    "Factura Electrónica - RI IVA - Aplicativo y Web Services",
    "Factura Electrónica - Exento en IVA - Web Services",
    "Factura Electrónica - Monotributo - Web Services",
)

_ENCABEZADO_TABLA = re.compile(
    r"(?:PUNTO\s+VENTA|P\.VTA\.)\s+"
    r"SISTEMA\s+DOMICILIO\s+NOMBRE\s+FANTASIA"
    r"(?:\s+ACTIVIDAD)?",
    re.IGNORECASE,
)
_FECHA_ARGENTINA = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")


class ConstanciaPuntosVentaError(ValueError):
    """Error controlado al procesar una constancia de puntos de venta."""


@dataclass
class PuntoVentaConstancia:
    """Punto de venta detectado en la constancia."""

    numero: int
    sistema: str
    domicilio: str | None = None
    nombre_fantasia: str | None = None
    es_webservice: bool = False


@dataclass
class DatosConstanciaPuntosVenta:
    """Datos detectados desde la constancia."""

    cuit: str | None = None
    razon_social: str | None = None
    documento_emitido_en: date | None = None
    puntos_venta: list[PuntoVentaConstancia] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


PROVINCIAS = [
    "CIUDAD AUTONOMA BUENOS AIRES",
    "BUENOS AIRES",
    "CATAMARCA",
    "CHACO",
    "CHUBUT",
    "CORDOBA",
    "CORRIENTES",
    "ENTRE RIOS",
    "FORMOSA",
    "JUJUY",
    "LA PAMPA",
    "LA RIOJA",
    "MENDOZA",
    "MISIONES",
    "NEUQUEN",
    "RIO NEGRO",
    "SALTA",
    "SAN JUAN",
    "SAN LUIS",
    "SANTA CRUZ",
    "SANTA FE",
    "SANTIAGO DEL ESTERO",
    "TIERRA DEL FUEGO",
    "TUCUMAN",
]


def extraer_texto_constancia_puntos_pdf(contenido: bytes) -> str:
    """Extrae texto de una constancia PDF de puntos de venta."""

    try:
        reader = PdfReader(BytesIO(contenido))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ConstanciaPuntosVentaError("No se pudo leer el PDF.") from exc

    if not text.strip():
        raise ConstanciaPuntosVentaError("El PDF no contiene texto extraíble.")

    compact = re.sub(r"\s+", " ", text).upper()
    if "PUNTOS DE VENTA" not in compact:
        raise ConstanciaPuntosVentaError(
            "El archivo no parece ser una constancia de puntos de venta ARCA."
        )

    return text


def parsear_constancia_puntos_venta(texto: str) -> DatosConstanciaPuntosVenta:
    """Parsea la lista de puntos de venta desde texto extraído del PDF."""

    datos = DatosConstanciaPuntosVenta()
    datos.cuit = _extraer_cuit(texto)
    datos.razon_social = _extraer_razon_social(texto)
    datos.documento_emitido_en = _extraer_fecha_documento(texto)

    bloque = _extraer_bloque_tabla(texto)
    rows = re.split(r"(?=\b\d{5}\s+)", bloque)

    for row in rows:
        row = row.strip()
        if not re.match(r"^\d{5}\s+", row):
            continue
        try:
            datos.puntos_venta.append(_parsear_fila(row))
        except ConstanciaPuntosVentaError as exc:
            datos.warnings.append(str(exc))

    if not datos.puntos_venta:
        raise ConstanciaPuntosVentaError(
            "No se detectaron puntos de venta en la constancia."
        )

    return datos


def es_senal_rece_exacta(sistema: str) -> bool:
    """Clasifica solo la señal administrativa allowlist de PF-19B."""
    normalizado = _normalizar_senal_rece(sistema)
    return any(
        normalizado == _normalizar_senal_rece(senal) for senal in SENALES_RECE_EXACTAS
    )


def _extraer_fecha_documento(texto: str) -> date | None:
    """Extrae una única fecha argentina sin inventar ante ambigüedad."""
    valores = re.findall(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", texto)
    if not valores:
        return None
    fechas: list[date] = []
    for valor in valores:
        try:
            fechas.append(datetime.strptime(valor, "%d/%m/%Y").date())
        except ValueError as exc:
            raise ConstanciaPuntosVentaError(
                "La fecha documental de la constancia no es válida."
            ) from exc
    unicas = set(fechas)
    if len(unicas) != 1:
        raise ConstanciaPuntosVentaError(
            "La constancia contiene fechas documentales ambiguas."
        )
    return fechas[0]


def _extraer_cuit(texto: str) -> str | None:
    match = re.search(r"\b(20|23|24|27|30|33|34)\d{9}\b", texto)
    return match.group(0) if match else None


def _extraer_razon_social(texto: str) -> str | None:
    match = re.search(r"CUIT\s*:\s*(.+?)\s+(20|23|24|27|30|33|34)\d{9}", texto)
    if not match:
        return None
    return _normalizar(match.group(1))


def _extraer_bloque_tabla(texto: str) -> str:
    encabezados = list(_ENCABEZADO_TABLA.finditer(texto))
    if not encabezados:
        raise ConstanciaPuntosVentaError("No se encontró la tabla de puntos de venta.")

    bloques: list[str] = []
    for indice, encabezado in enumerate(encabezados):
        fin_seccion = (
            encabezados[indice + 1].start()
            if indice + 1 < len(encabezados)
            else len(texto)
        )
        bloque = texto[encabezado.end() : fin_seccion]
        pie_pagina = _FECHA_ARGENTINA.search(bloque)
        if pie_pagina:
            bloque = bloque[: pie_pagina.start()]
        if bloque.strip():
            bloques.append(bloque)

    return "\n".join(bloques)


def _parsear_fila(row: str) -> PuntoVentaConstancia:
    number_match = re.match(r"^(?P<numero>\d{5})\s+(?P<resto>.+)$", row, re.S)
    if not number_match:
        raise ConstanciaPuntosVentaError(f"No se pudo leer fila: {row[:80]}")

    numero = int(number_match.group("numero"))
    if numero < 1:
        raise ConstanciaPuntosVentaError(
            "El número de punto de venta debe estar entre 1 y 99999."
        )
    resto = number_match.group("resto")
    marker = re.search(
        r"(FISCAL|LOCALES Y ESTABLECIMIENTOS)\s*-\s*\d{4}\s*-",
        resto,
        re.S,
    )
    if not marker:
        raise ConstanciaPuntosVentaError(
            f"No se pudo detectar domicilio para el punto {numero:05d}."
        )

    sistema = _normalizar(resto[: marker.start()])
    domicilio_raw = resto[marker.start() :]
    domicilio, fantasia = _separar_domicilio_y_fantasia(domicilio_raw)

    return PuntoVentaConstancia(
        numero=numero,
        sistema=sistema,
        domicilio=domicilio,
        nombre_fantasia=fantasia,
        es_webservice=_es_webservice(sistema),
    )


def _separar_domicilio_y_fantasia(value: str) -> tuple[str | None, str | None]:
    limpio = _normalizar(value)
    upper = limpio.upper()
    for provincia in sorted(PROVINCIAS, key=len, reverse=True):
        pos = upper.find(provincia)
        if pos == -1:
            continue
        end = pos + len(provincia)
        domicilio = limpio[:end].strip(" -")
        fantasia = limpio[end:].strip(" -") or None
        return domicilio or None, fantasia
    return limpio or None, None


def _es_webservice(sistema: str) -> bool:
    compact = re.sub(r"[^A-Z]", "", sistema.upper())
    return "WEBSERVICE" in compact or "WEBSERVICES" in compact


def _normalizar_senal_rece(value: str) -> str:
    """Normaliza solo diferencias tipográficas admitidas por el clasificador."""
    normalizado = unicodedata.normalize("NFKC", value)
    normalizado = re.sub(r"[\u2010-\u2015\u2212]", "-", normalizado)
    normalizado = re.sub(
        r"\bweb\s*services\b",
        "web services",
        normalizado,
        flags=re.IGNORECASE,
    )
    return " ".join(normalizado.split()).casefold()


def _normalizar(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
