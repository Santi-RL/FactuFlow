"""Contención preautorización para destinos fiscales bloqueados explícitamente."""

from __future__ import annotations

from app.core.config import BloqueoPreautorizacionArca, settings


CATEGORIA_BLOQUEO_PREAUTORIZACION = "punto_venta_bloqueado_preautorizacion"
MENSAJE_BLOQUEO_PREAUTORIZACION = (
    "El punto de venta está bloqueado preventivamente para esta operación fiscal"
)
DETALLE_BLOQUEO_PREAUTORIZACION = (
    "No se solicitó CAE. Revisá la elegibilidad RECE y la contención operativa "
    "antes de volver a intentar."
)


def obtener_bloqueo_preautorizacion(
    *,
    ambiente: str,
    empresa_id: int,
    punto_venta_id: int,
    punto_venta: int,
    tipo_comprobante: int,
    bloqueos: list[BloqueoPreautorizacionArca] | None = None,
) -> BloqueoPreautorizacionArca | None:
    """Devuelve de forma determinística un bloqueo fiscal coincidente."""
    ambiente_normalizado = ambiente.strip().lower()
    bloqueos_vigentes = (
        settings.arca_bloqueos_preautorizacion if bloqueos is None else bloqueos
    )
    candidatos: list[tuple[int, BloqueoPreautorizacionArca]] = []
    for bloqueo in bloqueos_vigentes:
        coincide_id = bloqueo.punto_venta_id == punto_venta_id
        coincide_numero = bloqueo.punto_venta == punto_venta
        if (
            bloqueo.ambiente == ambiente_normalizado
            and bloqueo.empresa_id == empresa_id
            and (coincide_id or coincide_numero)
            and bloqueo.tipo_comprobante == tipo_comprobante
        ):
            prioridad = (
                3 if coincide_id and coincide_numero else 2 if coincide_id else 1
            )
            candidatos.append((prioridad, bloqueo))
    if not candidatos:
        return None
    candidatos.sort(
        key=lambda candidato: (
            -candidato[0],
            candidato[1].punto_venta_id,
            candidato[1].punto_venta,
            candidato[1].motivo,
        )
    )
    return candidatos[0][1]
