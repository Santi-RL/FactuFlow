"""Proyección de sólo lectura, sin admisibilidad, escrituras ni servicios ARCA."""

import re
from collections import defaultdict
from datetime import date

from sqlalchemy import and_, case, or_, select

from app.core.evidencia_fiscal import (
    CAMPOS_CONTEXTO,
    EvidenciaFiscalError,
    leer_evidencia,
)
from app.models.idempotencia_fiscal import IntentoEmisionFiscal as Intento
from app.schemas.lectura_historica import EmisorLectura, LecturaHistorica

ERROR_HISTORIA_PDF = (
    "Datos históricos no verificados. El PDF no está disponible; "
    "consultá al responsable de la instalación."
)


class HistoriaNoVerificableError(ValueError):
    """Error público sin material del documento ni detalles del vínculo."""


def exigir_historia_pdf(lectura: LecturaHistorica) -> None:
    if lectura.cobertura == "no_verificable":
        raise HistoriaNoVerificableError(ERROR_HISTORIA_PDF)


def lectura_actual(comprobante, empresa=None, *, cobertura="ausente"):
    """Conserva la fuente anterior explícitamente, sin atribuir originalidad."""
    empresa = empresa if empresa is not None else comprobante.empresa
    emisor = {name: getattr(empresa, name, None) for name in EmisorLectura.model_fields}
    return LecturaHistorica(
        cobertura=cobertura,
        origen="ficha_actual",
        punto_venta_numero=(
            comprobante.punto_venta.numero if comprobante.punto_venta else 0
        ),
        emisor=EmisorLectura(**emisor),
    )


def proyectar_original(comprobante, intento) -> LecturaHistorica:
    """Exige correspondencia con hechos guardados, nunca con fichas vigentes."""
    evidencia = leer_evidencia(
        version=intento.evidencia_version,
        raw=intento.evidencia_json,
        sha256=intento.evidencia_hash,
        pertenencia={
            name: getattr(intento, name)
            for name in (
                *CAMPOS_CONTEXTO,
                "total",
                "fecha_emision",
                "receptor_tipo_documento",
                "receptor_numero_documento",
            )
        },
    )
    solicitud = evidencia.solicitud_wsfe
    receptor = evidencia.presentacion.receptor
    if (
        intento.estado != "autorizado"
        or comprobante.estado != "autorizado"
        or intento.comprobante_id != comprobante.id
        or intento.empresa_id != comprobante.empresa_id
        or intento.punto_venta_id != comprobante.punto_venta_id
        or intento.tipo_comprobante != comprobante.tipo_comprobante
        or intento.numero_planificado != comprobante.numero
        or intento.fecha_emision != comprobante.fecha_emision
        or intento.total != comprobante.total
        or not comprobante.cae
        or not comprobante.cae_vencimiento
        or intento.cae != comprobante.cae
        or intento.cae_vencimiento != comprobante.cae_vencimiento
        or solicitud.tipo_doc != comprobante.receptor_tipo_documento
        or solicitud.nro_doc != int(comprobante.receptor_numero_documento)
        or receptor.razon_social != comprobante.receptor_razon_social
        or receptor.condicion_iva != comprobante.receptor_condicion_iva
        or solicitud.moneda_id != comprobante.moneda
        or solicitud.moneda_cotiz != comprobante.cotizacion
        or not re.fullmatch(r"[0-9]{11}", evidencia.contexto.cuit)
        or int(evidencia.contexto.cuit) == 0
        or evidencia.contexto.punto_venta_numero <= 0
    ):
        raise EvidenciaFiscalError("La fuente no acredita este comprobante")
    datos = evidencia.presentacion.emisor.model_dump()
    if datos["inicio_actividades"] is not None:
        datos["inicio_actividades"] = date.fromisoformat(datos["inicio_actividades"])
    return LecturaHistorica(
        cobertura="completa" if all(datos.values()) else "incompleta",
        origen="evidencia_previa",
        punto_venta_numero=evidencia.contexto.punto_venta_numero,
        emisor=EmisorLectura(cuit=evidencia.contexto.cuit, **datos),
    )


async def cargar_lecturas_historicas(db, comprobantes):
    """Carga sólo la página/período seleccionado, en bloques de hasta 100 IDs.

    Cada bloque observa vínculos y documentos en una sola consulta. SQL sólo
    entrega el material de intentos autorizados propios; de vínculos ajenos se
    leen identidades y presencia, nunca el documento. No adjunta objetos ORM ni
    conserva documentos en una caché y no cambia los conteos o el orden.
    """
    lecturas = {}
    with db.no_autoflush:
        for inicio in range(0, len(comprobantes), 100):
            bloque = comprobantes[inicio : inicio + 100]
            por_id = {comp.id: comp for comp in bloque}
            vinculados = defaultdict(list)
            por_emisor = defaultdict(list)
            for comp in bloque:
                por_emisor[comp.empresa_id].append(comp.id)
            propia_autorizada = and_(
                Intento.estado == "autorizado",
                or_(
                    *(
                        and_(
                            Intento.comprobante_id.in_(ids),
                            Intento.empresa_id == empresa_id,
                        )
                        for empresa_id, ids in por_emisor.items()
                    )
                ),
            )
            presentes = or_(
                Intento.evidencia_version.is_not(None),
                Intento.evidencia_json.is_not(None),
                Intento.evidencia_hash.is_not(None),
            )
            publicas = ("id", "empresa_id", "comprobante_id", "estado")
            privadas = tuple(
                dict.fromkeys(
                    (
                        *CAMPOS_CONTEXTO,
                        "total",
                        "fecha_emision",
                        "receptor_tipo_documento",
                        "receptor_numero_documento",
                        "cae",
                        "cae_vencimiento",
                        "evidencia_version",
                        "evidencia_json",
                        "evidencia_hash",
                    )
                )
            )
            filas = await db.execute(
                select(
                    *(getattr(Intento, name) for name in publicas),
                    presentes.label("presente"),
                    *(
                        case(
                            (propia_autorizada, getattr(Intento, name)), else_=None
                        ).label(name)
                        for name in privadas
                        if name not in publicas
                    ),
                ).where(Intento.comprobante_id.in_(por_id))
            )
            for fila in filas:
                vinculados[fila.comprobante_id].append(fila)
            for comp in bloque:
                fuentes = vinculados[comp.id]
                autorizados = [f for f in fuentes if f.estado == "autorizado"]
                cruzados = any(f.empresa_id != comp.empresa_id for f in fuentes)
                ambiguos = len(autorizados) > 1
                presente = any(f.presente for f in fuentes)
                cobertura = "ausente"
                if cruzados or ambiguos or (presente and not autorizados):
                    cobertura = "no_verificable"
                elif autorizados and autorizados[0].presente:
                    try:
                        lecturas[comp.id] = proyectar_original(comp, autorizados[0])
                        continue
                    except (
                        EvidenciaFiscalError,
                        ValueError,
                        TypeError,
                        AttributeError,
                    ):
                        cobertura = "no_verificable"
                # Un rechazado previo no sustituye al autorizado sin snapshot.
                lecturas[comp.id] = lectura_actual(comp, cobertura=cobertura)
    return lecturas
