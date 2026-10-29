"""Procedencia de identidad, independiente de las bases e importes fiscales."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class EmisorLectura(BaseModel):
    model_config = ConfigDict(frozen=True)

    cuit: str | None = None
    razon_social: str | None = None
    domicilio: str | None = None
    localidad: str | None = None
    provincia: str | None = None
    condicion_iva: str | None = None
    ingresos_brutos: str | None = None
    inicio_actividades: date | None = None


class LecturaHistorica(BaseModel):
    model_config = ConfigDict(frozen=True)

    cobertura: Literal["completa", "incompleta", "ausente", "no_verificable"]
    origen: Literal["evidencia_previa", "ficha_actual"]
    punto_venta_numero: int
    emisor: EmisorLectura

    @property
    def aviso(self) -> str | None:
        return {
            "completa": None,
            "incompleta": "Datos originales incompletos",
            "ausente": "Sin snapshot histórico. Datos de ficha actual.",
            "no_verificable": (
                "Datos históricos no verificados. Datos de ficha actual. "
                "El PDF no está disponible; consultá al responsable de la instalación."
            ),
        }[self.cobertura]
