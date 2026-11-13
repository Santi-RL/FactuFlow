"""Notas individuales con originales sintéticos; ninguna llamada fiscal real."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.arca.models import ComprobanteResponse, IvaItem
from app.schemas.comprobante import EmitirComprobanteRequest, PreparacionNotaResponse
from app.services.facturacion_service import FacturacionService, ValidationError
from app.services.notas_service import NotasService
from tests.test_lecturas_historicas import crear_historia


def consulta(tipo=6, **cambios):
    datos = dict(
        punto_venta=4,
        tipo_cbte=tipo,
        numero=12,
        cuit_emisor="20123456789",
        cae="12345678901234",
        cae_vencimiento="20260818",
        fecha_cbte="20260809",
        fecha_proceso="20260809120000",
        imp_total=Decimal("121"),
        imp_neto=Decimal("100"),
        imp_iva=Decimal("21"),
        imp_op_ex=Decimal("0"),
        imp_tot_conc=Decimal("0"),
        imp_trib=Decimal("0"),
        moneda_id="PES",
        moneda_cotiz=Decimal("1"),
        tipo_doc=96,
        nro_doc=12345678,
        resultado="A",
        concepto=1,
        condicion_iva_receptor_id=5,
        iva=[IvaItem(id=5, base_imp=Decimal("100"), importe=Decimal("21"))],
    )
    return ComprobanteResponse(**{**datos, **cambios})


@pytest.fixture
def externo(monkeypatch):
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.execute.return_value.scalar_one_or_none.return_value = None
    wsfe = SimpleNamespace(fe_comp_consultar=AsyncMock(return_value=consulta()))
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_empresa",
        AsyncMock(return_value=SimpleNamespace(cuit="20123456789")),
    )
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        FacturacionService, "_obtener_cliente_wsfe", AsyncMock(return_value=wsfe)
    )
    return NotasService(db), wsfe


def request(original, tipo=8, **cambios):
    return EmitirComprobanteRequest(
        **{
            **dict(
                empresa_id=1,
                punto_venta_id=9,
                tipo_comprobante=tipo,
                concepto=1,
                fecha_emision=date(2026, 8, 10),
                confirmacion_fecha_fiscal=True,
                tipo_documento=original["receptor"]["tipo_documento"],
                numero_documento=original["receptor"]["numero_documento"],
                razon_social="Receptor sintético",
                condicion_iva="CF",
                guardar_cliente=False,
                items=[
                    {**i, "descripcion": "Devolución de servicios"}
                    for i in original["items"]
                ],
                comprobantes_asociados=[original["asociado"]],
                alcance_nota="total",
            ),
            **cambios,
        }
    )


@pytest.mark.parametrize("tipo", [1, 6, 11])
async def test_preparar_externa_no_inventa_detalle_y_conserva_decimales(externo, tipo):
    servicio, wsfe = externo
    wsfe.fe_comp_consultar.return_value = consulta(
        tipo,
        **(
            {"imp_total": Decimal("100"), "imp_iva": Decimal("0"), "iva": []}
            if tipo == 11
            else {}
        )
    )
    original = await servicio.original(1, tipo, 4, 12)
    assert original["origen"] == "arca"
    assert original["receptor"]["razon_social"] == ""
    assert original["items"][0]["descripcion"] == ""
    assert original["asociado"]["punto_venta"] == 4
    serializado = PreparacionNotaResponse(**original).model_dump(mode="json")
    assert serializado["items"][0]["precio_unitario"] == "100"
    assert serializado["total"] in {"100", "121"}
    assert not hasattr(wsfe, "fe_cae_solicitar")


@pytest.mark.parametrize(
    "cambio",
    [
        {"resultado": "R"},
        {"cuit_emisor": "30999999999"},
        {"numero": 13},
        {"imp_total": None},
        {"imp_trib": Decimal("1")},
        {"moneda_id": "DOL"},
        {"imp_iva": Decimal("20"), "imp_total": Decimal("120")},
    ],
)
async def test_original_externo_insuficiente_o_ajeno_no_se_prepara(externo, cambio):
    servicio, wsfe = externo
    wsfe.fe_comp_consultar.return_value = consulta(**cambio)
    with pytest.raises(ValidationError):
        await servicio.original(1, 6, 4, 12)


async def test_total_parcial_y_debito_comparten_original(externo):
    servicio, _ = externo
    original = await servicio.original(1, 6, 4, 12)
    await servicio.validar(request(original))
    parcial = request(original, alcance_nota="parcial")
    parcial.items[0].precio_unitario = Decimal("10")
    await servicio.validar(parcial)
    debito = request(original, tipo=7, alcance_nota="ajuste")
    debito.items[0].precio_unitario = Decimal("500")
    await servicio.validar(debito)  # No aplica un tope de crédito al débito.


@pytest.mark.parametrize(
    "cambio",
    [
        {"numero_documento": "87654321"},
        {"tipo_documento": 80},
        {"fecha_emision": date(2026, 8, 8)},
        {"moneda": "DOL"},
        {"comprobantes_asociados": []},
    ],
)
async def test_rechaza_receptor_fecha_referencia_o_alcance_adulterados(externo, cambio):
    servicio, _ = externo
    original = await servicio.original(1, 6, 4, 12)
    with pytest.raises(ValidationError):
        await servicio.validar(request(original, **cambio))


async def test_total_igual_con_iva_diferente_no_es_credito_total(externo):
    servicio, _ = externo
    original = await servicio.original(1, 6, 4, 12)
    nota = request(original)
    nota.items[0].iva_porcentaje = Decimal("0")
    nota.items[0].precio_unitario = Decimal("121")
    with pytest.raises(ValidationError, match="IVA"):
        await servicio.validar(nota)


async def test_parcial_no_acredita_otra_tasa_aunque_su_total_sea_menor(externo):
    servicio, _ = externo
    original = await servicio.original(1, 6, 4, 12)
    nota = request(original, alcance_nota="parcial")
    nota.items[0].iva_porcentaje = Decimal("27")
    nota.items[0].precio_unitario = Decimal("90")
    # 114,30 < 121,00, pero 24,30 de IVA excede los 21,00 originales.
    with pytest.raises(ValidationError, match="cada tasa"):
        await servicio.validar(nota)


async def test_original_iva_por_tasa_no_se_sustituye_por_igual_total(externo):
    servicio, wsfe = externo
    wsfe.fe_comp_consultar.return_value = consulta(
        imp_total=Decimal("248"),
        imp_neto=Decimal("200"),
        imp_iva=Decimal("48"),
        iva=[
            IvaItem(id=5, base_imp=Decimal("100"), importe=Decimal("20")),
            IvaItem(id=6, base_imp=Decimal("100"), importe=Decimal("28")),
        ],
    )
    with pytest.raises(ValidationError, match="IVA"):
        await servicio.original(1, 6, 4, 12)


async def test_original_local_usa_snapshot_sin_consultar_arca(
    db_session, test_empresa, monkeypatch
):
    facturas, punto = await crear_historia(db_session, test_empresa, monkeypatch)
    original = await NotasService(db_session).original(
        test_empresa.id, 6, punto.numero, facturas[0].numero
    )
    assert original["receptor"]["numero_documento"] == "00123456"
    assert original["items"][0]["cantidad"] == Decimal("1.00005")
    assert original["origen"] == "factuflow"


def test_campo_nuevo_no_modifica_payload_de_factura():
    from tests.test_evidencia_fiscal import _request

    assert "alcance_nota" not in _request().model_dump(mode="json")


async def test_consumidor_tecnico_sin_alcance_conserva_contrato(externo):
    servicio, wsfe = externo
    original = await servicio.original(1, 6, 4, 12)
    wsfe.fe_comp_consultar.reset_mock()
    await servicio.validar(request(original, alcance_nota=None))
    wsfe.fe_comp_consultar.assert_not_called()


async def test_preparacion_http_usa_emisor_autenticado(
    client, auth_headers, test_empresa, monkeypatch, externo
):
    servicio, _ = externo
    original = await servicio.original(1, 6, 4, 12)
    preparar = AsyncMock(return_value=original)
    monkeypatch.setattr(NotasService, "original", preparar)
    respuesta = await client.get(
        "/api/comprobantes/notas/original?tipo=6&punto_venta=4&numero=12&empresa_id=999",
        headers=auth_headers,
    )
    assert respuesta.status_code == 403
    preparar.assert_not_called()
    respuesta = await client.get(
        "/api/comprobantes/notas/original?tipo=6&punto_venta=4&numero=12",
        headers={**auth_headers, "X-Empresa-Id": str(test_empresa.id)},
    )
    assert respuesta.status_code == 200
    assert preparar.call_args.args == (test_empresa.id, 6, 4, 12)
    assert respuesta.json()["total"] == "121"
    assert (
        await client.get(
            "/api/comprobantes/notas/original?tipo=6&punto_venta=4&numero=12"
        )
    ).status_code == 403
