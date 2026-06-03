"""Tests para emision masiva de comprobantes."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import Workbook, load_workbook
from openpyxl.utils.datetime import to_excel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.certificado import Certificado
from app.models.comprobante import Comprobante
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteResponse
from app.services.lote_comprobantes_service import (
    LoteComprobanteError,
    LoteComprobantesService,
)


def _build_lote_excel(
    empresa_cuit: str,
    punto_venta_numero: int | str = 1,
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
            punto_venta_numero,
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


def _confirmacion_fecha_fiscal_header(
    fecha_emision: date | None = None, punto_venta: int = 1
) -> dict[str, str]:
    """Construye el header de confirmación fiscal exacta para tests."""
    fecha = fecha_emision or date.today()
    return {
        "X-Confirmacion-Fecha-Fiscal": (
            f"fechas={fecha.isoformat()};puntos_venta={punto_venta}"
        )
    }


@pytest.mark.asyncio
async def test_archivo_observado_escapa_textos_con_formulas(
    db_session: AsyncSession,
    test_empresa,
):
    """El Excel observado no debe abrir formulas tomadas del archivo original."""
    datos = {column: "" for column in LoteComprobantesService.TEMPLATE_COLUMNS}
    datos.update(
        {
            "comprobante_ref": "=SUM(1,1)",
            "empresa_cuit": test_empresa.cuit,
            "item_descripcion": "+cmd",
            "observaciones": " @malicioso",
        }
    )
    lote = LoteComprobante(
        nombre_archivo="observado.xlsx",
        archivo_hash="hash-observado-formulas",
        estado="con_errores",
        total_filas=1,
        total_grupos=1,
        grupos_con_error=1,
        empresa_id=test_empresa.id,
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="=SUM(1,1)",
        orden=1,
        estado="con_error",
        mensajes_json=["=HYPERLINK('http://malicioso')"],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="=SUM(1,1)",
        estado="con_error",
        datos_json=datos,
        mensajes_json=["=HYPERLINK('http://malicioso')"],
    )
    db_session.add_all([lote, grupo, fila])
    await db_session.commit()
    await db_session.refresh(lote)

    service = LoteComprobantesService(db_session)
    contenido = await service.generar_archivo_observado(lote.id, test_empresa.id)

    workbook = load_workbook(BytesIO(contenido), data_only=False)
    sheet = workbook["Resultados"]
    headers = [cell.value for cell in sheet[1]]
    row = {
        header: sheet.cell(row=2, column=index + 1).value
        for index, header in enumerate(headers)
    }

    assert row["comprobante_ref"] == "'=SUM(1,1)"
    assert row["item_descripcion"] == "'+cmd"
    assert row["observaciones"] == "' @malicioso"
    assert row["resultado_mensajes"] == "'=HYPERLINK('http://malicioso')"
    assert sheet["A2"].data_type == "s"


def _build_lote_excel_multi_grupo(empresa_cuit: str, total_grupos: int = 2) -> bytes:
    """Construye un Excel de prueba con varios comprobantes independientes."""
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
    for index in range(1, total_grupos + 1):
        sheet.append(
            [
                f"LOTE-{index:03d}",
                empresa_cuit,
                1,
                6,
                1,
                date.today().isoformat(),
                "CUIT",
                "20409378472",
                f"Cliente Lote {index}",
                "Responsable Inscripto",
                "Av. Siempre Viva 123",
                "",
                "",
                "",
                f"ITEM-{index:03d}",
                "Servicio mensual",
                1,
                "unidad",
                1000,
                0,
                21,
                "Factura de prueba",
                "",
                "",
                "",
                "",
                "",
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
    punto_venta_modo: str = "archivo",
    punto_venta_numero: int | None = None,
) -> dict[str, str]:
    """Devuelve opciones explícitas para validar lotes."""
    data = {
        "concepto_modo": concepto_modo,
        "descripcion_item_modo": descripcion_item_modo,
        "punto_venta_modo": punto_venta_modo,
        "fecha_emision_modo": fecha_emision_modo,
        "fecha_servicio_desde_modo": "archivo",
        "fecha_servicio_hasta_modo": "archivo",
        "fecha_vto_pago_modo": "archivo",
    }
    if fecha_emision_fija:
        data["fecha_emision_fija"] = fecha_emision_fija.isoformat()
    if descripcion_item_fija:
        data["descripcion_item_fija"] = descripcion_item_fija
    if punto_venta_numero:
        data["punto_venta_numero"] = str(punto_venta_numero)
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
        ambiente=settings.arca_env,
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
async def test_obtener_resumen_y_grupos_paginados_lote(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
):
    """El detalle paginado debe evitar traer todo el lote para abrir la UI."""
    lote = LoteComprobante(
        nombre_archivo="lote-grande.xlsx",
        archivo_hash="hash-lote-grande-paginado",
        estado="validado",
        total_filas=3,
        total_grupos=3,
        grupos_validos=2,
        grupos_con_error=1,
        empresa_id=test_empresa.id,
    )
    db_session.add(lote)
    await db_session.flush()

    for index, estado in enumerate(["validado", "validado", "con_error"], start=1):
        payload = {
            "fecha_emision": "2026-05-20",
            "concepto": 1,
            "items": [
                {
                    "cantidad": 1,
                    "precio_unitario": 1000,
                    "descuento_porcentaje": 0,
                    "iva_porcentaje": 21,
                }
            ],
        }
        grupo = LoteComprobanteGrupo(
            lote_id=lote.id,
            comprobante_ref=f"LOTE-{index:03d}",
            orden=index,
            estado=estado,
            tipo_comprobante=6,
            punto_venta_numero=1,
            cliente_documento="20409378472",
            cliente_razon_social=f"Cliente {index}",
            total_estimado=Decimal("1210"),
            payload_json=payload,
            mensajes_json=["Validado correctamente. Listo para emitir."]
            if estado == "validado"
            else ["Observado"],
        )
        db_session.add(grupo)
        await db_session.flush()
        db_session.add(
            LoteComprobanteFila(
                lote_id=lote.id,
                grupo_id=grupo.id,
                fila_excel=index + 1,
                comprobante_ref=grupo.comprobante_ref,
                estado=estado,
                datos_json={"item_descripcion": f"Servicio {index}"},
                mensajes_json=grupo.mensajes_json,
            )
        )
    await db_session.commit()

    resumen = await client.get(
        f"/api/lotes-comprobantes/{lote.id}/resumen",
        headers=auth_headers,
    )
    assert resumen.status_code == 200, resumen.text
    resumen_data = resumen.json()
    assert "grupos" not in resumen_data
    assert "filas" not in resumen_data
    assert resumen_data["confirmacion_fecha_fiscal"] == (
        "fechas=2026-05-20;puntos_venta=1"
    )
    assert resumen_data["fechas_emision_validas"] == ["2026-05-20"]
    assert resumen_data["puntos_venta_validos"] == [1]
    assert resumen_data["totales_listos_para_emitir"] == {
        "comprobantes": 2,
        "neto": 2000,
        "iva21": 420,
        "iva105": 0,
        "total": 2420,
        "valores_invalidos": 0,
    }

    pagina = await client.get(
        f"/api/lotes-comprobantes/{lote.id}/grupos?page=1&per_page=2",
        headers=auth_headers,
    )
    assert pagina.status_code == 200, pagina.text
    pagina_data = pagina.json()
    assert pagina_data["total"] == 3
    assert pagina_data["total_pages"] == 2
    assert [item["comprobante_ref"] for item in pagina_data["items"]] == [
        "LOTE-001",
        "LOTE-002",
    ]
    assert pagina_data["items"][0]["descripcion_facturada"] == "Servicio 1"

    filtrada = await client.get(
        f"/api/lotes-comprobantes/{lote.id}/grupos?estado=validado&per_page=10",
        headers=auth_headers,
    )
    assert filtrada.status_code == 200, filtrada.text
    filtrada_data = filtrada.json()
    assert filtrada_data["total"] == 2
    assert {item["estado"] for item in filtrada_data["items"]} == {"validado"}


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
async def test_validar_lote_mixto_no_anuncia_emision_si_estado_no_procesable(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote con errores conserva contrato consistente: no puede emitirse."""
    workbook = load_workbook(BytesIO(_build_lote_excel_multi_grupo(test_empresa.cuit)))
    sheet = workbook["Comprobantes"]
    sheet.cell(row=3, column=4).value = 11
    sheet.cell(row=3, column=21).value = 21
    stream = BytesIO()
    workbook.save(stream)

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-mixto.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["estado"] == "con_errores"
    assert data["lote"]["grupos_validos"] == 1
    assert data["lote"]["grupos_con_error"] == 1


@pytest.mark.asyncio
async def test_validar_lote_rechaza_xlsx_malformado(
    client: AsyncClient,
    auth_headers: dict,
):
    """Un .xlsx corrupto debe devolver error funcional, no 500."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "corrupto.xlsx",
                b"esto no es un zip",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "No se pudo leer el archivo Excel" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_rechaza_archivo_demasiado_grande(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """El límite de bytes debe aplicarse antes de parsear el Excel."""
    monkeypatch.setattr(settings, "batch_max_upload_bytes", 10)

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "grande.xlsx",
                b"01234567890",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "tamaño máximo" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_punto_venta_fijo_sobrescribe_archivo(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe permitir fijar un punto de venta habilitado para todo el lote."""
    punto_fijo = PuntoVenta(
        numero=13,
        nombre="Web Services 13",
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
    )
    db_session.add(punto_fijo)
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            punto_venta_modo="fijo",
            punto_venta_numero=13,
        ),
        files={
            "archivo": (
                "lote-pv-fijo.xlsx",
                _build_lote_excel(test_empresa.cuit, punto_venta_numero=1),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    detalle = await client.get(
        f"/api/lotes-comprobantes/{response.json()['lote']['id']}",
        headers=auth_headers,
    )
    detalle_data = detalle.json()
    assert detalle_data["grupos"][0]["punto_venta_numero"] == 13
    assert detalle_data["filas"][0]["datos_json"]["punto_venta_numero"] == 13
    assert (
        detalle_data["metadata_json"]["opciones_punto_venta"]["punto_venta_numero"]
        == 13
    )


@pytest.mark.asyncio
async def test_validar_lote_rechaza_punto_venta_fijo_no_habilitado(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe validar con un punto fijo no usable por el emisor activo."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            punto_venta_modo="fijo",
            punto_venta_numero=99,
        ),
        files={
            "archivo": (
                "lote-pv-invalido.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "Puntos de venta" in response.json()["detail"]


@pytest.mark.asyncio
async def test_validar_lote_guarda_snapshot_perfil_carga_masiva(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe conservar el perfil usado aunque luego se edite."""
    test_certificado.ambiente = settings.arca_env
    perfil = await client.post(
        "/api/perfiles-carga-masiva",
        headers=auth_headers,
        json={
            "nombre": "Servicios mensuales",
            "descripcion": "Perfil de prueba",
            "configuracion_json": {
                "version": 1,
                "formato_importacion_version_id": None,
                "concepto_modo": "productos",
                "descripcion_item_modo": "archivo",
                "fecha_emision": {"modo": "archivo"},
                "periodo_servicio": {"modo": "archivo"},
                "fecha_vto_pago": {"modo": "archivo"},
            },
            "es_predeterminado": True,
            "activo": True,
        },
    )
    assert perfil.status_code == 201, perfil.text

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(),
            "perfil_carga_masiva_id": str(perfil.json()["id"]),
        },
        files={
            "archivo": (
                "lote-con-perfil.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    detalle = await client.get(
        f"/api/lotes-comprobantes/{response.json()['lote']['id']}",
        headers=auth_headers,
    )
    metadata = detalle.json()["metadata_json"]
    assert metadata["perfil_carga_masiva"]["id"] == perfil.json()["id"]
    assert metadata["perfil_carga_masiva"]["nombre"] == "Servicios mensuales"
    assert (
        metadata["perfil_carga_masiva"]["configuracion_json"]["concepto_modo"]
        == "productos"
    )


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
async def test_validar_lote_rechaza_factura_c_con_iva(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Factura C no puede quedar lista si el archivo trae IVA."""
    test_empresa.condicion_iva = "Exento"
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-factura-c-con-iva.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    tipo_comprobante=11,
                    iva=21,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="A CONSUMIDOR FINAL",
                    cliente_condicion_iva="Consumidor Final",
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["puede_emitirse"] is False
    assert data["lote"]["estado"] == "con_errores"

    detalle = await client.get(
        f"/api/lotes-comprobantes/{data['lote']['id']}",
        headers=auth_headers,
    )
    mensajes = detalle.json()["grupos"][0]["mensajes_json"]
    assert any("tipo C no pueden incluir IVA" in mensaje for mensaje in mensajes)


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
async def test_detectar_formato_rechaza_archivo_demasiado_grande(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """La detección de formatos debe aplicar el mismo límite de upload."""
    monkeypatch.setattr(settings, "batch_max_upload_bytes", 10)

    response = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "grande.xlsx",
                b"01234567890",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "tamaño máximo" in response.json()["detail"]


@pytest.mark.asyncio
async def test_crear_formato_rechaza_configuracion_malformada(
    client: AsyncClient,
    auth_headers: dict,
):
    """La configuración de formato debe validarse antes de persistir."""
    response = await client.post(
        "/api/formatos-importacion",
        headers=auth_headers,
        json={
            "nombre": "Formato invalido",
            "descripcion": "No debe persistirse",
            "configuracion_json": {"campos": {"importe_total": None}},
        },
    )

    assert response.status_code == 400
    assert "debe ser un objeto" in response.json()["detail"]


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
async def test_validar_lote_formato_cano_bloquea_total_usado_como_neto(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe bloquear un formato que recalcula IVA sobre un total ya final."""
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

    configuracion = _config_formato_cano_factura_b()
    configuracion["campos"]["item_precio_unitario"] = {
        "origen": "header",
        "encabezados": ["Imp. Total"],
        "transformacion": "decimal",
        "requerido": True,
    }
    crear = await client.post(
        "/api/formatos-importacion",
        headers=auth_headers,
        json={
            "nombre": "Cano - Formato erroneo total como neto",
            "descripcion": "Config de prueba que no debe quedar emitible.",
            "configuracion_json": configuracion,
        },
    )
    assert crear.status_code == 201, crear.text

    contenido = _build_cano_factura_b_excel()
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data={
            **_opciones_fechas(
                concepto_modo="productos",
                descripcion_item_modo="fija",
                descripcion_item_fija="Venta mostrador",
            ),
            "formato_version_id": str(crear.json()["version_vigente"]["id"]),
        },
        files={
            "archivo": (
                "cano-total-como-neto.xlsx",
                contenido,
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
    assert any("no coincide con el total informado" in mensaje for mensaje in mensajes)


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
async def test_validar_lote_formato_con_header_blanco_preserva_indices(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Los headers vacíos no deben desplazar los índices físicos del Excel."""
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
    workbook = load_workbook(BytesIO(_build_extracto_bancario_excel(test_empresa.cuit)))
    workbook.active.insert_cols(1)
    stream = BytesIO()
    workbook.save(stream)
    contenido = stream.getvalue()

    detectar = await client.post(
        "/api/formatos-importacion/detectar",
        headers=auth_headers,
        files={
            "archivo": (
                "extracto-header-blanco.xlsx",
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert detectar.status_code == 200, detectar.text
    assert detectar.json()["headers_detectados"][0] == ""
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
                "extracto-header-blanco.xlsx",
                contenido,
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
    grupos = detalle.json()["grupos"]
    assert [grupo["punto_venta_numero"] for grupo in grupos] == [1, 10, 13]
    assert [grupo["total_estimado"] for grupo in grupos] == [
        "59500.00",
        "70500.00",
        "140000.00",
    ]


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
    test_certificado.ambiente = settings.arca_env

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
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
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
async def test_procesar_lote_background_encola_lote_chico(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Permite iniciar un lote chico en segundo plano para observar progreso."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        lambda app: None,
    )
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-background-chico.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is True
    assert data["lote"]["estado"] == "en_cola"
    assert data["lote"]["modo_procesamiento"] == "background"


@pytest.mark.asyncio
async def test_procesar_lote_actualiza_contadores_parciales(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe persistir avance real entre grupos durante la emisión."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-progreso-parcial.xlsx",
                _build_lote_excel_multi_grupo(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]
    llamadas = 0
    avance_observado = None

    async def fake_emitir(self, request):
        nonlocal llamadas, avance_observado
        llamadas += 1
        if llamadas == 2:
            result = await db_session.execute(
                select(LoteComprobante).where(LoteComprobante.id == lote_id)
            )
            lote = result.scalar_one()
            avance_observado = (
                lote.grupos_emitidos,
                lote.grupos_fallidos,
                lote.grupos_validos,
                lote.mensaje_resumen,
            )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=100 + llamadas,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=200 + llamadas,
            fecha=request.fecha_emision,
            cae=f"1234567890123{llamadas}",
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fake_emitir,
    )

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
    )

    assert procesar.status_code == 200, procesar.text
    assert avance_observado == (
        1,
        0,
        1,
        "Procesando comprobante 1 de 2...",
    )
    data = procesar.json()
    assert data["lote"]["estado"] == "completado"
    assert data["lote"]["grupos_emitidos"] == 2


@pytest.mark.asyncio
async def test_procesar_lote_post_arca_requiere_reconciliacion(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un fallo post-ARCA en lote no debe quedar como reintentable."""
    test_certificado.ambiente = settings.arca_env

    async def fake_emitir(self, request):
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=654,
            fecha=request.fecha_emision,
            cae="12345678901235",
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="ARCA autorizó el comprobante, pero FactuFlow no pudo guardarlo",
            errores=["No reintentes esta emisión"],
            requiere_reconciliacion=True,
            categoria_error="post_arca_persistencia",
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
                "lote-reconciliacion.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["lote"]["estado"] == "requiere_reconciliacion"
    assert data["lote"]["grupos_emitidos"] == 0
    assert data["lote"]["grupos_fallidos"] == 0

    detalle = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/resultados",
        headers=auth_headers,
    )
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == "requiere_reconciliacion"
    assert grupo["cae"] == "12345678901235"
    assert grupo["numero_asignado"] == 654

    service = LoteComprobantesService(db_session)
    lote = await service.obtener_lote(lote_id, test_empresa.id)
    assert service._lote_permite_reintento(lote) is False


@pytest.mark.asyncio
async def test_reanudar_lote_vincula_comprobante_ya_guardado_sin_reemitir(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
):
    """Si el comprobante ya fue guardado, reanudar no debe volver a emitirlo."""
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": date.today().isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": "20409378472",
        "razon_social": "Cliente Lote SA",
        "condicion_iva": "RI",
        "domicilio": "Av. Siempre Viva 123",
        "moneda": "PES",
        "cotizacion": "1",
        "guardar_cliente": False,
        "items": [
            {
                "descripcion": "Servicio mensual",
                "cantidad": "1",
                "unidad": "unidad",
                "precio_unitario": "1000",
                "iva_porcentaje": "21",
            }
        ],
    }
    lote = LoteComprobante(
        nombre_archivo="lote-reanudar-idempotente.xlsx",
        archivo_hash="hash-reanudar-idempotente",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        metadata_json={
            "opciones_concepto": {"concepto_modo": "archivo"},
            "opciones_descripcion_item": {"descripcion_item_modo": "archivo"},
        },
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento="20409378472",
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        payload_json=emitir_request,
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="validado",
        datos_json={},
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=date.today(),
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae="12345678901234",
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento="20409378472",
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, grupo, fila, comprobante])
    await db_session.commit()
    await db_session.refresh(lote)

    service = LoteComprobantesService(db_session)

    async def fail_emitir(_request):
        raise AssertionError("No debe reemitir un grupo ya guardado")

    service.facturacion_service.emitir_comprobante = fail_emitir

    resultado = await service.procesar_lote(lote.id, test_empresa.id, reanudar=True)

    assert resultado.estado == "completado"
    detalle = await service.obtener_lote(lote.id, test_empresa.id)
    assert detalle.grupos[0].estado == "autorizado"
    assert detalle.grupos[0].comprobante_id == comprobante.id
    assert detalle.grupos[0].numero_asignado == 77


@pytest.mark.asyncio
async def test_procesar_lote_exige_confirmacion_fecha_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe procesar lotes por API sin confirmacion fiscal final."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-sin-confirmacion.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers=auth_headers,
    )

    assert response.status_code == 400
    detalle = response.json()["detail"]
    assert "confirmar la fecha fiscal exacta" in detalle
    assert date.today().strftime("%d/%m/%y") in detalle
    assert "0001" in detalle
    assert "XX/XX/XX" not in detalle


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
    test_certificado.ambiente = settings.arca_env
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
async def test_procesar_background_no_reencola_lote_en_proceso(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote en procesamiento no debe volver a estado en_cola."""
    test_certificado.ambiente = settings.arca_env
    worker_iniciado = False

    def fake_ensure_worker(_app):
        nonlocal worker_iniciado
        worker_iniciado = True

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running",
        fake_ensure_worker,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-procesando-background.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    lote = await db_session.get(LoteComprobante, lote_id)
    lote.estado = "procesando"
    lote.procesamiento_async = True
    lote.modo_procesamiento = "background"
    await db_session.commit()

    procesar = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar?background=true",
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is True
    assert data["lote"]["estado"] == "procesando"
    assert data["mensaje"] == "El lote ya está siendo procesado."
    assert worker_iniciado is False


@pytest.mark.asyncio
async def test_reanudar_lote_procesando_solo_si_esta_stale(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El worker solo puede retomar lotes procesando con lease vencido."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-procesando-stale.xlsx",
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
        procesamiento_async=True,
        modo_procesamiento="background",
    )
    await db_session.commit()

    with pytest.raises(LoteComprobanteError, match="ya está siendo procesado"):
        await service._tomar_lote_para_procesamiento(
            lote_id=lote_id,
            empresa_id=test_empresa.id,
            procesamiento_async=True,
            modo_procesamiento="background",
            reanudar=True,
        )

    lote = await db_session.get(LoteComprobante, lote_id)
    lote.updated_at = datetime.utcnow() - timedelta(
        minutes=settings.batch_processing_stale_minutes + 1
    )
    await db_session.commit()

    await service._tomar_lote_para_procesamiento(
        lote_id=lote_id,
        empresa_id=test_empresa.id,
        procesamiento_async=True,
        modo_procesamiento="background",
        reanudar=True,
    )


@pytest.mark.asyncio
async def test_procesar_lote_reanuda_procesando_stale(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El camino usado por el worker debe procesar lotes procesando stale."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "batch_sync_limit", 0)

    async def fake_emitir(self, request):
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=432,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=987,
            fecha=request.fecha_emision,
            cae="12345678901236",
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
                "lote-procesando-stale-worker.xlsx",
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
        procesamiento_async=True,
        modo_procesamiento="background",
    )
    lote = await db_session.get(LoteComprobante, lote_id)
    lote.updated_at = datetime.utcnow() - timedelta(
        minutes=settings.batch_processing_stale_minutes + 1
    )
    await db_session.commit()

    lote = await service.procesar_lote(lote_id, test_empresa.id, reanudar=True)

    assert lote.estado == "completado"
    assert lote.grupos_emitidos == 1


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
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
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
    test_certificado.ambiente = settings.arca_env
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
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
    )

    assert procesar.status_code == 200, procesar.text
    data = procesar.json()
    assert data["en_progreso"] is True
    assert data["lote"]["estado"] == "en_cola"

    service = LoteComprobantesService(db_session)
    lote = await service.procesar_lote(lote_id, test_empresa.id, reanudar=True)

    assert lote.estado == "completado"
    assert lote.grupos_emitidos == 1
