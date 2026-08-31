"""Contrato y aritmética de PF-03B con datos sintéticos, sin ARCA."""

from decimal import Decimal, localcontext
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.comprobante_totales import calcular_totales
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.lote_comprobantes_service import LoteComprobantesService


def request_canonico():
    return {
        "empresa_id": 1,
        "punto_venta_id": 1,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": "2026-08-31",
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 99,
        "numero_documento": "0",
        "razon_social": "Caso sintético",
        "condicion_iva": "Consumidor Final",
        "items": [
            {
                "codigo": None,
                "descripcion": "Prueba",
                "cantidad": "2.00",
                "unidad": "unidades",
                "precio_unitario": "100.00",
                "descuento_porcentaje": "10.00",
                "iva_porcentaje": "21.00",
                "orden": 0,
            }
        ],
    }


def test_pf03b_snapshot_canonico_preserva_decimales_y_hash():
    payload = request_canonico()
    request = EmitirComprobanteRequest.model_validate(payload)
    dumped = request.model_dump(mode="json")
    assert dumped["items"] == payload["items"]
    revalidado = EmitirComprobanteRequest.model_validate(dumped).model_dump(mode="json")
    assert dumped == revalidado
    assert IdempotenciaFiscalService.calcular_payload_hash(dumped) == (
        IdempotenciaFiscalService.calcular_payload_hash(revalidado)
    )
    # Obtenido con el schema publicado en v0.3.2 para este mismo caso sintético.
    assert IdempotenciaFiscalService.calcular_payload_hash(dumped) == (
        "d7db2f74886e8b2270a4f96c98f2cfb296153ebc992780566c2e1a97248b0007"
    )
    assert calcular_totales(request.items)["total"] == Decimal("217.80")


@pytest.mark.parametrize("descuento,total", [("0", "242.00"), ("100", "0.00")])
def test_pf03b_conserva_bordes_de_descuento(descuento, total):
    payload = request_canonico()
    payload["items"][0]["descuento_porcentaje"] = descuento
    request = EmitirComprobanteRequest.model_validate(payload)
    assert calcular_totales(request.items)["total"] == Decimal(total)
    payload["items"][0]["precio_unitario"] = "0"
    request = EmitirComprobanteRequest.model_validate(payload)
    assert calcular_totales(request.items)["total"] == 0


def test_pf03b_rechaza_desborde_por_acumulacion_sin_topes_nuevos():
    payload = request_canonico()
    payload["items"][0].update(
        cantidad="1", precio_unitario="600000", iva_porcentaje="0"
    )
    with localcontext() as context:
        context.prec = 8
        request = EmitirComprobanteRequest.model_validate(payload)
        assert calcular_totales(request.items)["total"] == Decimal("540000.00")
        payload["items"] *= 2
        with pytest.raises(ValidationError, match="total válido"):
            EmitirComprobanteRequest.model_validate(payload)


def test_pf03b_conserva_redondeo_del_servicio():
    items = [
        ItemComprobanteCreate(
            descripcion="Redondeo",
            cantidad="1",
            precio_unitario="1.005",
            iva_porcentaje="0",
        )
    ]
    assert calcular_totales(items)["total"] == Decimal("1.00")
    assert FacturacionService(None)._calcular_totales(items) == calcular_totales(items)


def test_pf03b_resumen_desborde_no_publica_acumulacion_parcial():
    payload = request_canonico()
    payload["items"][0].update(
        cantidad="1", precio_unitario="600000", iva_porcentaje="0"
    )
    with localcontext() as context:
        context.prec = 8
        result = LoteComprobantesService(None)._calcular_totales_payloads(
            [
                (payload, 1, Decimal("540000")),
                (payload, 1, Decimal("540000")),
            ]
        )
    assert result["valores_invalidos"] == 1
    assert result["comprobantes"] == 1
    assert result["neto"] == result["total"] == Decimal("540000.00")


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "-Infinity"])
def test_pf03b_calculo_no_acepta_modelos_no_validados(valor):
    item = SimpleNamespace(
        cantidad=Decimal(valor),
        precio_unitario=Decimal("100"),
        descuento_porcentaje=Decimal("0"),
        iva_porcentaje=Decimal("21"),
    )
    with pytest.raises(ValueError, match="finitos"):
        calcular_totales([item])
