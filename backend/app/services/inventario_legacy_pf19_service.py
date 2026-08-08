"""Inventario sanitizado, privado y de solo lectura para legacy de PF-19."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, and_, case, or_, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.orm import aliased

from app.models.comprobante import Comprobante
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteGrupo
from app.models.punto_venta import PuntoVenta


CATEGORIAS_CANDIDATAS_PF19 = (
    "arca_batch_sin_respuesta",
    "arca_respuesta_incierta",
)
MAX_REGISTROS_INVENTARIO_PF19 = 500
_MARCA_10005_GLOBAL = re.compile(r"\[10005\]")
_PREFIJO_ERROR_GLOBAL = (
    "Error del servicio ARCA: ARCA devolvió errores globales al solicitar CAE:"
)
_ZONA_HORARIA_ARGENTINA = timezone(
    timedelta(hours=-3),
    name="America/Argentina/Buenos_Aires",
)


class InventarioLegacyPF19Error(RuntimeError):
    """Error funcional y sanitizado del inventario PF-19."""


class FiltrosInventarioLegacyPF19(BaseModel):
    """Filtros allowlist para aislar el inventario fiscal legacy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ambiente_runtime: Literal["homologacion", "produccion"]
    empresa_id: int = Field(strict=True, gt=0)
    punto_venta: int | None = Field(default=None, strict=True, gt=0, le=99999)
    tipo_comprobante: int | None = Field(default=None, strict=True, gt=0)
    lote_id: int | None = Field(default=None, strict=True, gt=0)


async def activar_transaccion_solo_lectura(connection: AsyncConnection) -> None:
    """Activa el modo de solo lectura soportado por PostgreSQL o SQLite."""
    dialecto = connection.dialect.name
    if dialecto == "postgresql":
        await connection.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        )
        verificacion = await connection.execute(text("SHOW transaction_read_only"))
        if str(verificacion.scalar_one()).strip().lower() != "on":
            raise InventarioLegacyPF19Error(
                "PostgreSQL no confirmó una transacción de solo lectura"
            )
        return
    if dialecto == "sqlite":
        await connection.execute(text("PRAGMA query_only = ON"))
        verificacion = await connection.execute(text("PRAGMA query_only"))
        if int(verificacion.scalar_one()) != 1:
            raise InventarioLegacyPF19Error("SQLite no confirmó el modo query_only")
        return
    raise InventarioLegacyPF19Error(
        "El inventario PF-19 solo admite PostgreSQL o SQLite en modo lectura"
    )


def construir_consulta_inventario(
    filtros: FiltrosInventarioLegacyPF19,
) -> Select:
    """Construye una consulta allowlist sin payloads ni datos de receptores."""
    comprobante_intento = aliased(Comprobante, name="comprobante_intento_pf19")
    comprobante_grupo = aliased(Comprobante, name="comprobante_grupo_pf19")
    comprobante_intento_alcance_valido = and_(
        comprobante_intento.id == IntentoEmisionFiscal.comprobante_id,
        comprobante_intento.empresa_id == IntentoEmisionFiscal.empresa_id,
        comprobante_intento.punto_venta_id == IntentoEmisionFiscal.punto_venta_id,
        comprobante_intento.tipo_comprobante == IntentoEmisionFiscal.tipo_comprobante,
        IntentoEmisionFiscal.numero_planificado.is_not(None),
        comprobante_intento.numero == IntentoEmisionFiscal.numero_planificado,
    )
    lote_alcance_valido = and_(
        LoteComprobante.id == IntentoEmisionFiscal.lote_id,
        LoteComprobante.empresa_id == IntentoEmisionFiscal.empresa_id,
    )
    grupo_cadena_valida = and_(
        lote_alcance_valido,
        LoteComprobanteGrupo.lote_id == LoteComprobante.id,
        LoteComprobanteGrupo.tipo_comprobante == IntentoEmisionFiscal.tipo_comprobante,
        LoteComprobanteGrupo.punto_venta_numero
        == IntentoEmisionFiscal.punto_venta_numero,
    )
    comprobante_grupo_alcance_valido = or_(
        LoteComprobanteGrupo.comprobante_id.is_(None),
        and_(
            comprobante_grupo.id == LoteComprobanteGrupo.comprobante_id,
            comprobante_grupo.empresa_id == IntentoEmisionFiscal.empresa_id,
            comprobante_grupo.punto_venta_id == IntentoEmisionFiscal.punto_venta_id,
            comprobante_grupo.tipo_comprobante == IntentoEmisionFiscal.tipo_comprobante,
            IntentoEmisionFiscal.numero_planificado.is_not(None),
            comprobante_grupo.numero == IntentoEmisionFiscal.numero_planificado,
        ),
    )
    grupo_senales_validas = and_(
        grupo_cadena_valida,
        comprobante_grupo_alcance_valido,
    )
    consulta = (
        select(
            IntentoEmisionFiscal.id.label("intento_id"),
            IntentoEmisionFiscal.empresa_id,
            IntentoEmisionFiscal.punto_venta_id,
            IntentoEmisionFiscal.punto_venta_numero,
            IntentoEmisionFiscal.tipo_comprobante,
            IntentoEmisionFiscal.numero_planificado,
            IntentoEmisionFiscal.estado.label("intento_estado"),
            IntentoEmisionFiscal.categoria_error,
            IntentoEmisionFiscal.cae.is_not(None).label("tiene_cae"),
            IntentoEmisionFiscal.comprobante_id.label("intento_comprobante_id"),
            comprobante_intento.id.label("intento_comprobante_actual_id"),
            comprobante_intento.empresa_id.label("intento_comprobante_empresa_id"),
            comprobante_intento.punto_venta_id.label(
                "intento_comprobante_punto_venta_id"
            ),
            comprobante_intento.tipo_comprobante.label(
                "intento_comprobante_tipo_comprobante"
            ),
            comprobante_intento.numero.label("intento_comprobante_numero"),
            case(
                (comprobante_intento_alcance_valido, True),
                else_=False,
            ).label("tiene_comprobante"),
            IntentoEmisionFiscal.lote_id,
            IntentoEmisionFiscal.grupo_id,
            IntentoEmisionFiscal.operacion_id,
            PuntoVenta.id.label("punto_actual_id"),
            PuntoVenta.empresa_id.label("punto_empresa_id"),
            case(
                (
                    PuntoVenta.empresa_id == IntentoEmisionFiscal.empresa_id,
                    PuntoVenta.sistema,
                ),
                else_=None,
            ).label("punto_sistema"),
            case(
                (
                    PuntoVenta.empresa_id == IntentoEmisionFiscal.empresa_id,
                    PuntoVenta.fuente,
                ),
                else_=None,
            ).label("punto_fuente"),
            case(
                (
                    PuntoVenta.empresa_id == IntentoEmisionFiscal.empresa_id,
                    PuntoVenta.numero,
                ),
                else_=None,
            ).label("punto_numero_actual"),
            case(
                (
                    PuntoVenta.empresa_id == IntentoEmisionFiscal.empresa_id,
                    PuntoVenta.es_webservice,
                ),
                else_=False,
            ).label("punto_es_webservice"),
            case(
                (
                    PuntoVenta.empresa_id == IntentoEmisionFiscal.empresa_id,
                    PuntoVenta.bloqueado,
                ),
                else_=False,
            ).label("punto_bloqueado"),
            case(
                (
                    PuntoVenta.empresa_id == IntentoEmisionFiscal.empresa_id,
                    PuntoVenta.activo,
                ),
                else_=False,
            ).label("punto_activo"),
            case(
                (
                    PuntoVenta.empresa_id == IntentoEmisionFiscal.empresa_id,
                    PuntoVenta.fecha_baja.is_not(None),
                ),
                else_=False,
            ).label("punto_con_fecha_baja"),
            LoteComprobante.id.label("lote_actual_id"),
            LoteComprobante.empresa_id.label("lote_empresa_id"),
            case(
                (
                    LoteComprobante.empresa_id == IntentoEmisionFiscal.empresa_id,
                    LoteComprobante.estado,
                ),
                else_=None,
            ).label("lote_estado"),
            LoteComprobanteGrupo.id.label("grupo_actual_id"),
            LoteComprobanteGrupo.lote_id.label("grupo_lote_id"),
            LoteComprobanteGrupo.tipo_comprobante.label(
                "grupo_tipo_comprobante_actual"
            ),
            LoteComprobanteGrupo.punto_venta_numero.label("grupo_punto_venta_actual"),
            LoteComprobanteGrupo.comprobante_id.label("grupo_comprobante_id"),
            comprobante_grupo.id.label("grupo_comprobante_actual_id"),
            comprobante_grupo.empresa_id.label("grupo_comprobante_empresa_id"),
            comprobante_grupo.punto_venta_id.label("grupo_comprobante_punto_venta_id"),
            comprobante_grupo.tipo_comprobante.label(
                "grupo_comprobante_tipo_comprobante"
            ),
            comprobante_grupo.numero.label("grupo_comprobante_numero"),
            case(
                (
                    grupo_senales_validas,
                    LoteComprobanteGrupo.estado,
                ),
                else_=None,
            ).label("grupo_estado"),
            case(
                (
                    grupo_senales_validas,
                    LoteComprobanteGrupo.cae.is_not(None),
                ),
                else_=False,
            ).label("grupo_tiene_cae"),
            case(
                (
                    grupo_senales_validas,
                    LoteComprobanteGrupo.comprobante_id.is_not(None),
                ),
                else_=False,
            ).label("grupo_tiene_comprobante"),
            case(
                (
                    grupo_senales_validas,
                    LoteComprobanteGrupo.mensajes_json,
                ),
                else_=None,
            ).label("grupo_mensajes"),
            OperacionIdempotente.id.label("operacion_actual_id"),
            OperacionIdempotente.empresa_id.label("operacion_empresa_id"),
            case(
                (
                    OperacionIdempotente.empresa_id == IntentoEmisionFiscal.empresa_id,
                    OperacionIdempotente.estado,
                ),
                else_=None,
            ).label("operacion_estado"),
            case(
                (
                    OperacionIdempotente.empresa_id == IntentoEmisionFiscal.empresa_id,
                    OperacionIdempotente.response_json,
                ),
                else_=None,
            ).label("operacion_respuesta"),
        )
        .outerjoin(
            PuntoVenta,
            PuntoVenta.id == IntentoEmisionFiscal.punto_venta_id,
        )
        .outerjoin(
            comprobante_intento,
            comprobante_intento.id == IntentoEmisionFiscal.comprobante_id,
        )
        .outerjoin(
            LoteComprobante,
            LoteComprobante.id == IntentoEmisionFiscal.lote_id,
        )
        .outerjoin(
            LoteComprobanteGrupo,
            LoteComprobanteGrupo.id == IntentoEmisionFiscal.grupo_id,
        )
        .outerjoin(
            comprobante_grupo,
            comprobante_grupo.id == LoteComprobanteGrupo.comprobante_id,
        )
        .outerjoin(
            OperacionIdempotente,
            OperacionIdempotente.id == IntentoEmisionFiscal.operacion_id,
        )
        .where(
            IntentoEmisionFiscal.categoria_error.in_(CATEGORIAS_CANDIDATAS_PF19),
            IntentoEmisionFiscal.empresa_id == filtros.empresa_id,
        )
    )
    if filtros.punto_venta is not None:
        consulta = consulta.where(
            IntentoEmisionFiscal.punto_venta_numero == filtros.punto_venta
        )
    if filtros.tipo_comprobante is not None:
        consulta = consulta.where(
            IntentoEmisionFiscal.tipo_comprobante == filtros.tipo_comprobante
        )
    if filtros.lote_id is not None:
        consulta = consulta.where(IntentoEmisionFiscal.lote_id == filtros.lote_id)
    return consulta.order_by(
        IntentoEmisionFiscal.empresa_id,
        IntentoEmisionFiscal.punto_venta_numero,
        IntentoEmisionFiscal.tipo_comprobante,
        IntentoEmisionFiscal.id,
    ).limit(MAX_REGISTROS_INVENTARIO_PF19 + 1)


async def inventariar_legacy_pf19(
    engine: AsyncEngine,
    filtros: FiltrosInventarioLegacyPF19,
) -> dict:
    """Ejecuta el inventario dentro de una transacción siempre revertida."""
    async with engine.connect() as connection:
        dialecto = connection.dialect.name
        transaction = await connection.begin()
        sqlite_query_only_anterior: int | None = None
        try:
            if dialecto == "sqlite":
                sqlite_query_only_anterior = int(
                    (await connection.execute(text("PRAGMA query_only"))).scalar_one()
                )
                if sqlite_query_only_anterior not in {0, 1}:
                    raise InventarioLegacyPF19Error(
                        "SQLite devolvió un estado query_only inválido"
                    )
            await activar_transaccion_solo_lectura(connection)
            resultado = await connection.execute(construir_consulta_inventario(filtros))
            filas = resultado.mappings().all()
            if len(filas) > MAX_REGISTROS_INVENTARIO_PF19:
                raise InventarioLegacyPF19Error(
                    "El inventario supera el máximo de "
                    f"{MAX_REGISTROS_INVENTARIO_PF19} registros; agregá filtros "
                    "por punto de venta, tipo de comprobante o lote para acotar "
                    "el incidente"
                )
            registros = [_sanitizar_registro(row) for row in filas]
        finally:
            await transaction.rollback()
            if dialecto == "sqlite" and sqlite_query_only_anterior is not None:
                restaurar_query_only = (
                    text("PRAGMA query_only = 1")
                    if sqlite_query_only_anterior == 1
                    else text("PRAGMA query_only = 0")
                )
                await connection.execute(restaurar_query_only)
                verificacion = await connection.execute(text("PRAGMA query_only"))
                if int(verificacion.scalar_one()) != sqlite_query_only_anterior:
                    raise InventarioLegacyPF19Error(
                        "SQLite no pudo restaurar la conexión después del inventario"
                    )
                await connection.rollback()

    conteos_tupla = Counter(
        (
            filtros.ambiente_runtime,
            registro["empresa_id"],
            registro["punto_venta"],
            registro["tipo_comprobante"],
        )
        for registro in registros
    )
    conteos_clasificacion = Counter(
        registro["clasificacion_inventario"] for registro in registros
    )
    return {
        "version_inventario": 1,
        "generado_el": datetime.now(_ZONA_HORARIA_ARGENTINA).strftime("%d/%m/%Y"),
        "modo": "solo_lectura",
        "ambiente_contexto_actual": filtros.ambiente_runtime,
        "ambiente_historico": "indeterminado",
        "aislamiento_ambiente_historico_demostrable": False,
        "solicitudes_fecae_reconstruibles": False,
        "filtros": filtros.model_dump(),
        "cantidad_registros": len(registros),
        "conteos_por_clasificacion": dict(sorted(conteos_clasificacion.items())),
        "conteos_por_tupla_contexto_actual": [
            {
                "ambiente": clave[0],
                "empresa_id": clave[1],
                "punto_venta": clave[2],
                "tipo_comprobante": clave[3],
                "cantidad": cantidad,
            }
            for clave, cantidad in sorted(conteos_tupla.items())
        ],
        "registros": registros,
        "advertencias": [
            (
                "El ambiente histórico no está persistido en los intentos legacy; "
                "ARCA_ENV solo identifica el contexto actual desde el que se leyó "
                "la base."
            ),
            (
                "Un código 10005 recuperado desde texto legacy sigue siendo una "
                "señal candidata, no una autorización para cambiar estados."
            ),
            (
                "El inventario no consulta ARCA, no solicita CAE y no modifica "
                "intentos, operaciones, grupos, lotes ni comprobantes."
            ),
        ],
    }


def _sanitizar_registro(row) -> dict:
    """Reduce una fila a una allowlist operativa que continúa siendo privada."""
    referencias = _clasificar_referencias(row)
    grupo_consumible = referencias["grupo"] == "valida" and referencias[
        "grupo_comprobante"
    ] in {"valida", "no_aplica"}
    evidencia_codigo = _evidencia_codigo_10005(
        (row["grupo_mensajes"] if grupo_consumible else None),
        (row["operacion_respuesta"] if referencias["operacion"] == "valida" else None),
    )
    grupo_tiene_cae = grupo_consumible and bool(row["grupo_tiene_cae"])
    grupo_tiene_comprobante = grupo_consumible and bool(row["grupo_tiene_comprobante"])
    return {
        "intento_id": row["intento_id"],
        "empresa_id": row["empresa_id"],
        "punto_venta_id": row["punto_venta_id"],
        "punto_venta": row["punto_venta_numero"],
        "tipo_comprobante": row["tipo_comprobante"],
        "intento_estado": row["intento_estado"],
        "categoria_error": row["categoria_error"],
        "tiene_cae": bool(row["tiene_cae"]),
        "tiene_comprobante": bool(row["tiene_comprobante"]),
        "lote_id": row["lote_id"],
        "grupo_id": row["grupo_id"],
        "operacion_id": row["operacion_id"],
        "lote_estado": row["lote_estado"],
        "grupo_estado": row["grupo_estado"] if grupo_consumible else None,
        "operacion_estado": row["operacion_estado"],
        "referencias": referencias,
        "senal_textual_sistema_actual": _clasificar_sistema_punto(row["punto_sistema"]),
        "fuente_punto": _clasificar_fuente_punto(row["punto_fuente"]),
        "punto_es_webservice": bool(row["punto_es_webservice"]),
        "punto_bloqueado": bool(row["punto_bloqueado"]),
        "punto_activo": bool(row["punto_activo"]),
        "punto_con_fecha_baja": bool(row["punto_con_fecha_baja"]),
        "punto_actual_presente": row["punto_numero_actual"] is not None,
        "numero_punto_mutado": (
            referencias["punto"] == "valida"
            and row["punto_numero_actual"] != row["punto_venta_numero"]
        ),
        "grupo_tiene_cae": grupo_tiene_cae,
        "grupo_tiene_comprobante": grupo_tiene_comprobante,
        "evidencia_codigo_10005": evidencia_codigo,
        "clasificacion_inventario": _clasificar_registro(
            row,
            evidencia_codigo,
            referencias=referencias,
            grupo_tiene_cae=grupo_tiene_cae,
            grupo_tiene_comprobante=grupo_tiene_comprobante,
        ),
    }


def _clasificar_registro(
    row,
    evidencia_codigo: str,
    *,
    referencias: dict[str, str] | None = None,
    grupo_tiene_cae: bool = False,
    grupo_tiene_comprobante: bool = False,
) -> str:
    """Distingue candidatos, incertidumbre e inconsistencias sin mutar estados."""
    referencias = referencias or {}
    grupo_valido = referencias.get("grupo", "valida") == "valida"
    operacion_valida = referencias.get("operacion", "valida") == "valida"
    if "huerfana" in referencias.values():
        return "referencia_huerfana"
    if "fuera_de_alcance" in referencias.values():
        return "referencia_fuera_de_alcance"
    if (
        bool(row["tiene_cae"])
        or bool(row["tiene_comprobante"])
        or grupo_tiene_cae
        or grupo_tiene_comprobante
        or (
            grupo_valido
            and row.get("grupo_estado") in {"autorizado", "autorizado_externo"}
        )
    ):
        return "preautorizacion_con_cae_o_comprobante"
    if row["intento_estado"] != "requiere_reconciliacion":
        return "marcador_inconsistente_con_estado"
    if evidencia_codigo != "ausente" and (
        (grupo_valido and row.get("grupo_estado") in {"fallido", "descartado"})
        or (
            operacion_valida
            and row.get("operacion_estado") in {"fallido", "finalizado"}
        )
    ):
        return "marcador_inconsistente_con_estado"
    if evidencia_codigo != "ausente":
        return "candidato_10005_no_confirmado"
    return "incertidumbre_sin_codigo_preservado"


def _clasificar_referencias(row) -> dict[str, str]:
    """Valida presencia y alcance antes de leer señales de relaciones legacy."""
    punto = _clasificar_referencia(
        row["punto_venta_id"],
        row["punto_actual_id"],
        row["punto_empresa_id"] == row["empresa_id"],
    )
    operacion = _clasificar_referencia(
        row["operacion_id"],
        row["operacion_actual_id"],
        row["operacion_empresa_id"] == row["empresa_id"],
    )
    intento_comprobante = _clasificar_referencia(
        row["intento_comprobante_id"],
        row["intento_comprobante_actual_id"],
        row["intento_comprobante_empresa_id"] == row["empresa_id"]
        and row["intento_comprobante_punto_venta_id"] == row["punto_venta_id"]
        and row["intento_comprobante_tipo_comprobante"] == row["tipo_comprobante"]
        and row["numero_planificado"] is not None
        and row["intento_comprobante_numero"] == row["numero_planificado"],
    )
    lote = _clasificar_referencia(
        row["lote_id"],
        row["lote_actual_id"],
        row["lote_empresa_id"] == row["empresa_id"],
    )
    grupo = _clasificar_referencia(
        row["grupo_id"],
        row["grupo_actual_id"],
        lote == "valida"
        and row["grupo_lote_id"] == row["lote_actual_id"]
        and row["grupo_tipo_comprobante_actual"] == row["tipo_comprobante"]
        and row["grupo_punto_venta_actual"] == row["punto_venta_numero"],
    )
    if grupo != "valida":
        grupo_comprobante = "no_evaluable"
    else:
        grupo_comprobante = _clasificar_referencia(
            row["grupo_comprobante_id"],
            row["grupo_comprobante_actual_id"],
            row["grupo_comprobante_empresa_id"] == row["empresa_id"]
            and row["grupo_comprobante_punto_venta_id"] == row["punto_venta_id"]
            and row["grupo_comprobante_tipo_comprobante"] == row["tipo_comprobante"]
            and row["numero_planificado"] is not None
            and row["grupo_comprobante_numero"] == row["numero_planificado"],
        )
    return {
        "punto": punto,
        "operacion": operacion,
        "intento_comprobante": intento_comprobante,
        "lote": lote,
        "grupo": grupo,
        "grupo_comprobante": grupo_comprobante,
    }


def _clasificar_referencia(
    referencia_id: object,
    actual_id: object,
    alcance_coincide: bool,
) -> str:
    """Clasifica una FK opcional sin seguir datos huérfanos o cruzados."""
    if referencia_id is None:
        return "no_aplica"
    if actual_id is None:
        return "huerfana"
    if not alcance_coincide:
        return "fuera_de_alcance"
    return "valida"


def _evidencia_codigo_10005(
    grupo_mensajes: object,
    operacion_respuesta: object,
) -> str:
    """Clasifica mensajes de grupo y el campo de errores de la operación."""
    campos_error: list[object] = [grupo_mensajes]
    if isinstance(operacion_respuesta, dict):
        campos_error.append(operacion_respuesta.get("errores"))

    resultado = "ausente"
    for valor in campos_error:
        evidencia = _buscar_codigo_10005(valor)
        if evidencia == "firma_global_legacy":
            resultado = evidencia
    return resultado


def _buscar_codigo_10005(valor: object) -> str:
    """Busca el código legacy en estructuras de error sin devolver mensajes."""
    if isinstance(valor, dict):
        resultado = "ausente"
        for contenido in valor.values():
            evidencia = _buscar_codigo_10005(contenido)
            if evidencia == "firma_global_legacy":
                resultado = evidencia
        return resultado
    if isinstance(valor, (list, tuple)):
        resultado = "ausente"
        for contenido in valor:
            evidencia = _buscar_codigo_10005(contenido)
            if evidencia == "firma_global_legacy":
                resultado = evidencia
        return resultado
    if isinstance(valor, str):
        texto = " ".join(valor.split())
        if texto.startswith(_PREFIJO_ERROR_GLOBAL) and _MARCA_10005_GLOBAL.search(
            texto[len(_PREFIJO_ERROR_GLOBAL) :]
        ):
            return "firma_global_legacy"
    return "ausente"


def _normalizar_texto(valor: object) -> str:
    """Normaliza una señal textual únicamente para clasificarla."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return " ".join(texto.encode("ascii", "ignore").decode("ascii").upper().split())


def _clasificar_sistema_punto(valor: object) -> str:
    """Clasifica la descripción actual sin convertirla en autoridad RECE."""
    texto = _normalizar_texto(valor)
    if not texto:
        return "sistema_ausente"
    if "RECE PARA APLICATIVO Y WEB SERVICES" in texto:
        return "texto_indica_rece"
    if "WEB SERVICES" in texto:
        return "web_services_generico"
    return "sin_indicio_web_services"


def _clasificar_fuente_punto(valor: object) -> str:
    """Conserva solo fuentes públicas conocidas o una categoría genérica."""
    fuente = str(valor or "").strip().lower()
    if not fuente:
        return "no_informada"
    if fuente in {"constancia_arca", "arca_wsfe", "manual"}:
        return fuente
    return "otra"
