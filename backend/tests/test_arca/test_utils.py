"""Tests para funciones de utilidad de ARCA."""

import pytest
from datetime import datetime

from app.arca.utils import (
    format_cuit,
    validate_cuit,
    clean_cuit,
    format_date_arca,
    parse_date_arca,
    format_importe,
)


class TestFormatCuit:
    """Tests para format_cuit."""

    def test_format_cuit_string(self):
        """Debe formatear CUIT desde string."""
        assert format_cuit("20123456789") == "20-12345678-9"

    def test_format_cuit_integer(self):
        """Debe formatear CUIT desde entero."""
        assert format_cuit(20123456789) == "20-12345678-9"

    def test_format_cuit_already_formatted(self):
        """Debe manejar CUIT ya formateado."""
        assert format_cuit("20-12345678-9") == "20-12345678-9"

    def test_format_cuit_invalid_length(self):
        """Debe lanzar error si el CUIT no tiene 11 dígitos."""
        with pytest.raises(ValueError):
            format_cuit("123")


class TestValidateCuit:
    """Tests para validate_cuit."""

    def test_validate_cuit_valid(self):
        """Debe validar CUIT correcto."""
        # CUIT de prueba de ARCA
        assert validate_cuit("20409378472") is True

    def test_validate_cuit_invalid_checksum(self):
        """Debe rechazar CUIT con checksum inválido."""
        assert validate_cuit("20409378471") is False

    def test_validate_cuit_invalid_length(self):
        """Debe rechazar CUIT con longitud inválida."""
        assert validate_cuit("123") is False

    def test_validate_cuit_with_letters(self):
        """Debe rechazar CUIT con letras."""
        assert validate_cuit("20ABC456789") is False


class TestCleanCuit:
    """Tests para clean_cuit."""

    def test_clean_cuit_with_dashes(self):
        """Debe limpiar CUIT con guiones."""
        assert clean_cuit("20-12345678-9") == "20123456789"

    def test_clean_cuit_with_dots(self):
        """Debe limpiar CUIT con puntos."""
        assert clean_cuit("20.12345678.9") == "20123456789"

    def test_clean_cuit_mixed_separators(self):
        """Debe limpiar CUIT con separadores mixtos."""
        assert clean_cuit("20-123.456-789") == "20123456789"

    def test_clean_cuit_integer(self):
        """Debe manejar enteros."""
        assert clean_cuit(20123456789) == "20123456789"


class TestFormatDateArca:
    """Tests para format_date_arca."""

    def test_format_date_from_datetime(self):
        """Debe formatear fecha desde datetime."""
        fecha = datetime(2024, 12, 31)
        assert format_date_arca(fecha) == "20241231"

    def test_format_date_from_string_iso(self):
        """Debe formatear fecha desde string ISO."""
        assert format_date_arca("2024-12-31") == "20241231"

    def test_format_date_already_formatted(self):
        """Debe manejar fecha ya formateada."""
        assert format_date_arca("20241231") == "20241231"

    def test_format_date_invalid(self):
        """Debe lanzar error con formato inválido."""
        with pytest.raises(ValueError):
            format_date_arca("31/12/2024")


class TestParseDateArca:
    """Tests para parse_date_arca."""

    def test_parse_date_valid(self):
        """Debe parsear fecha válida."""
        result = parse_date_arca("20241231")
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 31

    def test_parse_date_invalid_length(self):
        """Debe lanzar error con longitud inválida."""
        with pytest.raises(ValueError):
            parse_date_arca("202412")

    def test_parse_date_invalid_format(self):
        """Debe lanzar error con formato inválido."""
        with pytest.raises(ValueError):
            parse_date_arca("2024-12-31")


class TestFormatImporte:
    """Tests para format_importe."""

    def test_format_importe_float(self):
        """Debe formatear float con 2 decimales."""
        assert format_importe(123.456) == 123.46

    def test_format_importe_integer(self):
        """Debe formatear entero."""
        assert format_importe(100) == 100.0

    def test_format_importe_rounding(self):
        """Debe redondear correctamente."""
        assert format_importe(99.999) == 100.0
        assert format_importe(99.994) == 99.99
