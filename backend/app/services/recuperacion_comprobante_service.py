"""Consulta fiscal y recuperación exacta compartidas por emisiones individuales y lotes."""

import logging
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.arca.exceptions import ArcaError
from app.arca.utils import clean_cuit
from app.core.evidencia_fiscal import (
    CAMPOS_CONTEXTO,
    EvidenciaFiscalV1,
    EvidenciaFiscalError,
    comparar_evidencia,
    leer_evidencia,
)
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.idempotencia_fiscal import IntentoEmisionFiscal
from app.services.facturacion_service import FacturacionService, ValidationError

logger = logging.getLogger(__name__)

COBERTURA_OPCIONAL = {
    "cbte_desde",
    "cbte_hasta",
    "condicion_iva_receptor_id",
    "cbtes_asoc.cuit",
    "cbtes_asoc.fecha_cbte",
}


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


def evidencia_del_intento(intento):
    return leer_evidencia(
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


async def consultar_autorizacion_coincidente(db, evidencia) -> tuple[str, date] | None:
    try:
        respuesta = await FacturacionService(db).consultar_intento_individual(
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
        "event=reconciliacion_consulta intento=%s estado=%s campos=%s cobertura=%s",
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


async def recuperar_comprobante(db, intento, evidencia, cae, vencimiento):
    """Reconstruye o vincula sólo un registro de identidad y contenido exactos."""
    datos = _datos_comprobante(evidencia, cae, vencimiento)
    items = _datos_items(evidencia)
    comprobante = (
        await db.execute(
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
        return None
    if comprobante is None:
        comprobante = Comprobante(
            **datos,
            items=[ComprobanteItem(**item) for item in items],
        )
        db.add(comprobante)
        await db.flush()
    elif not contenido_coincidente(comprobante, datos, items):
        return None
    elif (
        await db.scalar(
            select(IntentoEmisionFiscal.id)
            .where(
                IntentoEmisionFiscal.comprobante_id == comprobante.id,
                IntentoEmisionFiscal.id != intento.id,
            )
            .limit(1)
        )
        is not None
    ):
        return None
    return comprobante


def contenido_coincidente(comprobante, datos, items):
    return not (
        any(getattr(comprobante, k) != v for k, v in datos.items())
        or len(comprobante.items) != len(items)
        or any(
            any(getattr(guardado, k) != v for k, v in original.items())
            for guardado, original in zip(
                sorted(comprobante.items, key=lambda item: item.id), items
            )
        )
    )
