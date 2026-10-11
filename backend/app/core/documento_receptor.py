"""Identificación explícita para nuevas preparaciones fiscales WSFE."""

import math
import re
from typing import Any

from app.arca.utils import validate_cuit

TIPO_DOCUMENTO_MAP = {
    "CUIT": 80,
    "CUIL": 86,
    "DNI": 96,
    "LE": 89,
    "LC": 90,
    "PASAPORTE": 94,
    # Alias legacy de receptor sin identificar, no código de cédula identificada.
    "CI": 99,
    "CONSUMIDOR FINAL": 99,
    **{str(code): code for code in (80, 86, 96, 89, 90, 94, 99)},
}


def parse_tipo_documento(value: Any) -> int | None:
    return TIPO_DOCUMENTO_MAP.get(texto_documento(value).upper())


def texto_documento(value: Any) -> str:
    """Conserva caracteres inválidos para informarlos, sin convertirlos en DNI."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalizar_documento(value: Any, tipo: int | None) -> str:
    """Valida el tipo declarado y la representación numérica ya soportada."""
    raw = texto_documento(value)
    if not raw:
        return ""
    if not isinstance(tipo, int) or isinstance(tipo, bool) or not 0 <= tipo <= 99:
        raise ValueError(
            "Indicá el tipo de documento del receptor desde una columna o un valor fijo."
        )
    if tipo == 99:
        if raw == "0":
            return "0"
        raise ValueError("El tipo sin identificar sólo admite documento vacío o 0.")
    if tipo in {80, 86}:
        pattern = r"(?:[0-9]{11}|[0-9]{2}[-. ][0-9]{8}[-. ][0-9])"
    elif tipo == 96:
        pattern = r"(?:[0-9]{1,8}|[0-9]{1,3}(?:\.[0-9]{3}){1,2})"
    else:
        pattern = r"[0-9]{1,11}"
    if not re.fullmatch(pattern, raw):
        raise ValueError(
            "El documento del receptor tiene un formato inválido para el tipo indicado."
        )
    numero = re.sub(r"[-. ]", "", raw)
    if tipo == 96 and len(numero) > 8:
        raise ValueError("El DNI del receptor tiene un formato inválido.")
    if set(numero) == {"0"}:
        raise ValueError("El documento del receptor no puede contener sólo ceros.")
    if tipo in {80, 86} and not validate_cuit(numero):
        raise ValueError("El CUIT o CUIL del receptor no es válido.")
    return numero
