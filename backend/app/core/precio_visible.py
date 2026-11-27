"""Texto del precio unitario para la revisión, el detalle y el PDF."""

from decimal import Decimal, ROUND_05UP, ROUND_HALF_EVEN, localcontext


def _precio_ar(precio: Decimal) -> str:
    if precio.is_zero():
        return "0,00"
    if abs(precio.adjusted()) > 1000:
        return str(precio).replace(".", ",")
    entero, _, fraccion = format(precio, ",f").partition(".")
    return entero.replace(",", ".") + "," + fraccion.rstrip("0").ljust(2, "0")


def precio_unitario_visible(
    cantidad: Decimal, precio: Decimal, descuento: Decimal, subtotal: Decimal
) -> str:
    """Elige la menor escala que explica ambos importes visibles del renglón."""
    escala = -precio.as_tuple().exponent
    if (
        escala <= 2
        or precio.is_zero()
        or abs(precio.adjusted()) > 1000
        or cantidad.adjusted() + precio.adjusted() > 1000
    ):
        return _precio_ar(precio)

    # Referencia que imprime el PDF con el precio original.
    bonificacion = cantidad * precio * descuento / 100
    centavo = Decimal("0.01")
    with localcontext() as ctx:
        # Evita el doble redondeo cuando una bonificación diminuta desplaza
        # un empate exacto. No se expande la escala del descuento para restar.
        ctx.rounding = ROUND_05UP
        cifras = sum(len(v.as_tuple().digits) for v in (cantidad, precio, descuento))
        ctx.prec = max(
            ctx.prec,
            cifras + 4,
            cantidad.adjusted() + precio.adjusted() + 6,
            precio.adjusted() + 4,
        )
        referencia_bonif = bonificacion.quantize(centavo, rounding=ROUND_HALF_EVEN)

        def coincide(candidato: Decimal) -> bool:
            bruto = cantidad * candidato
            bonif = bruto * descuento / 100
            return (bruto - bonif).quantize(
                centavo, rounding=ROUND_HALF_EVEN
            ) == subtotal and bonif.quantize(
                centavo, rounding=ROUND_HALF_EVEN
            ) == referencia_bonif

        if coincide(precio):
            for decimales in range(max(2, -precio.adjusted() - 1), escala):
                candidato = precio.quantize(
                    Decimal((0, (1,), -decimales)), rounding=ROUND_HALF_EVEN
                )
                if candidato and coincide(candidato):
                    return _precio_ar(candidato)
    return _precio_ar(precio)
