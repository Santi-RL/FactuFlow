"""Comparación y coordinación durable de duplicados para lotes v2."""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import heapq
import json
import secrets
import unicodedata
from collections.abc import Iterator
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import (
    Integer,
    String,
    and_,
    case,
    func,
    insert,
    literal,
    or_,
    select,
    text,
    union_all,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.arca.utils import validate_cuit
from app.models.empresa import LoteDuplicadosCoordinacion
from app.models.idempotencia_fiscal import (
    IntentoEmisionFiscal,
    LoteDuplicadoCoincidencia,
    LoteDuplicadoCoincidenciaMiembro,
    LoteDuplicadoEvidencia,
    OperacionIdempotente,
)
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta
from app.schemas.comprobante import EmitirComprobanteRequest
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService


VERSION = "duplicados_lotes/v2"
RELACION_FORMATO = "duplicados_relacion/1"
MENSAJE_BLOQUEO_LEGACY = (
    "Este lote antiguo no puede continuar porque su confirmación anterior no es "
    "comprobable. Prepará un lote nuevo; se aplicarán los controles de duplicados."
)
INSERT_BUFFER = 250
LIVE_QUERY_MEMBER_BUFFER = 80
HISTORICAL_READ_WINDOW = 80
READ_PARAMETER_BUFFER = 1000
LIVE_MEMBER_BIND_COUNT = 5
# La expansión lexicográfica tiene hasta 66 valores de watermark repetidos en
# sus prefijos. La proyección, los CASE de NULL, LIMIT y filtros fijos quedan
# cubiertos por otros 32 binds conservadores.
LIVE_QUERY_FIXED_BIND_BUDGET = sum(range(1, 12)) + 32
TIPO_ORDEN_PUBLICO = {
    "interna_nombre": 0,
    "interna_documento": 0,
    "completa": 1,
    "parcial_nombre": 2,
    "parcial_documento": 2,
    "individual_legacy": 3,
}
COBERTURAS = {"completa", "parcial_legacy", "no_comprobable"}
ESTADOS_AUTORIZADOS = {"autorizado", "autorizado_externo"}
ESTADOS_INCIERTOS = {"requiere_reconciliacion"}
ESTADOS_RESERVADOS = {"en_cola", "procesando", "reintentando"}
ESTADOS_SELECCION_ORIGINAL = {
    "cargado",
    "validado",
    "en_cola",
    "procesando",
    "reintentando",
    "autorizado",
    "autorizado_externo",
    "fallido",
    "requiere_reconciliacion",
    "descartado",
}
TIPOS_DOCUMENTO_RECONOCIDOS = {80, 86, 89, 90, 94, 96, 99}
NOMBRES_GENERICOS = {"", "consumidor final", "a consumidor final"}


class _ReverseOrderKey:
    """Invierte una clave total para mantener un max-heap con `heapq`."""

    __slots__ = ("key",)

    def __init__(self, key: tuple[Any, ...]):
        self.key = key

    def __lt__(self, other: _ReverseOrderKey) -> bool:
        return self.key > other.key


def _particiones_parametros(values: Any) -> Iterator[list[Any]]:
    ordered = sorted(set(values))
    for start in range(0, len(ordered), READ_PARAMETER_BUFFER):
        yield ordered[start : start + READ_PARAMETER_BUFFER]


def _particiones_lectura(
    values: Any, *, fixed_bind_count: int = 8
) -> Iterator[list[Any]]:
    """Reserva parámetros fijos además de los valores del IN de lectura."""
    ordered = sorted(set(values))
    size = max(1, READ_PARAMETER_BUFFER - fixed_bind_count)
    for start in range(0, len(ordered), size):
        yield ordered[start : start + size]


class DuplicadosLoteError(Exception):
    """Falla cerrada anterior a cualquier solicitud fiscal."""

    def __init__(
        self,
        mensaje: str,
        categoria: str = "duplicados_coordinacion_error",
        *,
        control: dict[str, Any] | None = None,
    ):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.categoria = categoria
        self.control = control


class DuplicadosLotePreflightCambioError(DuplicadosLoteError):
    """Señala evidencia relevante nueva antes de crear una guarda fiscal."""

    def __init__(self, control: dict[str, Any]):
        super().__init__(
            "La evidencia de duplicados cambió antes de solicitar CAE.",
            "duplicado_logico_lote",
            control=control,
        )


def _json_canonico(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: (
            item.isoformat()
            if isinstance(item, datetime)
            else decimal_canonico(item)
            if isinstance(item, Decimal)
            else str(item)
        ),
    )


def _datetime_utc(value: datetime | None) -> datetime | None:
    """Normaliza las marcas v2, almacenadas con semántica UTC, tras recargarlas."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sha256(value: Any) -> str:
    material = value if isinstance(value, str) else _json_canonico(value)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _digest_b64(value: Any) -> str:
    digest = hashlib.sha256(_json_canonico(value).encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def normalizar_texto(value: Any) -> str:
    """Normaliza texto de evidencia sin eliminar signos ni aproximar personas."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.split()).casefold()


def decimal_canonico(value: Any) -> str:
    """Serializa un Decimal finito sin ceros finales ni notación exponencial."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("El valor decimal no es válido") from exc
    if not number.is_finite():
        raise ValueError("El valor decimal debe ser finito")
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def decimal_dos_posiciones(value: Any) -> str:
    return f"{Decimal(str(value or 0)).quantize(Decimal('0.01')):.2f}"


def _desglosar_importes(
    componentes: list[tuple[str | None, Decimal]],
) -> dict[str, Any]:
    """Agrupa importes sólo dentro de una moneda acreditada."""
    acumulados: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    cantidades: Counter[str] = Counter()
    desconocidos = 0
    for moneda, importe in componentes:
        codigo = str(moneda or "").strip().upper()
        if not codigo:
            desconocidos += 1
            continue
        acumulados[codigo] += Decimal(str(importe))
        cantidades[codigo] += 1
    return {
        "por_moneda": [
            {
                "moneda": codigo,
                "importe": decimal_dos_posiciones(acumulados[codigo]),
                "cantidad": cantidades[codigo],
            }
            for codigo in sorted(acumulados)
        ],
        "cantidad_sin_moneda_acreditada": desconocidos,
    }


def _importe_escalar(desglose: dict[str, Any]) -> str | None:
    """Devuelve un total sólo cuando sus unidades son inequívocas."""
    por_moneda = desglose["por_moneda"]
    if desglose["cantidad_sin_moneda_acreditada"]:
        return None
    if not por_moneda:
        return "0.00"
    if len(por_moneda) != 1:
        return None
    return str(por_moneda[0]["importe"])


def _desglosar_importes_agregados(
    componentes: list[tuple[str | None, Decimal, int]],
) -> dict[str, Any]:
    """Publica agregados SQL sin convertir monedas ni perder sus cantidades."""
    por_moneda: list[dict[str, Any]] = []
    desconocidos = 0
    for moneda, importe, cantidad in componentes:
        codigo = str(moneda or "").strip().upper()
        if not codigo:
            desconocidos += int(cantidad)
            continue
        por_moneda.append(
            {
                "moneda": codigo,
                "importe": decimal_dos_posiciones(importe),
                "cantidad": int(cantidad),
            }
        )
    return {
        "por_moneda": sorted(por_moneda, key=lambda item: item["moneda"]),
        "cantidad_sin_moneda_acreditada": desconocidos,
    }


def identidad_entrada_v2(
    *, tipo_documento: Any, numero_documento: Any, razon_social: Any
) -> dict[str, Any]:
    """Construye identidad de comparación independiente del receptor fiscal."""
    nombre_original = str(razon_social or "").strip() or None
    nombre_normalizado = normalizar_texto(razon_social)
    nombre_hash = (
        _sha256({"nombre": nombre_normalizado})
        if nombre_normalizado not in NOMBRES_GENERICOS
        else None
    )
    try:
        tipo = int(tipo_documento) if str(tipo_documento or "").strip() else None
    except (TypeError, ValueError):
        tipo = None
    numero_original = str(numero_documento or "").strip() or None
    numero = "".join(
        character for character in str(numero_documento or "") if character.isdigit()
    )
    documento_valido = (
        tipo in TIPOS_DOCUMENTO_RECONOCIDOS
        and bool(numero)
        and set(numero) != {"0"}
        and not (tipo == 99 and numero == "0")
        and (tipo != 80 or validate_cuit(numero))
    )
    documento_hash = (
        _sha256({"tipo": tipo, "numero": numero}) if documento_valido else None
    )
    return {
        "nombre_original": nombre_original,
        "tipo_documento_original": tipo,
        "numero_documento_original": numero_original,
        "nombre_hash": nombre_hash,
        "documento_hash": documento_hash,
    }


def canonicalizar_payload_fiscal_v2(
    request: EmitirComprobanteRequest | dict[str, Any], *, punto_venta_numero: int
) -> dict[str, Any]:
    """Canonicaliza exactamente el contenido fiscal comparable del request."""
    parsed = (
        request
        if isinstance(request, EmitirComprobanteRequest)
        else EmitirComprobanteRequest.model_validate(request)
    )
    datos = parsed.model_dump(mode="json")

    def texto(field: str) -> str | None:
        normalized = normalizar_texto(datos.get(field))
        return normalized or None

    items = []
    for item in datos["items"]:
        items.append(
            {
                "codigo": normalizar_texto(item.get("codigo")) or None,
                "descripcion": normalizar_texto(item.get("descripcion")),
                "cantidad": decimal_canonico(item.get("cantidad")),
                "unidad": normalizar_texto(item.get("unidad")),
                "precio_unitario": decimal_canonico(item.get("precio_unitario")),
                "descuento_porcentaje": decimal_canonico(
                    item.get("descuento_porcentaje", 0)
                ),
                "iva_porcentaje": decimal_canonico(item.get("iva_porcentaje")),
            }
        )
    items.sort(key=_json_canonico)

    asociados = []
    for asociado in datos.get("comprobantes_asociados") or []:
        asociados.append(
            {
                "tipo_comprobante": int(asociado["tipo_comprobante"]),
                "punto_venta": int(asociado["punto_venta"]),
                "numero": int(asociado["numero"]),
                "fecha": asociado.get("fecha"),
                "cuit": "".join(
                    character
                    for character in str(asociado.get("cuit") or "")
                    if character.isdigit()
                )
                or None,
            }
        )
    asociados.sort(key=_json_canonico)

    return {
        "tipo_comprobante": int(datos["tipo_comprobante"]),
        "punto_venta_numero": int(punto_venta_numero),
        "concepto": int(datos["concepto"]),
        "fecha_emision": datos["fecha_emision"],
        "fecha_servicio_desde": datos.get("fecha_servicio_desde"),
        "fecha_servicio_hasta": datos.get("fecha_servicio_hasta"),
        "fecha_vto_pago": datos.get("fecha_vto_pago"),
        "tipo_documento": int(datos["tipo_documento"]),
        "numero_documento": "".join(
            character
            for character in str(datos.get("numero_documento") or "")
            if character.isdigit()
        ),
        "razon_social": texto("razon_social"),
        "condicion_iva": texto("condicion_iva"),
        "domicilio": texto("domicilio"),
        "moneda": str(datos.get("moneda") or "").upper(),
        "cotizacion": decimal_canonico(datos.get("cotizacion")),
        "observaciones": texto("observaciones"),
        "comprobantes_asociados": asociados,
        "items": items,
    }


def huella_fiscal_completa_v2(
    request: EmitirComprobanteRequest | dict[str, Any], *, punto_venta_numero: int
) -> str:
    return _sha256(
        canonicalizar_payload_fiscal_v2(
            request,
            punto_venta_numero=punto_venta_numero,
        )
    )


def material_grupo_v2(
    *,
    payload: dict[str, Any],
    punto_venta_numero: int,
    total: Decimal,
    identidad: dict[str, Any],
) -> dict[str, Any]:
    request = EmitirComprobanteRequest.model_validate(payload)
    return {
        "duplicados_version": VERSION,
        "duplicados_cobertura": "completa",
        "huella_fiscal_completa": huella_fiscal_completa_v2(
            request, punto_venta_numero=punto_venta_numero
        ),
        "identidad_nombre_hash": identidad.get("nombre_hash"),
        "identidad_documento_hash": identidad.get("documento_hash"),
        "identidad_nombre_original": identidad.get("nombre_original"),
        "identidad_tipo_documento_original": identidad.get("tipo_documento_original"),
        "identidad_numero_documento_original": identidad.get(
            "numero_documento_original"
        ),
        "fecha_emision_normalizada": request.fecha_emision,
        "moneda_duplicados": request.moneda,
        "cotizacion_duplicados": decimal_canonico(request.cotizacion),
        "total_centavos": int(
            (Decimal(str(total)).quantize(Decimal("0.01")) * 100).to_integral_exact()
        ),
    }


def aplicar_material_grupo_v2(
    grupo: LoteComprobanteGrupo, material: dict[str, Any]
) -> None:
    for field, value in material.items():
        setattr(grupo, field, value)


class DuplicadosLotesService:
    """Calcula evidencia v2 y publica reservas dentro de una sección crítica."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _grupos_actuales(
        self,
        *,
        lote_id: int,
        empresa_id: int,
        estados: set[str],
        grupo_ids: list[int] | None = None,
    ) -> list[LoteComprobanteGrupo]:
        stmt = (
            select(LoteComprobanteGrupo)
            .where(
                LoteComprobanteGrupo.lote_id == lote_id,
                LoteComprobanteGrupo.empresa_id == empresa_id,
                LoteComprobanteGrupo.estado.in_(estados),
            )
            .order_by(LoteComprobanteGrupo.orden, LoteComprobanteGrupo.id)
        )
        if grupo_ids:
            stmt = stmt.where(LoteComprobanteGrupo.id.in_(grupo_ids))
        grupos = list((await self.db.execute(stmt)).scalars().all())
        if grupo_ids and {int(item.id) for item in grupos} != set(grupo_ids):
            raise DuplicadosLoteError(
                "La selección cambió antes de evaluar duplicados.",
                "duplicados_seleccion_obsoleta",
            )
        return grupos

    @staticmethod
    def _seleccion_material(grupos: list[LoteComprobanteGrupo]) -> list[dict[str, Any]]:
        return [
            {
                "grupo_id": int(grupo.id),
                "huella": grupo.huella_fiscal_completa,
                "nombre_hash": grupo.identidad_nombre_hash,
                "documento_hash": grupo.identidad_documento_hash,
            }
            for grupo in grupos
        ]

    @staticmethod
    def _base_control(
        grupos: list[LoteComprobanteGrupo],
        *,
        lote_id: int,
    ) -> dict[str, Any]:
        seleccion = DuplicadosLotesService._seleccion_material(grupos)
        datos_hash = _sha256(
            sorted(str(grupo.huella_fiscal_completa or "") for grupo in grupos)
        )
        seleccion_hash = _sha256(seleccion)
        importes_actuales = _desglosar_importes(
            [
                (
                    grupo.moneda_duplicados,
                    Decimal(str(grupo.total_estimado or 0)),
                )
                for grupo in grupos
            ]
        )
        coberturas = {grupo.duplicados_cobertura for grupo in grupos}
        cobertura = "completa"
        if "no_comprobable" in coberturas or None in coberturas:
            cobertura = "no_comprobable"
        elif "parcial_legacy" in coberturas:
            cobertura = "parcial_legacy"
        return {
            "version": VERSION,
            "cobertura": cobertura,
            "estado": "sin_coincidencias",
            "evidencia_id": None,
            "datos_hash": datos_hash,
            "seleccion_hash": seleccion_hash,
            "tipos_coincidencia": [],
            "cantidad_actual": len(grupos),
            "cantidad_afectada": 0,
            "importe_actual": _importe_escalar(importes_actuales),
            "importe_afectado": "0.00",
            "importes_actuales": importes_actuales,
            "importes_afectados": _desglosar_importes([]),
            "antecedentes_resumen": [],
            "aceptacion_requerida": False,
            "aceptacion_habilitada": True,
            "bloqueo_operacion_ajena": None,
            "detalle_url": None,
            "_lote_id": lote_id,
            "_seleccion": seleccion,
            "_afectados_importes": {},
            "_bloques": {},
        }

    async def calcular_control(
        self,
        *,
        lote_id: int,
        empresa_id: int,
        estados: set[str],
        grupo_ids: list[int] | None = None,
        operacion_id: int | None = None,
        incluir_interno: bool = False,
    ) -> dict[str, Any]:
        grupos = await self._grupos_actuales(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados=estados,
            grupo_ids=grupo_ids,
        )
        control = self._base_control(grupos, lote_id=lote_id)
        if not grupos:
            return control if incluir_interno else self._publicable(control)
        if any(grupo.duplicados_version != VERSION for grupo in grupos):
            control["cobertura"] = "no_comprobable"

        await self._agregar_internas(control, grupos)
        await self._agregar_historicas_lotes(
            control,
            grupos,
            lote_id=lote_id,
            empresa_id=empresa_id,
            operacion_id=operacion_id,
        )
        await self._agregar_individuales_legacy(
            control,
            grupos,
            empresa_id=empresa_id,
        )
        self._finalizar_control(control, empresa_id=empresa_id, grupos=grupos)
        return control if incluir_interno else self._publicable(control)

    async def _propietario_legacy_aceptado(
        self,
        *,
        lote_id: int,
        empresa_id: int,
        bloquear: bool,
        propietario_bloqueado: OperacionIdempotente | None = None,
    ) -> OperacionIdempotente | None:
        """Acredita la aceptación v1 sólo mediante su owner durable exacto."""
        lote_query = select(LoteComprobante).where(
            LoteComprobante.id == lote_id,
            LoteComprobante.empresa_id == empresa_id,
        )
        if bloquear:
            lote_query = lote_query.with_for_update()
        lote = (
            await self.db.execute(lote_query.execution_options(populate_existing=True))
        ).scalar_one_or_none()
        metadata = lote.metadata_json if lote is not None else None
        if not isinstance(metadata, dict):
            return None
        owner_id = metadata.get("operacion_idempotente_id")
        if (
            not isinstance(owner_id, int)
            or isinstance(owner_id, bool)
            or metadata.get("confirmacion_duplicado_logico") is not True
        ):
            return None
        if propietario_bloqueado is not None:
            operacion = propietario_bloqueado
            if int(operacion.id) != owner_id:
                raise DuplicadosLoteError(
                    "El owner legacy cambió durante la coordinación.",
                    "duplicado_coordinacion_transaccional",
                )
        else:
            operacion_query = select(OperacionIdempotente).where(
                OperacionIdempotente.id == owner_id,
                OperacionIdempotente.empresa_id == empresa_id,
                OperacionIdempotente.lote_id == lote_id,
            )
            operacion = (
                await self.db.execute(
                    operacion_query.execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
        if (
            operacion is None
            or operacion.tipo_operacion
            not in {"procesar_lote", "reintentar_fallidos_lote"}
            or operacion.estado not in {"en_proceso", "interrumpida_pre_arca"}
            or operacion.duplicados_version == VERSION
        ):
            return None
        return operacion

    async def obtener_propietario_legacy_aceptado(
        self,
        *,
        lote_id: int,
        empresa_id: int,
    ) -> OperacionIdempotente | None:
        """Detecta sin locks la señal exacta que requiere admisión especializada."""
        return await self._propietario_legacy_aceptado(
            lote_id=lote_id,
            empresa_id=empresa_id,
            bloquear=False,
        )

    async def revalidar_propietario_legacy_aceptado(
        self,
        *,
        lote_id: int,
        empresa_id: int,
        propietario_bloqueado: OperacionIdempotente,
    ) -> OperacionIdempotente:
        """Bloquea el lote y exige que conserve el owner v1 observado antes."""
        propietario = await self._propietario_legacy_aceptado(
            lote_id=lote_id,
            empresa_id=empresa_id,
            bloquear=True,
            propietario_bloqueado=propietario_bloqueado,
        )
        if propietario is None:
            raise DuplicadosLoteError(
                "La clasificación legacy cambió durante la coordinación.",
                "duplicado_coordinacion_transaccional",
            )
        return propietario

    async def obtener_bloqueo_legacy_no_reconfirmable(
        self,
        *,
        lote_id: int,
        empresa_id: int,
        estados: set[str],
        bloquear: bool = False,
        propietario_bloqueado: OperacionIdempotente | None = None,
    ) -> dict[str, Any] | None:
        """Bloquea un remanente v1 aceptado sólo si hoy conserva coincidencias."""
        propietario = await self._propietario_legacy_aceptado(
            lote_id=lote_id,
            empresa_id=empresa_id,
            bloquear=bloquear,
            propietario_bloqueado=propietario_bloqueado,
        )
        if propietario is None:
            return None
        control = await self.calcular_control(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados=estados,
            grupo_ids=None,
            operacion_id=int(propietario.id),
        )
        if not control.get("aceptacion_requerida"):
            return None
        control = dict(control)
        control["aceptacion_habilitada"] = False
        return control

    async def _agregar_internas(
        self, control: dict[str, Any], grupos: list[LoteComprobanteGrupo]
    ) -> None:
        buckets: dict[tuple[Any, ...], list[LoteComprobanteGrupo]] = defaultdict(list)
        for grupo in grupos:
            base = (
                grupo.tipo_comprobante,
                grupo.punto_venta_numero,
                grupo.fecha_emision_normalizada,
                grupo.total_centavos,
                grupo.moneda_duplicados,
                decimal_canonico(grupo.cotizacion_duplicados or 1),
            )
            if grupo.identidad_nombre_hash:
                buckets[(*base, "nombre", grupo.identidad_nombre_hash)].append(grupo)
            if grupo.identidad_documento_hash:
                buckets[(*base, "documento", grupo.identidad_documento_hash)].append(
                    grupo
                )
        afectados: set[int] = set()
        for key, matches in buckets.items():
            if len(matches) < 2:
                continue
            campo = key[-2]
            clase = f"interna_{campo}"
            identidad_bloque = {
                "comparable": [
                    key[0],
                    key[1],
                    key[2],
                    key[3],
                    key[4],
                    key[5],
                ],
                campo: key[-1],
            }
            for grupo in matches:
                afectados.add(int(grupo.id))
                self._registrar_miembro_compacto(
                    control,
                    clase=clase,
                    antecedente_clave=None,
                    identidad_bloque=identidad_bloque,
                    snapshot_bloque={
                        "origen": "lote",
                        "tipo_coincidencia": "interna_receptor",
                        "campos_coincidentes": [campo],
                    },
                    lado="actual",
                    miembro_clave=f"g-{int(grupo.id)}",
                    grupo_id=int(grupo.id),
                    comprobante_id=None,
                    nombre_hash=grupo.identidad_nombre_hash,
                    documento_hash=grupo.identidad_documento_hash,
                    ordinal=None,
                    relevancia="actual",
                    snapshot=self._snapshot_actual(grupo),
                )
        if afectados:
            control["tipos_coincidencia"].append("interna_receptor")
            control["aceptacion_requerida"] = True
            control["cantidad_afectada"] = max(
                control["cantidad_afectada"], len(afectados)
            )
            for grupo in grupos:
                if int(grupo.id) in afectados:
                    control["_afectados_importes"][int(grupo.id)] = (
                        grupo.moneda_duplicados,
                        Decimal(str(grupo.total_estimado or 0)),
                    )

    async def _agregar_historicas_lotes(
        self,
        control: dict[str, Any],
        grupos: list[LoteComprobanteGrupo],
        *,
        lote_id: int,
        empresa_id: int,
        operacion_id: int | None,
    ) -> None:
        """Compara lotes históricos con memoria acotada a una sola frontera."""
        ambientes = {grupo.ambiente for grupo in grupos if grupo.ambiente}
        hashes = [
            (
                LoteComprobanteGrupo.huella_fiscal_completa,
                {
                    grupo.huella_fiscal_completa
                    for grupo in grupos
                    if grupo.huella_fiscal_completa
                },
            ),
            (
                LoteComprobanteGrupo.identidad_nombre_hash,
                {
                    grupo.identidad_nombre_hash
                    for grupo in grupos
                    if grupo.identidad_nombre_hash
                },
            ),
            (
                LoteComprobanteGrupo.identidad_documento_hash,
                {
                    grupo.identidad_documento_hash
                    for grupo in grupos
                    if grupo.identidad_documento_hash
                },
            ),
        ]
        if not ambientes or not any(values for _column, values in hashes):
            return

        candidate_group_ids: dict[int, set[int]] = defaultdict(set)
        for column, values in hashes:
            for value_partition in _particiones_lectura(values):
                watermark: tuple[int, int] | None = None
                while True:
                    statement = select(
                        LoteComprobanteGrupo.lote_id,
                        LoteComprobanteGrupo.id,
                    ).where(
                        LoteComprobanteGrupo.empresa_id == empresa_id,
                        LoteComprobanteGrupo.lote_id != lote_id,
                        LoteComprobanteGrupo.ambiente.in_(ambientes),
                        column.in_(value_partition),
                    )
                    if watermark is not None:
                        statement = statement.where(
                            or_(
                                LoteComprobanteGrupo.lote_id > watermark[0],
                                and_(
                                    LoteComprobanteGrupo.lote_id == watermark[0],
                                    LoteComprobanteGrupo.id > watermark[1],
                                ),
                            )
                        )
                    rows = list(
                        (
                            await self.db.execute(
                                statement.order_by(
                                    LoteComprobanteGrupo.lote_id,
                                    LoteComprobanteGrupo.id,
                                ).limit(HISTORICAL_READ_WINDOW)
                            )
                        )
                    )
                    for candidate_lote_id, candidate_group_id in rows:
                        candidate_group_ids[int(candidate_lote_id)].add(
                            int(candidate_group_id)
                        )
                    if len(rows) < HISTORICAL_READ_WINDOW:
                        break
                    watermark = (int(rows[-1][0]), int(rows[-1][1]))

        current_counter = Counter(grupo.huella_fiscal_completa for grupo in grupos)
        for previous_lote_id in sorted(candidate_group_ids):
            previous_lote = (
                await self.db.execute(
                    select(LoteComprobante).where(
                        LoteComprobante.id == previous_lote_id,
                        LoteComprobante.empresa_id == empresa_id,
                    )
                )
            ).scalar_one_or_none()
            if previous_lote is None:
                continue
            aggregate = (
                await self.db.execute(
                    select(
                        func.count(LoteComprobanteGrupo.id),
                        func.coalesce(func.sum(LoteComprobanteGrupo.total_estimado), 0),
                        func.sum(
                            case(
                                (
                                    or_(
                                        LoteComprobanteGrupo.duplicados_cobertura
                                        == "no_comprobable",
                                        LoteComprobanteGrupo.duplicados_cobertura.is_(
                                            None
                                        ),
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        func.sum(
                            case(
                                (
                                    LoteComprobanteGrupo.duplicados_cobertura
                                    == "parcial_legacy",
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                    ).where(
                        LoteComprobanteGrupo.empresa_id == empresa_id,
                        LoteComprobanteGrupo.lote_id == previous_lote_id,
                        LoteComprobanteGrupo.ambiente.in_(ambientes),
                    )
                )
            ).one()
            physical_stats = {
                "count": int(aggregate[0]),
                "amount": Decimal(str(aggregate[1] or 0)),
                "coverage": (
                    "no_comprobable"
                    if int(aggregate[2] or 0)
                    else "parcial_legacy"
                    if int(aggregate[3] or 0)
                    else "completa"
                ),
            }
            physical_amounts = [
                (row[0], Decimal(str(row[1] or 0)), int(row[2]))
                for row in (
                    await self.db.execute(
                        select(
                            LoteComprobanteGrupo.moneda_duplicados,
                            func.coalesce(
                                func.sum(LoteComprobanteGrupo.total_estimado), 0
                            ),
                            func.count(LoteComprobanteGrupo.id),
                        )
                        .where(
                            LoteComprobanteGrupo.empresa_id == empresa_id,
                            LoteComprobanteGrupo.lote_id == previous_lote_id,
                            LoteComprobanteGrupo.ambiente.in_(ambientes),
                        )
                        .group_by(LoteComprobanteGrupo.moneda_duplicados)
                    )
                )
            ]
            valid_durable_selection = False
            seen_frontiers: set[tuple[int, int, tuple[int, ...]]] = set()
            operation_watermark: tuple[int, int] | None = None
            while True:
                root = func.coalesce(
                    OperacionIdempotente.operacion_raiz_id,
                    OperacionIdempotente.id,
                )
                operation_filters = [
                    OperacionIdempotente.empresa_id == empresa_id,
                    OperacionIdempotente.lote_id == previous_lote_id,
                    OperacionIdempotente.duplicados_version == VERSION,
                    OperacionIdempotente.control_duplicados_json.is_not(None),
                ]
                if operacion_id is not None:
                    operation_filters.append(OperacionIdempotente.id != operacion_id)
                operation_statement = select(
                    OperacionIdempotente.id,
                    root.label("root_id"),
                    OperacionIdempotente.control_duplicados_json,
                ).where(*operation_filters)
                if operation_watermark is not None:
                    operation_statement = operation_statement.where(
                        or_(
                            root > operation_watermark[0],
                            and_(
                                root == operation_watermark[0],
                                OperacionIdempotente.id > operation_watermark[1],
                            ),
                        )
                    )
                operation_rows = list(
                    (
                        await self.db.execute(
                            operation_statement.order_by(
                                root, OperacionIdempotente.id
                            ).limit(HISTORICAL_READ_WINDOW)
                        )
                    )
                )
                for operation_row in operation_rows:
                    root_id = int(operation_row[1])
                    previous_control = operation_row[2]
                    selection = (
                        previous_control.get("seleccion_original")
                        if isinstance(previous_control, dict)
                        else None
                    )
                    if not isinstance(selection, list) or not selection:
                        continue
                    if any(
                        not isinstance(item, dict)
                        or set(item)
                        != {
                            "grupo_id",
                            "huella",
                            "nombre_hash",
                            "documento_hash",
                        }
                        or not isinstance(item.get("grupo_id"), int)
                        for item in selection
                    ):
                        continue
                    selection_ids = [int(item["grupo_id"]) for item in selection]
                    frontier_key = (
                        previous_lote_id,
                        root_id,
                        tuple(selection_ids),
                    )
                    if (
                        len(selection_ids) != len(set(selection_ids))
                        or frontier_key in seen_frontiers
                    ):
                        continue
                    previous_groups: list[LoteComprobanteGrupo] = []
                    for member_partition in _particiones_lectura(selection_ids):
                        previous_groups.extend(
                            list(
                                (
                                    await self.db.execute(
                                        select(LoteComprobanteGrupo).where(
                                            LoteComprobanteGrupo.id.in_(
                                                member_partition
                                            ),
                                            LoteComprobanteGrupo.empresa_id
                                            == empresa_id,
                                            LoteComprobanteGrupo.lote_id
                                            == previous_lote_id,
                                            LoteComprobanteGrupo.ambiente.in_(
                                                ambientes
                                            ),
                                        )
                                    )
                                ).scalars()
                            )
                        )
                    previous_groups.sort(key=lambda item: int(item.id))
                    if len(previous_groups) != len(
                        selection_ids
                    ) or selection != self._seleccion_material(previous_groups):
                        continue
                    seen_frontiers.add(frontier_key)
                    valid_durable_selection = True
                    await self._procesar_frontera_historica(
                        control,
                        grupos,
                        previous_lote=previous_lote,
                        previous_groups=previous_groups,
                        previous_lote_id=previous_lote_id,
                        source_operation_id=root_id,
                        current_counter=current_counter,
                        physical_stats=physical_stats,
                        physical_amounts=physical_amounts,
                        operacion_id=operacion_id,
                    )
                    del previous_groups
                if len(operation_rows) < HISTORICAL_READ_WINDOW:
                    break
                operation_watermark = (
                    int(operation_rows[-1][1]),
                    int(operation_rows[-1][0]),
                )
            if valid_durable_selection:
                del previous_lote
                continue
            previous_groups: list[LoteComprobanteGrupo] = []
            physical_ids = (
                None
                if physical_stats["count"] == len(grupos)
                else candidate_group_ids[previous_lote_id]
            )
            if physical_ids is None:
                previous_groups = list(
                    (
                        await self.db.execute(
                            select(LoteComprobanteGrupo)
                            .where(
                                LoteComprobanteGrupo.empresa_id == empresa_id,
                                LoteComprobanteGrupo.lote_id == previous_lote_id,
                                LoteComprobanteGrupo.ambiente.in_(ambientes),
                            )
                            .order_by(LoteComprobanteGrupo.id)
                        )
                    ).scalars()
                )
            else:
                for member_partition in _particiones_lectura(physical_ids):
                    previous_groups.extend(
                        list(
                            (
                                await self.db.execute(
                                    select(LoteComprobanteGrupo).where(
                                        LoteComprobanteGrupo.id.in_(member_partition),
                                        LoteComprobanteGrupo.empresa_id == empresa_id,
                                        LoteComprobanteGrupo.lote_id
                                        == previous_lote_id,
                                        LoteComprobanteGrupo.ambiente.in_(ambientes),
                                    )
                                )
                            ).scalars()
                        )
                    )
                previous_groups.sort(key=lambda item: int(item.id))
            await self._procesar_frontera_historica(
                control,
                grupos,
                previous_lote=previous_lote,
                previous_groups=previous_groups,
                previous_lote_id=previous_lote_id,
                source_operation_id=None,
                current_counter=current_counter,
                physical_stats=physical_stats,
                physical_amounts=physical_amounts,
                operacion_id=operacion_id,
            )
            del previous_groups
            del previous_lote

    async def _procesar_frontera_historica(
        self,
        control: dict[str, Any],
        grupos: list[LoteComprobanteGrupo],
        *,
        previous_lote: LoteComprobante,
        previous_groups: list[LoteComprobanteGrupo],
        previous_lote_id: int,
        source_operation_id: int | None,
        current_counter: Counter[Any],
        physical_stats: dict[str, Any],
        physical_amounts: list[tuple[str | None, Decimal, int]],
        operacion_id: int | None,
    ) -> None:
        if not previous_groups:
            return
        evidence_by_group = await self._evidencia_por_grupo(previous_groups)
        coverage = (
            self._coverage(previous_groups)
            if source_operation_id is not None
            else physical_stats["coverage"]
        )
        previous_counter = Counter(
            group.huella_fiscal_completa for group in previous_groups
        )
        previous_set_is_complete = source_operation_id is not None or (
            physical_stats["count"] == len(previous_groups)
            and len(previous_groups) == len(grupos)
        )
        full = (
            coverage != "no_comprobable"
            and previous_set_is_complete
            and current_counter == previous_counter
        )
        matches: Iterator[
            tuple[
                LoteComprobanteGrupo,
                LoteComprobanteGrupo,
                list[str],
                int | None,
            ]
        ]
        if full:
            previous_by_hash: dict[
                str | None, list[LoteComprobanteGrupo]
            ] = defaultdict(list)
            for previous in previous_groups:
                previous_by_hash[previous.huella_fiscal_completa].append(previous)
            for bucket in previous_by_hash.values():
                bucket.sort(key=lambda item: int(item.id))

            def iter_matches() -> (
                Iterator[
                    tuple[
                        LoteComprobanteGrupo,
                        LoteComprobanteGrupo,
                        list[str],
                        int | None,
                    ]
                ]
            ):
                ordinals: Counter[str | None] = Counter()
                for current in sorted(grupos, key=lambda item: int(item.id)):
                    bucket = previous_by_hash[current.huella_fiscal_completa]
                    ordinal = ordinals[current.huella_fiscal_completa]
                    ordinals[current.huella_fiscal_completa] += 1
                    yield current, bucket.pop(0), ["contenido_completo"], ordinal

            matches = iter_matches()
        else:
            matches = iter(())
        tipo = "historica_completa" if full else "historica_parcial_receptor"
        relevant_previous: dict[int, LoteComprobanteGrupo] = {}
        authorized: dict[int, LoteComprobanteGrupo] = {}
        reserved: dict[int, LoteComprobanteGrupo] = {}
        uncertain: dict[int, LoteComprobanteGrupo] = {}
        affected_ids: set[int] = set()
        authorized_current_ids: set[int] = set()
        antecedent_key = _sha256(
            {
                "lote_id": previous_lote_id,
                "operacion_raiz_id": source_operation_id,
                "seleccion": sorted(int(group.id) for group in previous_groups),
            }
        )
        for current, previous, fields, ordinal in matches:
            current_id = int(current.id)
            previous_id = int(previous.id)
            relevant_previous[previous_id] = previous
            affected_ids.add(current_id)
            is_authorized = previous.estado in ESTADOS_AUTORIZADOS
            is_uncertain = previous.estado in ESTADOS_INCIERTOS
            is_reserved = (
                previous.duplicados_reserva_operacion_id is not None
                and previous.duplicados_reserva_operacion_id != operacion_id
                and not is_authorized
                and not is_uncertain
            )
            if is_authorized:
                authorized[previous_id] = previous
                authorized_current_ids.add(current_id)
                control["_afectados_importes"][current_id] = (
                    current.moneda_duplicados,
                    Decimal(str(current.total_estimado or 0)),
                )
            elif is_uncertain:
                uncertain[previous_id] = previous
            elif is_reserved:
                reserved[previous_id] = previous
            relevance = (
                "autorizado"
                if is_authorized
                else "incierto"
                if is_uncertain
                else "reservado"
                if is_reserved
                else None
            )
            if relevance is None:
                continue
            comparable = {
                "tipo_comprobante": current.tipo_comprobante,
                "punto_venta_numero": current.punto_venta_numero,
                "fecha_emision": current.fecha_emision_normalizada,
                "total_centavos": current.total_centavos,
                "moneda": current.moneda_duplicados,
                "cotizacion": decimal_canonico(current.cotizacion_duplicados or 1),
            }
            identity = {
                "comparable": comparable,
                "huella": current.huella_fiscal_completa,
            }
            block_snapshot = {
                "origen": "lote",
                "tipo_coincidencia": tipo,
                "campos_coincidentes": fields,
                "lote_anterior_id": previous_lote_id,
                "multiplicidad_total": int(
                    current_counter[current.huella_fiscal_completa]
                ),
            }
            self._registrar_miembro_compacto(
                control,
                clase="completa",
                antecedente_clave=antecedent_key,
                identidad_bloque=identity,
                snapshot_bloque=block_snapshot,
                lado="actual",
                miembro_clave=f"g-{current_id}",
                grupo_id=current_id,
                comprobante_id=None,
                nombre_hash=current.identidad_nombre_hash,
                documento_hash=current.identidad_documento_hash,
                ordinal=ordinal,
                relevancia="actual",
                snapshot=self._snapshot_actual(current),
            )
            self._registrar_miembro_compacto(
                control,
                clase="completa",
                antecedente_clave=antecedent_key,
                identidad_bloque=identity,
                snapshot_bloque=block_snapshot,
                lado="anterior",
                miembro_clave=f"g-{previous_id}",
                grupo_id=previous_id,
                comprobante_id=None,
                nombre_hash=previous.identidad_nombre_hash,
                documento_hash=previous.identidad_documento_hash,
                ordinal=ordinal,
                relevancia=relevance,
                snapshot=self._snapshot_anterior_grupo(
                    previous,
                    lote_id=previous_lote_id,
                    evidence=evidence_by_group.get(previous_id, {}),
                    relevancia=relevance,
                ),
            )
        if not full:
            partial = self._agregar_bloques_parciales(
                control,
                current_groups=grupos,
                previous_groups=previous_groups,
                previous_lote_id=previous_lote_id,
                source_operation_id=source_operation_id,
                operation_id=operacion_id,
                evidence_by_group=evidence_by_group,
                tipo=tipo,
            )
            affected_ids = partial["affected_ids"]
            relevant_previous = partial["relevant_previous"]
            authorized = partial["authorized"]
            reserved = partial["reserved"]
            uncertain = partial["uncertain"]
            authorized_current_ids = partial["authorized_current_ids"]
        if not affected_ids:
            return
        authorized_groups = list(authorized.values())
        reserved_groups = list(reserved.values())
        uncertain_groups = list(uncertain.values())
        if authorized_groups:
            control["aceptacion_requerida"] = True
        control["tipos_coincidencia"].append(tipo)
        previous_amounts = (
            _desglosar_importes(
                [
                    (
                        group.moneda_duplicados,
                        Decimal(str(group.total_estimado or 0)),
                    )
                    for group in previous_groups
                ]
            )
            if source_operation_id is not None
            else _desglosar_importes_agregados(physical_amounts)
        )
        authorized_amounts = _desglosar_importes(
            [
                (
                    current.moneda_duplicados,
                    Decimal(str(current.total_estimado or 0)),
                )
                for current in grupos
                if int(current.id) in authorized_current_ids
            ]
        )
        authorized_evidence = [
            evidence_by_group.get(int(group.id), {}) for group in authorized_groups
        ]
        result_times = [
            evidence.get("resultado_fiscal_at")
            for evidence in authorized_evidence
            if evidence.get("resultado_fiscal_at") is not None
        ]
        reliable_time = bool(authorized_groups) and len(result_times) == len(
            authorized_groups
        )
        control["antecedentes_resumen"].append(
            {
                "origen": "lote",
                "lote_id": previous_lote_id,
                "nombre_archivo": previous_lote.nombre_archivo,
                "comprobante_ref": None,
                "tipo_coincidencia": tipo,
                "cobertura": coverage,
                "cantidad_lote_anterior": (
                    len(previous_groups)
                    if source_operation_id is not None
                    else physical_stats["count"]
                ),
                "cantidad_coincidente": len(affected_ids),
                "cantidad_autorizada": len(authorized_groups),
                "cantidad_solo_validada": sum(
                    group.estado == "validado" for group in relevant_previous.values()
                ),
                "cantidad_reservada_en_curso": len(reserved_groups),
                "cantidad_fallida": sum(
                    group.estado == "fallido" for group in relevant_previous.values()
                ),
                "cantidad_incierta": len(uncertain_groups),
                "importe_lote_anterior": _importe_escalar(previous_amounts),
                "importe_lote_actual": control["importe_actual"],
                "importe_afectado": _importe_escalar(authorized_amounts),
                "importes_lote_actual": control["importes_actuales"],
                "importes_lote_anterior": previous_amounts,
                "importes_afectados": authorized_amounts,
                "emitido_desde": min(result_times) if reliable_time else None,
                "emitido_hasta": max(result_times) if reliable_time else None,
                "hora_confiable": reliable_time,
                "solicitantes": self._solicitantes_desde_evidencia(authorized_evidence),
            }
        )

    async def _agregar_individuales_legacy(
        self,
        control: dict[str, Any],
        grupos: list[LoteComprobanteGrupo],
        *,
        empresa_id: int,
    ) -> None:
        idempotencia = IdempotenciaFiscalService(self.db)
        points: dict[int, PuntoVenta | None] = {}
        signatures: dict[
            str,
            tuple[list[Any], dict[int, IntentoEmisionFiscal]],
        ] = {}
        for grupo in grupos:
            if not grupo.payload_json or not grupo.punto_venta_id:
                continue
            try:
                request = EmitirComprobanteRequest.model_validate(grupo.payload_json)
            except Exception:
                control["cobertura"] = "no_comprobable"
                continue
            point_id = int(grupo.punto_venta_id)
            if point_id not in points:
                points[point_id] = (
                    await self.db.execute(
                        select(PuntoVenta).where(
                            PuntoVenta.id == point_id,
                            PuntoVenta.empresa_id == empresa_id,
                        )
                    )
                ).scalar_one_or_none()
            punto = points[point_id]
            if punto is None:
                continue
            firma = {
                "predicado": "idempotencia_fiscal.buscar_duplicados_logicos_lote/1",
                "argumentos": {
                    "empresa_id": int(request.empresa_id),
                    "punto_venta_id": point_id,
                    "punto_venta_numero": int(punto.numero),
                    "tipo_comprobante": int(request.tipo_comprobante),
                    "fecha_emision": request.fecha_emision.isoformat(),
                    "total": decimal_dos_posiciones(grupo.total_estimado),
                    "receptor_numero_documento": str(request.numero_documento or ""),
                },
                "huella_logica": idempotencia.calcular_huella_logica(
                    request=request,
                    punto_venta_numero=punto.numero,
                    total=Decimal(str(grupo.total_estimado)),
                ),
            }
            signature_key = _json_canonico(firma)
            cached = signatures.get(signature_key)
            if cached is None:
                matches = await idempotencia.buscar_duplicados_logicos_lote(
                    request=request,
                    punto_venta=punto,
                    total=Decimal(str(grupo.total_estimado)),
                )
                matches = sorted(matches, key=lambda item: int(item.id))
                match_ids = [int(match.id) for match in matches]
                linked_ids = set()
                for match_partition in _particiones_parametros(match_ids):
                    linked_ids.update(
                        (
                            await self.db.execute(
                                select(IntentoEmisionFiscal.comprobante_id).where(
                                    IntentoEmisionFiscal.comprobante_id.in_(
                                        match_partition
                                    ),
                                    IntentoEmisionFiscal.grupo_id.is_not(None),
                                )
                            )
                        ).scalars()
                    )
                individual_matches = [
                    match for match in matches if int(match.id) not in linked_ids
                ]
                individual_ids = [int(match.id) for match in individual_matches]
                attempts = []
                for individual_partition in _particiones_parametros(individual_ids):
                    attempts.extend(
                        list(
                            (
                                await self.db.execute(
                                    select(IntentoEmisionFiscal)
                                    .options(
                                        selectinload(IntentoEmisionFiscal.operacion)
                                    )
                                    .where(
                                        IntentoEmisionFiscal.comprobante_id.in_(
                                            individual_partition
                                        ),
                                        IntentoEmisionFiscal.estado == "autorizado",
                                    )
                                    .order_by(
                                        IntentoEmisionFiscal.comprobante_id,
                                        IntentoEmisionFiscal.resultado_fiscal_at.desc().nulls_last(),
                                        IntentoEmisionFiscal.created_at.desc().nulls_last(),
                                        IntentoEmisionFiscal.id.desc(),
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                    )
                latest_attempt: dict[int, IntentoEmisionFiscal] = {}
                for attempt in attempts:
                    if attempt.comprobante_id is not None:
                        latest_attempt.setdefault(int(attempt.comprobante_id), attempt)
                cached = (individual_matches, latest_attempt)
                signatures[signature_key] = cached
            individual_matches, latest_attempt = cached
            if not individual_matches:
                continue
            for match in individual_matches:
                attempt = latest_attempt.get(int(match.id))
                evidence = {
                    "operacion_id": attempt.operacion_id if attempt else None,
                    "usuario_id": attempt.usuario_id if attempt else None,
                    "nombre": (
                        attempt.solicitante_nombre_snapshot if attempt else None
                    ),
                    "solicitud_emision_at": _datetime_utc(
                        attempt.operacion.solicitud_emision_at
                        if attempt and attempt.operacion
                        else None
                    ),
                    "solicitud_arca_at": _datetime_utc(
                        attempt.solicitud_arca_at if attempt else None
                    ),
                    "resultado_fiscal_at": _datetime_utc(
                        attempt.resultado_fiscal_at if attempt else None
                    ),
                }
                control["tipos_coincidencia"].append("historica_individual_legacy")
                control["aceptacion_requerida"] = True
                control["_afectados_importes"][int(grupo.id)] = (
                    grupo.moneda_duplicados,
                    Decimal(str(grupo.total_estimado or 0)),
                )
                importes_match = _desglosar_importes(
                    [(match.moneda, Decimal(str(match.total)))]
                )
                control["antecedentes_resumen"].append(
                    {
                        "origen": "comprobante_individual",
                        "lote_id": None,
                        "nombre_archivo": None,
                        "comprobante_ref": f"comprobante-{match.id}",
                        "tipo_coincidencia": "historica_individual_legacy",
                        "cobertura": "parcial_legacy",
                        "cantidad_lote_anterior": None,
                        "cantidad_coincidente": 1,
                        "cantidad_autorizada": 1,
                        "cantidad_solo_validada": 0,
                        "cantidad_reservada_en_curso": 0,
                        "cantidad_fallida": 0,
                        "cantidad_incierta": 0,
                        "importe_lote_anterior": None,
                        "importe_lote_actual": control["importe_actual"],
                        "importe_afectado": _importe_escalar(importes_match),
                        "importes_lote_actual": control["importes_actuales"],
                        "importes_lote_anterior": None,
                        "importes_afectados": importes_match,
                        "emitido_desde": evidence["resultado_fiscal_at"],
                        "emitido_hasta": evidence["resultado_fiscal_at"],
                        "hora_confiable": (evidence["resultado_fiscal_at"] is not None),
                        "solicitantes": self._solicitantes_desde_evidencia([evidence]),
                    }
                )
                block_snapshot = {
                    "origen": "comprobante_individual",
                    "tipo_coincidencia": "historica_individual_legacy",
                    "campos_coincidentes": ["predicado_individual_vigente"],
                }
                self._registrar_miembro_compacto(
                    control,
                    clase="individual_legacy",
                    antecedente_clave=None,
                    identidad_bloque=firma,
                    snapshot_bloque=block_snapshot,
                    lado="actual",
                    miembro_clave=f"g-{int(grupo.id)}",
                    grupo_id=int(grupo.id),
                    comprobante_id=None,
                    nombre_hash=grupo.identidad_nombre_hash,
                    documento_hash=grupo.identidad_documento_hash,
                    ordinal=None,
                    relevancia="actual",
                    snapshot=self._snapshot_actual(grupo),
                )
                self._registrar_miembro_compacto(
                    control,
                    clase="individual_legacy",
                    antecedente_clave=None,
                    identidad_bloque=firma,
                    snapshot_bloque=block_snapshot,
                    lado="anterior",
                    miembro_clave=f"c-{int(match.id)}",
                    grupo_id=None,
                    comprobante_id=int(match.id),
                    nombre_hash=None,
                    documento_hash=None,
                    ordinal=None,
                    relevancia="autorizado",
                    snapshot={
                        "decision": {
                            "comprobante_id": int(match.id),
                            "estado": "autorizado",
                        },
                        "presentacion": {
                            "lote_anterior_id": None,
                            "grupo_anterior_id": None,
                            "comprobante_anterior_ref": f"comprobante-{match.id}",
                            "estado_grupo_anterior": None,
                            "operacion_anterior_ref": (
                                f"op-{evidence['operacion_id']}"
                                if evidence["operacion_id"] is not None
                                else None
                            ),
                            "solicitantes": self._solicitantes_desde_evidencia(
                                [evidence]
                            ),
                            "solicitud_emision_at": evidence["solicitud_emision_at"],
                            "solicitud_arca_at": evidence["solicitud_arca_at"],
                            "resultado_fiscal_at": evidence["resultado_fiscal_at"],
                            "hora_confiable": (
                                evidence["resultado_fiscal_at"] is not None
                            ),
                        },
                    },
                )

    @staticmethod
    def _registrar_miembro_compacto(
        control: dict[str, Any],
        *,
        clase: str,
        antecedente_clave: str | None,
        identidad_bloque: dict[str, Any],
        snapshot_bloque: dict[str, Any],
        lado: str,
        miembro_clave: str,
        grupo_id: int | None,
        comprobante_id: int | None,
        nombre_hash: str | None,
        documento_hash: str | None,
        ordinal: int | None,
        relevancia: str,
        snapshot: dict[str, Any],
    ) -> None:
        """Agrega una pertenencia sin expandir las parejas representadas."""
        bloque_clave = _sha256(
            {
                "dominio": RELACION_FORMATO,
                "clase": clase,
                "antecedente": antecedente_clave,
                "identidad": identidad_bloque,
            }
        )
        block = control["_bloques"].setdefault(
            bloque_clave,
            {
                "bloque_clave": bloque_clave,
                "clase": clase,
                "antecedente_clave": antecedente_clave,
                "snapshot": snapshot_bloque,
                "miembros": {},
            },
        )
        key = (lado, miembro_clave)
        candidate = {
            "lado": lado,
            "miembro_clave": miembro_clave,
            "grupo_id": grupo_id,
            "comprobante_id": comprobante_id,
            "nombre_hash": nombre_hash,
            "documento_hash": documento_hash,
            "ordinal": ordinal,
            "relevancia": relevancia,
            "snapshot": snapshot,
        }
        existing = block["miembros"].get(key)
        if existing is not None and existing != candidate:
            raise DuplicadosLoteError(
                "La relación compacta produjo una pertenencia contradictoria."
            )
        block["miembros"][key] = candidate

    @staticmethod
    def _snapshot_actual(
        grupo: LoteComprobanteGrupo,
    ) -> dict[str, Any]:
        return {
            "decision": {
                "grupo_id": int(grupo.id),
                "huella": grupo.huella_fiscal_completa,
                "nombre_hash": grupo.identidad_nombre_hash,
                "documento_hash": grupo.identidad_documento_hash,
                "importe": decimal_dos_posiciones(grupo.total_estimado),
                "moneda": grupo.moneda_duplicados,
                "cotizacion": (
                    decimal_canonico(grupo.cotizacion_duplicados)
                    if grupo.cotizacion_duplicados is not None
                    else None
                ),
            },
            "presentacion": {
                "grupo_id": int(grupo.id),
                "comprobante_ref": str(grupo.comprobante_ref),
                "importe": decimal_dos_posiciones(grupo.total_estimado),
                "moneda": grupo.moneda_duplicados,
                "cotizacion": (
                    decimal_canonico(grupo.cotizacion_duplicados)
                    if grupo.cotizacion_duplicados is not None
                    else None
                ),
            },
        }

    @staticmethod
    def _snapshot_anterior_grupo(
        grupo: LoteComprobanteGrupo,
        *,
        lote_id: int,
        evidence: dict[str, Any],
        relevancia: str,
    ) -> dict[str, Any]:
        return {
            "decision": {
                "grupo_id": int(grupo.id),
                "lote_id": lote_id,
                "huella": grupo.huella_fiscal_completa,
                "nombre_hash": grupo.identidad_nombre_hash,
                "documento_hash": grupo.identidad_documento_hash,
                "estado": grupo.estado,
                "relevancia": relevancia,
                "reserva_operacion_id": (
                    int(evidence["operacion_id"])
                    if relevancia == "reservado"
                    and evidence.get("procedencia") == "reserva_operacion_propietaria"
                    and evidence.get("operacion_id") is not None
                    else None
                ),
                "reserva_vinculo_hash": (
                    _sha256(
                        {
                            "grupo_id": int(grupo.id),
                            "reserva_operacion_id": int(
                                grupo.duplicados_reserva_operacion_id
                            ),
                        }
                    )
                    if relevancia == "reservado"
                    and grupo.duplicados_reserva_operacion_id is not None
                    else None
                ),
                "procedencia_operacion_id": evidence.get("operacion_id"),
                "procedencia": evidence.get("procedencia"),
            },
            "presentacion": {
                "lote_anterior_id": lote_id,
                "grupo_anterior_id": int(grupo.id),
                "comprobante_anterior_ref": None,
                "estado_grupo_anterior": grupo.estado,
                "operacion_anterior_ref": (
                    f"op-{evidence['operacion_id']}"
                    if evidence.get("operacion_id") is not None
                    else None
                ),
                "solicitantes": DuplicadosLotesService._solicitantes_desde_evidencia(
                    [evidence]
                ),
                "solicitud_emision_at": evidence.get("solicitud_emision_at"),
                "solicitud_arca_at": evidence.get("solicitud_arca_at"),
                "resultado_fiscal_at": evidence.get("resultado_fiscal_at"),
                "hora_confiable": evidence.get("resultado_fiscal_at") is not None,
                "detectado_at": _datetime_utc(grupo.updated_at),
            },
        }

    @staticmethod
    def _relacion_canonica(
        control: dict[str, Any], *, snapshot: bool
    ) -> list[dict[str, Any]]:
        result = []
        for block in sorted(
            control["_bloques"].values(), key=lambda item: item["bloque_clave"]
        ):
            members = []
            for member in sorted(
                block["miembros"].values(),
                key=lambda item: (
                    item["lado"],
                    item["ordinal"] if item["ordinal"] is not None else -1,
                    item["miembro_clave"],
                ),
            ):
                item = {
                    "lado": member["lado"],
                    "miembro_clave": member["miembro_clave"],
                    "grupo_id": member["grupo_id"],
                    "comprobante_id": member["comprobante_id"],
                    "nombre_hash": member["nombre_hash"],
                    "documento_hash": member["documento_hash"],
                    "ordinal": member["ordinal"],
                    "relevancia": member["relevancia"],
                    "snapshot": (
                        member["snapshot"]
                        if snapshot
                        else member["snapshot"].get("decision")
                    ),
                }
                members.append(item)
            result.append(
                {
                    "bloque_clave": block["bloque_clave"],
                    "clase": block["clase"],
                    "antecedente_clave": block["antecedente_clave"],
                    "snapshot": block["snapshot"],
                    "miembros": members,
                }
            )
        return result

    @staticmethod
    def _miembros_con_contraparte(
        source: list[LoteComprobanteGrupo],
        counterparts: list[LoteComprobanteGrupo],
        *,
        excluir_mismo_nombre_no_nulo: bool,
    ) -> list[LoteComprobanteGrupo]:
        """Filtra por existencia de contraparte mediante una distribución lineal."""
        if not source or not counterparts:
            return []
        if not excluir_mismo_nombre_no_nulo:
            return list(source)
        counterpart_names = Counter(item.identidad_nombre_hash for item in counterparts)
        counterpart_total = len(counterparts)

        def has_counterpart(item: LoteComprobanteGrupo) -> bool:
            name_hash = item.identidad_nombre_hash
            return name_hash is None or (
                counterpart_total > counterpart_names[name_hash]
            )

        return [item for item in source if has_counterpart(item)]

    def _agregar_bloques_parciales(
        self,
        control: dict[str, Any],
        *,
        current_groups: list[LoteComprobanteGrupo],
        previous_groups: list[LoteComprobanteGrupo],
        previous_lote_id: int,
        source_operation_id: int | None,
        operation_id: int | None,
        evidence_by_group: dict[int, dict[str, Any]],
        tipo: str,
    ) -> dict[str, Any]:
        def comparable(group: LoteComprobanteGrupo) -> tuple[Any, ...]:
            return (
                group.tipo_comprobante,
                group.punto_venta_numero,
                group.fecha_emision_normalizada,
                group.total_centavos,
                group.moneda_duplicados,
                decimal_canonico(group.cotizacion_duplicados or 1),
            )

        current_buckets: dict[
            tuple[str, tuple[Any, ...], str], list[LoteComprobanteGrupo]
        ] = defaultdict(list)
        previous_buckets: dict[
            tuple[str, tuple[Any, ...], str], list[LoteComprobanteGrupo]
        ] = defaultdict(list)
        for groups, buckets in (
            (current_groups, current_buckets),
            (previous_groups, previous_buckets),
        ):
            for group in groups:
                for field, value in (
                    ("nombre", group.identidad_nombre_hash),
                    ("documento", group.identidad_documento_hash),
                ):
                    if value is not None:
                        buckets[(field, comparable(group), value)].append(group)
        affected_ids: set[int] = set()
        relevant_previous: dict[int, LoteComprobanteGrupo] = {}
        authorized: dict[int, LoteComprobanteGrupo] = {}
        reserved: dict[int, LoteComprobanteGrupo] = {}
        uncertain: dict[int, LoteComprobanteGrupo] = {}
        authorized_current_ids: set[int] = set()
        antecedente_clave = _sha256(
            {
                "lote_id": previous_lote_id,
                "operacion_raiz_id": source_operation_id,
                "seleccion": sorted(int(group.id) for group in previous_groups),
            }
        )
        for key in sorted(
            current_buckets.keys() & previous_buckets.keys(),
            key=_json_canonico,
        ):
            field, comparable_key, identity_hash = key
            current = sorted(current_buckets[key], key=lambda item: int(item.id))
            previous = sorted(previous_buckets[key], key=lambda item: int(item.id))

            excluir_mismo_nombre = field == "documento"

            matched_current = self._miembros_con_contraparte(
                current,
                previous,
                excluir_mismo_nombre_no_nulo=excluir_mismo_nombre,
            )
            matched_previous = self._miembros_con_contraparte(
                previous,
                current,
                excluir_mismo_nombre_no_nulo=excluir_mismo_nombre,
            )
            if not matched_current or not matched_previous:
                continue
            affected_ids.update(int(item.id) for item in matched_current)
            relevant_previous.update((int(item.id), item) for item in matched_previous)
            relevant_prior: list[tuple[LoteComprobanteGrupo, str]] = []
            for prior in matched_previous:
                prior_id = int(prior.id)
                relevance = None
                if prior.estado in ESTADOS_AUTORIZADOS:
                    relevance = "autorizado"
                    authorized[prior_id] = prior
                elif prior.estado in ESTADOS_INCIERTOS:
                    relevance = "incierto"
                    uncertain[prior_id] = prior
                elif (
                    prior.duplicados_reserva_operacion_id is not None
                    and prior.duplicados_reserva_operacion_id != operation_id
                ):
                    relevance = "reservado"
                    reserved[prior_id] = prior
                if relevance is not None:
                    relevant_prior.append((prior, relevance))
            relevant_prior_groups = [prior for prior, _ in relevant_prior]
            matched_current_relevant = self._miembros_con_contraparte(
                matched_current,
                relevant_prior_groups,
                excluir_mismo_nombre_no_nulo=excluir_mismo_nombre,
            )
            relevant_prior_ids = {
                int(prior.id)
                for prior in self._miembros_con_contraparte(
                    relevant_prior_groups,
                    matched_current,
                    excluir_mismo_nombre_no_nulo=excluir_mismo_nombre,
                )
            }
            matched_prior_relevant = [
                (prior, relevance)
                for prior, relevance in relevant_prior
                if int(prior.id) in relevant_prior_ids
            ]
            if not matched_current_relevant or not matched_prior_relevant:
                continue
            block_snapshot = {
                "origen": "lote",
                "tipo_coincidencia": tipo,
                "campos_coincidentes": [field],
                "lote_anterior_id": previous_lote_id,
                "multiplicidad_total": None,
            }
            identity = {
                "comparable": {
                    "tipo_comprobante": comparable_key[0],
                    "punto_venta_numero": comparable_key[1],
                    "fecha_emision": comparable_key[2],
                    "total_centavos": comparable_key[3],
                    "moneda": comparable_key[4],
                    "cotizacion": comparable_key[5],
                },
                field: identity_hash,
            }
            authorized_counterparts = [
                prior
                for prior, relevance in matched_prior_relevant
                if relevance == "autorizado"
            ]
            authorized_current = {
                int(item.id)
                for item in self._miembros_con_contraparte(
                    matched_current_relevant,
                    authorized_counterparts,
                    excluir_mismo_nombre_no_nulo=excluir_mismo_nombre,
                )
            }
            for item in matched_current_relevant:
                if int(item.id) in authorized_current:
                    item_id = int(item.id)
                    authorized_current_ids.add(item_id)
                    control["_afectados_importes"][item_id] = (
                        item.moneda_duplicados,
                        Decimal(str(item.total_estimado or 0)),
                    )
                self._registrar_miembro_compacto(
                    control,
                    clase=f"parcial_{field}",
                    antecedente_clave=antecedente_clave,
                    identidad_bloque=identity,
                    snapshot_bloque=block_snapshot,
                    lado="actual",
                    miembro_clave=f"g-{int(item.id)}",
                    grupo_id=int(item.id),
                    comprobante_id=None,
                    nombre_hash=item.identidad_nombre_hash,
                    documento_hash=item.identidad_documento_hash,
                    ordinal=None,
                    relevancia="actual",
                    snapshot=self._snapshot_actual(item),
                )
            for prior, relevance in matched_prior_relevant:
                self._registrar_miembro_compacto(
                    control,
                    clase=f"parcial_{field}",
                    antecedente_clave=antecedente_clave,
                    identidad_bloque=identity,
                    snapshot_bloque=block_snapshot,
                    lado="anterior",
                    miembro_clave=f"g-{int(prior.id)}",
                    grupo_id=int(prior.id),
                    comprobante_id=None,
                    nombre_hash=prior.identidad_nombre_hash,
                    documento_hash=prior.identidad_documento_hash,
                    ordinal=None,
                    relevancia=relevance,
                    snapshot=self._snapshot_anterior_grupo(
                        prior,
                        lote_id=previous_lote_id,
                        evidence=evidence_by_group.get(int(prior.id), {}),
                        relevancia=relevance,
                    ),
                )
        return {
            "affected_ids": affected_ids,
            "relevant_previous": relevant_previous,
            "authorized": authorized,
            "reserved": reserved,
            "uncertain": uncertain,
            "authorized_current_ids": authorized_current_ids,
        }

    @staticmethod
    def _coverage(groups: list[LoteComprobanteGrupo]) -> str:
        values = {group.duplicados_cobertura for group in groups}
        if None in values or "no_comprobable" in values:
            return "no_comprobable"
        if "parcial_legacy" in values:
            return "parcial_legacy"
        return "completa"

    async def _evidencia_por_grupo(
        self, grupos: list[LoteComprobanteGrupo]
    ) -> dict[int, dict[str, Any]]:
        """Selecciona una sola evidencia proyectada por grupo de la frontera."""
        if not grupos:
            return {}
        grupos_por_id = {int(grupo.id): grupo for grupo in grupos}
        result: dict[int, dict[str, Any]] = {}
        attempt = IntentoEmisionFiscal
        operation = OperacionIdempotente
        for group_id in sorted(grupos_por_id):
            grupo = grupos_por_id[group_id]
            desired_state = (
                "autorizado"
                if grupo.estado in ESTADOS_AUTORIZADOS
                else "requiere_reconciliacion"
                if grupo.estado in ESTADOS_INCIERTOS
                else None
            )
            if desired_state is None:
                continue
            filters = [
                attempt.grupo_id == group_id,
                attempt.empresa_id == int(grupo.empresa_id),
                attempt.lote_id == grupo.lote_id,
                attempt.estado == desired_state,
                or_(attempt.ambiente.is_(None), attempt.ambiente == grupo.ambiente),
                or_(
                    attempt.operacion_id.is_(None),
                    and_(
                        operation.empresa_id == int(grupo.empresa_id),
                        operation.lote_id == grupo.lote_id,
                    ),
                ),
            ]
            if desired_state == "autorizado":
                if grupo.comprobante_id is not None:
                    filters.append(attempt.comprobante_id == grupo.comprobante_id)
                elif grupo.numero_asignado is not None or grupo.cae is not None:
                    filters.extend(
                        [
                            attempt.numero_planificado == grupo.numero_asignado,
                            attempt.cae == grupo.cae,
                        ]
                    )
            row = (
                (
                    await self.db.execute(
                        select(
                            attempt.operacion_id.label("operacion_id"),
                            attempt.usuario_id.label("usuario_id"),
                            attempt.solicitante_nombre_snapshot.label("nombre"),
                            operation.solicitud_emision_at.label(
                                "solicitud_emision_at"
                            ),
                            attempt.solicitud_arca_at.label("solicitud_arca_at"),
                            attempt.resultado_fiscal_at.label("resultado_fiscal_at"),
                            attempt.estado.label("estado"),
                        )
                        .outerjoin(operation, operation.id == attempt.operacion_id)
                        .where(*filters)
                        .order_by(
                            attempt.resultado_fiscal_at.desc().nulls_last(),
                            attempt.solicitud_arca_at.desc().nulls_last(),
                            attempt.created_at.desc().nulls_last(),
                            attempt.id.desc(),
                        )
                        .limit(1)
                    )
                )
                .mappings()
                .first()
            )
            if row is not None:
                result[group_id] = {
                    "operacion_id": row["operacion_id"],
                    "usuario_id": row["usuario_id"],
                    "nombre": row["nombre"],
                    "solicitud_emision_at": _datetime_utc(row["solicitud_emision_at"]),
                    "solicitud_arca_at": _datetime_utc(row["solicitud_arca_at"]),
                    "resultado_fiscal_at": _datetime_utc(row["resultado_fiscal_at"]),
                    "procedencia": f"intento_{row['estado']}",
                }

        reservation_ids = {
            int(grupo.duplicados_reserva_operacion_id)
            for grupo in grupos
            if grupo.duplicados_reserva_operacion_id is not None
            and grupo.estado not in ESTADOS_AUTORIZADOS | ESTADOS_INCIERTOS
        }
        reservation_owners: dict[int, Any] = {}
        for operation_partition in _particiones_lectura(
            reservation_ids, fixed_bind_count=0
        ):
            rows = list(
                (
                    await self.db.execute(
                        select(
                            operation.id.label("operacion_id"),
                            operation.empresa_id.label("operacion_empresa_id"),
                            operation.lote_id.label("operacion_lote_id"),
                            operation.duplicados_version.label("version"),
                            operation.usuario_id.label("usuario_id"),
                            operation.solicitante_nombre_snapshot.label("nombre"),
                            operation.solicitud_emision_at.label(
                                "solicitud_emision_at"
                            ),
                            LoteDuplicadoEvidencia.id.label("generacion_id"),
                            LoteDuplicadoEvidencia.operacion_id.label(
                                "generacion_operacion_id"
                            ),
                            LoteDuplicadoEvidencia.empresa_id.label(
                                "generacion_empresa_id"
                            ),
                            LoteDuplicadoEvidencia.lote_id.label("generacion_lote_id"),
                            LoteDuplicadoEvidencia.ambiente.label(
                                "generacion_ambiente"
                            ),
                        )
                        .outerjoin(
                            LoteDuplicadoEvidencia,
                            LoteDuplicadoEvidencia.id
                            == operation.duplicados_generacion_id,
                        )
                        .where(operation.id.in_(operation_partition))
                        .order_by(operation.id)
                    )
                ).mappings()
            )
            reservation_owners.update({int(row["operacion_id"]): row for row in rows})
        for group_id, grupo in grupos_por_id.items():
            reservation_id = grupo.duplicados_reserva_operacion_id
            if (
                group_id in result
                or reservation_id is None
                or grupo.estado in ESTADOS_AUTORIZADOS | ESTADOS_INCIERTOS
            ):
                continue
            owner = reservation_owners.get(int(reservation_id))
            accredited = bool(
                owner is not None
                and owner["generacion_id"] is not None
                and int(owner["operacion_empresa_id"]) == int(grupo.empresa_id)
                and owner["operacion_lote_id"] == grupo.lote_id
                and owner["version"] == VERSION
                and int(owner["generacion_operacion_id"]) == int(owner["operacion_id"])
                and int(owner["generacion_empresa_id"]) == int(grupo.empresa_id)
                and owner["generacion_lote_id"] == grupo.lote_id
                and owner["generacion_ambiente"] == grupo.ambiente
            )
            result[group_id] = {
                "operacion_id": int(owner["operacion_id"]) if accredited else None,
                "usuario_id": owner["usuario_id"] if accredited else None,
                "nombre": owner["nombre"] if accredited else None,
                "solicitud_emision_at": _datetime_utc(
                    owner["solicitud_emision_at"] if accredited else None
                ),
                "solicitud_arca_at": None,
                "resultado_fiscal_at": None,
                "procedencia": (
                    "reserva_operacion_propietaria"
                    if accredited
                    else "reserva_no_acreditada"
                ),
            }
        return result

    @staticmethod
    def _solicitantes_desde_evidencia(
        evidence_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result = []
        seen = set()
        for evidence in evidence_items:
            key = (evidence.get("usuario_id"), evidence.get("nombre"))
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "usuario_id": evidence.get("usuario_id"),
                    "nombre": evidence.get("nombre"),
                    "estado": (
                        "registrado" if evidence.get("nombre") else "no_registrado"
                    ),
                }
            )
        return result

    @staticmethod
    def _finalizar_control(
        control: dict[str, Any], *, empresa_id: int, grupos: list[LoteComprobanteGrupo]
    ) -> None:
        control["tipos_coincidencia"] = sorted(set(control["tipos_coincidencia"]))
        block = DuplicadosLotesService._bloqueo_desde_relacion(control)
        control["bloqueo_operacion_ajena"] = block
        if block:
            control["estado"] = "operacion_en_curso"
            control["aceptacion_habilitada"] = False
        elif control["aceptacion_requerida"]:
            control["estado"] = "requiere_confirmacion"
        relevant = {
            "dominio": RELACION_FORMATO,
            "version_publica": VERSION,
            "empresa_id": empresa_id,
            "ambiente": sorted({group.ambiente for group in grupos}),
            "datos_hash": control["datos_hash"],
            "seleccion_hash": control["seleccion_hash"],
            "seleccion": control["_seleccion"],
            "relacion": DuplicadosLotesService._relacion_canonica(
                control, snapshot=False
            ),
        }
        if control["_bloques"] or block:
            control["evidencia_id"] = f"v2.{_digest_b64(relevant)}"
            control[
                "detalle_url"
            ] = f"/api/lotes-comprobantes/{control['_lote_id']}/coincidencias"
        control["cantidad_afectada"] = len(control["_afectados_importes"])
        control["importes_afectados"] = _desglosar_importes(
            list(control["_afectados_importes"].values())
        )
        control["importe_afectado"] = _importe_escalar(control["importes_afectados"])

    @staticmethod
    def _bloqueo_desde_relacion(control: dict[str, Any]) -> dict[str, Any] | None:
        """Elige una presentación estable sin excluir bloqueantes del digest."""
        grouped: dict[tuple[str, int | None], dict[str, Any]] = {}
        for block in sorted(
            control["_bloques"].values(), key=lambda item: item["bloque_clave"]
        ):
            for member in block["miembros"].values():
                if member["lado"] != "anterior" or member["relevancia"] not in {
                    "incierto",
                    "reservado",
                }:
                    continue
                decision = member["snapshot"].get("decision") or {}
                operation_id = (
                    decision.get("procedencia_operacion_id")
                    if member["relevancia"] == "incierto"
                    else decision.get("reserva_operacion_id")
                )
                operation_id = int(operation_id) if operation_id is not None else None
                state = (
                    "incierta" if member["relevancia"] == "incierto" else "reservada"
                )
                presentation = member["snapshot"].get("presentacion") or {}
                candidate = grouped.setdefault(
                    (state, operation_id),
                    {
                        "estado": state,
                        "operacion_id": operation_id,
                        "grupos": set(),
                        "instantes": [],
                        "desempates": [],
                    },
                )
                candidate["grupos"].add(
                    (
                        "grupo",
                        int(member["grupo_id"]),
                    )
                    if member.get("grupo_id") is not None
                    else ("miembro", member["miembro_clave"])
                )
                candidate["instantes"].append(presentation.get("detectado_at"))
                candidate["desempates"].append(
                    (
                        block["antecedente_clave"] or "",
                        block["bloque_clave"],
                        member["miembro_clave"],
                    )
                )
        candidates = []
        for candidate in grouped.values():
            instants = sorted(
                candidate["instantes"],
                key=lambda value: (
                    value is not None,
                    _json_canonico(value),
                ),
            )
            operation_id = candidate["operacion_id"]
            public = {
                "referencia": f"op-{operation_id or 'fiscal'}",
                "estado": candidate["estado"],
                "cantidad_afectada": len(candidate["grupos"]),
                "detectado_at": instants[0] if instants else None,
            }
            candidates.append(
                (
                    (
                        0 if candidate["estado"] == "incierta" else 1,
                        operation_id is not None,
                        int(operation_id or 0),
                        instants[0] is not None if instants else False,
                        _json_canonico(instants[0] if instants else None),
                        min(candidate["desempates"]),
                    ),
                    public,
                )
            )
        return min(candidates, key=lambda item: item[0])[1] if candidates else None

    @staticmethod
    def _control_snapshot(
        control: dict[str, Any],
        *,
        selection_material: list[dict[str, Any]],
    ) -> dict[str, Any]:
        public = DuplicadosLotesService._publicable(control)
        delimitaciones = [
            {
                "bloque_clave": block["bloque_clave"],
                "clase": block["clase"],
                "antecedente_clave": block["antecedente_clave"],
                "snapshot": block["snapshot"],
            }
            for block in sorted(
                control["_bloques"].values(),
                key=lambda item: item["bloque_clave"],
            )
        ]
        return jsonable_encoder(
            {
                **public,
                "seleccion_original": selection_material,
                "formato_relacion": RELACION_FORMATO,
                "delimitaciones": delimitaciones,
                "manifiesto": {
                    "bloques": len(delimitaciones),
                    "miembros": sum(
                        len(block["miembros"]) for block in control["_bloques"].values()
                    ),
                },
            }
        )

    @staticmethod
    def _snapshot_hash(
        control: dict[str, Any], control_snapshot: dict[str, Any]
    ) -> str:
        stable_control = {
            key: value
            for key, value in control_snapshot.items()
            if key
            not in {
                "estado",
                "detalle_url",
                "aceptacion_habilitada",
                "aceptacion_requerida",
            }
        }
        return _sha256(
            {
                "dominio": RELACION_FORMATO,
                "control": stable_control,
                "relacion": DuplicadosLotesService._relacion_canonica(
                    control, snapshot=True
                ),
            }
        )

    @staticmethod
    def _validar_generacion(
        generation: LoteDuplicadoEvidencia,
        *,
        operacion_id: int,
        empresa_id: int,
        lote_id: int,
        ambiente: str,
    ) -> None:
        if generation.formato != RELACION_FORMATO:
            raise DuplicadosLoteError(
                "La generación usa una codificación de duplicados desconocida."
            )
        if (
            int(generation.operacion_id) != operacion_id
            or int(generation.empresa_id) != empresa_id
            or int(generation.lote_id) != lote_id
            or generation.ambiente != ambiente
            or not isinstance(generation.control_snapshot_json, dict)
            or len(str(generation.snapshot_hash)) != 64
        ):
            raise DuplicadosLoteError(
                "La generación de duplicados no acredita el scope fiscal exacto."
            )

    async def _validar_integridad_generacion(
        self,
        generation: LoteDuplicadoEvidencia,
        *,
        operacion_id: int,
        empresa_id: int,
        lote_id: int,
        ambiente: str,
        validar_aceptacion: bool = True,
        visitadas: set[int] | None = None,
    ) -> None:
        """Reconstruye snapshot y cadena de aceptación; cualquier desvío cierra."""
        self._validar_generacion(
            generation,
            operacion_id=operacion_id,
            empresa_id=empresa_id,
            lote_id=lote_id,
            ambiente=ambiente,
        )
        control_snapshot = generation.control_snapshot_json
        if (
            control_snapshot.get("formato_relacion") != RELACION_FORMATO
            or control_snapshot.get("evidencia_id") != generation.evidencia_id
            or not isinstance(control_snapshot.get("seleccion_original"), list)
            or not isinstance(control_snapshot.get("manifiesto"), dict)
        ):
            raise DuplicadosLoteError(
                "La cabecera no conserva un snapshot compacto verificable."
            )
        blocks = list(
            (
                await self.db.execute(
                    select(LoteDuplicadoCoincidencia)
                    .where(LoteDuplicadoCoincidencia.generacion_id == generation.id)
                    .order_by(LoteDuplicadoCoincidencia.bloque_clave)
                )
            ).scalars()
        )
        block_ids = [int(block.id) for block in blocks]
        members = []
        for block_partition in _particiones_parametros(block_ids):
            members.extend(
                list(
                    (
                        await self.db.execute(
                            select(LoteDuplicadoCoincidenciaMiembro)
                            .where(
                                LoteDuplicadoCoincidenciaMiembro.bloque_id.in_(
                                    block_partition
                                )
                            )
                            .order_by(
                                LoteDuplicadoCoincidenciaMiembro.bloque_id,
                                LoteDuplicadoCoincidenciaMiembro.lado,
                                LoteDuplicadoCoincidenciaMiembro.ordinal,
                                LoteDuplicadoCoincidenciaMiembro.miembro_clave,
                            )
                        )
                    ).scalars()
                )
            )
        members.sort(
            key=lambda item: (
                int(item.bloque_id),
                item.lado,
                item.ordinal if item.ordinal is not None else -1,
                item.miembro_clave,
            )
        )
        by_block: dict[int, list[LoteDuplicadoCoincidenciaMiembro]] = defaultdict(list)
        for member in members:
            by_block[int(member.bloque_id)].append(member)
        relation: list[dict[str, Any]] = []
        for block in blocks:
            if (
                int(block.operacion_id) != operacion_id
                or int(block.empresa_id) != empresa_id
                or int(block.lote_id) != lote_id
                or block.ambiente != ambiente
                or not isinstance(block.snapshot_json, dict)
            ):
                raise DuplicadosLoteError(
                    "Un bloque no pertenece al scope de su generación."
                )
            block_members = by_block[int(block.id)]
            actual = [item for item in block_members if item.lado == "actual"]
            previous = [item for item in block_members if item.lado == "anterior"]
            if block.clase.startswith("interna_"):
                valid_shape = (
                    len(actual) >= 2
                    and not previous
                    and all(item.ordinal is None for item in actual)
                )
            elif block.clase == "completa":
                actual_ordinals = {item.ordinal for item in actual}
                previous_ordinals = {item.ordinal for item in previous}
                valid_shape = bool(actual) and (
                    len(actual_ordinals) == len(actual)
                    and len(previous_ordinals) == len(previous)
                    and None not in actual_ordinals
                    and actual_ordinals == previous_ordinals
                )
                multiplicity = block.snapshot_json.get("multiplicidad_total")
                valid_shape = (
                    valid_shape
                    and isinstance(multiplicity, int)
                    and all(
                        0 <= int(ordinal) < multiplicity for ordinal in actual_ordinals
                    )
                )
            else:
                valid_shape = (
                    bool(actual)
                    and bool(previous)
                    and all(item.ordinal is None for item in block_members)
                )
            if not valid_shape:
                raise DuplicadosLoteError(
                    "La estructura de miembros de una generación no es válida."
                )
            canonical_members = []
            for member in block_members:
                snapshot = member.snapshot_json
                decision = (
                    snapshot.get("decision") if isinstance(snapshot, dict) else None
                )
                expected_entity_id = (
                    member.grupo_id
                    if member.grupo_id is not None
                    else member.comprobante_id
                )
                decision_entity_id = (
                    decision.get("grupo_id")
                    if member.grupo_id is not None and isinstance(decision, dict)
                    else decision.get("comprobante_id")
                    if isinstance(decision, dict)
                    else None
                )
                entity_shape = (
                    member.lado == "actual"
                    and member.grupo_id is not None
                    and member.comprobante_id is None
                    and member.relevancia == "actual"
                ) or (
                    member.lado == "anterior"
                    and member.relevancia in {"autorizado", "reservado", "incierto"}
                    and (
                        (
                            block.clase == "individual_legacy"
                            and member.grupo_id is None
                            and member.comprobante_id is not None
                        )
                        or (
                            block.clase != "individual_legacy"
                            and member.grupo_id is not None
                            and member.comprobante_id is None
                        )
                    )
                )
                if (
                    not entity_shape
                    or not isinstance(snapshot, dict)
                    or not isinstance(decision, dict)
                    or int(decision_entity_id or -1) != int(expected_entity_id or -2)
                ):
                    raise DuplicadosLoteError(
                        "Una pertenencia compacta no acredita su entidad."
                    )
                canonical_members.append(
                    {
                        "lado": member.lado,
                        "miembro_clave": member.miembro_clave,
                        "grupo_id": member.grupo_id,
                        "comprobante_id": member.comprobante_id,
                        "nombre_hash": member.nombre_hash,
                        "documento_hash": member.documento_hash,
                        "ordinal": member.ordinal,
                        "relevancia": member.relevancia,
                        "snapshot": snapshot,
                    }
                )
            relation.append(
                {
                    "bloque_clave": block.bloque_clave,
                    "clase": block.clase,
                    "antecedente_clave": block.antecedente_clave,
                    "snapshot": block.snapshot_json,
                    "miembros": sorted(
                        canonical_members,
                        key=lambda item: (
                            item["lado"],
                            item["ordinal"] if item["ordinal"] is not None else -1,
                            item["miembro_clave"],
                        ),
                    ),
                }
            )
        manifest = control_snapshot["manifiesto"]
        if manifest.get("bloques") != len(blocks) or manifest.get("miembros") != len(
            members
        ):
            raise DuplicadosLoteError(
                "La relación compacta no coincide con su manifiesto."
            )
        stable_control = {
            key: value
            for key, value in control_snapshot.items()
            if key
            not in {
                "estado",
                "detalle_url",
                "aceptacion_habilitada",
                "aceptacion_requerida",
            }
        }
        reconstructed = _sha256(
            {
                "dominio": RELACION_FORMATO,
                "control": stable_control,
                "relacion": relation,
            }
        )
        if not secrets.compare_digest(reconstructed, generation.snapshot_hash):
            raise DuplicadosLoteError(
                "El snapshot durable de duplicados perdió integridad."
            )
        if not validar_aceptacion:
            return
        acceptance_fields = (
            generation.aceptada_por_usuario_id,
            generation.aceptada_por_nombre,
            generation.aceptada_at,
        )
        if generation.aceptada_at is None:
            if any(value is not None for value in acceptance_fields) or (
                generation.aceptacion_origen_generacion_id is not None
            ):
                raise DuplicadosLoteError(
                    "La aceptación pendiente tiene auditoría contradictoria."
                )
            return
        if (
            generation.aceptacion_id is None
            or any(value is None for value in acceptance_fields)
            or generation.aceptacion_origen_generacion_id is None
        ):
            raise DuplicadosLoteError(
                "La aceptación durable no conserva su auditoría completa."
            )
        origin_id = int(generation.aceptacion_origen_generacion_id)
        if origin_id == int(generation.id):
            return
        seen = set(visitadas or ())
        if int(generation.id) in seen or origin_id in seen:
            raise DuplicadosLoteError("La cadena de aceptación contiene un ciclo.")
        seen.add(int(generation.id))
        origin = await self.db.get(LoteDuplicadoEvidencia, origin_id)
        if origin is None:
            raise DuplicadosLoteError(
                "La generación de origen de la aceptación no existe."
            )
        lineage_operations = list(
            (
                await self.db.execute(
                    select(OperacionIdempotente).where(
                        OperacionIdempotente.id.in_(
                            [int(generation.operacion_id), int(origin.operacion_id)]
                        )
                    )
                )
            ).scalars()
        )
        operations_by_id = {int(item.id): item for item in lineage_operations}
        generation_operation = operations_by_id.get(int(generation.operacion_id))
        origin_operation = operations_by_id.get(int(origin.operacion_id))
        same_root = bool(
            generation_operation is not None
            and origin_operation is not None
            and int(generation_operation.operacion_raiz_id or generation_operation.id)
            == int(origin_operation.operacion_raiz_id or origin_operation.id)
        )
        origin_snapshot = origin.control_snapshot_json
        same_lineage = (
            same_root
            and origin.empresa_id == empresa_id
            and origin.lote_id == lote_id
            and origin.ambiente == ambiente
            and origin.evidencia_id == generation.evidencia_id
            and isinstance(origin_snapshot, dict)
            and origin_snapshot.get("datos_hash") == control_snapshot.get("datos_hash")
            and origin_snapshot.get("seleccion_hash")
            == control_snapshot.get("seleccion_hash")
            and origin_snapshot.get("seleccion_original")
            == control_snapshot.get("seleccion_original")
            and origin.aceptacion_id == generation.aceptacion_id
            and origin.aceptada_por_usuario_id == generation.aceptada_por_usuario_id
            and origin.aceptada_por_nombre == generation.aceptada_por_nombre
            and _datetime_utc(origin.aceptada_at)
            == _datetime_utc(generation.aceptada_at)
        )
        if not same_lineage:
            raise DuplicadosLoteError(
                "La generación no acredita una herencia de aceptación compatible."
            )
        await self._validar_integridad_generacion(
            origin,
            operacion_id=int(origin.operacion_id),
            empresa_id=empresa_id,
            lote_id=lote_id,
            ambiente=ambiente,
            visitadas=seen,
        )

    async def _insertar_relacion(
        self,
        *,
        generation: LoteDuplicadoEvidencia,
        control: dict[str, Any],
    ) -> None:
        blocks = sorted(
            control["_bloques"].values(), key=lambda item: item["bloque_clave"]
        )
        for start in range(0, len(blocks), INSERT_BUFFER):
            rows = [
                {
                    "generacion_id": int(generation.id),
                    "operacion_id": int(generation.operacion_id),
                    "empresa_id": int(generation.empresa_id),
                    "ambiente": generation.ambiente,
                    "lote_id": int(generation.lote_id),
                    "bloque_clave": block["bloque_clave"],
                    "clase": block["clase"],
                    "antecedente_clave": block["antecedente_clave"],
                    "snapshot_json": jsonable_encoder(block["snapshot"]),
                }
                for block in blocks[start : start + INSERT_BUFFER]
            ]
            if rows:
                await self.db.execute(insert(LoteDuplicadoCoincidencia), rows)
        block_ids = dict(
            (
                await self.db.execute(
                    select(
                        LoteDuplicadoCoincidencia.bloque_clave,
                        LoteDuplicadoCoincidencia.id,
                    ).where(LoteDuplicadoCoincidencia.generacion_id == generation.id)
                )
            ).all()
        )
        member_rows: list[dict[str, Any]] = []
        for block in blocks:
            block_id = int(block_ids[block["bloque_clave"]])
            for member in sorted(
                block["miembros"].values(),
                key=lambda item: (item["lado"], item["miembro_clave"]),
            ):
                member_rows.append(
                    {
                        "bloque_id": block_id,
                        "lado": member["lado"],
                        "miembro_clave": member["miembro_clave"],
                        "grupo_id": member["grupo_id"],
                        "comprobante_id": member["comprobante_id"],
                        "nombre_hash": member["nombre_hash"],
                        "documento_hash": member["documento_hash"],
                        "ordinal": member["ordinal"],
                        "relevancia": member["relevancia"],
                        "snapshot_json": jsonable_encoder(member["snapshot"]),
                    }
                )
                if len(member_rows) == INSERT_BUFFER:
                    await self.db.execute(
                        insert(LoteDuplicadoCoincidenciaMiembro), member_rows
                    )
                    member_rows = []
        if member_rows:
            await self.db.execute(insert(LoteDuplicadoCoincidenciaMiembro), member_rows)

    async def _fuente_aceptacion_heredable(
        self,
        *,
        operation: OperacionIdempotente,
        evidencia_id: str | None,
        control_snapshot: dict[str, Any],
        ambiente: str,
    ) -> LoteDuplicadoEvidencia | None:
        if evidencia_id is None:
            return None
        root_id = int(operation.operacion_raiz_id or operation.id)
        operation_ids = list(
            (
                await self.db.execute(
                    select(OperacionIdempotente.id).where(
                        OperacionIdempotente.empresa_id == operation.empresa_id,
                        OperacionIdempotente.lote_id == operation.lote_id,
                        or_(
                            OperacionIdempotente.id == root_id,
                            OperacionIdempotente.operacion_raiz_id == root_id,
                        ),
                    )
                )
            ).scalars()
        )
        candidates = []
        for operation_partition in _particiones_parametros(operation_ids):
            query_result = await self.db.execute(
                select(LoteDuplicadoEvidencia)
                .where(
                    LoteDuplicadoEvidencia.operacion_id.in_(operation_partition),
                    LoteDuplicadoEvidencia.empresa_id == operation.empresa_id,
                    LoteDuplicadoEvidencia.lote_id == operation.lote_id,
                    LoteDuplicadoEvidencia.ambiente == ambiente,
                    LoteDuplicadoEvidencia.evidencia_id == evidencia_id,
                    LoteDuplicadoEvidencia.aceptada_at.is_not(None),
                )
                .order_by(
                    LoteDuplicadoEvidencia.created_at.desc(),
                    LoteDuplicadoEvidencia.id.desc(),
                )
            )
            candidates.extend(query_result.scalars())
        candidates.sort(
            key=lambda item: (
                _datetime_utc(item.created_at)
                or datetime.min.replace(tzinfo=timezone.utc),
                int(item.id),
            ),
            reverse=True,
        )
        for candidate in candidates:
            snapshot = candidate.control_snapshot_json
            if not isinstance(snapshot, dict):
                continue
            if (
                snapshot.get("datos_hash") == control_snapshot.get("datos_hash")
                and snapshot.get("seleccion_hash")
                == control_snapshot.get("seleccion_hash")
                and snapshot.get("seleccion_original")
                == control_snapshot.get("seleccion_original")
            ):
                if candidate.formato != RELACION_FORMATO:
                    raise DuplicadosLoteError(
                        "Una fuente de aceptación usa un formato desconocido."
                    )
                await self._validar_integridad_generacion(
                    candidate,
                    operacion_id=int(candidate.operacion_id),
                    empresa_id=int(operation.empresa_id),
                    lote_id=int(operation.lote_id),
                    ambiente=ambiente,
                )
                return candidate
        return None

    async def _publicar_generacion(
        self,
        *,
        operation: OperacionIdempotente,
        control: dict[str, Any],
        selection_material: list[dict[str, Any]],
        aceptacion_recibida: str | None,
        solicitante_nombre: str | None,
        ambiente: str,
    ) -> tuple[LoteDuplicadoEvidencia, dict[str, Any], str | None, bool]:
        control_snapshot = self._control_snapshot(
            control, selection_material=selection_material
        )
        snapshot_hash = self._snapshot_hash(control, control_snapshot)
        current = None
        if operation.duplicados_generacion_id is not None:
            current = await self.db.get(
                LoteDuplicadoEvidencia, int(operation.duplicados_generacion_id)
            )
            if current is None:
                raise DuplicadosLoteError(
                    "El puntero de duplicados referencia una generación inexistente."
                )
            await self._validar_integridad_generacion(
                current,
                operacion_id=int(operation.id),
                empresa_id=int(operation.empresa_id),
                lote_id=int(operation.lote_id),
                ambiente=ambiente,
            )
        generation = (
            current
            if current is not None
            and current.evidencia_id == control.get("evidencia_id")
            and current.snapshot_hash == snapshot_hash
            else None
        )
        if generation is None:
            current_snapshot = (
                current.control_snapshot_json
                if current is not None
                and isinstance(current.control_snapshot_json, dict)
                else {}
            )
            current_compatible = bool(
                current is not None
                and current.evidencia_id == control.get("evidencia_id")
                and current_snapshot.get("datos_hash")
                == control_snapshot.get("datos_hash")
                and current_snapshot.get("seleccion_hash")
                == control_snapshot.get("seleccion_hash")
                and current_snapshot.get("seleccion_original")
                == control_snapshot.get("seleccion_original")
            )
            inherited = (
                current
                if current_compatible
                else await self._fuente_aceptacion_heredable(
                    operation=operation,
                    evidencia_id=control.get("evidencia_id"),
                    control_snapshot=control_snapshot,
                    ambiente=ambiente,
                )
            )
            next_generation = (
                int(
                    (
                        await self.db.execute(
                            select(
                                func.coalesce(
                                    func.max(LoteDuplicadoEvidencia.generacion), 0
                                )
                            ).where(LoteDuplicadoEvidencia.operacion_id == operation.id)
                        )
                    ).scalar_one()
                )
                + 1
            )
            acceptance_id = None
            if control["aceptacion_requerida"]:
                acceptance_id = (
                    inherited.aceptacion_id
                    if inherited is not None
                    else "v2."
                    + base64.urlsafe_b64encode(secrets.token_bytes(32))
                    .decode("ascii")
                    .rstrip("=")
                )
            generation = LoteDuplicadoEvidencia(
                operacion_id=int(operation.id),
                empresa_id=int(operation.empresa_id),
                ambiente=ambiente,
                lote_id=int(operation.lote_id),
                generacion=next_generation,
                formato=RELACION_FORMATO,
                evidencia_id=control.get("evidencia_id"),
                snapshot_hash=snapshot_hash,
                control_snapshot_json=control_snapshot,
                aceptacion_id=acceptance_id,
                aceptada_por_usuario_id=(
                    inherited.aceptada_por_usuario_id
                    if inherited is not None and inherited.aceptada_at is not None
                    else None
                ),
                aceptada_por_nombre=(
                    inherited.aceptada_por_nombre
                    if inherited is not None and inherited.aceptada_at is not None
                    else None
                ),
                aceptada_at=(
                    inherited.aceptada_at
                    if inherited is not None and inherited.aceptada_at is not None
                    else None
                ),
                aceptacion_origen_generacion_id=(
                    int(inherited.id)
                    if inherited is not None and inherited.aceptada_at is not None
                    else None
                ),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(generation)
            await self.db.flush()
            await self._insertar_relacion(generation=generation, control=control)
            operation.duplicados_generacion_id = int(generation.id)
        acceptance_id = generation.aceptacion_id
        accepted = generation.aceptada_at is not None
        if (
            control["aceptacion_requerida"]
            and not accepted
            and control["aceptacion_habilitada"]
            and acceptance_id
            and secrets.compare_digest(
                str(acceptance_id), str(aceptacion_recibida or "")
            )
        ):
            now = datetime.now(timezone.utc)
            generation.aceptada_por_usuario_id = operation.usuario_id
            generation.aceptada_por_nombre = solicitante_nombre
            generation.aceptada_at = now
            generation.aceptacion_origen_generacion_id = int(generation.id)
            accepted = True
        if control["bloqueo_operacion_ajena"]:
            accepted = False
        public = self._publicable(control)
        if control["aceptacion_requerida"]:
            public["estado"] = "aceptada" if accepted else "requiere_confirmacion"
        durable = jsonable_encoder(
            {
                **public,
                "aceptacion_id": acceptance_id,
                "seleccion_original": selection_material,
                "aceptada_por_usuario_id": generation.aceptada_por_usuario_id,
                "aceptada_por_nombre": generation.aceptada_por_nombre,
                "aceptada_at": generation.aceptada_at,
                "duplicados_generacion_id": int(generation.id),
                "duplicados_generacion": int(generation.generacion),
                "formato_relacion": generation.formato,
                "testigos_individuales_ids": sorted(
                    {
                        member["comprobante_id"]
                        for block in control["_bloques"].values()
                        if block["clase"] == "individual_legacy"
                        for member in block["miembros"].values()
                        if member["lado"] == "anterior"
                        and member["comprobante_id"] is not None
                    }
                ),
                "testigos_lote_grupo_ids": sorted(
                    {
                        int(member["grupo_id"])
                        for block in control["_bloques"].values()
                        if block["clase"] != "individual_legacy"
                        for member in block["miembros"].values()
                        if member["lado"] == "anterior"
                        and member["relevancia"] == "autorizado"
                        and member["grupo_id"] is not None
                    }
                ),
            }
        )
        operation.control_duplicados_json = durable
        return generation, public, acceptance_id, accepted

    async def revalidar_operacion_lote(
        self,
        *,
        operacion_id: int,
        lote_id: int,
        empresa_id: int,
    ) -> dict[str, Any]:
        """Recalcula evidencia sobre la selección original sin abrir coordinación."""
        operation = (
            await self.db.execute(
                select(OperacionIdempotente).where(
                    OperacionIdempotente.id == operacion_id,
                    OperacionIdempotente.empresa_id == empresa_id,
                    OperacionIdempotente.lote_id == lote_id,
                    OperacionIdempotente.duplicados_version == VERSION,
                )
            )
        ).scalar_one_or_none()
        durable = operation.control_duplicados_json if operation is not None else None
        if not isinstance(durable, dict):
            raise DuplicadosLotePreflightCambioError(
                self._publicable(self._base_control([], lote_id=lote_id))
            )
        selection = durable.get("seleccion_original")
        if not isinstance(selection, list) or not selection:
            raise DuplicadosLotePreflightCambioError(
                self._publicable(self._base_control([], lote_id=lote_id))
            )
        group_ids = [
            int(item["grupo_id"])
            for item in selection
            if isinstance(item, dict) and isinstance(item.get("grupo_id"), int)
        ]
        if len(group_ids) != len(selection):
            raise DuplicadosLotePreflightCambioError(
                self._publicable(self._base_control([], lote_id=lote_id))
            )
        current = await self.calcular_control(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados=ESTADOS_SELECCION_ORIGINAL,
            grupo_ids=group_ids,
            operacion_id=operacion_id,
            incluir_interno=True,
        )
        public = self._publicable(current)
        comparison_groups = await self._grupos_actuales(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados=ESTADOS_SELECCION_ORIGINAL,
            grupo_ids=group_ids,
        )
        same_material = self._seleccion_material(comparison_groups) == selection
        ambientes = {group.ambiente for group in comparison_groups if group.ambiente}
        if len(ambientes) != 1:
            raise DuplicadosLotePreflightCambioError(public)
        expected_ambiente = str(next(iter(ambientes)))
        generation = None
        if operation.duplicados_generacion_id is not None:
            generation = await self.db.get(
                LoteDuplicadoEvidencia, int(operation.duplicados_generacion_id)
            )
        if generation is None:
            raise DuplicadosLotePreflightCambioError(public)
        try:
            await self._validar_integridad_generacion(
                generation,
                operacion_id=operacion_id,
                empresa_id=empresa_id,
                lote_id=lote_id,
                ambiente=expected_ambiente,
            )
        except DuplicadosLoteError as exc:
            raise DuplicadosLotePreflightCambioError(public) from exc
        generation_snapshot = generation.control_snapshot_json
        same_durable_header = (
            durable.get("duplicados_generacion_id") == int(generation.id)
            and durable.get("duplicados_generacion") == int(generation.generacion)
            and durable.get("formato_relacion") == RELACION_FORMATO
            and durable.get("seleccion_original")
            == generation_snapshot.get("seleccion_original")
            and durable.get("datos_hash") == generation_snapshot.get("datos_hash")
            and durable.get("seleccion_hash")
            == generation_snapshot.get("seleccion_hash")
            and durable.get("evidencia_id") == generation.evidencia_id
        )
        accepted = (
            not current["aceptacion_requerida"] or generation.aceptada_at is not None
        )
        same_evidence = generation.evidencia_id == public.get("evidencia_id")
        if not (
            same_material and same_durable_header and accepted and same_evidence
        ) or public.get("bloqueo_operacion_ajena"):
            raise DuplicadosLotePreflightCambioError(public)
        public["_duplicados_generacion_id"] = int(generation.id)
        return public

    @staticmethod
    def _publicable(control: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in control.items() if not key.startswith("_")}

    @staticmethod
    def _armar_detalle_compacto(
        *,
        clase: str,
        block_snapshot: dict[str, Any],
        current_snapshot: dict[str, Any],
        previous_snapshot: dict[str, Any] | None,
        current_document_hash: str | None,
        previous_document_hash: str | None,
    ) -> dict[str, Any]:
        current = current_snapshot.get("presentacion")
        if not isinstance(current, dict):
            raise DuplicadosLoteError(
                "Un miembro actual perdió su presentación durable."
            )
        fields = list(block_snapshot.get("campos_coincidentes") or [])
        if (
            clase == "parcial_nombre"
            and current_document_hash is not None
            and current_document_hash == previous_document_hash
            and "documento" not in fields
        ):
            fields.append("documento")
        detail = {
            "grupo_actual_id": int(current["grupo_id"]),
            "comprobante_actual_ref": str(current["comprobante_ref"]),
            "origen": block_snapshot.get("origen"),
            "tipo_coincidencia": block_snapshot.get("tipo_coincidencia"),
            "campos_coincidentes": fields,
            "lote_anterior_id": None,
            "grupo_anterior_id": None,
            "comprobante_anterior_ref": None,
            "operacion_anterior_ref": None,
            "estado_grupo_anterior": None,
            "importe": current["importe"],
            "moneda": current.get("moneda"),
            "cotizacion": current.get("cotizacion"),
            "solicitantes": [],
            "solicitud_emision_at": None,
            "solicitud_arca_at": None,
            "resultado_fiscal_at": None,
            "hora_confiable": False,
        }
        if previous_snapshot is not None:
            previous = previous_snapshot.get("presentacion")
            if not isinstance(previous, dict):
                raise DuplicadosLoteError(
                    "Un antecedente perdió su presentación durable."
                )
            detail.update(
                {key: value for key, value in previous.items() if key != "detectado_at"}
            )
        return detail

    @staticmethod
    def _total_bloque_compacto(block: dict[str, Any]) -> int:
        """Cuenta parejas por agregados de membresías, nunca materializándolas."""
        current = [
            item for item in block["miembros"].values() if item["lado"] == "actual"
        ]
        previous = [
            item for item in block["miembros"].values() if item["lado"] == "anterior"
        ]
        clase = block["clase"]
        if clase.startswith("interna_"):
            return len(current)
        if clase == "completa":
            current_ordinals = {item["ordinal"] for item in current}
            previous_ordinals = {item["ordinal"] for item in previous}
            if None in current_ordinals or current_ordinals != previous_ordinals:
                raise DuplicadosLoteError(
                    "Un bloque completo perdió su emparejamiento ordinal."
                )
            return len(current_ordinals)
        total = len(current) * len(previous)
        if clase == "parcial_documento":
            current_names = Counter(
                item["nombre_hash"]
                for item in current
                if item["nombre_hash"] is not None
            )
            previous_names = Counter(
                item["nombre_hash"]
                for item in previous
                if item["nombre_hash"] is not None
            )
            total -= sum(
                count * previous_names[name] for name, count in current_names.items()
            )
        return total

    @staticmethod
    def _clave_orden_publico(row: Any) -> tuple[Any, ...]:
        def nullable(value: Any) -> tuple[int, Any]:
            return (0, 0) if value is None else (1, value)

        return (
            int(row["grupo_actual_id"]),
            *nullable(row["lote_anterior_id"]),
            *nullable(row["grupo_anterior_id"]),
            int(row["tipo_orden"]),
            *nullable(row["comprobante_anterior_id"]),
            *nullable(row["antecedente_clave"]),
            row["bloque_clave"],
        )

    @staticmethod
    def _orden_sql_publico(relation: Any) -> list[Any]:
        return [
            relation.c.grupo_actual_id,
            case((relation.c.lote_anterior_id.is_(None), 0), else_=1),
            relation.c.lote_anterior_id,
            case((relation.c.grupo_anterior_id.is_(None), 0), else_=1),
            relation.c.grupo_anterior_id,
            relation.c.tipo_orden,
            case((relation.c.comprobante_anterior_id.is_(None), 0), else_=1),
            relation.c.comprobante_anterior_id,
            case((relation.c.antecedente_clave.is_(None), 0), else_=1),
            relation.c.antecedente_clave,
            relation.c.bloque_clave,
        ]

    @staticmethod
    def _despues_watermark(relation: Any, watermark: Any) -> Any:
        """Expande la clave pública lexicográficamente, incluidos sus NULL."""
        components = [
            (relation.c.grupo_actual_id, int(watermark["grupo_actual_id"])),
            (
                case((relation.c.lote_anterior_id.is_(None), 0), else_=1),
                0 if watermark["lote_anterior_id"] is None else 1,
            ),
            (relation.c.lote_anterior_id, watermark["lote_anterior_id"]),
            (
                case((relation.c.grupo_anterior_id.is_(None), 0), else_=1),
                0 if watermark["grupo_anterior_id"] is None else 1,
            ),
            (relation.c.grupo_anterior_id, watermark["grupo_anterior_id"]),
            (relation.c.tipo_orden, int(watermark["tipo_orden"])),
            (
                case((relation.c.comprobante_anterior_id.is_(None), 0), else_=1),
                0 if watermark["comprobante_anterior_id"] is None else 1,
            ),
            (
                relation.c.comprobante_anterior_id,
                watermark["comprobante_anterior_id"],
            ),
            (
                case((relation.c.antecedente_clave.is_(None), 0), else_=1),
                0 if watermark["antecedente_clave"] is None else 1,
            ),
            (relation.c.antecedente_clave, watermark["antecedente_clave"]),
            (relation.c.bloque_clave, watermark["bloque_clave"]),
        ]
        prefixes = []
        greater = []
        for expression, value in components:
            if value is not None:
                greater.append(and_(*prefixes, expression > value))
            prefixes.append(
                expression.is_(None) if value is None else expression == value
            )
        return or_(*greater)

    @staticmethod
    def _live_member_buffer() -> int:
        """Acota miembros considerando sus cinco binds y los binds fijos."""
        return max(
            1,
            min(
                LIVE_QUERY_MEMBER_BUFFER,
                (READ_PARAMETER_BUFFER - LIVE_QUERY_FIXED_BIND_BUDGET)
                // LIVE_MEMBER_BIND_COUNT,
            ),
        )

    @staticmethod
    def _miembros_cte(members: list[dict[str, Any]], *, name: str) -> Any:
        rows = [
            select(
                literal(member["miembro_clave"]).cast(String).label("miembro_clave"),
                literal(member["grupo_id"]).cast(Integer).label("grupo_id"),
                literal(member["comprobante_id"]).cast(Integer).label("comprobante_id"),
                literal(member["nombre_hash"]).cast(String).label("nombre_hash"),
                literal(member["ordinal"]).cast(Integer).label("ordinal"),
            )
            for member in members
        ]
        if not rows:
            raise DuplicadosLoteError("Un bloque compacto quedó sin miembros.")
        query = rows[0] if len(rows) == 1 else union_all(*rows)
        return query.cte(name)

    @classmethod
    def _proyeccion_viva(
        cls,
        *,
        block: dict[str, Any],
        current: Any,
        previous: Any | None,
    ) -> list[Any]:
        previous_id = (
            previous.c.miembro_clave
            if previous is not None
            else literal(None).cast(String)
        )
        previous_group_id = (
            previous.c.grupo_id if previous is not None else literal(None).cast(Integer)
        )
        previous_receipt_id = (
            previous.c.comprobante_id
            if previous is not None
            else literal(None).cast(Integer)
        )
        snapshot = block["snapshot"]
        return [
            current.c.grupo_id.label("grupo_actual_id"),
            literal(snapshot.get("lote_anterior_id"))
            .cast(Integer)
            .label("lote_anterior_id"),
            previous_group_id.label("grupo_anterior_id"),
            literal(TIPO_ORDEN_PUBLICO[block["clase"]])
            .cast(Integer)
            .label("tipo_orden"),
            previous_receipt_id.label("comprobante_anterior_id"),
            literal(block["antecedente_clave"]).cast(String).label("antecedente_clave"),
            literal(block["bloque_clave"]).cast(String).label("bloque_clave"),
            current.c.miembro_clave.label("actual_clave"),
            previous_id.label("anterior_clave"),
        ]

    @classmethod
    def _consultas_bloque_vivo(cls, block: dict[str, Any]) -> Iterator[Any]:
        members = list(block["miembros"].values())
        current = sorted(
            (item for item in members if item["lado"] == "actual"),
            key=lambda item: item["miembro_clave"],
        )
        previous = sorted(
            (item for item in members if item["lado"] == "anterior"),
            key=lambda item: item["miembro_clave"],
        )
        clase = block["clase"]
        member_buffer_limit = cls._live_member_buffer()
        if clase.startswith("interna_"):
            for index in range(0, len(current), member_buffer_limit):
                actual = cls._miembros_cte(
                    current[index : index + member_buffer_limit],
                    name=f"v_actual_{index}",
                )
                yield select(
                    *cls._proyeccion_viva(block=block, current=actual, previous=None)
                ).select_from(actual)
            return
        if clase == "completa":
            previous_by_ordinal = {item["ordinal"]: item for item in previous}
            pairs = []
            for actual in current:
                prior = previous_by_ordinal.get(actual["ordinal"])
                if actual["ordinal"] is None or prior is None:
                    raise DuplicadosLoteError(
                        "Un bloque completo perdió su emparejamiento ordinal."
                    )
                pairs.append((actual, prior))
            pair_buffer = max(1, member_buffer_limit // 2)
            for index in range(0, len(pairs), pair_buffer):
                partition = pairs[index : index + pair_buffer]
                actual = cls._miembros_cte(
                    [pair[0] for pair in partition], name=f"v_actual_{index}"
                )
                prior = cls._miembros_cte(
                    [pair[1] for pair in partition], name=f"v_anterior_{index}"
                )
                yield select(
                    *cls._proyeccion_viva(block=block, current=actual, previous=prior)
                ).select_from(actual.join(prior, prior.c.ordinal == actual.c.ordinal))
            return
        member_buffer = max(1, member_buffer_limit // 2)
        for current_index in range(0, len(current), member_buffer):
            for previous_index in range(0, len(previous), member_buffer):
                actual = cls._miembros_cte(
                    current[current_index : current_index + member_buffer],
                    name=f"v_actual_{current_index}_{previous_index}",
                )
                prior = cls._miembros_cte(
                    previous[previous_index : previous_index + member_buffer],
                    name=f"v_anterior_{current_index}_{previous_index}",
                )
                query = select(
                    *cls._proyeccion_viva(block=block, current=actual, previous=prior)
                ).select_from(actual.join(prior, literal(True)))
                if clase == "parcial_documento":
                    query = query.where(
                        or_(
                            actual.c.nombre_hash.is_(None),
                            prior.c.nombre_hash.is_(None),
                            actual.c.nombre_hash != prior.c.nombre_hash,
                        )
                    )
                yield query

    async def _pagina_relacion_viva(
        self,
        control: dict[str, Any],
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Pagina una relación viva mediante SQL sin crear una generación durable."""
        blocks = control["_bloques"]
        total = sum(self._total_bloque_compacto(block) for block in blocks.values())
        if not total or offset >= total:
            return [], total
        member_buffer = self._live_member_buffer()
        selected = []
        remaining_offset = offset
        watermark = None
        while len(selected) < limit:
            heap = []
            sequence = 0
            for block in blocks.values():
                for query in self._consultas_bloque_vivo(block):
                    relation = query.subquery()
                    statement = select(relation)
                    if watermark is not None:
                        statement = statement.where(
                            self._despues_watermark(relation, watermark)
                        )
                    statement = (
                        statement.order_by(*self._orden_sql_publico(relation))
                        .limit(member_buffer)
                        .execution_options(
                            yield_per=1, stream_results=True, max_row_buffer=1
                        )
                    )
                    result = await self.db.stream(statement)
                    try:
                        async for row in result.mappings():
                            key = self._clave_orden_publico(row)
                            item = (_ReverseOrderKey(key), sequence, row)
                            sequence += 1
                            if len(heap) < member_buffer:
                                heapq.heappush(heap, item)
                            elif key < heap[0][0].key:
                                heapq.heapreplace(heap, item)
                    finally:
                        await result.close()
            if not heap:
                break
            round_rows = sorted(
                (item[2] for item in heap), key=self._clave_orden_publico
            )
            start = min(remaining_offset, len(round_rows))
            remaining_offset -= start
            take = min(limit - len(selected), len(round_rows) - start)
            if take:
                selected.extend(round_rows[start : start + take])
            consumed = start + take
            if consumed:
                watermark = round_rows[consumed - 1]
            if consumed < len(round_rows) or len(round_rows) < member_buffer:
                break
        items = []
        for row in selected:
            block = blocks[row["bloque_clave"]]
            actual = block["miembros"][("actual", row["actual_clave"])]
            prior = (
                block["miembros"][("anterior", row["anterior_clave"])]
                if row["anterior_clave"] is not None
                else None
            )
            items.append(
                self._armar_detalle_compacto(
                    clase=block["clase"],
                    block_snapshot=block["snapshot"],
                    current_snapshot=actual["snapshot"],
                    previous_snapshot=prior["snapshot"] if prior else None,
                    current_document_hash=actual["documento_hash"],
                    previous_document_hash=prior["documento_hash"] if prior else None,
                )
            )
        return items, total

    async def _validar_estructura_generacion(
        self, generation: LoteDuplicadoEvidencia
    ) -> None:
        manifest = generation.control_snapshot_json.get("manifiesto")
        if not isinstance(manifest, dict):
            raise DuplicadosLoteError("La generación no conserva su manifiesto.")
        block_count = int(
            (
                await self.db.execute(
                    select(func.count(LoteDuplicadoCoincidencia.id)).where(
                        LoteDuplicadoCoincidencia.generacion_id == generation.id
                    )
                )
            ).scalar_one()
        )
        member_count = int(
            (
                await self.db.execute(
                    select(func.count(LoteDuplicadoCoincidenciaMiembro.id))
                    .join(LoteDuplicadoCoincidencia)
                    .where(LoteDuplicadoCoincidencia.generacion_id == generation.id)
                )
            ).scalar_one()
        )
        if (
            manifest.get("bloques") != block_count
            or manifest.get("miembros") != member_count
        ):
            raise DuplicadosLoteError(
                "La relación compacta no coincide con su manifiesto durable."
            )
        b = LoteDuplicadoCoincidencia
        m = LoteDuplicadoCoincidenciaMiembro
        invalid_scope = int(
            (
                await self.db.execute(
                    select(func.count(b.id)).where(
                        b.generacion_id == generation.id,
                        or_(
                            b.operacion_id != generation.operacion_id,
                            b.empresa_id != generation.empresa_id,
                            b.lote_id != generation.lote_id,
                            b.ambiente != generation.ambiente,
                        ),
                    )
                )
            ).scalar_one()
        )
        invalid_complete = int(
            (
                await self.db.execute(
                    select(func.count(m.id))
                    .join(b, b.id == m.bloque_id)
                    .where(
                        b.generacion_id == generation.id,
                        b.clase == "completa",
                        m.ordinal.is_(None),
                    )
                )
            ).scalar_one()
        )
        if invalid_scope or invalid_complete:
            raise DuplicadosLoteError(
                "La estructura de la generación de duplicados fue alterada."
            )

    async def _pagina_generacion(
        self,
        generation: LoteDuplicadoEvidencia,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        await self._validar_estructura_generacion(generation)
        block = LoteDuplicadoCoincidencia.__table__.alias("b")
        current = LoteDuplicadoCoincidenciaMiembro.__table__.alias("a")
        previous = LoteDuplicadoCoincidenciaMiembro.__table__.alias("p")
        type_order = case(
            (block.c.clase == "interna_nombre", 0),
            (block.c.clase == "interna_documento", 0),
            (block.c.clase == "completa", 1),
            (block.c.clase == "parcial_nombre", 2),
            (block.c.clase == "parcial_documento", 2),
            else_=3,
        )
        previous_lote_id = block.c.snapshot_json["lote_anterior_id"].as_integer()

        def projection(
            previous_id: Any,
            previous_group_id: Any,
            previous_receipt_id: Any,
        ) -> list[Any]:
            return [
                current.c.grupo_id.label("grupo_actual_id"),
                previous_lote_id.label("lote_anterior_id"),
                previous_group_id.label("grupo_anterior_id"),
                type_order.label("tipo_orden"),
                previous_receipt_id.label("comprobante_anterior_id"),
                block.c.antecedente_clave.label("antecedente_clave"),
                block.c.bloque_clave.label("bloque_clave"),
                block.c.id.label("bloque_id"),
                current.c.id.label("actual_id"),
                previous_id.label("anterior_id"),
            ]

        internal = (
            select(
                *projection(
                    literal(None).cast(LoteDuplicadoCoincidenciaMiembro.id.type),
                    literal(None).cast(Integer),
                    literal(None).cast(Integer),
                )
            )
            .select_from(
                block.join(
                    current,
                    and_(
                        current.c.bloque_id == block.c.id,
                        current.c.lado == "actual",
                    ),
                )
            )
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase.in_(["interna_nombre", "interna_documento"]),
            )
        )
        complete = (
            select(
                *projection(
                    previous.c.id,
                    previous.c.grupo_id,
                    previous.c.comprobante_id,
                )
            )
            .select_from(
                block.join(
                    current,
                    and_(current.c.bloque_id == block.c.id, current.c.lado == "actual"),
                ).join(
                    previous,
                    and_(
                        previous.c.bloque_id == block.c.id,
                        previous.c.lado == "anterior",
                        previous.c.ordinal == current.c.ordinal,
                    ),
                )
            )
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase == "completa",
            )
        )
        products = (
            select(
                *projection(
                    previous.c.id,
                    previous.c.grupo_id,
                    previous.c.comprobante_id,
                )
            )
            .select_from(
                block.join(
                    current,
                    and_(current.c.bloque_id == block.c.id, current.c.lado == "actual"),
                ).join(
                    previous,
                    and_(
                        previous.c.bloque_id == block.c.id,
                        previous.c.lado == "anterior",
                    ),
                )
            )
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase.in_(["parcial_nombre", "individual_legacy"]),
            )
        )
        documents = (
            select(
                *projection(
                    previous.c.id,
                    previous.c.grupo_id,
                    previous.c.comprobante_id,
                )
            )
            .select_from(
                block.join(
                    current,
                    and_(current.c.bloque_id == block.c.id, current.c.lado == "actual"),
                ).join(
                    previous,
                    and_(
                        previous.c.bloque_id == block.c.id,
                        previous.c.lado == "anterior",
                    ),
                )
            )
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase == "parcial_documento",
                or_(
                    current.c.nombre_hash.is_(None),
                    previous.c.nombre_hash.is_(None),
                    current.c.nombre_hash != previous.c.nombre_hash,
                ),
            )
        )
        relation = union_all(internal, complete, products, documents).subquery()

        internal_total = (
            select(func.count(current.c.id))
            .select_from(
                block.join(
                    current,
                    and_(current.c.bloque_id == block.c.id, current.c.lado == "actual"),
                )
            )
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase.in_(["interna_nombre", "interna_documento"]),
            )
            .scalar_subquery()
        )
        complete_total = (
            select(func.count(current.c.id))
            .select_from(
                block.join(
                    current,
                    and_(current.c.bloque_id == block.c.id, current.c.lado == "actual"),
                ).join(
                    previous,
                    and_(
                        previous.c.bloque_id == block.c.id,
                        previous.c.lado == "anterior",
                        previous.c.ordinal == current.c.ordinal,
                    ),
                )
            )
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase == "completa",
            )
            .scalar_subquery()
        )
        current_counts = (
            select(
                current.c.bloque_id.label("bloque_id"),
                func.count(current.c.id).label("cantidad"),
            )
            .select_from(block.join(current, current.c.bloque_id == block.c.id))
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase.in_(
                    ["parcial_nombre", "parcial_documento", "individual_legacy"]
                ),
                current.c.lado == "actual",
            )
            .group_by(current.c.bloque_id)
            .subquery("cant_actual")
        )
        previous_counts = (
            select(
                previous.c.bloque_id.label("bloque_id"),
                func.count(previous.c.id).label("cantidad"),
            )
            .select_from(block.join(previous, previous.c.bloque_id == block.c.id))
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase.in_(
                    ["parcial_nombre", "parcial_documento", "individual_legacy"]
                ),
                previous.c.lado == "anterior",
            )
            .group_by(previous.c.bloque_id)
            .subquery("cant_anterior")
        )
        product_total = (
            select(
                func.coalesce(
                    func.sum(current_counts.c.cantidad * previous_counts.c.cantidad),
                    0,
                )
            )
            .select_from(
                current_counts.join(
                    previous_counts,
                    previous_counts.c.bloque_id == current_counts.c.bloque_id,
                )
            )
            .scalar_subquery()
        )
        current_names = (
            select(
                current.c.bloque_id.label("bloque_id"),
                current.c.nombre_hash.label("nombre_hash"),
                func.count(current.c.id).label("cantidad"),
            )
            .select_from(block.join(current, current.c.bloque_id == block.c.id))
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase == "parcial_documento",
                current.c.lado == "actual",
                current.c.nombre_hash.is_not(None),
            )
            .group_by(current.c.bloque_id, current.c.nombre_hash)
            .subquery("nombres_actual")
        )
        previous_names = (
            select(
                previous.c.bloque_id.label("bloque_id"),
                previous.c.nombre_hash.label("nombre_hash"),
                func.count(previous.c.id).label("cantidad"),
            )
            .select_from(block.join(previous, previous.c.bloque_id == block.c.id))
            .where(
                block.c.generacion_id == generation.id,
                block.c.clase == "parcial_documento",
                previous.c.lado == "anterior",
                previous.c.nombre_hash.is_not(None),
            )
            .group_by(previous.c.bloque_id, previous.c.nombre_hash)
            .subquery("nombres_anterior")
        )
        excluded_document_total = (
            select(
                func.coalesce(
                    func.sum(current_names.c.cantidad * previous_names.c.cantidad),
                    0,
                )
            )
            .select_from(
                current_names.join(
                    previous_names,
                    and_(
                        previous_names.c.bloque_id == current_names.c.bloque_id,
                        previous_names.c.nombre_hash == current_names.c.nombre_hash,
                    ),
                )
            )
            .scalar_subquery()
        )
        total = int(
            (
                await self.db.execute(
                    select(
                        func.coalesce(internal_total, 0)
                        + func.coalesce(complete_total, 0)
                        + product_total
                        - excluded_document_total
                    )
                )
            ).scalar_one()
        )
        identifiers = list(
            (
                await self.db.execute(
                    select(relation)
                    .order_by(*self._orden_sql_publico(relation))
                    .offset(offset)
                    .limit(limit)
                )
            ).mappings()
        )
        if not identifiers:
            return [], total
        block_ids = {int(row["bloque_id"]) for row in identifiers}
        member_ids = {
            int(value)
            for row in identifiers
            for value in (row["actual_id"], row["anterior_id"])
            if value is not None
        }
        block_rows = {
            int(item.id): item
            for item in (
                await self.db.execute(
                    select(LoteDuplicadoCoincidencia).where(
                        LoteDuplicadoCoincidencia.id.in_(block_ids)
                    )
                )
            ).scalars()
        }
        member_rows = {
            int(item.id): item
            for item in (
                await self.db.execute(
                    select(LoteDuplicadoCoincidenciaMiembro).where(
                        LoteDuplicadoCoincidenciaMiembro.id.in_(member_ids)
                    )
                )
            ).scalars()
        }
        items = []
        for row in identifiers:
            block_row = block_rows[int(row["bloque_id"])]
            actual = member_rows[int(row["actual_id"])]
            prior = (
                member_rows[int(row["anterior_id"])]
                if row["anterior_id"] is not None
                else None
            )
            items.append(
                self._armar_detalle_compacto(
                    clase=block_row.clase,
                    block_snapshot=block_row.snapshot_json,
                    current_snapshot=actual.snapshot_json,
                    previous_snapshot=prior.snapshot_json if prior else None,
                    current_document_hash=actual.documento_hash,
                    previous_document_hash=prior.documento_hash if prior else None,
                )
            )
        return items, total

    async def obtener_detalle(
        self,
        *,
        lote_id: int,
        empresa_id: int,
        evidencia_id: str,
        page: int,
        per_page: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
        durable_row = (
            await self.db.execute(
                select(OperacionIdempotente, LoteDuplicadoEvidencia)
                .join(
                    LoteDuplicadoEvidencia,
                    LoteDuplicadoEvidencia.id
                    == OperacionIdempotente.duplicados_generacion_id,
                )
                .where(
                    OperacionIdempotente.empresa_id == empresa_id,
                    OperacionIdempotente.lote_id == lote_id,
                    OperacionIdempotente.duplicados_version == VERSION,
                    LoteDuplicadoEvidencia.empresa_id == empresa_id,
                    LoteDuplicadoEvidencia.lote_id == lote_id,
                    LoteDuplicadoEvidencia.evidencia_id == evidencia_id,
                )
                .order_by(OperacionIdempotente.updated_at.desc())
                .limit(1)
            )
        ).one_or_none()
        if durable_row is not None:
            operation, generation = durable_row
            durable = operation.control_duplicados_json
            if (
                not isinstance(durable, dict)
                or not isinstance(generation.control_snapshot_json, dict)
                or durable.get("evidencia_id") != evidencia_id
                or generation.control_snapshot_json.get("evidencia_id") != evidencia_id
            ):
                raise DuplicadosLoteError(
                    "La evidencia durable no coincide con su detalle.",
                    "duplicado_logico_lote",
                )
            selection = durable.get("seleccion_original")
            if not isinstance(selection, list):
                raise DuplicadosLoteError(
                    "La operación no conserva una selección verificable.",
                    "duplicado_logico_lote",
                )
            group_ids = [
                int(item["grupo_id"])
                for item in selection
                if isinstance(item, dict) and isinstance(item.get("grupo_id"), int)
            ]
            if len(group_ids) != len(selection):
                raise DuplicadosLoteError(
                    "La selección durable no es canónica.",
                    "duplicado_logico_lote",
                )
            selected_groups = await self._grupos_actuales(
                lote_id=lote_id,
                empresa_id=empresa_id,
                estados=ESTADOS_SELECCION_ORIGINAL,
                grupo_ids=group_ids,
            )
            selected_environments = {
                group.ambiente
                for group in selected_groups
                if group.ambiente is not None
            }
            if (
                len(group_ids) != len(set(group_ids))
                or len(selected_groups) != len(group_ids)
                or any(group.ambiente is None for group in selected_groups)
                or len(selected_environments) != 1
            ):
                raise DuplicadosLoteError(
                    "La selección durable no acredita un ambiente fiscal único.",
                    "duplicado_logico_lote",
                )
            expected_environment = next(iter(selected_environments))
            await self._validar_integridad_generacion(
                generation,
                operacion_id=int(operation.id),
                empresa_id=empresa_id,
                lote_id=lote_id,
                ambiente=expected_environment,
            )
            current = await self.calcular_control(
                lote_id=lote_id,
                empresa_id=empresa_id,
                estados=ESTADOS_SELECCION_ORIGINAL,
                grupo_ids=group_ids,
                operacion_id=int(operation.id),
                incluir_interno=True,
            )
            current_snapshot = self._control_snapshot(
                current,
                selection_material=self._seleccion_material(selected_groups),
            )
            if current.get(
                "evidencia_id"
            ) != evidencia_id or generation.snapshot_hash != self._snapshot_hash(
                current, current_snapshot
            ):
                raise DuplicadosLoteError(
                    "La evidencia cambió; revisá las coincidencias actuales.",
                    (
                        "duplicado_operacion_en_curso"
                        if current.get("bloqueo_operacion_ajena")
                        else "duplicado_logico_lote"
                    ),
                    control=self._publicable(current),
                )
            offset = (page - 1) * per_page
            items, total = await self._pagina_generacion(
                generation,
                offset=offset,
                limit=per_page,
            )
            return durable, items, total
        group_ids = None
        offset = (page - 1) * per_page
        internal = await self.calcular_control(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados={"validado", "fallido", "reintentando"},
            grupo_ids=group_ids,
            operacion_id=None,
            incluir_interno=True,
        )
        control = self._publicable(internal)
        if control.get("evidencia_id") != evidencia_id:
            raise DuplicadosLoteError(
                "La evidencia cambió; revisá las coincidencias actuales.",
                "duplicado_logico_lote",
            )
        items, total = await self._pagina_relacion_viva(
            internal,
            offset=offset,
            limit=per_page,
        )
        return control, items, total

    async def evaluar_y_reservar(
        self,
        *,
        operacion_id: int,
        lote_id: int,
        empresa_id: int,
        estados: set[str],
        grupo_ids: list[int] | None,
        aceptacion_recibida: str | None,
        solicitante_nombre: str | None,
        reservar: bool,
        ambiente: str,
    ) -> tuple[dict[str, Any], str | None, bool]:
        """Ejecuta la coordinación como única dueña de una transacción nueva."""
        if self.db.in_transaction():
            raise DuplicadosLoteError(
                "La coordinación requiere una frontera transaccional limpia."
            )
        try:
            await self.adquirir_coordinacion(
                empresa_id=empresa_id,
                ambiente=ambiente,
            )
            return await self.evaluar_y_reservar_bajo_coordinacion(
                operacion_id=operacion_id,
                lote_id=lote_id,
                empresa_id=empresa_id,
                estados=estados,
                grupo_ids=grupo_ids,
                aceptacion_recibida=aceptacion_recibida,
                solicitante_nombre=solicitante_nombre,
                reservar=reservar,
                ambiente=ambiente,
                commit=True,
            )
        except BaseException:
            if self.db.in_transaction():
                await self.db.rollback()
            raise

    async def adquirir_coordinacion(
        self,
        *,
        empresa_id: int,
        ambiente: str,
    ) -> None:
        """Abre la raíz y serializa decisiones de duplicados por empresa/ambiente."""
        if self.db.in_transaction():
            raise DuplicadosLoteError(
                "La coordinación requiere una frontera transaccional limpia."
            )
        bind = self.db.get_bind()
        if ambiente not in {"homologacion", "produccion"}:
            raise DuplicadosLoteError("El ambiente de coordinación no es válido.")
        if bind.dialect.name == "sqlite":
            await self.db.execute(text("BEGIN IMMEDIATE"))
        row = (
            await self.db.execute(
                select(LoteDuplicadosCoordinacion)
                .where(
                    LoteDuplicadosCoordinacion.empresa_id == empresa_id,
                    LoteDuplicadosCoordinacion.ambiente == ambiente,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            row = LoteDuplicadosCoordinacion(
                empresa_id=empresa_id,
                ambiente=ambiente,
                revision=0,
            )
            self.db.add(row)
            try:
                await self.db.flush()
            except IntegrityError as exc:
                raise DuplicadosLoteError(
                    "Otra operación inicializó la coordinación; repetí con la misma clave."
                ) from exc
        row.revision += 1
        await self.db.flush()

    async def evaluar_y_reservar_bajo_coordinacion(
        self,
        *,
        operacion_id: int,
        lote_id: int,
        empresa_id: int,
        estados: set[str],
        grupo_ids: list[int] | None,
        aceptacion_recibida: str | None,
        solicitante_nombre: str | None,
        reservar: bool,
        ambiente: str,
        commit: bool,
    ) -> tuple[dict[str, Any], str | None, bool]:
        """Evalúa dentro de una raíz que ya posee la coordinación."""
        if not self.db.in_transaction():
            raise DuplicadosLoteError(
                "La evaluación requiere una coordinación transaccional activa."
            )
        if ambiente not in {"homologacion", "produccion"}:
            raise DuplicadosLoteError("El ambiente de coordinación no es válido.")
        operacion = (
            await self.db.execute(
                select(OperacionIdempotente)
                .where(
                    OperacionIdempotente.id == operacion_id,
                    OperacionIdempotente.empresa_id == empresa_id,
                    OperacionIdempotente.lote_id == lote_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if operacion is None:
            raise DuplicadosLoteError("La operación idempotente no pertenece al lote.")
        bloqueo_legacy = await self.obtener_bloqueo_legacy_no_reconfirmable(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados=estados,
            bloquear=True,
        )
        if bloqueo_legacy is not None:
            raise DuplicadosLoteError(
                MENSAJE_BLOQUEO_LEGACY,
                "duplicado_legacy_no_reconfirmable",
                control=bloqueo_legacy,
            )
        grupos_enviables = await self._grupos_actuales(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados=estados,
            grupo_ids=grupo_ids,
        )
        if operacion.operacion_raiz_id is None:
            root_id = int(operacion.id)
            if operacion.tipo_operacion == "reintentar_fallidos_lote":
                enviables_ids = {int(group.id) for group in grupos_enviables}
                candidates = list(
                    (
                        await self.db.execute(
                            select(OperacionIdempotente)
                            .where(
                                OperacionIdempotente.id != operacion.id,
                                OperacionIdempotente.empresa_id == empresa_id,
                                OperacionIdempotente.lote_id == lote_id,
                                OperacionIdempotente.tipo_operacion == "procesar_lote",
                                OperacionIdempotente.duplicados_version == VERSION,
                                OperacionIdempotente.control_duplicados_json.is_not(
                                    None
                                ),
                            )
                            .order_by(OperacionIdempotente.id.desc())
                        )
                    )
                    .scalars()
                    .all()
                )
                for candidate in candidates:
                    candidate_control = candidate.control_duplicados_json
                    candidate_selection = (
                        candidate_control.get("seleccion_original")
                        if isinstance(candidate_control, dict)
                        else None
                    )
                    if not isinstance(candidate_selection, list):
                        continue
                    candidate_ids = {
                        int(item["grupo_id"])
                        for item in candidate_selection
                        if isinstance(item, dict)
                        and isinstance(item.get("grupo_id"), int)
                    }
                    if len(candidate_ids) == len(candidate_selection) and (
                        enviables_ids <= candidate_ids
                    ):
                        root_id = int(candidate.id)
                        break
            operacion.operacion_raiz_id = root_id
        previous_current = (
            operacion.control_duplicados_json
            if isinstance(operacion.control_duplicados_json, dict)
            else {}
        )
        previous = previous_current
        if not isinstance(previous.get("seleccion_original"), list):
            root_operation = (
                await self.db.execute(
                    select(OperacionIdempotente).where(
                        OperacionIdempotente.id == operacion.operacion_raiz_id,
                        OperacionIdempotente.empresa_id == empresa_id,
                        OperacionIdempotente.lote_id == lote_id,
                        OperacionIdempotente.duplicados_version == VERSION,
                    )
                )
            ).scalar_one_or_none()
            if root_operation is not None and isinstance(
                root_operation.control_duplicados_json, dict
            ):
                previous = root_operation.control_duplicados_json
        previous_selection = previous.get("seleccion_original")
        if isinstance(previous_selection, list) and previous_selection:
            previous_by_group_id = {
                int(item["grupo_id"]): item
                for item in previous_selection
                if isinstance(item, dict) and isinstance(item.get("grupo_id"), int)
            }
            selection_ids = [
                int(item["grupo_id"])
                for item in previous_selection
                if isinstance(item, dict) and isinstance(item.get("grupo_id"), int)
            ]
            if len(selection_ids) != len(previous_selection):
                raise DuplicadosLoteError(
                    "La selección original durable no es canónica.",
                    "duplicados_seleccion_obsoleta",
                )
            enviables_material = self._seleccion_material(grupos_enviables)
            if any(
                item["grupo_id"] not in previous_by_group_id
                or previous_by_group_id[item["grupo_id"]] != item
                for item in enviables_material
            ):
                raise DuplicadosLoteError(
                    "Los grupos enviables no pertenecen a la selección original.",
                    "duplicados_seleccion_obsoleta",
                )
        else:
            selection_ids = [int(group.id) for group in grupos_enviables]
        control = await self.calcular_control(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados=ESTADOS_SELECCION_ORIGINAL,
            grupo_ids=selection_ids,
            operacion_id=operacion_id,
            incluir_interno=True,
        )
        grupos_comparacion = await self._grupos_actuales(
            lote_id=lote_id,
            empresa_id=empresa_id,
            estados=ESTADOS_SELECCION_ORIGINAL,
            grupo_ids=selection_ids,
        )
        if {group.ambiente for group in grupos_comparacion} != {ambiente}:
            raise DuplicadosLoteError(
                "La selección no pertenece al ambiente de coordinación esperado."
            )
        selection_material = self._seleccion_material(grupos_comparacion)
        if (
            isinstance(previous_selection, list)
            and selection_material != previous_selection
        ):
            raise DuplicadosLoteError(
                "El material de la selección original cambió.",
                "duplicados_seleccion_obsoleta",
                control=self._publicable(control),
            )
        now = datetime.now(timezone.utc)
        (
            generation,
            public_control,
            acceptance_id,
            accepted,
        ) = await self._publicar_generacion(
            operation=operacion,
            control=control,
            selection_material=selection_material,
            aceptacion_recibida=aceptacion_recibida,
            solicitante_nombre=solicitante_nombre,
            ambiente=ambiente,
        )
        operacion.duplicados_version = VERSION
        operacion.solicitante_nombre_snapshot = (
            operacion.solicitante_nombre_snapshot or solicitante_nombre
        )
        operacion.solicitud_emision_at = operacion.solicitud_emision_at or now
        if (
            reservar
            and control["bloqueo_operacion_ajena"] is None
            and (not control["aceptacion_requerida"] or accepted)
        ):
            ids = [int(group.id) for group in grupos_enviables]
            result = await self.db.execute(
                update(LoteComprobanteGrupo)
                .where(
                    LoteComprobanteGrupo.id.in_(ids),
                    or_(
                        LoteComprobanteGrupo.duplicados_reserva_operacion_id.is_(None),
                        LoteComprobanteGrupo.duplicados_reserva_operacion_id
                        == operacion_id,
                    ),
                )
                .values(duplicados_reserva_operacion_id=operacion_id)
            )
            if result.rowcount != len(ids):
                raise DuplicadosLoteError(
                    "Otra operación reservó parte de la selección.",
                    "duplicado_operacion_en_curso",
                )
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
        return public_control, acceptance_id, accepted
