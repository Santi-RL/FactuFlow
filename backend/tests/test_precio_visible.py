from decimal import Decimal, localcontext

import pytest

from app.core.precio_visible import precio_unitario_visible


@pytest.mark.parametrize(
    "cantidad,precio,descuento,subtotal,visible",
    [
        ("1", "27272.727272727272", "0", "27272.73", "27.272,73"),
        ("1000", "0.123456", "0", "123.46", "0,12346"),
        ("2", "0.123456", "100", "0.00", "0,123"),
        ("1", "0.004", "0", "0.00", "0,004"),
        ("1", "0", "0", "0.00", "0,00"),
        ("1", "1.005", "0", "1.00", "1,00"),
        ("1", "1.015", "0", "1.02", "1,02"),
        (
            "1",
            "9007199254740992.016",
            "0",
            "9007199254740992.02",
            "9.007.199.254.740.992,02",
        ),
        # El precio abreviado podría ocultar la diferencia histórica.
        ("3", "0.124", "0", "0.36", "0,124"),
        ("1.5", "2.1234", "10", "2.87", "2,123"),
        ("1", "1E-200000", "0", "0.00", "1E-200000"),
    ],
)
def test_precio_visible(cantidad, precio, descuento, subtotal, visible):
    with localcontext() as ctx:
        ctx.prec = 8
        assert (
            precio_unitario_visible(
                *map(Decimal, (cantidad, precio, descuento, subtotal))
            )
            == visible
        )
