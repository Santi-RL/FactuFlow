"""Funciones de utilidad para ARCA."""

from datetime import datetime


def format_cuit(cuit: str | int) -> str:
    """
    Formatea un CUIT al formato XX-XXXXXXXX-X.

    Args:
        cuit: CUIT como string o entero

    Returns:
        CUIT formateado

    Examples:
        >>> format_cuit("20123456789")
        "20-12345678-9"
        >>> format_cuit(20123456789)
        "20-12345678-9"
    """
    cuit_str = str(cuit).replace("-", "").strip()

    if len(cuit_str) != 11:
        raise ValueError(f"CUIT inválido: debe tener 11 dígitos, tiene {len(cuit_str)}")

    return f"{cuit_str[:2]}-{cuit_str[2:10]}-{cuit_str[10]}"


def validate_cuit(cuit: str | int) -> bool:
    """
    Valida un CUIT argentino usando el algoritmo de dígito verificador.

    Args:
        cuit: CUIT a validar

    Returns:
        True si el CUIT es válido, False en caso contrario

    Examples:
        >>> validate_cuit("20123456789")
        False  # Dígito verificador incorrecto
        >>> validate_cuit("20409378472")
        True  # CUIT de prueba de ARCA
    """
    # Limpiar el CUIT
    cuit_str = str(cuit).replace("-", "").strip()

    if len(cuit_str) != 11 or not cuit_str.isdigit():
        return False

    # Multiplicadores para el cálculo
    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

    # Calcular suma ponderada
    suma = sum(int(cuit_str[i]) * multiplicadores[i] for i in range(10))

    # Calcular dígito verificador
    resto = suma % 11
    digito_calculado = 11 - resto

    if digito_calculado == 11:
        digito_calculado = 0
    elif digito_calculado == 10:
        digito_calculado = 9

    # Comparar con el dígito verificador del CUIT
    return int(cuit_str[10]) == digito_calculado


def clean_cuit(cuit: str | int) -> str:
    """
    Limpia un CUIT removiendo caracteres no numéricos.

    Args:
        cuit: CUIT a limpiar

    Returns:
        CUIT limpio solo con dígitos

    Examples:
        >>> clean_cuit("20-12345678-9")
        "20123456789"
        >>> clean_cuit("20.12345678.9")
        "20123456789"
    """
    return "".join(c for c in str(cuit) if c.isdigit())


def format_date_arca(fecha: datetime | str) -> str:
    """
    Formatea una fecha al formato esperado por ARCA (YYYYMMDD).

    Args:
        fecha: Fecha a formatear (datetime o string YYYY-MM-DD)

    Returns:
        Fecha en formato YYYYMMDD

    Examples:
        >>> format_date_arca(datetime(2024, 12, 31))
        "20241231"
        >>> format_date_arca("2024-12-31")
        "20241231"
    """
    if isinstance(fecha, str):
        # Intentar parsear string
        if "-" in fecha:
            fecha = datetime.strptime(fecha, "%Y-%m-%d")
        elif len(fecha) == 8 and fecha.isdigit():
            return fecha  # Ya está en formato correcto
        else:
            raise ValueError(f"Formato de fecha inválido: {fecha}")

    return fecha.strftime("%Y%m%d")


def parse_date_arca(fecha: str) -> datetime:
    """
    Parsea una fecha en formato ARCA (YYYYMMDD) a datetime.

    Args:
        fecha: Fecha en formato YYYYMMDD

    Returns:
        Objeto datetime

    Examples:
        >>> parse_date_arca("20241231")
        datetime.datetime(2024, 12, 31, 0, 0)
    """
    if len(fecha) != 8 or not fecha.isdigit():
        raise ValueError(f"Formato de fecha ARCA inválido: {fecha}")

    return datetime.strptime(fecha, "%Y%m%d")


def format_importe(importe: float | int) -> float:
    """
    Formatea un importe para ARCA con 2 decimales.

    Args:
        importe: Importe a formatear

    Returns:
        Importe con 2 decimales

    Examples:
        >>> format_importe(123.456)
        123.46
        >>> format_importe(100)
        100.0
    """
    return round(float(importe), 2)
