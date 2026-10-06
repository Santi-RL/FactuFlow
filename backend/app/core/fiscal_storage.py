"""Representación fiscal exacta, independiente del contexto y del motor SQL.

Los importes calculados conservan PF-03B. Este módulo sólo codifica, compara
y suma resultados monetarios ya calculados; no redondea entradas fiscales.
"""

from __future__ import annotations

from decimal import Decimal, DecimalException
from hashlib import sha256
from typing import Any

from sqlalchemy import Numeric, Text, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.types import TypeDecorator


def decimal_value(value: Any) -> Decimal:
    if isinstance(value, float):
        raise ValueError("La persistencia fiscal requiere decimales, no flotantes")
    number = value if isinstance(value, Decimal) else Decimal(value)
    if not number.is_finite():
        raise ValueError("El valor fiscal debe ser finito")
    return number


def encode_decimal(value: Any) -> str:
    """Coeficiente/exponente compacto, sin normalize ni operaciones con contexto."""
    number = decimal_value(value)
    sign, digits, exponent = number.as_tuple()
    if not any(digits):
        return "0E0"
    digits = list(digits)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    coefficient = "".join(str(digit) for digit in digits)
    return f"{'-' if sign else ''}{coefficient}E{exponent}"


def decimal_search_key(value: Any) -> str:
    return sha256(encode_decimal(value).encode("ascii")).hexdigest()


def quotation_search_default(context: Any) -> str | None:
    value = context.get_current_parameters().get("cotizacion_duplicados")
    return decimal_search_key(Decimal(value)) if value is not None else None


def persisted_item_subtotal(item: Any) -> Decimal:
    """Redondeo de guardado vigente, independiente del total fiscal PF-03B."""
    subtotal = item.cantidad * item.precio_unitario
    if item.descuento_porcentaje > 0:
        subtotal -= subtotal * (item.descuento_porcentaje / 100)
    return subtotal.quantize(Decimal("0.01"))


def validate_storage_request(request: Any) -> None:
    """Encodabilidad común antes de reserva/CAE, también para workers/reintentos."""
    encode_decimal(request.cotizacion)
    for index, item in enumerate(request.items):
        if not 0 <= (item.orden if item.orden > 0 else index) <= 2147483647:
            raise ValueError(
                "El orden del ítem excede la capacidad técnica de almacenamiento"
            )
        try:
            subtotal = persisted_item_subtotal(item)
        except DecimalException as exc:
            raise ValueError(
                "El importe del ítem excede la capacidad del cálculo fiscal vigente"
            ) from exc
        for value in (
            item.cantidad,
            item.precio_unitario,
            item.descuento_porcentaje,
            item.iva_porcentaje,
            subtotal,
        ):
            encode_decimal(value)


def scaled_integer(value: Any, scale: int = 0) -> int:
    """Escala exacta: tampoco la multiplicación por cien usa contexto Decimal."""
    number = decimal_value(value)
    sign, digits, exponent = number.as_tuple()
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    exponent += scale
    if exponent < 0:
        coefficient, remainder = divmod(coefficient, 10**-exponent)
        if remainder:
            raise ValueError("El valor fiscal no es integral en la escala requerida")
    else:
        coefficient *= 10**exponent
    return -coefficient if sign else coefficient


def from_scaled_integer(value: int, scale: int = 2) -> Decimal:
    # str(int) tiene un límite de seguridad global; los importes PF-03B y sus
    # agregados no requieren modificarlo para respetar su capacidad efectiva.
    return Decimal(f"{value}E{-scale}")


def sum_amounts(values: Any) -> Decimal:
    return from_scaled_integer(sum(scaled_integer(value, 2) for value in values))


def sum_decimals(values: Any) -> Decimal:
    """Suma lecturas exactas (incluidas bases legacy), sin reinterpretarlas."""
    numbers = [decimal_value(value) for value in values]
    scale = min((number.as_tuple().exponent for number in numbers), default=0)
    return from_scaled_integer(
        sum(scaled_integer(number, -scale) for number in numbers), -scale
    )


def decimal_json_dumps(value: Any) -> str:
    """JSON numérico exacto para QR; Decimal nunca pasa por float."""
    import json

    if isinstance(value, Decimal):
        return str(decimal_value(value))
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                json.dumps(key, ensure_ascii=False) + ":" + decimal_json_dumps(item)
                for key, item in value.items()
            )
            + "}"
        )
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(decimal_json_dumps(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def compare_decimal(left: str, right: str) -> int:
    a, b = Decimal(left), Decimal(right)
    if not a.is_finite() or not b.is_finite():
        raise ValueError("El valor fiscal debe ser finito")
    return (a > b) - (a < b)


class _SQLiteAmountSum:
    def __init__(self) -> None:
        self.cents = 0

    def step(self, value: str | None) -> None:
        if value is not None:
            self.cents += scaled_integer(value, 2)

    def finalize(self) -> str:
        return encode_decimal(from_scaled_integer(self.cents))


def _install_sqlite_functions(connection: Any, _record: Any) -> None:
    """Todas las conexiones: API, worker, Alembic, herramientas y tests.

    aiosqlite no expone create_aggregate/create_collation. Su cola _execute
    garantiza que el registro nativo ocurra en el mismo hilo que la conexión.
    """

    def install(native: Any) -> None:
        native.create_collation("ff_decimal", compare_decimal)
        native.create_aggregate("ff_amount_sum", 1, _SQLiteAmountSum)

    if hasattr(connection, "run_async"):
        if type(connection).__module__.startswith("sqlalchemy.dialects.sqlite"):

            async def install_async(driver: Any) -> None:
                await driver._execute(install, driver._conn)

            connection.run_async(install_async)
    elif type(connection).__module__ == "sqlite3":
        install(connection)


event.listen(Engine, "connect", _install_sqlite_functions)


class _DecimalOrder(FunctionElement):
    inherit_cache = True


class _AmountOrder(FunctionElement):
    inherit_cache = True


@compiles(_AmountOrder, "sqlite")
def _sqlite_amount_order(element: Any, compiler: Any, **kwargs: Any) -> str:
    return _sqlite_order(element, compiler, **kwargs)


@compiles(_AmountOrder, "postgresql")
def _postgres_amount_order(element: Any, compiler: Any, **kwargs: Any) -> str:
    return compiler.process(list(element.clauses)[0], **kwargs)


@compiles(_DecimalOrder, "sqlite")
def _sqlite_order(element: Any, compiler: Any, **kwargs: Any) -> str:
    return (
        f"({compiler.process(list(element.clauses)[0], **kwargs)} COLLATE ff_decimal)"
    )


@compiles(_DecimalOrder, "postgresql")
def _postgres_order(element: Any, compiler: Any, **kwargs: Any) -> str:
    value = compiler.process(list(element.clauses)[0], **kwargs)
    coefficient = f"ltrim(split_part({value}, 'E', 1), '-')"
    sign = f"CASE WHEN {value} = '0E0' THEN 0 WHEN {value} LIKE '-%' THEN -1 ELSE 1 END"
    adjusted = f"(split_part({value}, 'E', 2)::numeric + length({coefficient}))"
    # Rellenar a la derecha no depende del exponente. ':' ordena después de
    # cualquier dígito y revierte la relación de prefijos en negativos.
    fraction = (
        f"CASE WHEN {value} LIKE '-%' THEN "
        f"translate({coefficient}, '0123456789', '9876543210') || ':' "
        f'ELSE {coefficient} END COLLATE "C"'
    )
    return f"ROW(({sign}), ({sign}) * {adjusted}, ({fraction}))"


class ExactDecimal(TypeDecorator):
    """Campos variables como Decimal sobre TEXT en ambos motores."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        return dialect.type_descriptor(
            Text(collation="ff_decimal") if dialect.name == "sqlite" else Text()
        )

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return None if value is None else encode_decimal(value)

    def process_result_value(self, value: Any, dialect: Any) -> Decimal | None:
        return None if value is None else decimal_value(value)

    class comparator_factory(TypeDecorator.Comparator):
        def order_expression(self, expression: Any) -> Any:
            return _DecimalOrder(expression)

        def operate(self, op: Any, *other: Any, **kwargs: Any) -> Any:
            from sqlalchemy.sql import operators
            from sqlalchemy import literal

            if op in {operators.lt, operators.le, operators.gt, operators.ge}:
                right = other[0]
                if not hasattr(right, "__clause_element__"):
                    right = literal(right, type_=self.type)
                return op(
                    self.order_expression(self.expr), self.order_expression(right)
                )
            if op is operators.asc_op:
                return self.order_expression(self.expr).asc()
            if op is operators.desc_op:
                return self.order_expression(self.expr).desc()
            return super().operate(op, *other, **kwargs)


class ExactAmount(ExactDecimal):
    """Resultado monetario: NUMERIC sin typmod o TEXT exacto en SQLite."""

    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Numeric())
        return super().load_dialect_impl(dialect)

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        number = decimal_value(value)
        return number if dialect.name == "postgresql" else encode_decimal(number)

    def process_result_value(self, value: Any, dialect: Any) -> Decimal | None:
        if value is None:
            return None
        number = decimal_value(value)
        sign, digits, exponent = number.as_tuple()
        # Escala pública histórica de los resultados monetarios. Agregar ceros
        # es exacto y no depende del contexto; jamás descarta cifras.
        if exponent > -2:
            return Decimal((sign, digits + (0,) * (exponent + 2), -2))
        return number

    # Los tipos NUMERIC PostgreSQL ya comparan y ordenan numéricamente. El
    # comparador elige el dialecto al compilar, no al construir la consulta.
    class comparator_factory(ExactDecimal.comparator_factory):
        def order_expression(self, expression: Any) -> Any:
            return _AmountOrder(expression)


class ExactInteger(ExactAmount):
    """Centavos enteros sin límite int64; integralidad comprobada en ambas vías."""

    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        integer = scaled_integer(value)
        return Decimal(integer) if dialect.name == "postgresql" else str(integer)

    def process_result_value(self, value: Any, dialect: Any) -> int | None:
        return None if value is None else scaled_integer(value)


class amount_sum(FunctionElement):
    """Agregado monetario explícito; nunca reemplaza SUM de cardinalidades."""

    type = ExactAmount()
    inherit_cache = True


@compiles(amount_sum, "sqlite")
def _sqlite_sum(element: Any, compiler: Any, **kwargs: Any) -> str:
    return f"ff_amount_sum({compiler.process(element.clauses, **kwargs)})"


@compiles(amount_sum, "postgresql")
def _postgres_sum(element: Any, compiler: Any, **kwargs: Any) -> str:
    return f"sum({compiler.process(element.clauses, **kwargs)})"
