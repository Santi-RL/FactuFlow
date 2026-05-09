"""Tests para emision masiva de comprobantes."""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import Workbook
from openpyxl.utils.datetime import to_excel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.certificado import Certificado
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteResponse
from app.services.lote_comprobantes_service import (
    LoteComprobanteError,
    LoteComprobantesService,
)


def _build_lote_excel(
    empresa_cuit: str,
    concepto: int | str = 1,
    tipo_comprobante: int = 6,
    iva: int | float = 21,
    cliente_tipo_documento: str = "CUIT",
    cliente_numero_documento: str = "20409378472",
    cliente_razon_social: str = "Cliente Lote SA",
    cliente_condicion_iva: str = "Responsable Inscripto",
    item_precio_unitario: int | float = 1000,
    fecha_servicio_desde: date | str = "",
    fecha_servicio_hasta: date | str = "",
    fecha_vto_pago: date | str = "",
    asociado_tipo_comprobante: int | str = "",
    asociado_punto_venta: int | str = "",
    asociado_numero: int | str = "",
    asociado_fecha: date | str = "",
    asociado_cuit: str = "",
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Comprobantes"
    sheet.append(
        [
            "comprobante_ref",
            "empresa_cuit",
            "punto_venta_numero",
            "tipo_comprobante",
            "concepto",
            "fecha_emision",
            "cliente_tipo_documento",
            "cliente_numero_documento",
            "cliente_razon_social",
            "cliente_condicion_iva",
            "cliente_domicilio",
            "fecha_servicio_desde",
            "fecha_servicio_hasta",
            "fecha_vto_pago",
            "item_codigo",
            "item_descripcion",
            "item_cantidad",
            "item_unidad",
            "item_precio_unitario",
            "item_descuento_porcentaje",
            "item_iva_porcentaje",
            "observaciones",
            "asociado_tipo_comprobante",
            "asociado_punto_venta",
            "asociado_numero",
            "asociado_fecha",
            "asociado_cuit",
        ]
    )
    asociado_fecha_valor = (
        asociado_fecha.isoformat()
        if isinstance(asociado_fecha, date)
        else asociado_fecha
    )
    fecha_servicio_desde_valor = (
        fecha_servicio_desde.isoformat()
        if isinstance(fecha_servicio_desde, date)
        else fecha_servicio_desde
    )
    fecha_servicio_hasta_valor = (
        fecha_servicio_hasta.isoformat()
        if isinstance(fecha_servicio_hasta, date)
        else fecha_servicio_hasta
    )
    fecha_vto_pago_valor = (
        fecha_vto_pago.isoformat()
        if isinstance(fecha_vto_pago, date)
        else fecha_vto_pago
    )
    sheet.append(
        [
            "LOTE-001",
            empresa_cuit,
            1,
            tipo_comprobante,
            concepto,
            date.today().isoformat(),
            cliente_tipo_documento,
            cliente_numero_documento,
            cliente_razon_social,
            cliente_condicion_iva,
            "Av. Siempre Viva 123",
            fecha_servicio_desde_valor,
            fecha_servicio_hasta_valor,
            fecha_vto_pago_valor,
            "ITEM-001",
            "Servicio mensual",
            1,
            "unidad",
            item_precio_unitario,
            0,
            iva,
            "Factura de prueba",
            asociado_tipo_comprobante,
            asociado_punto_venta,
            asociado_numero,
            asociado_fecha_valor,
            asociado_cuit,
        ]
    )

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _build_extracto_bancario_excel(
    empresa_cuit: str,
    fecha_movimiento: date | None = None,
    fecha_como_serial: bool = False,
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Extracto"
    sheet.append(
        [
            "Fecha",
            "Créditos",
            "Leyendas Adicionales1",
            "Leyendas Adicionales2",
            "Pto Vta",
        ]
    )
    fecha_base = fecha_movimiento or date.today()
    fecha = (
        to_excel(fecha_base) if fecha_como_serial else fecha_base.strftime("%d/%m/%Y")
    )
    sheet.append([fecha, "59.500,00", "CLIENTE UNO", "20409378472", 1])
    sheet.append([fecha, "70.500,00", "CLIENTE DOS", "20409378472", 10])
    sheet.append([fecha, "140.000,00", "CLIENTE TRES", "20409378472", 13])

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _build_cano_factura_b_excel(fecha_movimiento: date | None = None) -> bytes:
    """Genera una muestra del formato Cano con Factura B e IVA discriminado."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Hoja1"
    sheet.append(
        [
            "Fecha",
            "Tipo",
            "Punto de Venta",
            "Número Desde",
            "Número Hasta",
            "Cód. Autorización",
            "Tipo Doc. Receptor",
            "Nro. Doc. Receptor",
            "Denominación Receptor",
            "Tipo Cambio",
            "Moneda",
            "Imp. Neto Gravado",
            "Imp. Neto No Gravado",
            "Imp. Op. Exentas",
            "Otros Tributos",
            "IVA",
            "Imp. Total",
        ]
    )
    fecha = fecha_movimiento or date.today()
    sheet.append(
        [
            fecha,
            "6 - Factura B",
            2,
            1,
            "",
            "",
            "DNI",
            "HEBER YOEL ASANCHEZ CA -",
            "",
            1,
            "$",
            74380.1652892562,
            0,
            0,
            "",
            15619.8347107438,
            90000,
        ]
    )

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _config_formato_cano_factura_b() -> dict:
    """Devuelve la configuración del formato Cano Factura B con IVA 21%."""
    return {
        "tipo": "cano_factura_b_iva_21",
        "header_row": 1,
        "modo_agrupacion": "fila",
        "campos": {
            "fecha_origen": {
                "origen": "header",
                "encabezados": ["Fecha"],
                "transformacion": "fecha",
                "requerido": True,
            },
            "importe_total": {
                "origen": "header",
                "encabezados": ["Imp. Total"],
                "transformacion": "decimal",
                "requerido": False,
            },
            "item_precio_unitario": {
                "origen": "header",
                "encabezados": ["Imp. Neto Gravado"],
                "transformacion": "decimal",
                "requerido": True,
            },
            "cliente_razon_social": {
                "origen": "header",
                "encabezados": ["Nro. Doc. Receptor", "Denominación Receptor"],
                "transformacion": "texto",
                "requerido": False,
                "default": "",
            },
            "punto_venta_numero": {
                "origen": "header",
                "encabezados": ["Punto de Venta"],
                "transformacion": "entero",
                "requerido": True,
            },
            "tipo_comprobante": {"origen": "constante", "valor": 6},
            "cliente_condicion_iva": {
                "origen": "constante",
                "valor": "Consumidor Final",
            },
            "item_cantidad": {"origen": "constante", "valor": 1},
            "item_unidad": {"origen": "constante", "valor": "unidad"},
            "item_iva_porcentaje": {"origen": "constante", "valor": 21},
            "item_descuento_porcentaje": {"origen": "constante", "valor": 0},
            "guardar_cliente": {"origen": "constante", "valor": False},
        },
    }


def _opciones_fechas(
    fecha_emision_modo: str = "archivo",
    fecha_emision_fija: date | None = None,
    concepto_modo: str = "productos",
    descripcion_item_modo: str = "archivo",
    descripcion_item_fija: str | None = None,
) -> dict[str, str]:
    """Devuelve opciones explícitas para validar lotes."""
    data = {
        "concepto_modo": concepto_modo,
        "descripcion_item_modo": descripcion_item_modo,
        "fecha_emision_modo": fecha_emision_modo,
        "fecha_servicio_desde_modo": "archivo",
        "fecha_servicio_hasta_modo": "archivo",
        "fecha_vto_pago_modo": "archivo",
    }
    if fecha_emision_fija:
        data["fecha_emision_fija"] = fecha_emision_fija.isoformat()
    if descripcion_item_fija:
        data["descripcion_item_fija"] = descripcion_item_fija
    return data


@pytest.fixture
async def test_punto_venta(db_session: AsyncSession, test_empresa) -> PuntoVenta:
    punto = PuntoVenta(
        numero=1,
        nombre="Principal",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto)
    await db_session.commit()
    await db_session.refresh(punto)
    return punto


@pytest.fixture
async def test_certificado(db_session: AsyncSession, test_empresa) -> Certificado:
    certificado = Certificado(
        nombre="Certificado homologacion",
        cuit=test_empresa.cuit,
        fecha_emision=date(2026, 1, 1),
        fecha_vencimiento=date(2026, 12, 31),
        archivo_crt="empresa-test.crt",
        archivo_key="empresa-test.key",
        activo=True,
        ambiente="homologacion",
        empresa_id=test_empresa.id,
    )
    db_session.add(certificado)
    await db_session.commit()
    await db_session.refresh(certificado)
    return certificado


@pytest.mark.asyncio
async def test_descargar_plantilla_lote(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.get(
        "/api/lotes-comprobantes/plantilla", headers=auth_headers
    )

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment;" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_validar_lote_registra_grupos_y_filas(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True
    assert data["lote"]["estado"] == "validado"
    assert data["lote"]["grupos_validos"] == 1
    assert data["lote"]["grupos_con_error"] == 0

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    assert detalle.status_code == 200
    detalle_data = detalle.json()
    assert len(detalle_data["grupos"]) == 1
    assert len(detalle_data["filas"]) == 1
    assert detalle_data["grupos"][0]["estado"] == "validado"


@pytest.mark.asyncio
async def test_validar_lote_rechaza_descripcion_item_faltante(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe validar un lote sin política de descripción facturada."""
    opciones = _opciones_fechas()
    opciones.pop("descripcion_item_modo")

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=opciones,
        files={
            "archivo": (
                "lote-sin-descripcion-modo.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validar_lote_descripcion_item_fija_sobrescribe_archivo(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe aplicar la descripción fija elegida para todo el lote."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            descripcion_item_modo="fija",
            descripcion_item_fija="Honorarios profesionales",
        ),
        files={
            "archivo": (
                "lote-descripcion-fija.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    fila = detalle.json()["filas"][0]
    assert fila["datos_json"]["item_descripcion"] == "Honorarios profesionales"


@pytest.mark.asyncio
async def test_validar_lote_rechaza_empresa_distinta(
    client: AsyncClient,
    auth_headers: dict,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-otra-empresa.xlsx",
                _build_lote_excel("30999999999"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "empresa activa" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_rechaza_iva_invalido(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-iva-invalido.xlsx",
                _build_lote_excel(test_empresa.cuit, iva=22),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["estado"] == "con_errores"
    assert data["lote"]["grupos_con_error"] == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("alícuota de IVA" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_consumidor_final_sin_documento_bajo_umbral(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-cf-sin-documento.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="",
                    cliente_condicion_iva="Consumidor Final",
                    item_precio_unitario=1000,
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == "validado"
    assert grupo["cliente_documento"] == "0"
    assert grupo["cliente_razon_social"] == "A CONSUMIDOR FINAL"


@pytest.mark.asyncio
async def test_validar_lote_nota_credito_requiere_comprobante_asociado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una nota de crédito no puede quedar lista sin comprobante asociado."""
    test_empresa.condicion_iva = "Exento"
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(concepto_modo="servicios"),
        files={
            "archivo": (
                "lote-nc-sin-asociado.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    tipo_comprobante=13,
                    concepto=2,
                    iva=0,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="A CONSUMIDOR FINAL",
                    cliente_condicion_iva="Consumidor Final",
                    fecha_servicio_desde=date.today(),
                    fecha_servicio_hasta=date.today(),
                    fecha_vto_pago=date.today(),
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["grupos_con_error"] == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("requiere comprobante asociado" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_nota_credito_guarda_comprobante_asociado_en_payload(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El lote debe persistir el asociado que luego se informa como CbtesAsoc."""
    test_empresa.condicion_iva = "Exento"
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(concepto_modo="servicios"),
        files={
            "archivo": (
                "lote-nc-con-asociado.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    tipo_comprobante=13,
                    concepto=2,
                    iva=0,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="A CONSUMIDOR FINAL",
                    cliente_condicion_iva="Consumidor Final",
                    fecha_servicio_desde=date.today(),
                    fecha_servicio_hasta=date.today(),
                    fecha_vto_pago=date.today(),
                    asociado_tipo_comprobante=11,
                    asociado_punto_venta=1,
                    asociado_numero=1234,
                    asociado_fecha=date(2026, 4, 30),
                    asociado_cuit=test_empresa.cuit,
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True
    stmt = select(LoteComprobanteGrupo).where(
        LoteComprobanteGrupo.lote_id == data["lote"]["id"]
    )
    grupo = (await db_session.execute(stmt)).scalar_one()
    asociado = grupo.payload_json["comprobantes_asociados"][0]
    assert asociado["tipo_comprobante"] == 11
    assert asociado["punto_venta"] == 1
    assert asociado["numero"] == 1234
    assert asociado["fecha"] == "2026-04-30"
    assert asociado["cuit"] == test_empresa.cuit


@pytest.mark.asyncio
async def test_detectar_formato_extracto_bancario(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
):
    response = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-bancario.xlsx",
                _build_extracto_bancario_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["headers_detectados"] == [
        "Fecha",
        "Créditos",
        "Leyendas Adicionales1",
        "Leyendas Adicionales2",
        "Pto Vta",
    ]
    assert data["formato_sugerido_version_id"] is not None
    assert data["candidatos"][0]["confianza"] == "alta"


@pytest.mark.asyncio
async def test_validar_lote_formato_cano_factura_b_iva_21(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe validar el formato Cano como Factura B con IVA 21%."""
    test_empresa.condicion_iva = "RI"
    db_session.add(
        PuntoVenta(
            numero=2,
            nombre="Cano PV 2",
            activo=True,
            es_webservice=True,
            empresa_id=test_empresa.id,
        )
    )
    await db_session.commit()

    crear = await client.post(
        "/api/formatos-importacion",
        headers=auth_headers,
        json={
            "nombre": "Cano - Factura B IVA 21%",
            "descripcion": (
                "Formato particular para planillas Cano: neto gravado, IVA "
                "discriminado y total de Factura B a consumidor final."
            ),
            "configuracion_json": _config_formato_cano_factura_b(),
        },
    )
    assert crear.status_code == 201, crear.text

    contenido = _build_cano_factura_b_excel()
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "cano-factura-b.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert detectar.status_code == 200, detectar.text
    formato_version_id = detectar.json()["formato_sugerido_version_id"]
    assert formato_version_id == crear.json()["version_vigente"]["id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="productos",
                descripcion_item_modo="fija",
                descripcion_item_fija="Venta mostrador",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "cano-factura-b.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True
    assert data["lote"]["grupos_validos"] == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupo = detalle.json()["grupos"][0]
    fila = detalle.json()["filas"][0]["datos_json"]
    assert grupo["tipo_comprobante"] == 6
    assert grupo["punto_venta_numero"] == 2
    assert grupo["cliente_documento"] == "0"
    assert grupo["total_estimado"] == "90000.00"
    assert fila["item_precio_unitario"] == "74380.1652892562"
    assert fila["item_iva_porcentaje"] == 21


@pytest.mark.asyncio
async def test_validar_lote_extracto_bancario_varios_puntos_venta(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    test_empresa.condicion_iva = "Exento"
    for numero in [10, 13]:
        db_session.add(
            PuntoVenta(
                numero=numero,
                nombre=f"Punto {numero}",
                activo=True,
                es_webservice=True,
                empresa_id=test_empresa.id,
            )
        )
    await db_session.commit()
    contenido = _build_extracto_bancario_excel(test_empresa.cuit)
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-bancario-multi-pv.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-bancario-multi-pv.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True
    assert data["lote"]["grupos_validos"] == 3
    assert data["lote"]["formato_importacion_version_id"] is not None

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupos = detalle.json()["grupos"]
    assert [grupo["punto_venta_numero"] for grupo in grupos] == [1, 10, 13]
    assert [grupo["cliente_documento"] for grupo in grupos] == ["0", "0", "0"]
    assert [grupo["total_estimado"] for grupo in grupos] == [
        "59500.00",
        "70500.00",
        "140000.00",
    ]
    assert [grupo["concepto"] for grupo in grupos] == [2, 2, 2]
    assert grupos[0]["fecha_emision"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_validar_lote_rechaza_fecha_emision_fuera_de_ventana_arca(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe observar el lote si la fecha del archivo no puede usarse en ARCA."""
    test_empresa.condicion_iva = "Exento"
    for numero in [10, 13]:
        db_session.add(
            PuntoVenta(
                numero=numero,
                nombre=f"Punto {numero}",
                activo=True,
                es_webservice=True,
                empresa_id=test_empresa.id,
            )
        )
    await db_session.commit()
    contenido = _build_extracto_bancario_excel(
        test_empresa.cuit,
        fecha_movimiento=date.today() - timedelta(days=20),
        fecha_como_serial=True,
    )
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-fecha-vieja.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-fecha-vieja.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["grupos_con_error"] == 3

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("ventana ARCA" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_concepto_definido_por_archivo(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe aceptar Producto/Servicio del Excel cuando se elige archivo."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(concepto_modo="archivo"),
        files={
            "archivo": (
                "lote-concepto-archivo.xlsx",
                _build_lote_excel(test_empresa.cuit, concepto="Producto"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is True

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    grupo = detalle.json()["grupos"][0]
    assert grupo["concepto"] == 1


@pytest.mark.asyncio
async def test_validar_lote_rechaza_concepto_archivo_sin_columna(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe rechazar 'Definido por archivo' si el formato no trae columna."""
    test_empresa.condicion_iva = "Exento"
    contenido = _build_extracto_bancario_excel(test_empresa.cuit)
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-sin-concepto.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="archivo",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-sin-concepto.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "columna de concepto fiscal" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_rechaza_descripcion_archivo_sin_columna(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe rechazar descripción desde archivo si el formato no la mapea."""
    test_empresa.condicion_iva = "Exento"
    contenido = _build_extracto_bancario_excel(test_empresa.cuit)
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-sin-descripcion.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="archivo",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-sin-descripcion.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "descripción facturada" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_extracto_bancario_exige_confirmar_formato(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "extracto-sin-formato.xlsx",
                _build_extracto_bancario_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "formato de importación" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_extracto_bancario_rechaza_factura_c_para_ri(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    for numero in [10, 13]:
        db_session.add(
            PuntoVenta(
                numero=numero,
                nombre=f"Punto {numero}",
                activo=True,
                es_webservice=True,
                empresa_id=test_empresa.id,
            )
        )
    await db_session.commit()
    contenido = _build_extracto_bancario_excel(test_empresa.cuit)
    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-ri.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    formato_version_id = detectar.json()["formato_sugerido_version_id"]

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="servicios",
                descripcion_item_modo="fija",
                descripcion_item_fija="Honorarios",
            ),
            "formato_version_id": str(formato_version_id),
        },
        files={
            "archivo": (
                "extracto-ri.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["grupos_con_error"] == 3

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("Responsable Inscripto" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_consumidor_final_sin_documento_sobre_umbral(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-cf-sin-documento-alto.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="",
                    cliente_condicion_iva="Consumidor Final",
                    item_precio_unitario=10_000_000,
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("$10.000.000" in mensaje for mensaje in mensajes)


@pytest.mark.asyncio
async def test_validar_lote_rechaza_archivo_duplicado(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    contenido = _build_lote_excel(test_empresa.cuit)
    files = {
        "archivo": (
            "lote-duplicado.xlsx",
            contenido,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    primera = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files=files,
    )
    assert primera.status_code == 200, primera.text

    segunda = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-duplicado.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert segunda.status_code == 400
    assert "ya fue cargado" in segunda.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_permite_reintentar_fallido_sin_emitidos(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote fallido sin CAE emitidos puede revalidarse con el mismo archivo."""
    contenido = _build_lote_excel(test_empresa.cuit)
    files = {
        "archivo": (
            "lote-reintento.xlsx",
            contenido,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    primera = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files=files,
    )
    assert primera.status_code == 200, primera.text
    lote_id = primera.json()["lote"]["id"]

    lote_previo = await db_session.get(LoteComprobante, lote_id)
    lote_previo.estado = "fallido"
    lote_previo.grupos_validos = 0
    lote_previo.grupos_fallidos = 1
    lote_previo.grupos_emitidos = 0
    await db_session.commit()

    segunda = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-reintento.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["lote"]["id"] != lote_id
    await db_session.refresh(lote_previo)
    assert lote_previo.metadata_json["reemplazado_por_reintento"][
        "archivo_hash_original"
    ]


@pytest.mark.asyncio
async def test_procesar_lote_sync_actualiza_resultados(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    async def fake_emitir(self, request):
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=123,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=456,
            fecha=request.fecha_emision,
            cae="12345678901234",
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-procesar.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, "X-Confirmacion-Fecha-Fiscal": "true"},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is False
    assert data["lote"]["estado"] == "completado"
    assert data["lote"]["grupos_emitidos"] == 1
    assert data["lote"]["grupos_fallidos"] == 0

    detalle = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/resultados",
        headers=auth_headers,
    )
    assert detalle.status_code == 200
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == "autorizado"
    assert grupo["cae"] == "12345678901234"


@pytest.mark.asyncio
async def test_procesar_lote_exige_confirmacion_fecha_fiscal(
    client: AsyncClient,
    auth_headers: dict,
):
    """No debe procesar lotes por API sin confirmacion fiscal final."""
    response = await client.post(
        "/api/lotes-comprobantes/1/procesar",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "confirmar la fecha fiscal" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tomar_lote_para_procesamiento_es_atomico(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote ya tomado no puede volver a tomarse para emisión."""
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-lock.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    service = LoteComprobantesService(db_session)

    await service._tomar_lote_para_procesamiento(
        lote_id=lote_id,
        empresa_id=test_empresa.id,
        procesamiento_async=False,
        modo_procesamiento="sincronico",
    )
    await db_session.commit()

    with pytest.raises(LoteComprobanteError, match="ya está siendo procesado"):
        await service._tomar_lote_para_procesamiento(
            lote_id=lote_id,
            empresa_id=test_empresa.id,
            procesamiento_async=False,
            modo_procesamiento="sincronico",
        )


@pytest.mark.asyncio
async def test_procesar_lote_legacy_sin_descripcion_item_bloquea_emision(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe emitir lotes validados antes de confirmar descripción facturada."""
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-legacy-descripcion.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    metadata = dict(lote.metadata_json or {})
    metadata.pop("opciones_descripcion_item", None)
    lote.metadata_json = metadata
    await db_session.commit()

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, "X-Confirmacion-Fecha-Fiscal": "true"},
    )

    assert procesar.status_code == 400
    assert "descripción facturada" in procesar.json()["detail"]


@pytest.mark.asyncio
async def test_procesar_lote_grande_encola_y_se_reanuda(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    monkeypatch.setattr(settings, "batch_sync_limit", 0)

    async def fake_emitir(self, request):
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=321,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=654,
            fecha=request.fecha_emision,
            cae="12345678901235",
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-background.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, "X-Confirmacion-Fecha-Fiscal": "true"},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is True
    assert data["lote"]["estado"] == "en_cola"

    service = LoteComprobantesService(db_session)
    lote = await service.procesar_lote(lote_id, test_empresa.id, reanudar=True)

    assert lote.estado == "completado"
    assert lote.grupos_emitidos == 1
