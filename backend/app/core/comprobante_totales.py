"""Cálculo decimal compartido por el contrato fiscal y la emisión."""

from decimal import Decimal, DecimalException
from typing import Iterable, Protocol


class ItemImportes(Protocol):
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_porcentaje: Decimal
    iva_porcentaje: Decimal


ALICUOTAS_IVA_SOPORTADAS = frozenset(
    (Decimal("0"), Decimal("10.5"), Decimal("21"), Decimal("27"))
)


def preparar_importes(items: Iterable[ItemImportes]) -> dict[str, Decimal]:
    """Prepara emisiones nuevas sin reinterpretar tasas ni cambiar la lectura histórica."""
    items = list(items)
    for index, item in enumerate(items, start=1):
        if item.iva_porcentaje not in ALICUOTAS_IVA_SOPORTADAS:
            tasa = str(item.iva_porcentaje).replace(".", ",")
            raise ValueError(
                f"El ítem {index} tiene IVA {tasa} % sin soporte. "
                "Las tasas soportadas son 0 %, 10,5 %, 21 % y 27 %. "
                "Corregí el ítem antes de emitir."
            )
    return calcular_totales(items)


def calcular_totales(items: Iterable[ItemImportes]) -> dict[str, Decimal]:
    """Conserva operaciones y redondeo fiscal; rechaza importes no calculables."""
    subtotal = Decimal("0")
    base_21 = Decimal("0")
    base_10_5 = Decimal("0")
    base_27 = Decimal("0")
    base_0 = Decimal("0")
    iva_21 = Decimal("0")
    iva_10_5 = Decimal("0")
    iva_27 = Decimal("0")

    try:
        for item in items:
            if not all(
                value.is_finite()
                for value in (
                    item.cantidad,
                    item.precio_unitario,
                    item.descuento_porcentaje,
                    item.iva_porcentaje,
                )
            ):
                raise ValueError("Los importes de los ítems deben ser finitos")
            item_subtotal = item.cantidad * item.precio_unitario
            if item.descuento_porcentaje > 0:
                descuento = item_subtotal * (item.descuento_porcentaje / 100)
                item_subtotal -= descuento
            subtotal += item_subtotal
            if item.iva_porcentaje == Decimal("21"):
                base_21 += item_subtotal
                iva_21 += item_subtotal * Decimal("0.21")
            elif item.iva_porcentaje == Decimal("10.5"):
                base_10_5 += item_subtotal
                iva_10_5 += item_subtotal * Decimal("0.105")
            elif item.iva_porcentaje == Decimal("27"):
                base_27 += item_subtotal
                iva_27 += item_subtotal * Decimal("0.27")
            else:
                base_0 += item_subtotal

        total = subtotal + iva_21 + iva_10_5 + iva_27
        valores = {
            "subtotal": subtotal,
            "base_21": base_21,
            "base_10_5": base_10_5,
            "base_27": base_27,
            "base_0": base_0,
            "iva_21": iva_21,
            "iva_10_5": iva_10_5,
            "iva_27": iva_27,
            "total": total,
        }
        resultado = {
            key: value.quantize(Decimal("0.01")) for key, value in valores.items()
        }
        if not all(value.is_finite() for value in resultado.values()):
            raise ValueError("Los totales de los ítems deben ser finitos")
        return resultado
    except DecimalException as exc:
        raise ValueError(
            "Los importes de los ítems no permiten calcular un total válido"
        ) from exc
