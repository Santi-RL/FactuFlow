"""Descriptor congelado del esquema anterior a A-01 (no consulta el ORM)."""

from decimal import Decimal
import math

import sqlalchemy as sa

from app.core.fiscal_storage import encode_decimal, scaled_integer

A01_HEAD = "b2c3d4e5f6a7"
LEGACY_HEAD = "a1b2c3d4e5f6"
LEGACY_COLUMNS = {
    "comprobante_items": {
        "codigo": sa.String(50),
        "cantidad": sa.Numeric(10, 4),
        "precio_unitario": sa.Numeric(12, 4),
        "descuento_porcentaje": sa.Numeric(5, 2),
        "iva_porcentaje": sa.Numeric(5, 2),
        "subtotal": sa.Numeric(12, 2),
    },
    "comprobantes": {
        **{
            name: sa.Numeric(12, 2)
            for name in (
                "subtotal",
                "descuento",
                "iva_21",
                "iva_10_5",
                "iva_27",
                "otros_impuestos",
                "total",
            )
        },
        "cotizacion": sa.Numeric(10, 6),
    },
    "intentos_emision_fiscal": {"total": sa.Numeric(12, 2)},
    "lotes_comprobantes_grupos": {
        "total_estimado": sa.Numeric(12, 2),
        "cotizacion_duplicados": sa.String(100),
        "total_centavos": sa.BigInteger(),
    },
}
VARIABLE_COLUMNS = {
    "cantidad",
    "precio_unitario",
    "descuento_porcentaje",
    "iva_porcentaje",
    "cotizacion",
}


def legacy_read(value, old_type, dialect):
    """Usa el procesador original para REAL SQLite, nunca Decimal(str(REAL))."""
    if value is None:
        return None
    processor = old_type.result_processor(dialect, None)
    return processor(value) if processor else value


def legacy_roundtrip(value, old_type, dialect) -> bool:
    if value is None:
        return True
    if isinstance(old_type, sa.String):
        return len(value) <= old_type.length
    if isinstance(old_type, sa.Integer):
        integer = scaled_integer(value)
        return -(2**63) <= integer < 2**63
    number = Decimal(value)
    encode_decimal(number)
    if dialect.name == "sqlite":
        floating = float(number)
        return (
            math.isfinite(floating)
            and legacy_read(floating, old_type, dialect) == number
        )
    if number != 0 and (
        number.adjusted() >= old_type.precision - old_type.scale
        or Decimal(encode_decimal(number)).as_tuple().exponent < -old_type.scale
    ):
        return False
    try:
        integer = scaled_integer(number, old_type.scale)
    except ValueError:
        return False
    return abs(integer) < 10**old_type.precision
