"""Autoridad común y fail-closed de elegibilidad RECE."""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import threading
import weakref
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager, nullcontext
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.elegibilidad_rece import (
    FASES_GUARDA_RECE_ACTIVAS,
    OperacionIdempotenteElegibilidadRece,
    PuntoVentaElegibilidadReceActual,
    PuntoVentaElegibilidadReceRevision,
    PuntoVentaGuardaEmisionRece,
)
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.services.constancia_puntos_venta_service import (
    CLASIFICADOR_RECE_VERSION,
    es_senal_rece_exacta,
)
from app.services.contencion_fiscal_service import (
    CATEGORIA_BLOQUEO_PREAUTORIZACION,
    MENSAJE_BLOQUEO_PREAUTORIZACION,
    obtener_bloqueo_preautorizacion,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService


CATEGORIA_ELEGIBILIDAD_RECE = "elegibilidad_rece_no_verificada"
MENSAJE_ELEGIBILIDAD_RECE = (
    "El punto de venta no tiene una acreditación RECE válida para este ambiente."
)
DETALLE_ELEGIBILIDAD_RECE = (
    "Comprobá el estado del punto con ARCA y verificá que esté habilitado "
    "para usar en FactuFlow."
)
CLASIFICADOR_WSFE_VERSION = "wsfe_emision_tipo_cae_v1"
_ZONA_ARGENTINA = timezone(
    timedelta(hours=-3),
    name="America/Argentina/Buenos_Aires",
)
_PUNTO_LOCKS_GUARD = threading.Lock()
_PUNTO_LOCKS: weakref.WeakValueDictionary[
    tuple[int, int], asyncio.Lock
] = weakref.WeakValueDictionary()


def _obtener_lock_local_punto(empresa_id: int, punto_venta_id: int) -> asyncio.Lock:
    """Obtiene el lock en proceso que complementa SQLite en desarrollo/tests."""
    key = (empresa_id, punto_venta_id)
    with _PUNTO_LOCKS_GUARD:
        lock = _PUNTO_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _PUNTO_LOCKS[key] = lock
        return lock


class ElegibilidadReceError(Exception):
    """Error funcional seguro de elegibilidad o snapshot RECE."""

    def __init__(
        self,
        mensaje: str = MENSAJE_ELEGIBILIDAD_RECE,
        *,
        categoria: str = CATEGORIA_ELEGIBILIDAD_RECE,
        status_code: int = 409,
    ) -> None:
        """Inicializa un error público sin evidencia fiscal privada."""
        self.mensaje = mensaje
        self.categoria = categoria
        self.status_code = status_code
        super().__init__(mensaje)


@dataclass(frozen=True)
class ContextoElegibilidadRece:
    """Snapshot mínimo autorizado para una operación fiscal."""

    empresa_id: int
    punto_venta_id: int
    punto_venta_numero: int
    ambiente: str
    elegibilidad_revision_id: int
    punto_venta_revision_fiscal: int

    def material_digest(self) -> dict[str, int | str]:
        """Serializa el snapshot con tipos y claves canónicos."""
        return {
            "empresa_id": self.empresa_id,
            "punto_venta_id": self.punto_venta_id,
            "punto_venta_numero": self.punto_venta_numero,
            "ambiente": self.ambiente,
            "elegibilidad_revision_id": self.elegibilidad_revision_id,
            "punto_venta_revision_fiscal": self.punto_venta_revision_fiscal,
        }


@dataclass(frozen=True)
class AtestacionPuntoRece:
    """Entrada interna para atestiguar un punto desde una constancia completa."""

    punto_venta: PuntoVenta
    cambios: dict[str, object]
    sistema_constancia: str


@dataclass(frozen=True)
class EstadoElegibilidadReceVisible:
    """Estado público mínimo de la cabeza RECE para el ambiente actual."""

    ambiente: Literal["homologacion", "produccion"]
    estado: Literal["verificado_rece", "no_rece", "no_verificado"]
    estado_efectivo: Literal["verificado_rece", "no_rece", "no_verificado"]
    fuente: str | None
    revision_id: int | None
    revision: int | None
    punto_revision_fiscal: int | None
    verificado_en: datetime | None
    vigente_hasta: date | None
    motivo: str | None


class ElegibilidadReceService:
    """Resuelve heads, snapshots y guardas RECE sin consultar ARCA."""

    DIGEST_VERSION = 1
    CLASIFICADOR_VERSION = CLASIFICADOR_RECE_VERSION
    COMPROBACION_ARCA_DIAS = 90
    CAMPOS_DESCRIPTIVOS = frozenset(
        {
            "nombre",
            "domicilio",
            "domicilio_fuente",
            "nombre_fantasia",
            "nombre_fantasia_fuente",
        }
    )
    CAMPOS_SIN_REVISION = CAMPOS_DESCRIPTIVOS | frozenset(
        {"ultima_comprobacion_arca_en"}
    )
    CAMPOS_ATESTACION_CONSTANCIA = frozenset(
        {
            "nombre",
            "sistema",
            "domicilio",
            "nombre_fantasia",
            "es_webservice",
            "bloqueado",
            "fecha_baja",
            "fuente",
            "activo",
            "ultima_comprobacion_arca_en",
        }
    )

    def __init__(
        self,
        db: AsyncSession,
        *,
        hoy: date | Callable[[], date] | None = None,
        ahora: datetime | Callable[[], datetime] | None = None,
    ) -> None:
        """Inicializa el servicio con relojes fiscal y técnico inyectables."""
        self.db = db
        if hoy is None:
            self._obtener_hoy = lambda: datetime.now(_ZONA_ARGENTINA).date()
        elif callable(hoy):
            self._obtener_hoy = hoy
        else:
            self._obtener_hoy = lambda hoy_fijo=hoy: hoy_fijo
        if ahora is None:
            self._obtener_ahora = datetime.utcnow
        elif callable(ahora):
            self._obtener_ahora = ahora
        else:
            self._obtener_ahora = lambda ahora_fijo=ahora: ahora_fijo

    def comprobacion_arca_desactualizada(self, punto_venta: PuntoVenta) -> bool:
        """Indica si corresponde refrescar la señal técnica antes de emitir."""
        comprobado_en = punto_venta.ultima_comprobacion_arca_en
        if comprobado_en is None:
            return True
        limite = self._obtener_ahora() - timedelta(days=self.COMPROBACION_ARCA_DIAS)
        return comprobado_en <= limite

    @asynccontextmanager
    async def bloqueo_local_punto(
        self,
        *,
        empresa_id: int,
        punto_venta_id: int,
    ) -> AsyncIterator[None]:
        """Serializa el borde crítico en un único proceso SQLite."""
        async with _obtener_lock_local_punto(empresa_id, punto_venta_id):
            yield

    @asynccontextmanager
    async def bloquear_frontera_atestacion_productiva(
        self,
        *,
        empresa_id: int,
        empresa_cuit: str,
        actor_usuario_id: int,
    ) -> AsyncIterator[None]:
        """Retiene Usuario y Empresa antes de crear dependencias de la constancia."""
        await self._adquirir_frontera_atestacion_productiva(
            empresa_id=empresa_id,
            empresa_cuit=empresa_cuit,
            actor_usuario_id=actor_usuario_id,
        )
        yield

    async def crear_contextos_iniciales_no_verificados(
        self,
        punto_venta: PuntoVenta,
        *,
        creado_por_usuario_id: int | None = None,
        fuente: str = "alta_manual",
    ) -> None:
        """Crea heads cerradas para un punto nuevo, sin productor positivo."""
        if fuente not in {"alta_manual", "sincronizacion_wsfe"}:
            raise ElegibilidadReceError(
                "La procedencia del contexto RECE inicial no es válida."
            )
        if punto_venta.empresa_id is None:
            raise ElegibilidadReceError(
                "No se pudo identificar el punto de venta para crear su contexto RECE."
            )
        await self.db.flush()
        if punto_venta.id is None:
            raise ElegibilidadReceError(
                "No se pudo identificar el punto de venta para crear su contexto RECE."
            )
        result = await self.db.execute(
            select(PuntoVentaElegibilidadReceActual).where(
                PuntoVentaElegibilidadReceActual.punto_venta_id == punto_venta.id
            )
        )
        existentes = list(result.scalars().all())
        if len(existentes) == 2 and {
            (head.empresa_id, head.ambiente) for head in existentes
        } == {
            (punto_venta.empresa_id, "homologacion"),
            (punto_venta.empresa_id, "produccion"),
        }:
            return
        if existentes:
            raise ElegibilidadReceError(
                "El punto de venta tiene un contexto RECE inicial incompleto."
            )

        revision_fiscal = int(punto_venta.revision_fiscal or 1)
        ahora = datetime.utcnow()
        for ambiente in ("homologacion", "produccion"):
            revision = PuntoVentaElegibilidadReceRevision(
                empresa_id=punto_venta.empresa_id,
                punto_venta_id=punto_venta.id,
                ambiente=ambiente,
                revision=1,
                estado="no_verificado",
                fuente=fuente,
                evidencia_tipo="sin_evidencia",
                punto_revision_fiscal=revision_fiscal,
                observado_en=ahora,
                creado_por_usuario_id=creado_por_usuario_id,
                actor_usuario_id_snapshot=creado_por_usuario_id,
                created_at=ahora,
            )
            self.db.add(revision)
            await self.db.flush()
            self.db.add(
                PuntoVentaElegibilidadReceActual(
                    empresa_id=punto_venta.empresa_id,
                    punto_venta_id=punto_venta.id,
                    ambiente=ambiente,
                    revision_actual_id=revision.id,
                    created_at=ahora,
                    updated_at=ahora,
                )
            )
        await self.db.flush()

    async def aplicar_cambios_punto(
        self,
        punto_venta: PuntoVenta,
        cambios: dict[str, object],
        *,
        fuente: str,
        actor_usuario_id: int | None = None,
        forzar_revision: bool = False,
        commit: bool = True,
        _lock_adquirido: bool = False,
    ) -> bool:
        """Aplica una mutación con CAS, locks y rechazo ante guarda activa."""
        if not commit and not _lock_adquirido:
            raise RuntimeError(
                "Una mutación RECE sin commit requiere conservar el lock local."
            )
        if fuente not in {"edicion", "sincronizacion_wsfe"}:
            raise ElegibilidadReceError(
                "La procedencia del cambio fiscal del punto no es válida."
            )
        if punto_venta.id is None or punto_venta.empresa_id is None:
            raise ElegibilidadReceError(
                "No se pudo identificar el punto de venta que se desea modificar."
            )

        cambios_reales = {
            field: value
            for field, value in cambios.items()
            if hasattr(punto_venta, field) and getattr(punto_venta, field) != value
        }
        revision_requerida = forzar_revision or bool(
            set(cambios_reales) - self.CAMPOS_SIN_REVISION
        )
        if not revision_requerida:
            for field, value in cambios_reales.items():
                setattr(punto_venta, field, value)
            if commit:
                await self.db.commit()
                await self.db.refresh(punto_venta)
            else:
                await self.db.flush()
            return False

        revision_anterior = int(punto_venta.revision_fiscal)
        empresa_id = int(punto_venta.empresa_id)
        punto_venta_id = int(punto_venta.id)
        lock_context = (
            nullcontext()
            if _lock_adquirido
            else self.bloqueo_local_punto(
                empresa_id=empresa_id,
                punto_venta_id=punto_venta_id,
            )
        )
        async with lock_context:
            with self.db.no_autoflush:
                locked_result = await self.db.execute(
                    select(PuntoVenta)
                    .where(
                        PuntoVenta.id == punto_venta_id,
                        PuntoVenta.empresa_id == empresa_id,
                    )
                    .with_for_update()
                )
            locked_point = locked_result.scalar_one_or_none()
            if (
                locked_point is None
                or int(locked_point.revision_fiscal) != revision_anterior
            ):
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El punto de venta cambió de forma concurrente; recargá y reintentá.",
                    categoria="conflicto_revision_fiscal",
                )

            heads_result = await self.db.execute(
                select(
                    PuntoVentaElegibilidadReceActual,
                    PuntoVentaElegibilidadReceRevision,
                )
                .join(
                    PuntoVentaElegibilidadReceRevision,
                    PuntoVentaElegibilidadReceRevision.id
                    == PuntoVentaElegibilidadReceActual.revision_actual_id,
                )
                .where(
                    PuntoVentaElegibilidadReceActual.empresa_id == empresa_id,
                    PuntoVentaElegibilidadReceActual.punto_venta_id == punto_venta_id,
                )
                .order_by(PuntoVentaElegibilidadReceActual.ambiente)
                .with_for_update()
            )
            heads = list(heads_result.all())
            active_guard = await self.db.execute(
                select(PuntoVentaGuardaEmisionRece.id)
                .where(
                    PuntoVentaGuardaEmisionRece.empresa_id == empresa_id,
                    PuntoVentaGuardaEmisionRece.punto_venta_id == punto_venta_id,
                    PuntoVentaGuardaEmisionRece.fase.in_(FASES_GUARDA_RECE_ACTIVAS),
                )
                .with_for_update()
            )
            if active_guard.first() is not None:
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El punto de venta tiene una solicitud fiscal activa o incierta.",
                    categoria="conflicto_guarda_rece_activa",
                )

            revision_nueva = revision_anterior + 1
            values = {**cambios_reales, "revision_fiscal": revision_nueva}
            result = await self.db.execute(
                update(PuntoVenta)
                .where(
                    PuntoVenta.id == punto_venta_id,
                    PuntoVenta.empresa_id == empresa_id,
                    PuntoVenta.revision_fiscal == revision_anterior,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El punto de venta cambió de forma concurrente; recargá y reintentá.",
                    categoria="conflicto_revision_fiscal",
                )
            await self.db.refresh(punto_venta)

            if not heads:
                await self.crear_contextos_iniciales_no_verificados(
                    punto_venta,
                    creado_por_usuario_id=actor_usuario_id,
                )
                if commit:
                    await self.db.commit()
                    await self.db.refresh(punto_venta)
                return True
            if len(heads) != 2:
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El punto de venta tiene un contexto RECE incompleto."
                )

            ahora = self._obtener_ahora()
            for head, revision_actual in heads:
                preservar_acreditacion = (
                    revision_actual.estado == "verificado_rece"
                    and set(cambios_reales)
                    <= self.CAMPOS_DESCRIPTIVOS | {"usar_en_factuflow"}
                )
                revision = PuntoVentaElegibilidadReceRevision(
                    empresa_id=empresa_id,
                    punto_venta_id=punto_venta_id,
                    ambiente=head.ambiente,
                    revision=revision_actual.revision + 1,
                    estado=(
                        "verificado_rece" if preservar_acreditacion else "no_verificado"
                    ),
                    fuente=(
                        revision_actual.fuente if preservar_acreditacion else fuente
                    ),
                    evidencia_tipo=(
                        revision_actual.evidencia_tipo
                        if preservar_acreditacion
                        else "sin_evidencia"
                    ),
                    evidencia_sha256=(
                        revision_actual.evidencia_sha256
                        if preservar_acreditacion
                        else None
                    ),
                    clasificador_version=(
                        revision_actual.clasificador_version
                        if preservar_acreditacion
                        else None
                    ),
                    empresa_cuit_snapshot=(
                        revision_actual.empresa_cuit_snapshot
                        if preservar_acreditacion
                        else None
                    ),
                    punto_venta_numero_snapshot=(
                        int(punto_venta.numero) if preservar_acreditacion else None
                    ),
                    punto_revision_fiscal=revision_nueva,
                    documento_emitido_en=(
                        revision_actual.documento_emitido_en
                        if preservar_acreditacion
                        else None
                    ),
                    vigente_hasta=None,
                    observado_en=ahora,
                    verificado_en=(
                        revision_actual.verificado_en
                        if preservar_acreditacion
                        else None
                    ),
                    creado_por_usuario_id=(
                        revision_actual.creado_por_usuario_id
                        if preservar_acreditacion
                        else actor_usuario_id
                    ),
                    actor_usuario_id_snapshot=(
                        revision_actual.actor_usuario_id_snapshot
                        if preservar_acreditacion
                        else actor_usuario_id
                    ),
                    created_at=ahora,
                )
                self.db.add(revision)
                await self.db.flush()
                moved = await self.db.execute(
                    update(PuntoVentaElegibilidadReceActual)
                    .where(
                        PuntoVentaElegibilidadReceActual.id == head.id,
                        PuntoVentaElegibilidadReceActual.revision_actual_id
                        == revision_actual.id,
                    )
                    .values(revision_actual_id=revision.id, updated_at=ahora)
                )
                if moved.rowcount != 1:
                    await self.db.rollback()
                    raise ElegibilidadReceError(
                        "La elegibilidad RECE cambió de forma concurrente.",
                        categoria="conflicto_revision_fiscal",
                    )
            if commit:
                await self.db.commit()
                await self.db.refresh(punto_venta)
            else:
                await self.db.flush()
            return True

    async def aplicar_snapshot_wsfe_atomico(
        self,
        acciones: list[tuple[PuntoVenta, dict[str, object], bool, bool]],
        *,
        empresa_id: int,
        empresa_cuit: str,
        ambiente: Literal["homologacion", "produccion"],
        actor_usuario_id: int,
    ) -> None:
        """Aplica un snapshot WSFE completo y mueve sus heads en un commit."""
        if ambiente not in {"homologacion", "produccion"}:
            raise ElegibilidadReceError("El ambiente ARCA configurado no es válido.")
        if len(empresa_cuit) != 11 or actor_usuario_id <= 0:
            raise ElegibilidadReceError(
                "No se pudo acreditar la identidad del emisor o del usuario."
            )
        if not acciones:
            raise ElegibilidadReceError(
                "ARCA no informó puntos de venta; no se aplicaron cambios.",
                categoria="comprobacion_arca_no_disponible",
                status_code=503,
            )
        ids = [
            int(punto.id or 0) for punto, _cambios, _compatible, _presente in acciones
        ]
        if (
            any(punto_id <= 0 for punto_id in ids)
            or len(set(ids)) != len(ids)
            or any(int(punto.empresa_id or 0) != empresa_id for punto, *_ in acciones)
        ):
            raise ElegibilidadReceError(
                "La comprobación ARCA contiene puntos locales inconsistentes."
            )

        ordenadas = sorted(acciones, key=lambda item: int(item[0].id))
        try:
            async with AsyncExitStack() as locks:
                for punto, _cambios, _compatible, _presente in ordenadas:
                    await locks.enter_async_context(
                        self.bloqueo_local_punto(
                            empresa_id=empresa_id,
                            punto_venta_id=int(punto.id),
                        )
                    )
                for punto, cambios, _compatible, _presente in ordenadas:
                    await self._prevalidar_cambio_punto(
                        punto,
                        cambios,
                        forzar_revision=False,
                    )
                for punto, cambios, compatible, presente in ordenadas:
                    await self.aplicar_cambios_punto(
                        punto,
                        cambios,
                        fuente="sincronizacion_wsfe",
                        actor_usuario_id=actor_usuario_id,
                        commit=False,
                        _lock_adquirido=True,
                    )
                    await self._registrar_revision_wsfe_bajo_lock(
                        punto,
                        ambiente=ambiente,
                        empresa_cuit=empresa_cuit,
                        actor_usuario_id=actor_usuario_id,
                        compatible=compatible,
                        presente=presente,
                    )
                await self.db.commit()
                for punto, _cambios, _compatible, _presente in ordenadas:
                    await self.db.refresh(punto)
        except Exception:
            await self.db.rollback()
            raise

    async def _registrar_revision_wsfe_bajo_lock(
        self,
        punto: PuntoVenta,
        *,
        ambiente: Literal["homologacion", "produccion"],
        empresa_cuit: str,
        actor_usuario_id: int,
        compatible: bool,
        presente: bool,
    ) -> None:
        """Registra la observación WSFE con el lock local ya retenido."""
        row = (
            await self.db.execute(
                select(
                    PuntoVentaElegibilidadReceActual,
                    PuntoVentaElegibilidadReceRevision,
                )
                .join(
                    PuntoVentaElegibilidadReceRevision,
                    PuntoVentaElegibilidadReceRevision.id
                    == PuntoVentaElegibilidadReceActual.revision_actual_id,
                )
                .where(
                    PuntoVentaElegibilidadReceActual.empresa_id == punto.empresa_id,
                    PuntoVentaElegibilidadReceActual.punto_venta_id == punto.id,
                    PuntoVentaElegibilidadReceActual.ambiente == ambiente,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if row is None:
            raise ElegibilidadReceError(
                "El punto de venta tiene un contexto RECE incompleto."
            )
        head, revision_actual = row
        ahora = self._obtener_ahora()
        verificado = bool(presente and compatible)
        estado = (
            "verificado_rece"
            if verificado
            else ("no_rece" if presente else "no_verificado")
        )
        revision = PuntoVentaElegibilidadReceRevision(
            empresa_id=int(punto.empresa_id),
            punto_venta_id=int(punto.id),
            ambiente=ambiente,
            revision=int(revision_actual.revision) + 1,
            estado=estado,
            fuente="sincronizacion_wsfe",
            evidencia_tipo=(
                "wsfe_param_get_ptos_venta_v1" if verificado else "sin_evidencia"
            ),
            evidencia_sha256=None,
            clasificador_version=(CLASIFICADOR_WSFE_VERSION if verificado else None),
            empresa_cuit_snapshot=(empresa_cuit if verificado else None),
            punto_venta_numero_snapshot=(int(punto.numero) if verificado else None),
            punto_revision_fiscal=int(punto.revision_fiscal),
            documento_emitido_en=None,
            vigente_hasta=None,
            observado_en=ahora,
            verificado_en=(ahora if verificado else None),
            creado_por_usuario_id=actor_usuario_id,
            actor_usuario_id_snapshot=(actor_usuario_id if verificado else None),
            created_at=ahora,
        )
        self.db.add(revision)
        await self.db.flush()
        moved = await self.db.execute(
            update(PuntoVentaElegibilidadReceActual)
            .where(
                PuntoVentaElegibilidadReceActual.id == head.id,
                PuntoVentaElegibilidadReceActual.revision_actual_id
                == revision_actual.id,
            )
            .values(revision_actual_id=revision.id, updated_at=ahora)
        )
        if moved.rowcount != 1:
            raise ElegibilidadReceError(
                "La elegibilidad RECE cambió de forma concurrente.",
                categoria="conflicto_revision_fiscal",
            )

    async def aplicar_cambios_puntos_atomicos(
        self,
        cambios_por_punto: list[tuple[PuntoVenta, dict[str, object]]],
        *,
        fuente: str,
        actor_usuario_id: int | None = None,
        forzar_revision: bool = False,
        forzar_revision_ids: set[int] | None = None,
    ) -> list[bool]:
        """Prevalida guardas en orden y commitea todo el conjunto una vez."""
        if not cambios_por_punto:
            return []
        if any(
            punto.id is None or punto.empresa_id is None
            for punto, _ in cambios_por_punto
        ):
            raise ElegibilidadReceError(
                "No se pudo identificar un punto de venta de la mutación."
            )
        if len({int(punto.id) for punto, _ in cambios_por_punto}) != len(
            cambios_por_punto
        ):
            raise ElegibilidadReceError(
                "La mutación fiscal contiene puntos de venta duplicados."
            )
        ids_puntos = {int(punto.id) for punto, _ in cambios_por_punto}
        ids_forzados = set(forzar_revision_ids or set())
        if ids_forzados - ids_puntos:
            raise ElegibilidadReceError(
                "La mutación fiscal intenta forzar un punto fuera del conjunto."
            )

        ordenados = sorted(cambios_por_punto, key=lambda item: int(item[0].id))
        try:
            async with AsyncExitStack() as locks:
                for punto, _ in ordenados:
                    await locks.enter_async_context(
                        self.bloqueo_local_punto(
                            empresa_id=int(punto.empresa_id),
                            punto_venta_id=int(punto.id),
                        )
                    )
                for punto, cambios in ordenados:
                    await self._prevalidar_cambio_punto(
                        punto,
                        cambios,
                        forzar_revision=(
                            forzar_revision or int(punto.id) in ids_forzados
                        ),
                    )
                resultados_ordenados = [
                    await self.aplicar_cambios_punto(
                        punto,
                        cambios,
                        fuente=fuente,
                        actor_usuario_id=actor_usuario_id,
                        forzar_revision=(
                            forzar_revision or int(punto.id) in ids_forzados
                        ),
                        commit=False,
                        _lock_adquirido=True,
                    )
                    for punto, cambios in ordenados
                ]
                await self.db.commit()
                for punto, _ in ordenados:
                    await self.db.refresh(punto)
        except Exception:
            await self.db.rollback()
            raise

        por_id = {
            int(punto.id): resultado
            for (punto, _), resultado in zip(
                ordenados,
                resultados_ordenados,
                strict=True,
            )
        }
        return [por_id[int(punto.id)] for punto, _ in cambios_por_punto]

    async def atestiguar_constancia_productiva(
        self,
        atestaciones: list[AtestacionPuntoRece],
        *,
        invalidaciones_ausentes: list[tuple[PuntoVenta, dict[str, object]]]
        | None = None,
        empresa_id: int,
        empresa_cuit: str,
        evidencia_sha256: str,
        documento_emitido_en: date,
        actor_usuario_id: int,
    ) -> dict[int, Literal["verificado_rece", "no_verificado"]]:
        """Atestigua una constancia productiva con un único commit ordenado."""
        invalidaciones = list(invalidaciones_ausentes or [])
        self._validar_atestacion_constancia(
            atestaciones,
            empresa_id=empresa_id,
            empresa_cuit=empresa_cuit,
            evidencia_sha256=evidencia_sha256,
            documento_emitido_en=documento_emitido_en,
            actor_usuario_id=actor_usuario_id,
        )
        self._validar_invalidaciones_ausentes(
            invalidaciones,
            atestaciones=atestaciones,
            empresa_id=empresa_id,
        )
        acciones = sorted(
            [
                (
                    item.punto_venta,
                    item.cambios,
                    es_senal_rece_exacta(item.sistema_constancia),
                    True,
                )
                for item in atestaciones
            ]
            + [(punto, cambios, False, False) for punto, cambios in invalidaciones],
            key=lambda item: int(item[0].id),
        )
        resultados: dict[int, Literal["verificado_rece", "no_verificado"]] = {}
        try:
            await self._adquirir_frontera_atestacion_productiva(
                empresa_id=empresa_id,
                empresa_cuit=empresa_cuit,
                actor_usuario_id=actor_usuario_id,
            )
            async with AsyncExitStack() as locks:
                for punto, _cambios, _senal, _presente in acciones:
                    await locks.enter_async_context(
                        self.bloqueo_local_punto(
                            empresa_id=empresa_id,
                            punto_venta_id=int(punto.id),
                        )
                    )
                for punto, cambios, _senal, _presente in acciones:
                    await self._prevalidar_cambio_punto(
                        punto,
                        cambios,
                        forzar_revision=True,
                    )
                for punto, cambios, senal_exacta, presente in acciones:
                    estado = await self._atestiguar_punto_bajo_lock(
                        punto,
                        cambios,
                        senal_rece_exacta=senal_exacta,
                        empresa_cuit=empresa_cuit,
                        evidencia_sha256=evidencia_sha256,
                        documento_emitido_en=documento_emitido_en,
                        actor_usuario_id=actor_usuario_id,
                    )
                    if presente:
                        resultados[int(punto.id)] = estado
                await self.db.commit()
                for punto, _cambios, _senal, _presente in acciones:
                    await self.db.refresh(punto)
        except Exception:
            await self.db.rollback()
            raise
        return resultados

    async def _adquirir_frontera_atestacion_productiva(
        self,
        *,
        empresa_id: int,
        empresa_cuit: str,
        actor_usuario_id: int,
    ) -> None:
        """Bloquea actor y emisor, en ese orden, sin flush de hijos pendientes."""
        with self.db.no_autoflush:
            await self._exigir_actor_admin(actor_usuario_id)
            await self._exigir_empresa_cuit_actual(
                empresa_id=empresa_id,
                empresa_cuit=empresa_cuit,
            )

    async def _exigir_actor_admin(self, actor_usuario_id: int) -> None:
        """Bloquea y revalida al administrador durante la atestación."""
        actor = (
            await self.db.execute(
                select(Usuario)
                .where(
                    Usuario.id == actor_usuario_id,
                    Usuario.activo.is_(True),
                    Usuario.es_admin.is_(True),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if actor is None:
            raise ElegibilidadReceError(
                "Solo un administrador activo puede acreditar elegibilidad RECE."
            )

    async def _exigir_empresa_cuit_actual(
        self,
        *,
        empresa_id: int,
        empresa_cuit: str,
    ) -> None:
        """Bloquea el emisor y rechaza una constancia con identidad obsoleta."""
        empresa = (
            await self.db.execute(
                select(Empresa)
                .where(Empresa.id == empresa_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if empresa is None or empresa.cuit != empresa_cuit:
            raise ElegibilidadReceError(
                "La identidad fiscal del emisor cambió durante la acreditación RECE."
            )

    def _validar_invalidaciones_ausentes(
        self,
        invalidaciones: list[tuple[PuntoVenta, dict[str, object]]],
        *,
        atestaciones: list[AtestacionPuntoRece],
        empresa_id: int,
    ) -> None:
        """Valida puntos ausentes que deben quedar inactivos en la misma carga."""
        ids_atestados = {int(item.punto_venta.id or 0) for item in atestaciones}
        ids_invalidos = [int(punto.id or 0) for punto, _ in invalidaciones]
        if (
            any(punto_id <= 0 for punto_id in ids_invalidos)
            or len(set(ids_invalidos)) != len(ids_invalidos)
            or bool(ids_atestados.intersection(ids_invalidos))
            or any(punto.empresa_id != empresa_id for punto, _ in invalidaciones)
            or any(cambios != {"activo": False} for _, cambios in invalidaciones)
        ):
            raise ElegibilidadReceError(
                "La invalidación de puntos ausentes no conserva una membresía segura."
            )

    def _validar_atestacion_constancia(
        self,
        atestaciones: list[AtestacionPuntoRece],
        *,
        empresa_id: int,
        empresa_cuit: str,
        evidencia_sha256: str,
        documento_emitido_en: date,
        actor_usuario_id: int,
    ) -> None:
        """Valida la membresía antes de tomar locks o escribir."""
        self.validar_documento_constancia_productiva(
            empresa_id=empresa_id,
            empresa_cuit=empresa_cuit,
            evidencia_sha256=evidencia_sha256,
            documento_emitido_en=documento_emitido_en,
            actor_usuario_id=actor_usuario_id,
        )
        if not atestaciones:
            raise ElegibilidadReceError(
                "La constancia no contiene puntos de venta para atestiguar."
            )
        if any(
            not isinstance(item.cambios, dict)
            or not isinstance(item.sistema_constancia, str)
            or item.cambios.get("sistema") != item.sistema_constancia
            or bool(set(item.cambios) - self.CAMPOS_ATESTACION_CONSTANCIA)
            for item in atestaciones
        ):
            raise ElegibilidadReceError(
                "La atestación contiene datos fuera del contrato de la constancia."
            )
        ids = [int(item.punto_venta.id or 0) for item in atestaciones]
        if any(punto_id <= 0 for punto_id in ids) or len(set(ids)) != len(ids):
            raise ElegibilidadReceError(
                "La constancia contiene puntos de venta duplicados o sin identidad durable."
            )
        if any(item.punto_venta.empresa_id != empresa_id for item in atestaciones):
            raise ElegibilidadReceError(
                "La constancia contiene un punto de venta de otro emisor."
            )

    def validar_documento_constancia_productiva(
        self,
        *,
        empresa_id: int,
        empresa_cuit: str,
        evidencia_sha256: str,
        documento_emitido_en: date,
        actor_usuario_id: int,
    ) -> None:
        """Valida autoridad, ambiente e integridad antes de cualquier consulta ARCA."""
        if settings.arca_env != "produccion":
            raise ElegibilidadReceError(
                "La acreditación RECE solo puede realizarse en un servidor configurado para producción."
            )
        if (
            not isinstance(actor_usuario_id, int)
            or isinstance(actor_usuario_id, bool)
            or actor_usuario_id <= 0
            or not isinstance(empresa_id, int)
            or isinstance(empresa_id, bool)
            or empresa_id <= 0
        ):
            raise ElegibilidadReceError(
                "No se pudo identificar al administrador o al emisor de la atestación."
            )
        if (
            not isinstance(empresa_cuit, str)
            or len(empresa_cuit) != 11
            or not empresa_cuit.isdigit()
        ):
            raise ElegibilidadReceError(
                "La constancia no conserva un CUIT válido del emisor."
            )
        try:
            hash_valido = len(evidencia_sha256) == 64 and int(evidencia_sha256, 16) >= 0
        except (TypeError, ValueError):
            hash_valido = False
        if not hash_valido:
            raise ElegibilidadReceError(
                "La evidencia de la constancia no conserva un hash válido."
            )
        if not isinstance(documento_emitido_en, date) or isinstance(
            documento_emitido_en,
            datetime,
        ):
            raise ElegibilidadReceError(
                "La constancia no conserva una fecha documental válida."
            )
        hoy = self._obtener_hoy()
        antiguedad = (hoy - documento_emitido_en).days
        if antiguedad < 0:
            raise ElegibilidadReceError(
                "La fecha documental de la constancia no puede ser futura."
            )

    async def _atestiguar_punto_bajo_lock(
        self,
        punto: PuntoVenta,
        cambios: dict[str, object],
        *,
        senal_rece_exacta: bool,
        empresa_cuit: str,
        evidencia_sha256: str,
        documento_emitido_en: date,
        actor_usuario_id: int,
    ) -> Literal["verificado_rece", "no_verificado"]:
        """Mueve ambas heads y la revisión fiscal con locks ya retenidos."""
        empresa_id = int(punto.empresa_id)
        punto_venta_id = int(punto.id)
        revision_anterior = int(punto.revision_fiscal)
        punto_locked = (
            await self.db.execute(
                select(PuntoVenta)
                .where(
                    PuntoVenta.id == punto_venta_id,
                    PuntoVenta.empresa_id == empresa_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if (
            punto_locked is None
            or int(punto_locked.revision_fiscal) != revision_anterior
        ):
            raise ElegibilidadReceError(
                "El punto de venta cambió de forma concurrente; recargá y reintentá.",
                categoria="conflicto_revision_fiscal",
            )
        heads = list(
            (
                await self.db.execute(
                    select(
                        PuntoVentaElegibilidadReceActual,
                        PuntoVentaElegibilidadReceRevision,
                    )
                    .join(
                        PuntoVentaElegibilidadReceRevision,
                        PuntoVentaElegibilidadReceRevision.id
                        == PuntoVentaElegibilidadReceActual.revision_actual_id,
                    )
                    .where(
                        PuntoVentaElegibilidadReceActual.empresa_id == empresa_id,
                        PuntoVentaElegibilidadReceActual.punto_venta_id
                        == punto_venta_id,
                    )
                    .order_by(PuntoVentaElegibilidadReceActual.ambiente)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        if len(heads) != 2 or {head.ambiente for head, _ in heads} != {
            "homologacion",
            "produccion",
        }:
            raise ElegibilidadReceError(
                "El punto de venta tiene un contexto RECE incompleto."
            )
        ultima_fecha_documental = await self.db.scalar(
            select(
                func.max(PuntoVentaElegibilidadReceRevision.documento_emitido_en)
            ).where(
                PuntoVentaElegibilidadReceRevision.empresa_id == empresa_id,
                PuntoVentaElegibilidadReceRevision.punto_venta_id == punto_venta_id,
                PuntoVentaElegibilidadReceRevision.ambiente == "produccion",
            )
        )
        if (
            ultima_fecha_documental is not None
            and documento_emitido_en < ultima_fecha_documental
        ):
            raise ElegibilidadReceError(
                "La constancia es anterior a una evidencia ya procesada para el punto de venta.",
                categoria="constancia_rece_obsoleta",
            )

        cambios_reales = {
            field: value
            for field, value in cambios.items()
            if hasattr(punto_locked, field) and getattr(punto_locked, field) != value
        }
        revision_nueva = revision_anterior + 1
        updated = await self.db.execute(
            update(PuntoVenta)
            .where(
                PuntoVenta.id == punto_venta_id,
                PuntoVenta.empresa_id == empresa_id,
                PuntoVenta.revision_fiscal == revision_anterior,
            )
            .values(**cambios_reales, revision_fiscal=revision_nueva)
        )
        if updated.rowcount != 1:
            raise ElegibilidadReceError(
                "El punto de venta cambió de forma concurrente; recargá y reintentá.",
                categoria="conflicto_revision_fiscal",
            )
        await self.db.refresh(punto)

        ahora = datetime.utcnow()
        estado_produccion: Literal["verificado_rece", "no_verificado"] = (
            "verificado_rece" if senal_rece_exacta else "no_verificado"
        )
        for head, revision_actual in heads:
            es_produccion = head.ambiente == "produccion"
            estado = estado_produccion if es_produccion else "no_verificado"
            revision = PuntoVentaElegibilidadReceRevision(
                empresa_id=empresa_id,
                punto_venta_id=punto_venta_id,
                ambiente=head.ambiente,
                revision=int(revision_actual.revision) + 1,
                estado=estado,
                fuente=("constancia_arca_atestada" if es_produccion else "edicion"),
                evidencia_tipo=(
                    "rece_aplicativo_web_services_v1"
                    if estado == "verificado_rece"
                    else "sin_evidencia"
                ),
                evidencia_sha256=evidencia_sha256 if es_produccion else None,
                clasificador_version=(
                    self.CLASIFICADOR_VERSION if es_produccion else None
                ),
                empresa_cuit_snapshot=empresa_cuit if es_produccion else None,
                punto_venta_numero_snapshot=(
                    int(punto.numero) if es_produccion else None
                ),
                punto_revision_fiscal=revision_nueva,
                documento_emitido_en=(documento_emitido_en if es_produccion else None),
                vigente_hasta=None,
                observado_en=ahora,
                verificado_en=(ahora if estado == "verificado_rece" else None),
                creado_por_usuario_id=actor_usuario_id,
                actor_usuario_id_snapshot=actor_usuario_id,
                created_at=ahora,
            )
            self.db.add(revision)
            await self.db.flush()
            moved = await self.db.execute(
                update(PuntoVentaElegibilidadReceActual)
                .where(
                    PuntoVentaElegibilidadReceActual.id == head.id,
                    PuntoVentaElegibilidadReceActual.revision_actual_id
                    == revision_actual.id,
                )
                .values(revision_actual_id=revision.id, updated_at=ahora)
            )
            if moved.rowcount != 1:
                raise ElegibilidadReceError(
                    "La elegibilidad RECE cambió de forma concurrente.",
                    categoria="conflicto_revision_fiscal",
                )
        return estado_produccion

    async def obtener_estado_visible(
        self,
        punto_venta: PuntoVenta,
        *,
        ambiente: Literal["homologacion", "produccion"],
    ) -> EstadoElegibilidadReceVisible:
        """Expone la cabeza efectiva sin hashes, CUIT ni actor probatorio."""
        row = (
            await self.db.execute(
                select(
                    PuntoVentaElegibilidadReceActual,
                    PuntoVentaElegibilidadReceRevision,
                )
                .join(
                    PuntoVentaElegibilidadReceRevision,
                    and_(
                        PuntoVentaElegibilidadReceRevision.id
                        == PuntoVentaElegibilidadReceActual.revision_actual_id,
                        PuntoVentaElegibilidadReceRevision.empresa_id
                        == PuntoVentaElegibilidadReceActual.empresa_id,
                        PuntoVentaElegibilidadReceRevision.punto_venta_id
                        == PuntoVentaElegibilidadReceActual.punto_venta_id,
                        PuntoVentaElegibilidadReceRevision.ambiente
                        == PuntoVentaElegibilidadReceActual.ambiente,
                    ),
                )
                .where(
                    PuntoVentaElegibilidadReceActual.empresa_id
                    == punto_venta.empresa_id,
                    PuntoVentaElegibilidadReceActual.punto_venta_id == punto_venta.id,
                    PuntoVentaElegibilidadReceActual.ambiente == ambiente,
                )
            )
        ).one_or_none()
        if row is None:
            return EstadoElegibilidadReceVisible(
                ambiente=ambiente,
                estado="no_verificado",
                estado_efectivo="no_verificado",
                fuente=None,
                revision_id=None,
                revision=None,
                punto_revision_fiscal=None,
                verificado_en=None,
                vigente_hasta=None,
                motivo="contexto_rece_ausente",
            )
        _head, revision = row
        estado_efectivo = revision.estado
        motivo: str | None = None
        if revision.punto_revision_fiscal != punto_venta.revision_fiscal or (
            revision.punto_venta_numero_snapshot is not None
            and revision.punto_venta_numero_snapshot != punto_venta.numero
        ):
            estado_efectivo = "no_verificado"
            motivo = "revision_fiscal_obsoleta"
        elif revision.estado == "no_rece":
            motivo = "punto_no_rece"
        elif revision.estado != "verificado_rece":
            motivo = "elegibilidad_rece_no_verificada"
        return EstadoElegibilidadReceVisible(
            ambiente=ambiente,
            estado=revision.estado,
            estado_efectivo=estado_efectivo,
            fuente=revision.fuente,
            revision_id=int(revision.id),
            revision=int(revision.revision),
            punto_revision_fiscal=int(revision.punto_revision_fiscal),
            verificado_en=revision.verificado_en,
            vigente_hasta=revision.vigente_hasta,
            motivo=motivo,
        )

    async def _prevalidar_cambio_punto(
        self,
        punto_venta: PuntoVenta,
        cambios: dict[str, object],
        *,
        forzar_revision: bool,
    ) -> None:
        """Toma punto/heads y rechaza guardas antes de escribir un batch."""
        cambios_reales = {
            field: value
            for field, value in cambios.items()
            if hasattr(punto_venta, field) and getattr(punto_venta, field) != value
        }
        if not (
            forzar_revision or bool(set(cambios_reales) - self.CAMPOS_SIN_REVISION)
        ):
            return
        revision_esperada = int(punto_venta.revision_fiscal)
        empresa_id = int(punto_venta.empresa_id)
        punto_venta_id = int(punto_venta.id)
        with self.db.no_autoflush:
            punto = (
                await self.db.execute(
                    select(PuntoVenta)
                    .where(
                        PuntoVenta.id == punto_venta_id,
                        PuntoVenta.empresa_id == empresa_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
        if punto is None or int(punto.revision_fiscal) != revision_esperada:
            raise ElegibilidadReceError(
                "El punto de venta cambió de forma concurrente; recargá y reintentá.",
                categoria="conflicto_revision_fiscal",
            )
        heads = list(
            (
                await self.db.execute(
                    select(PuntoVentaElegibilidadReceActual)
                    .where(
                        PuntoVentaElegibilidadReceActual.empresa_id == empresa_id,
                        PuntoVentaElegibilidadReceActual.punto_venta_id
                        == punto_venta_id,
                    )
                    .order_by(PuntoVentaElegibilidadReceActual.ambiente)
                    .with_for_update()
                )
            ).scalars()
        )
        if heads and len(heads) != 2:
            raise ElegibilidadReceError(
                "El punto de venta tiene un contexto RECE incompleto."
            )
        active_guard = await self.db.execute(
            select(PuntoVentaGuardaEmisionRece.id)
            .where(
                PuntoVentaGuardaEmisionRece.empresa_id == empresa_id,
                PuntoVentaGuardaEmisionRece.punto_venta_id == punto_venta_id,
                PuntoVentaGuardaEmisionRece.fase.in_(FASES_GUARDA_RECE_ACTIVAS),
            )
            .with_for_update()
        )
        if active_guard.first() is not None:
            raise ElegibilidadReceError(
                "El punto de venta tiene una solicitud fiscal activa o incierta.",
                categoria="conflicto_guarda_rece_activa",
            )

    async def exigir_contexto_actual(
        self,
        *,
        empresa_id: int,
        punto_venta_id: int,
        ambiente: str,
        bloquear: bool = False,
    ) -> ContextoElegibilidadRece:
        """Exige estado positivo vigente y coherencia técnica del punto."""
        if ambiente not in {"homologacion", "produccion"}:
            raise ElegibilidadReceError("El ambiente ARCA configurado no es válido.")

        stmt = (
            select(
                PuntoVenta,
                PuntoVentaElegibilidadReceActual,
                PuntoVentaElegibilidadReceRevision,
            )
            .join(
                PuntoVentaElegibilidadReceActual,
                and_(
                    PuntoVentaElegibilidadReceActual.punto_venta_id == PuntoVenta.id,
                    PuntoVentaElegibilidadReceActual.empresa_id
                    == PuntoVenta.empresa_id,
                    PuntoVentaElegibilidadReceActual.ambiente == ambiente,
                ),
            )
            .join(
                PuntoVentaElegibilidadReceRevision,
                and_(
                    PuntoVentaElegibilidadReceRevision.id
                    == PuntoVentaElegibilidadReceActual.revision_actual_id,
                    PuntoVentaElegibilidadReceRevision.empresa_id
                    == PuntoVentaElegibilidadReceActual.empresa_id,
                    PuntoVentaElegibilidadReceRevision.punto_venta_id
                    == PuntoVentaElegibilidadReceActual.punto_venta_id,
                    PuntoVentaElegibilidadReceRevision.ambiente
                    == PuntoVentaElegibilidadReceActual.ambiente,
                ),
            )
            .where(
                PuntoVenta.id == punto_venta_id,
                PuntoVenta.empresa_id == empresa_id,
            )
        )
        if bloquear:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        row = result.one_or_none()
        if row is None:
            raise ElegibilidadReceError()
        punto, _cabeza, revision = row

        if not (
            punto.activo
            and punto.es_webservice
            and not punto.bloqueado
            and not punto.fecha_baja
            and punto.usar_en_factuflow
        ):
            raise ElegibilidadReceError(
                "El punto de venta no está disponible para usar en FactuFlow."
            )
        if revision.estado != "verificado_rece":
            raise ElegibilidadReceError()
        evidencia_wsfe = (
            revision.ambiente == ambiente
            and revision.fuente == "sincronizacion_wsfe"
            and revision.evidencia_tipo == "wsfe_param_get_ptos_venta_v1"
        )
        evidencia_constancia_legacy = (
            revision.ambiente == "produccion"
            and revision.fuente == "constancia_arca_atestada"
            and revision.evidencia_tipo == "rece_aplicativo_web_services_v1"
        )
        if not (evidencia_wsfe or evidencia_constancia_legacy):
            raise ElegibilidadReceError()
        if (
            revision.punto_revision_fiscal != punto.revision_fiscal
            or revision.punto_venta_numero_snapshot != punto.numero
        ):
            raise ElegibilidadReceError(
                "La acreditación RECE quedó obsoleta por un cambio fiscal del punto."
            )
        empresa_cuit_actual = (
            await self.db.execute(select(Empresa.cuit).where(Empresa.id == empresa_id))
        ).scalar_one_or_none()
        if (
            empresa_cuit_actual is None
            or revision.empresa_cuit_snapshot != empresa_cuit_actual
        ):
            raise ElegibilidadReceError(
                "La acreditación RECE quedó obsoleta por un cambio fiscal del emisor."
            )

        return ContextoElegibilidadRece(
            empresa_id=empresa_id,
            punto_venta_id=punto.id,
            punto_venta_numero=punto.numero,
            ambiente=ambiente,
            elegibilidad_revision_id=revision.id,
            punto_venta_revision_fiscal=punto.revision_fiscal,
        )

    async def exigir_contexto_preautorizacion(
        self,
        *,
        empresa_id: int,
        punto_venta_id: int,
        ambiente: str,
        tipo_comprobante: int,
        bloquear: bool = False,
    ) -> ContextoElegibilidadRece:
        """Aplica PF-19A antes de exigir el snapshot RECE vigente."""
        if ambiente != settings.arca_env:
            raise ElegibilidadReceError(
                "El snapshot RECE no pertenece al ambiente ARCA configurado."
            )
        stmt = select(PuntoVenta).where(
            PuntoVenta.id == punto_venta_id,
            PuntoVenta.empresa_id == empresa_id,
        )
        if bloquear:
            stmt = stmt.with_for_update()
        punto = (await self.db.execute(stmt)).scalar_one_or_none()
        if punto is None:
            raise ElegibilidadReceError(
                "El punto de venta no pertenece al emisor activo."
            )
        bloqueo = obtener_bloqueo_preautorizacion(
            ambiente=ambiente,
            empresa_id=empresa_id,
            punto_venta_id=punto.id,
            punto_venta=punto.numero,
            tipo_comprobante=tipo_comprobante,
        )
        if bloqueo is not None:
            raise ElegibilidadReceError(
                MENSAJE_BLOQUEO_PREAUTORIZACION,
                categoria=CATEGORIA_BLOQUEO_PREAUTORIZACION,
            )
        return await self.exigir_contexto_actual(
            empresa_id=empresa_id,
            punto_venta_id=punto_venta_id,
            ambiente=ambiente,
            bloquear=bloquear,
        )

    @classmethod
    def calcular_digest_contextos(
        cls,
        contextos: list[ContextoElegibilidadRece],
    ) -> str:
        """Calcula el digest versionado de un conjunto RECE sin duplicados."""
        unicos = {
            (contexto.empresa_id, contexto.punto_venta_id, contexto.ambiente): contexto
            for contexto in contextos
        }
        if len(unicos) != len(contextos) or not contextos:
            raise ElegibilidadReceError(
                "El snapshot RECE de la operación está vacío o contiene duplicados."
            )
        material = {
            "version": cls.DIGEST_VERSION,
            "contextos": [
                contexto.material_digest()
                for contexto in sorted(
                    contextos,
                    key=lambda item: (
                        item.empresa_id,
                        item.punto_venta_id,
                        item.ambiente,
                    ),
                )
            ],
        }
        encoded = json.dumps(
            material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    async def agregar_snapshots_a_operacion(
        self,
        operacion: OperacionIdempotente,
        contextos: list[ContextoElegibilidadRece],
    ) -> str:
        """Agrega asociaciones y digest en la transacción de creación padre."""
        if operacion.id is None:
            await self.db.flush()
        if operacion.empresa_id is None or any(
            contexto.empresa_id != operacion.empresa_id for contexto in contextos
        ):
            raise ElegibilidadReceError(
                "El snapshot RECE no pertenece al emisor de la operación."
            )
        digest = self.calcular_digest_contextos(contextos)
        for contexto in contextos:
            self.db.add(
                OperacionIdempotenteElegibilidadRece(
                    operacion_id=operacion.id,
                    empresa_id=contexto.empresa_id,
                    punto_venta_id=contexto.punto_venta_id,
                    ambiente=contexto.ambiente,
                    elegibilidad_revision_id=contexto.elegibilidad_revision_id,
                    punto_venta_revision_fiscal=(contexto.punto_venta_revision_fiscal),
                )
            )
        operacion.rece_snapshot_hash = digest
        self.db.add(operacion)
        await self.db.flush()
        return digest

    async def validar_operacion_para_continuar(
        self,
        *,
        operacion_id: int,
        empresa_id: int,
        contextos_esperados: list[ContextoElegibilidadRece] | None = None,
    ) -> list[ContextoElegibilidadRece]:
        """Rechaza operaciones legacy o snapshots incompletos antes de ARCA."""
        operacion = await self.db.get(OperacionIdempotente, operacion_id)
        if operacion is None or operacion.empresa_id != empresa_id:
            raise ElegibilidadReceError("La operación fiscal no pertenece al emisor.")
        result = await self.db.execute(
            select(OperacionIdempotenteElegibilidadRece)
            .where(
                OperacionIdempotenteElegibilidadRece.operacion_id == operacion_id,
                OperacionIdempotenteElegibilidadRece.empresa_id == empresa_id,
            )
            .order_by(
                OperacionIdempotenteElegibilidadRece.punto_venta_id,
                OperacionIdempotenteElegibilidadRece.ambiente,
            )
        )
        asociaciones = list(result.scalars().all())
        if not asociaciones or operacion.rece_snapshot_hash is None:
            raise ElegibilidadReceError(
                "La operación fiscal es legacy y no puede continuar hacia ARCA."
            )

        contextos = [
            ContextoElegibilidadRece(
                empresa_id=asociacion.empresa_id,
                punto_venta_id=asociacion.punto_venta_id,
                punto_venta_numero=0,
                ambiente=asociacion.ambiente,
                elegibilidad_revision_id=asociacion.elegibilidad_revision_id,
                punto_venta_revision_fiscal=(asociacion.punto_venta_revision_fiscal),
            )
            for asociacion in asociaciones
        ]
        actuales: list[ContextoElegibilidadRece] = []
        for contexto in contextos:
            actual = await self.exigir_contexto_actual(
                empresa_id=contexto.empresa_id,
                punto_venta_id=contexto.punto_venta_id,
                ambiente=contexto.ambiente,
            )
            if (
                actual.elegibilidad_revision_id != contexto.elegibilidad_revision_id
                or actual.punto_venta_revision_fiscal
                != contexto.punto_venta_revision_fiscal
            ):
                raise ElegibilidadReceError(
                    "La acreditación RECE cambió después de confirmar la operación."
                )
            actuales.append(actual)

        digest = self.calcular_digest_contextos(actuales)
        if digest != operacion.rece_snapshot_hash:
            raise ElegibilidadReceError(
                "El digest RECE de la operación no coincide con sus asociaciones."
            )
        if contextos_esperados is not None:
            esperado = self.calcular_digest_contextos(contextos_esperados)
            if esperado != digest:
                raise ElegibilidadReceError(
                    "La operación no conserva la membresía RECE confirmada."
                )
        return actuales

    async def validar_grupos_lote(
        self,
        *,
        lote_id: int,
        empresa_id: int,
        grupo_ids: list[int],
        tipo_comprobante_por_grupo: dict[int, int],
        material_confirmado: list[dict[str, object]],
        bloquear: bool = False,
    ) -> list[ContextoElegibilidadRece]:
        """Valida sin filtrado la membresía y snapshots de grupos confirmados."""
        ids_esperados = set(grupo_ids)
        if not ids_esperados or len(ids_esperados) != len(grupo_ids):
            raise ElegibilidadReceError(
                "La membresía RECE del lote está vacía o contiene duplicados."
            )
        stmt = (
            select(LoteComprobanteGrupo)
            .where(
                LoteComprobanteGrupo.lote_id == lote_id,
                LoteComprobanteGrupo.empresa_id == empresa_id,
                LoteComprobanteGrupo.id.in_(ids_esperados),
            )
            .order_by(LoteComprobanteGrupo.id)
        )
        if bloquear:
            stmt = stmt.with_for_update()
        result = await self.db.execute(stmt)
        grupos = list(result.scalars().all())
        if {int(grupo.id) for grupo in grupos} != ids_esperados:
            raise ElegibilidadReceError(
                "La membresía confirmada del lote cambió antes de emitir."
            )
        material_por_id = {int(item["grupo_id"]): item for item in material_confirmado}
        if set(material_por_id) != ids_esperados or len(material_por_id) != len(
            material_confirmado
        ):
            raise ElegibilidadReceError(
                "El material confirmado del lote está incompleto o duplicado."
            )
        contextos_por_punto: dict[tuple[int, int, str], ContextoElegibilidadRece] = {}
        for grupo in sorted(
            grupos,
            key=lambda item: (int(item.punto_venta_id or 0), int(item.id)),
        ):
            tipo_comprobante = tipo_comprobante_por_grupo.get(int(grupo.id))
            if (
                tipo_comprobante is None
                or grupo.punto_venta_id is None
                or grupo.ambiente is None
                or grupo.punto_venta_elegibilidad_revision_id is None
                or grupo.punto_venta_revision_fiscal is None
                or grupo.punto_venta_numero is None
            ):
                raise ElegibilidadReceError(
                    "El lote es legacy y debe revalidarse antes de emitir."
                )
            payload = grupo.payload_json or {}
            if not isinstance(payload, dict):
                raise ElegibilidadReceError(
                    "El payload fiscal del grupo no tiene un objeto válido."
                )
            material_actual: dict[str, object] = {
                "grupo_id": int(grupo.id),
                "empresa_id": int(grupo.empresa_id),
                "punto_venta_id": grupo.punto_venta_id,
                "punto_venta_numero": grupo.punto_venta_numero,
                "ambiente": grupo.ambiente,
                "elegibilidad_revision_id": (
                    grupo.punto_venta_elegibilidad_revision_id
                ),
                "punto_venta_revision_fiscal": grupo.punto_venta_revision_fiscal,
                "tipo_comprobante": grupo.tipo_comprobante,
                "payload_hash": hashlib.sha256(
                    json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    ).encode("utf-8")
                ).hexdigest(),
            }
            if material_actual != material_por_id[int(grupo.id)]:
                raise ElegibilidadReceError(
                    "El material fiscal del grupo cambió después de confirmarse."
                )
            try:
                payload_empresa_id = int(payload.get("empresa_id", 0))
                payload_punto_venta_id = int(payload.get("punto_venta_id", 0))
            except (TypeError, ValueError) as exc:
                raise ElegibilidadReceError(
                    "El payload fiscal del grupo contiene identidades inválidas."
                ) from exc
            if (
                payload_empresa_id != empresa_id
                or payload_punto_venta_id != grupo.punto_venta_id
                or int(grupo.tipo_comprobante or 0) != tipo_comprobante
            ):
                raise ElegibilidadReceError(
                    "El payload fiscal del grupo no coincide con su snapshot RECE."
                )
            actual = await self.exigir_contexto_preautorizacion(
                empresa_id=empresa_id,
                punto_venta_id=grupo.punto_venta_id,
                ambiente=grupo.ambiente,
                tipo_comprobante=tipo_comprobante,
                bloquear=bloquear,
            )
            if (
                actual.punto_venta_numero != grupo.punto_venta_numero
                or actual.elegibilidad_revision_id
                != grupo.punto_venta_elegibilidad_revision_id
                or actual.punto_venta_revision_fiscal
                != grupo.punto_venta_revision_fiscal
            ):
                raise ElegibilidadReceError(
                    "El lote quedó obsoleto por un cambio de elegibilidad RECE."
                )
            contextos_por_punto[
                (empresa_id, actual.punto_venta_id, actual.ambiente)
            ] = actual
        return list(contextos_por_punto.values())

    async def crear_guarda_pre_arca(
        self,
        *,
        operacion_id: int,
        contexto: ContextoElegibilidadRece,
        contextos_operacion: list[ContextoElegibilidadRece],
    ) -> PuntoVentaGuardaEmisionRece:
        """Crea una guarda pre-ARCA ligada al snapshot de la operación."""
        if contexto not in contextos_operacion:
            raise ElegibilidadReceError(
                "La guarda RECE no pertenece a la membresía de la operación."
            )
        await self.validar_operacion_para_continuar(
            operacion_id=operacion_id,
            empresa_id=contexto.empresa_id,
            contextos_esperados=contextos_operacion,
        )
        guarda = PuntoVentaGuardaEmisionRece(
            token=secrets.token_hex(32),
            fase="pre_arca",
            operacion_id=operacion_id,
            empresa_id=contexto.empresa_id,
            punto_venta_id=contexto.punto_venta_id,
            ambiente=contexto.ambiente,
            elegibilidad_revision_id=contexto.elegibilidad_revision_id,
            punto_venta_revision_fiscal=contexto.punto_venta_revision_fiscal,
        )
        self.db.add(guarda)
        await self.db.flush()
        return guarda

    async def recuperar_guarda_interrumpida_pre_arca(
        self,
        *,
        operacion_id: int,
        guarda_id: int,
        token: str,
        commit: bool = True,
    ) -> Literal["recuperada_pre_arca", "requiere_reconciliacion", "no_recuperable",]:
        """Cierra por CAS solo una guarda propia que prueba cero inicio ARCA."""
        operacion = (
            await self.db.execute(
                select(OperacionIdempotente)
                .where(OperacionIdempotente.id == operacion_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        intentos_operacion = list(
            (
                await self.db.execute(
                    select(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.operacion_id == operacion_id)
                    .order_by(IntentoEmisionFiscal.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        guardas_operacion = list(
            (
                await self.db.execute(
                    select(PuntoVentaGuardaEmisionRece)
                    .where(PuntoVentaGuardaEmisionRece.operacion_id == operacion_id)
                    .order_by(PuntoVentaGuardaEmisionRece.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        guardas_por_id = {
            int(guarda_operacion.id): guarda_operacion
            for guarda_operacion in guardas_operacion
        }
        ids_guardas_referenciadas = {
            int(intento.guarda_rece_id)
            for intento in intentos_operacion
            if intento.guarda_rece_id is not None
        }
        if (
            any(intento.guarda_rece_id is None for intento in intentos_operacion)
            or set(guardas_por_id) != ids_guardas_referenciadas
        ):
            return "no_recuperable"
        guarda = guardas_por_id.get(guarda_id)
        if guarda is None or guarda.token != token:
            return "no_recuperable"
        intentos = [
            intento
            for intento in intentos_operacion
            if intento.guarda_rece_id == guarda_id
        ]
        intentos_ajenos = [
            intento
            for intento in intentos_operacion
            if intento.guarda_rece_id != guarda_id
        ]
        if operacion is None or not intentos:
            return "no_recuperable"
        if operacion.rece_snapshot_hash is None or operacion.response_json is not None:
            return "no_recuperable"
        if any(
            intento.operacion_id != operacion_id
            or intento.empresa_id != guarda.empresa_id
            or intento.punto_venta_id != guarda.punto_venta_id
            or intento.ambiente != guarda.ambiente
            or intento.punto_venta_elegibilidad_revision_id
            != guarda.elegibilidad_revision_id
            or intento.punto_venta_revision_fiscal != guarda.punto_venta_revision_fiscal
            for intento in intentos
        ):
            return "no_recuperable"
        if intentos_ajenos:
            ids_guardas_ajenas = {
                int(intento.guarda_rece_id)
                for intento in intentos_ajenos
                if intento.guarda_rece_id is not None
            }
            if len(ids_guardas_ajenas) == 0 or any(
                intento.guarda_rece_id is None for intento in intentos_ajenos
            ):
                return "no_recuperable"
            guardas_ajenas_por_id = {
                guarda_ajena_id: guardas_por_id[guarda_ajena_id]
                for guarda_ajena_id in ids_guardas_ajenas
                if guarda_ajena_id in guardas_por_id
            }
            if len(guardas_ajenas_por_id) != len(ids_guardas_ajenas):
                return "no_recuperable"
            evidencia_ajena_coherente = True
            for intento_ajeno in intentos_ajenos:
                guarda_ajena = guardas_ajenas_por_id[int(intento_ajeno.guarda_rece_id)]
                terminal_arca = (
                    guarda_ajena.fase == "cerrada_terminal"
                    and guarda_ajena.arca_iniciada_en is not None
                    and guarda_ajena.cerrada_en is not None
                    and intento_ajeno.estado in {"autorizado", "rechazado_arca"}
                    and (
                        intento_ajeno.estado != "autorizado"
                        or (
                            intento_ajeno.cae is not None
                            and intento_ajeno.comprobante_id is not None
                        )
                    )
                    and (
                        intento_ajeno.estado != "rechazado_arca"
                        or (
                            intento_ajeno.cae is None
                            and intento_ajeno.comprobante_id is None
                        )
                    )
                )
                terminal_pre_arca = (
                    guarda_ajena.fase == "cerrada_pre_arca"
                    and guarda_ajena.arca_iniciada_en is None
                    and guarda_ajena.cerrada_en is not None
                    and intento_ajeno.estado == "fallido_verificado"
                    and intento_ajeno.cae is None
                    and intento_ajeno.comprobante_id is None
                )
                if not (terminal_arca or terminal_pre_arca):
                    evidencia_ajena_coherente = False
                    break
            if not evidencia_ajena_coherente:
                return "no_recuperable"

        if guarda.fase in {"arca_iniciada", "requiere_reconciliacion"}:
            await self._marcar_recuperacion_guarda_ambigua(
                guarda=guarda,
                operacion=operacion,
                intentos=intentos,
                commit=commit,
            )
            return "requiere_reconciliacion"

        sin_evidencia_arca = all(
            intento.cae is None
            and intento.comprobante_id is None
            and intento.estado in {"en_proceso", "fallido_verificado"}
            for intento in intentos
        )
        if (
            guarda.fase == "cerrada_pre_arca"
            and guarda.arca_iniciada_en is None
            and guarda.cerrada_en is not None
            and sin_evidencia_arca
        ):
            if intentos_ajenos:
                if operacion.estado == "en_proceso":
                    result = await self.db.execute(
                        update(OperacionIdempotente)
                        .where(
                            OperacionIdempotente.id == operacion_id,
                            OperacionIdempotente.estado == "en_proceso",
                            OperacionIdempotente.response_json.is_(None),
                        )
                        .values(estado="requiere_reconciliacion")
                    )
                    if result.rowcount != 1:
                        await self.db.rollback()
                        return "no_recuperable"
                elif operacion.estado != "requiere_reconciliacion":
                    return "no_recuperable"
                if commit:
                    await self.db.commit()
                else:
                    await self.db.flush()
                return "requiere_reconciliacion"
            if operacion.estado == "en_proceso":
                result = await self.db.execute(
                    update(OperacionIdempotente)
                    .where(
                        OperacionIdempotente.id == operacion_id,
                        OperacionIdempotente.estado == "en_proceso",
                        OperacionIdempotente.response_json.is_(None),
                    )
                    .values(estado="interrumpida_pre_arca")
                )
                if result.rowcount != 1:
                    await self.db.rollback()
                    return "no_recuperable"
            elif operacion.estado != "interrumpida_pre_arca":
                return "no_recuperable"
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()
            return "recuperada_pre_arca"

        if (
            guarda.fase != "pre_arca"
            or guarda.arca_iniciada_en is not None
            or guarda.cerrada_en is not None
            or operacion.estado != "en_proceso"
            or not sin_evidencia_arca
            or any(intento.estado != "en_proceso" for intento in intentos)
        ):
            return "no_recuperable"

        if not intentos_ajenos:
            otra_guarda_activa = (
                await self.db.execute(
                    select(PuntoVentaGuardaEmisionRece.id)
                    .where(
                        PuntoVentaGuardaEmisionRece.operacion_id == operacion_id,
                        PuntoVentaGuardaEmisionRece.id != guarda_id,
                        PuntoVentaGuardaEmisionRece.fase.in_(FASES_GUARDA_RECE_ACTIVAS),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if otra_guarda_activa is not None:
                return "no_recuperable"

        ahora = datetime.utcnow()
        guarda_cerrada = await self.db.execute(
            update(PuntoVentaGuardaEmisionRece)
            .where(
                PuntoVentaGuardaEmisionRece.id == guarda_id,
                PuntoVentaGuardaEmisionRece.token == token,
                PuntoVentaGuardaEmisionRece.operacion_id == operacion_id,
                PuntoVentaGuardaEmisionRece.fase == "pre_arca",
                PuntoVentaGuardaEmisionRece.arca_iniciada_en.is_(None),
                PuntoVentaGuardaEmisionRece.cerrada_en.is_(None),
            )
            .values(fase="cerrada_pre_arca", cerrada_en=ahora)
        )
        intento_ids = [intento.id for intento in intentos]
        intentos_cerrados = await self.db.execute(
            update(IntentoEmisionFiscal)
            .where(
                IntentoEmisionFiscal.id.in_(intento_ids),
                IntentoEmisionFiscal.operacion_id == operacion_id,
                IntentoEmisionFiscal.guarda_rece_id == guarda_id,
                IntentoEmisionFiscal.estado == "en_proceso",
            )
            .values(
                estado="fallido_verificado",
                categoria_error="interrumpida_pre_arca_recuperada",
                mensaje=(
                    "La solicitud quedó cerrada antes de iniciar ARCA y puede "
                    "reclamarse con la misma clave de idempotencia."
                ),
            )
        )
        estado_operacion_destino = (
            "requiere_reconciliacion" if intentos_ajenos else "interrumpida_pre_arca"
        )
        operacion_interrumpida = await self.db.execute(
            update(OperacionIdempotente)
            .where(
                OperacionIdempotente.id == operacion_id,
                OperacionIdempotente.estado == "en_proceso",
                OperacionIdempotente.response_json.is_(None),
            )
            .values(estado=estado_operacion_destino)
        )
        if (
            guarda_cerrada.rowcount != 1
            or intentos_cerrados.rowcount != len(intento_ids)
            or operacion_interrumpida.rowcount != 1
        ):
            await self.db.rollback()
            return "no_recuperable"
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
        if intentos_ajenos:
            return "requiere_reconciliacion"
        return "recuperada_pre_arca"

    async def _marcar_recuperacion_guarda_ambigua(
        self,
        *,
        guarda: PuntoVentaGuardaEmisionRece,
        operacion: OperacionIdempotente,
        intentos: list[IntentoEmisionFiscal],
        commit: bool,
    ) -> None:
        """Conserva activa una guarda cuyo inicio ARCA ya no puede descartarse."""
        if guarda.fase == "arca_iniciada":
            await self.db.execute(
                update(PuntoVentaGuardaEmisionRece)
                .where(
                    PuntoVentaGuardaEmisionRece.id == guarda.id,
                    PuntoVentaGuardaEmisionRece.token == guarda.token,
                    PuntoVentaGuardaEmisionRece.fase == "arca_iniciada",
                )
                .values(fase="requiere_reconciliacion")
            )
        await self.db.execute(
            update(IntentoEmisionFiscal)
            .where(
                IntentoEmisionFiscal.id.in_([intento.id for intento in intentos]),
                IntentoEmisionFiscal.estado == "en_proceso",
            )
            .values(
                estado="requiere_reconciliacion",
                categoria_error="arca_inicio_ambiguo",
                mensaje=(
                    "La guarda pudo haber iniciado ARCA y requiere reconciliación."
                ),
            )
        )
        await self.db.execute(
            update(OperacionIdempotente)
            .where(
                OperacionIdempotente.id == operacion.id,
                OperacionIdempotente.estado == "en_proceso",
                OperacionIdempotente.response_json.is_(None),
            )
            .values(estado="requiere_reconciliacion")
        )
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()

    async def marcar_arca_iniciada(
        self,
        *,
        guarda: PuntoVentaGuardaEmisionRece,
        contexto: ContextoElegibilidadRece,
        tipo_comprobante: int,
    ) -> None:
        """Revalida por CAS, commitea y recién entonces permite FECAE."""
        actual = await self.exigir_contexto_preautorizacion(
            empresa_id=contexto.empresa_id,
            punto_venta_id=contexto.punto_venta_id,
            ambiente=contexto.ambiente,
            tipo_comprobante=tipo_comprobante,
            bloquear=True,
        )
        if actual != contexto:
            raise ElegibilidadReceError(
                "La acreditación RECE cambió inmediatamente antes de ARCA."
            )
        guarda_id = int(guarda.id)
        operacion_id = int(guarda.operacion_id)
        guarda_token = str(guarda.token)
        await self.validar_operacion_para_continuar(
            operacion_id=operacion_id,
            empresa_id=contexto.empresa_id,
        )
        fila_operacion_propietaria = (
            await self.db.execute(
                select(
                    OperacionIdempotente,
                    OperacionIdempotente.response_json.is_(None).label(
                        "respuesta_es_sql_null"
                    ),
                )
                .where(
                    OperacionIdempotente.id == operacion_id,
                    OperacionIdempotente.empresa_id == contexto.empresa_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        operacion_propietaria = (
            fila_operacion_propietaria[0]
            if fila_operacion_propietaria is not None
            else None
        )
        respuesta_es_sql_null = bool(
            fila_operacion_propietaria[1]
            if fila_operacion_propietaria is not None
            else False
        )
        intentos_operacion = list(
            (
                await self.db.execute(
                    select(
                        IntentoEmisionFiscal.id,
                        IntentoEmisionFiscal.estado,
                        IntentoEmisionFiscal.operacion_id,
                        IntentoEmisionFiscal.empresa_id,
                        IntentoEmisionFiscal.punto_venta_id,
                        IntentoEmisionFiscal.ambiente,
                        IntentoEmisionFiscal.punto_venta_elegibilidad_revision_id,
                        IntentoEmisionFiscal.punto_venta_revision_fiscal,
                        IntentoEmisionFiscal.lote_id,
                        IntentoEmisionFiscal.grupo_id,
                        IntentoEmisionFiscal.guarda_rece_id,
                    )
                    .where(IntentoEmisionFiscal.operacion_id == operacion_id)
                    .order_by(IntentoEmisionFiscal.id)
                    .with_for_update()
                )
            ).all()
        )
        guardas_operacion = list(
            (
                await self.db.execute(
                    select(PuntoVentaGuardaEmisionRece)
                    .where(PuntoVentaGuardaEmisionRece.operacion_id == operacion_id)
                    .order_by(PuntoVentaGuardaEmisionRece.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        guarda_actual = next(
            (
                guarda_operacion
                for guarda_operacion in guardas_operacion
                if int(guarda_operacion.id) == guarda_id
            ),
            None,
        )
        ids_guardas_referenciadas = {
            int(intento.guarda_rece_id)
            for intento in intentos_operacion
            if intento.guarda_rece_id is not None
        }
        if (
            any(intento.guarda_rece_id is None for intento in intentos_operacion)
            or {int(guarda_operacion.id) for guarda_operacion in guardas_operacion}
            != ids_guardas_referenciadas
        ):
            await self.db.rollback()
            raise ElegibilidadReceError(
                "La operación conserva guardas RECE sin intentos coherentes."
            )
        intentos = [
            intento
            for intento in intentos_operacion
            if intento.guarda_rece_id == guarda_id
        ]
        if (
            operacion_propietaria is None
            or not intentos
            or any(
                intento.estado != "en_proceso"
                or intento.operacion_id != operacion_id
                or intento.empresa_id != contexto.empresa_id
                or intento.punto_venta_id != contexto.punto_venta_id
                or intento.ambiente != contexto.ambiente
                or intento.punto_venta_elegibilidad_revision_id
                != contexto.elegibilidad_revision_id
                or intento.punto_venta_revision_fiscal
                != contexto.punto_venta_revision_fiscal
                for intento in intentos
            )
        ):
            await self.db.rollback()
            raise ElegibilidadReceError(
                "La operación o sus intentos perdieron ownership antes de ARCA."
            )
        if (
            guarda_actual is None
            or guarda_actual.token != guarda_token
            or guarda_actual.fase != "pre_arca"
            or guarda_actual.empresa_id != contexto.empresa_id
            or guarda_actual.punto_venta_id != contexto.punto_venta_id
            or guarda_actual.ambiente != contexto.ambiente
            or guarda_actual.elegibilidad_revision_id
            != contexto.elegibilidad_revision_id
            or guarda_actual.punto_venta_revision_fiscal
            != contexto.punto_venta_revision_fiscal
        ):
            await self.db.rollback()
            raise ElegibilidadReceError(
                "La guarda RECE perdió ownership antes de ARCA."
            )
        intentos_batch = [
            intento
            for intento in intentos
            if intento.lote_id is not None or intento.grupo_id is not None
        ]
        if any(
            intento.lote_id is None or intento.grupo_id is None
            for intento in intentos_batch
        ):
            await self.db.rollback()
            raise ElegibilidadReceError(
                "La membresía batch de la guarda está incompleta antes de ARCA."
            )
        if operacion_propietaria.tipo_operacion == "emitir_comprobante":
            membresia_operacion_valida = not intentos_batch
        else:
            membresia_operacion_valida = (
                bool(intentos_batch)
                and operacion_propietaria.lote_id is not None
                and all(
                    intento.lote_id == operacion_propietaria.lote_id
                    for intento in intentos_batch
                )
            )
        if not membresia_operacion_valida:
            await self.db.rollback()
            raise ElegibilidadReceError(
                "La operación perdió su membresía fiscal antes de ARCA."
            )
        lote_operacion: LoteComprobante | None = None
        lote_background: bool | None = None
        material_rece: dict[str, object] | None = None
        if operacion_propietaria.tipo_operacion != "emitir_comprobante":
            lote_operacion = (
                await self.db.execute(
                    select(LoteComprobante)
                    .where(
                        LoteComprobante.id == operacion_propietaria.lote_id,
                        LoteComprobante.empresa_id == contexto.empresa_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if lote_operacion is None:
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El lote de la operación no conserva ownership antes de ARCA."
                )
            modo_background_db = (
                lote_operacion.procesamiento_async is True
                or lote_operacion.modo_procesamiento == "background"
            )
            if operacion_propietaria.tipo_operacion == "reintentar_fallidos_lote":
                lote_background = False
            else:
                lote_background = modo_background_db
            metadata_lote = lote_operacion.metadata_json
            owner_metadata = (
                metadata_lote.get("operacion_idempotente_id")
                if isinstance(metadata_lote, dict)
                else None
            )
            if (
                not isinstance(metadata_lote, dict)
                or not isinstance(owner_metadata, int)
                or isinstance(owner_metadata, bool)
                or owner_metadata != int(operacion_propietaria.id)
            ):
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El lote perdió su operación propietaria antes de ARCA."
                )
            material_candidato = metadata_lote.get("pf19b_rece_material")
            if isinstance(material_candidato, dict):
                material_rece = material_candidato
        if not IdempotenciaFiscalService.operacion_conserva_ownership_pre_arca(
            operacion_propietaria,
            respuesta_es_sql_null=respuesta_es_sql_null,
            lote_background=lote_background,
            material_rece=material_rece,
        ):
            await self.db.rollback()
            raise ElegibilidadReceError(
                "La operación perdió ownership durable antes de ARCA."
            )
        if intentos_batch:
            if (
                material_rece is None
                or set(material_rece) != {"grupo_ids", "grupos_hash", "grupos"}
                or not isinstance(material_rece.get("grupo_ids"), list)
                or not isinstance(material_rece.get("grupos"), list)
                or not isinstance(material_rece.get("grupos_hash"), str)
            ):
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El lote no conserva su material RECE canónico."
                )
            try:
                grupo_ids_material = [
                    int(grupo_id) for grupo_id in material_rece["grupo_ids"]
                ]
                material_por_id = {
                    int(item["grupo_id"]): item for item in material_rece["grupos"]
                }
            except (KeyError, TypeError, ValueError) as exc:
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El material RECE del lote contiene identidades inválidas."
                ) from exc
            if (
                not grupo_ids_material
                or len(grupo_ids_material) != len(set(grupo_ids_material))
                or set(material_por_id) != set(grupo_ids_material)
                or len(material_por_id) != len(material_rece["grupos"])
                or any(
                    intento.grupo_id not in material_por_id
                    for intento in intentos_batch
                )
            ):
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "La respuesta del worker no conserva la membresía confirmada."
                )
            grupos_material = list(
                (
                    await self.db.execute(
                        select(LoteComprobanteGrupo)
                        .where(
                            LoteComprobanteGrupo.lote_id
                            == operacion_propietaria.lote_id,
                            LoteComprobanteGrupo.empresa_id == contexto.empresa_id,
                            LoteComprobanteGrupo.id.in_(grupo_ids_material),
                        )
                        .order_by(LoteComprobanteGrupo.id)
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            material_actual: list[dict[str, object]] = []
            for grupo_material in grupos_material:
                payload = grupo_material.payload_json
                if not isinstance(payload, dict):
                    await self.db.rollback()
                    raise ElegibilidadReceError(
                        "El payload fiscal del grupo dejó de ser un objeto válido."
                    )
                material_actual.append(
                    {
                        "grupo_id": int(grupo_material.id),
                        "empresa_id": int(grupo_material.empresa_id),
                        "punto_venta_id": grupo_material.punto_venta_id,
                        "punto_venta_numero": grupo_material.punto_venta_numero,
                        "ambiente": grupo_material.ambiente,
                        "elegibilidad_revision_id": (
                            grupo_material.punto_venta_elegibilidad_revision_id
                        ),
                        "punto_venta_revision_fiscal": (
                            grupo_material.punto_venta_revision_fiscal
                        ),
                        "tipo_comprobante": grupo_material.tipo_comprobante,
                        "payload_hash": hashlib.sha256(
                            json.dumps(
                                payload,
                                sort_keys=True,
                                separators=(",", ":"),
                                default=str,
                            ).encode("utf-8")
                        ).hexdigest(),
                    }
                )
            material_hash_actual = hashlib.sha256(
                json.dumps(
                    material_actual,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if (
                [int(grupo.id) for grupo in grupos_material] != grupo_ids_material
                or material_actual != material_rece["grupos"]
                or material_hash_actual != material_rece["grupos_hash"]
            ):
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El material fiscal del lote cambió antes de iniciar ARCA."
                )
        estados_lote_permitidos: set[str] = set()
        estados_grupo_permitidos: set[str] = set()
        if intentos_batch:
            if operacion_propietaria.tipo_operacion == "procesar_lote":
                estados_lote_permitidos = {"procesando"}
                estados_grupo_permitidos = {"validado"}
            elif operacion_propietaria.tipo_operacion == "reintentar_fallidos_lote":
                estados_lote_permitidos = {"con_errores", "fallido"}
                estados_grupo_permitidos = {"reintentando"}
            else:
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El tipo de operación no admite membresía batch."
                )
            grupos_propios = list(
                (
                    await self.db.execute(
                        select(IntentoEmisionFiscal.id)
                        .join(
                            LoteComprobanteGrupo,
                            LoteComprobanteGrupo.id == IntentoEmisionFiscal.grupo_id,
                        )
                        .join(
                            LoteComprobante,
                            LoteComprobante.id == IntentoEmisionFiscal.lote_id,
                        )
                        .where(
                            IntentoEmisionFiscal.guarda_rece_id == guarda_id,
                            LoteComprobanteGrupo.lote_id
                            == IntentoEmisionFiscal.lote_id,
                            LoteComprobanteGrupo.empresa_id
                            == IntentoEmisionFiscal.empresa_id,
                            LoteComprobanteGrupo.estado.in_(estados_grupo_permitidos),
                            LoteComprobante.empresa_id
                            == IntentoEmisionFiscal.empresa_id,
                            LoteComprobante.estado.in_(estados_lote_permitidos),
                        )
                        .order_by(IntentoEmisionFiscal.id)
                        .with_for_update()
                    )
                ).scalars()
            )
            if len(grupos_propios) != len(intentos_batch):
                await self.db.rollback()
                raise ElegibilidadReceError(
                    "El lote o sus grupos perdieron ownership antes de ARCA."
                )
        ahora = datetime.utcnow()
        operacion_updated_at = operacion_propietaria.updated_at
        existe_intento = exists(
            select(IntentoEmisionFiscal.id).where(
                IntentoEmisionFiscal.guarda_rece_id == guarda_id,
                IntentoEmisionFiscal.estado == "en_proceso",
            )
        )
        existe_intento_invalido = exists(
            select(IntentoEmisionFiscal.id).where(
                IntentoEmisionFiscal.guarda_rece_id == guarda_id,
                IntentoEmisionFiscal.estado != "en_proceso",
            )
        )
        conserva_operacion = exists(
            select(OperacionIdempotente.id).where(
                OperacionIdempotente.id == operacion_id,
                OperacionIdempotente.empresa_id == contexto.empresa_id,
                OperacionIdempotente.estado == "en_proceso",
                OperacionIdempotente.updated_at == operacion_updated_at,
            )
        )
        grupo_batch_valido = exists(
            select(LoteComprobanteGrupo.id)
            .join(
                LoteComprobante,
                LoteComprobante.id == LoteComprobanteGrupo.lote_id,
            )
            .where(
                LoteComprobanteGrupo.id == IntentoEmisionFiscal.grupo_id,
                LoteComprobanteGrupo.lote_id == IntentoEmisionFiscal.lote_id,
                LoteComprobanteGrupo.empresa_id == IntentoEmisionFiscal.empresa_id,
                LoteComprobanteGrupo.estado.in_(estados_grupo_permitidos),
                LoteComprobante.empresa_id == IntentoEmisionFiscal.empresa_id,
                LoteComprobante.estado.in_(estados_lote_permitidos),
            )
        )
        existe_intento_batch_invalido = exists(
            select(IntentoEmisionFiscal.id).where(
                IntentoEmisionFiscal.guarda_rece_id == guarda_id,
                IntentoEmisionFiscal.grupo_id.is_not(None),
                ~grupo_batch_valido,
            )
        )
        result = await self.db.execute(
            update(PuntoVentaGuardaEmisionRece)
            .where(
                PuntoVentaGuardaEmisionRece.id == guarda_id,
                PuntoVentaGuardaEmisionRece.token == guarda_token,
                PuntoVentaGuardaEmisionRece.fase == "pre_arca",
                PuntoVentaGuardaEmisionRece.operacion_id == operacion_id,
                PuntoVentaGuardaEmisionRece.empresa_id == contexto.empresa_id,
                PuntoVentaGuardaEmisionRece.punto_venta_id == contexto.punto_venta_id,
                PuntoVentaGuardaEmisionRece.ambiente == contexto.ambiente,
                PuntoVentaGuardaEmisionRece.elegibilidad_revision_id
                == contexto.elegibilidad_revision_id,
                PuntoVentaGuardaEmisionRece.punto_venta_revision_fiscal
                == contexto.punto_venta_revision_fiscal,
                existe_intento,
                ~existe_intento_invalido,
                conserva_operacion,
                ~existe_intento_batch_invalido,
            )
            .values(fase="arca_iniciada", arca_iniciada_en=ahora)
        )
        if result.rowcount != 1:
            await self.db.rollback()
            raise ElegibilidadReceError(
                "La guarda RECE no pudo cruzar de forma exclusiva hacia ARCA."
            )
        await self.db.commit()

    async def cerrar_pre_arca(
        self,
        guarda: PuntoVentaGuardaEmisionRece,
        *,
        commit: bool = True,
    ) -> None:
        """Cierra una guarda cuando se prueba que FECAE no comenzó."""
        await self._cambiar_fase_guarda(
            guarda,
            desde={"pre_arca"},
            hacia="cerrada_pre_arca",
            cerrada_en=datetime.utcnow(),
            commit=commit,
        )

    async def cerrar_terminal(
        self,
        guarda: PuntoVentaGuardaEmisionRece,
        *,
        commit: bool = True,
    ) -> None:
        """Cierra una guarda cuyo resultado ARCA quedó durablemente resuelto."""
        await self._cambiar_fase_guarda(
            guarda,
            desde={"arca_iniciada"},
            hacia="cerrada_terminal",
            cerrada_en=datetime.utcnow(),
            commit=commit,
        )

    async def marcar_requiere_reconciliacion(
        self,
        guarda: PuntoVentaGuardaEmisionRece,
        *,
        commit: bool = True,
    ) -> None:
        """Conserva activa una guarda ante cualquier resultado incierto."""
        await self._cambiar_fase_guarda(
            guarda,
            desde={"arca_iniciada", "requiere_reconciliacion"},
            hacia="requiere_reconciliacion",
            cerrada_en=None,
            commit=commit,
        )

    async def _cambiar_fase_guarda(
        self,
        guarda: PuntoVentaGuardaEmisionRece,
        *,
        desde: set[str],
        hacia: str,
        cerrada_en: datetime | None,
        commit: bool,
    ) -> None:
        """Actualiza una guarda por CAS y persiste su fase durable."""
        result = await self.db.execute(
            update(PuntoVentaGuardaEmisionRece)
            .where(
                PuntoVentaGuardaEmisionRece.id == guarda.id,
                PuntoVentaGuardaEmisionRece.token == guarda.token,
                PuntoVentaGuardaEmisionRece.fase.in_(desde),
            )
            .values(fase=hacia, cerrada_en=cerrada_en)
        )
        if result.rowcount != 1:
            await self.db.rollback()
            raise ElegibilidadReceError(
                "La guarda RECE cambió de fase de forma concurrente."
            )
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
