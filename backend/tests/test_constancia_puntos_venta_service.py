"""Tests de importacion de constancia de puntos de venta ARCA."""

import pytest
from weasyprint import HTML

from app.services.constancia_puntos_venta_service import (
    ConstanciaPuntosVentaError,
    extraer_texto_constancia_puntos_pdf,
    parsear_constancia_puntos_venta,
)


def test_extraer_y_parsear_constancia_puntos_pdf_real_sintetico() -> None:
    """Debe extraer y parsear una constancia sintética real en memoria."""
    contenido = HTML(
        string="""
            <pre>
            CONSTANCIA DE PUNTOS DE VENTA / EMISIÓN Y DOMICILIOS
            CUIT: ENTIDAD DE PRUEBA SIN DATOS REALES 30123456789
            PUNTO VENTA SISTEMA DOMICILIO NOMBRE FANTASIA
            00006 Factura Electrónica - Exento en IVA - Web Services
            LOCALES Y ESTABLECIMIENTOS - 0002 - CALLE FALSA 123 -
            CIUDAD DE PRUEBA - BUENOS AIRES ESTABLECIMIENTO QA
            04/05/2026
            </pre>
            """
    ).write_pdf()

    texto = extraer_texto_constancia_puntos_pdf(contenido)
    datos = parsear_constancia_puntos_venta(texto)

    assert datos.cuit == "30123456789"
    assert len(datos.puntos_venta) == 1
    assert datos.puntos_venta[0].numero == 6
    assert datos.puntos_venta[0].es_webservice is True


def test_extraer_texto_constancia_puntos_pdf_malformado_devuelve_error() -> None:
    """Debe encapsular como error de dominio un PDF sintético malformado."""
    with pytest.raises(ConstanciaPuntosVentaError, match="No se pudo leer el PDF"):
        extraer_texto_constancia_puntos_pdf(b"%PDF-1.7\ncontenido sintetico malformado")


def test_parsear_constancia_puntos_venta() -> None:
    texto = """
    CONSTANCIA DE PUNTOS DE VENTA / EMISION Y DOMICILIOS
    CUIT:ENTIDAD DE PRUEBA SIN DATOS REALES
    30123456789
    PUNTO VENTA SISTEMA DOMICILIO NOMBRE FANTASIA
    00006 Factura Electrónica -
    Exento en IVA - Web
    ServicesLOCALES Y ESTABLECIMIENTOS - 0002 - CALLE
    FALSA 123 - CIUDAD DE PRUEBA -
    BUENOS AIRESESTABLECIMIENTO QA
    00007 Factuweb  (Imprenta) -
    Exento en IVAFISCAL - 0001 - CALLE DOS 456 - CIUDAD DE PRUEBA - BUENOS
    AIRESESTABLECIMIENTO QA
    04/5/2026 7:59:00 PM
    """

    datos = parsear_constancia_puntos_venta(texto)

    assert datos.cuit == "30123456789"
    assert len(datos.puntos_venta) == 2
    assert datos.puntos_venta[0].numero == 6
    assert datos.puntos_venta[0].es_webservice is True
    assert datos.puntos_venta[0].nombre_fantasia == "ESTABLECIMIENTO QA"
    assert "CALLE FALSA" in datos.puntos_venta[0].domicilio
    assert datos.puntos_venta[1].numero == 7
    assert datos.puntos_venta[1].es_webservice is False
