"""Tests de importación de constancia de puntos de venta ARCA."""

from datetime import date

import pytest
from weasyprint import HTML

from app.services.constancia_puntos_venta_service import (
    ConstanciaPuntosVentaError,
    es_senal_rece_exacta,
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
            P.VTA. SISTEMA DOMICILIO NOMBRE FANTASIA ACTIVIDAD
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
    assert es_senal_rece_exacta(datos.puntos_venta[0].sistema) is True
    assert datos.documento_emitido_en == date(2026, 5, 4)


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
    assert datos.documento_emitido_en == date(2026, 5, 4)


def test_parsear_constancia_rechaza_fecha_documental_invalida() -> None:
    """Una fecha con forma argentina no puede normalizarse silenciosamente."""
    texto = """
    CONSTANCIA DE PUNTOS DE VENTA / EMISION Y DOMICILIOS
    CUIT: ENTIDAD DE PRUEBA 30123456789
    PUNTO VENTA SISTEMA DOMICILIO NOMBRE FANTASIA
    00006 RECE para aplicativo y web services
    FISCAL - 0001 - CALLE FALSA 123 - BUENOS AIRES QA
    31/02/2026
    """

    with pytest.raises(ConstanciaPuntosVentaError, match="fecha documental"):
        parsear_constancia_puntos_venta(texto)


def test_parsear_constancia_rechaza_fechas_documentales_distintas() -> None:
    """Dos fechas válidas distintas no pueden elegir autoridad por posición."""
    texto = """
    CONSTANCIA DE PUNTOS DE VENTA / EMISION Y DOMICILIOS
    CUIT: ENTIDAD DE PRUEBA 30123456789
    PUNTO VENTA SISTEMA DOMICILIO NOMBRE FANTASIA
    00006 RECE para aplicativo y web services
    FISCAL - 0001 - CALLE FALSA 123 - BUENOS AIRES QA
    08/08/2026
    09/08/2026
    """

    with pytest.raises(
        ConstanciaPuntosVentaError, match="fechas documentales ambiguas"
    ):
        parsear_constancia_puntos_venta(texto)


def test_parsear_constancia_omite_punto_cero_con_warning() -> None:
    """El valor 00000 no puede convertirse en una identidad fiscal durable."""
    texto = """
    CONSTANCIA DE PUNTOS DE VENTA / EMISION Y DOMICILIOS
    CUIT: ENTIDAD DE PRUEBA 30123456789
    PUNTO VENTA SISTEMA DOMICILIO NOMBRE FANTASIA
    00000 RECE para aplicativo y web services
    FISCAL - 0001 - CALLE CERO 100 - BUENOS AIRES QA
    00001 RECE para aplicativo y web services
    FISCAL - 0001 - CALLE UNO 101 - BUENOS AIRES QA
    09/08/2026
    """

    datos = parsear_constancia_puntos_venta(texto)

    assert [punto.numero for punto in datos.puntos_venta] == [1]
    assert len(datos.warnings) == 1
    assert "entre 1 y 99999" in datos.warnings[0]


def test_parsear_constancia_multipagina_con_encabezado_actual() -> None:
    """Cada página conserva sus filas sin incorporar encabezados ni pies."""
    texto = """
    CONSTANCIA DE PUNTOS DE VENTA / EMISION Y DOMICILIOS
    CUIT: ENTIDAD DE PRUEBA 30123456789
    P.VTA. SISTEMA DOMICILIO NOMBRE FANTASIA ACTIVIDAD
    00006 Factura Electrónica - Exento en IVA - Web Services
    FISCAL - 0001 - CALLE UNO 100 - BUENOS AIRES SEDE UNO
    09/08/2026 Página 1 de 2
    CONSTANCIA DE PUNTOS DE VENTA / EMISION Y DOMICILIOS
    P.VTA. SISTEMA DOMICILIO NOMBRE FANTASIA ACTIVIDAD
    00007 Factura Electrónica - Monotributo - Webservices
    FISCAL - 0002 - CALLE DOS 200 - BUENOS AIRES SEDE DOS
    09/08/2026 Página 2 de 2
    """

    datos = parsear_constancia_puntos_venta(texto)

    assert [punto.numero for punto in datos.puntos_venta] == [6, 7]
    assert [punto.nombre_fantasia for punto in datos.puntos_venta] == [
        "SEDE UNO",
        "SEDE DOS",
    ]
    assert all(es_senal_rece_exacta(punto.sistema) for punto in datos.puntos_venta)
    assert datos.documento_emitido_en == date(2026, 8, 9)


@pytest.mark.parametrize(
    ("sistema", "esperado"),
    [
        ("RECE para aplicativo y web services", True),
        ("  RECE   para aplicativo y web services  ", True),
        ("Factura Electrónica - RI IVA - Aplicativo y Webservices", True),
        ("Factura Electrónica - Exento en IVA - Web Services", True),
        ("Factura Electrónica – Monotributo – Web Services", True),
        ("Web Services", False),
        ("Factura electrónica - Web Services", False),
        ("Factura Electrónica - Exento en IVA - Comprobantes en Línea", False),
        ("Factuweb (Imprenta) - Exento en IVA", False),
        ("Controlador Fiscal", False),
        ("RECE para aplicativo y web services adicional", False),
        ("", False),
    ],
)
def test_clasificador_rece_solo_admite_senales_exactas_versionadas(
    sistema: str,
    esperado: bool,
) -> None:
    """Sinónimos y coincidencias parciales deben fallar cerrado."""
    assert es_senal_rece_exacta(sistema) is esperado
