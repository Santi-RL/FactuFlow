"""Recupera los resultados de una operación de lote que ya quedó inmovilizada."""

from collections import defaultdict
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS
from app.core.evidencia_fiscal import EvidenciaFiscalError
from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaGuardaEmisionRece as Guarda,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal as Intento
from app.models.idempotencia_fiscal import OperacionIdempotente as Operacion
from app.models.lote_comprobante import (
    LoteComprobante as Lote,
    LoteComprobanteEvento as Evento,
    LoteComprobanteFila as Fila,
    LoteComprobanteGrupo as Grupo,
)
from app.models.usuario import Usuario
from app.models.usuario_emisor_acceso import UsuarioEmisorAcceso
from app.models.comprobante import Comprobante
from app.models.idempotencia_fiscal import LoteDuplicadoEvidencia
from sqlalchemy.orm import selectinload
from app.services.duplicados_lotes_service import (
    DuplicadosLotesService,
    DuplicadosLoteError,
)
from app.schemas.comprobante import EmitirComprobanteResponse
from app.schemas.lote_comprobante import (
    LoteAccionResponse,
    LoteComprobanteResponse,
    LoteProcesamientoResponse,
    VerificacionLote,
)
from app.services.autorizacion_emisor_service import puede_operar_empresa
from app.services.elegibilidad_rece_service import (
    ContextoElegibilidadRece,
    ElegibilidadReceError,
    ElegibilidadReceService,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.lote_comprobantes_service import (
    LoteComprobanteConflictoError,
    LoteComprobantesService,
)
from app.services.recuperacion_comprobante_service import (
    _datos_comprobante,
    _datos_items,
    contenido_coincidente,
    consultar_autorizacion_coincidente,
    evidencia_del_intento,
    recuperar_comprobante,
)

INCIERTO = "requiere_reconciliacion"
SIN_ENVIAR = (
    "Sin enviar. Podés seleccionarlo en un nuevo reintento con confirmación fiscal."
)
POR_CONSULTA = 5


def _rechazado(i):
    return (
        i.estado == "rechazado_arca"
        and i.resultado_fiscal_at is not None
        and i.categoria_error in {"arca_no_aprobado", "arca_rechazo_global_excluyente"}
        and i.cae is None
        and i.comprobante_id is None
    )


def _cerrado_sin_envio(intento, guarda):
    return (
        guarda is not None
        and guarda.fase == "cerrada_pre_arca"
        and guarda.arca_iniciada_en is None
        and guarda.cerrada_en is not None
        and intento.estado == "fallido_verificado"
        and intento.solicitud_arca_at is None
        and intento.resultado_fiscal_at is None
        and intento.cae is None
        and intento.comprobante_id is None
    )


def _particion(evento, material, miembros):
    if not evento or evento.get("seleccion_hash") != material["grupos_hash"]:
        return None
    partes = [evento.get(k) for k in ("procesados", "sublote", "remanente")]
    if not all(
        isinstance(p, list)
        and all(isinstance(g, int) and not isinstance(g, bool) for g in p)
        for p in partes
    ):
        return None
    if sorted(g for parte in partes for g in parte) != sorted(material["grupo_ids"]):
        return None
    if evento.get("guardas") != miembros or not partes[1]:
        return None
    # Un bloque enviado pertenece a una sola guarda y tiene todos sus intentos.
    if sorted(partes[1]) not in miembros.values():
        return None
    if set(partes[0] + partes[1]) != {g for ids in miembros.values() for g in ids}:
        return None
    return set(partes[2])


@dataclass
class Recuperacion:
    lote: Lote
    operacion: Operacion
    grupos: dict
    intentos: dict
    guardas: dict
    sin_enviar: set
    membresia_probada: bool
    vinculados: set[int]

    def autorizado(self, g):
        i = self.intentos.get(g.id)
        return bool(
            g.id in self.vinculados
            and i
            and i.estado == "autorizado"
            and g.estado == "autorizado"
            and i.comprobante_id
            and i.comprobante_id == g.comprobante_id
            and i.cae
            and i.cae == g.cae
            and i.numero_planificado == g.numero_asignado
        )

    def rechazado(self, g):
        i = self.intentos.get(g.id)
        return (
            i is not None
            and _rechazado(i)
            and g.estado == "fallido"
            and not g.cae
            and not g.comprobante_id
        )

    def resumen(self):
        autorizados = sum(self.autorizado(g) for g in self.grupos.values())
        rechazados = sum(self.rechazado(g) for g in self.grupos.values())
        return VerificacionLote(
            operacion_id=self.operacion.id,
            autorizados=autorizados,
            pendientes=len(self.grupos)
            - autorizados
            - rechazados
            - len(self.sin_enviar),
            sin_enviar=len(self.sin_enviar),
            rechazados=rechazados,
        )

    def candidato(self, gid):
        i = self.intentos.get(gid)
        if not i or i.estado not in {INCIERTO, "en_proceso", "autorizado"}:
            return None
        g = self.grupos[gid]
        guarda = self.guardas[i.guarda_rece_id]
        if (
            self.autorizado(g)
            or i.solicitud_arca_at is None
            or not guarda.arca_iniciada_en
            or guarda.fase not in {INCIERTO, "arca_iniciada", "cerrada_terminal"}
            or (guarda.fase == "cerrada_terminal" and i.estado != "autorizado")
            or g.estado not in {INCIERTO, "reintentando", "validado", "autorizado"}
            or g.numero_asignado not in (None, i.numero_planificado)
        ):
            return None
        try:
            evidencia = evidencia_del_intento(i)
        except EvidenciaFiscalError:
            return None
        return evidencia, (
            self.operacion.id,
            i.id,
            i.evidencia_hash,
            guarda.token,
            guarda.fase,
        )


class ReconciliacionLoteService:
    def __init__(self, db):
        self.db = db
        self.lotes = LoteComprobantesService(db)

    async def _acceso(self, usuario_id, empresa_id, *, publicar=False):
        consulta = select(Usuario).where(Usuario.id == usuario_id)
        if publicar:
            consulta = consulta.with_for_update(read=True)
        usuario = await self.db.scalar(
            consulta.execution_options(populate_existing=True)
        )
        if usuario and usuario.activo:
            if not publicar:
                permitido = await puede_operar_empresa(self.db, usuario, empresa_id)
            elif usuario.es_admin:
                permitido = True
            else:
                # La revocación y el commit de recuperación se ordenan por la
                # misma fila de acceso. Nunca mantener este bloqueo al consultar ARCA.
                permitido = (
                    await self.db.scalar(
                        select(UsuarioEmisorAcceso.usuario_id)
                        .where(
                            UsuarioEmisorAcceso.usuario_id == usuario_id,
                            UsuarioEmisorAcceso.empresa_id == empresa_id,
                        )
                        .with_for_update(read=True)
                    )
                    is not None
                )
            if permitido:
                return
        raise PermissionError("Perdiste el permiso para operar este emisor.")

    async def _grafo(self, lote_id, empresa_id, op_id, *, bloquear=False):
        async def filas(modelo, *criterios):
            stmt = select(modelo).where(*criterios).order_by(modelo.id)
            if bloquear:
                stmt = stmt.with_for_update()
            return (
                await self.db.scalars(stmt.execution_options(populate_existing=True))
            ).all()

        operaciones = await filas(
            Operacion,
            Operacion.id == op_id,
            Operacion.lote_id == lote_id,
            Operacion.empresa_id == empresa_id,
            Operacion.estado == INCIERTO,
            Operacion.tipo_operacion.in_({"procesar_lote", "reintentar_fallidos_lote"}),
        )
        if not operaciones:
            return None
        op = operaciones[0]
        intentos = await filas(Intento, Intento.operacion_id == op.id)
        guardas = {g.id: g for g in await filas(Guarda, Guarda.operacion_id == op.id)}
        lotes = await filas(Lote, Lote.id == lote_id, Lote.empresa_id == empresa_id)
        if not lotes or not intentos or not guardas:
            return None
        lote = lotes[0]
        meta = lote.metadata_json or {}
        material = meta.get("pf19b_rece_material")
        if (
            lote.estado != INCIERTO
            or lote.compactado_at
            or meta.get("operacion_idempotente_id") != op.id
            or not IdempotenciaFiscalService.material_rece_valido(
                material, empresa_id=empresa_id
            )
        ):
            return None
        if op.response_json is None and not await self.db.scalar(
            select(Operacion.response_json.is_(None)).where(Operacion.id == op.id)
        ):
            return None
        if not self._respuesta_compatible(op, lote, material):
            return None
        seleccion = material["grupo_ids"]
        grupos = await filas(Grupo, Grupo.lote_id == lote.id, Grupo.id.in_(seleccion))
        if not IdempotenciaFiscalService.material_rece_coincide_grupos(
            material, empresa_id=empresa_id, grupos=grupos
        ):
            return None
        if any(g.duplicados_reserva_operacion_id not in (None, op.id) for g in grupos):
            return None
        if not await self._snapshots_validos(op, grupos):
            return None
        por_grupo = {g.id: g for g in grupos}
        if len({i.grupo_id for i in intentos}) != len(intentos):
            return None
        miembros = defaultdict(list)
        for i in intentos:
            g = por_grupo.get(i.grupo_id)
            guarda = guardas.get(i.guarda_rece_id)
            if (
                not g
                or not guarda
                or i.lote_id != lote.id
                or i.empresa_id != empresa_id
                or i.duplicados_generacion_id != op.duplicados_generacion_id
                or i.tipo_comprobante != g.tipo_comprobante
                or i.punto_venta_numero != g.punto_venta_numero
                or g.punto_venta_id != i.punto_venta_id
                or g.ambiente != i.ambiente
                or guarda.empresa_id != empresa_id
                or guarda.punto_venta_id != i.punto_venta_id
                or guarda.ambiente != i.ambiente
                or guarda.elegibilidad_revision_id
                != i.punto_venta_elegibilidad_revision_id
                or guarda.punto_venta_revision_fiscal != i.punto_venta_revision_fiscal
                or g.punto_venta_elegibilidad_revision_id
                != guarda.elegibilidad_revision_id
                or g.punto_venta_revision_fiscal != guarda.punto_venta_revision_fiscal
            ):
                return None
            miembros[str(guarda.id)].append(g.id)
        if set(miembros) != {str(k) for k in guardas}:
            return None
        detalle = (
            select(Fila.grupo_id, Fila.lote_id, Fila.comprobante_ref)
            .where(Fila.grupo_id.in_(seleccion))
            .order_by(Fila.id)
        )
        if bloquear:
            detalle = detalle.with_for_update()
        detalle = (await self.db.execute(detalle)).all()
        if {f.grupo_id for f in detalle} != set(seleccion) or any(
            f.lote_id != lote.id
            or f.comprobante_ref != por_grupo[f.grupo_id].comprobante_ref
            for f in detalle
        ):
            return None
        eventos = [
            e
            for e in await self.db.scalars(
                select(Evento.metadata_json).where(
                    Evento.lote_id == lote.id, Evento.accion == "frontera_envio_lote"
                )
            )
            if isinstance(e, dict) and e.get("operacion_id") == op.id
        ]
        por_intento = {i.grupo_id: i for i in intentos}
        remanente = (
            _particion(
                eventos[0], material, {k: sorted(v) for k, v in miembros.items()}
            )
            if len(eventos) == 1
            else None
        )
        historicos = await self.db.execute(
            select(Intento, Guarda)
            .outerjoin(Guarda, Guarda.id == Intento.guarda_rece_id)
            .where(
                Intento.grupo_id.in_(seleccion),
                Intento.operacion_id.is_distinct_from(op.id),
            )
        )
        ambiguos = {
            i.grupo_id
            for i, guarda in historicos
            if not (
                op.tipo_operacion == "reintentar_fallidos_lote"
                and i.operacion_id is not None
                and i.operacion_id < op.id
                and (_rechazado(i) or _cerrado_sin_envio(i, guarda))
            )
        }
        if ambiguos:
            return None
        if not await self._generacion_coincide(op, grupos):
            return None
        vinculados = await self._autorizaciones_locales(intentos)
        sin_enviar = {
            gid
            for gid in remanente or ()
            if gid not in por_intento
            and por_grupo[gid].estado in {INCIERTO, "validado", "reintentando"}
            and all(
                v is None
                for v in (
                    por_grupo[gid].cae,
                    por_grupo[gid].numero_asignado,
                    por_grupo[gid].comprobante_id,
                )
            )
        }
        for gid, i in por_intento.items():
            if (
                _cerrado_sin_envio(i, guardas[i.guarda_rece_id])
                and not por_grupo[gid].cae
                and not por_grupo[gid].comprobante_id
                and not por_grupo[gid].numero_asignado
            ):
                sin_enviar.add(gid)
        completa = remanente is not None or (
            not eventos and set(por_intento) == set(seleccion)
        )
        return Recuperacion(
            lote, op, por_grupo, por_intento, guardas, sin_enviar, completa, vinculados
        )

    async def _generacion_coincide(self, op, grupos):
        generacion = (
            await self.db.get(LoteDuplicadoEvidencia, op.duplicados_generacion_id)
            if op.duplicados_generacion_id
            else None
        )
        if generacion is None or not isinstance(op.control_duplicados_json, dict):
            return False
        duplicados = DuplicadosLotesService(self.db)
        try:
            await duplicados._validar_integridad_generacion(
                generacion,
                operacion_id=op.id,
                empresa_id=op.empresa_id,
                lote_id=op.lote_id,
                ambiente=grupos[0].ambiente,
            )
        except DuplicadosLoteError:
            return False
        original = generacion.control_snapshot_json.get("seleccion_original")
        if (
            not isinstance(original, list)
            or op.control_duplicados_json.get("seleccion_original") != original
            or op.control_duplicados_json.get("duplicados_generacion_id")
            != generacion.id
        ):
            return False
        # La generación de duplicados puede cubrir el lote raíz completo. El
        # material RECE y la frontera de envío delimitan el reintento confirmado.
        seleccionados = {g.id for g in grupos}
        seleccion = duplicados._seleccion_material(
            sorted(grupos, key=lambda g: (g.orden, g.id))
        )
        return [
            x
            for x in original
            if isinstance(x, dict) and x.get("grupo_id") in seleccionados
        ] == seleccion

    async def _autorizaciones_locales(self, intentos):
        vinculados = set()
        autorizados = {
            i.comprobante_id: i
            for i in intentos
            if i.estado == "autorizado" and i.comprobante_id
        }
        if autorizados:
            locales = await self.db.scalars(
                select(Comprobante)
                .where(Comprobante.id.in_(autorizados))
                .options(selectinload(Comprobante.items))
            )
            for comprobante in locales:
                i = autorizados[comprobante.id]
                try:
                    evidencia = evidencia_del_intento(i)
                except EvidenciaFiscalError:
                    continue
                if (
                    i.cae
                    and i.cae_vencimiento
                    and contenido_coincidente(
                        comprobante,
                        _datos_comprobante(evidencia, i.cae, i.cae_vencimiento),
                        _datos_items(evidencia),
                    )
                ):
                    vinculados.add(i.grupo_id)
        return vinculados

    async def _snapshots_validos(self, op, grupos):
        contextos = {
            ContextoElegibilidadRece(
                empresa_id=g.empresa_id,
                punto_venta_id=g.punto_venta_id,
                punto_venta_numero=g.punto_venta_numero,
                ambiente=g.ambiente,
                elegibilidad_revision_id=g.punto_venta_elegibilidad_revision_id,
                punto_venta_revision_fiscal=g.punto_venta_revision_fiscal,
            )
            for g in grupos
        }
        snapshots = (
            await self.db.scalars(
                select(OperacionIdempotenteElegibilidadRece).where(
                    OperacionIdempotenteElegibilidadRece.operacion_id == op.id
                )
            )
        ).all()
        campos = (
            "empresa_id",
            "punto_venta_id",
            "ambiente",
            "elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
        )

        def identidad(c):
            return tuple(getattr(c, k) for k in campos)

        return (
            {identidad(c) for c in contextos} == {identidad(s) for s in snapshots}
            and len(contextos) == len(snapshots)
            and op.rece_snapshot_hash
            == ElegibilidadReceService.calcular_digest_contextos(list(contextos))
        )

    def _respuesta_compatible(self, op, lote, material):
        raw = op.response_json
        if raw is None:
            return True
        if IdempotenciaFiscalService.respuesta_worker_en_progreso_valida(
            raw,
            lote_id=lote.id,
            empresa_id=lote.empresa_id,
            operacion_id=op.id,
            material_rece=material,
        ):
            return True
        try:
            if op.tipo_operacion == "procesar_lote" or lote.metadata_json.get(
                "reintento_background"
            ):
                respuesta = LoteProcesamientoResponse.model_validate(raw)
                if respuesta.en_progreso:
                    return False
            else:
                respuesta = LoteAccionResponse.model_validate(raw)
        except ValidationError:
            return False
        meta = respuesta.lote.metadata_json or {}
        return (
            meta.get("operacion_idempotente_id") == op.id
            and meta.get("pf19b_rece_material") == material
            and self.lotes.respuesta_lote_coincide_operacion(
                respuesta,
                estado_operacion=op.estado,
                operacion_id=op.id,
                lote_id=lote.id,
                empresa_id=lote.empresa_id,
            )
        )

    async def resumen(self, lote):
        op_id = (lote.metadata_json or {}).get("operacion_idempotente_id")
        if (
            lote.estado != INCIERTO
            or not isinstance(op_id, int)
            or isinstance(op_id, bool)
        ):
            return None
        grafo = await self._grafo(lote.id, lote.empresa_id, op_id)
        return grafo.resumen() if grafo else None

    async def verificar(self, lote_id, empresa_id, usuario_id, op_id, despues=0):
        await self._acceso(usuario_id, empresa_id)
        grafo = await self._grafo(lote_id, empresa_id, op_id)
        if grafo is None:
            return await self._releer(lote_id, empresa_id, usuario_id, op_id)
        candidatos = [
            gid
            for gid in sorted(grafo.intentos)
            if gid > despues
            and not grafo.autorizado(grafo.grupos[gid])
            and not grafo.rechazado(grafo.grupos[gid])
        ]
        pagina = candidatos[:POR_CONSULTA]
        siguiente = pagina[-1] if len(candidatos) > len(pagina) else None
        # El rollback expira los objetos ORM. Conservar sólo los sobres inmutables.
        consultas = [(gid, grafo.candidato(gid)) for gid in pagina]
        await self.db.rollback()
        for gid, candidato in consultas:
            if candidato is None:
                continue
            await self._acceso(usuario_id, empresa_id)
            evidencia, huella = candidato
            confirmado = await consultar_autorizacion_coincidente(self.db, evidencia)
            await self.db.rollback()
            if confirmado:
                await self._publicar(
                    lote_id, empresa_id, usuario_id, op_id, gid, huella, confirmado
                )
        await self._publicar(lote_id, empresa_id, usuario_id, op_id)
        resumen = await self._releer(lote_id, empresa_id, usuario_id, op_id)
        resumen.siguiente = siguiente if resumen.pendientes else None
        return resumen

    async def _releer(self, lote_id, empresa_id, usuario_id, op_id):
        await self._acceso(usuario_id, empresa_id)
        # La selección puede haber cambiado por un reintento posterior. El replay
        # pertenece a la operación consultada, incluso después de cambiar de lote activo.
        grafo = await self._grafo(lote_id, empresa_id, op_id)
        if grafo:
            return grafo.resumen()
        op = await self.db.scalar(
            select(Operacion)
            .where(
                Operacion.id == op_id,
                Operacion.lote_id == lote_id,
                Operacion.empresa_id == empresa_id,
                Operacion.estado == "finalizado",
            )
            .execution_options(populate_existing=True)
        )
        if op and isinstance(op.response_json, dict):
            publicado = op.response_json.get("lote", {})
            if (
                isinstance(publicado, dict)
                and publicado.get("id") == lote_id
                and publicado.get("empresa_id") == empresa_id
            ):
                ultimo = (publicado.get("metadata_json") or {}).get(
                    "verificacion_final"
                )
                if isinstance(ultimo, dict) and ultimo.get("operacion_id") == op_id:
                    return VerificacionLote.model_validate(ultimo)
        raise LoteComprobanteConflictoError(
            "La operación cambió o la evidencia requiere revisión. Actualizá el lote."
        )

    async def _publicar(
        self,
        lote_id,
        empresa_id,
        usuario_id,
        op_id,
        gid=None,
        huella=None,
        confirmado=None,
    ):
        try:
            grafo = await self._grafo(lote_id, empresa_id, op_id, bloquear=True)
            await self._acceso(usuario_id, empresa_id, publicar=True)
            if grafo is None:
                return
            if gid is not None:
                candidato = grafo.candidato(gid)
                if not candidato or candidato[1] != huella:
                    return
                if not await self._recuperar(
                    grafo, gid, candidato[0], confirmado, usuario_id
                ):
                    return
            await self._cerrar(grafo, usuario_id)
            await self.db.commit()
        except (
            IntegrityError,
            ElegibilidadReceError,
            *DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS,
        ):
            # Si el commit fue ambiguo, el llamador relee desde una transacción nueva.
            await self.db.rollback()
        finally:
            await self.db.rollback()

    async def _recuperar(self, grafo, gid, evidencia, confirmado, usuario_id):
        i, g = grafo.intentos[gid], grafo.grupos[gid]
        cae, vence = confirmado
        if (
            i.cae not in (None, cae)
            or g.cae not in (None, cae)
            or i.cae_vencimiento not in (None, vence)
        ):
            return False
        comprobante = await recuperar_comprobante(self.db, i, evidencia, cae, vence)
        if comprobante is None or g.comprobante_id not in (None, comprobante.id):
            return False
        ajeno = await self.db.scalar(
            select(Grupo.id).where(
                Grupo.comprobante_id == comprobante.id, Grupo.id != gid
            )
        )
        if ajeno is not None:
            return False
        respuesta = EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante.id,
            numero=i.numero_planificado,
            tipo_comprobante=i.tipo_comprobante,
            punto_venta=i.punto_venta_numero,
            fecha=i.fecha_emision,
            total=i.total,
            cae=cae,
            cae_vencimiento=vence,
            mensaje="Comprobante recuperado y verificado en ARCA.",
        )
        await IdempotenciaFiscalService(self.db).actualizar_intento_desde_respuesta(
            i, respuesta, commit=False, conservar_instante_fiscal=True
        )
        await self.lotes._aplicar_resultado_emision_grupo(g, respuesta)
        grafo.vinculados.add(gid)
        self.lotes._registrar_evento_lote(
            grafo.lote.id,
            "verificar_autorizacion",
            usuario_id,
            grupo_id=gid,
            metadata_json={
                "operacion_id": grafo.operacion.id,
                "intento_id": i.id,
                "comprobante_id": comprobante.id,
            },
        )
        return True

    async def _cerrar(self, grafo, usuario_id):
        resumen = grafo.resumen()
        lote, op = grafo.lote, grafo.operacion
        if grafo.membresia_probada:
            por_guarda = defaultdict(list)
            for intento in grafo.intentos.values():
                por_guarda[intento.guarda_rece_id].append(
                    grafo.grupos[intento.grupo_id]
                )
            for guarda in grafo.guardas.values():
                hermanos = por_guarda[guarda.id]
                if (
                    guarda.fase in {INCIERTO, "arca_iniciada"}
                    and hermanos
                    and all(grafo.autorizado(g) or grafo.rechazado(g) for g in hermanos)
                ):
                    await ElegibilidadReceService(
                        self.db
                    ).cerrar_reconciliacion_verificada(guarda)
        terminal = (
            resumen.pendientes == 0
            and grafo.membresia_probada
            and all(
                g.fase in {"cerrada_pre_arca", "cerrada_terminal"}
                for g in grafo.guardas.values()
            )
        )
        for gid in grafo.sin_enviar:
            g = grafo.grupos[gid]
            mensajes = [
                (
                    SIN_ENVIAR
                    if terminal
                    else "Sin enviar. Primero verificá los comprobantes pendientes del lote."
                )
            ]
            g.mensajes_json = mensajes
            g.estado = "fallido" if terminal else INCIERTO
            if terminal:
                g.duplicados_reserva_operacion_id = None
            await self.lotes._marcar_filas(g, g.estado, mensajes)
        await self.db.flush()
        if terminal:
            lote.metadata_json = {
                **lote.metadata_json,
                "verificacion_final": resumen.model_dump(),
            }
            self.lotes._registrar_evento_lote(
                lote.id,
                "verificacion_lote_cerrada",
                usuario_id,
                metadata_json=resumen.model_dump(),
            )
            await self.lotes._actualizar_estado_lote(lote)
        else:
            lote.metadata_json = {
                **lote.metadata_json,
                "verificacion_parcial": resumen.model_dump(),
            }
            await self.lotes._actualizar_contadores_lote(lote)
        await self.db.flush()
        clase = LoteProcesamientoResponse
        if (
            op.tipo_operacion == "reintentar_fallidos_lote"
            and not lote.metadata_json.get("reintento_background")
        ):
            clase = LoteAccionResponse
        respuesta = clase(
            **({"en_progreso": False} if clase is LoteProcesamientoResponse else {}),
            lote=LoteComprobanteResponse.model_validate(lote),
            mensaje=lote.mensaje_resumen or "Verificación del lote."
        )
        op.response_json = respuesta.model_dump(mode="json")
        op.estado = "finalizado" if terminal else INCIERTO
