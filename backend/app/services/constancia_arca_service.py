"""Extraccion de datos desde constancias de inscripcion ARCA."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
import re
import unicodedata

from pypdf import PdfReader

from app.core.provincias import normalizar_provincia_argentina


class ConstanciaArcaError(ValueError):
    """Error controlado al procesar una constancia ARCA."""


@dataclass
class DatosConstanciaArca:
    """Datos fiscales extraidos desde una constancia."""

    razon_social: str | None = None
    cuit: str | None = None
    condicion_iva: str | None = None
    domicilio: str | None = None
    localidad: str | None = None
    provincia: str | None = None
    codigo_postal: str | None = None
    inicio_actividades: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, str | list[str] | None]:
        """Convertir a diccionario serializable."""
        return {
            "razon_social": self.razon_social,
            "cuit": self.cuit,
            "condicion_iva": self.condicion_iva,
            "domicilio": self.domicilio,
            "localidad": self.localidad,
            "provincia": self.provincia,
            "codigo_postal": self.codigo_postal,
            "inicio_actividades": self.inicio_actividades,
            "warnings": self.warnings,
        }


FORMATO_INSCRIPCION_PERSONA_JURIDICA = "inscripcion_persona_juridica"
FORMATO_INSCRIPCION_PERSONA_FISICA = "inscripcion_persona_fisica"
FORMATO_OPCION_MONOTRIBUTO = "opcion_monotributo"

REPARACIONES_TEXTO_PDF = {
    "MA TIAS": "MATIAS",
    "VICT ORIA": "VICTORIA",
    "IMPUEST OS": "IMPUESTOS",
    "PRODUCT OS": "PRODUCTOS",
    "VENT A": "VENTA",
}


def extraer_texto_constancia_pdf(contenido: bytes) -> str:
    """Extraer texto de una constancia PDF."""
    try:
        reader = PdfReader(BytesIO(contenido))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ConstanciaArcaError("No se pudo leer el PDF de la constancia.") from exc

    if not text.strip():
        raise ConstanciaArcaError("El PDF no contiene texto extraible.")

    texto_compacto = _compactar_letras(text)
    es_constancia_inscripcion = "CONSTANCIADEINSCRIPCION" in texto_compacto
    es_constancia_opcion = (
        "CONSTANCIADEOPCION" in texto_compacto
        and "REGIMENSIMPLIFICADOPARAPEQUENOSCONTRIBUYENTES" in texto_compacto
    )
    if not es_constancia_inscripcion and not es_constancia_opcion:
        raise ConstanciaArcaError(
            "El archivo no parece ser una constancia de inscripcion ARCA."
        )

    return text


def parsear_constancia_arca(texto: str) -> DatosConstanciaArca:
    """Parsear campos fiscales desde el texto de una constancia ARCA."""
    lines = _lineas_limpias(texto)
    normalizado = _normalizar(texto).upper()
    formato = _detectar_formato_constancia(texto, lines)
    datos = DatosConstanciaArca()

    datos.cuit = _extraer_cuit(texto)
    datos.razon_social = _extraer_razon_social(lines)
    datos.condicion_iva = _extraer_condicion_iva(normalizado)

    domicilio, localidad, codigo_postal, provincia = _extraer_domicilio(
        lines,
        formato,
    )
    datos.domicilio = domicilio
    datos.localidad = localidad
    datos.codigo_postal = codigo_postal
    datos.provincia = provincia
    datos.inicio_actividades = _extraer_inicio_actividades(texto)

    campos_obligatorios = {
        "nombre fiscal / razon social": datos.razon_social,
        "CUIT": datos.cuit,
        "condicion IVA": datos.condicion_iva,
        "domicilio fiscal": datos.domicilio,
        "localidad": datos.localidad,
        "provincia": datos.provincia,
        "codigo postal": datos.codigo_postal,
        "inicio de actividades": datos.inicio_actividades,
    }
    for label, value in campos_obligatorios.items():
        if not value:
            datos.warnings.append(f"No se pudo detectar {label}.")

    return datos


def _normalizar(value: str) -> str:
    """Reducir espacios para busquedas."""
    return re.sub(r"[ \t\xa0]+", " ", value).strip()


def _compactar_letras(value: str) -> str:
    """Compactar texto para detectar titulos aun si el PDF separa letras."""
    sin_acentos = unicodedata.normalize("NFKD", value)
    sin_marcas = "".join(
        char for char in sin_acentos if not unicodedata.combining(char)
    )
    return re.sub(r"[^A-Z]", "", sin_marcas.upper())


def _lineas_limpias(texto: str) -> list[str]:
    """Obtener lineas sin ruido de espacios."""
    return [line.strip() for line in texto.splitlines() if line.strip()]


def _detectar_formato_constancia(texto: str, lines: list[str]) -> str:
    """Detectar el formato de constancia ARCA extraida."""
    compacto = _compactar_letras(texto)
    if (
        "CONSTANCIADEOPCION" in compacto
        and "REGIMENSIMPLIFICADOPARAPEQUENOSCONTRIBUYENTES" in compacto
    ):
        return FORMATO_OPCION_MONOTRIBUTO

    if "CONSTANCIADEINSCRIPCION" in compacto:
        tiene_datos_societarios = any(
            "FORMAJURIDICA" in _compactar_letras(line)
            or "FECHACONTRATOSOCIAL" in _compactar_letras(line)
            for line in lines
        )
        if tiene_datos_societarios:
            return FORMATO_INSCRIPCION_PERSONA_JURIDICA
        return FORMATO_INSCRIPCION_PERSONA_FISICA

    raise ConstanciaArcaError(
        "El archivo no parece ser una constancia de inscripcion ARCA."
    )


def _extraer_cuit(texto: str) -> str | None:
    """Extraer CUIT sin guiones."""
    match = re.search(r"CUIT\s*:\s*(\d{2})-?(\d{8})-?(\d)", texto, re.IGNORECASE)
    if not match:
        return None
    return "".join(match.groups())


def _extraer_razon_social(lines: list[str]) -> str | None:
    """Extraer nombre fiscal o razon social."""
    for index, line in enumerate(lines):
        if "CUIT" not in line.upper():
            continue
        if re.match(r"^\s*CUIT\s*:", line, flags=re.IGNORECASE):
            name = ""
        else:
            name = re.split(r"\s+CUIT\s*:", line, flags=re.IGNORECASE)[0]
        name = name.replace("CONSTANCIA DE INSCRIPCION", "").strip()
        if not name and index + 1 < len(lines):
            name = lines[index + 1]
        return _normalizar_nombre(name) or None
    return None


def _extraer_condicion_iva(texto_normalizado_upper: str) -> str | None:
    """Mapear condicion IVA local desde impuestos de la constancia."""
    texto_compacto = _compactar_letras(texto_normalizado_upper)
    if "IVAEXENTO" in texto_compacto:
        return "Exento"
    if "MONOTRIBUTO" in texto_normalizado_upper:
        return "Monotributo"
    if "IVA" in texto_normalizado_upper:
        return "RI"
    return None


def _extraer_domicilio(
    lines: list[str],
    formato: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Extraer domicilio, localidad, CP y provincia."""
    if formato == FORMATO_OPCION_MONOTRIBUTO:
        return _extraer_domicilio_constancia_opcion(lines)

    if formato == FORMATO_INSCRIPCION_PERSONA_FISICA:
        cuit_index = _buscar_indice_cuit(lines)
        if cuit_index is None:
            return None, None, None, None
        return _parsear_bloque_domicilio(lines[cuit_index + 1 :])

    start = None
    for index, line in enumerate(lines):
        compact = _compactar_letras(line)
        if "FECHACONTRATOSOCIAL" in compact or "FORMAJURIDICA" in compact:
            start = index + 1
            break

    if start is None:
        return None, None, None, None

    return _parsear_bloque_domicilio(lines[start:])


def _parsear_bloque_domicilio(
    lines: list[str],
) -> tuple[str | None, str | None, str | None, str | None]:
    """Parsear un bloque domicilio/localidad/codigo postal-provincia."""
    block: list[str] = []
    for line in lines:
        if _es_linea_tecnica(line):
            break
        if re.search(r"FORMA JURIDICA|FECHA CONTRATO SOCIAL", line, re.IGNORECASE):
            continue
        block.append(line)
        if len(block) == 3:
            break

    if len(block) < 3:
        return None, None, None, None

    domicilio = _normalizar_domicilio(block[0])
    localidad = _normalizar_ubicacion(block[1])
    cp_provincia = _normalizar_ubicacion(block[2])
    match = re.match(r"(?P<cp>\d{4,8})\s*-\s*(?P<provincia>.+)", cp_provincia)
    if not match:
        return domicilio, localidad, None, None

    provincia = normalizar_provincia_argentina(match.group("provincia"))
    return domicilio, localidad, match.group("cp"), provincia


def _extraer_inicio_actividades(texto: str) -> str | None:
    """Extraer fecha de inicio como primer dia del mes detectado."""
    start_match = re.search(r"FECHA DE INICIO:\s*(\d{2})-(\d{2})-(\d{4})", texto)
    if start_match:
        day, month, year = start_match.groups()
        return date(int(year), int(month), int(day)).isoformat()

    month_matches = re.findall(r"Mes de inicio:\s*(\d{2})/(\d{4})", texto)
    if month_matches:
        fechas = [date(int(year), int(month), 1) for month, year in month_matches]
        return min(fechas).isoformat()

    tax_matches = re.findall(r"\b(\d{2})-(\d{4})\b", texto)
    if tax_matches:
        fechas = [date(int(year), int(month), 1) for month, year in tax_matches]
        return min(fechas).isoformat()

    social_match = re.search(r"Fecha Contrato Social:\s*(\d{2})-(\d{2})-(\d{4})", texto)
    if social_match:
        day, month, year = social_match.groups()
        return date(int(year), int(month), int(day)).isoformat()

    return None


def _extraer_domicilio_constancia_opcion(
    lines: list[str],
) -> tuple[str | None, str | None, str | None, str | None]:
    """Extraer domicilio desde constancias de opcion monotributo."""
    cuit_index = _buscar_indice_cuit(lines)
    if cuit_index is None:
        return None, None, None, None

    block: list[str] = []
    for line in lines[cuit_index + 2 :]:
        if _es_linea_tecnica(line) or "CONSTANCIA DE OPC" in line.upper():
            break
        block.append(line)

    if len(block) < 3:
        return None, None, None, None

    domicilio = _normalizar_domicilio(block[0])
    localidad = _normalizar_ubicacion(block[1])
    cp_provincia = _normalizar_ubicacion(block[2])
    match = re.match(r"(?P<cp>\d{4,8})\s*-\s*(?P<provincia>.+)", cp_provincia)
    if not match:
        return domicilio, localidad, None, None

    provincia = normalizar_provincia_argentina(match.group("provincia"))
    return domicilio, localidad, match.group("cp"), provincia


def _buscar_indice_cuit(lines: list[str]) -> int | None:
    """Buscar la linea que contiene el ancla CUIT."""
    for index, line in enumerate(lines):
        if re.search(r"\bCUIT\s*:", line, re.IGNORECASE):
            return index
    return None


def _es_linea_tecnica(line: str) -> bool:
    """Detectar lineas tecnicas que no deben completar campos fiscales."""
    compacto = _compactar_letras(line)
    return any(
        marker in compacto
        for marker in {
            "IMPUESTOSREGIMENES",
            "ACTIVIDADESNACIONALES",
            "VIGENCIADELAPRESENTECONSTANCIA",
            "FORMULARIODEIMPRESION",
            "HTTP",
            "CONSTANCIADE",
            "AGENCIADE",
        }
    )


def _normalizar_nombre(value: str) -> str:
    """Normalizar nombre fiscal reparando artefactos comunes de PDF."""
    return _reparar_texto_pdf(_normalizar(value))


def _normalizar_domicilio(value: str) -> str:
    """Normalizar domicilio reparando numeracion separada por el PDF."""
    normalizado = _reparar_texto_pdf(_normalizar(value))
    return re.sub(r"\b(\d{1,4})\s+(\d{2})\b$", r"\1\2", normalizado)


def _normalizar_ubicacion(value: str) -> str:
    """Normalizar ubicaciones reparando cortes de letras comunes en PDFs."""
    normalizado = _reparar_texto_pdf(_normalizar(value))
    return re.sub(r"\b([A-Z])\s+([A-Z]{2})\b", r"\1\2", normalizado)


def _reparar_texto_pdf(value: str) -> str:
    """Reparar cortes internos conocidos que introduce la extraccion PDF."""
    reparado = value
    for origen, destino in REPARACIONES_TEXTO_PDF.items():
        reparado = re.sub(rf"\b{re.escape(origen)}\b", destino, reparado)
    return _normalizar(reparado)
