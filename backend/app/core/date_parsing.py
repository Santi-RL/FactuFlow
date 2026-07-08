"""Helpers estrictos para parsear fechas de entrada."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


SUPPORTED_DATE_FORMATS = (
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "%d/%m/%Y", "DD/MM/AAAA"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d", "YYYY-MM-DD"),
    (re.compile(r"^\d{8}$"), "%Y%m%d", "YYYYMMDD"),
)
ISO_DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ].+")


def parse_fecha_input(
    value: Any,
    *,
    field_name: str = "fecha",
    allow_empty: bool = False,
) -> date | None:
    """Parsea fechas explícitas sin normalizar calendarios inválidos."""
    if value is None:
        if allow_empty:
            return None
        raise ValueError(f"{field_name} es obligatoria")

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        if allow_empty:
            return None
        raise ValueError(f"{field_name} es obligatoria")

    for pattern, fmt, _label in SUPPORTED_DATE_FORMATS:
        if not pattern.match(text):
            continue
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    if ISO_DATETIME_PATTERN.match(text):
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            pass

    formatos = ", ".join(label for _pattern, _fmt, label in SUPPORTED_DATE_FORMATS)
    raise ValueError(
        f"{field_name} debe ser una fecha válida en formato {formatos} "
        "o ISO datetime"
    )
