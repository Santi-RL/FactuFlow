"""Recuperación simultánea de A/B/C/D con conexiones PostgreSQL independientes."""

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.arca.exceptions import ArcaConnectionError, ArcaServiceError
from app.arca.models import CAEResponse, ComprobanteResponse
from app.core.config import settings
from app.models.comprobante import Comprobante
from app.models.elegibilidad_rece import PuntoVentaGuardaEmisionRece as Guarda
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import (
    IntentoEmisionFiscal as Intento,
    OperacionIdempotente as Operacion,
)
from app.models.lote_comprobante import (
    LoteComprobante as Lote,
    LoteComprobanteEvento as Evento,
    LoteComprobanteGrupo as Grupo,
    LoteComprobanteFila as Fila,
)
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.services.facturacion_service import FacturacionService
from app.services.lote_comprobantes_service import (
    LoteComprobantesService,
    LoteComprobanteConflictoError,
)
from app.services.reconciliacion_lote_service import ReconciliacionLoteService
from tests.integration.test_integridad_fiscal_postgresql import (
    _reset_schema,
    _run_alembic,
)
from tests.postgresql_harness import require_disposable_postgres_url
from tests.test_evidencia_fiscal import _request
from tests.test_facturacion_service import (
    _fijar_reloj_facturacion,
    _crear_operacion_rece_sintetica,
)


class ArcaLote:
    def __init__(self, cuit):
        self.cuit = cuit
        self.config = SimpleNamespace(ambiente="produccion")
        self.enviados = {}
        self.habilitado_c = False
        self.consultas = []
        self.cruce = asyncio.Event()
        self.barrera = set()

    async def fe_param_get_ptos_venta(self):
        return [SimpleNamespace(numero=5, bloqueado="N", emision_tipo="CAE")]

    async def fe_comp_ultimo_autorizado(self, *_):
        return len(self.enviados)

    async def fe_cae_solicitar_lote(self, solicitudes):
        assert len(self.enviados) < 3, "La recuperación volvió a solicitar CAE"
        self.enviados.update({s.cbte_desde: s for s in solicitudes})
        if len(solicitudes) > 1:
            raise ArcaConnectionError("Interrupción sintética tras recibir el bloque")
        s = solicitudes[0]
        return [
            CAEResponse(
                cae=f"{s.cbte_desde:014d}",
                cae_vencimiento="20260818",
                numero_comprobante=s.cbte_desde,
                tipo_cbte=s.tipo_cbte,
                punto_venta=s.punto_venta,
                resultado="A",
            )
        ]

    async def fe_comp_consultar(self, *, punto_venta, tipo_cbte, numero):
        self.consultas.append(numero)
        if numero in self.barrera:
            if len(self.consultas) >= 2:
                self.cruce.set()
            await asyncio.wait_for(self.cruce.wait(), 10)
        if numero == 3 and not self.habilitado_c:
            raise ArcaServiceError("Resultado inconcluso", codigo="602")
        original = self.enviados[numero]
        assert (punto_venta, tipo_cbte) == (original.punto_venta, original.tipo_cbte)
        return ComprobanteResponse(
            **original.model_dump(),
            numero=numero,
            cuit_emisor=self.cuit,
            resultado="A",
            emision_tipo="CAE",
            cae=f"{numero:014d}",
            cae_vencimiento="20260818",
        )


async def preparar(db, monkeypatch):
    _fijar_reloj_facturacion(monkeypatch)
    monkeypatch.setattr(settings, "arca_env", "produccion")
    empresa = Empresa(
        razon_social="Emisor sintético",
        cuit="20123456789",
        condicion_iva="RI",
        domicilio="Sintético",
        localidad="Sintética",
        provincia="Buenos Aires",
        codigo_postal="1000",
        inicio_actividades=date(2020, 1, 1),
    )
    operador = Usuario(
        email="operador@example.test",
        nombre="Operador sintético",
        hashed_password="sintetico",
        es_admin=True,
    )
    db.add_all([empresa, operador])
    await db.flush()
    p = PuntoVenta(
        numero=5,
        activo=True,
        es_webservice=True,
        empresa_id=empresa.id,
        revision_fiscal=1,
    )
    db.add(p)
    await db.commit()
    wsfe = ArcaLote(empresa.cuit)

    async def cliente(*_):
        return wsfe

    async def certificado(*_):
        return SimpleNamespace()

    monkeypatch.setattr(FacturacionService, "_obtener_cliente_wsfe", cliente)
    monkeypatch.setattr(FacturacionService, "_obtener_certificado_activo", certificado)
    requests = [_request(empresa.id, p.id, f"Receptor {k}") for k in "ABCD"]
    for n, request in enumerate(requests):
        request.numero_documento = f"1234567{n}"
    op, _, metadata = await _crear_operacion_rece_sintetica(
        db, empresa=empresa, punto_venta=p, requests=requests, batch=True
    )
    ids = [m["grupo_id"] for m in metadata]
    params = (op.lote_id, empresa.id, operador.id, op.id)
    lotes = LoteComprobantesService(db)
    fiscal = FacturacionService(db)
    for inicio, fin in [(0, 1), (1, 3)]:
        resultados = await fiscal.emitir_comprobantes_lote(
            requests[inicio:fin], contextos=metadata[inicio:fin]
        )
        for gid, respuesta in zip(ids[inicio:fin], resultados):
            assert (
                respuesta.exito if inicio == 0 else respuesta.requiere_reconciliacion
            ), respuesta
            await lotes._aplicar_resultado_emision_grupo(
                await db.get(Grupo, gid), respuesta
            )
        await db.commit()
    await lotes._cerrar_lote_por_incertidumbre_post_arca(
        lote_id=params[0],
        empresa_id=params[1],
        operacion_id=params[3],
        grupos_seleccionados_ids=set(ids),
        grupos_inmovilizados_ids=set(ids[1:]),
        grupos_sublote_ids=set(ids[1:3]),
    )
    await db.commit()
    return wsfe, params, ids


@pytest.mark.integration
async def test_lote_concurrente_guarda_compartida_y_worker_tardio(monkeypatch):
    url = require_disposable_postgres_url(purpose="recuperación concurrente de lotes")
    await _reset_schema(url)
    _run_alembic("upgrade", "head", url)
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as db:
            wsfe, params, ids = await preparar(db, monkeypatch)

        async def verificar(cursor=0):
            async with factory() as db:
                return await ReconciliacionLoteService(db).verificar(
                    *params, despues=cursor
                )

        async def publicar_worker_tardio():
            await asyncio.wait_for(wsfe.cruce.wait(), 10)
            async with factory() as db:
                lote = await db.get(Lote, params[0])
                try:
                    await LoteComprobantesService(
                        db
                    )._guardar_respuesta_operacion_background(lote, params[3])
                except LoteComprobanteConflictoError:
                    pass  # Todavía no se publicó ningún resultado de verificación.

        # Dos verificadores consultan B y uno consulta C de la misma guarda.
        wsfe.barrera = {2, 3}
        await asyncio.wait_for(
            asyncio.gather(
                verificar(), verificar(), verificar(ids[1]), publicar_worker_tardio()
            ),
            30,
        )
        async with factory() as db:
            lote = await db.get(Lote, params[0])
            resumen = await ReconciliacionLoteService(db).resumen(lote)
            assert (resumen.autorizados, resumen.pendientes, resumen.sin_enviar) == (
                2,
                1,
                1,
            )
            assert lote.estado == "requiere_reconciliacion"
            assert (await db.get(Grupo, ids[3])).estado == "requiere_reconciliacion"
            assert await db.scalar(select(func.count(Comprobante.id))) == 2
            i = await db.scalar(select(Intento).where(Intento.grupo_id == ids[2]))
            assert (
                await db.get(Guarda, i.guarda_rece_id)
            ).fase == "requiere_reconciliacion"
            assert (await db.get(Operacion, params[3])).response_json["lote"][
                "grupos_emitidos"
            ] == 2
            assert await LoteComprobantesService(db).grupos_con_verificacion_propia(
                lote, ids[2:]
            ) == set(ids[2:])
        wsfe.habilitado_c = True
        primera, segunda = await asyncio.gather(verificar(), verificar())
        assert (
            primera == segunda
            and primera.autorizados == 3
            and primera.sin_enviar == 1
            and primera.pendientes == 0
        )
        consultas = len(wsfe.consultas)
        assert await verificar() == primera and len(wsfe.consultas) == consultas
        assert len(wsfe.enviados) == 3
        async with factory() as db:
            lote = await db.get(Lote, params[0])
            assert (lote.estado, lote.grupos_emitidos, lote.grupos_fallidos) == (
                "autorizado_parcial",
                3,
                1,
            )
            assert (
                (await db.get(Grupo, ids[3])).mensajes_json[0].startswith("Sin enviar.")
            )
            assert (await db.scalars(select(Fila.estado).order_by(Fila.id))).all() == [
                "autorizado"
            ] * 3 + ["fallido"]
            assert await db.scalar(select(func.count(Comprobante.id))) == 3
            assert set(await db.scalars(select(Guarda.fase))) == {"cerrada_terminal"}
            assert (
                await db.scalar(
                    select(func.count(Evento.id)).where(
                        Evento.accion == "verificacion_lote_cerrada"
                    )
                )
                == 1
            )
            op = await db.get(Operacion, params[3])
            publicada = op.response_json
            lote.grupos_emitidos = 0
            await LoteComprobantesService(db)._guardar_respuesta_operacion_background(
                lote, params[3]
            )
            assert lote.grupos_emitidos == 3
            assert (await db.get(Operacion, params[3])).response_json == publicada
            assert (
                op.estado == "finalizado" and op.response_json["en_progreso"] is False
            )
    finally:
        await engine.dispose()
