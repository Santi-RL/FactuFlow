"""Fidelidad del receptor: Excel sintético, preparación y evidencia histórica."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from app.core.documento_receptor import normalizar_documento
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService, ValidationError
from app.services.formatos_importacion_service import (
    FormatosImportacionService,
    FormatoImportacionError,
)


def _version(**campos):
    config = {
        "tipo": "sintetico_pf13",
        "header_row": 1,
        "campos": {
            "cliente_tipo_documento": {
                "origen": "header",
                "encabezados": ["Tipo documento"],
            },
            "cliente_numero_documento": {
                "origen": "header",
                "encabezados": ["Documento"],
                "transformacion": "documento",
            },
            "cliente_condicion_iva": {
                "origen": "header",
                "encabezados": ["Condición IVA"],
            },
            "cliente_razon_social": {"origen": "header", "encabezados": ["Nombre"]},
            "importe_total": {
                "origen": "header",
                "encabezados": ["Importe"],
                "transformacion": "decimal",
            },
            **campos,
        },
    }
    return SimpleNamespace(configuracion_json=config, formato=SimpleNamespace(id=1))


def _excel(rows, headers=None):
    wb = Workbook()
    wb.active.append(
        headers or ["Tipo documento", "Documento", "Condición IVA", "Nombre", "Importe"]
    )
    for row in rows:
        wb.active.append(row)
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def _request(tipo=96, numero="12345678", importe="1000", condicion="CF", comprobante=6):
    return EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=comprobante,
        concepto=1,
        fecha_emision=date(2026, 10, 9),
        confirmacion_fecha_fiscal=True,
        tipo_documento=tipo,
        numero_documento=numero,
        razon_social="Receptor sintético",
        condicion_iva=condicion,
        guardar_cliente=False,
        items=[
            ItemComprobanteCreate(
                descripcion="Producto sintético",
                cantidad=Decimal("1"),
                precio_unitario=Decimal(importe),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )


@pytest.mark.parametrize(
    ("tipo", "numero", "codigo"),
    [
        ("DNI", "12.345.678", 96),
        ("CUIT", "20-40937847-2", 80),
        ("CUIL", "20409378472", 86),
        ("96", 12345678.0, 96),
    ],
)
@pytest.mark.asyncio
async def test_excel_cf_identificado_conserva_tipo_numero_nombre_hasta_wsfe(
    tipo, numero, codigo
):
    service = FormatosImportacionService(None)
    version = _version()
    original = deepcopy(version.configuracion_json)
    importacion = await service.importar_con_version(
        _excel([[tipo, numero, "Consumidor Final", "Receptor sintético", 1000]]),
        SimpleNamespace(cuit=""),
        version,
    )
    fila = importacion.filas[0]
    assert fila["cliente_tipo_documento"] == codigo
    assert fila["cliente_numero_documento"] == normalizar_documento(numero, codigo)
    assert fila["cliente_razon_social"] == "Receptor sintético"
    assert fila["cliente_condicion_iva"] == "CF"
    assert fila["_duplicados_identidad_entrada"]["tipo_documento"] == codigo
    assert fila["_duplicados_identidad_entrada"]["numero_documento"] == str(
        numero
    ).removesuffix(".0")
    facturacion = FacturacionService(None)
    request = facturacion.normalizar_receptor(
        _request(codigo, fila["cliente_numero_documento"])
    )
    armado = facturacion._armar_request_arca(
        request, 1, facturacion._calcular_totales(request.items), 1
    )
    assert armado.tipo_doc == codigo
    assert str(armado.nro_doc) == fila["cliente_numero_documento"]
    assert armado.condicion_iva_receptor_id == 5
    assert version.configuracion_json == original


@pytest.mark.parametrize("condicion", ["", "Otra", "RNI"])
@pytest.mark.asyncio
async def test_condicion_invalida_no_degrada_a_cf(condicion):
    with pytest.raises(FormatoImportacionError, match="Fila 2"):
        await FormatosImportacionService(None).importar_con_version(
            _excel([["DNI", "12345678", condicion, "Sintético", 1000]]),
            SimpleNamespace(cuit=""),
            _version(),
        )


@pytest.mark.parametrize(
    ("campo", "fila"),
    [
        ("cliente_tipo_documento", ["DNI", "12345678", "CF", "Sintético", 1000]),
        ("cliente_condicion_iva", ["", "", "CF", "Sintético", 1000]),
    ],
)
@pytest.mark.asyncio
async def test_formato_legacy_ambiguo_exige_configuracion_sin_reescribirlo(campo, fila):
    version = _version()
    del version.configuracion_json["campos"][campo]
    original = deepcopy(version.configuracion_json)
    with pytest.raises(FormatoImportacionError):
        await FormatosImportacionService(None).importar_con_version(
            _excel([fila]),
            SimpleNamespace(cuit=""),
            version,
        )
    assert version.configuracion_json == original


@pytest.mark.parametrize("condicion", ["RI", "", "Otra"])
@pytest.mark.asyncio
async def test_columna_fiscal_no_es_sustituida_por_constante(condicion):
    version = _version(cliente_condicion_iva={"origen": "constante", "valor": "CF"})
    with pytest.raises(FormatoImportacionError, match="difiere de la configuración"):
        await FormatosImportacionService(None).importar_con_version(
            _excel([["DNI", "12345678", condicion, "Sintético", 1000]]),
            SimpleNamespace(cuit=""),
            version,
        )


@pytest.mark.asyncio
async def test_constantes_explicitas_sin_columnas_innecesarias():
    version = _version(
        cliente_tipo_documento={"origen": "constante", "valor": "DNI"},
        cliente_condicion_iva={"origen": "constante", "valor": "CF"},
    )
    resultado = await FormatosImportacionService(None).importar_con_version(
        _excel([["12345678", "Sintético", 1000]], ["Documento", "Nombre", "Importe"]),
        SimpleNamespace(cuit=""),
        version,
    )
    assert resultado.filas[0]["cliente_tipo_documento"] == 96
    assert (
        resultado.mapeo_usado["campos"]["cliente_condicion_iva"]["origen"]
        == "constante"
    )


@pytest.mark.parametrize(
    ("tipo", "numero"),
    [
        ("DNI", "AB12345678"),
        ("CUIL", "20409378471"),
        ("", "12345678"),
        ("DNI", "00000000"),
    ],
)
@pytest.mark.asyncio
async def test_documento_invalido_no_se_convierte_en_anonimo(tipo, numero):
    with pytest.raises(FormatoImportacionError, match="Fila 2"):
        await FormatosImportacionService(None).importar_con_version(
            _excel([[tipo, numero, "CF", "Sintético", 1000]]),
            SimpleNamespace(cuit=""),
            _version(),
        )


@pytest.mark.parametrize("numero", ["", "0"])
def test_anonimo_respeta_total_del_comprobante(numero):
    facturacion = FacturacionService(None)
    request = _request(99, numero)
    assert facturacion.normalizar_receptor(request).numero_documento == "0"
    request.items *= 2
    request.items[0].precio_unitario = Decimal("5000000")
    with pytest.raises(ValidationError, match="igual o superior"):
        facturacion.normalizar_receptor(request)


def test_normalizacion_historica_no_se_reinterpreta():
    facturacion = FacturacionService(None)
    request = _request(96, "AB12345678")
    assert (
        facturacion._normalizar_datos_receptor(request, historico=True).numero_documento
        == "12345678"
    )
    with pytest.raises(ValidationError, match="formato inválido"):
        facturacion.normalizar_receptor(request)
    assert request.numero_documento == "AB12345678"


def test_documento_99_cero_conserva_condicion_exenta_explicita():
    request = _request(99, "0", condicion="Exento")
    normalizado = FacturacionService(None).normalizar_receptor(request)
    assert normalizado.condicion_iva == "Exento"
    assert normalizado.tipo_documento == 99
    assert normalizado.numero_documento == "0"


@pytest.mark.asyncio
async def test_alias_ci_legacy_es_anonimo_y_no_borra_documento_identificado():
    service = FormatosImportacionService(None)
    resultado = await service.importar_con_version(
        _excel([["CI", "0", "CF", "Sintético", 1000]]),
        SimpleNamespace(cuit=""),
        _version(),
    )
    assert resultado.filas[0]["cliente_tipo_documento"] == 99
    assert resultado.filas[0]["cliente_numero_documento"] == "0"
    with pytest.raises(FormatoImportacionError, match="sin identificar"):
        await service.importar_con_version(
            _excel([["CI", "12345678", "CF", "Sintético", 1000]]),
            SimpleNamespace(cuit=""),
            _version(),
        )


def test_hash_historico_cf_cero_sobre_umbral_no_se_reinterpreta():
    request = _request(99, "0", importe="10000000")
    facturacion = FacturacionService(None)
    assert (
        facturacion._normalizar_datos_receptor(request, historico=True).numero_documento
        == "0"
    )
    with pytest.raises(ValidationError, match="igual o superior"):
        facturacion.normalizar_receptor(request)


@pytest.mark.asyncio
async def test_tipo_fraccionario_no_se_trunca_por_transformacion_entero():
    version = _version(
        cliente_tipo_documento={
            "origen": "header",
            "encabezados": ["Tipo documento"],
            "transformacion": "entero",
        }
    )
    with pytest.raises(FormatoImportacionError, match="Fila 2"):
        await FormatosImportacionService(None).importar_con_version(
            _excel([[80.5, "20409378472", "CF", "Sintético", 1000]]),
            SimpleNamespace(cuit=""),
            version,
        )


@pytest.mark.parametrize("campo", ["cliente_tipo_documento", "cliente_condicion_iva"])
@pytest.mark.asyncio
async def test_columna_fiscal_ausente_no_usa_default(campo):
    version = _version(
        **{
            campo: {
                "origen": "header",
                "encabezados": ["Columna ausente"],
                "default": "CF" if campo == "cliente_condicion_iva" else "DNI",
            }
        }
    )
    with pytest.raises(FormatoImportacionError):
        await FormatosImportacionService(None).importar_con_version(
            _excel(
                [["12345678", "Sintético", 1000]], ["Documento", "Nombre", "Importe"]
            ),
            SimpleNamespace(cuit=""),
            version,
        )
