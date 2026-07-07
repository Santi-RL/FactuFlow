"""Tests del cliente WSFEv1."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.arca.exceptions import ArcaServiceError, ArcaValidationError
from app.arca.models import ComprobanteRequest, TicketAcceso
from app.arca.wsfev1 import WSFEv1Client


def _crear_cliente_wsfe(service) -> WSFEv1Client:
    """Crea un cliente WSFE sin instanciar transporte SOAP real."""
    client = object.__new__(WSFEv1Client)
    client.ticket = TicketAcceso(
        token="token",
        sign="sign",
        expiracion=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    client.cuit = "20123456789"
    client.client = SimpleNamespace(service=service)
    return client


def _comprobante(numero: int = 1, punto_venta: int = 1, tipo: int = 6):
    """Construye un request ARCA mínimo para pruebas."""
    return ComprobanteRequest(
        punto_venta=punto_venta,
        tipo_cbte=tipo,
        concepto=1,
        tipo_doc=99,
        nro_doc=0,
        cbte_desde=numero,
        cbte_hasta=numero,
        fecha_cbte="20260601",
        imp_total=1000,
        imp_tot_conc=0,
        imp_neto=1000,
        imp_op_ex=0,
        imp_iva=0,
        imp_trib=0,
        moneda_id="PES",
        moneda_cotiz=1,
    )


@pytest.mark.asyncio
async def test_fe_comp_tot_x_request_parsea_reg_x_req():
    """FECompTotXRequest devuelve el máximo RegXReq informado por ARCA."""

    class FakeService:
        """Servicio SOAP simulado."""

        def FECompTotXRequest(self, Auth):
            """Devuelve un máximo de registros simulado."""
            return SimpleNamespace(RegXReq=250)

    client = _crear_cliente_wsfe(FakeService())

    assert await client.fe_comp_tot_x_request() == 250


@pytest.mark.asyncio
async def test_fe_cae_solicitar_lote_envia_cant_reg_y_detalles():
    """FECAESolicitar por lote informa CantReg y un detalle por comprobante."""

    class FakeService:
        """Servicio SOAP simulado que captura el request."""

        def __init__(self) -> None:
            """Inicializa el registro de llamadas."""
            self.request = None

        def FECAESolicitar(self, Auth, FeCAEReq):
            """Captura el request y devuelve dos CAE simulados."""
            self.request = FeCAEReq
            detalles = [
                SimpleNamespace(
                    CAE="12345678901231",
                    CAEFchVto="20260610",
                    CbteDesde=1,
                    CbteHasta=1,
                    Resultado="A",
                ),
                SimpleNamespace(
                    CAE="12345678901232",
                    CAEFchVto="20260610",
                    CbteDesde=2,
                    CbteHasta=2,
                    Resultado="A",
                ),
            ]
            return SimpleNamespace(FeDetResp=SimpleNamespace(FECAEDetResponse=detalles))

    service = FakeService()
    client = _crear_cliente_wsfe(service)

    resultados = await client.fe_cae_solicitar_lote([_comprobante(1), _comprobante(2)])

    assert service.request["FeCabReq"]["CantReg"] == 2
    assert service.request["FeCabReq"]["PtoVta"] == 1
    assert service.request["FeCabReq"]["CbteTipo"] == 6
    detalles_request = service.request["FeDetReq"]["FECAEDetRequest"]
    assert [detalle["CbteDesde"] for detalle in detalles_request] == [1, 2]
    assert [resultado.cae for resultado in resultados] == [
        "12345678901231",
        "12345678901232",
    ]


@pytest.mark.asyncio
async def test_fe_cae_solicitar_lote_ordena_detalles_por_numero():
    """Debe asociar respuestas batch por CbteDesde, no por posición."""

    class FakeService:
        """Servicio SOAP simulado que devuelve detalles fuera de orden."""

        def FECAESolicitar(self, Auth, FeCAEReq):
            """Devuelve CAE en orden inverso al solicitado."""
            detalles = [
                SimpleNamespace(
                    CAE="12345678901232",
                    CAEFchVto="20260610",
                    CbteDesde=2,
                    CbteHasta=2,
                    Resultado="A",
                ),
                SimpleNamespace(
                    CAE="12345678901231",
                    CAEFchVto="20260610",
                    CbteDesde=1,
                    CbteHasta=1,
                    Resultado="A",
                ),
            ]
            return SimpleNamespace(FeDetResp=SimpleNamespace(FECAEDetResponse=detalles))

    client = _crear_cliente_wsfe(FakeService())

    resultados = await client.fe_cae_solicitar_lote([_comprobante(1), _comprobante(2)])

    assert [resultado.numero_comprobante for resultado in resultados] == [1, 2]
    assert [resultado.cae for resultado in resultados] == [
        "12345678901231",
        "12345678901232",
    ]


@pytest.mark.asyncio
async def test_fe_cae_solicitar_lote_rechaza_numeros_no_solicitados():
    """Debe rechazar detalles ARCA que no coinciden con los números pedidos."""

    class FakeService:
        """Servicio SOAP simulado con un CbteDesde inesperado."""

        def FECAESolicitar(self, Auth, FeCAEReq):
            """Devuelve un detalle para un número no solicitado."""
            detalles = [
                SimpleNamespace(
                    CAE="12345678901232",
                    CAEFchVto="20260610",
                    CbteDesde=2,
                    CbteHasta=2,
                    Resultado="A",
                ),
                SimpleNamespace(
                    CAE="12345678901233",
                    CAEFchVto="20260610",
                    CbteDesde=3,
                    CbteHasta=3,
                    Resultado="A",
                ),
            ]
            return SimpleNamespace(FeDetResp=SimpleNamespace(FECAEDetResponse=detalles))

    client = _crear_cliente_wsfe(FakeService())

    with pytest.raises(ArcaServiceError, match="números distintos"):
        await client.fe_cae_solicitar_lote([_comprobante(1), _comprobante(2)])


@pytest.mark.asyncio
async def test_fe_cae_solicitar_lote_rechaza_detalle_sin_cbte_hasta():
    """Debe rechazar respuestas batch sin extremo final de rango fiscal."""

    class FakeService:
        """Servicio SOAP simulado sin CbteHasta en el detalle."""

        def FECAESolicitar(self, Auth, FeCAEReq):
            """Devuelve un detalle incompleto."""
            detalles = [
                SimpleNamespace(
                    CAE="12345678901231",
                    CAEFchVto="20260610",
                    CbteDesde=1,
                    Resultado="A",
                ),
            ]
            return SimpleNamespace(FeDetResp=SimpleNamespace(FECAEDetResponse=detalles))

    client = _crear_cliente_wsfe(FakeService())

    with pytest.raises(ArcaServiceError, match="sin CbteHasta"):
        await client.fe_cae_solicitar_lote([_comprobante(1)])


@pytest.mark.asyncio
async def test_fe_cae_solicitar_lote_rechaza_cbte_hasta_distinto():
    """Debe rechazar CAE si ARCA responde un rango fiscal distinto."""

    class FakeService:
        """Servicio SOAP simulado con CbteHasta inesperado."""

        def FECAESolicitar(self, Auth, FeCAEReq):
            """Devuelve un detalle con extremo final no solicitado."""
            detalles = [
                SimpleNamespace(
                    CAE="12345678901231",
                    CAEFchVto="20260610",
                    CbteDesde=1,
                    CbteHasta=999,
                    Resultado="A",
                ),
            ]
            return SimpleNamespace(FeDetResp=SimpleNamespace(FECAEDetResponse=detalles))

    client = _crear_cliente_wsfe(FakeService())

    with pytest.raises(ArcaServiceError, match="rangos distintos"):
        await client.fe_cae_solicitar_lote([_comprobante(1)])


@pytest.mark.asyncio
async def test_fe_cae_solicitar_lote_rechaza_punto_o_tipo_mixto():
    """Un request WSFE batch no puede mezclar punto de venta o tipo."""
    client = _crear_cliente_wsfe(SimpleNamespace())

    with pytest.raises(ArcaValidationError, match="mismo punto de venta y tipo"):
        await client.fe_cae_solicitar_lote(
            [_comprobante(1, punto_venta=1), _comprobante(2, punto_venta=2)]
        )
