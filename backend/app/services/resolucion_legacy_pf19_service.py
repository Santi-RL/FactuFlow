"""Resolución administrativa, explícita y auditada de candidatos legacy PF-19."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.idempotencia_fiscal import (
    IntentoEmisionFiscal,
    OperacionIdempotente,
    ResolucionLegacyPF19Journal,
)
from app.models.empresa import Empresa
from app.models.elegibilidad_rece import PuntoVentaGuardaEmisionRece
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.schemas.comprobante import EmitirComprobanteResponse
from app.schemas.lote_comprobante import (
    LoteAccionResponse,
    LoteComprobanteResponse,
    LoteProcesamientoResponse,
)
from app.services.inventario_legacy_pf19_service import (
    FiltrosInventarioLegacyPF19,
    InventarioLegacyPF19Error,
    _sanitizar_registro,
    activar_transaccion_solo_lectura,
    construir_consulta_inventario,
)


ACCION_CIERRE_LEGACY_PF19 = "cerrar_legacy_sin_autorizacion_verificada"
CATEGORIA_CIERRE_LEGACY_PF19 = "legacy_sin_autorizacion_verificada"
CONFIRMACION_APPLY_LEGACY_PF19 = "APLICAR_CIERRE_LEGACY_PF19"
ESTADOS_TERMINALES_LOTE_HIJO = frozenset(
    {"autorizado", "autorizado_externo", "fallido", "descartado", "con_error"}
)
ESTADOS_TERMINALES_INTENTO = frozenset(
    {"autorizado", "fallido_verificado", "rechazado_arca"}
)
ESTADOS_TERMINALES_GUARDA = frozenset({"cerrada_pre_arca", "cerrada_terminal"})


class ResolucionLegacyPF19Error(RuntimeError):
    """Error funcional, sanitizado y fail-closed de la resolución legacy."""


class PlanLegacyPF19(BaseModel):
    """Plan inmutable y sanitizado para cerrar un solo intento legacy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version_plan: Literal[1] = 1
    accion: Literal["cerrar_legacy_sin_autorizacion_verificada"]
    intento_id: int
    empresa_id: int
    punto_venta: int
    tipo_comprobante: int
    numero_planificado: int
    ambientes_consultados: tuple[Literal["homologacion", "produccion"], ...]
    estado_intento: str
    categoria_error: str
    version_intento: str
    precondiciones: dict[str, str | int | bool]
    plan_sha256: str


class SolicitudPlanLegacyPF19(BaseModel):
    """Identidad explícita necesaria para planificar un único candidato."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intento_id: int = Field(strict=True, gt=0)
    empresa_id: int = Field(strict=True, gt=0)
    punto_venta: int = Field(strict=True, gt=0, le=99999)
    tipo_comprobante: int = Field(strict=True, gt=0)


class BackupLegacyPF19(BaseModel):
    """Metadatos mínimos de un backup externo ya verificado por administración."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identificador: str = Field(min_length=1, max_length=128)
    timestamp: str = Field(min_length=1, max_length=64)
    proposito: str = Field(min_length=1, max_length=128)
    referencia_codigo: str = Field(min_length=1, max_length=128)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("identificador", "referencia_codigo")
    @classmethod
    def validar_texto_sanitizado(cls, valor: str) -> str:
        """Normaliza metadatos y rechaza rutas, URIs, DSN o credenciales."""
        limpio = valor.strip()
        terminos_prohibidos = re.compile(
            r"\b(?:password|passwd|clave|secret|token|dsn|user|usuario|"
            r"credential|credencial|host|localhost|database|postgresql|sqlite|"
            r"mysql|admin|server|servidor|port|puerto)\b",
            re.IGNORECASE,
        )
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", limpio)
            or terminos_prohibidos.search(limpio)
            or re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", limpio)
        ):
            raise ValueError("metadato de backup no permitido")
        return limpio

    @field_validator("proposito")
    @classmethod
    def validar_proposito(cls, valor: str) -> str:
        """Acepta únicamente el propósito administrativo fijo de este corte."""
        limpio = valor.strip().lower()
        if limpio != "cierre legacy pf19c":
            raise ValueError("propósito de backup no permitido")
        return limpio

    @field_validator("timestamp")
    @classmethod
    def validar_timestamp_utc(cls, valor: str) -> str:
        """Exige un timestamp ISO 8601 con zona UTC explícita."""
        limpio = valor.strip()
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z",
            limpio,
        ):
            raise ValueError("timestamp de backup debe usar ISO 8601 UTC estricto")
        try:
            parsed = datetime.fromisoformat(limpio[:-1] + "+00:00")
        except ValueError as exc:
            raise ValueError("timestamp de backup inválido") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(
            parsed
        ):
            raise ValueError("timestamp de backup debe estar en UTC")
        return limpio


class SolicitudApplyLegacyPF19(BaseModel):
    """Confirmaciones explícitas exigidas para aplicar un plan legacy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan: PlanLegacyPF19
    actor_usuario_id: int = Field(strict=True, gt=0)
    confirmacion: Literal["APLICAR_CIERRE_LEGACY_PF19"]
    ventana_mantenimiento_confirmada: Literal[True]
    backup: BackupLegacyPF19


@dataclass(frozen=True)
class ConsultaComprobanteLegacyPF19:
    """Resultado sanitizado de FECompConsultar para la decisión legacy."""

    existe: bool
    autorizado: bool
    identidad_exacta: bool

    def __post_init__(self) -> None:
        """Rechaza truthy/falsy ambiguos en la frontera externa."""
        if any(
            valor.__class__ is not bool
            for valor in (self.existe, self.autorizado, self.identidad_exacta)
        ):
            raise ResolucionLegacyPF19Error(
                "ARCA devolvió flags de consulta inválidos; no se aplicó el cierre"
            )


class ConsultasArcaLegacyPF19(Protocol):
    """Puerto mínimo de consultas ARCA de solo lectura para el cierre legacy."""

    async def ultimo_autorizado(
        self,
        ambiente: Literal["homologacion", "produccion"],
        punto_venta: int,
        tipo_comprobante: int,
    ) -> int:
        """Devuelve el último número autorizado por ARCA."""

    async def consultar(
        self,
        ambiente: Literal["homologacion", "produccion"],
        punto_venta: int,
        tipo_comprobante: int,
        numero: int,
    ) -> ConsultaComprobanteLegacyPF19:
        """Consulta un comprobante exacto sin solicitar CAE."""


class AdaptadorWSFELegacyPF19:
    """Adapta WSFEv1 a la vista mínima y sanitizada requerida por PF-19C."""

    def __init__(self, clientes_wsfe: dict[str, object]):
        self._clientes_wsfe = dict(clientes_wsfe)

    async def ultimo_autorizado(
        self,
        ambiente: Literal["homologacion", "produccion"],
        punto_venta: int,
        tipo_comprobante: int,
    ) -> int:
        """Consulta el último autorizado sin exponer credenciales ni payloads."""
        cliente_wsfe = self._clientes_wsfe.get(ambiente)
        if cliente_wsfe is None:
            raise ResolucionLegacyPF19Error(
                "No hay cliente ARCA para el ambiente requerido; no se aplicó el cierre"
            )
        resultado = await cliente_wsfe.fe_comp_ultimo_autorizado(
            punto_venta,
            tipo_comprobante,
        )
        if resultado.__class__ is not int or resultado < 0:
            raise ResolucionLegacyPF19Error(
                "ARCA devolvió un último autorizado inválido; no se aplicó el cierre"
            )
        return resultado

    async def consultar(
        self,
        ambiente: Literal["homologacion", "produccion"],
        punto_venta: int,
        tipo_comprobante: int,
        numero: int,
    ) -> ConsultaComprobanteLegacyPF19:
        """Reduce una respuesta exacta a existencia/autorización/identidad."""
        cliente_wsfe = self._clientes_wsfe.get(ambiente)
        if cliente_wsfe is None:
            raise ResolucionLegacyPF19Error(
                "No hay cliente ARCA para el ambiente requerido; no se aplicó el cierre"
            )
        respuesta = await cliente_wsfe.fe_comp_consultar(
            punto_venta,
            tipo_comprobante,
            numero,
        )

        identidad_exacta = (
            respuesta.punto_venta == punto_venta
            and respuesta.tipo_cbte == tipo_comprobante
            and respuesta.numero == numero
        )
        return ConsultaComprobanteLegacyPF19(
            existe=True,
            autorizado=bool(respuesta.resultado == "A"),
            identidad_exacta=identidad_exacta,
        )


class AdaptadorWSFEDiferidoLegacyPF19(AdaptadorWSFELegacyPF19):
    """Crea clientes WSFE recién después de locks y revalidación del plan."""

    def __init__(self, crear_cliente: Callable[[str], Awaitable[object]]):
        super().__init__({})
        self._crear_cliente = crear_cliente

    async def _cliente(self, ambiente: str) -> object:
        cliente = self._clientes_wsfe.get(ambiente)
        if cliente is None:
            cliente = await self._crear_cliente(ambiente)
            self._clientes_wsfe[ambiente] = cliente
        return cliente

    async def ultimo_autorizado(
        self,
        ambiente: Literal["homologacion", "produccion"],
        punto_venta: int,
        tipo_comprobante: int,
    ) -> int:
        """Obtiene el cliente requerido solo al iniciar la consulta segura."""
        await self._cliente(ambiente)
        return await super().ultimo_autorizado(ambiente, punto_venta, tipo_comprobante)

    async def consultar(
        self,
        ambiente: Literal["homologacion", "produccion"],
        punto_venta: int,
        tipo_comprobante: int,
        numero: int,
    ) -> ConsultaComprobanteLegacyPF19:
        """Obtiene el cliente requerido solo para la consulta exacta necesaria."""
        await self._cliente(ambiente)
        return await super().consultar(ambiente, punto_venta, tipo_comprobante, numero)


def _version_intento(intento: IntentoEmisionFiscal) -> str:
    """Serializa una versión estable sin incorporar datos fiscales sensibles."""
    updated_at = intento.updated_at
    if updated_at is None:
        return "sin_updated_at"
    return updated_at.isoformat(timespec="microseconds")


def _sha256_plan(contenido: dict[str, object]) -> str:
    """Calcula la huella determinista del contenido sanitizado del plan."""
    serializado = json.dumps(
        contenido,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _validar_sha_plan_recibido(plan: PlanLegacyPF19) -> None:
    """Autentica todo el contenido del plan antes de tomar locks o usar factories."""
    contenido = plan.model_dump(exclude={"plan_sha256"}, mode="python")
    if _sha256_plan(contenido) != plan.plan_sha256:
        raise ResolucionLegacyPF19Error(
            "El contenido del plan legacy no coincide con su SHA-256"
        )


def _validar_backup_recibido(backup: BackupLegacyPF19) -> BackupLegacyPF19:
    """Revalida metadatos de backup aun si el objeto llegó por una frontera interna."""
    try:
        return BackupLegacyPF19.model_validate(backup.model_dump(mode="python"))
    except (AttributeError, ValidationError) as exc:
        raise ResolucionLegacyPF19Error(
            "Los metadatos del backup legacy no son válidos ni sanitizados"
        ) from exc


def _huella_json(valor: object) -> str:
    """Calcula una huella canónica sin exponer la respuesta legacy."""
    try:
        serializado = json.dumps(
            valor, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
    except (TypeError, ValueError) as exc:
        raise ResolucionLegacyPF19Error(
            "La respuesta legacy no tiene una forma canónica reconstruible"
        ) from exc
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _serializar_snapshot(registros: list[dict[str, object]]) -> tuple[str, str]:
    """Serializa una lista de precondiciones con orden y huella canónicos."""
    serializado = json.dumps(registros, separators=(",", ":"), sort_keys=True)
    return serializado, hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _leer_snapshot_plan(
    plan: PlanLegacyPF19,
    nombre: str,
) -> list[dict[str, object]]:
    """Lee y autentica una lista de snapshot incluida en el digest del plan."""
    try:
        serializado = plan.precondiciones[f"{nombre}_snapshot"]
        esperado_sha = plan.precondiciones[f"{nombre}_sha256"]
        esperado_cantidad = plan.precondiciones[f"{nombre}_cantidad"]
        if not isinstance(serializado, str) or not isinstance(esperado_sha, str):
            raise TypeError
        registros = json.loads(serializado)
        if not isinstance(registros, list) or any(
            not isinstance(registro, dict) for registro in registros
        ):
            raise TypeError
        canonico, sha = _serializar_snapshot(registros)
        if (
            canonico != serializado
            or sha != esperado_sha
            or len(registros) != esperado_cantidad
        ):
            raise ValueError
        return registros
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ResolucionLegacyPF19Error(
            f"El plan legacy no conserva el snapshot {nombre} exacto"
        ) from exc


def _snapshot_intento(intento: IntentoEmisionFiscal) -> dict[str, object]:
    """Versiona identidad, relaciones y evidencia fiscal de un intento."""
    return {
        "id": intento.id,
        "empresa_id": intento.empresa_id,
        "punto_venta_id": intento.punto_venta_id,
        "punto_venta_numero": intento.punto_venta_numero,
        "tipo_comprobante": intento.tipo_comprobante,
        "numero_planificado": intento.numero_planificado or 0,
        "fecha_emision": intento.fecha_emision.isoformat(),
        "total": str(intento.total),
        "estado": intento.estado,
        "version": _version_intento(intento),
        "operacion_id": intento.operacion_id or 0,
        "lote_id": intento.lote_id or 0,
        "grupo_id": intento.grupo_id or 0,
        "guarda_rece_id": intento.guarda_rece_id or 0,
        "ambiente": intento.ambiente or "legacy_null",
        "cae_ausente": intento.cae is None,
        "comprobante_ausente": intento.comprobante_id is None,
        "errores_arca_ausentes": intento.errores_arca_json is None,
    }


def _snapshot_grupo(grupo: LoteComprobanteGrupo) -> dict[str, object]:
    """Versiona identidad y evidencia fiscal de un grupo batch."""
    return {
        "id": grupo.id,
        "empresa_id": grupo.empresa_id,
        "lote_id": grupo.lote_id,
        "estado": grupo.estado,
        "version": _version_intento(grupo),
        "tipo_comprobante": grupo.tipo_comprobante or 0,
        "punto_venta_numero": grupo.punto_venta_numero or 0,
        "punto_venta_id": grupo.punto_venta_id or 0,
        "ambiente": grupo.ambiente or "legacy_null",
        "numero_asignado": grupo.numero_asignado or 0,
        "cae_ausente": grupo.cae is None,
        "comprobante_ausente": grupo.comprobante_id is None,
    }


def _snapshot_fila(fila: LoteComprobanteFila) -> dict[str, object]:
    """Versiona contenido mutable de una fila que no posee updated_at."""
    contenido: dict[str, object] = {
        "id": fila.id,
        "lote_id": fila.lote_id,
        "grupo_id": fila.grupo_id,
        "estado": fila.estado,
        "created_at": fila.created_at.isoformat(timespec="microseconds"),
        "datos_sha256": _huella_json(fila.datos_json),
        "mensajes_sha256": _huella_json(fila.mensajes_json),
    }
    contenido["version"] = _huella_json(contenido)
    return contenido


def _snapshot_guarda(guarda: PuntoVentaGuardaEmisionRece) -> dict[str, object]:
    """Versiona identidad y fase de una guarda asociada a la operación."""
    return {
        "id": guarda.id,
        "operacion_id": guarda.operacion_id,
        "empresa_id": guarda.empresa_id,
        "punto_venta_id": guarda.punto_venta_id,
        "ambiente": guarda.ambiente,
        "fase": guarda.fase,
        "version": _version_intento(guarda),
    }


async def _registro_candidato(
    session: AsyncSession,
    solicitud: SolicitudPlanLegacyPF19,
) -> tuple[IntentoEmisionFiscal, dict[str, object]]:
    """Carga el intento y exige la clasificación candidata del inventario PF-19A."""
    intento = await session.get(IntentoEmisionFiscal, solicitud.intento_id)
    if intento is None:
        raise ResolucionLegacyPF19Error("El intento legacy indicado no existe")
    if (
        intento.empresa_id != solicitud.empresa_id
        or intento.punto_venta_numero != solicitud.punto_venta
        or intento.tipo_comprobante != solicitud.tipo_comprobante
    ):
        raise ResolucionLegacyPF19Error(
            "La identidad explícita no coincide con el intento legacy"
        )

    filtros = FiltrosInventarioLegacyPF19(
        ambiente_runtime="produccion",
        empresa_id=solicitud.empresa_id,
        punto_venta=solicitud.punto_venta,
        tipo_comprobante=solicitud.tipo_comprobante,
    )
    resultado = await session.execute(
        construir_consulta_inventario(filtros).where(
            IntentoEmisionFiscal.id == solicitud.intento_id
        )
    )
    fila = resultado.mappings().one_or_none()
    if fila is None:
        raise ResolucionLegacyPF19Error(
            "El intento no pertenece al inventario candidato de PF-19"
        )
    registro = _sanitizar_registro(fila)
    if registro["clasificacion_inventario"] != "candidato_10005_no_confirmado":
        raise ResolucionLegacyPF19Error(
            "El intento legacy no cumple las precondiciones de candidato"
        )
    return intento, registro


async def _validar_sin_siblings_inciertos(
    session: AsyncSession,
    intento: IntentoEmisionFiscal,
) -> None:
    """Impide cerrar una reserva cuando coexiste otra incertidumbre de la tupla."""
    resultado = await session.execute(
        select(IntentoEmisionFiscal.id)
        .where(
            IntentoEmisionFiscal.empresa_id == intento.empresa_id,
            IntentoEmisionFiscal.punto_venta_id == intento.punto_venta_id,
            IntentoEmisionFiscal.tipo_comprobante == intento.tipo_comprobante,
            IntentoEmisionFiscal.numero_planificado == intento.numero_planificado,
            IntentoEmisionFiscal.id != intento.id,
            IntentoEmisionFiscal.estado.in_(("en_proceso", "requiere_reconciliacion")),
        )
        .order_by(IntentoEmisionFiscal.id)
    )
    if resultado.scalars().first() is not None:
        raise ResolucionLegacyPF19Error(
            "Existen reservas sibling inciertas para la misma tupla fiscal"
        )


async def _inventariar_forma_grafo(
    session: AsyncSession,
    intento: IntentoEmisionFiscal,
    operacion: OperacionIdempotente,
) -> dict[str, str | int | bool]:
    """Valida forma exacta y devuelve un snapshot canónico del grafo mutable."""
    intentos_operacion = (
        (
            await session.execute(
                select(IntentoEmisionFiscal)
                .where(IntentoEmisionFiscal.operacion_id == operacion.id)
                .order_by(IntentoEmisionFiscal.id)
            )
        )
        .scalars()
        .all()
    )
    if not any(item.id == intento.id for item in intentos_operacion):
        raise ResolucionLegacyPF19Error(
            "La operación legacy ya no contiene el intento planificado"
        )
    snapshot_intentos = [_snapshot_intento(item) for item in intentos_operacion]
    intentos_json, intentos_sha = _serializar_snapshot(snapshot_intentos)
    if operacion.tipo_operacion == "emitir_comprobante":
        if [item.id for item in intentos_operacion] != [intento.id]:
            raise ResolucionLegacyPF19Error(
                "La operación individual legacy no pertenece exclusivamente al intento"
            )
        if any(
            valor is not None
            for valor in (operacion.lote_id, intento.lote_id, intento.grupo_id)
        ):
            raise ResolucionLegacyPF19Error(
                "La operación individual legacy tiene forma de lote inconsistente"
            )
        return {
            "forma_grafo": "individual",
            "intentos_cantidad": 1,
            "intentos_snapshot": intentos_json,
            "intentos_sha256": intentos_sha,
        }

    intentos_relevantes = (
        (
            await session.execute(
                select(IntentoEmisionFiscal)
                .where(
                    (IntentoEmisionFiscal.operacion_id == operacion.id)
                    | (IntentoEmisionFiscal.grupo_id == intento.grupo_id)
                )
                .order_by(IntentoEmisionFiscal.id)
            )
        )
        .scalars()
        .all()
    )
    otros_intentos = [item for item in intentos_relevantes if item.id != intento.id]
    if any(item.estado not in ESTADOS_TERMINALES_INTENTO for item in otros_intentos):
        raise ResolucionLegacyPF19Error(
            "La operación batch conserva otros intentos no terminales"
        )
    snapshot_intentos = [_snapshot_intento(item) for item in intentos_relevantes]
    intentos_json, intentos_sha = _serializar_snapshot(snapshot_intentos)

    if (
        operacion.lote_id is None
        or intento.lote_id is None
        or intento.grupo_id is None
        or operacion.lote_id != intento.lote_id
    ):
        raise ResolucionLegacyPF19Error(
            "La operación batch legacy no conserva lote y grupo exactos"
        )
    lote = await session.get(LoteComprobante, intento.lote_id)
    grupo = await session.get(LoteComprobanteGrupo, intento.grupo_id)
    if (
        lote is None
        or grupo is None
        or lote.empresa_id != intento.empresa_id
        or grupo.empresa_id != intento.empresa_id
        or grupo.lote_id != lote.id
        or grupo.estado != "requiere_reconciliacion"
        or lote.estado != "requiere_reconciliacion"
    ):
        raise ResolucionLegacyPF19Error(
            "El lote o grupo legacy no conserva el estado incierto esperado"
        )
    grupos = (
        (
            await session.execute(
                select(LoteComprobanteGrupo)
                .where(LoteComprobanteGrupo.lote_id == lote.id)
                .order_by(LoteComprobanteGrupo.id)
            )
        )
        .scalars()
        .all()
    )
    if any(
        item.id != grupo.id and item.estado not in ESTADOS_TERMINALES_LOTE_HIJO
        for item in grupos
    ):
        raise ResolucionLegacyPF19Error(
            "El lote conserva otros grupos no terminales y no puede cerrarse"
        )
    filas = (
        (
            await session.execute(
                select(LoteComprobanteFila)
                .where(LoteComprobanteFila.lote_id == lote.id)
                .order_by(LoteComprobanteFila.id)
            )
        )
        .scalars()
        .all()
    )
    filas_objetivo = [fila for fila in filas if fila.grupo_id == grupo.id]
    grupos_ids = {item.id for item in grupos}
    if any(
        fila.lote_id != lote.id or fila.grupo_id not in grupos_ids for fila in filas
    ):
        raise ResolucionLegacyPF19Error(
            "El lote conserva filas asociadas a un grupo ajeno"
        )
    if not filas_objetivo or any(
        fila.estado != "requiere_reconciliacion" for fila in filas_objetivo
    ):
        raise ResolucionLegacyPF19Error(
            "Las filas legacy no conservan el estado incierto esperado"
        )
    if any(
        fila.grupo_id != grupo.id and fila.estado not in ESTADOS_TERMINALES_LOTE_HIJO
        for fila in filas
    ):
        raise ResolucionLegacyPF19Error(
            "El lote conserva otras filas no terminales y no puede cerrarse"
        )
    if grupo.cae is not None or grupo.comprobante_id is not None:
        raise ResolucionLegacyPF19Error(
            "El grupo objetivo ya conserva autorización o comprobante"
        )
    grupos_json, grupos_sha = _serializar_snapshot(
        [_snapshot_grupo(item) for item in grupos]
    )
    filas_json, filas_sha = _serializar_snapshot(
        [_snapshot_fila(fila) for fila in filas]
    )
    return {
        "forma_grafo": "batch",
        "intentos_cantidad": len(intentos_relevantes),
        "intentos_snapshot": intentos_json,
        "intentos_sha256": intentos_sha,
        "lote_id": lote.id,
        "lote_empresa_id": lote.empresa_id,
        "lote_estado": lote.estado,
        "lote_version": _version_intento(lote),
        "grupo_id": grupo.id,
        "grupo_estado": grupo.estado,
        "grupo_version": _version_intento(grupo),
        "grupos_cantidad": len(grupos),
        "grupos_snapshot": grupos_json,
        "grupos_sha256": grupos_sha,
        "filas_cantidad": len(filas),
        "filas_objetivo_cantidad": len(filas_objetivo),
        "filas_snapshot": filas_json,
        "filas_sha256": filas_sha,
    }


async def _inventariar_guarda_legacy(
    session: AsyncSession,
    intento: IntentoEmisionFiscal,
    operacion: OperacionIdempotente,
) -> dict[str, str | int | bool]:
    """Valida y versiona la guarda RECE opcional asociada a la operación."""
    guardas = (
        (
            await session.execute(
                select(PuntoVentaGuardaEmisionRece)
                .where(PuntoVentaGuardaEmisionRece.operacion_id == operacion.id)
                .order_by(PuntoVentaGuardaEmisionRece.id)
            )
        )
        .scalars()
        .all()
    )
    guarda_objetivo = next(
        (guarda for guarda in guardas if guarda.id == intento.guarda_rece_id),
        None,
    )
    otras_guardas = [guarda for guarda in guardas if guarda is not guarda_objetivo]
    if any(guarda.fase not in ESTADOS_TERMINALES_GUARDA for guarda in otras_guardas):
        raise ResolucionLegacyPF19Error(
            "La operación legacy conserva otra guarda RECE no terminal"
        )
    if intento.guarda_rece_id is not None:
        if (
            guarda_objetivo is None
            or guarda_objetivo.empresa_id != intento.empresa_id
            or guarda_objetivo.punto_venta_id != intento.punto_venta_id
            or guarda_objetivo.fase not in {"arca_iniciada", "requiere_reconciliacion"}
            or intento.ambiente != guarda_objetivo.ambiente
        ):
            raise ResolucionLegacyPF19Error(
                "La guarda RECE legacy no conserva el estado incierto esperado"
            )
    guardas_json, guardas_sha = _serializar_snapshot(
        [_snapshot_guarda(guarda) for guarda in guardas]
    )
    resultado: dict[str, str | int | bool] = {
        "guarda_presente": guarda_objetivo is not None,
        "guardas_cantidad": len(guardas),
        "guardas_snapshot": guardas_json,
        "guardas_sha256": guardas_sha,
    }
    if guarda_objetivo is not None:
        resultado.update(
            {
                "guarda_id": guarda_objetivo.id,
                "guarda_fase": guarda_objetivo.fase,
                "guarda_ambiente": guarda_objetivo.ambiente,
                "guarda_version": _version_intento(guarda_objetivo),
            }
        )
    return resultado


async def _construir_plan_desde_sesion(
    session: AsyncSession,
    solicitud: SolicitudPlanLegacyPF19,
) -> PlanLegacyPF19:
    """Construye el plan sin efectos laterales a partir del estado actual."""
    intento, registro = await _registro_candidato(session, solicitud)
    await _validar_sin_siblings_inciertos(session, intento)
    if intento.numero_planificado is None:
        raise ResolucionLegacyPF19Error(
            "El candidato legacy no tiene número planificado"
        )
    if intento.numero_planificado <= 0 or intento.total < 0:
        raise ResolucionLegacyPF19Error(
            "El candidato legacy no conserva número o total reconstruibles"
        )
    if intento.cae is not None or intento.comprobante_id is not None:
        raise ResolucionLegacyPF19Error(
            "El candidato legacy ya conserva autorización o comprobante"
        )
    operacion = (
        await session.get(OperacionIdempotente, intento.operacion_id)
        if intento.operacion_id is not None
        else None
    )
    if (
        operacion is None
        or operacion.empresa_id != intento.empresa_id
        or operacion.estado != "requiere_reconciliacion"
        or operacion.tipo_operacion
        not in {"emitir_comprobante", "procesar_lote", "reintentar_fallidos_lote"}
    ):
        raise ResolucionLegacyPF19Error(
            "La operación legacy no conserva un contrato de replay cerrable"
        )
    snapshot_grafo = await _inventariar_forma_grafo(session, intento, operacion)
    snapshot_guarda = await _inventariar_guarda_legacy(session, intento, operacion)

    referencias = registro["referencias"]
    if not isinstance(referencias, dict) or any(
        estado not in {"valida", "no_aplica", "no_evaluable"}
        for estado in referencias.values()
    ):
        raise ResolucionLegacyPF19Error(
            "No puede reconstruirse el alcance histórico del candidato legacy"
        )
    precondiciones: dict[str, str | int | bool] = {
        "clasificacion_inventario": "candidato_10005_no_confirmado",
        "sin_cae": True,
        "sin_comprobante": True,
        "sin_siblings_inciertos": True,
        "referencias_reconstruibles": True,
        "estado_requerido": "requiere_reconciliacion",
        "categoria_requerida": str(intento.categoria_error),
        "version_intento": _version_intento(intento),
    }
    precondiciones.update(snapshot_grafo)
    precondiciones.update(snapshot_guarda)
    precondiciones.update(
        {
            "operacion_id": operacion.id,
            "operacion_tipo": operacion.tipo_operacion,
            "operacion_estado": operacion.estado,
            "operacion_lote_id": operacion.lote_id or 0,
            "operacion_version": _version_intento(operacion),
            "operacion_response_sha256": _huella_json(operacion.response_json),
        }
    )
    contenido: dict[str, object] = {
        "version_plan": 1,
        "accion": ACCION_CIERRE_LEGACY_PF19,
        "intento_id": intento.id,
        "empresa_id": intento.empresa_id,
        "punto_venta": intento.punto_venta_numero,
        "tipo_comprobante": intento.tipo_comprobante,
        "numero_planificado": intento.numero_planificado,
        "ambientes_consultados": _ambientes_para_intento(intento),
        "estado_intento": intento.estado,
        "categoria_error": intento.categoria_error,
        "version_intento": _version_intento(intento),
        "precondiciones": precondiciones,
    }
    return PlanLegacyPF19(**contenido, plan_sha256=_sha256_plan(contenido))


def _ambientes_para_intento(
    intento: IntentoEmisionFiscal,
) -> tuple[Literal["homologacion", "produccion"], ...]:
    """Fija ambientes por evidencia durable, sin aceptar elección del operador."""
    if intento.ambiente in {"homologacion", "produccion"}:
        return (intento.ambiente,)
    return ("homologacion", "produccion")


async def planificar_resolucion_legacy_pf19(
    engine: AsyncEngine,
    solicitud: SolicitudPlanLegacyPF19,
) -> PlanLegacyPF19:
    """Genera un plan read-only y siempre revierte antes de devolverlo."""
    async with engine.connect() as connection:
        dialecto = connection.dialect.name
        transaccion = await connection.begin()
        sqlite_query_only_anterior: int | None = None
        try:
            if dialecto == "sqlite":
                sqlite_query_only_anterior = int(
                    (await connection.execute(text("PRAGMA query_only"))).scalar_one()
                )
            await activar_transaccion_solo_lectura(connection)
            session = AsyncSession(bind=connection, expire_on_commit=False)
            try:
                return await _construir_plan_desde_sesion(session, solicitud)
            finally:
                await session.close()
        except InventarioLegacyPF19Error as exc:
            raise ResolucionLegacyPF19Error(str(exc)) from exc
        finally:
            await transaccion.rollback()
            if dialecto == "sqlite" and sqlite_query_only_anterior is not None:
                await connection.execute(
                    text(f"PRAGMA query_only = {sqlite_query_only_anterior}")
                )
                restaurado = int(
                    (await connection.execute(text("PRAGMA query_only"))).scalar_one()
                )
                if restaurado != sqlite_query_only_anterior:
                    raise ResolucionLegacyPF19Error(
                        "SQLite no pudo restaurar query_only después del plan"
                    )
                await connection.rollback()


def _clave_lock(plan: PlanLegacyPF19) -> int:
    """Deriva una llave advisory estable para una tupla fiscal concreta."""
    valor = (
        f"pf19c:{plan.empresa_id}:{plan.punto_venta}:"
        f"{plan.tipo_comprobante}:{plan.numero_planificado}"
    )
    return int.from_bytes(
        hashlib.sha256(valor.encode("ascii")).digest()[:8],
        byteorder="big",
        signed=True,
    )


async def _adquirir_locks(
    session: AsyncSession,
    plan: PlanLegacyPF19,
    actor_usuario_id: int,
) -> None:
    """Toma locks en orden estable antes de cualquier consulta externa."""
    conexion = await session.connection()
    if conexion.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:clave)").bindparams(
                clave=_clave_lock(plan)
            )
        )

    # Esta lectura solo identifica el grafo. Los locks y la revalidación posterior
    # son los que habilitan el cierre; no se decide nada con este snapshot.
    referencias = (
        (
            await session.execute(
                select(
                    IntentoEmisionFiscal.operacion_id,
                    IntentoEmisionFiscal.lote_id,
                    IntentoEmisionFiscal.grupo_id,
                    IntentoEmisionFiscal.guarda_rece_id,
                    IntentoEmisionFiscal.punto_venta_id,
                ).where(IntentoEmisionFiscal.id == plan.intento_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if referencias is None:
        raise ResolucionLegacyPF19Error("El intento legacy ya no existe")
    await _exigir_actor_admin(session, actor_usuario_id, plan.empresa_id)
    await session.execute(
        select(Empresa.id).where(Empresa.id == plan.empresa_id).with_for_update()
    )
    punto = (
        await session.execute(
            select(PuntoVenta.id)
            .where(
                PuntoVenta.id == referencias["punto_venta_id"],
                PuntoVenta.empresa_id == plan.empresa_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if punto is None:
        raise ResolucionLegacyPF19Error("El punto de venta del intento no es coherente")
    if referencias["operacion_id"] is not None:
        await session.execute(
            select(OperacionIdempotente.id)
            .where(OperacionIdempotente.id == referencias["operacion_id"])
            .with_for_update()
        )
        condicion_intentos = (
            IntentoEmisionFiscal.operacion_id == referencias["operacion_id"]
        )
        if referencias["grupo_id"] is not None:
            condicion_intentos = condicion_intentos | (
                IntentoEmisionFiscal.grupo_id == referencias["grupo_id"]
            )
        intentos_bloqueados = (
            (
                await session.execute(
                    select(IntentoEmisionFiscal.id)
                    .where(condicion_intentos)
                    .order_by(IntentoEmisionFiscal.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if plan.intento_id not in intentos_bloqueados:
            raise ResolucionLegacyPF19Error(
                "El intento cambió de operación durante la adquisición de locks"
            )
        await session.execute(
            select(PuntoVentaGuardaEmisionRece.id)
            .where(
                PuntoVentaGuardaEmisionRece.operacion_id == referencias["operacion_id"]
            )
            .order_by(PuntoVentaGuardaEmisionRece.id)
            .with_for_update()
        )
    if referencias["lote_id"] is not None:
        await session.execute(
            select(LoteComprobante.id)
            .where(LoteComprobante.id == referencias["lote_id"])
            .with_for_update()
        )
        await session.execute(
            select(LoteComprobanteGrupo.id)
            .where(LoteComprobanteGrupo.lote_id == referencias["lote_id"])
            .order_by(LoteComprobanteGrupo.id)
            .with_for_update()
        )
        await session.execute(
            select(LoteComprobanteFila.id)
            .where(LoteComprobanteFila.lote_id == referencias["lote_id"])
            .order_by(LoteComprobanteFila.id)
            .with_for_update()
        )


async def _exigir_actor_admin(
    session: AsyncSession,
    actor_usuario_id: int,
    empresa_id: int,
) -> None:
    """Bloquea y revalida administración activa del mismo emisor."""
    actor = (
        await session.execute(
            select(Usuario).where(Usuario.id == actor_usuario_id).with_for_update()
        )
    ).scalar_one_or_none()
    if (
        actor is None
        or not actor.activo
        or not actor.es_admin
        or actor.empresa_id != empresa_id
    ):
        raise ResolucionLegacyPF19Error(
            "Solo un administrador activo del mismo emisor puede aplicar el cierre legacy"
        )


async def _plan_revalidado(
    session: AsyncSession,
    plan: PlanLegacyPF19,
) -> PlanLegacyPF19:
    """Recalcula el plan bloqueado y aborta si cualquier precondición cambió."""
    solicitud = SolicitudPlanLegacyPF19(
        intento_id=plan.intento_id,
        empresa_id=plan.empresa_id,
        punto_venta=plan.punto_venta,
        tipo_comprobante=plan.tipo_comprobante,
    )
    recalculado = await _construir_plan_desde_sesion(session, solicitud)
    if recalculado.plan_sha256 != plan.plan_sha256:
        raise ResolucionLegacyPF19Error(
            "El plan legacy cambió desde su revisión; generá uno nuevo"
        )
    return recalculado


def _respuesta_individual_terminal(
    intento: IntentoEmisionFiscal,
) -> EmitirComprobanteResponse:
    """Reconstruye el DTO individual únicamente desde campos fiscales durables."""
    if intento.numero_planificado is None or intento.numero_planificado <= 0:
        raise ResolucionLegacyPF19Error(
            "El intento individual no conserva un número reconstruible"
        )
    if intento.total < 0:
        raise ResolucionLegacyPF19Error(
            "El intento individual no conserva un total reconstruible"
        )
    return EmitirComprobanteResponse(
        exito=False,
        comprobante_id=None,
        tipo_comprobante=intento.tipo_comprobante,
        punto_venta=intento.punto_venta_numero,
        numero=intento.numero_planificado,
        fecha=intento.fecha_emision,
        cae=None,
        cae_vencimiento=None,
        total=intento.total,
        mensaje="Cierre legacy por ausencia de autorización verificada",
        errores=[],
        errores_arca=[],
        requiere_reconciliacion=False,
        categoria_error=CATEGORIA_CIERRE_LEGACY_PF19,
    )


def _respuesta_lote_terminal(
    lote: LoteComprobante,
    tipo_operacion: str,
) -> LoteProcesamientoResponse | LoteAccionResponse:
    """Reconstruye el envelope exacto de replay para la acción batch original."""
    lote_respuesta = LoteComprobanteResponse.model_validate(lote, from_attributes=True)
    if tipo_operacion == "procesar_lote":
        return LoteProcesamientoResponse(
            lote=lote_respuesta,
            mensaje="Cierre legacy por ausencia de autorización verificada",
            en_progreso=False,
        )
    if tipo_operacion == "reintentar_fallidos_lote":
        return LoteAccionResponse(
            lote=lote_respuesta,
            mensaje="Cierre legacy por ausencia de autorización verificada",
        )
    raise ResolucionLegacyPF19Error(
        "El tipo de operación legacy no tiene un contrato batch reconstruible"
    )


def _sin_claves(registro: dict[str, object], *claves: str) -> dict[str, object]:
    """Devuelve una copia sin los campos que el cierre muta deliberadamente."""
    return {clave: valor for clave, valor in registro.items() if clave not in claves}


async def _validar_intentos_replay(
    session: AsyncSession,
    plan: PlanLegacyPF19,
    intento: IntentoEmisionFiscal,
    operacion: OperacionIdempotente,
) -> None:
    """Revalida identidad y cardinalidad de intentos contra el snapshot original."""
    snapshots = _leer_snapshot_plan(plan, "intentos")
    condicion = IntentoEmisionFiscal.operacion_id == operacion.id
    if intento.grupo_id is not None:
        condicion = condicion | (IntentoEmisionFiscal.grupo_id == intento.grupo_id)
    actuales = (
        (
            await session.execute(
                select(IntentoEmisionFiscal)
                .where(condicion)
                .order_by(IntentoEmisionFiscal.id)
            )
        )
        .scalars()
        .all()
    )
    if [item.id for item in actuales] != [int(item["id"]) for item in snapshots]:
        raise ResolucionLegacyPF19Error(
            "La cardinalidad de intentos diverge del journal legacy"
        )
    por_id = {item.id: item for item in actuales}
    for snapshot in snapshots:
        actual = por_id[int(snapshot["id"])]
        actual_snapshot = _snapshot_intento(actual)
        if actual.id == intento.id:
            if (
                _sin_claves(actual_snapshot, "estado", "version")
                != _sin_claves(snapshot, "estado", "version")
                or actual.estado != "fallido_verificado"
                or actual.categoria_error != CATEGORIA_CIERRE_LEGACY_PF19
                or actual.mensaje
                != "Cierre legacy por ausencia de autorización verificada"
                or not actual_snapshot["cae_ausente"]
                or not actual_snapshot["comprobante_ausente"]
                or not actual_snapshot["errores_arca_ausentes"]
            ):
                raise ResolucionLegacyPF19Error(
                    "La identidad fiscal del intento terminal diverge del plan"
                )
        elif (
            actual_snapshot != snapshot
            or actual.estado not in ESTADOS_TERMINALES_INTENTO
        ):
            raise ResolucionLegacyPF19Error(
                "Un intento sibling terminal cambió desde el plan legacy"
            )


async def _validar_guardas_replay(
    session: AsyncSession,
    plan: PlanLegacyPF19,
    intento: IntentoEmisionFiscal,
    operacion: OperacionIdempotente,
) -> None:
    """Revalida la guarda objetivo cerrada y preserva siblings terminales exactos."""
    snapshots = _leer_snapshot_plan(plan, "guardas")
    guardas = (
        (
            await session.execute(
                select(PuntoVentaGuardaEmisionRece)
                .where(PuntoVentaGuardaEmisionRece.operacion_id == operacion.id)
                .order_by(PuntoVentaGuardaEmisionRece.id)
            )
        )
        .scalars()
        .all()
    )
    if [guarda.id for guarda in guardas] != [int(item["id"]) for item in snapshots]:
        raise ResolucionLegacyPF19Error(
            "La cardinalidad de guardas diverge del journal legacy"
        )
    por_id = {guarda.id: guarda for guarda in guardas}
    for snapshot in snapshots:
        guarda = por_id[int(snapshot["id"])]
        actual = _snapshot_guarda(guarda)
        if guarda.id == intento.guarda_rece_id:
            if (
                _sin_claves(actual, "fase", "version")
                != _sin_claves(snapshot, "fase", "version")
                or guarda.fase != "cerrada_terminal"
            ):
                raise ResolucionLegacyPF19Error(
                    "La guarda objetivo terminal diverge del journal legacy"
                )
        elif actual != snapshot or guarda.fase not in ESTADOS_TERMINALES_GUARDA:
            raise ResolucionLegacyPF19Error(
                "Una guarda sibling terminal cambió desde el plan legacy"
            )


def _validar_filas_replay(
    plan: PlanLegacyPF19,
    filas: list[LoteComprobanteFila],
    grupo_objetivo_id: int,
) -> None:
    """Revalida filas target mutadas y siblings preservadas por contenido."""
    snapshots = _leer_snapshot_plan(plan, "filas")
    if [fila.id for fila in filas] != [int(item["id"]) for item in snapshots]:
        raise ResolucionLegacyPF19Error(
            "La cardinalidad de filas diverge del journal legacy"
        )
    por_id = {fila.id: fila for fila in filas}
    for snapshot in snapshots:
        fila = por_id[int(snapshot["id"])]
        actual = _snapshot_fila(fila)
        if int(snapshot["grupo_id"]) == grupo_objetivo_id:
            if (
                _sin_claves(actual, "estado", "mensajes_sha256", "version")
                != _sin_claves(snapshot, "estado", "mensajes_sha256", "version")
                or fila.estado != "fallido"
                or fila.mensajes_json != [CATEGORIA_CIERRE_LEGACY_PF19]
            ):
                raise ResolucionLegacyPF19Error(
                    "Una fila objetivo terminal diverge del journal legacy"
                )
        elif actual != snapshot or fila.estado not in ESTADOS_TERMINALES_LOTE_HIJO:
            raise ResolucionLegacyPF19Error(
                "Una fila sibling terminal cambió desde el plan legacy"
            )


def _validar_grupos_replay(
    plan: PlanLegacyPF19,
    grupos: list[LoteComprobanteGrupo],
    grupo_objetivo_id: int,
) -> None:
    """Revalida grupo target cerrado y siblings terminales sin mutación."""
    snapshots = _leer_snapshot_plan(plan, "grupos")
    if [grupo.id for grupo in grupos] != [int(item["id"]) for item in snapshots]:
        raise ResolucionLegacyPF19Error(
            "La cardinalidad de grupos diverge del journal legacy"
        )
    por_id = {grupo.id: grupo for grupo in grupos}
    for snapshot in snapshots:
        grupo = por_id[int(snapshot["id"])]
        actual = _snapshot_grupo(grupo)
        if grupo.id == grupo_objetivo_id:
            if (
                _sin_claves(actual, "estado", "version")
                != _sin_claves(snapshot, "estado", "version")
                or grupo.estado != "fallido"
                or grupo.mensajes_json != [CATEGORIA_CIERRE_LEGACY_PF19]
                or grupo.cae is not None
                or grupo.comprobante_id is not None
            ):
                raise ResolucionLegacyPF19Error(
                    "El grupo objetivo terminal diverge del journal legacy"
                )
        elif actual != snapshot or grupo.estado not in ESTADOS_TERMINALES_LOTE_HIJO:
            raise ResolucionLegacyPF19Error(
                "Un grupo sibling terminal cambió desde el plan legacy"
            )


async def _validar_replay_journal(
    session: AsyncSession,
    plan: PlanLegacyPF19,
    journal: ResolucionLegacyPF19Journal,
) -> None:
    """Comprueba que journal, grafo y DTO terminal continúan siendo coherentes."""
    intento = await session.get(IntentoEmisionFiscal, plan.intento_id)
    ambiente_esperado = (
        plan.ambientes_consultados[0]
        if len(plan.ambientes_consultados) == 1
        else "ambos"
    )
    consultas_esperadas = {
        ambiente: "ultimo_menor_al_planificado"
        for ambiente in plan.ambientes_consultados
    }
    if (
        journal.plan_sha256 != plan.plan_sha256
        or journal.empresa_id != plan.empresa_id
        or journal.intento_id != plan.intento_id
        or journal.accion != ACCION_CIERRE_LEGACY_PF19
        or journal.resultado != CATEGORIA_CIERRE_LEGACY_PF19
        or journal.ambiente_consultado != ambiente_esperado
        or journal.resultado_consultas_json != consultas_esperadas
        or intento is None
        or intento.empresa_id != plan.empresa_id
        or intento.estado != "fallido_verificado"
        or intento.categoria_error != CATEGORIA_CIERRE_LEGACY_PF19
        or intento.operacion_id is None
    ):
        raise ResolucionLegacyPF19Error(
            "El replay legacy diverge del journal o del intento terminal"
        )
    operacion = await session.get(OperacionIdempotente, intento.operacion_id)
    if (
        operacion is None
        or operacion.empresa_id != plan.empresa_id
        or operacion.id != plan.precondiciones.get("operacion_id")
        or operacion.tipo_operacion != plan.precondiciones.get("operacion_tipo")
        or (operacion.lote_id or 0) != plan.precondiciones.get("operacion_lote_id")
        or journal.terminal_response_sha256 != _huella_json(operacion.response_json)
    ):
        raise ResolucionLegacyPF19Error(
            "El replay legacy perdió su operación o respuesta terminal exacta"
        )
    try:
        metadata_backup = dict(journal.backup_metadata_json)
        _validar_backup_recibido(
            BackupLegacyPF19(**metadata_backup, sha256=journal.backup_sha256)
        )
    except Exception as exc:
        raise ResolucionLegacyPF19Error(
            "El replay legacy no conserva metadata de backup válida"
        ) from exc
    await _validar_intentos_replay(session, plan, intento, operacion)
    await _validar_guardas_replay(session, plan, intento, operacion)
    try:
        if operacion.tipo_operacion == "emitir_comprobante":
            if (
                operacion.estado != "fallido_verificado"
                or operacion.lote_id is not None
                or intento.lote_id is not None
                or intento.grupo_id is not None
            ):
                raise ResolucionLegacyPF19Error(
                    "El replay individual legacy tiene una forma divergente"
                )
            dto = EmitirComprobanteResponse.model_validate(operacion.response_json)
            esperado = _respuesta_individual_terminal(intento)
            if dto.model_dump(mode="json") != esperado.model_dump(mode="json"):
                raise ResolucionLegacyPF19Error(
                    "El DTO individual del replay legacy no coincide con el intento"
                )
            return
        if operacion.tipo_operacion not in {
            "procesar_lote",
            "reintentar_fallidos_lote",
        }:
            raise ResolucionLegacyPF19Error(
                "El replay legacy tiene un tipo de operación desconocido"
            )
        if (
            operacion.estado != "finalizado"
            or operacion.lote_id is None
            or operacion.lote_id != intento.lote_id
            or intento.grupo_id is None
        ):
            raise ResolucionLegacyPF19Error(
                "El replay batch legacy tiene una forma divergente"
            )
        lote = await session.get(LoteComprobante, operacion.lote_id)
        grupos = (
            (
                await session.execute(
                    select(LoteComprobanteGrupo)
                    .where(LoteComprobanteGrupo.lote_id == operacion.lote_id)
                    .order_by(LoteComprobanteGrupo.id)
                )
            )
            .scalars()
            .all()
        )
        filas = (
            (
                await session.execute(
                    select(LoteComprobanteFila)
                    .where(LoteComprobanteFila.lote_id == operacion.lote_id)
                    .order_by(LoteComprobanteFila.id)
                )
            )
            .scalars()
            .all()
        )
        grupo_objetivo = next(
            (grupo for grupo in grupos if grupo.id == intento.grupo_id), None
        )
        filas_objetivo = [fila for fila in filas if fila.grupo_id == intento.grupo_id]
        if (
            lote is None
            or lote.empresa_id != plan.empresa_id
            or lote.id != plan.precondiciones.get("lote_id")
            or lote.estado != "fallido"
            or not grupos
            or grupo_objetivo is None
            or grupo_objetivo.estado != "fallido"
            or any(grupo.estado not in ESTADOS_TERMINALES_LOTE_HIJO for grupo in grupos)
            or not filas
            or not filas_objetivo
            or any(fila.estado != "fallido" for fila in filas_objetivo)
            or any(fila.estado not in ESTADOS_TERMINALES_LOTE_HIJO for fila in filas)
        ):
            raise ResolucionLegacyPF19Error(
                "El grafo batch del replay legacy no permanece terminal"
            )
        _validar_grupos_replay(plan, grupos, intento.grupo_id)
        _validar_filas_replay(plan, filas, intento.grupo_id)
        modelo = (
            LoteProcesamientoResponse
            if operacion.tipo_operacion == "procesar_lote"
            else LoteAccionResponse
        )
        dto = modelo.model_validate(operacion.response_json)
        esperado = _respuesta_lote_terminal(lote, operacion.tipo_operacion)
        if dto.model_dump(mode="json") != esperado.model_dump(mode="json"):
            raise ResolucionLegacyPF19Error(
                "El DTO de lote del replay legacy diverge del lote terminal"
            )
    except ResolucionLegacyPF19Error:
        raise
    except Exception as exc:
        raise ResolucionLegacyPF19Error(
            "El replay legacy no conserva un DTO terminal válido"
        ) from exc


async def aplicar_resolucion_legacy_pf19(
    session: AsyncSession,
    solicitud: SolicitudApplyLegacyPF19,
    consultas_arca: ConsultasArcaLegacyPF19,
) -> dict[str, object]:
    """Aplica un plan confirmado en un único commit o revierte todo el cierre."""
    plan = solicitud.plan
    _validar_sha_plan_recibido(plan)
    backup = _validar_backup_recibido(solicitud.backup)
    if (
        solicitud.confirmacion != CONFIRMACION_APPLY_LEGACY_PF19
        or solicitud.ventana_mantenimiento_confirmada is not True
    ):
        raise ResolucionLegacyPF19Error("Falta la confirmación administrativa exacta")
    if (
        solicitud.actor_usuario_id.__class__ is not int
        or solicitud.actor_usuario_id <= 0
    ):
        raise ResolucionLegacyPF19Error("El actor administrativo no es válido")
    if session.in_transaction():
        raise ResolucionLegacyPF19Error(
            "La aplicación legacy requiere una sesión sin transacción previa"
        )

    try:
        async with session.begin():
            await _adquirir_locks(session, plan, solicitud.actor_usuario_id)
            journal_existente = (
                await session.execute(
                    select(ResolucionLegacyPF19Journal)
                    .where(ResolucionLegacyPF19Journal.intento_id == plan.intento_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if journal_existente is not None:
                if journal_existente.plan_sha256 == plan.plan_sha256:
                    await _validar_replay_journal(session, plan, journal_existente)
                    return {
                        "resultado": "replay_idempotente",
                        "intento_id": plan.intento_id,
                        "plan_sha256": plan.plan_sha256,
                    }
                raise ResolucionLegacyPF19Error(
                    "El intento ya posee un cierre legacy con otro plan"
                )
            plan = await _plan_revalidado(session, plan)

            consultas: dict[str, str] = {}
            for ambiente in plan.ambientes_consultados:
                try:
                    ultimo = await consultas_arca.ultimo_autorizado(
                        ambiente,
                        plan.punto_venta,
                        plan.tipo_comprobante,
                    )
                except Exception:
                    return _sin_cambio(plan, "ultimo_autorizado_incierto")
                if ultimo.__class__ is not int or ultimo < 0:
                    return _sin_cambio(plan, "ultimo_autorizado_invalido")
                if ultimo < plan.numero_planificado:
                    consultas[ambiente] = "ultimo_menor_al_planificado"
                    continue
                try:
                    comprobante = await consultas_arca.consultar(
                        ambiente,
                        plan.punto_venta,
                        plan.tipo_comprobante,
                        plan.numero_planificado,
                    )
                except Exception:
                    return _sin_cambio(plan, "consulta_exacta_incierta")
                if comprobante.__class__ is not ConsultaComprobanteLegacyPF19:
                    return _sin_cambio(plan, "consulta_exacta_invalida")
                if (
                    comprobante.existe
                    and comprobante.autorizado
                    and comprobante.identidad_exacta
                ):
                    return _sin_cambio(plan, "autorizacion_confirmada")
                return _sin_cambio(plan, "resultado_no_terminal")

            intento = await session.get(IntentoEmisionFiscal, plan.intento_id)
            if intento is None:
                raise ResolucionLegacyPF19Error("El intento legacy ya no existe")
            terminal_response_sha256 = await _cerrar_grafo_legacy(
                session, intento, plan
            )
            session.add(
                ResolucionLegacyPF19Journal(
                    accion=ACCION_CIERRE_LEGACY_PF19,
                    plan_sha256=plan.plan_sha256,
                    terminal_response_sha256=terminal_response_sha256,
                    actor_usuario_id=solicitud.actor_usuario_id,
                    ambiente_consultado=(
                        plan.ambientes_consultados[0]
                        if len(plan.ambientes_consultados) == 1
                        else "ambos"
                    ),
                    resultado=CATEGORIA_CIERRE_LEGACY_PF19,
                    resultado_consultas_json=consultas,
                    backup_metadata_json=backup.model_dump(exclude={"sha256"}),
                    backup_sha256=backup.sha256,
                    intento_id=plan.intento_id,
                    empresa_id=plan.empresa_id,
                )
            )
        return {
            "resultado": "cerrado",
            "intento_id": plan.intento_id,
            "plan_sha256": plan.plan_sha256,
            "categoria_error": CATEGORIA_CIERRE_LEGACY_PF19,
        }
    except IntegrityError as exc:
        await session.rollback()
        raise ResolucionLegacyPF19Error(
            "La resolución legacy perdió una carrera; releé el journal antes de reintentar"
        ) from exc


def _sin_cambio(plan: PlanLegacyPF19, motivo: str) -> dict[str, object]:
    """Devuelve una salida sanitaria sin persistir journal ni modificar estados."""
    return {
        "resultado": "sin_cambio",
        "intento_id": plan.intento_id,
        "plan_sha256": plan.plan_sha256,
        "motivo": motivo,
    }


async def _cerrar_grafo_legacy(
    session: AsyncSession,
    intento: IntentoEmisionFiscal,
    plan: PlanLegacyPF19,
) -> str:
    """Cierra el grafo mínimo coherente del candidato en el mismo commit."""
    mensaje = "Cierre legacy por ausencia de autorización verificada"
    intento_cas = await session.execute(
        update(IntentoEmisionFiscal)
        .where(
            IntentoEmisionFiscal.id == intento.id,
            IntentoEmisionFiscal.empresa_id == intento.empresa_id,
            IntentoEmisionFiscal.estado == "requiere_reconciliacion",
            IntentoEmisionFiscal.updated_at == intento.updated_at,
        )
        .values(
            estado="fallido_verificado",
            categoria_error=CATEGORIA_CIERRE_LEGACY_PF19,
            mensaje=mensaje,
        )
    )
    if intento_cas.rowcount != 1:
        raise ResolucionLegacyPF19Error(
            "El intento legacy perdió una carrera; no se aplicó el cierre"
        )
    await session.refresh(intento)

    if intento.grupo_id is not None:
        grupo = await session.get(LoteComprobanteGrupo, intento.grupo_id)
        if grupo is None or grupo.lote_id != intento.lote_id:
            raise ResolucionLegacyPF19Error("El grupo legacy no conserva su lote")
        intentos_grupo = (
            (
                await session.execute(
                    select(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.grupo_id == grupo.id)
                    .order_by(IntentoEmisionFiscal.id)
                )
            )
            .scalars()
            .all()
        )
        if not any(item.id == intento.id for item in intentos_grupo) or any(
            item.id != intento.id and item.estado not in ESTADOS_TERMINALES_INTENTO
            for item in intentos_grupo
        ):
            raise ResolucionLegacyPF19Error(
                "El sublote legacy conserva otro intento no terminal"
            )
        grupo_cas = await session.execute(
            update(LoteComprobanteGrupo)
            .where(
                LoteComprobanteGrupo.id == grupo.id,
                LoteComprobanteGrupo.estado == "requiere_reconciliacion",
                LoteComprobanteGrupo.updated_at == grupo.updated_at,
            )
            .values(
                estado="fallido",
                mensajes_json=[CATEGORIA_CIERRE_LEGACY_PF19],
            )
        )
        if grupo_cas.rowcount != 1:
            raise ResolucionLegacyPF19Error(
                "El grupo legacy perdió una carrera; no se aplicó el cierre"
            )
        await session.refresh(grupo)
        snapshot_filas = _leer_snapshot_plan(plan, "filas")
        try:
            filas_ids = [
                int(fila["id"])
                for fila in snapshot_filas
                if int(fila["grupo_id"]) == grupo.id
                and int(fila["lote_id"]) == grupo.lote_id
                and fila["estado"] == "requiere_reconciliacion"
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise ResolucionLegacyPF19Error(
                "El plan legacy no conserva el inventario de filas"
            ) from exc
        if len(filas_ids) != int(plan.precondiciones["filas_objetivo_cantidad"]):
            raise ResolucionLegacyPF19Error(
                "El plan legacy no conserva la cardinalidad exacta de filas"
            )
        filas_cas = await session.execute(
            update(LoteComprobanteFila)
            .where(
                LoteComprobanteFila.id.in_(filas_ids),
                LoteComprobanteFila.lote_id == grupo.lote_id,
                LoteComprobanteFila.grupo_id == grupo.id,
                LoteComprobanteFila.estado == "requiere_reconciliacion",
            )
            .values(
                estado="fallido",
                mensajes_json=[CATEGORIA_CIERRE_LEGACY_PF19],
            )
        )
        if filas_cas.rowcount != len(filas_ids):
            raise ResolucionLegacyPF19Error(
                "Las filas legacy perdieron una carrera; no se aplicó el cierre"
            )
        await session.flush()
        lote = await session.get(LoteComprobante, grupo.lote_id)
        if lote is None:
            raise ResolucionLegacyPF19Error("El lote legacy no existe")
        conteos = dict(
            (
                await session.execute(
                    select(LoteComprobanteGrupo.estado, func.count())
                    .where(LoteComprobanteGrupo.lote_id == lote.id)
                    .group_by(LoteComprobanteGrupo.estado)
                )
            ).all()
        )
        lote.total_grupos = sum(conteos.values())
        lote.grupos_validos = conteos.get("validado", 0)
        lote.grupos_con_error = conteos.get("con_error", 0)
        lote.grupos_emitidos = conteos.get("autorizado", 0)
        lote.grupos_fallidos = conteos.get("fallido", 0)
        lote.grupos_reconciliados_externos = conteos.get("autorizado_externo", 0)
        lote.grupos_descartados = conteos.get("descartado", 0)
        if not any(
            conteos.get(estado, 0)
            for estado in ("requiere_reconciliacion", "reintentando", "procesando")
        ):
            lote.estado = "fallido" if lote.grupos_fallidos else lote.estado
            lote.mensaje_resumen = mensaje

    if intento.guarda_rece_id is not None:
        guarda = await session.get(PuntoVentaGuardaEmisionRece, intento.guarda_rece_id)
        if (
            guarda is None
            or guarda.operacion_id != intento.operacion_id
            or guarda.empresa_id != intento.empresa_id
            or guarda.punto_venta_id != intento.punto_venta_id
            or plan.precondiciones.get("guarda_id") != guarda.id
            or plan.precondiciones.get("guarda_fase") != guarda.fase
            or plan.precondiciones.get("guarda_ambiente") != guarda.ambiente
            or plan.precondiciones.get("guarda_version") != _version_intento(guarda)
        ):
            raise ResolucionLegacyPF19Error(
                "La guarda RECE legacy es inconsistente; no se aplicó el cierre"
            )
        guarda_cas = await session.execute(
            update(PuntoVentaGuardaEmisionRece)
            .where(
                PuntoVentaGuardaEmisionRece.id == guarda.id,
                PuntoVentaGuardaEmisionRece.operacion_id == intento.operacion_id,
                PuntoVentaGuardaEmisionRece.empresa_id == intento.empresa_id,
                PuntoVentaGuardaEmisionRece.punto_venta_id == intento.punto_venta_id,
                PuntoVentaGuardaEmisionRece.fase == guarda.fase,
                PuntoVentaGuardaEmisionRece.updated_at == guarda.updated_at,
            )
            .values(fase="cerrada_terminal", cerrada_en=datetime.utcnow())
        )
        if guarda_cas.rowcount != 1:
            raise ResolucionLegacyPF19Error(
                "La guarda RECE legacy perdió una carrera; no se aplicó el cierre"
            )

    await session.flush()
    return await _cerrar_operacion_legacy(session, intento, plan)


async def _cerrar_operacion_legacy(
    session: AsyncSession,
    intento: IntentoEmisionFiscal,
    plan: PlanLegacyPF19,
) -> str:
    """Publica por CAS una respuesta terminal válida cuando todo el grafo cerró."""
    if intento.operacion_id is None:
        return
    operacion = await session.get(OperacionIdempotente, intento.operacion_id)
    if operacion is None or operacion.empresa_id != intento.empresa_id:
        raise ResolucionLegacyPF19Error("La operación legacy es inconsistente")
    restantes = (
        await session.execute(
            select(func.count())
            .select_from(IntentoEmisionFiscal)
            .where(
                IntentoEmisionFiscal.operacion_id == operacion.id,
                IntentoEmisionFiscal.estado.in_(
                    ("en_proceso", "requiere_reconciliacion")
                ),
            )
        )
    ).scalar_one()
    if int(restantes) != 0:
        raise ResolucionLegacyPF19Error(
            "La operación conserva intentos inciertos y no puede cerrarse parcialmente"
        )
    total_intentos = (
        await session.execute(
            select(func.count())
            .select_from(IntentoEmisionFiscal)
            .where(IntentoEmisionFiscal.operacion_id == operacion.id)
        )
    ).scalar_one()
    if operacion.tipo_operacion == "emitir_comprobante" and int(total_intentos) != 1:
        raise ResolucionLegacyPF19Error(
            "La operación legacy no conserva cardinalidad exacta de intentos"
        )
    precondiciones = plan.precondiciones
    if (
        precondiciones.get("operacion_id") != operacion.id
        or precondiciones.get("operacion_tipo") != operacion.tipo_operacion
        or precondiciones.get("operacion_estado") != operacion.estado
        or precondiciones.get("operacion_version") != _version_intento(operacion)
        or precondiciones.get("operacion_response_sha256")
        != _huella_json(operacion.response_json)
    ):
        raise ResolucionLegacyPF19Error(
            "La operación cambió desde el plan legacy; no se publicó el cierre"
        )
    if operacion.tipo_operacion == "emitir_comprobante":
        respuesta = _respuesta_individual_terminal(intento)
    elif operacion.tipo_operacion in {"procesar_lote", "reintentar_fallidos_lote"}:
        if operacion.lote_id is None:
            raise ResolucionLegacyPF19Error("La operación de lote no conserva su lote")
        lote = await session.get(LoteComprobante, operacion.lote_id)
        if lote is None or lote.empresa_id != operacion.empresa_id:
            raise ResolucionLegacyPF19Error("El lote de la operación es inconsistente")
        estados_grupos = (
            (
                await session.execute(
                    select(LoteComprobanteGrupo.estado)
                    .where(LoteComprobanteGrupo.lote_id == lote.id)
                    .order_by(LoteComprobanteGrupo.id)
                )
            )
            .scalars()
            .all()
        )
        estados_filas = (
            (
                await session.execute(
                    select(LoteComprobanteFila.estado)
                    .where(LoteComprobanteFila.lote_id == lote.id)
                    .order_by(LoteComprobanteFila.id)
                )
            )
            .scalars()
            .all()
        )
        if (
            not estados_grupos
            or not estados_filas
            or any(
                estado not in ESTADOS_TERMINALES_LOTE_HIJO
                for estado in (*estados_grupos, *estados_filas)
            )
        ):
            raise ResolucionLegacyPF19Error(
                "El lote conserva hijos no terminales y no puede publicar replay"
            )
        await session.refresh(lote)
        if lote.estado != "fallido":
            raise ResolucionLegacyPF19Error(
                "El lote legacy no alcanzó el estado terminal esperado"
            )
        respuesta = _respuesta_lote_terminal(lote, operacion.tipo_operacion)
    else:
        raise ResolucionLegacyPF19Error(
            "El tipo de operación legacy no tiene un contrato de replay reconstruible"
        )
    publicado = await session.execute(
        update(OperacionIdempotente)
        .where(
            OperacionIdempotente.id == operacion.id,
            OperacionIdempotente.empresa_id == operacion.empresa_id,
            OperacionIdempotente.estado == "requiere_reconciliacion",
            OperacionIdempotente.updated_at == operacion.updated_at,
        )
        .values(
            estado=(
                "fallido_verificado"
                if operacion.tipo_operacion == "emitir_comprobante"
                else "finalizado"
            ),
            response_json=respuesta.model_dump(mode="json"),
        )
    )
    if publicado.rowcount != 1:
        raise ResolucionLegacyPF19Error(
            "La publicación terminal perdió una carrera; no se aplicó el cierre"
        )
    return _huella_json(respuesta.model_dump(mode="json"))
