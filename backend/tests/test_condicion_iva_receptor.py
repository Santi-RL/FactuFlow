"""Contrato RG 5616: nuevas solicitudes estrictas e historia preservada."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.condicion_iva_receptor import resolver_condicion_iva_receptor_id
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService, ValidationError


def _request(condicion: str, tipo: int = 11) -> EmitirComprobanteRequest:
    return EmitirComprobanteRequest(
        empresa_id=1,
        punto_venta_id=1,
        tipo_comprobante=tipo,
        concepto=1,
        fecha_emision=date(2026, 8, 9),
        confirmacion_fecha_fiscal=True,
        tipo_documento=96,
        numero_documento="30000001",
        razon_social="Receptor sintético",
        condicion_iva=condicion,
        items=[
            ItemComprobanteCreate(
                descripcion="Producto sintético",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                iva_porcentaje=Decimal("0"),
            )
        ],
    )


@pytest.mark.parametrize("tipo", [1, 2, 3, 6, 7, 8, 11, 12, 13])
@pytest.mark.parametrize(
    ("condicion", "codigo"),
    [("RI", 1), ("Monotributo", 6), ("Exento", 4), ("CF", 5)],
)
def test_matriz_rg5616_hasta_el_armado_wsfe(tipo, condicion, codigo):
    """El mismo contrato valida y coloca el ID en cada tipo soportado."""
    service = FacturacionService(None)
    request = _request(condicion, tipo)
    if tipo in [1, 2, 3]:
        request = request.model_copy(
            update={"tipo_documento": 80, "numero_documento": "20409378472"}
        )
    compatible = tipo in [11, 12, 13] or (
        codigo in ({1, 6} if tipo in [1, 2, 3] else {4, 5})
    )
    if not compatible:
        with pytest.raises(ValidationError, match="no corresponde"):
            service.normalizar_receptor(request)
        with pytest.raises(ValidationError, match="no corresponde"):
            service._armar_request_arca(
                request, 1, service._calcular_totales(request.items), 1
            )
        return
    normalized = service.normalizar_receptor(request)
    armado = service._armar_request_arca(
        normalized, 1, service._calcular_totales(normalized.items), 1
    )
    assert armado.condicion_iva_receptor_id == codigo


@pytest.mark.parametrize(
    ("valor", "codigo"),
    [
        ("  RESPONSABLE   INSCRIPTO ", 1),
        ("IVA Responsable Inscripto", 1),
        (" responsable monotributo ", 6),
        ("IVA Sujeto Exento", 4),
        ("cF", 5),
        ("consumidor_final", 5),
    ],
)
def test_aliases_inequivocos(valor, codigo):
    assert resolver_condicion_iva_receptor_id(valor, 11) == codigo


@pytest.mark.parametrize(
    "condicion", ["", " ", "RNI", "Responsable No Inscripto", "Otra"]
)
@pytest.mark.parametrize("documento", [96, 99])
def test_condicion_invalida_no_se_infiere_por_documento(condicion, documento):
    service = FacturacionService(None)
    request = _request(condicion).model_copy(update={"tipo_documento": documento})
    with pytest.raises(ValidationError, match="Revisá la condición IVA"):
        service.normalizar_receptor(request)
    assert request.condicion_iva == condicion
    assert service._normalizar_condicion_iva(condicion) == condicion


def test_documento_99_no_reclasifica_una_condicion_explicita_valida():
    request = _request("Exento", 6).model_copy(update={"tipo_documento": 99})
    assert (
        FacturacionService(None).normalizar_receptor(request).condicion_iva == "Exento"
    )


def test_verificacion_de_hash_historico_conserva_normalizacion_anterior():
    """La evidencia legacy se verifica sin habilitar una solicitud nueva."""
    service = FacturacionService(None)
    request = _request("Responsable No Inscripto", 1).model_copy(
        update={"tipo_documento": 80, "numero_documento": "20409378472"}
    )
    historical = service._normalizar_datos_receptor(request, historico=True)
    assert historical.condicion_iva == "RI"
    assert request.condicion_iva == "Responsable No Inscripto"
    with pytest.raises(ValidationError):
        service.normalizar_receptor(request)
