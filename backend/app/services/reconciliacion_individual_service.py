"""Recuperación de una emisión individual ya enviada a ARCA."""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.arca.exceptions import ArcaError
from app.arca.utils import clean_cuit
from app.core.config import settings
from app.core.database import DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS
from app.core.evidencia_fiscal import (
    CAMPOS_CONTEXTO,
    EvidenciaFiscalError,
    EvidenciaFiscalV1,
    comparar_evidencia,
    leer_evidencia,
)
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.elegibilidad_rece import (
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaGuardaEmisionRece,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.usuario import Usuario
from app.schemas.comprobante import (
    EmitirComprobanteResponse,
    EmisionIndividualPendiente,
)
from app.services.autorizacion_emisor_service import puede_operar_empresa
from app.services.elegibilidad_rece_service import (
    ContextoElegibilidadRece,
    ElegibilidadReceError,
    ElegibilidadReceService,
)
from app.services.facturacion_service import FacturacionService, ValidationError
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService

logger = logging.getLogger(__name__)

ESTADOS_PENDIENTES = {"en_proceso", "requiere_reconciliacion"}
COBERTURA_OPCIONAL = {
    "cbte_desde",
    "cbte_hasta",
    "condicion_iva_receptor_id",
    "cbtes_asoc.cuit",
    "cbtes_asoc.fecha_cbte",
}


@dataclass(frozen=True)
class IntentoRecuperable:
    intento: IntentoEmisionFiscal
    guarda: PuntoVentaGuardaEmisionRece
    evidencia: EvidenciaFiscalV1


def _fecha_fiscal(valor: str | None) -> date | None:
    if valor is None:
        return None
    if not re.fullmatch(r"[0-9]{8}", valor):
        raise ValueError("Fecha fiscal inválida")
    return date(int(valor[:4]), int(valor[4:6]), int(valor[6:]))


def _datos_comprobante(evidencia: EvidenciaFiscalV1, cae: str, vencimiento: date):
    contexto = evidencia.contexto
    solicitud = evidencia.solicitud_wsfe
    receptor = evidencia.presentacion.receptor
    importes = evidencia.importes_guardado
    return {
        "empresa_id": contexto.empresa_id,
        "punto_venta_id": contexto.punto_venta_id,
        "tipo_comprobante": contexto.tipo_comprobante,
        "numero": contexto.numero_planificado,
        "concepto": solicitud.concepto,
        "fecha_emision": _fecha_fiscal(solicitud.fecha_cbte),
        "fecha_servicio_desde": _fecha_fiscal(solicitud.fecha_serv_desde),
        "fecha_servicio_hasta": _fecha_fiscal(solicitud.fecha_serv_hasta),
        "fecha_vto_pago": _fecha_fiscal(solicitud.fecha_vto_pago),
        "fecha_vencimiento": _fecha_fiscal(solicitud.fecha_vto_pago),
        "subtotal": importes.subtotal,
        "iva_21": importes.iva_21,
        "iva_10_5": importes.iva_10_5,
        "iva_27": importes.iva_27,
        "total": importes.total,
        "descuento": 0,
        "otros_impuestos": solicitud.imp_trib,
        "moneda": solicitud.moneda_id,
        "cotizacion": solicitud.moneda_cotiz,
        "observaciones": evidencia.presentacion.observaciones,
        "receptor_tipo_documento": receptor.tipo_documento,
        "receptor_numero_documento": clean_cuit(receptor.numero_documento),
        "receptor_razon_social": receptor.razon_social,
        "receptor_condicion_iva": receptor.condicion_iva,
        "receptor_domicilio": receptor.domicilio,
        "estado": "autorizado",
        "cae": cae,
        "cae_vencimiento": vencimiento,
        "origen_emision": "factuflow",
    }


def _datos_items(evidencia: EvidenciaFiscalV1):
    return [
        {
            **item.model_dump(),
            "orden": item.orden if item.orden > 0 else indice,
            "subtotal": subtotal,
        }
        for indice, (item, subtotal) in enumerate(
            zip(
                evidencia.presentacion.items,
                evidencia.importes_guardado.subtotales_items,
            )
        )
    ]


class ReconciliacionIndividualService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.idempotencia = IdempotenciaFiscalService(db)

    @staticmethod
    def _operaciones(empresa_id: int):
        return select(OperacionIdempotente).where(
            OperacionIdempotente.empresa_id == empresa_id,
            OperacionIdempotente.tipo_operacion == "emitir_comprobante",
            OperacionIdempotente.lote_id.is_(None),
        )

    async def pendientes(self, empresa_id: int) -> list[EmisionIndividualPendiente]:
        consulta = (
            self._operaciones(empresa_id)
            .add_columns(IntentoEmisionFiscal)
            .join(
                IntentoEmisionFiscal,
                IntentoEmisionFiscal.operacion_id == OperacionIdempotente.id,
            )
            .join(
                PuntoVentaGuardaEmisionRece,
                PuntoVentaGuardaEmisionRece.id == IntentoEmisionFiscal.guarda_rece_id,
            )
            .where(
                OperacionIdempotente.estado.in_(ESTADOS_PENDIENTES),
                IntentoEmisionFiscal.empresa_id == empresa_id,
                IntentoEmisionFiscal.lote_id.is_(None),
                IntentoEmisionFiscal.grupo_id.is_(None),
                IntentoEmisionFiscal.estado.in_(ESTADOS_PENDIENTES),
                IntentoEmisionFiscal.numero_planificado.is_not(None),
                PuntoVentaGuardaEmisionRece.empresa_id == empresa_id,
                PuntoVentaGuardaEmisionRece.operacion_id == OperacionIdempotente.id,
                PuntoVentaGuardaEmisionRece.fase.in_(
                    {"arca_iniciada", "requiere_reconciliacion"}
                ),
            )
            .order_by(IntentoEmisionFiscal.id.desc())
        )
        return [
            EmisionIndividualPendiente(
                operacion_id=operacion.id,
                tipo_comprobante=intento.tipo_comprobante,
                punto_venta=intento.punto_venta_numero,
                numero=intento.numero_planificado,
                fecha=intento.fecha_emision,
            )
            for operacion, intento in (await self.db.execute(consulta)).all()
        ]

    async def verificar(
        self,
        *,
        empresa_id: int,
        usuario_id: int,
        operacion_id: int | None,
        clave: str | None
    ) -> EmitirComprobanteResponse | None:
        consulta = self._operaciones(empresa_id)
        if operacion_id is not None:
            consulta = consulta.where(OperacionIdempotente.id == operacion_id)
        else:
            consulta = consulta.where(OperacionIdempotente.idempotency_key == clave)
        operacion = (await self.db.execute(consulta)).scalar_one_or_none()
        if operacion is None:
            return None
        operacion_id = operacion.id
        if operacion.estado not in ESTADOS_PENDIENTES:
            return await self._terminal(operacion)

        grafo = await self._cargar_grafo(operacion, bloquear=False)
        if grafo is None:
            return None
        intento = grafo.intento
        pendiente = self._pendiente(intento)
        if not self._puede_consultar(grafo):
            return pendiente

        huella = (intento.id, intento.evidencia_hash, grafo.guarda.token)
        evidencia = grafo.evidencia
        await self.db.rollback()
        confirmado = await self._consultar(evidencia)
        await self.db.rollback()

        try:
            operacion = await self._bloquear_operacion(empresa_id, operacion_id)
            if not await self._tiene_acceso(usuario_id, empresa_id):
                return None
            if operacion is None:
                return None
            if operacion.estado not in ESTADOS_PENDIENTES:
                return await self._terminal(operacion)
            grafo = await self._cargar_grafo(operacion, bloquear=True)
            if (
                grafo is None
                or huella
                != (grafo.intento.id, grafo.intento.evidencia_hash, grafo.guarda.token)
                or not self._puede_consultar(grafo)
                or confirmado is None
            ):
                return pendiente
            return await self._cerrar(operacion, grafo, *confirmado)
        except (
            IntegrityError,
            ElegibilidadReceError,
            *DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS,
        ):
            await self.db.rollback()
            operacion = (await self.db.execute(consulta)).scalar_one_or_none()
            if operacion is not None and await self._tiene_acceso(
                usuario_id, empresa_id
            ):
                if operacion.estado not in ESTADOS_PENDIENTES:
                    return await self._terminal(operacion)
                return pendiente
            return None
        finally:
            await self.db.rollback()

    async def _bloquear_operacion(self, empresa_id, operacion_id):
        consulta = (
            self._operaciones(empresa_id)
            .where(OperacionIdempotente.id == operacion_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self.db.execute(consulta)).scalar_one_or_none()

    async def _tiene_acceso(self, usuario_id, empresa_id):
        usuario = await self.db.get(Usuario, usuario_id, populate_existing=True)
        return bool(
            usuario
            and usuario.activo
            and await puede_operar_empresa(self.db, usuario, empresa_id)
        )

    async def _terminal(self, operacion):
        return await self.idempotencia.validar_replay_individual_durable(
            operacion_id=operacion.id,
            empresa_id=operacion.empresa_id,
            respuesta_raw=operacion.response_json,
        )

    async def _cargar_grafo(self, operacion, *, bloquear) -> IntentoRecuperable | None:
        filas = []
        for modelo in (IntentoEmisionFiscal, PuntoVentaGuardaEmisionRece):
            consulta = select(modelo).where(modelo.operacion_id == operacion.id)
            if bloquear:
                consulta = consulta.with_for_update().execution_options(
                    populate_existing=True
                )
            resultados = (await self.db.execute(consulta)).scalars().all()
            if len(resultados) != 1:
                return None
            filas.append(resultados[0])
        intento, guarda = filas
        if (
            intento.empresa_id != operacion.empresa_id
            or guarda.empresa_id != operacion.empresa_id
            or intento.lote_id is not None
            or intento.grupo_id is not None
            or intento.duplicados_generacion_id is not None
            or intento.guarda_rece_id != guarda.id
            or intento.punto_venta_id != guarda.punto_venta_id
            or intento.ambiente != guarda.ambiente
            or intento.punto_venta_elegibilidad_revision_id
            != guarda.elegibilidad_revision_id
            or intento.punto_venta_revision_fiscal != guarda.punto_venta_revision_fiscal
            or intento.solicitud_arca_at is None
            or guarda.arca_iniciada_en is None
            or intento.estado not in ESTADOS_PENDIENTES
            or guarda.fase not in {"arca_iniciada", "requiere_reconciliacion"}
        ):
            return None
        contexto = ContextoElegibilidadRece(
            empresa_id=guarda.empresa_id,
            punto_venta_id=guarda.punto_venta_id,
            punto_venta_numero=intento.punto_venta_numero,
            ambiente=guarda.ambiente,
            elegibilidad_revision_id=guarda.elegibilidad_revision_id,
            punto_venta_revision_fiscal=guarda.punto_venta_revision_fiscal,
        )
        if (
            operacion.rece_snapshot_hash
            != ElegibilidadReceService.calcular_digest_contextos([contexto])
        ):
            return None
        snapshots = (
            await self.db.scalars(
                select(OperacionIdempotenteElegibilidadRece).where(
                    OperacionIdempotenteElegibilidadRece.operacion_id == operacion.id
                )
            )
        ).all()
        material = contexto.material_digest()
        del material["punto_venta_numero"]
        if len(snapshots) != 1 or any(
            getattr(snapshots[0], k) != v for k, v in material.items()
        ):
            return None
        try:
            evidencia = leer_evidencia(
                version=intento.evidencia_version,
                raw=intento.evidencia_json,
                sha256=intento.evidencia_hash,
                pertenencia={
                    campo: getattr(intento, campo)
                    for campo in (
                        *CAMPOS_CONTEXTO,
                        "total",
                        "fecha_emision",
                        "receptor_tipo_documento",
                        "receptor_numero_documento",
                    )
                },
            )
        except EvidenciaFiscalError:
            return None
        return IntentoRecuperable(intento, guarda, evidencia)

    @staticmethod
    def _puede_consultar(grafo):
        intento, guarda = grafo.intento, grafo.guarda
        if guarda.fase == "requiere_reconciliacion":
            return intento.estado == "requiere_reconciliacion"
        limite = datetime.utcnow() - timedelta(
            minutes=settings.fiscal_attempt_stale_minutes
        )
        return intento.estado == "en_proceso" and guarda.arca_iniciada_en <= limite

    async def _consultar(self, evidencia) -> tuple[str, date] | None:
        try:
            respuesta = await FacturacionService(self.db).consultar_intento_individual(
                evidencia.contexto
            )
            vencimiento = _fecha_fiscal(respuesta.cae_vencimiento)
        except (ArcaError, EvidenciaFiscalError, ValidationError, ValueError):
            return None
        if (
            respuesta.resultado != "A"
            or respuesta.emision_tipo != "CAE"
            or not re.fullmatch(r"[0-9]{14}", respuesta.cae or "")
            or vencimiento is None
        ):
            return None
        comparacion = comparar_evidencia(evidencia, respuesta)
        logger.info(
            "event=reconciliacion_individual_consulta intento=%s estado=%s campos=%s cobertura=%s",
            evidencia.contexto.id,
            comparacion.estado,
            comparacion.campos,
            comparacion.cobertura_desconocida,
        )
        if (
            respuesta.campos_invalidos
            or comparacion.estado != "coincidente"
            or not COBERTURA_OPCIONAL.issuperset(comparacion.cobertura_desconocida)
        ):
            return None
        return respuesta.cae, vencimiento

    @staticmethod
    def _pendiente(intento):
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=intento.tipo_comprobante,
            punto_venta=intento.punto_venta_numero,
            numero=intento.numero_planificado,
            fecha=intento.fecha_emision,
            total=intento.total,
            cae=intento.cae,
            cae_vencimiento=intento.cae_vencimiento,
            mensaje="La emisión sigue pendiente de verificación.",
            requiere_reconciliacion=True,
            categoria_error="arca_respuesta_incierta",
        )

    async def _cerrar(self, operacion, grafo, cae, vencimiento):
        intento, guarda = grafo.intento, grafo.guarda
        publicada = operacion.response_json
        if (
            (intento.cae is not None and intento.cae != cae)
            or (
                intento.cae_vencimiento is not None
                and intento.cae_vencimiento != vencimiento
            )
            or (
                publicada is not None
                and (
                    not isinstance(publicada, dict)
                    or publicada.get("exito") is not False
                    or publicada.get("requiere_reconciliacion") is not True
                    or publicada.get("cae") not in (None, cae)
                    or publicada.get("cae_vencimiento")
                    not in (None, vencimiento.isoformat())
                )
            )
        ):
            return self._pendiente(intento)

        datos = _datos_comprobante(grafo.evidencia, cae, vencimiento)
        items = _datos_items(grafo.evidencia)
        comprobante = (
            await self.db.execute(
                select(Comprobante)
                .where(
                    Comprobante.empresa_id == intento.empresa_id,
                    Comprobante.punto_venta_id == intento.punto_venta_id,
                    Comprobante.tipo_comprobante == intento.tipo_comprobante,
                    Comprobante.numero == intento.numero_planificado,
                )
                .options(selectinload(Comprobante.items))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if intento.comprobante_id is not None and (
            comprobante is None or comprobante.id != intento.comprobante_id
        ):
            return self._pendiente(intento)
        if comprobante is None:
            comprobante = Comprobante(
                **datos,
                items=[ComprobanteItem(**item) for item in items],
            )
            self.db.add(comprobante)
            await self.db.flush()
        elif (
            any(getattr(comprobante, k) != v for k, v in datos.items())
            or len(comprobante.items) != len(items)
            or any(
                any(getattr(guardado, k) != v for k, v in original.items())
                for guardado, original in zip(
                    sorted(comprobante.items, key=lambda item: item.id), items
                )
            )
        ):
            return self._pendiente(intento)
        elif (
            await self.db.scalar(
                select(IntentoEmisionFiscal.id)
                .where(
                    IntentoEmisionFiscal.comprobante_id == comprobante.id,
                    IntentoEmisionFiscal.id != intento.id,
                )
                .limit(1)
            )
            is not None
        ):
            return self._pendiente(intento)
        respuesta = EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante.id,
            tipo_comprobante=intento.tipo_comprobante,
            punto_venta=intento.punto_venta_numero,
            numero=intento.numero_planificado,
            fecha=intento.fecha_emision,
            cae=cae,
            cae_vencimiento=vencimiento,
            total=intento.total,
            mensaje="Comprobante recuperado y verificado en ARCA.",
        )
        pendiente = self._pendiente(intento)
        await self.idempotencia.actualizar_intento_desde_respuesta(
            intento, respuesta, commit=False, conservar_instante_fiscal=True
        )
        await ElegibilidadReceService(self.db).cerrar_reconciliacion_individual(guarda)
        publicada = await self.idempotencia.guardar_respuesta_operacion_cas(
            operacion_id=operacion.id,
            response_json=respuesta,
            estado="finalizado",
            estado_esperado=operacion.estado,
            commit=False,
        )
        if not publicada:
            return pendiente
        await self.db.commit()
        logger.info(
            "event=reconciliacion_individual_cerrada operacion=%s", operacion.id
        )
        return respuesta
