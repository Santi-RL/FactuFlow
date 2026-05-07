"""Tests de importacion de constancia de puntos de venta ARCA."""

from app.services.constancia_puntos_venta_service import parsear_constancia_puntos_venta


def test_parsear_constancia_puntos_venta() -> None:
    texto = """
    CONSTANCIA DE PUNTOS DE VENTA / EMISION Y DOMICILIOS
    CUIT:FUNDACION ESCUELA DE GIMNASIA FEDE MOLINARI
    30716164175
    PUNTO VENTA SISTEMA DOMICILIO NOMBRE FANTASIA
    00006 Factura Electrónica -
    Exento en IVA - Web
    ServicesLOCALES Y ESTABLECIMIENTOS - 0002 - AV. ANGEL
    T. DE ALVEAR 2100 - DON TORCUATO NORTE -
    BUENOS AIRESFM GYMNASTICS
    00007 Factuweb  (Imprenta) -
    Exento en IVAFISCAL - 0001 - GORRITI 133 - BOULOGNE - BUENOS
    AIRESFM GYMNASTICS
    04/5/2026 7:59:00 PM
    """

    datos = parsear_constancia_puntos_venta(texto)

    assert datos.cuit == "30716164175"
    assert len(datos.puntos_venta) == 2
    assert datos.puntos_venta[0].numero == 6
    assert datos.puntos_venta[0].es_webservice is True
    assert datos.puntos_venta[0].nombre_fantasia == "FM GYMNASTICS"
    assert "AV. ANGEL T. DE ALVEAR" in datos.puntos_venta[0].domicilio
    assert datos.puntos_venta[1].numero == 7
    assert datos.puntos_venta[1].es_webservice is False
