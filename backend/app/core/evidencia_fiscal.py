"""Evidencia fiscal v1: contrato histórico puro, sin admisibilidad ni red."""

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, DecimalException
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, ValidationError

from app.core.comparacion_fiscal import ComparacionFiscal, comparar_consulta_fiscal

VERSION_EVIDENCIA = "solicitud_fiscal/1"
EVIDENCIA_HEAD = "c3d4e5f6a7b8"
COLUMNAS_EVIDENCIA = ("evidencia_version", "evidencia_json", "evidencia_hash")
CAMPOS_CONTEXTO = (
    "empresa_id",
    "ambiente",
    "operacion_id",
    "id",
    "punto_venta_id",
    "punto_venta_numero",
    "tipo_comprobante",
    "numero_planificado",
    "lote_id",
    "grupo_id",
    "guarda_rece_id",
    "punto_venta_elegibilidad_revision_id",
    "punto_venta_revision_fiscal",
    "duplicados_generacion_id",
)


class EvidenciaFiscalError(ValueError):
    """Diagnóstico sanitizado: nunca incluye el documento privado."""


def _decimal_historico(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise ValueError("Decimal histórico inválido")
    return Decimal(value)


DecimalHistorico = Annotated[Decimal, BeforeValidator(_decimal_historico)]


class _Historico(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )


class _IvaV1(_Historico):
    id: int
    base_imp: DecimalHistorico
    importe: DecimalHistorico


class _TributoV1(_IvaV1):
    descripcion: str
    alic: DecimalHistorico


def _fecha_arca(value):
    if value is not None:
        if not isinstance(value, str) or not re.fullmatch(r"\d{8}", value):
            raise ValueError("Fecha histórica inválida")
        date(int(value[:4]), int(value[4:6]), int(value[6:]))
    return value


FechaArca = Annotated[str, BeforeValidator(_fecha_arca)]


class _AsociadoV1(_Historico):
    tipo: int
    punto_venta: int
    numero: int
    cuit: str | None
    fecha_cbte: FechaArca | None


class SolicitudFiscalV1(_Historico):
    """No hereda las validaciones mutables de nuevas solicitudes WSFE."""

    punto_venta: int
    tipo_cbte: int
    concepto: int
    tipo_doc: int
    nro_doc: int
    cbte_desde: int
    cbte_hasta: int
    fecha_cbte: FechaArca
    fecha_vto_pago: FechaArca | None
    fecha_serv_desde: FechaArca | None
    fecha_serv_hasta: FechaArca | None
    imp_total: DecimalHistorico
    imp_neto: DecimalHistorico
    imp_iva: DecimalHistorico
    imp_op_ex: DecimalHistorico
    imp_tot_conc: DecimalHistorico
    imp_trib: DecimalHistorico
    moneda_id: str
    moneda_cotiz: DecimalHistorico
    condicion_iva_receptor_id: int | None
    observaciones: str | None
    iva: list[_IvaV1]
    tributos: list[_TributoV1]
    cbtes_asoc: list[_AsociadoV1]


class ContextoFiscalV1(_Historico):
    empresa_id: int
    cuit: str
    ambiente: Literal["homologacion", "produccion"]
    operacion_id: int
    id: int
    punto_venta_id: int
    punto_venta_numero: int
    tipo_comprobante: int
    numero_planificado: int
    lote_id: int | None
    grupo_id: int | None
    guarda_rece_id: int
    punto_venta_elegibilidad_revision_id: int
    punto_venta_revision_fiscal: int
    duplicados_generacion_id: int | None


class _EmisorV1(_Historico):
    razon_social: str | None
    domicilio: str | None
    localidad: str | None
    provincia: str | None
    condicion_iva: str | None
    ingresos_brutos: str | None
    inicio_actividades: str | None


class _ReceptorV1(_Historico):
    tipo_documento: int
    numero_documento: str
    razon_social: str
    condicion_iva: str
    domicilio: str | None


class _ItemV1(_Historico):
    codigo: str | None
    descripcion: str
    cantidad: DecimalHistorico
    unidad: str
    precio_unitario: DecimalHistorico
    descuento_porcentaje: DecimalHistorico
    iva_porcentaje: DecimalHistorico
    orden: int


class _PresentacionV1(_Historico):
    emisor: _EmisorV1
    receptor: _ReceptorV1
    observaciones: str | None
    items: list[_ItemV1]


class _ImportesV1(_Historico):
    subtotal: DecimalHistorico
    base_21: DecimalHistorico
    base_10_5: DecimalHistorico
    base_27: DecimalHistorico
    base_0: DecimalHistorico
    iva_21: DecimalHistorico
    iva_10_5: DecimalHistorico
    iva_27: DecimalHistorico
    total: DecimalHistorico
    subtotales_items: list[DecimalHistorico]


class EvidenciaFiscalV1(_Historico):
    version: Literal["solicitud_fiscal/1"]
    contexto: ContextoFiscalV1
    solicitud_wsfe: SolicitudFiscalV1
    presentacion: _PresentacionV1
    importes_guardado: _ImportesV1


def _material(value):
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise EvidenciaFiscalError("La evidencia contiene un decimal no finito")
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _material(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_material(item) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    raise EvidenciaFiscalError("La evidencia contiene un tipo no soportado")


def serializar_evidencia(documento: dict) -> str:
    """No admite float, exponentes decimales ni material no incluido en v1."""
    try:
        material = _material(documento)
        EvidenciaFiscalV1.model_validate(material)
        return json.dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (ValueError, TypeError, ValidationError) as exc:
        raise EvidenciaFiscalError(
            "La evidencia fiscal no tiene estructura v1 válida"
        ) from exc


def hash_evidencia(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def solicitud_historica(request) -> SolicitudFiscalV1:
    """Proyecta la solicitud construida sin volver a calcular importes."""
    return SolicitudFiscalV1.model_validate(
        _material(request.model_dump(mode="python"))
    )


def leer_evidencia(*, version, raw, sha256, pertenencia: dict) -> EvidenciaFiscalV1:
    """Valida el sobre contra la fila durable, nunca contra fichas actuales."""
    try:
        if version != VERSION_EVIDENCIA or not isinstance(raw, str):
            raise ValueError()
        if not isinstance(sha256, str) or hash_evidencia(raw) != sha256:
            raise ValueError()
        documento = json.loads(raw)
        if serializar_evidencia(documento) != raw:
            raise ValueError()
        evidencia = EvidenciaFiscalV1.model_validate(documento)
        if any(
            getattr(evidencia.contexto, key) != pertenencia[key]
            for key in CAMPOS_CONTEXTO
        ):
            raise ValueError()
        solicitud = evidencia.solicitud_wsfe
        contexto = evidencia.contexto
        if (
            solicitud.punto_venta != contexto.punto_venta_numero
            or solicitud.tipo_cbte != contexto.tipo_comprobante
            or solicitud.cbte_desde != contexto.numero_planificado
            or solicitud.cbte_hasta != contexto.numero_planificado
            or solicitud.imp_total != evidencia.importes_guardado.total
            or len(evidencia.presentacion.items)
            != len(evidencia.importes_guardado.subtotales_items)
        ):
            raise ValueError()
        if "total" in pertenencia and solicitud.imp_total != Decimal(
            str(pertenencia["total"])
        ):
            raise ValueError()
        if "fecha_emision" in pertenencia:
            fecha = pertenencia["fecha_emision"]
            fecha = fecha if isinstance(fecha, date) else date.fromisoformat(fecha)
            if solicitud.fecha_cbte != fecha.strftime("%Y%m%d"):
                raise ValueError()
        if "receptor_tipo_documento" in pertenencia and (
            solicitud.tipo_doc != pertenencia["receptor_tipo_documento"]
            or solicitud.nro_doc != int(pertenencia["receptor_numero_documento"])
        ):
            raise ValueError()
        return evidencia
    except (ValueError, TypeError, KeyError, AttributeError, DecimalException) as exc:
        raise EvidenciaFiscalError(
            "La evidencia fiscal está ausente, alterada o no pertenece al intento"
        ) from exc


def comparar_evidencia(evidencia: EvidenciaFiscalV1, consulta):
    """Sólo compara: no vincula, reconstruye, libera reservas ni cambia estados."""
    resultado = comparar_consulta_fiscal(evidencia.solicitud_wsfe, consulta)
    cuit = getattr(consulta, "cuit_emisor", None)
    disponible = isinstance(cuit, str) and re.fullmatch(r"[0-9]{11}", cuit)
    if disponible and cuit == evidencia.contexto.cuit:
        return resultado
    if disponible:
        diferencias = resultado.campos if resultado.estado == "diferente" else ()
        return ComparacionFiscal(
            "diferente",
            diferencias + ("cuit_emisor",),
            resultado.cobertura_desconocida,
        )
    if resultado.estado == "diferente":
        return resultado
    return ComparacionFiscal(
        "no_disponible",
        tuple(dict.fromkeys((*resultado.campos, "cuit_emisor"))),
        resultado.cobertura_desconocida,
    )
