"""Tests de extraccion de constancias ARCA."""

import pytest
from httpx import AsyncClient

from app.api import empresas
from app.services.constancia_arca_service import parsear_constancia_arca


def test_parsear_constancia_arca_extrae_datos_del_emisor():
    """Debe extraer datos fiscales principales desde texto de constancia."""
    texto = """
    AGENCIA  DE RECAUDACION Y CONTROL  ADUANERO
    CONST ANCIA DE INSCRIPCION
     FUNDACION ESCUELA  DE GIMNASIA  FEDE MOLINARI  CUIT :  30-71616417-5
    Forma Jurídica:  FUNDACION
    Fecha Contrato Social:  15-09-2017
    GORRITI 133
    BOULOGNE
    1609-BUENOS AIRES
    IMPUEST OS/REGIMENES NACIONALES REGISTRADOS Y FECHA  DE ALTA
    IVA EXENT O 08-2018
    ACTIVIDADES NACIONALES REGISTRADAS Y FECHA  DE ALTA
    Actividad principal: 949990 SERVICIOS Mes de inicio: 08/2018
    """

    datos = parsear_constancia_arca(texto)

    assert datos.razon_social == "FUNDACION ESCUELA DE GIMNASIA FEDE MOLINARI"
    assert datos.cuit == "30716164175"
    assert datos.condicion_iva == "Exento"
    assert datos.domicilio == "GORRITI 133"
    assert datos.localidad == "BOULOGNE"
    assert datos.codigo_postal == "1609"
    assert datos.provincia == "BUENOS AIRES"
    assert datos.inicio_actividades == "2018-08-01"
    assert datos.warnings == []


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
