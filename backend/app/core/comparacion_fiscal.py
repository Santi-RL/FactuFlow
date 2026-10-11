"""Comparación fiscal v1 de evidencia histórica; no prepara nuevas emisiones."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from app.arca.models import ComprobanteRequest


@dataclass(frozen=True)
class ComparacionFiscal:
    """Diferencias acreditadas y cobertura insuficiente, sin valores privados."""

    estado: Literal["coincidente", "diferente", "no_disponible"]
    campos: tuple[str, ...] = ()
    cobertura_desconocida: tuple[str, ...] = ()


def decimal_fiscal(valor) -> Decimal:
    """No redondea ni acepta NaN/infinito como evidencia."""
    if valor is None or isinstance(valor, bool):
        raise ValueError("Importe fiscal no disponible")
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Importe fiscal inválido") from exc
    if not numero.is_finite():
        raise ValueError("Importe fiscal no finito")
    return numero


def comparar_consulta_fiscal(
    esperado: ComprobanteRequest, consulta
) -> ComparacionFiscal:
    """Compara componentes enviados, preservando el contrato histórico de WSFE."""
    diferencias: list[str] = []
    faltantes: list[str] = list(getattr(consulta, "campos_invalidos", []) or [])
    cobertura: list[str] = []

    def comparar(campo: str, valor, convertir=None, *, opcional=False) -> None:
        observado = getattr(consulta, campo, None)
        if observado is None:
            (cobertura if opcional else faltantes).append(campo)
            return
        try:
            if convertir:
                observado = convertir(observado)
                valor = convertir(valor)
            if observado != valor:
                diferencias.append(campo)
        except (ValueError, TypeError, InvalidOperation):
            faltantes.append(campo)

    for campo in ("concepto", "tipo_doc", "nro_doc", "punto_venta", "tipo_cbte"):
        comparar(campo, getattr(esperado, campo), int)
    comparar("numero", esperado.cbte_desde, int)
    comparar("fecha_cbte", esperado.fecha_cbte, str)
    comparar("emision_tipo", "CAE", str)
    for campo in ("cbte_desde", "cbte_hasta"):
        # Algunos contratos históricos sólo devuelven CbteNro.
        comparar(campo, getattr(esperado, campo), int, opcional=True)
    for campo in (
        "imp_total",
        "imp_neto",
        "imp_iva",
        "imp_op_ex",
        "imp_tot_conc",
        "imp_trib",
        "moneda_cotiz",
    ):
        comparar(campo, getattr(esperado, campo), decimal_fiscal)
    comparar("moneda_id", esperado.moneda_id, str)
    if esperado.condicion_iva_receptor_id is not None:
        # No se inventa condición para consultas antiguas que no la devuelven.
        comparar(
            "condicion_iva_receptor_id",
            esperado.condicion_iva_receptor_id,
            int,
            opcional=True,
        )
    else:
        cobertura.append("condicion_iva_receptor_id")
    for campo in ("fecha_serv_desde", "fecha_serv_hasta", "fecha_vto_pago"):
        valor = getattr(esperado, campo)
        observado = getattr(consulta, campo, None) or None
        if valor is not None and observado is None:
            faltantes.append(campo)
        elif valor != observado:
            diferencias.append(campo)

    def iva(item):
        return (
            int(item.id),
            decimal_fiscal(item.base_imp),
            decimal_fiscal(item.importe),
        )

    def tributo(item):
        return (
            int(item.id),
            str(item.descripcion),
            decimal_fiscal(item.base_imp),
            decimal_fiscal(item.alic),
            decimal_fiscal(item.importe),
        )

    def asociado(item):
        return (int(item.tipo), int(item.punto_venta), int(item.numero))

    for campo, convertir in (
        ("iva", iva),
        ("tributos", tributo),
        ("cbtes_asoc", asociado),
    ):
        originales = getattr(esperado, campo)
        observados = getattr(consulta, campo, None)
        if observados is None and originales:
            faltantes.append(campo)
            continue
        try:
            if Counter(map(convertir, originales)) != Counter(
                map(convertir, observados or [])
            ):
                diferencias.append(campo)
                continue
            if campo == "cbtes_asoc":
                # Atributos opcionales no presentes en todos los contratos de consulta.
                for atributo in ("cuit", "fecha_cbte"):
                    enviados = Counter(
                        (asociado(item), getattr(item, atributo))
                        for item in originales
                        if getattr(item, atributo) is not None
                    )
                    if not enviados:
                        continue
                    disponibles = Counter(
                        (asociado(item), getattr(item, atributo, None))
                        for item in observados or []
                    )
                    contradice = any(
                        getattr(item, atributo, None) is not None
                        and not any(
                            asociado(original) == asociado(item)
                            and getattr(original, atributo)
                            in (None, getattr(item, atributo))
                            for original in originales
                        )
                        for item in observados or []
                    )
                    if contradice:
                        diferencias.append(f"cbtes_asoc.{atributo}")
                    elif any(
                        getattr(item, atributo, None) is None
                        for item in observados or []
                    ):
                        cobertura.append(f"cbtes_asoc.{atributo}")
                    elif any(
                        disponibles[clave] < cantidad
                        for clave, cantidad in enviados.items()
                    ):
                        diferencias.append(f"cbtes_asoc.{atributo}")
        except (ValueError, TypeError, AttributeError):
            faltantes.append(campo)
    if getattr(consulta, "adicionales_presentes", None):
        diferencias.append("adicionales_no_enviados")
    return ComparacionFiscal(
        "diferente" if diferencias else "no_disponible" if faltantes else "coincidente",
        tuple(diferencias or faltantes),
        tuple(cobertura),
    )
