"""Tests para emision masiva de comprobantes."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from httpx import AsyncClient
from openpyxl import Workbook, load_workbook
from openpyxl.utils.datetime import to_excel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.arca.exceptions import ArcaServiceError
from app.arca.models import ComprobanteResponse as ArcaComprobanteResponse
from app.core.config import settings
from app.models.certificado import Certificado
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteEvento,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, EmitirComprobanteResponse
from app.schemas.lote_comprobante import LoteReconciliacionExternaItem
from app.services.lote_comprobantes_service import (
    LoteComprobanteError,
    LoteComprobantesService,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.lote_worker import LoteWorker


# Identificadores sintéticos de fixtures. Se construyen en partes para evitar
# versionar por accidente datos fiscales reales o emitidos.
CUIT_RECEPTOR_TEST_NO_REAL = "".join(("20", "40937847", "2"))
CUIT_RECEPTOR_TEST_NO_REAL_INT = int(CUIT_RECEPTOR_TEST_NO_REAL)
CAE_TEST_NO_REAL_SERIE = "".join(("1234567", "89012"))
CAE_TEST_NO_REAL_PREFIX = f"{CAE_TEST_NO_REAL_SERIE}3"
CAE_TEST_NO_REAL = f"{CAE_TEST_NO_REAL_SERIE}34"
CAE_TEST_NO_REAL_ALT = f"{CAE_TEST_NO_REAL_SERIE}35"
CAE_TEST_NO_REAL_36 = f"{CAE_TEST_NO_REAL_SERIE}36"
CAE_TEST_NO_REAL_37 = f"{CAE_TEST_NO_REAL_SERIE}37"
CAE_TEST_NO_REAL_38 = f"{CAE_TEST_NO_REAL_SERIE}38"
CAE_TEST_NO_REAL_39 = f"{CAE_TEST_NO_REAL_SERIE}39"
CAE_TEST_NO_REAL_40 = f"{CAE_TEST_NO_REAL_SERIE}40"


@pytest.fixture(autouse=True)
def _desactivar_batch_arca_por_defecto(monkeypatch: pytest.MonkeyPatch):
    """Evita consultas WSAA/WSFE reales en tests que no prueban batching ARCA."""
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", False)


def _build_lote_excel(
    empresa_cuit: str,
    punto_venta_numero: int | str = 1,
    concepto: int | str = 1,
    tipo_comprobante: int = 6,
    iva: int | float = 21,
    cliente_tipo_documento: str = "CUIT",
    cliente_numero_documento: str = CUIT_RECEPTOR_TEST_NO_REAL,
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
    fecha_emision: date | None = None,
    punto_venta: int = 1,
    idempotency_key: str = "idem-lote-test",
) -> dict[str, str]:
    """Construye el header de confirmación fiscal exacta para tests."""
    fecha = fecha_emision or date.today()
    return {
        "X-Confirmacion-Fecha-Fiscal": (
            f"fechas={fecha.isoformat()};puntos_venta={punto_venta}"
        ),
        "X-Idempotency-Key": idempotency_key,
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
                CUIT_RECEPTOR_TEST_NO_REAL,
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
    sheet.append([fecha, "59.500,00", "CLIENTE UNO", CUIT_RECEPTOR_TEST_NO_REAL, 1])
    sheet.append([fecha, "70.500,00", "CLIENTE DOS", CUIT_RECEPTOR_TEST_NO_REAL, 10])
    sheet.append([fecha, "140.000,00", "CLIENTE TRES", CUIT_RECEPTOR_TEST_NO_REAL, 13])

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


def _fecha_argentina(value: date | str) -> str:
    """Formatea una fecha de test en DD/MM/AAAA."""
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return datetime.strptime(str(value), "%Y-%m-%d").strftime("%d/%m/%Y")


def test_reconciliacion_externa_item_rechaza_fecha_calendario_invalida():
    """El schema no debe aceptar fechas externas imposibles."""
    with pytest.raises(ValueError):
        LoteReconciliacionExternaItem(
            grupo_id=1,
            tipo_comprobante=6,
            punto_venta_numero=1,
            numero=123,
            fecha_emision="31/02/2026",
            total=Decimal("1210.00"),
            motivo="Emitido manualmente por ARCA Web",
        )


def _hashes_fiscales_request(
    request: EmitirComprobanteRequest,
    punto_venta_numero: int,
    total: Decimal,
) -> tuple[str, str]:
    """Calcula los hashes fiscales del request igual que producción."""
    payload = request.model_dump(mode="json")
    payload_hash = IdempotenciaFiscalService.calcular_payload_hash(
        IdempotenciaFiscalService.payload_sin_confirmacion_duplicado(payload)
    )
    huella = IdempotenciaFiscalService.calcular_huella_logica(
        request=request,
        punto_venta_numero=punto_venta_numero,
        total=total,
    )
    return payload_hash, huella


def _payload_lote_basico(
    empresa_id: int,
    punto_venta_id: int,
    fecha_fiscal: date,
    razon_social: str = "Cliente Lote SA",
) -> dict[str, object]:
    """Construye un payload fiscal sintético y estable para tests de lotes."""
    return {
        "empresa_id": empresa_id,
        "punto_venta_id": punto_venta_id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
        "razon_social": razon_social,
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


def _opciones_fechas(
    fecha_emision_modo: str = "archivo",
    fecha_emision_fija: date | str | None = None,
    concepto_modo: str = "productos",
    descripcion_item_modo: str = "archivo",
    descripcion_item_fija: str | None = None,
    punto_venta_modo: str = "archivo",
    punto_venta_numero: int | None = None,
    fecha_servicio_desde_fija: date | str | None = None,
    fecha_servicio_hasta_fija: date | str | None = None,
    fecha_vto_pago_fija: date | str | None = None,
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
    for key, value in {
        "fecha_emision_fija": fecha_emision_fija,
        "fecha_servicio_desde_fija": fecha_servicio_desde_fija,
        "fecha_servicio_hasta_fija": fecha_servicio_hasta_fija,
        "fecha_vto_pago_fija": fecha_vto_pago_fija,
    }.items():
        if value:
            data[key] = value.isoformat() if isinstance(value, date) else value
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


async def _persistir_comprobante_autorizado(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta: PuntoVenta,
    *,
    tipo_comprobante: int,
    numero: int,
    fecha_emision: date,
    cae: str,
    cae_vencimiento: date,
    total: Decimal,
) -> int:
    """Crea un comprobante sintético para fakes que simulan CAE autorizado."""
    comprobante = Comprobante(
        tipo_comprobante=tipo_comprobante,
        concepto=1,
        numero=numero,
        fecha_emision=fecha_emision,
        subtotal=total,
        descuento=Decimal("0.00"),
        iva_21=Decimal("0.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=total,
        cae=cae,
        cae_vencimiento=cae_vencimiento,
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=99,
        receptor_numero_documento="0",
        receptor_razon_social="A CONSUMIDOR FINAL",
        receptor_condicion_iva="Consumidor Final",
    )
    db_session.add(comprobante)
    await db_session.flush()
    return comprobante.id


async def _crear_lote_validado_por_api(
    client: AsyncClient,
    auth_headers: dict,
    empresa_cuit: str,
    nombre_archivo: str = "lote-resolucion.xlsx",
    total_grupos: int = 1,
) -> int:
    """Crea un lote validado usando el endpoint público de carga masiva."""
    archivo = (
        _build_lote_excel_multi_grupo(empresa_cuit, total_grupos)
        if total_grupos > 1
        else _build_lote_excel(empresa_cuit)
    )
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                nombre_archivo,
                archivo,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    return int(response.json()["lote"]["id"])


async def _marcar_grupos_lote(
    db_session: AsyncSession,
    lote_id: int,
    estados: list[str],
) -> list[LoteComprobanteGrupo]:
    """Actualiza estados de grupos y recalcula el lote en pruebas."""
    grupos = list(
        (
            await db_session.execute(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote_id)
                .order_by(LoteComprobanteGrupo.orden)
            )
        )
        .scalars()
        .all()
    )
    assert len(grupos) >= len(estados)
    for grupo, estado in zip(grupos, estados, strict=False):
        grupo.estado = estado
        grupo.mensajes_json = [f"Estado de prueba: {estado}"]
        if estado in {"autorizado", "requiere_reconciliacion"}:
            grupo.cae = CAE_TEST_NO_REAL
            grupo.numero_asignado = 100 + grupo.orden
        filas = list(
            (
                await db_session.execute(
                    select(LoteComprobanteFila).where(
                        LoteComprobanteFila.grupo_id == grupo.id
                    )
                )
            )
            .scalars()
            .all()
        )
        for fila in filas:
            fila.estado = estado
            fila.mensajes_json = grupo.mensajes_json

    lote = await db_session.get(LoteComprobante, lote_id)
    assert lote is not None
    await db_session.flush()
    service = LoteComprobantesService(db_session)
    await service._actualizar_estado_lote(lote)
    await db_session.commit()
    return grupos


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
            cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
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
async def test_validar_lote_productos_acepta_fechas_servicio_omitidas(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote de productos no debe exigir campos de servicio en multipart."""
    data = _opciones_fechas(concepto_modo="productos")
    for key in [
        "fecha_servicio_desde_modo",
        "fecha_servicio_hasta_modo",
        "fecha_vto_pago_modo",
    ]:
        data.pop(key)

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=data,
        files={
            "archivo": (
                "lote-productos-sin-servicio.xlsx",
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
    assert detalle.status_code == 200, detalle.text
    grupo = detalle.json()["grupos"][0]
    assert grupo["concepto"] == 1
    assert grupo["fecha_servicio_desde"] is None
    assert grupo["fecha_servicio_hasta"] is None
    assert grupo["fecha_vto_pago"] is None


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
async def test_validar_lote_acepta_fecha_fija_argentina(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe aceptar DD/MM/AAAA en fechas fijas del formulario."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            fecha_emision_modo="fija",
            fecha_emision_fija="20/05/2026",
        ),
        files={
            "archivo": (
                "lote-fecha-fija-argentina.xlsx",
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
    assert detalle.json()["grupos"][0]["fecha_emision"] == "2026-05-20"


@pytest.mark.asyncio
async def test_validar_lote_rechaza_fecha_fija_argentina_invalida(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Debe rechazar fechas fijas con calendario imposible."""
    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(
            fecha_emision_modo="fija",
            fecha_emision_fija="31/02/2026",
        ),
        files={
            "archivo": (
                "lote-fecha-fija-invalida.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 400
    assert "fecha_emision_fija debe ser una fecha válida" in response.json()["detail"]


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
async def test_validar_lote_nota_debito_requiere_comprobante_asociado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una nota de débito no puede quedar lista sin comprobante asociado."""
    test_empresa.condicion_iva = "Exento"
    await db_session.commit()

    response = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(concepto_modo="servicios"),
        files={
            "archivo": (
                "lote-nd-sin-asociado.xlsx",
                _build_lote_excel(
                    test_empresa.cuit,
                    tipo_comprobante=12,
                    concepto=2,
                    iva=0,
                    cliente_tipo_documento="",
                    cliente_numero_documento="",
                    cliente_razon_social="A CONSUMIDOR FINAL",
                    cliente_condicion_iva="Consumidor Final",
                    fecha_servicio_desde=date(2026, 5, 31),
                    fecha_servicio_hasta=date(2026, 5, 31),
                    fecha_vto_pago=date(2026, 5, 31),
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
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    test_certificado.ambiente = settings.arca_env
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=456,
            fecha_emision=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=456,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
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
    assert llamadas == 1

    replay = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
    )

    assert replay.status_code == 200, replay.text
    replay_data = replay.json()
    assert replay_data["en_progreso"] is False
    assert replay_data["lote"]["estado"] == "completado"
    assert replay_data["lote"]["grupos_emitidos"] == 1
    assert llamadas == 1

    detalle = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/resultados",
        headers=auth_headers,
    )
    assert detalle.status_code == 200
    grupo = detalle.json()["grupos"][0]
    assert grupo["estado"] == "autorizado"
    assert grupo["cae"] == CAE_TEST_NO_REAL


@pytest.mark.asyncio
async def test_procesar_lote_background_encola_lote_chico(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
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
    llamadas = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas
        llamadas += 1
        numero = 500 + llamadas
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=numero,
            fecha_emision=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=numero,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
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

    operacion = (
        (
            await db_session.execute(
                select(OperacionIdempotente).where(
                    OperacionIdempotente.idempotency_key == "idem-lote-test"
                )
            )
        )
        .scalars()
        .one()
    )
    assert operacion.estado == "en_proceso"
    assert operacion.response_json["en_progreso"] is True

    service = LoteComprobantesService(db_session)
    lote = await service.procesar_lote(lote_id, test_empresa.id, reanudar=True)
    await db_session.refresh(operacion)

    assert lote.estado == "completado"
    assert llamadas == 1
    assert operacion.estado == "finalizado"
    assert operacion.response_json["en_progreso"] is False
    assert operacion.response_json["lote"]["estado"] == "completado"


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

    async def fake_emitir(self, request, **kwargs):
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
        numero = 200 + llamadas
        cae = f"{CAE_TEST_NO_REAL_PREFIX}{llamadas}"
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=numero,
            fecha_emision=request.fecha_emision,
            cae=cae,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=numero,
            fecha=request.fecha_emision,
            cae=cae,
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
async def test_procesar_lote_usa_sublotes_arca_segun_regxreq(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote elegible se divide en sublotes según RegXReq."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    llamadas_batch: list[int] = []
    numero = 0

    async def fake_regxreq(self, empresa_id):
        return 2

    async def fake_emitir_lote(self, requests, max_registros=None, contextos=None):
        nonlocal numero
        llamadas_batch.append(len(requests))
        respuestas = []
        for request in requests:
            numero += 1
            cae = f"{CAE_TEST_NO_REAL_PREFIX}{numero}"
            comprobante_id = await _persistir_comprobante_autorizado(
                db_session,
                test_empresa,
                test_punto_venta,
                tipo_comprobante=request.tipo_comprobante,
                numero=numero,
                fecha_emision=request.fecha_emision,
                cae=cae,
                cae_vencimiento=date(2026, 3, 31),
                total=Decimal("1210.00"),
            )
            respuestas.append(
                EmitirComprobanteResponse(
                    exito=True,
                    comprobante_id=comprobante_id,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=1,
                    numero=numero,
                    fecha=request.fecha_emision,
                    cae=cae,
                    cae_vencimiento=date(2026, 3, 31),
                    total=Decimal("1210.00"),
                    mensaje="Comprobante autorizado",
                    errores=[],
                )
            )
        return respuestas

    async def fail_emitir_unitario(self, request, **kwargs):
        raise AssertionError("No debe usar emisión unitaria en sublotes de tamaño 2")

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.obtener_registros_maximos_por_request",
        fake_regxreq,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobantes_lote",
        fake_emitir_lote,
    )
    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.emitir_comprobante",
        fail_emitir_unitario,
    )

    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-batch-regxreq.xlsx",
                _build_lote_excel_multi_grupo(test_empresa.cuit, total_grupos=4),
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
    assert llamadas_batch == [2, 2]
    assert data["lote"]["estado"] == "completado"
    assert data["lote"]["metadata_json"]["arca_batch"]["reg_x_req"] == 2
    assert data["lote"]["metadata_json"]["arca_batch"]["chunk_size"] == 2
    assert data["lote"]["metadata_json"]["arca_batch"]["modo"] == "batch"


@pytest.mark.asyncio
async def test_procesar_lote_fallback_regxreq_degrada_a_unitario_con_aviso(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Si RegXReq no está disponible, el lote usa modo unitario y avisa."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)

    async def fake_regxreq(self, empresa_id):
        raise RuntimeError("RegXReq no disponible")

    async def fake_emitir(self, request, **kwargs):
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=456,
            fecha_emision=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=456,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
            mensaje="Comprobante autorizado",
            errores=[],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService.obtener_registros_maximos_por_request",
        fake_regxreq,
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
                "lote-fallback-regxreq.xlsx",
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
    arca_batch = data["lote"]["metadata_json"]["arca_batch"]
    assert arca_batch["modo"] == "unitario_fallback"
    assert arca_batch["fallback_unitario"] is True
    assert "RegXReq no disponible" in arca_batch["fallback_motivo"]
    assert "modo unitario" in data["lote"]["mensaje_resumen"]


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

    async def fake_emitir(self, request, **kwargs):
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=654,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL_ALT,
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
    assert grupo["cae"] == CAE_TEST_NO_REAL_ALT
    assert grupo["numero_asignado"] == 654

    service = LoteComprobantesService(db_session)
    lote = await service.obtener_lote(lote_id, test_empresa.id)
    assert service._lote_permite_reintento(lote) is False


@pytest.mark.asyncio
async def test_descartar_grupos_cierra_lote_con_descartes(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Descartar pendientes no emitidos debe cerrar un lote parcial."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-descartar-pendientes.xlsx",
        total_grupos=2,
    )
    grupos = await _marcar_grupos_lote(
        db_session,
        lote_id,
        ["autorizado", "fallido"],
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/descartar-grupos",
        headers=auth_headers,
        json={
            "grupo_ids": [grupos[1].id],
            "motivo": "Emitido manualmente en otro flujo operativo",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["lote"]
    assert data["estado"] == "cerrado_con_descartes"
    assert data["grupos_emitidos"] == 1
    assert data["grupos_descartados"] == 1

    grupo_descartado = await db_session.get(LoteComprobanteGrupo, grupos[1].id)
    assert grupo_descartado.estado == "descartado"


@pytest.mark.asyncio
async def test_reintentar_fallidos_exige_confirmacion_fecha_fiscal(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El reintento de fallidos también debe confirmar fecha fiscal exacta."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-sin-confirmacion.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["fallido"])

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={
            **auth_headers,
            "X-Idempotency-Key": "idem-reintento-sin-confirmacion",
        },
        json={"grupo_ids": []},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "confirmar la fecha fiscal exacta" in detail["mensaje"]
    assert "0001" in detail["mensaje"]


@pytest.mark.asyncio
async def test_reintentar_fallidos_reclama_grupo_antes_de_emitir(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El reintento debe sacar el grupo de fallido antes de pedir CAE."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-claim.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]
    estados_vistos: list[str] = []

    async def fake_emitir_locked(self, request, commit=True, **kwargs):
        estado = await db_session.scalar(
            select(LoteComprobanteGrupo.estado).where(
                LoteComprobanteGrupo.id == grupo.id
            )
        )
        estados_vistos.append(str(estado))
        assert commit is False
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=grupo.punto_venta_numero,
            numero=0,
            fecha=request.fecha_emision,
            total=Decimal("1210.00"),
            mensaje="Error controlado",
            errores=["Error controlado"],
        )

    monkeypatch.setattr(
        "app.services.facturacion_service.FacturacionService._emitir_comprobante_locked",
        fake_emitir_locked,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos",
        headers={**auth_headers, **_confirmacion_fecha_fiscal_header()},
        json={"grupo_ids": [grupo.id]},
    )

    assert response.status_code == 200, response.text
    assert estados_vistos == ["reintentando"]
    await db_session.refresh(grupo)
    assert grupo.estado == "fallido"


@pytest.mark.asyncio
async def test_reconciliar_externo_verifica_arca_y_crea_comprobante(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un comprobante manual se reconcilia solo si ARCA confirma los datos."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-externo.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_ALT,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "cae": CAE_TEST_NO_REAL_ALT,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["lote"]
    assert data["estado"] == "cerrado_reconciliado"
    assert data["grupos_reconciliados_externos"] == 1

    await db_session.refresh(grupo)
    assert grupo.estado == "autorizado_externo"
    assert grupo.numero_asignado == 456
    assert grupo.comprobante_id is not None
    comprobante = await db_session.get(Comprobante, grupo.comprobante_id)
    assert comprobante.origen_emision == "arca_web"
    assert comprobante.estado == "autorizado"


@pytest.mark.asyncio
async def test_reconciliar_externo_rechaza_receptor_distinto_en_arca(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No se debe vincular un comprobante ARCA emitido a otro receptor."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-receptor-distinto.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_38,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=30712345678,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "cae": CAE_TEST_NO_REAL_38,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "receptor informado por ARCA no coincide" in response.json()["detail"]
    await db_session.refresh(grupo)
    assert grupo.estado == "fallido"
    assert grupo.comprobante_id is None


@pytest.mark.asyncio
async def test_reconciliar_externo_rechaza_comprobante_ya_vinculado(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un comprobante externo no puede cerrar dos grupos distintos."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-externo-duplicado.xlsx",
        total_grupos=2,
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido", "fallido"])

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_39,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupos[0].fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    payload_base = {
        "tipo_comprobante": grupos[0].tipo_comprobante,
        "punto_venta_numero": grupos[0].punto_venta_numero,
        "numero": 456,
        "fecha_emision": str(grupos[0].fecha_emision),
        "total": 1210.0,
        "cae": CAE_TEST_NO_REAL_39,
        "motivo": "Emitido manualmente por ARCA Web",
    }
    primera = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={"comprobantes": [{**payload_base, "grupo_id": grupos[0].id}]},
    )
    assert primera.status_code == 200, primera.text

    segunda = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={"comprobantes": [{**payload_base, "grupo_id": grupos[1].id}]},
    )

    assert segunda.status_code == 400
    assert "ya está vinculado a otro grupo" in segunda.json()["detail"]
    await db_session.refresh(grupos[1])
    assert grupos[1].estado == "fallido"
    assert grupos[1].comprobante_id is None


@pytest.mark.asyncio
async def test_reconciliar_externo_resuelve_lote_con_reconciliacion_tecnica(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Los grupos inciertos deben poder cerrarse con verificación de ARCA."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-requiere-reconciliacion.xlsx",
    )
    grupos = await _marcar_grupos_lote(
        db_session,
        lote_id,
        ["requiere_reconciliacion"],
    )
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_36,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 789,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "motivo": "Recuperación luego de corte post-ARCA",
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["lote"]["estado"] == "cerrado_reconciliado"


@pytest.mark.asyncio
async def test_reconciliar_externo_resuelve_reintento_interrumpido(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un grupo reclamado para reintento debe cerrarse verificando ARCA."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reintento-interrumpido.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["reintentando"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_40,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 790,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "motivo": "Recuperación de reintento interrumpido",
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["lote"]["estado"] == "cerrado_reconciliado"


@pytest.mark.asyncio
async def test_reconciliar_externo_error_arca_responde_400_controlado(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un error esperado de consulta ARCA no debe escapar como 500."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-error-arca.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(self, *args, **kwargs):
            raise ArcaServiceError("Comprobante inexistente")

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert (
        "No se pudo verificar el comprobante externo contra ARCA"
        in response.json()["detail"]
    )


@pytest.mark.asyncio
async def test_reconciliar_externo_rechaza_arca_sin_cae(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una consulta ARCA autorizada pero sin CAE no puede cerrar el grupo."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-sin-cae.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido"])
    grupo = grupos[0]

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae="",
                cae_vencimiento="20260630",
                fecha_cbte=str(grupo.fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": _fecha_argentina(grupo.fecha_emision),
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "ARCA no devolvió un CAE válido" in response.json()["detail"]
    await db_session.refresh(grupo)
    assert grupo.estado == "fallido"
    assert grupo.comprobante_id is None


@pytest.mark.asyncio
async def test_reconciliar_externo_con_error_incompleto_responde_400(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un grupo observado sin payload fiscal completo no debe escapar como 500."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-con-error-incompleto.xlsx",
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["con_error"])
    grupo = grupos[0]
    fecha_emision = str(grupo.fecha_emision)
    grupo.payload_json = {}
    await db_session.commit()

    class FakeWsfeClient:
        async def fe_comp_consultar(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("No debe consultar ARCA con payload incompleto")

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupo.id,
                    "tipo_comprobante": grupo.tipo_comprobante,
                    "punto_venta_numero": grupo.punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": fecha_emision,
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "datos fiscales completos" in response.json()["detail"]


@pytest.mark.asyncio
async def test_reconciliar_externos_multi_item_es_atomico_si_un_item_falla(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Una reconciliación parcial fallida no debe dejar comprobantes huérfanos."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-reconciliar-atomico.xlsx",
        total_grupos=2,
    )
    grupos = await _marcar_grupos_lote(db_session, lote_id, ["fallido", "fallido"])
    consultas = 0

    class FakeWsfeClient:
        async def fe_comp_consultar(
            self,
            punto_venta: int,
            tipo_cbte: int,
            numero: int,
        ) -> ArcaComprobanteResponse:
            nonlocal consultas
            consultas += 1
            if consultas == 2:
                raise ArcaServiceError("Comprobante inexistente")
            return ArcaComprobanteResponse(
                punto_venta=punto_venta,
                tipo_cbte=tipo_cbte,
                numero=numero,
                cuit_emisor=test_empresa.cuit,
                cae=CAE_TEST_NO_REAL_37,
                cae_vencimiento="20260630",
                fecha_cbte=str(grupos[0].fecha_emision).replace("-", ""),
                fecha_proceso="20260601",
                imp_total=1210.0,
                imp_neto=1000.0,
                imp_iva=210.0,
                imp_op_ex=0.0,
                imp_tot_conc=0.0,
                imp_trib=0.0,
                moneda_id="PES",
                moneda_cotiz=1.0,
                tipo_doc=80,
                nro_doc=CUIT_RECEPTOR_TEST_NO_REAL_INT,
                resultado="A",
            )

    async def fake_get_wsfe_client(*args, **kwargs):
        return FakeWsfeClient()

    monkeypatch.setattr(
        "app.api.lotes_comprobantes.get_wsfe_client",
        fake_get_wsfe_client,
    )

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reconciliar-externos",
        headers=auth_headers,
        json={
            "comprobantes": [
                {
                    "grupo_id": grupos[0].id,
                    "tipo_comprobante": grupos[0].tipo_comprobante,
                    "punto_venta_numero": grupos[0].punto_venta_numero,
                    "numero": 456,
                    "fecha_emision": str(grupos[0].fecha_emision),
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                },
                {
                    "grupo_id": grupos[1].id,
                    "tipo_comprobante": grupos[1].tipo_comprobante,
                    "punto_venta_numero": grupos[1].punto_venta_numero,
                    "numero": 457,
                    "fecha_emision": str(grupos[1].fecha_emision),
                    "total": 1210.0,
                    "motivo": "Emitido manualmente por ARCA Web",
                },
            ]
        },
    )

    assert response.status_code == 400
    assert consultas == 2

    comprobantes = await db_session.scalar(
        select(func.count())
        .select_from(Comprobante)
        .where(Comprobante.origen_emision == "arca_web")
    )
    assert comprobantes == 0

    for grupo in grupos:
        await db_session.refresh(grupo)
        assert grupo.estado == "fallido"
        assert grupo.comprobante_id is None


@pytest.mark.asyncio
async def test_compactar_lote_cerrado_elimina_filas_y_bloquea_observado(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Compactar debe eliminar filas pesadas sin borrar grupos ni resumen."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-compactar.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["autorizado"])

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/compactar",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    lote_data = response.json()["lote"]
    assert lote_data["compactado_at"] is not None

    filas = await db_session.scalar(
        select(func.count())
        .select_from(LoteComprobanteFila)
        .where(LoteComprobanteFila.lote_id == lote_id)
    )
    grupos = await db_session.scalar(
        select(func.count())
        .select_from(LoteComprobanteGrupo)
        .where(LoteComprobanteGrupo.lote_id == lote_id)
    )
    assert filas == 0
    assert grupos == 1
    evento = (
        await db_session.execute(
            select(LoteComprobanteEvento).where(
                LoteComprobanteEvento.accion == "compactar_lote"
            )
        )
    ).scalar_one()
    assert evento.motivo == "Compactación para ahorro de almacenamiento"

    observado = await client.get(
        f"/api/lotes-comprobantes/{lote_id}/archivo-observado",
        headers=auth_headers,
    )
    assert observado.status_code == 400
    assert "compactado" in observado.json()["detail"]


@pytest.mark.asyncio
async def test_eliminar_lote_sin_emision_permite_y_conserva_evento(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Solo se elimina físicamente un lote sin emisión ni incertidumbre."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-eliminar-sin-emision.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["con_error"])

    response = await client.request(
        "DELETE",
        f"/api/lotes-comprobantes/{lote_id}",
        headers=auth_headers,
        json={"motivo": "Carga con archivo equivocado"},
    )

    assert response.status_code == 204, response.text
    assert await db_session.get(LoteComprobante, lote_id) is None

    evento = (
        await db_session.execute(
            select(LoteComprobanteEvento).where(
                LoteComprobanteEvento.accion == "eliminar_lote"
            )
        )
    ).scalar_one()
    assert evento.lote_id is None
    assert evento.metadata_json["lote_id_original"] == lote_id


@pytest.mark.asyncio
async def test_eliminar_lote_rechaza_emitidos_o_inciertos(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote con emisión o incertidumbre fiscal no puede borrarse."""
    lote_id = await _crear_lote_validado_por_api(
        client,
        auth_headers,
        test_empresa.cuit,
        nombre_archivo="lote-no-eliminar-emitido.xlsx",
    )
    await _marcar_grupos_lote(db_session, lote_id, ["autorizado"])

    response = await client.request(
        "DELETE",
        f"/api/lotes-comprobantes/{lote_id}",
        headers=auth_headers,
        json={"motivo": "No quiero conservarlo"},
    )

    assert response.status_code == 400
    assert "comprobantes emitidos" in response.json()["detail"]
    assert await db_session.get(LoteComprobante, lote_id) is not None


@pytest.mark.asyncio
async def test_reanudar_lote_vincula_comprobante_ya_guardado_sin_reemitir(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
):
    """Si el comprobante ya fue guardado, reanudar no debe volver a emitirlo."""
    fecha_fiscal = date(2026, 3, 20)
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
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
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]
    request_model = EmitirComprobanteRequest.model_validate(emitir_request)
    payload_hash, huella = _hashes_fiscales_request(
        request_model,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    db_session.add_all([lote, grupo, fila, comprobante])
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=fecha_fiscal,
        total=Decimal("1210.00"),
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=comprobante.cae,
        cae_vencimiento=comprobante.cae_vencimiento,
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=comprobante.id,
        lote_id=lote.id,
        grupo_id=grupo.id,
    )
    db_session.add(intento)
    await db_session.commit()
    await db_session.refresh(lote)
    lote_id = lote.id
    empresa_id = test_empresa.id
    comprobante_id = comprobante.id
    comprobante_numero = comprobante.numero
    db_session.expire_all()

    service = LoteComprobantesService(db_session)

    async def fail_emitir(_request, **kwargs):
        raise AssertionError("No debe reemitir un grupo ya guardado")

    service.facturacion_service.emitir_comprobante = fail_emitir

    resultado = await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    assert resultado.estado == "completado"
    assert resultado.finished_at is not None
    detalle = await service.obtener_lote(lote_id, empresa_id)
    assert detalle.grupos[0].estado == "autorizado"
    assert detalle.grupos[0].comprobante_id == comprobante_id
    assert detalle.grupos[0].numero_asignado == comprobante_numero


@pytest.mark.asyncio
async def test_reanudar_lote_stale_con_grupos_autorizados_cierra_sin_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un lote stale localmente emitido se cierra sin pedir nuevos CAE."""
    fecha_fiscal = date(2026, 3, 20)
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
        nombre_archivo="lote-stale-ya-autorizado.xlsx",
        archivo_hash="hash-stale-ya-autorizado",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        empresa_id=test_empresa.id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]
    request_model = EmitirComprobanteRequest.model_validate(emitir_request)
    payload_hash, huella = _hashes_fiscales_request(
        request_model,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    db_session.add_all([lote, comprobante])
    await db_session.flush()
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        payload_json=emitir_request,
        cae=comprobante.cae,
        numero_asignado=comprobante.numero,
        comprobante_id=comprobante.id,
        mensajes_json=["Comprobante autorizado."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="autorizado",
        datos_json={},
        mensajes_json=["Comprobante autorizado."],
    )
    db_session.add_all([grupo, fila])
    await db_session.flush()
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=comprobante.numero,
        fecha_emision=fecha_fiscal,
        total=Decimal("1210.00"),
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=comprobante.cae,
        cae_vencimiento=comprobante.cae_vencimiento,
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=comprobante.id,
        lote_id=lote.id,
        grupo_id=grupo.id,
    )
    db_session.add(intento)
    await db_session.commit()
    await db_session.refresh(lote)
    lote_id = lote.id
    empresa_id = test_empresa.id
    db_session.expire_all()

    service = LoteComprobantesService(db_session)

    async def fail_emitir(_request, **kwargs):
        raise AssertionError("No debe reemitir un lote localmente completo")

    service.facturacion_service.emitir_comprobante = fail_emitir

    resultado = await service.procesar_lote(lote_id, empresa_id, reanudar=True)

    assert resultado.estado == "completado"
    assert resultado.finished_at is not None
    assert resultado.grupos_emitidos == 1
    assert "Todos los comprobantes" in resultado.mensaje_resumen

    eventos = (
        (
            await db_session.execute(
                select(LoteComprobanteEvento).where(
                    LoteComprobanteEvento.lote_id == lote_id,
                    LoteComprobanteEvento.accion == "reconciliacion_local_stale",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].metadata_json["grupos_reconciliados"] == 0


@pytest.mark.asyncio
async def test_reanudar_lote_stale_con_pendientes_intactos_reencola_tras_preflight(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un lote stale parcial se reencola solo si los pendientes nunca pidieron CAE."""
    fecha_fiscal = date(2026, 3, 20)
    payload_autorizado = _payload_lote_basico(
        test_empresa.id,
        test_punto_venta.id,
        fecha_fiscal,
        razon_social="Cliente Autorizado SA",
    )
    payload_pendiente = _payload_lote_basico(
        test_empresa.id,
        test_punto_venta.id,
        fecha_fiscal,
        razon_social="Cliente Pendiente SA",
    )
    lote = LoteComprobante(
        nombre_archivo="lote-stale-parcial-intacto.xlsx",
        archivo_hash="hash-stale-parcial-intacto",
        estado="procesando",
        total_filas=2,
        total_grupos=2,
        empresa_id=test_empresa.id,
        metadata_json={
            "opciones_concepto": {"concepto_modo": "archivo"},
            "opciones_descripcion_item": {"descripcion_item_modo": "archivo"},
        },
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Autorizado SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]
    db_session.add_all([lote, comprobante])
    await db_session.flush()

    grupo_autorizado = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Autorizado SA",
        total_estimado=Decimal("1210.00"),
        payload_json=payload_autorizado,
        cae=comprobante.cae,
        numero_asignado=comprobante.numero,
        comprobante_id=comprobante.id,
        mensajes_json=["Comprobante autorizado."],
    )
    grupo_pendiente = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-002",
        orden=2,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Pendiente SA",
        total_estimado=Decimal("1210.00"),
        payload_json=payload_pendiente,
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    filas = [
        LoteComprobanteFila(
            lote=lote,
            grupo=grupo_autorizado,
            fila_excel=2,
            comprobante_ref="LOTE-001",
            estado="autorizado",
            datos_json={},
            mensajes_json=["Comprobante autorizado."],
        ),
        LoteComprobanteFila(
            lote=lote,
            grupo=grupo_pendiente,
            fila_excel=3,
            comprobante_ref="LOTE-002",
            estado="validado",
            datos_json={},
            mensajes_json=["Validado correctamente. Listo para emitir."],
        ),
    ]
    db_session.add_all([grupo_autorizado, grupo_pendiente, *filas])
    await db_session.flush()

    request_autorizado = EmitirComprobanteRequest.model_validate(payload_autorizado)
    payload_hash, huella = _hashes_fiscales_request(
        request_autorizado,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    db_session.add(
        IntentoEmisionFiscal(
            tipo_comprobante=6,
            punto_venta_numero=test_punto_venta.numero,
            numero_planificado=comprobante.numero,
            fecha_emision=fecha_fiscal,
            total=Decimal("1210.00"),
            receptor_tipo_documento=80,
            receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
            receptor_razon_social="Cliente Autorizado SA",
            payload_hash=payload_hash,
            huella_logica=huella,
            cae=comprobante.cae,
            cae_vencimiento=comprobante.cae_vencimiento,
            estado="autorizado",
            empresa_id=test_empresa.id,
            punto_venta_id=test_punto_venta.id,
            comprobante_id=comprobante.id,
            lote_id=lote.id,
            grupo_id=grupo_autorizado.id,
        )
    )
    lote_id = lote.id
    empresa_id = test_empresa.id
    punto_venta_id = test_punto_venta.id
    punto_venta_numero = test_punto_venta.numero
    await db_session.commit()
    db_session.expire_all()

    service = LoteComprobantesService(db_session)
    preflight_llamadas: list[dict[str, int]] = []

    async def fake_preflight(**kwargs):
        preflight_llamadas.append(dict(kwargs))
        return {
            **kwargs,
            "punto_venta_numero": punto_venta_numero,
            "proximo_numero": 78,
        }

    service.facturacion_service.verificar_numeracion_alineada_para_emision = (
        fake_preflight
    )

    resultado = await service.bloquear_lote_procesando_stale(
        lote_id,
        empresa_id,
    )

    assert resultado.estado == "en_cola"
    assert resultado.finished_at is None
    assert resultado.grupos_emitidos == 1
    assert resultado.grupos_validos == 1
    assert preflight_llamadas == [
        {
            "empresa_id": empresa_id,
            "punto_venta_id": punto_venta_id,
            "tipo_comprobante": 6,
        }
    ]

    detalle = await service.obtener_lote(lote_id, empresa_id)
    pendiente = next(
        grupo for grupo in detalle.grupos if grupo.comprobante_ref == "LOTE-002"
    )
    assert pendiente.estado == "validado"
    assert pendiente.cae is None
    assert pendiente.numero_asignado is None
    assert pendiente.comprobante_id is None

    eventos = (
        (
            await db_session.execute(
                select(LoteComprobanteEvento).where(
                    LoteComprobanteEvento.lote_id == lote_id,
                    LoteComprobanteEvento.accion == "reanudacion_segura_stale",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].metadata_json["estado_nuevo"] == "en_cola"
    assert eventos[0].metadata_json["grupos_intactos"] == 1


@pytest.mark.asyncio
async def test_reanudar_lote_stale_autorizado_sin_evidencia_requiere_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un estado autorizado sin evidencia fiscal no alcanza para cerrar stale."""
    fecha_fiscal = date(2026, 3, 20)
    lote = LoteComprobante(
        nombre_archivo="lote-stale-autorizado-sin-evidencia.xlsx",
        archivo_hash="hash-stale-autorizado-sin-evidencia",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        empresa_id=test_empresa.id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, comprobante])
    await db_session.flush()
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        cae=comprobante.cae,
        numero_asignado=comprobante.numero,
        comprobante_id=comprobante.id,
        mensajes_json=["Comprobante autorizado."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="autorizado",
        datos_json={},
        mensajes_json=["Comprobante autorizado."],
    )
    db_session.add_all([grupo, fila])
    await db_session.commit()
    await db_session.refresh(lote)

    service = LoteComprobantesService(db_session)

    async def fail_emitir(_request, **kwargs):
        raise AssertionError("No debe reemitir un lote stale")

    service.facturacion_service.emitir_comprobante = fail_emitir

    resultado = await service.procesar_lote(lote.id, test_empresa.id, reanudar=True)

    assert resultado.estado == "requiere_reconciliacion"
    assert resultado.grupos_emitidos == 1
    assert "reconciliar contra ARCA" in resultado.mensaje_resumen


@pytest.mark.asyncio
async def test_reanudar_lote_stale_autorizado_con_intento_incierto_requiere_reconciliacion(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un lote localmente autorizado no se cierra si conserva intentos inciertos."""
    fecha_fiscal = date(2026, 3, 20)
    lote = LoteComprobante(
        nombre_archivo="lote-stale-autorizado-incierto.xlsx",
        archivo_hash="hash-stale-autorizado-incierto",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        empresa_id=test_empresa.id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, comprobante])
    await db_session.flush()
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="autorizado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        cae=comprobante.cae,
        numero_asignado=comprobante.numero,
        comprobante_id=comprobante.id,
        mensajes_json=["Comprobante autorizado."],
    )
    fila = LoteComprobanteFila(
        lote=lote,
        grupo=grupo,
        fila_excel=2,
        comprobante_ref="LOTE-001",
        estado="autorizado",
        datos_json={},
        mensajes_json=["Comprobante autorizado."],
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=78,
        fecha_emision=fecha_fiscal,
        total=Decimal("1210.00"),
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        payload_hash="hash-payload-incierto",
        huella_logica="hash-huella-incierta",
        estado="en_proceso",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        lote_id=lote.id,
        grupo_id=grupo.id,
    )
    db_session.add_all([grupo, fila, intento])
    await db_session.commit()
    await db_session.refresh(lote)

    service = LoteComprobantesService(db_session)

    async def fail_emitir(_request, **kwargs):
        raise AssertionError("No debe reemitir un lote con intento incierto")

    service.facturacion_service.emitir_comprobante = fail_emitir

    resultado = await service.procesar_lote(lote.id, test_empresa.id, reanudar=True)

    assert resultado.estado == "requiere_reconciliacion"
    assert resultado.grupos_emitidos == 1
    assert "reconciliar contra ARCA" in resultado.mensaje_resumen


@pytest.mark.asyncio
async def test_reanudar_lote_no_vincula_comprobante_sin_intento_del_grupo(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
):
    """Un comprobante parecido pero sin intento del grupo no cierra el lote."""
    fecha_fiscal = date(2026, 3, 20)
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
        nombre_archivo="lote-reanudar-sin-intento.xlsx",
        archivo_hash="hash-reanudar-sin-intento",
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
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
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
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, grupo, fila, comprobante])
    await db_session.commit()
    await db_session.refresh(lote)

    service = LoteComprobantesService(db_session)

    async def fail_emitir(_request, **kwargs):
        raise AssertionError("No debe reemitir un grupo en estado incierto")

    service.facturacion_service.emitir_comprobante = fail_emitir

    resultado = await service.procesar_lote(lote.id, test_empresa.id, reanudar=True)

    assert resultado.estado == "requiere_reconciliacion"
    detalle = await service.obtener_lote(lote.id, test_empresa.id)
    assert detalle.grupos[0].estado == "requiere_reconciliacion"
    assert detalle.grupos[0].comprobante_id is None
    assert detalle.grupos[0].numero_asignado is None
    assert "reconciliar" in resultado.mensaje_resumen


@pytest.mark.asyncio
async def test_reanudar_lote_no_reconcilia_intentos_autorizados_duplicados(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Múltiples intentos autorizados del mismo grupo requieren auditoría."""
    fecha_fiscal = date(2026, 3, 20)
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
        nombre_archivo="lote-reanudar-intentos-duplicados.xlsx",
        archivo_hash="hash-reanudar-intentos-duplicados",
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
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
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
    comprobante_1 = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante_2 = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=78,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL_ALT,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    db_session.add_all([lote, grupo, fila, comprobante_1, comprobante_2])
    await db_session.flush()
    db_session.add_all(
        [
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=test_punto_venta.numero,
                numero_planificado=comprobante_1.numero,
                fecha_emision=fecha_fiscal,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash="hash-payload-grupo-001-a",
                huella_logica="hash-logica-grupo-001",
                cae=comprobante_1.cae,
                cae_vencimiento=comprobante_1.cae_vencimiento,
                estado="autorizado",
                empresa_id=test_empresa.id,
                punto_venta_id=test_punto_venta.id,
                comprobante_id=comprobante_1.id,
                lote_id=lote.id,
                grupo_id=grupo.id,
            ),
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=test_punto_venta.numero,
                numero_planificado=comprobante_2.numero,
                fecha_emision=fecha_fiscal,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash="hash-payload-grupo-001-b",
                huella_logica="hash-logica-grupo-001-b",
                cae=comprobante_2.cae,
                cae_vencimiento=comprobante_2.cae_vencimiento,
                estado="autorizado",
                empresa_id=test_empresa.id,
                punto_venta_id=test_punto_venta.id,
                comprobante_id=comprobante_2.id,
                lote_id=lote.id,
                grupo_id=grupo.id,
            ),
        ]
    )
    await db_session.commit()
    await db_session.refresh(lote)

    service = LoteComprobantesService(db_session)

    async def fail_emitir(_request, **kwargs):
        raise AssertionError("No debe reemitir un grupo con duplicados fiscales")

    service.facturacion_service.emitir_comprobante = fail_emitir

    resultado = await service.procesar_lote(lote.id, test_empresa.id, reanudar=True)

    assert resultado.estado == "requiere_reconciliacion"
    detalle = await service.obtener_lote(lote.id, test_empresa.id)
    assert detalle.grupos[0].estado == "requiere_reconciliacion"
    assert detalle.grupos[0].comprobante_id is None
    assert detalle.grupos[0].numero_asignado is None
    assert "reconciliar" in resultado.mensaje_resumen


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_intento_incierto_del_grupo(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Un intento incierto del mismo grupo bloquea el cierre local automático."""
    fecha_fiscal = date(2026, 3, 20)
    emitir_request = {
        "empresa_id": test_empresa.id,
        "punto_venta_id": test_punto_venta.id,
        "tipo_comprobante": 6,
        "concepto": 1,
        "fecha_emision": fecha_fiscal.isoformat(),
        "confirmacion_fecha_fiscal": True,
        "tipo_documento": 80,
        "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
    request = EmitirComprobanteRequest.model_validate(emitir_request)
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    lote = LoteComprobante(
        nombre_archivo="lote-intento-incierto.xlsx",
        archivo_hash="hash-intento-incierto",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    grupo = LoteComprobanteGrupo(
        lote=lote,
        comprobante_ref="LOTE-001",
        orden=1,
        estado="validado",
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        cliente_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        cliente_razon_social="Cliente Lote SA",
        total_estimado=Decimal("1210.00"),
        payload_json=emitir_request,
        mensajes_json=["Validado correctamente. Listo para emitir."],
    )
    comprobante = Comprobante(
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=fecha_fiscal,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=80,
        receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
        receptor_razon_social="Cliente Lote SA",
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]
    db_session.add_all([lote, grupo, comprobante])
    await db_session.flush()
    db_session.add_all(
        [
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=test_punto_venta.numero,
                numero_planificado=77,
                fecha_emision=fecha_fiscal,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash=payload_hash,
                huella_logica=huella,
                cae=comprobante.cae,
                cae_vencimiento=comprobante.cae_vencimiento,
                estado="autorizado",
                empresa_id=test_empresa.id,
                punto_venta_id=test_punto_venta.id,
                comprobante_id=comprobante.id,
                lote_id=lote.id,
                grupo_id=grupo.id,
            ),
            IntentoEmisionFiscal(
                tipo_comprobante=6,
                punto_venta_numero=test_punto_venta.numero,
                numero_planificado=78,
                fecha_emision=fecha_fiscal,
                total=Decimal("1210.00"),
                receptor_tipo_documento=80,
                receptor_numero_documento=CUIT_RECEPTOR_TEST_NO_REAL,
                receptor_razon_social="Cliente Lote SA",
                payload_hash=payload_hash,
                huella_logica=huella,
                estado="en_proceso",
                empresa_id=test_empresa.id,
                punto_venta_id=test_punto_venta.id,
                lote_id=lote.id,
                grupo_id=grupo.id,
            ),
        ]
    )
    await db_session.commit()

    assert (
        await LoteComprobantesService(
            db_session
        )._reconciliar_grupo_autorizado_existente(grupo, request)
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_payload_drift(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """La reconciliación local exige que la huella fiscal completa coincida."""
    request_original = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": "2026-03-20",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
            "razon_social": "Cliente Lote SA",
            "condicion_iva": "RI",
            "domicilio": "Av. Siempre Viva 123",
            "moneda": "PES",
            "cotizacion": "1",
            "guardar_cliente": False,
            "items": [
                {
                    "descripcion": "Servicio mensual original",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "1000",
                    "iva_porcentaje": "21",
                }
            ],
        }
    )
    request_drift = request_original.model_copy(deep=True)
    request_drift.items[0].descripcion = "Servicio mensual cambiado"
    payload_hash, huella = _hashes_fiscales_request(
        request_original,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request_original.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request_original.tipo_documento,
        receptor_numero_documento=request_original.numero_documento,
        receptor_razon_social=request_original.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=request_original.fecha_emision,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request_original.tipo_documento,
        receptor_numero_documento=request_original.numero_documento,
        receptor_razon_social=request_original.razon_social,
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual original",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request_drift,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_nota_usa_huella_del_intento_con_asociado(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """La huella autorizada del intento conserva el asociado fiscal de la nota."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 13,
            "concepto": 2,
            "fecha_emision": "2026-06-01",
            "fecha_servicio_desde": "2026-06-01",
            "fecha_servicio_hasta": "2026-06-01",
            "fecha_vto_pago": "2026-06-10",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 99,
            "numero_documento": "0",
            "razon_social": "A CONSUMIDOR FINAL",
            "condicion_iva": "CF",
            "moneda": "PES",
            "cotizacion": "1",
            "guardar_cliente": False,
            "comprobantes_asociados": [
                {
                    "tipo_comprobante": 11,
                    "punto_venta": test_punto_venta.numero,
                    "numero": 1645,
                    "fecha": "2026-04-30",
                    "cuit": test_empresa.cuit,
                }
            ],
            "items": [
                {
                    "descripcion": "Anulación por duplicado",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "59500",
                    "iva_porcentaje": "0",
                }
            ],
        }
    )
    total = Decimal("59500.00")
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        total,
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=request.tipo_comprobante,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=27,
        fecha_emision=request.fecha_emision,
        total=total,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 6, 11),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=request.tipo_comprobante,
        concepto=request.concepto,
        numero=27,
        fecha_emision=request.fecha_emision,
        fecha_servicio_desde=request.fecha_servicio_desde,
        fecha_servicio_hasta=request.fecha_servicio_hasta,
        fecha_vto_pago=request.fecha_vto_pago,
        fecha_vencimiento=request.fecha_vto_pago,
        subtotal=total,
        descuento=Decimal("0.00"),
        iva_21=Decimal("0.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=total,
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva="CF",
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Anulación por duplicado",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("59500"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("0"),
            subtotal=total,
            orden=0,
        )
    ]

    assert LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
        intento=intento,
        comprobante=comprobante,
        request=request,
        total=total,
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_snapshot_comprobante_distinto(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """El comprobante local debe conservar el snapshot completo del request."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": "2026-03-20",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
    )
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=request.fecha_emision,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva=request.condicion_iva,
        receptor_domicilio=request.domicilio,
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="hora",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_cae_vencimiento_distinto(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """El vencimiento de CAE local debe coincidir con el intento autorizado."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": "2026-03-20",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
    )
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=request.fecha_emision,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=date(2026, 5, 27),
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva=request.condicion_iva,
        receptor_domicilio=request.domicilio,
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_fechas_servicio_distintas(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """Las fechas fiscales de servicio deben coincidir con el request."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 2,
            "fecha_emision": "2026-03-20",
            "fecha_servicio_desde": "2026-03-01",
            "fecha_servicio_hasta": "2026-03-31",
            "fecha_vto_pago": "2026-04-10",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
    )
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=2,
        numero=77,
        fecha_emision=request.fecha_emision,
        fecha_servicio_desde=date(2026, 3, 2),
        fecha_servicio_hasta=request.fecha_servicio_hasta,
        fecha_vto_pago=request.fecha_vto_pago,
        fecha_vencimiento=request.fecha_vto_pago,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva=request.condicion_iva,
        receptor_domicilio=request.domicilio,
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request,
            total=Decimal("1210.00"),
        )
        is False
    )


@pytest.mark.asyncio
async def test_reconciliacion_local_rechaza_comprobante_con_tipo_doc_distinto(
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
) -> None:
    """La reconciliación local exige identidad fiscal completa del receptor."""
    request = EmitirComprobanteRequest.model_validate(
        {
            "empresa_id": test_empresa.id,
            "punto_venta_id": test_punto_venta.id,
            "tipo_comprobante": 6,
            "concepto": 1,
            "fecha_emision": "2026-03-20",
            "confirmacion_fecha_fiscal": True,
            "tipo_documento": 80,
            "numero_documento": CUIT_RECEPTOR_TEST_NO_REAL,
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
    )
    payload_hash, huella = _hashes_fiscales_request(
        request,
        test_punto_venta.numero,
        Decimal("1210.00"),
    )
    intento = IntentoEmisionFiscal(
        tipo_comprobante=6,
        punto_venta_numero=test_punto_venta.numero,
        numero_planificado=77,
        fecha_emision=request.fecha_emision,
        total=Decimal("1210.00"),
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        payload_hash=payload_hash,
        huella_logica=huella,
        cae=CAE_TEST_NO_REAL,
        cae_vencimiento=date(2026, 5, 26),
        estado="autorizado",
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        comprobante_id=123,
        lote_id=456,
        grupo_id=789,
    )
    comprobante = Comprobante(
        id=123,
        tipo_comprobante=6,
        concepto=1,
        numero=77,
        fecha_emision=request.fecha_emision,
        subtotal=Decimal("1000.00"),
        descuento=Decimal("0.00"),
        iva_21=Decimal("210.00"),
        iva_10_5=Decimal("0.00"),
        iva_27=Decimal("0.00"),
        otros_impuestos=Decimal("0.00"),
        total=Decimal("1210.00"),
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        moneda="PES",
        cotizacion=Decimal("1"),
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        receptor_tipo_documento=96,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva="RI",
        receptor_domicilio="Av. Siempre Viva 123",
    )
    comprobante.punto_venta = test_punto_venta
    comprobante.items = [
        ComprobanteItem(
            descripcion="Servicio mensual",
            cantidad=Decimal("1"),
            unidad="unidad",
            precio_unitario=Decimal("1000"),
            descuento_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("21"),
            subtotal=Decimal("1000.00"),
            orden=0,
        )
    ]

    assert (
        LoteComprobantesService(db_session)._intento_local_coincide_con_grupo(
            intento=intento,
            comprobante=comprobante,
            request=request,
            total=Decimal("1210.00"),
        )
        is False
    )


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
        headers={**auth_headers, "X-Idempotency-Key": "idem-lote-sin-confirmacion"},
    )

    assert response.status_code == 400
    detalle = response.json()["detail"]
    assert "confirmar la fecha fiscal exacta" in detalle["mensaje"]
    assert date.today().strftime("%d/%m/%y") in detalle["mensaje"]
    assert "0001" in detalle["mensaje"]
    assert "XX/XX/XX" not in detalle["mensaje"]


@pytest.mark.asyncio
async def test_procesar_lote_exige_idempotency_key(
    client: AsyncClient,
    auth_headers: dict,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """No debe procesar un lote confirmado sin clave de idempotencia."""
    test_certificado.ambiente = settings.arca_env
    validar = await client.post(
        "/api/lotes-comprobantes/validar",
        headers=auth_headers,
        data=_opciones_fechas(),
        files={
            "archivo": (
                "lote-sin-idem.xlsx",
                _build_lote_excel(test_empresa.cuit),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert validar.status_code == 200, validar.text
    lote_id = validar.json()["lote"]["id"]

    response = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/procesar",
        headers={
            **auth_headers,
            "X-Confirmacion-Fecha-Fiscal": (
                f"fechas={date.today().isoformat()};puntos_venta=1"
            ),
        },
    )

    assert response.status_code == 400
    assert "X-Idempotency-Key" in response.json()["detail"]["mensaje"]


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
async def test_tomar_lote_no_reanuda_procesando_stale(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """Un lote procesando vencido no debe volver a tomarse para emitir."""
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

    with pytest.raises(LoteComprobanteError, match="ya está siendo procesado"):
        await service._tomar_lote_para_procesamiento(
            lote_id=lote_id,
            empresa_id=test_empresa.id,
            procesamiento_async=True,
            modo_procesamiento="background",
            reanudar=True,
        )


@pytest.mark.asyncio
async def test_procesar_lote_procesando_stale_bloquea_y_preserva_intactos_sin_emitir(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    """El worker bloquea si no puede comprobar una reanudación segura."""
    test_certificado.ambiente = settings.arca_env
    monkeypatch.setattr(settings, "batch_sync_limit", 0)
    llamadas_emitir = 0

    async def fake_emitir(self, request, **kwargs):
        nonlocal llamadas_emitir
        llamadas_emitir += 1
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=432,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=987,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL_36,
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

    async def fail_preflight(**_kwargs):
        raise RuntimeError("preflight ARCA no disponible")

    service.facturacion_service.verificar_numeracion_alineada_para_emision = (
        fail_preflight
    )

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

    assert lote.estado == "requiere_reconciliacion"
    assert lote.grupos_validos == 1
    assert lote.grupos_emitidos == 0
    assert llamadas_emitir == 0
    assert "reconciliar contra ARCA" in lote.mensaje_resumen
    grupo = (
        (
            await db_session.execute(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id
                )
            )
        )
        .scalars()
        .one()
    )
    assert grupo.estado == "validado"
    assert grupo.cae is None
    assert grupo.numero_asignado is None
    assert grupo.comprobante_id is None
    eventos = (
        (
            await db_session.execute(
                select(LoteComprobanteEvento).where(
                    LoteComprobanteEvento.lote_id == lote_id,
                    LoteComprobanteEvento.accion == "bloqueo_operativo_no_reemitir",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].metadata_json["estado_nuevo"] == "requiere_reconciliacion"
    assert eventos[0].metadata_json["grupos_marcados_reconciliacion"] == 0
    assert eventos[0].metadata_json["grupos_intactos_preservados"] == 1
    assert "preflight ARCA no disponible" in eventos[0].metadata_json["preflight_error"]


@pytest.mark.asyncio
async def test_worker_no_procesa_en_cola_si_falla_bloqueo_stale(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
):
    """Si no puede bloquear un stale, el worker no sigue con nuevos CAE."""

    class SessionFactory:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    stale = LoteComprobante(
        nombre_archivo="lote-stale-worker.xlsx",
        archivo_hash="hash-stale-worker",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        updated_at=datetime.utcnow()
        - timedelta(minutes=settings.batch_processing_stale_minutes + 1),
    )
    en_cola = LoteComprobante(
        nombre_archivo="lote-en-cola-worker.xlsx",
        archivo_hash="hash-en-cola-worker",
        estado="en_cola",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([stale, en_cola])
    await db_session.commit()

    bloqueados: list[int] = []
    procesados: list[int] = []

    async def fail_bloquear(self, lote_id, empresa_id, **kwargs):
        bloqueados.append(lote_id)
        raise RuntimeError("fallo controlado de bloqueo stale")

    async def record_procesar(self, lote_id, empresa_id, **kwargs):
        procesados.append(lote_id)
        return await self.obtener_lote_resumen(lote_id, empresa_id)

    monkeypatch.setattr("app.services.lote_worker.AsyncSessionLocal", SessionFactory)
    monkeypatch.setattr(
        LoteComprobantesService,
        "bloquear_lote_procesando_stale",
        fail_bloquear,
    )
    monkeypatch.setattr(LoteComprobantesService, "procesar_lote", record_procesar)

    await LoteWorker().procesar_pendientes()

    assert bloqueados == [stale.id]
    assert procesados == []


@pytest.mark.asyncio
async def test_worker_no_procesa_en_cola_si_quedan_stale_fuera_del_batch(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
    test_empresa,
) -> None:
    """Si quedan stale fuera del batch, el worker posterga nuevos CAE."""

    class SessionFactory:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(settings, "batch_worker_batch_size", 1)
    vencido = datetime.utcnow() - timedelta(
        minutes=settings.batch_processing_stale_minutes + 3
    )
    stale_1 = LoteComprobante(
        nombre_archivo="lote-stale-worker-1.xlsx",
        archivo_hash="hash-stale-worker-1",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        updated_at=vencido,
    )
    stale_2 = LoteComprobante(
        nombre_archivo="lote-stale-worker-2.xlsx",
        archivo_hash="hash-stale-worker-2",
        estado="procesando",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
        updated_at=vencido + timedelta(minutes=1),
    )
    en_cola = LoteComprobante(
        nombre_archivo="lote-en-cola-worker-overflow.xlsx",
        archivo_hash="hash-en-cola-worker-overflow",
        estado="en_cola",
        total_filas=1,
        total_grupos=1,
        grupos_validos=1,
        empresa_id=test_empresa.id,
    )
    db_session.add_all([stale_1, stale_2, en_cola])
    await db_session.commit()

    bloqueados: list[int] = []
    procesados: list[int] = []

    async def fake_bloquear(self, lote_id, empresa_id, **kwargs):
        bloqueados.append(lote_id)
        lote = await self.db.get(LoteComprobante, lote_id)
        lote.estado = "requiere_reconciliacion"
        await self.db.commit()
        return lote

    async def record_procesar(self, lote_id, empresa_id, **kwargs):
        procesados.append(lote_id)
        return await self.obtener_lote_resumen(lote_id, empresa_id)

    monkeypatch.setattr("app.services.lote_worker.AsyncSessionLocal", SessionFactory)
    monkeypatch.setattr(
        LoteComprobantesService,
        "bloquear_lote_procesando_stale",
        fake_bloquear,
    )
    monkeypatch.setattr(LoteComprobantesService, "procesar_lote", record_procesar)

    await LoteWorker().procesar_pendientes()

    assert bloqueados == [stale_1.id]
    assert procesados == []


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
    detail = procesar.json()["detail"]
    assert "descripción facturada" in detail["mensaje"]


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

    async def fake_emitir(self, request, **kwargs):
        comprobante_id = await _persistir_comprobante_autorizado(
            db_session,
            test_empresa,
            test_punto_venta,
            tipo_comprobante=request.tipo_comprobante,
            numero=654,
            fecha_emision=request.fecha_emision,
            cae=CAE_TEST_NO_REAL_ALT,
            cae_vencimiento=date(2026, 3, 31),
            total=Decimal("1210.00"),
        )
        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=1,
            numero=654,
            fecha=request.fecha_emision,
            cae=CAE_TEST_NO_REAL_ALT,
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
