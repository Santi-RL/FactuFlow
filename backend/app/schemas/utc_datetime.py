"""Zona explícita para respuestas de instantes producidos en UTC."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def _serialize_utc_datetime(value: datetime) -> datetime:
    """Conserva el instante sin modificar el objeto ni su valor en Python."""
    if value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# Sólo campos con procedencia UTC acreditada; no fechas ni historia sin zona.
UTCResponseDateTime = Annotated[
    datetime,
    PlainSerializer(_serialize_utc_datetime, return_type=datetime, when_used="json"),
]
