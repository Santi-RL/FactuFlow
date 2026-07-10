"""Tests del cliente WSFEv1."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.arca.exceptions import ArcaServiceError, ArcaValidationError
from app.arca.models import ComprobanteRequest, IvaItem, TicketAcceso, TributoItem
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


def _comprobante(
    numero: int = 1,
    punto_venta: int = 1,
    tipo: int = 6,
    concepto: int = 1,
    fecha_cbte: str = "20260601",
    **extra,
):
    """Construye un request ARCA mínimo para pruebas."""
    return ComprobanteRequest(
        punto_venta=punto_venta,
        tipo_cbte=tipo,
        concepto=concepto,
        tipo_doc=99,
        nro_doc=0,
        cbte_desde=numero,
        cbte_hasta=numero,
        fecha_cbte=fecha_cbte,
        imp_total=1000,
        imp_tot_conc=0,
        imp_neto=1000,
        imp_op_ex=0,
        imp_iva=0,
        imp_trib=0,
        moneda_id="PES",
        moneda_cotiz=1,
        **extra,
    )


def test_comprobante_request_preserva_importes_decimal():
    """Debe conservar Decimal en los modelos internos que llegan a WSFE."""
    comprobante = ComprobanteRequest(
        punto_venta=1,
        tipo_cbte=6,
        concepto=1,
        tipo_doc=99,
        nro_doc=0,
        cbte_desde=1,
        cbte_hasta=1,
        fecha_cbte="20260601",
        imp_total=Decimal("2.675"),
        imp_tot_conc=Decimal("1.005"),
        imp_neto=Decimal("2.675"),
        imp_op_ex=Decimal("1.005"),
        imp_iva=Decimal("1.005"),
        imp_trib=Decimal("2.675"),
        moneda_id="PES",
        moneda_cotiz=Decimal("1.2345"),
        iva=[IvaItem(id=5, base_imp=Decimal("2.675"), importe=Decimal("1.005"))],
        tributos=[
            TributoItem(
                id=99,
                descripcion="Prueba",
                base_imp=Decimal("2.675"),
                alic=Decimal("1.5"),
                importe=Decimal("1.005"),
            )
        ],
    )

    assert comprobante.imp_total == Decimal("2.675")
    assert comprobante.imp_tot_conc == Decimal("1.005")
    assert comprobante.imp_neto == Decimal("2.675")
    assert comprobante.imp_op_ex == Decimal("1.005")
    assert comprobante.imp_iva == Decimal("1.005")
    assert comprobante.imp_trib == Decimal("2.675")
    assert comprobante.moneda_cotiz == Decimal("1.2345")
    assert comprobante.iva[0].base_imp == Decimal("2.675")
    assert comprobante.iva[0].importe == Decimal("1.005")
    assert comprobante.tributos[0].base_imp == Decimal("2.675")
    assert comprobante.tributos[0].alic == Decimal("1.5")
    assert comprobante.tributos[0].importe == Decimal("1.005")


def test_comprobante_request_rechaza_fecha_calendario_invalida():
    """No debe aceptar CbteFch con día o mes imposible."""
    with pytest.raises(ValueError):
        _comprobante(fecha_cbte="20260231")


def test_comprobante_request_exige_fechas_servicio_para_servicios():
    """Los conceptos de servicio requieren período y vencimiento."""
    with pytest.raises(ValueError, match="fechas de servicio"):
        _comprobante(concepto=2)


def test_comprobante_request_normaliza_fechas_servicio_argentinas():
    """Debe convertir fechas argentinas a YYYYMMDD antes de WSFE."""
    comprobante = _comprobante(
        concepto=2,
        fecha_serv_desde="01/06/2026",
        fecha_serv_hasta="30/06/2026",
        fecha_vto_pago="10/07/2026",
    )

    assert comprobante.fecha_serv_desde == "20260601"
    assert comprobante.fecha_serv_hasta == "20260630"
    assert comprobante.fecha_vto_pago == "20260710"


@pytest.mark.asyncio
async def test_fe_comp_consultar_acepta_cbte_nro_sin_cbte_desde():
    """FECompConsultar no debe evaluar un fallback ausente si existe CbteNro."""

    class FakeService:
        """Servicio SOAP simulado con el número canónico de consulta."""

        def FECompConsultar(self, Auth, FeCompConsReq):
            """Devuelve un comprobante sin el atributo alternativo CbteDesde."""
            result = SimpleNamespace(
                PtoVta=1,
                CbteTipo=6,
                CbteNro=42,
                CuitEmisor="20123456789",
                CodAutorizacion="12345678901234",
                FchVto="20260610",
                CbteFch="20260601",
                FchProceso="20260601120000",
                ImpTotal=Decimal("1000.00"),
                ImpNeto=Decimal("1000.00"),
                ImpIVA=Decimal("0.00"),
                ImpOpEx=Decimal("0.00"),
                ImpTotConc=Decimal("0.00"),
                ImpTrib=Decimal("0.00"),
                MonId="PES",
                MonCotiz=Decimal("1.00"),
                DocTipo=99,
                DocNro=0,
                Resultado="A",
            )
            return SimpleNamespace(ResultGet=result, Errors=None)

    client = _crear_cliente_wsfe(FakeService())

    resultado = await client.fe_comp_consultar(1, 6, 42)

    assert resultado.numero == 42


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
async def test_fe_cae_solicitar_rechaza_resultado_parcial():
    """La variante individual solo retorna cuando el detalle está aprobado."""

    class FakeService:
        """Servicio SOAP simulado con resultado parcial sin CAE utilizable."""

        def FECAESolicitar(self, Auth, FeCAEReq):
            """Devuelve un detalle parcial para el comprobante solicitado."""
            detalle = SimpleNamespace(
                CAE=None,
                CAEFchVto=None,
                CbteDesde=1,
                CbteHasta=1,
                Resultado="P",
            )
            return SimpleNamespace(
                FeDetResp=SimpleNamespace(FECAEDetResponse=[detalle]),
                Errors=None,
            )

    client = _crear_cliente_wsfe(FakeService())

    with pytest.raises(ArcaValidationError, match="resultado P"):
        await client.fe_cae_solicitar(_comprobante())


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
async def test_fe_cae_solicitar_lote_cuantiza_importes_decimales():
    """Debe cuantizar importes fiscales con Decimal antes del request ARCA."""

    class FakeService:
        """Servicio SOAP simulado que captura importes del request."""

        def __init__(self) -> None:
            """Inicializa el registro de llamadas."""
            self.detalle = None

        def FECAESolicitar(self, Auth, FeCAEReq):
            """Captura el detalle y devuelve un CAE simulado."""
            self.detalle = FeCAEReq["FeDetReq"]["FECAEDetRequest"][0]
            detalle = SimpleNamespace(
                CAE="12345678901231",
                CAEFchVto="20260610",
                CbteDesde=1,
                CbteHasta=1,
                Resultado="A",
            )
            return SimpleNamespace(
                FeDetResp=SimpleNamespace(FECAEDetResponse=[detalle])
            )

    service = FakeService()
    client = _crear_cliente_wsfe(service)
    comprobante = _comprobante()
    comprobante.imp_total = Decimal("2.675")
    comprobante.imp_tot_conc = Decimal("1.005")
    comprobante.imp_neto = Decimal("2.675")
    comprobante.imp_op_ex = Decimal("1.005")
    comprobante.imp_iva = Decimal("1.005")
    comprobante.imp_trib = Decimal("2.675")
    comprobante.iva = [
        IvaItem(id=5, base_imp=Decimal("2.675"), importe=Decimal("1.005"))
    ]
    comprobante.tributos = [
        TributoItem(
            id=99,
            descripcion="Prueba",
            base_imp=Decimal("2.675"),
            alic=Decimal("1.5"),
            importe=Decimal("1.005"),
        )
    ]

    await client.fe_cae_solicitar_lote([comprobante])

    assert service.detalle["ImpTotal"] == Decimal("2.68")
    assert service.detalle["ImpTotConc"] == Decimal("1.01")
    assert service.detalle["ImpNeto"] == Decimal("2.68")
    assert service.detalle["ImpOpEx"] == Decimal("1.01")
    assert service.detalle["ImpIVA"] == Decimal("1.01")
    assert service.detalle["ImpTrib"] == Decimal("2.68")
    assert service.detalle["Iva"]["AlicIva"][0]["BaseImp"] == Decimal("2.68")
    assert service.detalle["Iva"]["AlicIva"][0]["Importe"] == Decimal("1.01")
    assert service.detalle["Tributos"]["Tributo"][0]["BaseImp"] == Decimal("2.68")
    assert service.detalle["Tributos"]["Tributo"][0]["Importe"] == Decimal("1.01")


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
