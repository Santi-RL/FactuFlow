"""Tests de extraccion de constancias ARCA."""

import pytest
from httpx import AsyncClient

from app.api import empresas
from app.schemas.empresa import EmpresaCreate
from app.services import constancia_arca_service
from app.services.constancia_arca_service import parsear_constancia_arca


def test_parsear_constancia_arca_extrae_datos_del_emisor():
    """Debe extraer datos fiscales principales desde texto de constancia."""
    texto = """
    AGENCIA  DE RECAUDACION Y CONTROL  ADUANERO
    CONST ANCIA DE INSCRIPCION
     ENTIDAD  DE  PRUEBA  SIN  DATOS  REALES  CUIT :  30-12345678-9
    Forma Jurídica:  ASOCIACION
    Fecha Contrato Social:  15-09-2017
    CALLE FALSA 123
    CIUDAD DE PRUEBA
    1609-BUENOS AIRES
    IMPUEST OS/REGIMENES NACIONALES REGISTRADOS Y FECHA  DE ALTA
    IVA EXENT O 08-2018
    ACTIVIDADES NACIONALES REGISTRADAS Y FECHA  DE ALTA
    Actividad principal: 949990 SERVICIOS Mes de inicio: 08/2018
    """

    datos = parsear_constancia_arca(texto)

    assert datos.razon_social == "ENTIDAD DE PRUEBA SIN DATOS REALES"
    assert datos.cuit == "30123456789"
    assert datos.condicion_iva == "Exento"
    assert datos.domicilio == "CALLE FALSA 123"
    assert datos.localidad == "CIUDAD DE PRUEBA"
    assert datos.codigo_postal == "1609"
    assert datos.provincia == "Buenos Aires"
    assert datos.inicio_actividades == "2018-08-01"
    assert datos.warnings == []


def test_parsear_constancia_opcion_monotributo_extrae_datos_del_emisor():
    """Debe extraer datos desde constancias de opcion monotributo."""
    texto = """
    CUIT:  27-12345678-5
    CONTRIBUYENTE DE PRUEBA
    RIVADAVIA 286
    JOSE CLEMENTE PAZ
    1665-BUENOS AIRES

    CONSTANCIA DE OPCIÓN
    Régimen Simplificado para Pequeños Contribuyentes

    020 - MONOTRIBUTO
    CATEGORÍA
    F
    LOCACIONES DE SERVICIOS
    FECHA DE INICIO: 01-05-2025
    ACTIVIDAD: F883 - 960202 - SERVICIOS DE TRATAMIENTO DE BELLEZA
    """

    datos = parsear_constancia_arca(texto)

    assert datos.razon_social == "CONTRIBUYENTE DE PRUEBA"
    assert datos.cuit == "27123456785"
    assert datos.condicion_iva == "Monotributo"
    assert datos.domicilio == "RIVADAVIA 286"
    assert datos.localidad == "JOSE CLEMENTE PAZ"
    assert datos.codigo_postal == "1665"
    assert datos.provincia == "Buenos Aires"
    assert datos.inicio_actividades == "2025-05-01"
    assert datos.warnings == []


def test_parsear_constancia_inscripcion_persona_fisica_extrae_domicilio():
    """Debe soportar constancias de inscripcion de persona fisica."""
    texto = """
    AGENCIA  DE RECAUDACION Y CONTROL  ADUANERO
    CONST ANCIA DE INSCRIPCION
     PERSONA  DE  PRUEBA  MA TIAS CUIT :  20-12345678-3
    CARLOS CASARES 31 10
    VICT ORIA
    1644-BUENOS AIRES
    IMPUEST OS/REGIMENES NACIONALES REGISTRADOS Y FECHA  DE ALTA
    GANANCIAS PERSONAS FISICAS 07-2025
    IVA 07-2025
    ACTIVIDADES NACIONALES REGISTRADAS Y FECHA  DE ALTA
    Actividad principal: 561014 SERVICIOS Mes de inicio: 07/2025
    DOMICILIO FISCAL  - ARCA
    """

    datos = parsear_constancia_arca(texto)

    assert datos.razon_social == "PERSONA DE PRUEBA MATIAS"
    assert datos.cuit == "20123456783"
    assert datos.condicion_iva == "RI"
    assert datos.domicilio == "CARLOS CASARES 3110"
    assert datos.localidad == "VICTORIA"
    assert datos.codigo_postal == "1644"
    assert datos.provincia == "Buenos Aires"
    assert datos.inicio_actividades == "2025-07-01"
    assert datos.warnings == []


def test_parsear_constancia_no_completa_provincia_contaminada():
    """No debe usar lineas tecnicas como provincia."""
    texto = """
    AGENCIA  DE RECAUDACION Y CONTROL  ADUANERO
    CONST ANCIA DE INSCRIPCION
     PERSONA  DE  PRUEBA  CUIT :  20-12345678-3
    CALLE FALSA 123
    CIUDAD DE PRUEBA
    1644-IMPUEST OS/REGIMENES NACIONALES REGISTRADOS
    IMPUEST OS/REGIMENES NACIONALES REGISTRADOS Y FECHA  DE ALTA
    IVA 07-2025
    Actividad principal: 561014 SERVICIOS Mes de inicio: 07/2025
    """

    datos = parsear_constancia_arca(texto)

    assert datos.provincia is None
    assert "No se pudo detectar provincia." in datos.warnings


def test_empresa_create_normaliza_provincia():
    """Debe normalizar provincia al crear emisores."""
    empresa = EmpresaCreate(
        razon_social="ENTIDAD DE PRUEBA",
        cuit="30123456789",
        condicion_iva="RI",
        domicilio="CALLE FALSA 123",
        localidad="CIUDAD DE PRUEBA",
        provincia="BUENOS AIRES",
        codigo_postal="1609",
        inicio_actividades="2025-01-01",
    )

    assert empresa.provincia == "Buenos Aires"


def test_empresa_create_rechaza_provincia_invalida():
    """Debe rechazar provincias que no pertenezcan al catalogo argentino."""
    with pytest.raises(ValueError):
        EmpresaCreate(
            razon_social="ENTIDAD DE PRUEBA",
            cuit="30123456789",
            condicion_iva="RI",
            domicilio="CALLE FALSA 123",
            localidad="CIUDAD DE PRUEBA",
            provincia="IMPUESTOS/REGIMENES",
            codigo_postal="1609",
            inicio_actividades="2025-01-01",
        )


def test_extraer_texto_acepta_constancia_opcion_monotributo(
    monkeypatch: pytest.MonkeyPatch,
):
    """Debe aceptar PDFs de constancia de opcion monotributo."""

    class FakePage:
        def extract_text(self) -> str:
            return """
            CONSTANCIA DE OPCIÓN
            Régimen Simplificado para Pequeños Contribuyentes
            CUIT: 27-12345678-5
            """

    class FakeReader:
        def __init__(self, _stream):
            self.pages = [FakePage()]

    monkeypatch.setattr(constancia_arca_service, "PdfReader", FakeReader)

    texto = constancia_arca_service.extraer_texto_constancia_pdf(b"%PDF-test")

    assert "CONSTANCIA DE OPCIÓN" in texto


@pytest.mark.asyncio
async def test_extraer_constancia_endpoint_devuelve_datos_detectados(
    client: AsyncClient, admin_auth_headers: dict, monkeypatch: pytest.MonkeyPatch
):
    """El endpoint debe exponer los datos parseados sin crear el emisor."""

    def fake_extraer_texto(_contenido: bytes) -> str:
        return "CONSTANCIA DE INSCRIPCION TEST CUIT: 20-12345678-9"

    def fake_parsear(_texto: str):
        return type(
            "Datos",
            (),
            {
                "to_dict": lambda self: {
                    "razon_social": "TEST",
                    "cuit": "20123456789",
                    "condicion_iva": "RI",
                    "domicilio": "CALLE 1",
                    "localidad": "CABA",
                    "provincia": "BUENOS AIRES",
                    "codigo_postal": "1000",
                    "inicio_actividades": "2020-01-01",
                    "warnings": [],
                }
            },
        )()

    monkeypatch.setattr(empresas, "extraer_texto_constancia_pdf", fake_extraer_texto)
    monkeypatch.setattr(empresas, "parsear_constancia_arca", fake_parsear)

    response = await client.post(
        "/api/empresas/extraer-constancia",
        headers=admin_auth_headers,
        files={"file": ("constancia.pdf", b"%PDF-test", "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["razon_social"] == "TEST"
    assert data["cuit"] == "20123456789"
