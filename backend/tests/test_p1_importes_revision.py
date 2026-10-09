"""Admisibilidad nueva y revisión decimal, sin ARCA ni datos reales."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, select

from app.api.comprobantes import _resolver_operacion_emitir
from app.core.comprobante_totales import calcular_totales, preparar_importes
from app.models.idempotencia_fiscal import OperacionIdempotente, IntentoEmisionFiscal
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest
from app.services.facturacion_service import FacturacionService, ValidationError
from app.services.formatos_importacion_service import (
    FormatosImportacionService,
    FormatoImportacionError,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.lote_comprobantes_service import LoteComprobantesService
from app.services.puntos_venta_arca_service import PuntosVentaArcaService


def payload(tasa="21", precio="100", descuento="0"):
    return {
        "empresa_id": 1,
        "punto_venta_id": 1,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": "2026-10-09",
        "confirmacion_fecha_fiscal": False,
        "tipo_documento": 99,
        "numero_documento": "0",
        "razon_social": "A CONSUMIDOR FINAL",
        "condicion_iva": "CF",
        "moneda": "PES",
        "cotizacion": "1",
        "items": [
            {
                "descripcion": "Ítem sintético",
                "cantidad": "1",
                "precio_unitario": precio,
                "iva_porcentaje": tasa,
                "descuento_porcentaje": descuento,
            }
        ],
    }


@pytest.mark.parametrize(
    "tasa,total",
    [
        ("0", "100.00"),
        ("10.5", "110.50"),
        ("21", "121.00"),
        ("27", "127.00"),
    ],
)
def test_preparacion_tasas_soportadas_y_request_wsfe(tasa, total):
    request = EmitirComprobanteRequest.model_validate(payload(tasa))
    importes = preparar_importes(request.items)
    assert importes == calcular_totales(request.items)
    assert importes["total"] == Decimal(total)
    arca = FacturacionService(None)._armar_request_arca(request, 1, importes, 1)
    assert arca.imp_total == Decimal(total)
    assert arca.imp_op_ex == 0
    assert arca.iva[0].id == {"0": 3, "10.5": 4, "21": 5, "27": 6}[tasa]


@pytest.mark.parametrize("tasa", ["2.5", "5", "19", "99"])
def test_tasa_sin_soporte_rechaza_nueva_preparacion_y_conserva_lectura(tasa):
    request = EmitirComprobanteRequest.model_validate(payload(tasa))
    original = request.model_dump(mode="json")
    original_hash = IdempotenciaFiscalService.calcular_payload_hash(original)
    with pytest.raises(ValueError, match="ítem 1.*sin soporte"):
        preparar_importes(request.items)
    with pytest.raises(ValidationError, match="ítem 1"):
        FacturacionService(None).normalizar_receptor(request)
    # El schema y cálculo que verifican snapshots legacy siguen leyendo sin reinterpretar el archivo.
    historico = EmitirComprobanteRequest.model_validate(original)
    assert calcular_totales(historico.items)["total"] == Decimal("100.00")
    assert (
        IdempotenciaFiscalService.calcular_payload_hash(
            historico.model_dump(mode="json")
        )
        == original_hash
    )


def test_resumen_suma_comprobantes_decimales_y_iva27_sin_estimados():
    mitad = payload("0", "1.005")
    tasa27 = payload("27")
    invalido = payload("5")
    resumen = LoteComprobantesService(None)._calcular_totales_payloads(
        [
            (mitad, 1, Decimal("1.01")),
            (mitad, 1, Decimal("1.01")),
            (tasa27, 1, Decimal("999")),
            (invalido, 1, Decimal("100")),
        ]
    )
    assert resumen["comprobantes"] == 3
    assert resumen["valores_invalidos"] == 1
    assert resumen["neto"] == Decimal("102.00")
    assert resumen["iva27"] == Decimal("27.00")
    assert resumen["total"] == Decimal("129.00")


@pytest.mark.parametrize(
    "descuento,neto,total",
    [
        ("0", "1.00", "1.00"),
        ("100", "0.00", "0.00"),
    ],
)
def test_preparacion_preserva_mitad_centavo_y_descuentos(descuento, neto, total):
    request = EmitirComprobanteRequest.model_validate(payload("0", "1.005", descuento))
    preparado = preparar_importes(request.items)
    assert preparado["subtotal"] == Decimal(neto)
    assert preparado["total"] == Decimal(total)


@pytest.mark.parametrize("tasa", ["2.5", "5", "19"])
def test_constante_excel_comparte_dominio_soportado(tasa):
    with pytest.raises(FormatoImportacionError, match="IVA fija"):
        FormatosImportacionService(None)._validar_constante_fiscal(
            "item_iva_porcentaje", tasa
        )


@pytest.mark.asyncio
async def test_servicios_unitario_y_batch_rechazan_antes_de_numeracion_y_cae(
    monkeypatch,
):
    servicio = FacturacionService(None)
    request = EmitirComprobanteRequest.model_validate(payload("5"))
    no_io = AsyncMock(
        side_effect=AssertionError("No debe avanzar una tasa sin soporte")
    )
    monkeypatch.setattr(servicio, "_tomar_lock_numeracion", no_io)
    monkeypatch.setattr(servicio, "_obtener_cliente_wsfe", no_io)
    resultado = await servicio.emitir_comprobante(request)
    resultados = await servicio.emitir_comprobantes_lote([request])
    assert resultado.exito is False
    assert "sin soporte" in " ".join(resultado.errores)
    assert resultados[0].exito is False
    assert "sin soporte" in " ".join(resultados[0].errores)
    no_io.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_se_busca_antes_de_aplicar_admisibilidad_nueva(monkeypatch):
    request = EmitirComprobanteRequest.model_validate(payload("5"))
    existente = SimpleNamespace(estado="requiere_reconciliacion")
    monkeypatch.setattr(
        IdempotenciaFiscalService,
        "obtener_operacion_existente",
        AsyncMock(return_value=existente),
    )
    no_io = AsyncMock(side_effect=AssertionError("El replay no inicia otra operación"))
    monkeypatch.setattr(PuntosVentaArcaService, "asegurar_comprobacion_reciente", no_io)
    _, operacion, creada, contexto = await _resolver_operacion_emitir(
        db=None,
        request=request,
        empresa_id=1,
        usuario_id=1,
        idempotency_key="legacy",
    )
    assert operacion is existente
    assert creada is False
    assert contexto is None
    no_io.assert_not_awaited()


@pytest.fixture
async def punto_local(db_session, test_empresa):
    punto = PuntoVenta(numero=1, nombre="Punto sintético", empresa_id=test_empresa.id)
    db_session.add(punto)
    await db_session.commit()
    return punto


@pytest.fixture(autouse=True)
def fecha_local(monkeypatch):
    class FechaFija(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 9)

    monkeypatch.setattr("app.services.facturacion_service.date", FechaFija)


@pytest.mark.asyncio
async def test_api_revision_exacta_sin_confirmacion_clave_io_ni_escrituras(
    client,
    auth_headers,
    db_session,
    test_empresa,
    punto_local,
    monkeypatch,
):
    no_io = AsyncMock(side_effect=AssertionError("La revisión no consulta ARCA"))
    monkeypatch.setattr(FacturacionService, "_obtener_cliente_wsfe", no_io)
    monkeypatch.setattr(FacturacionService, "_obtener_certificado_activo", no_io)
    monkeypatch.setattr(PuntosVentaArcaService, "asegurar_comprobacion_reciente", no_io)
    escritos = []

    def registrar(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            escritos.append(statement.split()[0])

    motor = db_session.bind.sync_engine
    event.listen(motor, "before_cursor_execute", registrar)
    try:
        pedido = payload("0", "1.005")
        pedido.update(empresa_id=999, punto_venta_id=punto_local.id)
        response = await client.post(
            "/api/comprobantes/previsualizar", json=pedido, headers=auth_headers
        )
    finally:
        event.remove(motor, "before_cursor_execute", registrar)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == result["subtotal"] == "1.00"
    assert result["subtotales_items"] == ["1.00"]
    assert result["receptor"]["tipo_documento"] == 99
    assert result["moneda"] == "PES"
    assert result["cotizacion"] == "1"
    assert escritos == []
    no_io.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("campo,valor", [("punto_venta_id", 999), ("cliente_id", 999)])
async def test_revision_no_acepta_entidades_ajenas(
    client,
    auth_headers,
    punto_local,
    campo,
    valor,
):
    pedido = payload()
    pedido["punto_venta_id"] = punto_local.id
    pedido[campo] = valor
    response = await client.post(
        "/api/comprobantes/previsualizar", json=pedido, headers=auth_headers
    )
    assert response.status_code == 400
    assert "empresa activa" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ruta", ["previsualizar", "emitir"])
async def test_api_tasa_sin_soporte_no_consulta_preflight_ni_crea_operacion(
    client,
    auth_headers,
    db_session,
    ruta,
    monkeypatch,
):
    no_io = AsyncMock(side_effect=AssertionError("Debe rechazar antes de preflight"))
    monkeypatch.setattr(PuntosVentaArcaService, "asegurar_comprobacion_reciente", no_io)
    pedido = payload("2.5")
    pedido["confirmacion_fecha_fiscal"] = True
    response = await client.post(
        f"/api/comprobantes/{ruta}",
        json=pedido,
        headers={**auth_headers, "X-Idempotency-Key": "sin-soporte"},
    )
    assert response.status_code == 400, response.text
    assert "ítem 1" in response.json()["detail"]
    assert "2,5 %" in response.json()["detail"]
    assert (
        await db_session.execute(select(OperacionIdempotente))
    ).scalars().all() == []
    assert (
        await db_session.execute(select(IntentoEmisionFiscal))
    ).scalars().all() == []
    no_io.assert_not_awaited()
