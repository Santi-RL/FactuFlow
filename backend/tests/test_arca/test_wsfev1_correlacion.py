"""SC-09: respuestas SOAP sintéticas correlacionadas, sin transporte real."""

from types import SimpleNamespace

import pytest

from app.arca.exceptions import ArcaServiceError
from tests.test_arca.test_wsfev1 import _comprobante, _crear_cliente_wsfe


def _respuesta(requests, resultados=None):
    resultados = resultados or ["A"] * len(requests)
    detalles = [
        SimpleNamespace(
            Concepto=r.concepto,
            DocTipo=r.tipo_doc,
            DocNro=r.nro_doc,
            CbteFch=r.fecha_cbte,
            CbteDesde=r.cbte_desde,
            CbteHasta=r.cbte_hasta,
            Resultado=resultado,
            CAE="12345678901234" if resultado == "A" else None,
            CAEFchVto="20260610" if resultado == "A" else None,
        )
        for r, resultado in zip(requests, resultados)
    ]
    resumen = resultados[0] if len(set(resultados)) == 1 else "P"
    return SimpleNamespace(
        FeCabResp=SimpleNamespace(
            Cuit=20123456789,
            PtoVta=requests[0].punto_venta,
            CbteTipo=requests[0].tipo_cbte,
            CantReg=len(requests),
            Resultado=resumen,
        ),
        FeDetResp=SimpleNamespace(FECAEDetResponse=detalles),
    )


def _cliente(response):
    return _crear_cliente_wsfe(
        SimpleNamespace(FECAESolicitar=lambda **kwargs: response)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("campo", ["Cuit", "PtoVta", "CbteTipo", "CantReg"])
@pytest.mark.parametrize("valor", [None, -1, True, "1", 1.5])
async def test_sc09_cabecera_no_correlacionada_es_incierta(batch, campo, valor):
    requests = [_comprobante(1)] + ([_comprobante(2)] if batch else [])
    response = _respuesta(requests)
    setattr(response.FeCabResp, campo, valor)
    client = _cliente(response)
    with pytest.raises(ArcaServiceError):
        if batch:
            await client.fe_cae_solicitar_lote(requests)
        else:
            await client.fe_cae_solicitar(requests[0])


@pytest.mark.asyncio
async def test_sc09_cabecera_ausente_no_acredita_autorizacion():
    response = _respuesta([_comprobante()])
    del response.FeCabResp
    with pytest.raises(ArcaServiceError):
        await _cliente(response).fe_cae_solicitar(_comprobante())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "campo,valor",
    [(campo, None) for campo in ("Concepto", "DocTipo", "DocNro")]
    + [("Concepto", 2), ("DocTipo", 80), ("DocNro", 1), ("CbteFch", "20260602")]
    + [("CbteDesde", True), ("CbteHasta", 1.5)],
)
async def test_sc09_detalle_ajeno_no_se_asocia_por_posicion(campo, valor):
    requests = [_comprobante(1), _comprobante(2)]
    response = _respuesta(requests)
    setattr(response.FeDetResp.FECAEDetResponse[0], campo, valor)
    response.FeDetResp.FECAEDetResponse.reverse()
    with pytest.raises(ArcaServiceError):
        await _cliente(response).fe_cae_solicitar_lote(requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("resumen", [None, "", "X", "a", True])
async def test_sc09_resultado_global_invalido_no_es_terminal(resumen):
    response = _respuesta([_comprobante()])
    response.FeCabResp.Resultado = resumen
    with pytest.raises(ArcaServiceError):
        await _cliente(response).fe_cae_solicitar(_comprobante())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resultados,resumen",
    [(["A", "A"], "R"), (["A", "R"], "A"), (["R", "R"], "P"), (["A", "A"], "P")],
)
async def test_sc09_resumen_contradictorio_preserva_cae_correlacionado(
    resultados, resumen
):
    requests = [_comprobante(1), _comprobante(2)]
    response = _respuesta(requests, resultados)
    response.FeCabResp.Resultado = resumen
    parsed = await _cliente(response).fe_cae_solicitar_lote(requests)
    assert all(r.requiere_reconciliacion for r in parsed)
    assert [r.cae for r in parsed] == [
        d.CAE for d in response.FeDetResp.FECAEDetResponse
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("campo", ["CAE", "CAEFchVto"])
async def test_sc09_rechazo_con_senal_cae_inmoviliza_todo_el_sublote(campo):
    requests = [_comprobante(1), _comprobante(2)]
    response = _respuesta(requests, ["A", "R"])
    setattr(
        response.FeDetResp.FECAEDetResponse[1],
        campo,
        "12345678901235" if campo == "CAE" else "20260610",
    )
    parsed = await _cliente(response).fe_cae_solicitar_lote(requests)
    assert all(r.requiere_reconciliacion for r in parsed)
    assert parsed[0].cae == "12345678901234"
    assert parsed[1].resultado == "R"


@pytest.mark.asyncio
@pytest.mark.parametrize("resultados", [["A"], ["R"], ["A", "R"], ["A", "A"]])
async def test_sc09_respuesta_coherente_preserva_contrato(resultados):
    requests = [_comprobante(i + 1) for i in range(len(resultados))]
    response = _respuesta(requests, resultados)
    response.FeDetResp.FECAEDetResponse.reverse()
    parsed = await _cliente(response).fe_cae_solicitar_lote(requests)
    assert [r.resultado for r in parsed] == resultados
    assert not any(r.requiere_reconciliacion for r in parsed)


@pytest.mark.asyncio
@pytest.mark.parametrize("resultados", [["A"], ["R"], ["A", "R"]])
async def test_sc09_fecha_opcional_ausente_preserva_respuesta_legitima(resultados):
    requests = [_comprobante(i + 1) for i in range(len(resultados))]
    response = _respuesta(requests, resultados)
    for detalle in response.FeDetResp.FECAEDetResponse:
        detalle.CbteFch = None
    parsed = await _cliente(response).fe_cae_solicitar_lote(requests)
    assert [r.resultado for r in parsed] == resultados
    assert not any(r.requiere_reconciliacion for r in parsed)


def test_sc09_parser_legacy_no_convierte_contradiccion_en_validacion():
    request = _comprobante()
    response = _respuesta([request], ["R"])
    response.FeDetResp.FECAEDetResponse[0].CAE = "12345678901234"
    with pytest.raises(ArcaServiceError):
        _cliente(response)._parse_cae_response(response, request)
