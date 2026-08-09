"""Servicios de idempotencia y deduplicación fiscal."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import exists, inspect as sa_inspect, null, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.arca.utils import clean_cuit
from app.core.database import DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS
from app.models.comprobante import Comprobante
from app.models.idempotencia_fiscal import (
    ESTADOS_INTENTO_FISCAL_BLOQUEANTES,
    ESTADOS_RESERVA_FISCAL_ACTIVA,
    IntentoEmisionFiscal,
    OperacionIdempotente,
)
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, EmitirComprobanteResponse

if TYPE_CHECKING:
    from app.services.elegibilidad_rece_service import ContextoElegibilidadRece


class CreacionOperacionAmbiguaError(Exception):
    """Indica que esta request pudo crear una operación sin confirmarlo."""

    def __init__(self, error_original: Exception) -> None:
        """Conserva el error DB temporal que volvió ambigua la creación."""
        self.error_original = error_original
        super().__init__(str(error_original))


class IdempotenciaFiscalError(Exception):
    """Error funcional del control de idempotencia fiscal."""

    def __init__(self, status_code: int, detail: Any) -> None:
        """Inicializa el error con estado HTTP sugerido y detalle seguro."""
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


class IdempotenciaFiscalService:
    """Coordina operaciones idempotentes e intentos fiscales durables."""

    ESTADOS_INTENTO_ACTIVOS = ESTADOS_RESERVA_FISCAL_ACTIVA
    ESTADOS_INTENTO_BLOQUEANTES = ESTADOS_INTENTO_FISCAL_BLOQUEANTES

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el servicio con una sesión async."""
        self.db = db

    @staticmethod
    def respuesta_worker_en_progreso_valida(
        response_json: Any,
        *,
        lote_id: int,
        empresa_id: int,
        operacion_id: int,
        material_rece: dict[str, Any],
    ) -> bool:
        """Reconoce solo el ownership durable exacto del worker de un lote."""
        if not isinstance(response_json, dict) or set(response_json) != {
            "lote",
            "mensaje",
            "en_progreso",
        }:
            return False
        lote = response_json.get("lote")
        if (
            response_json.get("en_progreso") is not True
            or not isinstance(response_json.get("mensaje"), str)
            or not response_json["mensaje"].strip()
            or not isinstance(lote, dict)
            or lote.get("id") != lote_id
            or lote.get("empresa_id") != empresa_id
            or lote.get("estado") not in {"en_cola", "procesando"}
            or lote.get("modo_procesamiento") != "background"
            or lote.get("procesamiento_async") is not True
        ):
            return False
        metadata = lote.get("metadata_json")
        if (
            not isinstance(metadata, dict)
            or metadata.get("operacion_idempotente_id") != operacion_id
        ):
            return False
        material = metadata.get("pf19b_rece_material")
        if (
            not isinstance(material, dict)
            or set(material) != {"grupo_ids", "grupos_hash", "grupos"}
            or material != material_rece
        ):
            return False
        grupos = material.get("grupos")
        grupo_ids = material.get("grupo_ids")
        grupos_hash = material.get("grupos_hash")
        if (
            not isinstance(grupos, list)
            or not grupos
            or not isinstance(grupo_ids, list)
            or not grupo_ids
            or not isinstance(grupos_hash, str)
            or len(grupos_hash) != 64
        ):
            return False
        try:
            ids_normalizados = [int(grupo_id) for grupo_id in grupo_ids]
        except (TypeError, ValueError):
            return False
        if len(ids_normalizados) != len(set(ids_normalizados)):
            return False
        campos_grupo = {
            "grupo_id",
            "empresa_id",
            "punto_venta_id",
            "punto_venta_numero",
            "ambiente",
            "elegibilidad_revision_id",
            "punto_venta_revision_fiscal",
            "tipo_comprobante",
            "payload_hash",
        }
        grupos_normalizados: list[int] = []
        for grupo in grupos:
            if not isinstance(grupo, dict) or not campos_grupo.issubset(grupo):
                return False
            try:
                grupo_id = int(grupo["grupo_id"])
                grupo_empresa_id = int(grupo["empresa_id"])
                punto_venta_id = int(grupo["punto_venta_id"])
                punto_venta_numero = int(grupo["punto_venta_numero"])
                revision_id = int(grupo["elegibilidad_revision_id"])
                revision_fiscal = int(grupo["punto_venta_revision_fiscal"])
                tipo_comprobante = int(grupo["tipo_comprobante"])
            except (TypeError, ValueError):
                return False
            if (
                grupo_empresa_id != empresa_id
                or punto_venta_id <= 0
                or not 1 <= punto_venta_numero <= 99999
                or grupo.get("ambiente") not in {"homologacion", "produccion"}
                or revision_id <= 0
                or revision_fiscal <= 0
                or tipo_comprobante <= 0
                or not isinstance(grupo.get("payload_hash"), str)
                or len(grupo["payload_hash"]) != 64
            ):
                return False
            grupos_normalizados.append(grupo_id)
        if grupos_normalizados != ids_normalizados:
            return False
        grupos_hash_calculado = hashlib.sha256(
            json.dumps(
                grupos,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return grupos_hash_calculado == grupos_hash

    @classmethod
    def operacion_conserva_ownership_pre_arca(
        cls,
        operacion: OperacionIdempotente,
        *,
        respuesta_es_sql_null: bool,
        lote_background: bool | None,
        material_rece: dict[str, Any] | None,
    ) -> bool:
        """Valida los dos ownerships admitidos antes de iniciar ARCA."""
        if (
            operacion.estado != "en_proceso"
            or not isinstance(operacion.rece_snapshot_hash, str)
            or len(operacion.rece_snapshot_hash) != 64
        ):
            return False
        if operacion.tipo_operacion == "emitir_comprobante":
            return (
                operacion.lote_id is None
                and lote_background is None
                and respuesta_es_sql_null
            )
        if operacion.tipo_operacion == "reintentar_fallidos_lote":
            return (
                operacion.lote_id is not None
                and lote_background is False
                and respuesta_es_sql_null
            )
        if operacion.tipo_operacion != "procesar_lote" or operacion.lote_id is None:
            return False
        if lote_background is False:
            return respuesta_es_sql_null
        if lote_background is not True or material_rece is None:
            return False
        return cls.respuesta_worker_en_progreso_valida(
            operacion.response_json,
            lote_id=int(operacion.lote_id),
            empresa_id=int(operacion.empresa_id),
            operacion_id=int(operacion.id),
            material_rece=material_rece,
        )

    @staticmethod
    def validar_idempotency_key(idempotency_key: str | None) -> str:
        """Valida y normaliza una clave de idempotencia de cliente."""
        key = (idempotency_key or "").strip()
        if not key:
            raise IdempotenciaFiscalError(
                400,
                {
                    "mensaje": "La operación fiscal requiere X-Idempotency-Key.",
                    "errores": [
                        "Volvé a confirmar la emisión desde la interfaz antes de continuar."
                    ],
                },
            )
        if len(key) > 128:
            raise IdempotenciaFiscalError(
                400,
                {
                    "mensaje": "X-Idempotency-Key excede el largo máximo.",
                    "errores": ["La clave no puede superar 128 caracteres."],
                },
            )
        return key

    @classmethod
    def calcular_payload_hash(cls, payload: dict[str, Any]) -> str:
        """Calcula un hash estable del payload idempotente."""
        normalizado = cls._normalizar_para_hash(payload)
        encoded = json.dumps(
            normalizado,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def payload_sin_confirmacion_duplicado(payload: dict[str, Any]) -> dict[str, Any]:
        """Quita la confirmación de duplicado del material idempotente."""
        limpio = dict(payload)
        limpio.pop("confirmacion_duplicado_logico", None)
        limpio.pop("x_confirmacion_duplicado_logico", None)
        return limpio

    async def obtener_o_crear_operacion(
        self,
        *,
        empresa_id: int,
        usuario_id: int | None,
        idempotency_key: str | None,
        tipo_operacion: str,
        payload_hash: str,
        lote_id: int | None = None,
        contextos_rece: list[ContextoElegibilidadRece] | None = None,
    ) -> tuple[OperacionIdempotente, bool]:
        """Obtiene o crea operación, asociaciones y digest atómicamente."""
        from app.services.elegibilidad_rece_service import ElegibilidadReceService

        key = self.validar_idempotency_key(idempotency_key)
        operacion = await self.obtener_operacion_existente(
            empresa_id=empresa_id,
            idempotency_key=key,
            payload_hash=payload_hash,
        )
        if operacion is not None:
            if contextos_rece:
                await ElegibilidadReceService(self.db).validar_operacion_para_continuar(
                    operacion_id=operacion.id,
                    empresa_id=empresa_id,
                    contextos_esperados=contextos_rece,
                )
            return operacion, False
        if not contextos_rece:
            raise IdempotenciaFiscalError(
                409,
                {
                    "mensaje": (
                        "No se pudo crear la operación sin un snapshot RECE vigente."
                    ),
                    "errores": [
                        "Revalidá el punto de venta antes de volver a confirmar."
                    ],
                    "categoria_error": "elegibilidad_rece_no_verificada",
                },
            )

        operacion = OperacionIdempotente(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            idempotency_key=key,
            tipo_operacion=tipo_operacion,
            payload_hash=payload_hash,
            lote_id=lote_id,
            estado="en_proceso",
        )
        self.db.add(operacion)
        try:
            await self.db.flush()
            await ElegibilidadReceService(self.db).agregar_snapshots_a_operacion(
                operacion,
                contextos_rece,
            )
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            operacion = await self._obtener_operacion(empresa_id, key)
            if operacion is None:
                raise
            self._validar_payload_operacion(operacion, payload_hash)
            await ElegibilidadReceService(self.db).validar_operacion_para_continuar(
                operacion_id=operacion.id,
                empresa_id=empresa_id,
                contextos_esperados=contextos_rece,
            )
            return operacion, False
        except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS as exc:
            raise CreacionOperacionAmbiguaError(exc) from exc

        try:
            await self.db.refresh(operacion)
        except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS as exc:
            raise CreacionOperacionAmbiguaError(exc) from exc
        return operacion, True

    async def obtener_operacion_existente(
        self,
        *,
        empresa_id: int,
        idempotency_key: str | None,
        payload_hash: str,
    ) -> OperacionIdempotente | None:
        """Busca una operación sin crearla y conserva el conflicto de payload."""
        key = self.validar_idempotency_key(idempotency_key)
        operacion = await self._obtener_operacion(empresa_id, key)
        if operacion is not None:
            self._validar_payload_operacion(operacion, payload_hash)
        return operacion

    async def guardar_respuesta_operacion_cas(
        self,
        *,
        operacion_id: int,
        response_json: Any,
        estado: str,
        estado_esperado: str | set[str],
        respuesta_esperada_nula: bool = False,
        commit: bool = True,
    ) -> bool:
        """Publica una respuesta solo si la operación conserva su estado esperado."""
        condicion_estado = (
            OperacionIdempotente.estado == estado_esperado
            if isinstance(estado_esperado, str)
            else OperacionIdempotente.estado.in_(estado_esperado)
        )
        condiciones = [
            OperacionIdempotente.id == operacion_id,
            condicion_estado,
        ]
        if respuesta_esperada_nula:
            condiciones.append(OperacionIdempotente.response_json.is_(None))
        result = await self.db.execute(
            update(OperacionIdempotente)
            .where(*condiciones)
            .values(
                response_json=jsonable_encoder(response_json),
                estado=estado,
            )
        )
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
        return result.rowcount == 1

    async def guardar_resultado_operacion_sync(
        self,
        operacion: OperacionIdempotente,
        *,
        response_json: Any,
        estado: str,
    ) -> OperacionIdempotente:
        """Publica un resultado sync sin reabrir ni sobrescribir otra operación."""
        estado_esperado = (
            "requiere_reconciliacion"
            if estado == "requiere_reconciliacion"
            else "en_proceso"
        )
        identidad = sa_inspect(operacion).identity
        if not identidad:
            raise SQLAlchemyTimeoutError(
                "La operación fiscal no conserva una identidad durable."
            )
        publicada = await self.guardar_respuesta_operacion_cas(
            operacion_id=int(identidad[0]),
            response_json=response_json,
            estado=estado,
            estado_esperado=estado_esperado,
            respuesta_esperada_nula=True,
            commit=False,
        )
        if not publicada:
            await self.db.rollback()
            raise SQLAlchemyTimeoutError(
                "La operación fiscal perdió ownership antes de publicar su resultado."
            )
        await self.db.commit()
        await self.db.refresh(operacion)
        return operacion

    async def guardar_resultado_post_arca_incierto(
        self,
        operacion: OperacionIdempotente,
        *,
        response_json: Any,
    ) -> OperacionIdempotente:
        """Publica reconciliación post-ARCA sin sobrescribir un terminal."""
        identidad = sa_inspect(operacion).identity
        if not identidad:
            raise SQLAlchemyTimeoutError(
                "La operación fiscal no conserva una identidad durable."
            )
        publicada = await self.guardar_respuesta_operacion_cas(
            operacion_id=int(identidad[0]),
            response_json=response_json,
            estado="requiere_reconciliacion",
            estado_esperado={"en_proceso", "requiere_reconciliacion"},
            respuesta_esperada_nula=True,
            commit=False,
        )
        if not publicada:
            await self.db.rollback()
            raise SQLAlchemyTimeoutError(
                "La operación fiscal perdió ownership antes del cierre post-ARCA."
            )
        await self.db.commit()
        await self.db.refresh(operacion)
        return operacion

    async def marcar_operacion_en_proceso(
        self,
        operacion: OperacionIdempotente,
    ) -> tuple[OperacionIdempotente, bool]:
        """Toma atómicamente una operación pausada por confirmación adicional."""
        result = await self.db.execute(
            update(OperacionIdempotente)
            .where(
                OperacionIdempotente.id == operacion.id,
                OperacionIdempotente.estado == "requiere_confirmacion_duplicado",
            )
            .values(
                estado="en_proceso",
                response_json=null(),
            )
        )
        await self.db.commit()
        await self.db.refresh(operacion)
        return operacion, result.rowcount == 1

    async def marcar_operacion_interrumpida_pre_arca(
        self,
        operacion_id: int,
        *,
        commit: bool = True,
    ) -> bool:
        """Marca una operación reanudable solo si nunca creó un intento fiscal."""
        sin_intentos = ~exists(
            select(IntentoEmisionFiscal.id).where(
                IntentoEmisionFiscal.operacion_id == operacion_id
            )
        )
        result = await self.db.execute(
            update(OperacionIdempotente)
            .where(
                OperacionIdempotente.id == operacion_id,
                OperacionIdempotente.estado == "en_proceso",
                OperacionIdempotente.response_json.is_(None),
                sin_intentos,
            )
            .values(estado="interrumpida_pre_arca")
        )
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
        return result.rowcount == 1

    async def recuperar_creacion_ambigua_pre_arca(
        self,
        *,
        empresa_id: int,
        idempotency_key: str | None,
        payload_hash: str,
        tipo_operacion: str,
        lote_id: int | None,
        contextos_rece: list[ContextoElegibilidadRece],
    ) -> bool:
        """Confirma payload y snapshots antes de abrir un replay ambiguo."""
        from app.services.elegibilidad_rece_service import ElegibilidadReceService

        key = self.validar_idempotency_key(idempotency_key)
        sin_intentos = ~exists(
            select(IntentoEmisionFiscal.id).where(
                IntentoEmisionFiscal.operacion_id == OperacionIdempotente.id
            )
        )
        identidad = (
            OperacionIdempotente.empresa_id == empresa_id,
            OperacionIdempotente.idempotency_key == key,
            OperacionIdempotente.payload_hash == payload_hash,
            OperacionIdempotente.tipo_operacion == tipo_operacion,
            OperacionIdempotente.lote_id == lote_id,
            OperacionIdempotente.response_json.is_(None),
            OperacionIdempotente.rece_snapshot_hash.is_not(None),
            sin_intentos,
        )

        await self.db.rollback()
        try:
            await self.db.execute(
                update(OperacionIdempotente)
                .where(
                    *identidad,
                    OperacionIdempotente.estado == "en_proceso",
                )
                .values(estado="interrumpida_pre_arca")
            )
            await self.db.commit()
        except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
            await self.db.rollback()

        result = await self.db.execute(
            select(OperacionIdempotente).where(
                *identidad,
                OperacionIdempotente.estado == "interrumpida_pre_arca",
            )
        )
        operacion = result.scalar_one_or_none()
        if operacion is None:
            return False
        await ElegibilidadReceService(self.db).validar_operacion_para_continuar(
            operacion_id=operacion.id,
            empresa_id=empresa_id,
            contextos_esperados=contextos_rece,
        )
        return True

    async def reclamar_operacion_interrumpida_pre_arca(
        self,
        operacion: OperacionIdempotente,
    ) -> tuple[OperacionIdempotente, bool]:
        """Reclama por CAS una operación interrumpida para un único replay."""
        result = await self.db.execute(
            update(OperacionIdempotente)
            .where(
                OperacionIdempotente.id == operacion.id,
                OperacionIdempotente.estado == "interrumpida_pre_arca",
                OperacionIdempotente.response_json.is_(None),
            )
            .values(estado="en_proceso")
        )
        await self.db.commit()
        await self.db.refresh(operacion)
        return operacion, result.rowcount == 1

    @staticmethod
    def requiere_confirmacion_duplicado(response_json: Any) -> bool:
        """Indica si una respuesta guardada solo pide confirmar duplicado."""
        if not isinstance(response_json, dict):
            return False
        categoria = response_json.get("categoria_error")
        if categoria in {"duplicado_logico", "duplicado_logico_lote"}:
            return True
        detail = response_json.get("detail")
        return isinstance(detail, dict) and detail.get("categoria_error") in {
            "duplicado_logico",
            "duplicado_logico_lote",
        }

    async def crear_intento_emision(
        self,
        *,
        request: EmitirComprobanteRequest,
        punto_venta: PuntoVenta,
        numero_planificado: int,
        total: Decimal,
        operacion_id: int,
        usuario_id: int | None,
        lote_id: int | None,
        grupo_id: int | None,
        contexto_rece: ContextoElegibilidadRece,
        guarda_rece_id: int,
        commit: bool = True,
    ) -> IntentoEmisionFiscal:
        """Reserva durablemente el comprobante planificado antes de ARCA."""
        if (
            operacion_id <= 0
            or guarda_rece_id <= 0
            or contexto_rece.empresa_id != request.empresa_id
            or contexto_rece.punto_venta_id != punto_venta.id
            or contexto_rece.punto_venta_numero != punto_venta.numero
        ):
            raise IdempotenciaFiscalError(
                409,
                {
                    "mensaje": "El intento fiscal no coincide con su snapshot RECE.",
                    "categoria_error": "elegibilidad_rece_no_verificada",
                },
            )
        payload = request.model_dump(mode="json")
        payload_hash = self.calcular_payload_hash(
            self.payload_sin_confirmacion_duplicado(payload)
        )
        huella = self.calcular_huella_logica(
            request=request,
            punto_venta_numero=punto_venta.numero,
            total=total,
        )
        intento = IntentoEmisionFiscal(
            operacion_id=operacion_id,
            empresa_id=request.empresa_id,
            usuario_id=usuario_id,
            lote_id=lote_id,
            grupo_id=grupo_id,
            punto_venta_id=punto_venta.id,
            punto_venta_numero=punto_venta.numero,
            tipo_comprobante=request.tipo_comprobante,
            numero_planificado=numero_planificado,
            fecha_emision=request.fecha_emision,
            total=total,
            receptor_tipo_documento=request.tipo_documento,
            receptor_numero_documento=clean_cuit(request.numero_documento),
            receptor_razon_social=request.razon_social.strip(),
            payload_hash=payload_hash,
            huella_logica=huella,
            estado="en_proceso",
            ambiente=contexto_rece.ambiente,
            punto_venta_elegibilidad_revision_id=(
                contexto_rece.elegibilidad_revision_id
            ),
            punto_venta_revision_fiscal=(contexto_rece.punto_venta_revision_fiscal),
            guarda_rece_id=guarda_rece_id,
        )
        self.db.add(intento)
        if commit:
            await self.db.commit()
            await self.db.refresh(intento)
        else:
            await self.db.flush()
        return intento

    async def actualizar_intento_desde_respuesta(
        self,
        intento: IntentoEmisionFiscal | None,
        response: EmitirComprobanteResponse,
        *,
        commit: bool = True,
    ) -> None:
        """Actualiza un intento fiscal con el resultado conocido."""
        if intento is None:
            return

        intento.cae = response.cae
        intento.cae_vencimiento = response.cae_vencimiento
        intento.categoria_error = response.categoria_error
        intento.mensaje = response.mensaje
        if response.exito:
            intento.estado = "autorizado"
            intento.comprobante_id = response.comprobante_id
        elif response.requiere_reconciliacion:
            intento.estado = "requiere_reconciliacion"
        elif response.categoria_error == "arca_no_aprobado":
            intento.estado = "rechazado_arca"
        else:
            intento.estado = "fallido_verificado"

        self.db.add(intento)
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()

    async def existe_intento_bloqueante(
        self,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
    ) -> IntentoEmisionFiscal | None:
        """Busca intentos activos que bloquean nueva numeración."""
        result = await self.db.execute(
            select(IntentoEmisionFiscal)
            .where(
                IntentoEmisionFiscal.empresa_id == empresa_id,
                IntentoEmisionFiscal.punto_venta_id == punto_venta_id,
                IntentoEmisionFiscal.tipo_comprobante == tipo_comprobante,
                IntentoEmisionFiscal.estado.in_(self.ESTADOS_INTENTO_BLOQUEANTES),
            )
            .order_by(IntentoEmisionFiscal.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def buscar_duplicado_logico(
        self,
        *,
        request: EmitirComprobanteRequest,
        punto_venta: PuntoVenta,
        total: Decimal,
    ) -> Comprobante | None:
        """Busca un comprobante local probablemente duplicado."""
        receptor_doc = clean_cuit(request.numero_documento)
        result = await self.db.execute(
            select(Comprobante)
            .options(
                selectinload(Comprobante.items),
                selectinload(Comprobante.punto_venta),
            )
            .where(
                Comprobante.empresa_id == request.empresa_id,
                Comprobante.punto_venta_id == punto_venta.id,
                Comprobante.tipo_comprobante == request.tipo_comprobante,
                Comprobante.fecha_emision == request.fecha_emision,
                Comprobante.total == total,
                Comprobante.receptor_numero_documento == receptor_doc,
                Comprobante.estado == "autorizado",
            )
        )
        huella_request = self.calcular_huella_logica(
            request=request,
            punto_venta_numero=punto_venta.numero,
            total=total,
        )
        comprobantes = result.scalars().all()
        huellas_intentos = await self._huellas_autorizadas_por_comprobante(
            [comprobante.id for comprobante in comprobantes]
        )
        for comprobante in comprobantes:
            huella_comprobante = huellas_intentos.get(comprobante.id)
            if huella_comprobante is None:
                huella_comprobante = self.calcular_huella_logica_comprobante(
                    comprobante
                )
            if huella_comprobante == huella_request:
                return comprobante
        return None

    async def _huellas_autorizadas_por_comprobante(
        self, comprobante_ids: list[int]
    ) -> dict[int, str]:
        """Obtiene snapshots lógicos autorizados por comprobante persistido."""
        if not comprobante_ids:
            return {}
        result = await self.db.execute(
            select(
                IntentoEmisionFiscal.comprobante_id,
                IntentoEmisionFiscal.huella_logica,
            )
            .where(
                IntentoEmisionFiscal.comprobante_id.in_(comprobante_ids),
                IntentoEmisionFiscal.estado == "autorizado",
                IntentoEmisionFiscal.huella_logica.is_not(None),
            )
            .order_by(IntentoEmisionFiscal.created_at.desc())
        )
        huellas: dict[int, str] = {}
        for comprobante_id, huella_logica in result.all():
            if comprobante_id is not None and comprobante_id not in huellas:
                huellas[comprobante_id] = huella_logica
        return huellas

    @classmethod
    def calcular_huella_logica(
        cls,
        *,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        total: Decimal,
    ) -> str:
        """Calcula la huella lógica fiscal de un request de emisión."""
        payload = {
            "empresa_id": request.empresa_id,
            "tipo_comprobante": request.tipo_comprobante,
            "punto_venta_numero": punto_venta_numero,
            "fecha_emision": request.fecha_emision.isoformat(),
            "receptor": {
                "tipo_documento": request.tipo_documento,
                "numero_documento": clean_cuit(request.numero_documento),
            },
            "total": cls._money(total),
            "items": [
                {
                    "codigo": (item.codigo or "").strip(),
                    "descripcion": item.descripcion.strip(),
                    "cantidad": cls._decimal_str(item.cantidad),
                    "precio_unitario": cls._money(item.precio_unitario),
                    "descuento_porcentaje": cls._decimal_str(item.descuento_porcentaje),
                    "iva_porcentaje": cls._decimal_str(item.iva_porcentaje),
                    "orden": item.orden,
                }
                for item in sorted(request.items, key=lambda item: item.orden)
            ],
            "comprobantes_asociados": [
                {
                    "tipo_comprobante": asociado.tipo_comprobante,
                    "punto_venta": asociado.punto_venta,
                    "numero": asociado.numero,
                    "fecha": asociado.fecha.isoformat()
                    if isinstance(asociado.fecha, date)
                    else None,
                    "cuit": clean_cuit(asociado.cuit or ""),
                }
                for asociado in request.comprobantes_asociados
            ],
        }
        return cls.calcular_payload_hash(payload)

    @classmethod
    def calcular_huella_logica_comprobante(cls, comprobante: Comprobante) -> str:
        """Calcula la huella lógica desde un comprobante local guardado."""
        payload = {
            "empresa_id": comprobante.empresa_id,
            "tipo_comprobante": comprobante.tipo_comprobante,
            "punto_venta_numero": comprobante.punto_venta.numero,
            "fecha_emision": comprobante.fecha_emision.isoformat(),
            "receptor": {
                "tipo_documento": comprobante.receptor_tipo_documento,
                "numero_documento": clean_cuit(
                    comprobante.receptor_numero_documento or ""
                ),
            },
            "total": cls._money(comprobante.total),
            "items": [
                {
                    "codigo": (item.codigo or "").strip(),
                    "descripcion": item.descripcion.strip(),
                    "cantidad": cls._decimal_str(item.cantidad),
                    "precio_unitario": cls._money(item.precio_unitario),
                    "descuento_porcentaje": cls._decimal_str(item.descuento_porcentaje),
                    "iva_porcentaje": cls._decimal_str(item.iva_porcentaje),
                    "orden": item.orden,
                }
                for item in sorted(comprobante.items, key=lambda item: item.orden)
            ],
            "comprobantes_asociados": [],
        }
        return cls.calcular_payload_hash(payload)

    async def _obtener_operacion(
        self,
        empresa_id: int,
        idempotency_key: str,
    ) -> OperacionIdempotente | None:
        """Busca una operación por emisor y clave."""
        result = await self.db.execute(
            select(OperacionIdempotente).where(
                OperacionIdempotente.empresa_id == empresa_id,
                OperacionIdempotente.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _validar_payload_operacion(
        operacion: OperacionIdempotente,
        payload_hash: str,
    ) -> None:
        """Conserva el conflicto estable cuando una clave cambia de payload."""
        if operacion.payload_hash == payload_hash:
            return
        raise IdempotenciaFiscalError(
            409,
            {
                "mensaje": "La clave de idempotencia ya fue usada con otros datos.",
                "errores": [
                    "Generá una nueva confirmación fiscal para emitir datos distintos."
                ],
            },
        )

    @staticmethod
    def _normalizar_para_hash(value: Any) -> Any:
        """Convierte objetos comunes a una representación JSON estable."""
        return jsonable_encoder(value)

    @staticmethod
    def _decimal_str(value: Any) -> str:
        """Serializa decimales sin notación flotante."""
        decimal_value = Decimal(str(value))
        return format(decimal_value.normalize(), "f")

    @classmethod
    def _money(cls, value: Any) -> str:
        """Serializa un importe a centavos."""
        return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")
