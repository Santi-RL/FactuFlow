"""Regresiones A-03 con hechos sintéticos, sin ARCA ni escrituras fiscales."""

from datetime import date
from decimal import Decimal, localcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.comprobante_totales import calcular_totales
from app.core.fiscal_storage import persisted_item_subtotal
from app.core.lecturas_fiscales import leer_bases_iva
from app.services.reportes_service import ReportesService
from app.api.reportes import reporte_clientes
from app.models.comprobante import Comprobante
from app.models.empresa import Empresa
from app.models.punto_venta import PuntoVenta


def item(precio="0.03", tasa="21", cantidad="1", descuento="0", orden=0):
    resultado = SimpleNamespace(
        cantidad=Decimal(cantidad),
        precio_unitario=Decimal(precio),
        descuento_porcentaje=Decimal(descuento),
        iva_porcentaje=Decimal(tasa),
        orden=orden,
    )
    resultado.subtotal = persisted_item_subtotal(resultado)
    return resultado


def comprobante(items=None, moneda="PES", tipo=1, numero=1, receptor="0"):
    items = items if items is not None else [item()]
    totales = calcular_totales(items)
    return SimpleNamespace(
        **{
            key: totales[key]
            for key in ("subtotal", "iva_21", "iva_10_5", "iva_27", "total")
        },
        id=numero,
        numero=numero,
        tipo_comprobante=tipo,
        items=items,
        fecha_emision=date(2026, 5, 15),
        moneda=moneda,
        cotizacion=Decimal("1500.123456"),
        punto_venta=SimpleNamespace(numero=1),
        cliente=None,
        receptor_razon_social="Receptor sintético",
        receptor_numero_documento=receptor,
    )


@pytest.mark.parametrize(
    "tasa,precio,base,iva",
    [
        ("21", "0.03", "0.03", "0.01"),
        ("10.5", "0.05", "0.05", "0.01"),
        ("27", "0.02", "0.02", "0.01"),
    ],
)
def test_base_desde_detalle_no_desde_iva_redondeado(tasa, precio, base, iva):
    comp = comprobante([item(precio, tasa)])
    lectura = leer_bases_iva(comp)
    key = tasa.replace(".", "_")
    assert lectura[f"gravado_{key}"] == Decimal(base)
    assert getattr(comp, f"iva_{key}") == Decimal(iva)
    assert lectura["bases_acreditadas"]


def test_medios_centavos_se_redondean_por_base_no_por_linea():
    comp = comprobante([item("0.005", orden=0), item("0.005", orden=1)])
    assert sum(linea.subtotal for linea in comp.items) == 0
    assert leer_bases_iva(comp)["gravado_21"] == Decimal("0.01")


def test_varias_tasas_descuentos_y_contexto_del_lector():
    comp = comprobante(
        [item("100", "21", "0.5", "10", 0), item("1.005", "27", orden=1)]
    )
    with localcontext() as contexto:
        contexto.prec = 4
        lectura = leer_bases_iva(comp)
    assert lectura["gravado_21"] == Decimal("45.00")
    assert lectura["gravado_27"] == Decimal("1.00")


@pytest.mark.parametrize("tipo", [1, 6, 11, 12, 13])
@pytest.mark.parametrize(
    "caso",
    [
        "sin_items",
        "importe_distinto",
        "tasa_no_soportada",
        "total_distinto",
        "subtotal_linea_distinto",
    ],
)
def test_historia_insuficiente_no_inventa_base(caso, tipo):
    comp = comprobante([item("100", "0")] if tipo in {11, 12, 13} else None, tipo=tipo)
    if caso == "sin_items":
        comp.items = []
    elif caso == "importe_distinto":
        comp.subtotal = Decimal("0.04")
    elif caso == "total_distinto":
        comp.total = Decimal("999")
    elif caso == "subtotal_linea_distinto":
        comp.items[0].subtotal = Decimal("999")
    else:
        comp.items[0].iva_porcentaje = Decimal("5")
    lectura = leer_bases_iva(comp)
    assert lectura["gravado_21"] is None
    assert not lectura["bases_acreditadas"]
    assert lectura["no_gravado"] is None and lectura["exento"] is None
    assert lectura["sin_iva_discriminado"] is None


@pytest.mark.parametrize("tipo", [11, 12, 13])
@pytest.mark.parametrize("tasa", ["10.5", "21", "27"])
def test_c_no_acredita_tasa_positiva_aunque_iva_redondee_a_cero(tipo, tasa):
    comp = comprobante([item("0.01", tasa)], tipo=tipo)
    assert comp.iva_21 == comp.iva_10_5 == comp.iva_27 == 0
    lectura = leer_bases_iva(comp)
    assert not lectura["bases_acreditadas"]
    assert lectura["sin_iva_discriminado"] is None


def test_c_y_cero_no_acreditan_exencion():
    c = leer_bases_iva(comprobante([item("100", "0")], tipo=11))
    b = leer_bases_iva(comprobante([item("100", "0")], tipo=6))
    assert c["sin_iva_discriminado"] == Decimal("100")
    assert b["sin_clasificacion"] == Decimal("100")
    assert c["exento"] is None and b["no_gravado"] is None


async def test_monedas_y_limite_ranking_son_independientes(monkeypatch):
    servicio = ReportesService()
    comps = [
        comprobante([item("100", "0")], moneda="PES", receptor="1"),
        comprobante([item("100", "0")], moneda="DOL", receptor="1", numero=2),
        comprobante([item("99", "0")], moneda="PES", receptor="2", numero=3),
        comprobante([item("99", "0")], moneda="DOL", receptor="2", numero=4),
    ]
    servicio.obtener_comprobantes_por_periodo = AsyncMock(return_value=comps)
    desde, hasta = date(2026, 5, 1), date(2026, 5, 31)
    ventas = await servicio.generar_reporte_ventas(None, 1, desde, hasta)
    iva = await servicio.generar_reporte_iva(None, 1, 5, 2026)
    ranking = await servicio.obtener_ranking_clientes(None, 1, desde, hasta, 1)
    assert ventas["resumen"]["total_neto"] is None
    assert iva["resumen"]["total_neto"] is None
    assert [Decimal(g["total_neto"]) for g in ventas["por_moneda"]] == [
        Decimal("199"),
        Decimal("199"),
    ]
    assert len(ranking) == 2
    assert {r["moneda"] for r in ranking} == {"PES", "DOL"}
    assert all(Decimal(r["total_facturado"]) == 100 for r in ranking)
    assert ventas["comprobantes"][1]["cotizacion"] == "1500.123456"
    monkeypatch.setattr("app.api.reportes.reportes_service", servicio)
    api = await reporte_clientes(desde, hasta, 1, None, None, 1)
    assert api["total_general"] is None
    assert {g["moneda"] for g in api["por_moneda"]} == {"PES", "DOL"}


async def test_nc_y_bases_desconocidas_no_ocultan_totales():
    servicio = ReportesService()
    nc = comprobante(tipo=3)
    incompleto = comprobante(numero=2)
    incompleto.items = []
    servicio.obtener_comprobantes_por_periodo = AsyncMock(return_value=[nc, incompleto])
    reporte = await servicio.generar_reporte_iva(None, 1, 5, 2026)
    assert reporte["comprobantes"][0]["gravado_21"] == "-0.03"
    assert reporte["resumen"]["gravado_21"] is None
    assert Decimal(reporte["resumen"]["total_neto"]) == 0
    assert Decimal(reporte["resumen"]["total_iva"]) == 0
    assert reporte["resumen"]["cantidad_bases_no_acreditadas"] == 1


async def test_moneda_desconocida_no_se_convierte_en_pesos():
    servicio = ReportesService()
    servicio.obtener_comprobantes_por_periodo = AsyncMock(
        return_value=[comprobante(moneda="XYZ")]
    )
    reporte = await servicio.generar_reporte_ventas(
        None, 1, date(2026, 5, 1), date(2026, 5, 31)
    )
    assert reporte["resumen"]["moneda"] == "XYZ"
    assert reporte["por_moneda"][0]["moneda"] == "XYZ"


async def test_lectura_sql_aisla_emisor_periodo_y_autorizados(db_session, test_empresa):
    otra = Empresa(
        razon_social="Otro emisor sintético",
        cuit="20999999999",
        condicion_iva="RI",
        domicilio="Domicilio sintético",
        localidad="Localidad sintética",
        provincia="Provincia sintética",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    db_session.add(otra)
    await db_session.flush()
    puntos = [
        PuntoVenta(numero=1, empresa_id=empresa.id, activo=True)
        for empresa in (test_empresa, otra)
    ]
    db_session.add_all(puntos)
    await db_session.flush()
    for idx, (punto, fecha, estado) in enumerate(
        [
            (puntos[0], date(2026, 5, 15), "autorizado"),
            (puntos[1], date(2026, 5, 15), "autorizado"),
            (puntos[0], date(2026, 6, 15), "autorizado"),
            (puntos[0], date(2026, 5, 15), "borrador"),
        ],
        1,
    ):
        db_session.add(
            Comprobante(
                empresa_id=punto.empresa_id,
                punto_venta_id=punto.id,
                numero=idx,
                tipo_comprobante=11,
                concepto=1,
                fecha_emision=fecha,
                subtotal=Decimal("100"),
                total=Decimal("100"),
                estado=estado,
                moneda="DOL",
                cotizacion=Decimal("1500.123456"),
                cae="12345678901234" if estado == "autorizado" else None,
                cae_vencimiento=date(2026, 6, 30) if estado == "autorizado" else None,
            )
        )
    await db_session.commit()
    servicio = ReportesService()
    filas = await servicio.obtener_comprobantes_por_periodo(
        db_session, test_empresa.id, date(2026, 5, 1), date(2026, 5, 31)
    )
    assert [fila.numero for fila in filas] == [1]
    reporte = await servicio.generar_reporte_ventas(
        db_session, test_empresa.id, date(2026, 5, 1), date(2026, 5, 31)
    )
    assert reporte["resumen"]["moneda"] == "DOL"
    assert Decimal(reporte["resumen"]["total_neto"]) == 100
