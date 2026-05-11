"""Catalogo de provincias argentinas."""

from __future__ import annotations

import re
import unicodedata


PROVINCIAS_ARGENTINAS = {
    "BUENOS AIRES": "Buenos Aires",
    "CABA": "CABA",
    "CIUDAD AUTONOMA DE BUENOS AIRES": "CABA",
    "CIUDAD AUTÓNOMA DE BUENOS AIRES": "CABA",
    "CAPITAL FEDERAL": "CABA",
    "CATAMARCA": "Catamarca",
    "CHACO": "Chaco",
    "CHUBUT": "Chubut",
    "CORDOBA": "Córdoba",
    "CÓRDOBA": "Córdoba",
    "CORRIENTES": "Corrientes",
    "ENTRE RIOS": "Entre Ríos",
    "ENTRE RÍOS": "Entre Ríos",
    "FORMOSA": "Formosa",
    "JUJUY": "Jujuy",
    "LA PAMPA": "La Pampa",
    "LA RIOJA": "La Rioja",
    "MENDOZA": "Mendoza",
    "MISIONES": "Misiones",
    "NEUQUEN": "Neuquén",
    "NEUQUÉN": "Neuquén",
    "RIO NEGRO": "Río Negro",
    "RÍO NEGRO": "Río Negro",
    "SALTA": "Salta",
    "SAN JUAN": "San Juan",
    "SAN LUIS": "San Luis",
    "SANTA CRUZ": "Santa Cruz",
    "SANTA FE": "Santa Fe",
    "SANTIAGO DEL ESTERO": "Santiago del Estero",
    "TIERRA DEL FUEGO": "Tierra del Fuego",
    "TUCUMAN": "Tucumán",
    "TUCUMÁN": "Tucumán",
}


def normalizar_provincia_argentina(value: str | None) -> str | None:
    """Normalizar una provincia argentina a su etiqueta canonica."""
    if not value:
        return None

    normalizada = _normalizar_clave(value)
    return PROVINCIAS_ARGENTINAS.get(normalizada)


def _normalizar_clave(value: str) -> str:
    """Normalizar texto para busqueda tolerante de provincias."""
    sin_acentos = unicodedata.normalize("NFKD", value)
    sin_marcas = "".join(
        char for char in sin_acentos if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", sin_marcas.upper()).strip()
