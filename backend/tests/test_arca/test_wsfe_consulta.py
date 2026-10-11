"""Contrato de lectura de FECompConsultar, sin transporte real."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock
from app.arca.models import ComprobanteRequest, CbteAsocItem
from app.core.comparacion_fiscal import comparar_consulta_fiscal

from tests.test_arca.test_wsfev1 import _crear_cliente_wsfe


def respuesta_soap():
    return SimpleNamespace(
        PtoVta=1,
        CbteTipo=6,
        CbteDesde=42,
        CbteHasta=42,
        Concepto=2,
        CodAutorizacion="00000000000000",
        EmisionTipo="CAE",
        FchVto="20260819",
        CbteFch="20260805",
        FchProceso="20260805120000",
        ImpTotal=Decimal("1.21"),
        ImpNeto=Decimal("1"),
        ImpIVA=Decimal("0.21"),
        ImpOpEx=Decimal("0"),
        ImpTotConc=Decimal("0"),
        ImpTrib=Decimal("0"),
        MonId="DOL",
        MonCotiz=Decimal("1234.123456789012345678901234"),
        DocTipo=99,
        DocNro=0,
        Resultado="A",
        CondicionIVAReceptorId=5,
        FchServDesde="20260801",
        FchServHasta="20260805",
        FchVtoPago="20260810",
        Iva=SimpleNamespace(
            AlicIva=[
                SimpleNamespace(Id=5, BaseImp=Decimal("1"), Importe=Decimal("0.21"))
            ]
        ),
        Tributos=SimpleNamespace(
            Tributo=[
                SimpleNamespace(
                    Id=99,
                    Desc="Sintético",
                    BaseImp=Decimal("1"),
                    Alic=Decimal("1.5"),
                    Importe=Decimal("0.015"),
                )
            ]
        ),
        CbtesAsoc=SimpleNamespace(
            CbteAsoc=[
                SimpleNamespace(
                    Tipo=6, PtoVta=1, Nro=41, Cuit=20999999999, CbteFch="20260801"
                )
            ]
        ),
        PeriodoAsoc=SimpleNamespace(FchDesde="20260801", FchHasta="20260805"),
    )


async def consultar(result):
    class SOAP:
        def FECompConsultar(self, Auth, FeCompConsReq):
            assert FeCompConsReq == {"PtoVta": 1, "CbteTipo": 6, "CbteNro": 42}
            return SimpleNamespace(ResultGet=result, Errors=None)

    return await _crear_cliente_wsfe(SOAP()).fe_comp_consultar(1, 6, 42)


@pytest.mark.asyncio
async def test_consulta_preserva_componentes_y_decimales_sin_cast_float():
    result = respuesta_soap()
    consulta = await consultar(result)
    assert consulta.moneda_cotiz == Decimal("1234.123456789012345678901234")
    assert isinstance(consulta.imp_total, Decimal)
    assert consulta.concepto == 2 and consulta.emision_tipo == "CAE"
    assert consulta.cbte_desde == consulta.cbte_hasta == 42
    assert consulta.condicion_iva_receptor_id == 5
    assert consulta.fecha_serv_desde == "20260801"
    assert consulta.fecha_serv_hasta == "20260805"
    assert consulta.fecha_vto_pago == "20260810"
    assert consulta.iva[0].base_imp == Decimal("1")
    assert consulta.tributos[0].importe == Decimal("0.015")
    assert consulta.cbtes_asoc[0].cuit == "20999999999"
    assert consulta.cbtes_asoc[0].fecha_cbte == "20260801"
    assert consulta.adicionales_presentes == ["PeriodoAsoc"]
    # El contrato HTTP conserva números, sin degradar la evidencia en memoria.
    assert consulta.model_dump(mode="json")["imp_total"] == 1.21
    assert consulta.moneda_cotiz == result.MonCotiz


@pytest.mark.asyncio
async def test_consulta_ausencia_no_agrega_concepto_condicion_ni_iva():
    result = respuesta_soap()
    for campo in (
        "Concepto",
        "CondicionIVAReceptorId",
        "Iva",
        "CbtesAsoc",
        "PeriodoAsoc",
    ):
        delattr(result, campo)
    consulta = await consultar(result)
    assert consulta.concepto is None
    assert consulta.condicion_iva_receptor_id is None
    assert consulta.iva is None and consulta.cbtes_asoc is None
    assert consulta.adicionales_presentes == []


@pytest.mark.asyncio
@pytest.mark.parametrize("campo", ["ImpTotal", "ImpNeto", "MonCotiz"])
async def test_consulta_rechaza_evidencia_decimal_no_finita(campo):
    result = respuesta_soap()
    setattr(result, campo, Decimal("NaN"))
    consulta = await consultar(result)
    assert consulta.cae == "00000000000000"
    assert consulta.campos_invalidos
    assert (
        getattr(
            consulta,
            {
                "ImpTotal": "imp_total",
                "ImpNeto": "imp_neto",
                "MonCotiz": "moneda_cotiz",
            }[campo],
        )
        is None
    )


@pytest.mark.asyncio
async def test_consulta_contenedor_iva_malformado_no_se_toma_por_vacio():
    result = respuesta_soap()
    result.Iva = SimpleNamespace()
    consulta = await consultar(result)
    assert consulta.cae == "00000000000000"
    assert consulta.iva is None and consulta.campos_invalidos == ["iva"]


@pytest.mark.asyncio
@pytest.mark.parametrize("parcial", [False, True])
async def test_consulta_http_conserva_contrato_completo(
    client, auth_headers, monkeypatch, parcial
):
    result = respuesta_soap()
    if parcial:
        delattr(result, "ImpNeto")
    consulta = await consultar(result)
    assert consulta.datos_basicos_completos is (not parcial)
    wsfe = AsyncMock()
    wsfe.fe_comp_consultar.return_value = consulta
    monkeypatch.setattr("app.api.arca.get_wsfe_client", AsyncMock(return_value=wsfe))
    response = await client.get(
        "/api/arca/consultar-comprobante/1/6/42", headers=auth_headers
    )
    assert response.status_code == (500 if parcial else 200)
    if not parcial:
        assert response.json()["imp_total"] == 1.21
    else:
        assert "incompletos" in response.json()["detail"]


@pytest.mark.parametrize("fecha_observada", ["20260801", "20260802"])
def test_asociado_sin_fecha_no_oculta_otro_asociado_con_fecha_distinta(fecha_observada):
    esperado = ComprobanteRequest(
        punto_venta=1,
        tipo_cbte=8,
        concepto=1,
        tipo_doc=99,
        nro_doc=0,
        cbte_desde=1,
        cbte_hasta=1,
        fecha_cbte="20260805",
        imp_total=Decimal("1000"),
        imp_neto=Decimal("1000"),
        imp_iva=Decimal("0"),
        cbtes_asoc=[
            CbteAsocItem(tipo=6, punto_venta=1, numero=9, fecha_cbte="20260801"),
            CbteAsocItem(tipo=6, punto_venta=1, numero=10, fecha_cbte="20260801"),
        ],
    )
    consulta = SimpleNamespace(
        **{campo: getattr(esperado, campo) for campo in type(esperado).model_fields}
    )
    consulta.numero = 1
    consulta.emision_tipo = "CAE"
    consulta.cbtes_asoc = [
        CbteAsocItem(tipo=6, punto_venta=1, numero=9, fecha_cbte=fecha_observada),
        CbteAsocItem(tipo=6, punto_venta=1, numero=10),
    ]
    resultado = comparar_consulta_fiscal(esperado, consulta)
    if fecha_observada == "20260802":
        assert resultado.estado == "diferente"
        assert "cbtes_asoc.fecha_cbte" in resultado.campos
    else:
        assert resultado.estado == "coincidente"
        assert "cbtes_asoc.fecha_cbte" in resultado.cobertura_desconocida
