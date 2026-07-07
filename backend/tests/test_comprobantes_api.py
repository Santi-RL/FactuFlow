"""Tests de endpoints de comprobantes."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteResponse
from app.services.facturacion_service import FacturacionService


def _idempotency_header(key: str = "idem-test-emitir") -> dict[str, str]:
    """Construye header de idempotencia para tests fiscales."""
    return {"X-Idempotency-Key": key}


def _request_emitir_base(test_empresa) -> dict:
    """Construye un request mínimo de emisión confirmada."""
    return {
        "empresa_id": test_empresa.id,
        "punto_venta_id": 1,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": date.today().isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 99,
        "numero_documento": "0",
        "razon_social": "A CONSUMIDOR FINAL",
        "condicion_iva": "Consumidor Final",
        "items": [
            {
                "descripcion": "Servicio",
                "cantidad": 1,
                "unidad": "unidad",
                "precio_unitario": 1000,
                "iva_porcentaje": 0,
            }
        ],
    }


@pytest.mark.asyncio
async def test_emitir_comprobante_rechaza_concepto_faltante(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    """No debe completar Productos por defecto si falta concepto."""
    response = await client.post(
        "/api/comprobantes/emitir",
        headers=auth_headers,
        json={
            "empresa_id": test_empresa.id,
            "punto_venta_id": 1,
            "tipo_comprobante": 6,
            "fecha_emision": date.today().isoformat(),
            "tipo_documento": 96,
            "numero_documento": "12345678",
            "razon_social": "Cliente sin concepto",
            "condicion_iva": "Consumidor Final",
            "items": [
                {
                    "descripcion": "Servicio",
                    "cantidad": 1,
                    "unidad": "unidad",
                    "precio_unitario": 100,
                    "iva_porcentaje": 0,
                }
            ],
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_emitir_comprobante_exige_confirmacion_fecha_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    """No debe emitir por API si no se confirmó la fecha fiscal en la UI."""
    response = await client.post(
        "/api/comprobantes/emitir",
        headers=auth_headers,
        json={
            "empresa_id": test_empresa.id,
            "punto_venta_id": 1,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": date.today().isoformat(),
            "tipo_documento": 96,
            "numero_documento": "12345678",
            "razon_social": "Cliente sin confirmacion",
            "condicion_iva": "Consumidor Final",
            "items": [
                {
                    "descripcion": "Servicio",
                    "cantidad": 1,
                    "unidad": "unidad",
                    "precio_unitario": 100,
                    "iva_porcentaje": 0,
                }
            ],
        },
    )

    assert response.status_code == 400
    assert "confirmar la fecha fiscal" in response.json()["detail"]


@pytest.mark.asyncio
async def test_emitir_comprobante_reconciliacion_devuelve_409(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """La API debe exponer datos fiscales si ARCA autorizó y falló persistencia."""

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=12,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            total=Decimal("1000.00"),
            mensaje="ARCA autorizó el comprobante, pero FactuFlow no pudo guardarlo",
            errores=["No reintentes esta emisión"],
            requiere_reconciliacion=True,
            categoria_error="post_arca_persistencia",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={**auth_headers, **_idempotency_header()},
        json=_request_emitir_base(test_empresa),
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["requiere_reconciliacion"] is True
    assert detail["categoria_error"] == "post_arca_persistencia"
    assert detail["cae"] == "12345678901234"
    assert detail["numero"] == 12


@pytest.mark.asyncio
async def test_emitir_comprobante_exige_idempotency_key(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    """No debe solicitar CAE si falta X-Idempotency-Key."""
    response = await client.post(
        "/api/comprobantes/emitir",
        headers=auth_headers,
        json=_request_emitir_base(test_empresa),
    )

    assert response.status_code == 400
    assert "X-Idempotency-Key" in response.json()["detail"]["mensaje"]


@pytest.mark.asyncio
async def test_emitir_comprobante_rechaza_emisor_ajeno_antes_de_servicio(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Un usuario común no debe solicitar CAE bajo un emisor ajeno."""
    segunda = test_empresa.__class__(
        razon_social="Empresa Ajena Emision S.A.",
        cuit="30444444446",
        condicion_iva="RI",
        domicilio="Av. Ajena 456",
        localidad="CABA",
        provincia="Buenos Aires",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(segunda)
    await db_session.commit()
    await db_session.refresh(segunda)
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=999,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=1,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)

    response = await client.post(
        "/api/comprobantes/emitir",
        headers={
            **auth_headers,
            **_idempotency_header("idem-emisor-ajeno"),
            "X-Empresa-Id": str(segunda.id),
        },
        json=_request_emitir_base(test_empresa),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "No tenés permiso para operar el emisor seleccionado"
    )
    assert llamadas == 0


@pytest.mark.asyncio
async def test_emitir_comprobante_replay_misma_clave_no_reemite(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """La misma clave y payload debe devolver la respuesta persistida."""
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=100 + llamadas,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=20 + llamadas,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    headers = {**auth_headers, **_idempotency_header("idem-replay")}
    payload = _request_emitir_base(test_empresa)

    primera = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )
    segunda = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert llamadas == 1
    assert segunda.json()["numero"] == primera.json()["numero"]
    assert segunda.json()["comprobante_id"] == primera.json()["comprobante_id"]


@pytest.mark.asyncio
async def test_emitir_comprobante_misma_clave_payload_distinto_devuelve_409(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    monkeypatch: pytest.MonkeyPatch,
):
    """Una clave reutilizada con otro payload debe fallar antes de emitir."""

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=101,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=6,
            numero=21,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 5, 26),
            total=Decimal("1000.00"),
            mensaje="Comprobante emitido exitosamente",
        )

    monkeypatch.setattr(FacturacionService, "emitir_comprobante", fake_emitir)
    headers = {**auth_headers, **_idempotency_header("idem-conflicto")}
    payload = _request_emitir_base(test_empresa)

    primera = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload,
    )
    payload_distinto = {**payload, "observaciones": "Otro dato fiscal"}
    segunda = await client.post(
        "/api/comprobantes/emitir",
        headers=headers,
        json=payload_distinto,
    )

    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 409
    assert "otros datos" in segunda.json()["detail"]["mensaje"]


@pytest.mark.asyncio
async def test_get_comprobante_detalle_con_items(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """Debe devolver el detalle de un comprobante con items sin error 500."""
    cliente = Cliente(
        razon_social="Cliente API Test",
        tipo_documento="DNI",
        numero_documento="12345678",
        condicion_iva="CF",
        empresa_id=test_empresa.id,
    )
    punto_venta = PuntoVenta(
        numero=5,
        nombre="PV Test",
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([cliente, punto_venta])
    await db_session.flush()

    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=1,
        fecha_emision=date(2026, 3, 9),
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae="12345678901234",
        cae_vencimiento=date(2026, 3, 19),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1.000000"),
        empresa_id=test_empresa.id,
        punto_venta_id=punto_venta.id,
        cliente_id=cliente.id,
    )
    db_session.add(comprobante)
    await db_session.flush()

    item = ComprobanteItem(
        codigo="ITEM-1",
        descripcion="Producto API Test",
        cantidad=Decimal("1.00"),
        unidad="unidades",
        precio_unitario=Decimal("1000.00"),
        descuento_porcentaje=Decimal("0.00"),
        iva_porcentaje=Decimal("21.00"),
        subtotal=Decimal("1000.00"),
        orden=1,
        comprobante_id=comprobante.id,
    )
    db_session.add(item)
    await db_session.commit()

    response = await client.get(
        f"/api/comprobantes/{comprobante.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == comprobante.id
    assert data["cliente_nombre"] == "Cliente API Test"
    assert data["punto_venta_numero"] == 5
    assert len(data["items"]) == 1
    assert data["items"][0]["descripcion"] == "Producto API Test"


@pytest.mark.asyncio
async def test_proximo_numero_rechaza_punto_no_usable(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """No debe consultar ARCA para puntos que no son usables por FactuFlow."""
    punto_venta = PuntoVenta(
        numero=998,
        nombre="Factuweb",
        sistema="Factuweb (Imprenta) - Monotributo",
        es_webservice=False,
        bloqueado=False,
        activo=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_venta)
    await db_session.commit()

    response = await client.get(
        "/api/comprobantes/proximo-numero/998/6",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "no está habilitado" in response.json()["detail"]
