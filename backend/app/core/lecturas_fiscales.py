"""Lectura de bases desde detalle conservado, sin modificar hechos fiscales."""

from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

from app.core.comprobante_totales import calcular_totales
from app.core.fiscal_storage import persisted_item_subtotal


def leer_bases_iva(comprobante) -> dict:
    """Contrasta la reconstrucción PF-03B; una base desconocida nunca es cero."""
    desconocidas = {f"gravado_{tasa}": None for tasa in ("21", "10_5", "27")}
    desconocidas.update(
        sin_clasificacion=None,
        sin_iva_discriminado=None,
        no_gravado=None,
        exento=None,
        bases_acreditadas=False,
        origen_bases="detalle_no_acreditado",
    )
    items = sorted(comprobante.items or [], key=lambda item: item.orden)
    tasas_soportadas = (
        {Decimal("0")}
        if comprobante.tipo_comprobante in {11, 12, 13}
        else {Decimal("0"), Decimal("10.5"), Decimal("21"), Decimal("27")}
    )
    if not items or any(item.iva_porcentaje not in tasas_soportadas for item in items):
        return desconocidas
    try:
        with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
            if any(persisted_item_subtotal(item) != item.subtotal for item in items):
                return desconocidas
            totales = calcular_totales(items)
        if any(
            totales[key] != getattr(comprobante, key)
            for key in ("subtotal", "iva_21", "iva_10_5", "iva_27", "total")
        ):
            return desconocidas
    except (ValueError, ArithmeticError):
        return desconocidas
    if comprobante.tipo_comprobante in {11, 12, 13}:
        if any(
            getattr(comprobante, key) != 0 for key in ("iva_21", "iva_10_5", "iva_27")
        ):
            return desconocidas
        return {
            **desconocidas,
            "gravado_21": Decimal(0),
            "gravado_10_5": Decimal(0),
            "gravado_27": Decimal(0),
            "sin_iva_discriminado": comprobante.subtotal,
            "sin_clasificacion": Decimal(0),
            "bases_acreditadas": True,
            "origen_bases": "sin_iva_discriminado",
        }
    return {
        **desconocidas,
        **{f"gravado_{tasa}": totales[f"base_{tasa}"] for tasa in ("21", "10_5", "27")},
        "sin_clasificacion": totales["base_0"],
        "sin_iva_discriminado": Decimal(0),
        "bases_acreditadas": True,
        "origen_bases": "detalle_contrastado",
    }
