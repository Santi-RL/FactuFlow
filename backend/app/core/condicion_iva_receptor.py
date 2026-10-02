"""Condiciones soportadas según el anexo de WSFEv1 v4.7 de ARCA."""

CONDICIONES_IVA_IDS = {"RI": 1, "Monotributo": 6, "Exento": 4, "CF": 5}
_ALIASES = {
    "responsable inscripto": "RI",
    "iva responsable inscripto": "RI",
    "ri": "RI",
    "monotributo": "Monotributo",
    "responsable monotributo": "Monotributo",
    "exento": "Exento",
    "iva sujeto exento": "Exento",
    "consumidor final": "CF",
    "consumidor_final": "CF",
    "cf": "CF",
}
_CLASES = {1: "A", 2: "A", 3: "A", 6: "B", 7: "B", 8: "B", 11: "C", 12: "C", 13: "C"}
_IDS_POR_CLASE = {"A": {1, 6}, "B": {4, 5}, "C": {1, 4, 5, 6}}
_OPCIONES = {
    "A": "Responsable Inscripto o Monotributo",
    "B": "Exento o Consumidor Final",
    "C": "Responsable Inscripto, Monotributo, Exento o Consumidor Final",
}


def normalizar_condicion_iva_receptor(valor: str) -> str | None:
    """Resuelve sólo equivalencias inequívocas; nunca infiere por documento."""
    return _ALIASES.get(" ".join(valor.split()).casefold())


def validar_condicion_iva_receptor_id(valor: int | None, tipo_comprobante: int) -> int:
    """Exige un ID soportado y compatible antes de serializar una solicitud."""
    clase = _CLASES.get(tipo_comprobante)
    if clase is None:
        raise ValueError("El tipo de comprobante no está soportado para emisión.")
    if (
        not isinstance(valor, int)
        or isinstance(valor, bool)
        or valor not in CONDICIONES_IVA_IDS.values()
    ):
        raise ValueError(
            "Seleccioná una condición IVA del receptor válida antes de emitir."
        )
    if valor not in _IDS_POR_CLASE[clase]:
        raise ValueError(
            f"La condición IVA del receptor no corresponde a un comprobante {clase}. "
            f"Seleccioná {_OPCIONES[clase]} según la situación fiscal del receptor."
        )
    return valor


def resolver_condicion_iva_receptor_id(valor: str, tipo_comprobante: int) -> int:
    """Valida un dato de UI/API/archivo sin asignar categorías desconocidas."""
    condicion = normalizar_condicion_iva_receptor(valor)
    if condicion is None:
        raise ValueError(
            "Revisá la condición IVA del receptor: seleccioná Responsable Inscripto, "
            "Monotributo, Exento o Consumidor Final según su situación fiscal. "
            "Responsable No Inscripto requiere corrección explícita."
        )
    return validar_condicion_iva_receptor_id(
        CONDICIONES_IVA_IDS[condicion], tipo_comprobante
    )
