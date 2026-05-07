"""Extraccion de puntos de venta desde constancias ARCA."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import re

from pypdf import PdfReader


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
    """Extraer texto de una constancia PDF de puntos de venta."""

    try:
        reader = PdfReader(BytesIO(contenido))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ConstanciaPuntosVentaError("No se pudo leer el PDF.") from exc

    if not text.strip():
        raise ConstanciaPuntosVentaError("El PDF no contiene texto extraible.")

    compact = re.sub(r"\s+", " ", text).upper()
    if "PUNTOS DE VENTA" not in compact:
        raise ConstanciaPuntosVentaError(
            "El archivo no parece ser una constancia de puntos de venta ARCA."
        )

    return text


def parsear_constancia_puntos_venta(texto: str) -> DatosConstanciaPuntosVenta:
    """Parsear la lista de puntos de venta desde texto extraido del PDF."""

    datos = DatosConstanciaPuntosVenta()
    datos.cuit = _extraer_cuit(texto)
    datos.razon_social = _extraer_razon_social(texto)

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


def _extraer_cuit(texto: str) -> str | None:
    match = re.search(r"\b(20|23|24|27|30|33|34)\d{9}\b", texto)
    return match.group(0) if match else None


def _extraer_razon_social(texto: str) -> str | None:
    match = re.search(r"CUIT\s*:\s*(.+?)\s+(20|23|24|27|30|33|34)\d{9}", texto)
    if not match:
        return None
    return _normalizar(match.group(1))


def _extraer_bloque_tabla(texto: str) -> str:
    start = re.search(r"PUNTO VENTA\s+SISTEMA\s+DOMICILIO\s+NOMBRE FANTASIA", texto)
    if not start:
        raise ConstanciaPuntosVentaError("No se encontro la tabla de puntos de venta.")
    bloque = texto[start.end() :]
    end = re.search(r"\d{1,2}/\d{1,2}/\d{4}", bloque)
    return bloque[: end.start()] if end else bloque


def _parsear_fila(row: str) -> PuntoVentaConstancia:
    number_match = re.match(r"^(?P<numero>\d{5})\s+(?P<resto>.+)$", row, re.S)
    if not number_match:
        raise ConstanciaPuntosVentaError(f"No se pudo leer fila: {row[:80]}")

    numero = int(number_match.group("numero"))
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


def _normalizar(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
