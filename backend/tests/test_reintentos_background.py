"""Regresiones del contrato durable de reintentos; ARCA completamente simulado."""

import asyncio
from time import perf_counter

import pytest
from sqlalchemy import select

from app.arca.exceptions import ArcaConnectionError
from app.arca.models import CAEResponse
from app.core.config import settings
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.services.duplicados_lotes_service import DuplicadosLotesService
from app.services.lote_comprobantes_service import LoteComprobantesService
from app.services.lote_comprobantes_service import LoteComprobanteConflictoError
from tests.test_lotes_comprobantes import (
    CAE_TEST_NO_REAL,
    _configurar_ambiente_rece_productivo,  # noqa: F401
    _controlar_reloj_fecha_fiscal,  # noqa: F401
    _confirmacion_fecha_fiscal_header_lote,
    _preparar_reintento_manual_pf02b2,
    _marcar_grupos_lote,
    test_punto_venta as _fixture_punto_venta,
    test_certificado as _fixture_certificado,
)

test_punto_venta = _fixture_punto_venta
test_certificado = _fixture_certificado


@pytest.mark.asyncio
@pytest.mark.parametrize("batch", [False, True])
async def test_rg5616_worker_rechaza_payload_legacy_antes_de_cae(
    client,
    auth_headers,
    db_session,
    monkeypatch,
    test_empresa,
    test_punto_venta,
    test_certificado,
    batch,
):
    class WSFE:
        def __init__(self, **kwargs):
            pass

        async def fe_comp_tot_x_request(self):
            return 2

        async def fe_comp_ultimo_autorizado(self, *args):
            return 0

        async def fe_cae_solicitar(self, request):
            raise AssertionError("No debe emitir un receptor ambiguo")

        async def fe_cae_solicitar_lote(self, requests):
            raise AssertionError("No debe emitir un batch con receptor ambiguo")

    empresa_id = test_empresa.id
    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        WSFE,
        nombre_archivo="rg5616-worker.xlsx",
        total_grupos=2,
    )
    for grupo in grupos:
        grupo.payload_json = {
            **grupo.payload_json,
            "condicion_iva": "Responsable No Inscripto",
        }
    await db_session.commit()
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", batch)
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running", lambda app: True
    )
    headers = {
        **auth_headers,
        **await _confirmacion_fecha_fiscal_header_lote(
            db_session,
            lote_id=lote_id,
            estados={"fallido"},
        ),
    }
    url = f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos?background=true"
    encolado = await client.post(url, headers=headers, json={"grupo_ids": []})
    assert encolado.status_code == 200, encolado.text
    await LoteComprobantesService(db_session).procesar_lote(
        lote_id, empresa_id, reanudar=True
    )
    for grupo in grupos:
        await db_session.refresh(grupo)
        assert grupo.estado == "fallido"
        assert "condición IVA" in str(grupo.mensajes_json)
        assert grupo.numero_asignado is None
        assert grupo.cae is None
    assert await db_session.scalar(select(IntentoEmisionFiscal)) is None
    replay = await client.post(url, headers=headers, json={"grupo_ids": []})
    assert replay.status_code == 200, replay.text


@pytest.mark.asyncio
async def test_cliente_wsfe_reutiliza_solo_la_identidad_y_ticket_actuales(
    db_session, monkeypatch
):
    from types import SimpleNamespace

    from app.arca.config import ArcaAmbiente
    from app.services.facturacion_service import FacturacionService

    construidos = []

    class Cliente:
        def __init__(self, **kwargs):
            construidos.append(kwargs)

    ticket = SimpleNamespace(token="token-sintetico", sign="firma-sintetica")
    ambiente = ArcaAmbiente.HOMOLOGACION

    async def obtener_ticket(empresa, certificado):
        return ticket

    service = FacturacionService(db_session)
    monkeypatch.setattr(service, "_obtener_ticket_acceso", obtener_ticket)
    monkeypatch.setattr(service, "_get_arca_ambiente", lambda: ambiente)
    monkeypatch.setattr("app.services.facturacion_service.WSFEv1Client", Cliente)
    empresa = SimpleNamespace(id=1, cuit="emisor-sintetico")
    certificado = SimpleNamespace(
        id=1, archivo_crt="sintetico.crt", archivo_key="sintetico.key"
    )
    primero = await service._obtener_cliente_wsfe(empresa, certificado)
    assert await service._obtener_cliente_wsfe(empresa, certificado) is primero
    certificado.id = 2
    segundo = await service._obtener_cliente_wsfe(empresa, certificado)
    assert segundo is not primero
    empresa.id = 2
    tercero = await service._obtener_cliente_wsfe(empresa, certificado)
    assert tercero is not segundo
    ambiente = ArcaAmbiente.PRODUCCION
    cuarto = await service._obtener_cliente_wsfe(empresa, certificado)
    assert cuarto is not tercero
    ticket.token = "ticket-renovado-sintetico"
    quinto = await service._obtener_cliente_wsfe(empresa, certificado)
    assert quinto is not cuarto
    assert len(construidos) == 5


@pytest.mark.asyncio
async def test_conflicto_previo_a_cola_cierra_operacion_y_replay(
    client,
    auth_headers,
    db_session,
    monkeypatch,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    lote_id, _ = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        object,
        nombre_archivo="conflicto-cola.xlsx",
    )
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running", lambda app: True
    )
    headers = {
        **auth_headers,
        **await _confirmacion_fecha_fiscal_header_lote(
            db_session,
            lote_id=lote_id,
            estados={"fallido"},
        ),
    }

    async def conflicto(self, **kwargs):
        raise LoteComprobanteConflictoError("La selección cambió antes de encolar.")

    monkeypatch.setattr(LoteComprobantesService, "encolar_reintento", conflicto)
    url = f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos?background=true"
    primera = await client.post(url, headers=headers, json={"grupo_ids": []})
    segunda = await client.post(url, headers=headers, json={"grupo_ids": []})
    assert primera.status_code == segunda.status_code == 409
    assert primera.json() == segunda.json()
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-lote-test"
        )
    )
    assert operacion.estado == "fallido_verificado"


@pytest.mark.asyncio
async def test_timeout_post_cae_reintento_background_no_reenvia_ni_libera_incertidumbre(
    client,
    auth_headers,
    db_session,
    monkeypatch,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    empresa_id = test_empresa.id
    llamadas = []

    class WSFE:
        def __init__(self, **kwargs):
            pass

        async def fe_comp_ultimo_autorizado(self, *args):
            return 0

        async def fe_cae_solicitar(self, request):
            llamadas.append(request.cbte_desde)
            raise ArcaConnectionError("Timeout después del envío simulado")

    lote_id, _ = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        WSFE,
        nombre_archivo="incierto-background.xlsx",
        total_grupos=2,
    )
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", False)
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running", lambda app: True
    )
    headers = {
        **auth_headers,
        **await _confirmacion_fecha_fiscal_header_lote(
            db_session,
            lote_id=lote_id,
            estados={"fallido"},
        ),
    }
    url = f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos?background=true"
    respuesta = await client.post(url, headers=headers, json={"grupo_ids": []})
    assert respuesta.status_code == 200, respuesta.text
    lote = await LoteComprobantesService(db_session).procesar_lote(
        lote_id, empresa_id, reanudar=True
    )
    assert lote.estado == "requiere_reconciliacion"
    assert llamadas == [1]
    replay = await client.post(url, headers=headers, json={"grupo_ids": []})
    assert replay.status_code == 200, replay.text
    assert llamadas == [1]
    progreso = (
        await client.get(
            f"/api/lotes-comprobantes/{lote_id}/seguimiento", headers=auth_headers
        )
    ).json()["operacion_progreso"]
    assert progreso["inciertos"] == 2
    grupos = list(
        (
            await db_session.execute(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id,
                )
            )
        ).scalars()
    )
    assert all(g.duplicados_reserva_operacion_id is not None for g in grupos)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("modo", "seleccion_explicita"),
    [("reintento", True), ("reintento", False), ("normal", False)],
)
async def test_reintento_durable_seleccion_bloques_progreso_y_replay(
    client,
    auth_headers,
    db_session,
    monkeypatch,
    test_empresa,
    test_punto_venta,
    test_certificado,
    seleccion_explicita,
    modo,
):
    llamadas = []
    inicializaciones = []
    ultimo = 0
    empresa_id = test_empresa.id

    class WSFE:
        def __init__(self, **kwargs):
            inicializaciones.append(1)

        async def fe_comp_tot_x_request(self):
            return 2

        async def fe_comp_ultimo_autorizado(self, *args):
            await asyncio.sleep(0.005)
            return ultimo

        async def fe_cae_solicitar_lote(self, requests):
            nonlocal ultimo
            await asyncio.sleep(0.005)
            llamadas.append([r.cbte_desde for r in requests])
            ultimo = requests[-1].cbte_desde
            return [
                CAEResponse(
                    cae=CAE_TEST_NO_REAL,
                    cae_vencimiento="20260831",
                    numero_comprobante=r.cbte_desde,
                    tipo_cbte=r.tipo_cbte,
                    punto_venta=r.punto_venta,
                    resultado="A",
                )
                for r in requests
            ]

        async def fe_cae_solicitar(self, request):
            return (await self.fe_cae_solicitar_lote([request]))[0]

    lote_id, grupos = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        WSFE,
        nombre_archivo="reintento-background.xlsx",
        total_grupos=4,
    )
    ids = [g.id for g in grupos[:3]] if seleccion_explicita else None
    if modo == "normal":
        await _marcar_grupos_lote(db_session, lote_id, ["validado"] * 4)
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", True)
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running", lambda app: True
    )
    headers = {
        **auth_headers,
        **await _confirmacion_fecha_fiscal_header_lote(
            db_session,
            lote_id=lote_id,
            estados={"validado"} if modo == "normal" else {"fallido"},
            grupo_ids=ids,
        ),
    }
    accion = "procesar" if modo == "normal" else "reintentar-fallidos"
    url = f"/api/lotes-comprobantes/{lote_id}/{accion}?background=true"
    body = {"grupo_ids": ids or []}
    primera = await client.post(url, headers=headers, json=body)
    assert primera.status_code == 200, primera.text
    assert primera.json()["lote"]["estado"] == "en_cola"
    assert llamadas == []
    replay = await client.post(url, headers=headers, json=body)
    assert replay.status_code == 200, replay.text
    assert llamadas == []
    progreso = (
        await client.get(
            f"/api/lotes-comprobantes/{lote_id}/seguimiento",
            headers=auth_headers,
        )
    ).json()["operacion_progreso"]
    if modo == "reintento":
        assert progreso["seleccionados"] == (3 if seleccion_explicita else 4)
        assert progreso["autorizados"] == progreso["fallidos"] == 0
        assert progreso["pendientes"] == progreso["seleccionados"]
    inicio = perf_counter()
    lote = await LoteComprobantesService(db_session).procesar_lote(
        lote_id,
        empresa_id,
        reanudar=True,
    )
    assert llamadas == ([[1, 2], [3]] if seleccion_explicita else [[1, 2], [3, 4]])
    assert len(inicializaciones) == 1
    print(
        f"benchmark modo={modo} seleccion={len(ids or grupos)} latencia_ms=5 bloques={len(llamadas)} inicializaciones={len(inicializaciones)} duracion_s={perf_counter() - inicio:.3f}"
    )
    assert lote.grupos_emitidos == (3 if seleccion_explicita else 4)
    if seleccion_explicita:
        await db_session.refresh(grupos[3])
        assert grupos[3].estado == "fallido"
    operacion = await db_session.scalar(
        select(OperacionIdempotente).where(
            OperacionIdempotente.idempotency_key == "idem-lote-test",
        )
    )
    assert operacion.estado == "finalizado"
    final = await client.post(url, headers=headers, json=body)
    assert final.status_code == 200, final.text
    assert len(llamadas) == 2
    progreso_final = (
        await client.get(
            f"/api/lotes-comprobantes/{lote_id}/seguimiento",
            headers=auth_headers,
        )
    ).json()["operacion_progreso"]
    if modo == "reintento":
        assert progreso_final["pendientes"] == 0
        assert progreso_final["autorizados"] == progreso["seleccionados"]


@pytest.mark.asyncio
async def test_preparacion_sin_conexion_deja_fallidos_seguros_y_motivo_persistente(
    client,
    auth_headers,
    db_session,
    monkeypatch,
    test_empresa,
    test_punto_venta,
    test_certificado,
):
    class SinConexion:
        def __init__(self, **kwargs):
            raise ArcaConnectionError("Fallo WSDL simulado")

    empresa_id = test_empresa.id

    lote_id, _ = await _preparar_reintento_manual_pf02b2(
        client,
        auth_headers,
        monkeypatch,
        db_session,
        test_empresa,
        test_punto_venta,
        SinConexion,
        nombre_archivo="reintento-sin-conexion.xlsx",
        total_grupos=3,
    )
    monkeypatch.setattr(settings, "arca_fecaesolicitar_batch_enabled", False)
    monkeypatch.setattr(
        "app.api.lotes_comprobantes.ensure_lote_worker_running", lambda app: True
    )
    headers = {
        **auth_headers,
        **await _confirmacion_fecha_fiscal_header_lote(
            db_session,
            lote_id=lote_id,
            estados={"fallido"},
        ),
    }
    respuesta = await client.post(
        f"/api/lotes-comprobantes/{lote_id}/reintentar-fallidos?background=true",
        headers=headers,
        json={"grupo_ids": []},
    )
    assert respuesta.status_code == 200, respuesta.text
    lote = await LoteComprobantesService(db_session).procesar_lote(
        lote_id, empresa_id, reanudar=True
    )
    assert lote.estado == "fallido"
    assert lote.grupos_fallidos == 3
    grupos = list(
        (
            await db_session.execute(
                select(LoteComprobanteGrupo).where(
                    LoteComprobanteGrupo.lote_id == lote_id,
                )
            )
        ).scalars()
    )
    assert all(g.duplicados_reserva_operacion_id is None for g in grupos)
    assert all("No se solicitó CAE" in " ".join(g.mensajes_json) for g in grupos)
    assert all("numeración" not in " ".join(g.mensajes_json) for g in grupos)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "estado", ["finalizado", "en_proceso", "requiere_reconciliacion"]
)
async def test_reservas_terminales_recuperables_sin_alterar_otro_owner(
    db_session,
    test_empresa,
    test_punto_venta,
    estado,
):
    lote = LoteComprobante(
        empresa_id=test_empresa.id,
        nombre_archivo="reserva.xlsx",
        archivo_hash="reserva",
        estado="fallido",
        metadata_json={},
    )
    db_session.add(lote)
    await db_session.flush()
    owner = OperacionIdempotente(
        empresa_id=test_empresa.id,
        lote_id=lote.id,
        tipo_operacion="procesar_lote",
        idempotency_key="reserva-terminal",
        payload_hash="a" * 64,
        estado=estado,
        response_json={
            "lote": {"id": lote.id, "empresa_id": test_empresa.id, "estado": "fallido"},
            "en_progreso": False,
        },
    )
    db_session.add(owner)
    await db_session.flush()
    grupo = LoteComprobanteGrupo(
        empresa_id=test_empresa.id,
        lote_id=lote.id,
        comprobante_ref="reserva",
        orden=1,
        estado="fallido",
        duplicados_reserva_operacion_id=owner.id,
    )
    db_session.add(grupo)
    await db_session.commit()
    # Snapshot RECE sintético completo tomado de la fixture, para scoping de ambiente.
    from app.services.elegibilidad_rece_service import ElegibilidadReceService

    contexto = await ElegibilidadReceService(
        db_session
    ).exigir_contexto_preautorizacion(
        empresa_id=test_empresa.id,
        punto_venta_id=test_punto_venta.id,
        ambiente="produccion",
        tipo_comprobante=6,
    )
    grupo.punto_venta_id = contexto.punto_venta_id
    grupo.punto_venta_numero = contexto.punto_venta_numero
    grupo.ambiente = contexto.ambiente
    grupo.punto_venta_elegibilidad_revision_id = contexto.elegibilidad_revision_id
    grupo.punto_venta_revision_fiscal = contexto.punto_venta_revision_fiscal
    grupo.tipo_comprobante = 6
    await db_session.commit()
    servicio = DuplicadosLotesService(db_session)
    await servicio.adquirir_coordinacion(
        empresa_id=test_empresa.id, ambiente="produccion"
    )
    await servicio.recuperar_reservas_terminales(
        empresa_id=test_empresa.id, ambiente="produccion"
    )
    await db_session.commit()
    await db_session.refresh(grupo)
    assert grupo.duplicados_reserva_operacion_id == (
        None if estado == "finalizado" else owner.id
    )
