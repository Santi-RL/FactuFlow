"""Servicios de idempotencia y deduplicación fiscal."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.arca.utils import clean_cuit
from app.models.comprobante import Comprobante
from app.models.idempotencia_fiscal import (
    IntentoEmisionFiscal,
    OperacionIdempotente,
)
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest, EmitirComprobanteResponse


class IdempotenciaFiscalError(Exception):
    """Error funcional del control de idempotencia fiscal."""

    def __init__(self, status_code: int, detail: Any) -> None:
        """Inicializa el error con estado HTTP sugerido y detalle seguro."""
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


class IdempotenciaFiscalService:
    """Coordina operaciones idempotentes e intentos fiscales durables."""

    ESTADOS_INTENTO_ACTIVOS = {
        "en_proceso",
        "autorizado",
        "requiere_reconciliacion",
    }
    ESTADOS_INTENTO_BLOQUEANTES = {"en_proceso", "requiere_reconciliacion"}

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el servicio con una sesión async."""
        self.db = db

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
    ) -> tuple[OperacionIdempotente, bool]:
        """Obtiene o crea una operación idempotente durable."""
        key = self.validar_idempotency_key(idempotency_key)
        operacion = await self._obtener_operacion(empresa_id, key)
        if operacion is not None:
            if operacion.payload_hash != payload_hash:
                raise IdempotenciaFiscalError(
                    409,
                    {
                        "mensaje": "La clave de idempotencia ya fue usada con otros datos.",
                        "errores": [
                            "Generá una nueva confirmación fiscal para emitir datos distintos."
                        ],
                    },
                )
            return operacion, False

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
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            operacion = await self._obtener_operacion(empresa_id, key)
            if operacion is None:
                raise
            if operacion.payload_hash != payload_hash:
                raise IdempotenciaFiscalError(
                    409,
                    {
                        "mensaje": "La clave de idempotencia ya fue usada con otros datos.",
                        "errores": [
                            "Generá una nueva confirmación fiscal para emitir datos distintos."
                        ],
                    },
                )
            return operacion, False

        await self.db.refresh(operacion)
        return operacion, True

    async def guardar_respuesta_operacion(
        self,
        operacion: OperacionIdempotente,
        *,
        response_json: Any,
        estado: str,
    ) -> OperacionIdempotente:
        """Persiste la respuesta observable de una operación fiscal."""
        operacion.response_json = jsonable_encoder(response_json)
        operacion.estado = estado
        self.db.add(operacion)
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
                response_json=None,
            )
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
        operacion_id: int | None,
        usuario_id: int | None,
        lote_id: int | None,
        grupo_id: int | None,
    ) -> IntentoEmisionFiscal:
        """Reserva durablemente el comprobante planificado antes de ARCA."""
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
        )
        self.db.add(intento)
        await self.db.commit()
        await self.db.refresh(intento)
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
        for comprobante in result.scalars().all():
            if self.calcular_huella_logica_comprobante(comprobante) == huella_request:
                return comprobante
        return None

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
