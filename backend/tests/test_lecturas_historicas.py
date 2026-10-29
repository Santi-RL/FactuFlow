"""Identidad histórica PF-04/PF-02 con datos sintéticos y cero red fiscal."""

import base64
import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pypdf import PdfReader
from sqlalchemy import event, select, update
from sqlalchemy.orm import joinedload

from app.arca.models import CAEResponse
from app.core.config import settings
from app.core.evidencia_fiscal import hash_evidencia
from app.models.comprobante import Comprobante
from app.models.idempotencia_fiscal import IntentoEmisionFiscal as Intento
from app.models.punto_venta import PuntoVenta
from app.services.facturacion_service import FacturacionService
from app.services.lecturas_historicas_service import (
    HistoriaNoVerificableError,
    cargar_lecturas_historicas,
    proyectar_original,
)
from app.services.pdf_service import PDFService
from app.services.reportes_service import ReportesService
from tests import test_evidencia_fiscal as evidencia_tests
from tests.test_evidencia_fiscal import _request
from tests.test_facturacion_service import (
    _crear_operacion_rece_sintetica,
    _fijar_reloj_facturacion,
)


@pytest.fixture
def evidencia():
    return evidencia_tests.evidencia.__wrapped__()


async def crear_historia(
    db,
    empresa,
    monkeypatch,
    *,
    batch=False,
    terminar_operacion=False,
    condicion_receptor="CF",
):
    """Ejercita el escritor vigente mediante un doble local, nunca ARCA real."""
    monkeypatch.setattr(settings, "arca_env", "produccion")
    _fijar_reloj_facturacion(monkeypatch)
    empresa.razon_social = "Emisor original sintético"
    empresa.ingresos_brutos = "IB-0001"
    punto = PuntoVenta(
        numero=5,
        activo=True,
        es_webservice=True,
        empresa_id=empresa.id,
        revision_fiscal=1,
    )
    db.add(punto)
    await db.commit()
    requests = [
        _request(empresa.id, punto.id, f"Receptor sintético {i}")
        for i in range(2 if batch else 1)
    ]
    for request in requests:
        request.condicion_iva = condicion_receptor
    operacion, contexto, metadata = await _crear_operacion_rece_sintetica(
        db,
        empresa=empresa,
        punto_venta=punto,
        requests=requests,
        batch=batch,
    )

    class WSFE:
        cuit = empresa.cuit
        config = SimpleNamespace(ambiente="produccion")

        async def fe_param_get_ptos_venta(self):
            return [SimpleNamespace(numero=5, bloqueado="N", emision_tipo="CAE")]

        async def fe_comp_ultimo_autorizado(self, *_args):
            return 0

        async def fe_cae_solicitar_lote(self, solicitudes):
            return [
                CAEResponse(
                    cae="12345678901234",
                    cae_vencimiento="20260818",
                    numero_comprobante=s.cbte_desde,
                    tipo_cbte=s.tipo_cbte,
                    punto_venta=s.punto_venta,
                    resultado="A",
                )
                for s in solicitudes
            ]

        async def fe_cae_solicitar(self, solicitud):
            return (await self.fe_cae_solicitar_lote([solicitud]))[0]

    monkeypatch.setattr(
        FacturacionService, "_obtener_cliente_wsfe", AsyncMock(return_value=WSFE())
    )
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_certificado_activo",
        AsyncMock(return_value=SimpleNamespace()),
    )
    service = FacturacionService(db)
    if batch:
        respuestas = await service.emitir_comprobantes_lote(
            requests, contextos=metadata
        )
    else:
        respuestas = [
            await service.emitir_comprobante(
                requests[0],
                operacion_id=operacion.id,
                contexto_rece=contexto,
                contextos_operacion=[contexto],
            )
        ]
    assert all(r.exito for r in respuestas)
    if terminar_operacion:
        from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService

        await IdempotenciaFiscalService(db).guardar_resultado_operacion_sync(
            operacion, response_json=respuestas[0], estado="finalizado"
        )
    # Desde aquí cualquier consulta fiscal sería un defecto del lector.
    monkeypatch.setattr(
        FacturacionService,
        "_obtener_cliente_wsfe",
        AsyncMock(side_effect=AssertionError("Red fiscal en una lectura")),
    )
    resultado = await db.execute(
        select(Comprobante)
        .options(
            joinedload(Comprobante.empresa),
            joinedload(Comprobante.punto_venta),
            joinedload(Comprobante.cliente),
            joinedload(Comprobante.items),
        )
        .order_by(Comprobante.numero)
    )
    comprobantes = list(resultado.unique().scalars())
    return comprobantes, punto


@pytest.fixture
async def historia(db_session, test_empresa, monkeypatch):
    return await crear_historia(db_session, test_empresa, monkeypatch)


def comp_de_evidencia(evidencia):
    intento, empresa, request, wsfe, _ = evidencia
    intento.estado = "autorizado"
    intento.comprobante_id = 12
    intento.fecha_emision = request.fecha_emision
    intento.total = wsfe.imp_total
    intento.receptor_tipo_documento = request.tipo_documento
    intento.receptor_numero_documento = request.numero_documento
    intento.cae = "12345678901234"
    intento.cae_vencimiento = date(2026, 8, 18)
    comp = SimpleNamespace(
        id=12,
        empresa_id=intento.empresa_id,
        punto_venta_id=intento.punto_venta_id,
        tipo_comprobante=intento.tipo_comprobante,
        numero=intento.numero_planificado,
        fecha_emision=request.fecha_emision,
        total=wsfe.imp_total,
        cae=intento.cae,
        cae_vencimiento=intento.cae_vencimiento,
        estado="autorizado",
        receptor_tipo_documento=request.tipo_documento,
        receptor_numero_documento=request.numero_documento,
        receptor_razon_social=request.razon_social,
        receptor_condicion_iva=request.condicion_iva,
        moneda=request.moneda,
        cotizacion=request.cotizacion,
    )
    return comp, intento


def test_campos_originales_nulos_no_se_enriquecen(evidencia):
    comp, intento = comp_de_evidencia(evidencia)
    lectura = proyectar_original(comp, intento)
    assert lectura.cobertura == "incompleta"
    assert lectura.emisor.domicilio is None
    assert lectura.emisor.razon_social == "Emisor original"
    assert lectura.punto_venta_numero == 5


@pytest.mark.parametrize("batch", [False, True])
async def test_alias_iva_se_congela_despues_de_normalizar_en_ambos_escritores(
    db_session, test_empresa, monkeypatch, batch
):
    comps, _ = await crear_historia(
        db_session,
        test_empresa,
        monkeypatch,
        batch=batch,
        condicion_receptor="  Consumidor final  ",
    )
    fuentes = list(await db_session.scalars(select(Intento)))
    assert all(
        json.loads(f.evidencia_json)["presentacion"]["receptor"]["condicion_iva"]
        == "CF"
        for f in fuentes
    )
    assert all(comp.receptor_condicion_iva == "CF" for comp in comps)
    lecturas = await cargar_lecturas_historicas(db_session, comps)
    assert all(lectura.cobertura == "completa" for lectura in lecturas.values())


def test_cuit_original_cero_no_acredita_un_qr(evidencia):
    from app.core.evidencia_fiscal import EvidenciaFiscalError

    comp, intento = comp_de_evidencia(evidencia)
    doc = json.loads(intento.evidencia_json)
    doc["contexto"]["cuit"] = "00000000000"
    intento.evidencia_json = json.dumps(
        doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    intento.evidencia_hash = hash_evidencia(intento.evidencia_json)
    with pytest.raises(EvidenciaFiscalError):
        proyectar_original(comp, intento)


@pytest.mark.parametrize("tipo", [1, 2, 3, 6, 7, 8, 11, 12, 13])
def test_tipos_soportados_sin_recalcular(evidencia, tipo):
    comp, intento = comp_de_evidencia(evidencia)
    doc = json.loads(intento.evidencia_json)
    doc["contexto"]["tipo_comprobante"] = tipo
    doc["solicitud_wsfe"]["tipo_cbte"] = tipo
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    intento.evidencia_json, intento.evidencia_hash = raw, hash_evidencia(raw)
    intento.tipo_comprobante = comp.tipo_comprobante = tipo
    assert proyectar_original(comp, intento).punto_venta_numero == 5


@pytest.mark.parametrize("batch", [False, True])
async def test_original_en_todos_los_consumidores(
    db_session, test_empresa, monkeypatch, batch
):
    comps, punto = await crear_historia(
        db_session, test_empresa, monkeypatch, batch=batch
    )
    before = [(c.numero, c.total, c.cae, c.estado) for c in comps]
    test_empresa.razon_social = "Ficha cambiada"
    test_empresa.cuit = "20999999999"
    test_empresa.domicilio = "Domicilio nuevo"
    test_empresa.localidad = "Localidad nueva"
    test_empresa.provincia = "Provincia nueva"
    test_empresa.condicion_iva = "Exento"
    test_empresa.ingresos_brutos = "IB-CAMBIADO"
    test_empresa.inicio_actividades = date(2026, 1, 1)
    punto.numero = 99
    await db_session.commit()
    # El ambiente actual no selecciona ni valida historia.
    monkeypatch.setattr(settings, "arca_env", "homologacion")
    lecturas = await cargar_lecturas_historicas(db_session, comps)
    pdf_service = PDFService()
    for comp in comps:
        lectura = lecturas[comp.id]
        assert lectura.cobertura == "completa"
        assert lectura.emisor.razon_social == "Emisor original sintético"
        assert lectura.emisor.cuit == "20123456789"
        assert lectura.emisor.ingresos_brutos == "IB-0001"
        payload = pdf_service._generar_qr_payload_arca(comp, lectura)
        assert payload["ptoVta"] == 5 and payload["cuit"] == 20123456789
        url = pdf_service._generar_qr_url_arca(comp, lectura)
        assert json.loads(base64.b64decode(url.split("?p=")[1]))["ptoVta"] == 5
        pdf = await pdf_service.generar_pdf_comprobante(comp, test_empresa, lectura)
        text = " ".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
        assert "Emisor original sintético" in text and "Ficha cambiada" not in text
        assert "0005" in text and "0099" not in text
    reportes = ReportesService()
    ventas = await reportes.generar_reporte_ventas(
        db_session, test_empresa.id, date(2026, 8, 1), date(2026, 8, 31)
    )
    iva = await reportes.generar_reporte_iva(db_session, test_empresa.id, 8, 2026)
    for reporte in (ventas, iva):
        assert len(reporte["comprobantes"]) == len(comps)
        assert all(
            c["numero_completo"].startswith("0005-") for c in reporte["comprobantes"]
        )
        assert all(
            c["datos_historicos"]["cobertura"] == "completa"
            for c in reporte["comprobantes"]
        )
    assert before == [(c.numero, c.total, c.cae, c.estado) for c in comps]
    assert not db_session.dirty and not db_session.new and not db_session.deleted


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("cae", "99999999999999"),
        ("cae_vencimiento", date(2026, 8, 19)),
        ("total", Decimal("1")),
        ("numero", 999),
        ("empresa_id", 999),
        ("punto_venta_id", 999),
        ("fecha_emision", date(2026, 8, 10)),
        ("receptor_numero_documento", "99999"),
        ("receptor_tipo_documento", 80),
        ("receptor_razon_social", "Receptor ajeno"),
        ("moneda", "DOL"),
        ("cotizacion", Decimal("2")),
        ("estado", "pendiente"),
    ],
)
def test_rechaza_contradiccion_sin_transiciones(evidencia, campo, valor):
    comp, intento = comp_de_evidencia(evidencia)
    setattr(comp, campo, valor)
    from app.core.evidencia_fiscal import EvidenciaFiscalError

    with pytest.raises(EvidenciaFiscalError):
        proyectar_original(comp, intento)
    assert intento.estado == "autorizado"


@pytest.mark.parametrize("caso", ["hash", "json", "cruzado", "doble", "cae", "ausente"])
async def test_api_cobertura_y_contencion_pdf(
    historia, db_session, client, auth_headers, caso, monkeypatch
):
    comps, punto = historia
    comp = comps[0]
    if caso in {"hash", "json", "ausente"}:
        valores = {
            "hash": {"evidencia_hash": "0" * 64},
            "json": {"evidencia_json": "{}"},
            "ausente": {
                "evidencia_version": None,
                "evidencia_hash": None,
                "evidencia_json": None,
            },
        }[caso]
        await db_session.execute(
            update(Intento).where(Intento.comprobante_id == comp.id).values(**valores)
        )
    elif caso == "cae":
        await db_session.execute(
            update(Intento)
            .where(Intento.comprobante_id == comp.id)
            .values(cae="99999999999999")
        )
    else:
        empresa_id, punto_id = comp.empresa_id, punto.id
        if caso == "cruzado":
            from app.models.empresa import Empresa

            empresa = Empresa(
                razon_social="Emisor ajeno",
                cuit="20999999999",
                condicion_iva="RI",
                domicilio="Otra calle",
                localidad="Otra",
                provincia="Otra",
                codigo_postal="1000",
                inicio_actividades=date(2020, 1, 1),
            )
            db_session.add(empresa)
            await db_session.flush()
            p = PuntoVenta(numero=5, empresa_id=empresa.id)
            db_session.add(p)
            await db_session.flush()
            empresa_id, punto_id = empresa.id, p.id
        db_session.add(
            Intento(
                empresa_id=empresa_id,
                punto_venta_id=punto_id,
                punto_venta_numero=5,
                tipo_comprobante=6,
                numero_planificado=99,
                fecha_emision=comp.fecha_emision,
                total=comp.total,
                payload_hash="a" * 64,
                huella_logica="b" * 64,
                estado="autorizado",
                comprobante_id=comp.id,
                cae=comp.cae,
                cae_vencimiento=comp.cae_vencimiento,
                **(
                    {
                        "evidencia_version": "solicitud_fiscal/1",
                        "evidencia_json": "DOCUMENTO-AJENO-NO-CARGAR",
                        "evidencia_hash": "a" * 64,
                    }
                    if caso == "cruzado"
                    else {}
                ),
            )
        )
    await db_session.commit()
    if caso == "cruzado":
        execute = db_session.execute

        async def comprobar_aislamiento(statement, *args, **kwargs):
            resultado = await execute(statement, *args, **kwargs)
            if "presente" in resultado.keys():
                congelado = resultado.freeze()
                for fila in congelado():
                    if fila.empresa_id != comp.empresa_id:
                        assert fila.evidencia_json is None
                        assert fila.receptor_numero_documento is None
                return congelado()
            return resultado

        monkeypatch.setattr(db_session, "execute", comprobar_aislamiento)
    resultado = await client.get(f"/api/comprobantes/{comp.id}", headers=auth_headers)
    assert resultado.status_code == 200
    cobertura = "ausente" if caso == "ausente" else "no_verificable"
    assert resultado.json()["datos_historicos"]["cobertura"] == cobertura
    lista = await client.get("/api/comprobantes/?per_page=1", headers=auth_headers)
    assert lista.json()["total"] == 1
    assert lista.json()["items"][0]["datos_historicos"]["cobertura"] == cobertura
    for ruta in (
        f"/api/pdf/comprobante/{comp.id}",
        f"/api/pdf/comprobante/{comp.id}/preview",
    ):
        respuesta = await client.get(ruta, headers=auth_headers)
        assert respuesta.status_code == (200 if caso == "ausente" else 409)
        if caso != "ausente":
            assert "Datos históricos no verificados" in respuesta.json()["detail"]
            assert "hash" not in respuesta.text and "Emisor ajeno" not in respuesta.text
    assert comp.estado == "autorizado"
    for ruta in (
        "/api/reportes/ventas?desde=2026-08-01&hasta=2026-08-31",
        "/api/reportes/iva-ventas?periodo_mes=8&periodo_anio=2026",
    ):
        respuesta = await client.get(ruta, headers=auth_headers)
        assert respuesta.status_code == 200
        fila = respuesta.json()["comprobantes"][0]
        assert fila["datos_historicos"]["cobertura"] == cobertura
        assert Decimal(fila["total"]) == comp.total


async def test_lectura_y_error_preservan_todas_las_filas(historia, db_session):
    from app.core.database import Base

    comps, _ = historia

    async def snapshot():
        return {
            table.name: (
                await db_session.execute(
                    select(table).order_by(*table.primary_key.columns)
                )
            ).all()
            for table in Base.metadata.tables.values()
        }

    before = await snapshot()
    lectura = (await cargar_lecturas_historicas(db_session, comps))[comps[0].id]
    await PDFService().generar_pdf_comprobante(comps[0], comps[0].empresa, lectura)
    with pytest.raises(HistoriaNoVerificableError):
        await PDFService().generar_pdf_comprobante(
            comps[0],
            comps[0].empresa,
            lectura.model_copy(update={"cobertura": "no_verificable"}),
        )
    assert before == await snapshot()


@pytest.mark.parametrize("caso", ["version", "json", "contexto", "fecha", "parcial"])
def test_no_verificable_no_es_ausente(evidencia, caso):
    comp, intento = comp_de_evidencia(evidencia)
    if caso == "version":
        intento.evidencia_version = "solicitud_fiscal/99"
    elif caso == "json":
        intento.evidencia_json = "{"
        intento.evidencia_hash = hash_evidencia("{")
    elif caso == "parcial":
        intento.evidencia_json = None
    else:
        doc = json.loads(intento.evidencia_json)
        if caso == "contexto":
            doc["contexto"]["empresa_id"] = 999
        else:
            doc["presentacion"]["emisor"]["inicio_actividades"] = "2020-02-30"
        intento.evidencia_json = json.dumps(
            doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        intento.evidencia_hash = hash_evidencia(intento.evidencia_json)
    from app.core.evidencia_fiscal import EvidenciaFiscalError

    with pytest.raises((EvidenciaFiscalError, ValueError)):
        proyectar_original(comp, intento)


@pytest.mark.parametrize("muchas_fuentes", [False, True])
async def test_pagina_periodo_sin_n_mas_uno_ni_escrituras(
    historia, db_session, muchas_fuentes
):
    import time
    import tracemalloc
    from sqlalchemy import insert

    comps, _ = historia
    original = comps[0]
    filas = []
    for numero in range(2, 203):
        filas.append(
            dict(
                empresa_id=original.empresa_id,
                punto_venta_id=original.punto_venta_id,
                tipo_comprobante=6,
                concepto=1,
                numero=numero,
                fecha_emision=original.fecha_emision,
                subtotal=original.subtotal,
                total=original.total,
                iva_21=original.iva_21,
                receptor_tipo_documento=original.receptor_tipo_documento,
                receptor_numero_documento=original.receptor_numero_documento,
                receptor_razon_social=original.receptor_razon_social,
                receptor_condicion_iva=original.receptor_condicion_iva,
                cae=original.cae,
                cae_vencimiento=original.cae_vencimiento,
                estado="autorizado",
            )
        )
    await db_session.execute(insert(Comprobante), filas)
    await db_session.commit()
    result = await db_session.execute(
        select(Comprobante)
        .options(
            joinedload(Comprobante.empresa),
            joinedload(Comprobante.punto_venta),
        )
        .order_by(Comprobante.numero)
    )
    comps = list(result.scalars())
    if muchas_fuentes:
        fuente = (await db_session.execute(select(Intento.__table__))).mappings().one()
        nuevos = []
        for ordinal, comp in enumerate(comps[1:], start=1):
            row = dict(fuente)
            row.update(
                id=fuente["id"] + ordinal,
                comprobante_id=comp.id,
                numero_planificado=comp.numero,
            )
            doc = json.loads(row["evidencia_json"])
            doc["contexto"].update(id=row["id"], numero_planificado=comp.numero)
            doc["solicitud_wsfe"].update(cbte_desde=comp.numero, cbte_hasta=comp.numero)
            row["evidencia_json"] = json.dumps(
                doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            row["evidencia_hash"] = hash_evidencia(row["evidencia_json"])
            nuevos.append(row)
        await db_session.execute(insert(Intento.__table__), nuevos)
        await db_session.commit()
    statements = []

    def registrar(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(db_session.bind.sync_engine, "before_cursor_execute", registrar)
    tracemalloc.start()
    started = time.perf_counter()
    try:
        lecturas = await cargar_lecturas_historicas(db_session, comps)
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        event.remove(db_session.bind.sync_engine, "before_cursor_execute", registrar)
    assert len(lecturas) == 202
    assert lecturas[original.id].origen == "evidencia_previa"
    assert sum(lectura.cobertura == "ausente" for lectura in lecturas.values()) == (
        0 if muchas_fuentes else 201
    )
    assert all(lectura.cobertura != "no_verificable" for lectura in lecturas.values())
    assert len(statements) == 3
    assert all(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert peak < 20 * 1024 * 1024 and elapsed < 10
    print(
        f"lectura_sintetica filas=202 consultas={len(statements)} segundos={elapsed:.3f} pico_bytes={peak}"
    )
    assert not db_session.dirty and not db_session.new and not db_session.deleted


async def verificar_compactacion(db_session, test_empresa, monkeypatch):
    from app.models.lote_comprobante import LoteComprobante, LoteComprobanteFila
    from app.services.lote_comprobantes_service import LoteComprobantesService

    comps, _ = await crear_historia(db_session, test_empresa, monkeypatch, batch=True)
    intentos = list(await db_session.scalars(select(Intento)))
    antes = [
        (i.id, i.comprobante_id, i.evidencia_json, i.evidencia_hash) for i in intentos
    ]
    lectura_antes = await cargar_lecturas_historicas(db_session, comps)
    # Ya hay autorizados mientras el lote sigue en proceso: su lectura funciona.
    assert all(
        lectura.origen == "evidencia_previa" for lectura in lectura_antes.values()
    )
    lote = await db_session.get(LoteComprobante, intentos[0].lote_id)
    assert lote.estado == "procesando"
    lote.estado = "completado"
    await db_session.commit()
    await LoteComprobantesService(db_session).compactar_lote(
        lote.id, test_empresa.id, None
    )
    assert not list(await db_session.scalars(select(LoteComprobanteFila)))
    assert lectura_antes == await cargar_lecturas_historicas(db_session, comps)
    assert antes == [
        (i.id, i.comprobante_id, i.evidencia_json, i.evidencia_hash)
        for i in await db_session.scalars(select(Intento))
    ]


async def test_compactacion_preserva_fuente_y_lectura(
    db_session, test_empresa, monkeypatch
):
    await verificar_compactacion(db_session, test_empresa, monkeypatch)


async def test_pdf_invalidado_entre_consulta_y_descarga_no_renderiza(
    historia, db_session, monkeypatch
):
    comps, _ = historia
    comp = comps[0]
    lectura = (await cargar_lecturas_historicas(db_session, comps))[comp.id]
    invalida = lectura.model_copy(update={"cobertura": "no_verificable"})
    service = PDFService()
    with pytest.raises(HistoriaNoVerificableError):
        await service.generar_pdf_comprobante(comp, comp.empresa, invalida)
    with pytest.raises(HistoriaNoVerificableError):
        service._generar_qr_url_arca(comp, invalida)


async def test_lecturas_validas_api_y_descarga_comparten_numero(
    historia, db_session, client, auth_headers
):
    comps, punto = historia
    punto.numero = 99
    await db_session.commit()
    comp = comps[0]
    for ruta in (f"/api/comprobantes/{comp.id}", "/api/comprobantes/?per_page=1"):
        respuesta = await client.get(ruta, headers=auth_headers)
        assert respuesta.status_code == 200
        fila = respuesta.json() if "?" not in ruta else respuesta.json()["items"][0]
        assert fila["punto_venta_numero"] == 5
        assert (
            fila["datos_historicos"]["emisor"]["razon_social"]
            == "Emisor original sintético"
        )
    respuesta = await client.get(
        f"/api/pdf/comprobante/{comp.id}", headers=auth_headers
    )
    assert respuesta.status_code == 200
    assert "0005-00000001.pdf" in respuesta.headers["content-disposition"]
    assert "0099" not in PdfReader(BytesIO(respuesta.content)).pages[0].extract_text()
