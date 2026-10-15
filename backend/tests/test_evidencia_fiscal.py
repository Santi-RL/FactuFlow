"""Evidencia previa PF-04/PF-02: fuente original, fallos y frontera irreversible."""

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.evidencia_fiscal import (
    CAMPOS_CONTEXTO,
    EvidenciaFiscalError,
    comparar_evidencia,
    hash_evidencia,
    leer_evidencia,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService, FaseSolicitudArca
from tests.test_facturacion_service import (
    FECHA_FISCAL_PRUEBA,
    _crear_operacion_rece_sintetica,
    _fijar_reloj_facturacion,
)


def _request(empresa_id=1, punto_id=1, nombre="Receptor sintético"):
    return EmitirComprobanteRequest(
        empresa_id=empresa_id,
        punto_venta_id=punto_id,
        tipo_comprobante=6,
        concepto=1,
        fecha_emision=FECHA_FISCAL_PRUEBA,
        tipo_documento=96,
        numero_documento="00123456",
        razon_social=nombre,
        condicion_iva="CF",
        guardar_cliente=False,
        items=[
            ItemComprobanteCreate(
                codigo="0001",
                descripcion="Ítem de prueba",
                cantidad=Decimal("1.00005"),
                precio_unitario=Decimal("1000.12345"),
                iva_porcentaje=Decimal("21"),
            )
        ],
    )


def _leer(intento):
    return leer_evidencia(
        version=intento.evidencia_version,
        raw=intento.evidencia_json,
        sha256=intento.evidencia_hash,
        pertenencia={name: getattr(intento, name) for name in CAMPOS_CONTEXTO},
    )


@pytest.fixture
def evidencia():
    request = _request()
    intento = IntentoEmisionFiscal(
        id=10,
        empresa_id=1,
        operacion_id=2,
        punto_venta_id=1,
        punto_venta_numero=5,
        tipo_comprobante=6,
        numero_planificado=30,
        ambiente="produccion",
        guarda_rece_id=3,
        punto_venta_elegibilidad_revision_id=4,
        punto_venta_revision_fiscal=1,
    )
    empresa = SimpleNamespace(
        cuit="20123456789",
        razon_social="Emisor original",
        inicio_actividades=date(2020, 1, 1),
    )
    client = SimpleNamespace(
        cuit=empresa.cuit, config=SimpleNamespace(ambiente="produccion")
    )
    service = FacturacionService(None)
    totales = service._calcular_totales(request.items)
    arca_request = service._armar_request_arca(request, 30, totales, 5)
    service._congelar_evidencia(
        intento, request, arca_request, totales, empresa, client
    )
    return intento, empresa, request, arca_request, client


def test_lectura_original_exacta_no_depende_de_fichas_actuales(evidencia):
    intento, empresa, request, arca_request, _ = evidencia
    raw = intento.evidencia_json
    empresa.razon_social = "Emisor cambiado"
    request.razon_social = "Receptor cambiado"
    request.items[0].precio_unitario = Decimal("2")
    snapshot = _leer(intento)
    assert snapshot.presentacion.emisor.razon_social == "Emisor original"
    assert snapshot.presentacion.receptor.razon_social == "Receptor sintético"
    assert snapshot.presentacion.receptor.numero_documento == "00123456"
    assert snapshot.presentacion.items[0].codigo == "0001"
    assert snapshot.presentacion.items[0].cantidad == Decimal("1.00005")
    assert snapshot.solicitud_wsfe.imp_total == arca_request.imp_total
    assert snapshot.importes_guardado.subtotales_items == [Decimal("1000.17")]
    assert intento.evidencia_json == raw
    assert all(
        secret not in raw
        for secret in (
            "token",
            "archivo_crt",
            "confirmacion_fecha_fiscal",
            "guardar_cliente",
        )
    )


def test_captura_cuit_representado_con_la_normalizacion_del_cliente_wsfe(evidencia):
    intento, empresa, request, arca_request, client = evidencia
    empresa.cuit = "20-12345678-9"
    service = FacturacionService(None)
    service._congelar_evidencia(
        intento,
        request,
        arca_request,
        service._calcular_totales(request.items),
        empresa,
        client,
    )
    assert _leer(intento).contexto.cuit == client.cuit == "20123456789"


@pytest.mark.parametrize("campo", CAMPOS_CONTEXTO)
def test_rechaza_evidencia_cruzada_en_cada_frontera(evidencia, campo):
    intento, *_ = evidencia
    pertenencia = {name: getattr(intento, name) for name in CAMPOS_CONTEXTO}
    pertenencia[campo] = "otro" if campo == "ambiente" else 999
    with pytest.raises(EvidenciaFiscalError):
        leer_evidencia(
            version=intento.evidencia_version,
            raw=intento.evidencia_json,
            sha256=intento.evidencia_hash,
            pertenencia=pertenencia,
        )


@pytest.mark.parametrize(
    "cambio",
    ["total", "fecha_emision", "receptor_tipo_documento", "receptor_numero_documento"],
)
def test_lector_contrasta_los_datos_fiscales_de_la_fila(evidencia, cambio):
    intento, _, _, wsfe, _ = evidencia
    pertenencia = {name: getattr(intento, name) for name in CAMPOS_CONTEXTO}
    pertenencia.update(
        total=wsfe.imp_total,
        fecha_emision=FECHA_FISCAL_PRUEBA,
        receptor_tipo_documento=wsfe.tipo_doc,
        receptor_numero_documento=str(wsfe.nro_doc),
    )
    pertenencia[cambio] = {
        "total": Decimal("1"),
        "fecha_emision": date(2026, 8, 10),
        "receptor_tipo_documento": 80,
        "receptor_numero_documento": "99999",
    }[cambio]
    with pytest.raises(EvidenciaFiscalError):
        leer_evidencia(
            version=intento.evidencia_version,
            raw=intento.evidencia_json,
            sha256=intento.evidencia_hash,
            pertenencia=pertenencia,
        )


@pytest.mark.parametrize(
    "cambio",
    [
        "hash",
        "version",
        "campo_extra",
        "decimal_float",
        "fecha_imposible",
        "numero",
        "null",
    ],
)
def test_rechaza_material_alterado_incluso_con_hash_recalculado(evidencia, cambio):
    intento, *_ = evidencia
    doc = json.loads(intento.evidencia_json)
    if cambio == "campo_extra":
        doc["solicitud_wsfe"]["token"] = "dato-no-admitido"
    elif cambio == "decimal_float":
        doc["solicitud_wsfe"]["imp_total"] = 1210.0
    elif cambio == "fecha_imposible":
        doc["solicitud_wsfe"]["fecha_cbte"] = "20260230"
    elif cambio == "numero":
        doc["solicitud_wsfe"]["cbte_desde"] = 99
    elif cambio == "null":
        doc["solicitud_wsfe"]["imp_iva"] = None
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    intento.evidencia_json = raw
    intento.evidencia_hash = "0" * 64 if cambio == "hash" else hash_evidencia(raw)
    if cambio == "version":
        intento.evidencia_version = "solicitud_fiscal/2"
    with pytest.raises(EvidenciaFiscalError):
        _leer(intento)


def _consulta_evidencia(snapshot):
    expected = snapshot.solicitud_wsfe.model_dump()
    expected.update(numero=30, emision_tipo="CAE", cuit_emisor=snapshot.contexto.cuit)
    # Las colecciones conservan atributos tipados en el comparador común.
    for name in ("iva", "tributos", "cbtes_asoc"):
        expected[name] = getattr(snapshot.solicitud_wsfe, name)
    return SimpleNamespace(**expected)


def test_comparacion_pura_distingue_diferencia_y_cobertura(evidencia):
    intento, *_ = evidencia
    snapshot = _leer(intento)
    consulta = _consulta_evidencia(snapshot)
    assert comparar_evidencia(snapshot, consulta).estado == "coincidente"
    consulta.moneda_id = "DOL"
    consulta.imp_iva = None
    result = comparar_evidencia(snapshot, consulta)
    assert result.estado == "diferente"
    assert "moneda_id" in result.campos
    assert intento.estado is None  # No transición fiscal, ni siquiera en memoria.


@pytest.mark.parametrize(
    "cuit,estado",
    [
        ("20123456789", "coincidente"),
        ("20987654321", "diferente"),
        (None, "no_disponible"),
        ("", "no_disponible"),
        ("inválido", "no_disponible"),
        (20123456789, "no_disponible"),
        (False, "no_disponible"),
    ],
)
def test_comparacion_contrasta_identidad_del_emisor(evidencia, cuit, estado):
    intento, *_ = evidencia
    snapshot = _leer(intento)
    consulta = _consulta_evidencia(snapshot)
    consulta.cuit_emisor = cuit
    resultado = comparar_evidencia(snapshot, consulta)
    assert resultado.estado == estado
    assert ("cuit_emisor" in resultado.campos) == (estado != "coincidente")
    del consulta.cuit_emisor
    assert comparar_evidencia(snapshot, consulta).estado == "no_disponible"
    assert intento.estado is None


def test_comparacion_diferencia_prevalece_sobre_cobertura_ausente(evidencia):
    intento, *_ = evidencia
    snapshot = _leer(intento)
    consulta = _consulta_evidencia(snapshot)
    consulta.cuit_emisor = "20987654321"
    consulta.imp_iva = None
    consulta.cbte_hasta = None
    resultado = comparar_evidencia(snapshot, consulta)
    assert resultado.estado == "diferente"
    assert resultado.campos == ("cuit_emisor",)
    assert "cbte_hasta" in resultado.cobertura_desconocida
    consulta.cuit_emisor = None
    resultado = comparar_evidencia(snapshot, consulta)
    assert resultado.estado == "no_disponible"
    assert set(resultado.campos) == {"cuit_emisor", "imp_iva"}
    consulta.moneda_id = "DOL"
    resultado = comparar_evidencia(snapshot, consulta)
    assert resultado.estado == "diferente"
    assert resultado.campos == ("moneda_id",)


@pytest.mark.parametrize("tipo", [1, 2, 3, 6, 7, 8, 11, 12, 13])
def test_contrato_conserva_notas_servicios_moneda_y_asociados(evidencia, tipo):
    from app.schemas.comprobante import ComprobanteAsociadoCreate

    intento, empresa, request, _, client = evidencia
    request.tipo_comprobante = tipo
    request.condicion_iva = "RI" if tipo in {1, 2, 3} else "CF"
    if tipo in {1, 2, 3}:
        request.tipo_documento = 80
        request.numero_documento = empresa.cuit
    if tipo in {11, 12, 13}:
        request.items[0].iva_porcentaje = Decimal("0")
    request.concepto = 3
    request.fecha_servicio_desde = date(2026, 8, 1)
    request.fecha_servicio_hasta = FECHA_FISCAL_PRUEBA
    request.fecha_vto_pago = date(2026, 8, 20)
    request.moneda = "DOL"
    request.cotizacion = Decimal("1234.123456789012345678901234")
    request.observaciones = "Observación original"
    if tipo in {2, 3, 7, 8, 12, 13}:
        request.comprobantes_asociados = [
            ComprobanteAsociadoCreate(
                tipo_comprobante=1 if tipo in {2, 3} else 6 if tipo in {7, 8} else 11,
                punto_venta=5,
                numero=1,
                cuit=empresa.cuit,
                fecha=date(2026, 8, 1),
            )
        ]
    intento.tipo_comprobante = tipo
    service = FacturacionService(None)
    totals = service._calcular_totales(request.items)
    wsfe = service._armar_request_arca(request, 30, totals, 5)
    service._congelar_evidencia(intento, request, wsfe, totals, empresa, client)
    snapshot = _leer(intento)
    assert snapshot.solicitud_wsfe.tipo_cbte == tipo
    assert snapshot.solicitud_wsfe.moneda_cotiz == request.cotizacion
    assert snapshot.solicitud_wsfe.fecha_serv_desde == "20260801"
    assert snapshot.presentacion.observaciones == request.observaciones
    if request.comprobantes_asociados:
        assert snapshot.solicitud_wsfe.cbtes_asoc[0].cuit == empresa.cuit
        assert snapshot.solicitud_wsfe.cbtes_asoc[0].fecha_cbte == "20260801"
    assert (snapshot.solicitud_wsfe.iva == []) is (tipo in {11, 12, 13})


@pytest.mark.asyncio
@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize(
    "fallo",
    [
        None,
        "construccion",
        "timeout",
        "identidad",
        "alteracion",
        "commit_previo",
        "commit_ambiguo",
    ],
)
async def test_evidencia_confirmada_antes_de_cae_y_conservada_en_fallos(
    db_session,
    test_empresa,
    monkeypatch,
    batch,
    fallo,
):
    from app.arca.models import CAEResponse
    from app.arca.exceptions import ArcaConnectionError

    monkeypatch.setattr(settings, "arca_env", "produccion")
    _fijar_reloj_facturacion(monkeypatch)
    punto = PuntoVenta(
        numero=5,
        activo=True,
        es_webservice=True,
        empresa_id=test_empresa.id,
        revision_fiscal=1,
    )
    db_session.add(punto)
    await db_session.commit()
    requests = [
        _request(test_empresa.id, punto.id, f"Receptor {i}")
        for i in range(2 if batch else 1)
    ]
    operacion, contexto, metadata = await _crear_operacion_rece_sintetica(
        db_session,
        empresa=test_empresa,
        punto_venta=punto,
        requests=requests,
        batch=batch,
    )
    enviados = []

    class WSFE:
        cuit = test_empresa.cuit if fallo != "identidad" else "20999999999"
        config = SimpleNamespace(ambiente="produccion")

        async def fe_param_get_ptos_venta(self):
            return [SimpleNamespace(numero=5, bloqueado="N", emision_tipo="CAE")]

        async def fe_comp_ultimo_autorizado(self, *_args):
            return 0

        async def fe_cae_solicitar_lote(self, solicitudes):
            from sqlalchemy.ext.asyncio import AsyncSession

            # Otra sesión observa las reservas ya confirmadas antes de cualquier envío.
            async with AsyncSession(
                db_session.bind, expire_on_commit=False
            ) as observer:
                attempts = list(
                    await observer.scalars(
                        select(IntentoEmisionFiscal).order_by(IntentoEmisionFiscal.id)
                    )
                )
                assert len(attempts) == len(solicitudes)
                for attempt, solicitud in zip(attempts, solicitudes):
                    assert (
                        _leer(attempt).solicitud_wsfe.imp_total == solicitud.imp_total
                    )
                    assert attempt.solicitud_arca_at is not None
            enviados.extend(solicitudes)
            if fallo == "timeout":
                raise ArcaConnectionError("Timeout sintético después del envío")
            return [
                CAEResponse(
                    cae="12345678901234",
                    cae_vencimiento="20260818",
                    numero_comprobante=s.cbte_desde,
                    tipo_cbte=s.tipo_cbte,
                    punto_venta=s.punto_venta,
                    resultado="A",
                )
                for s in reversed(solicitudes)
            ]

        async def fe_cae_solicitar(self, solicitud):
            return (await self.fe_cae_solicitar_lote([solicitud]))[0]

    async def client(*_args):
        return WSFE()

    async def certificado(*_args):
        return SimpleNamespace()

    monkeypatch.setattr(FacturacionService, "_obtener_cliente_wsfe", client)
    monkeypatch.setattr(FacturacionService, "_obtener_certificado_activo", certificado)
    service = FacturacionService(db_session)
    original = service._congelar_evidencia
    evidencia_preparada = False

    def congelar(*args):
        nonlocal evidencia_preparada
        if fallo == "construccion" and (not batch or args[0].numero_planificado == 2):
            raise ValueError("No se pudo construir el segundo detalle")
        result = original(*args)
        evidencia_preparada = True
        return result

    monkeypatch.setattr(service, "_congelar_evidencia", congelar)
    if fallo in {"commit_previo", "commit_ambiguo"}:
        from sqlalchemy.exc import OperationalError
        from sqlalchemy.ext.asyncio import AsyncSession

        commit_original = db_session.commit
        fallo_inyectado = False

        async def fallar_commit():
            nonlocal fallo_inyectado
            if evidencia_preparada and not fallo_inyectado:
                fallo_inyectado = True
                if fallo == "commit_ambiguo":
                    await commit_original()
                raise OperationalError("COMMIT", {}, RuntimeError("Fallo sintético"))
            return await commit_original()

        monkeypatch.setattr(db_session, "commit", fallar_commit)
        fase = FaseSolicitudArca()
        with pytest.raises(OperationalError):
            if batch:
                await service.emitir_comprobantes_lote(
                    requests, contextos=metadata, fase_solicitud_arca=fase
                )
            else:
                await service.emitir_comprobante(
                    requests[0],
                    operacion_id=operacion.id,
                    contexto_rece=contexto,
                    contextos_operacion=[contexto],
                    fase_solicitud_arca=fase,
                )
        await db_session.rollback()
        assert fallo_inyectado and not enviados and not fase.iniciada
        async with AsyncSession(db_session.bind, expire_on_commit=False) as restarted:
            durable = list(await restarted.scalars(select(IntentoEmisionFiscal)))
            assert len(durable) == (len(requests) if fallo == "commit_ambiguo" else 0)
            for attempt in durable:
                assert _leer(attempt).contexto.id == attempt.id
                assert attempt.solicitud_arca_at is None
                assert attempt.estado == "en_proceso"
        return
    if fallo == "alteracion":
        verificar = service._verificar_evidencia_durable

        async def alterar(intentos, arca_requests, cliente):
            from sqlalchemy import update

            await db_session.execute(
                update(IntentoEmisionFiscal).values(evidencia_hash="0" * 64)
            )
            await db_session.commit()
            return await verificar(intentos, arca_requests, cliente)

        monkeypatch.setattr(service, "_verificar_evidencia_durable", alterar)
    if batch:
        responses = await service.emitir_comprobantes_lote(requests, contextos=metadata)
    else:
        responses = [
            await service.emitir_comprobante(
                requests[0],
                operacion_id=operacion.id,
                contexto_rece=contexto,
                contextos_operacion=[contexto],
            )
        ]
    attempts = list(await db_session.scalars(select(IntentoEmisionFiscal)))
    if fallo in {"construccion", "identidad", "alteracion"}:
        assert enviados == []
        assert not any(response.exito for response in responses)
        if fallo == "alteracion":
            assert all(
                response.categoria_error == "evidencia_fiscal_no_verificada"
                for response in responses
            )
            assert all(
                "RECE" not in " ".join(response.errores or []) for response in responses
            )
    else:
        assert len(enviados) == len(requests)
        assert len(attempts) == len(requests)
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(db_session.bind, expire_on_commit=False) as restarted:
            recovered = list(await restarted.scalars(select(IntentoEmisionFiscal)))
            assert {attempt.evidencia_hash for attempt in recovered} == {
                attempt.evidencia_hash for attempt in attempts
            }
            assert {attempt.estado for attempt in recovered} == {
                "requiere_reconciliacion" if fallo else "autorizado"
            }
            assert all(
                _leer(attempt).contexto.id == attempt.id for attempt in recovered
            )
        for attempt in attempts:
            raw = attempt.evidencia_json
            assert _leer(attempt).contexto.guarda_rece_id == attempt.guarda_rece_id
            assert attempt.estado == (
                "requiere_reconciliacion" if fallo else "autorizado"
            )
            if fallo == "timeout":
                db_session.expire(attempt, ["evidencia_json"])
            attempt.evidencia_json = raw.replace("Receptor", "Modificado")
            with pytest.raises(ValueError, match="inmutable"):
                await db_session.flush()
            await db_session.rollback()
            break
