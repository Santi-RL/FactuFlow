"""
Módulo de integración con ARCA (Agencia de Recaudación y Control Aduanero).

Nota: los webservices mantienen URLs heredadas como `wsaa.afip.gov.ar` por
compatibilidad tecnica.
"""

from .config import ArcaAmbiente, ArcaConfig
from .exceptions import (
    ArcaError,
    ArcaAuthError,
    ArcaValidationError,
    ArcaConnectionError,
    ArcaServiceError,
)

__all__ = [
    "ArcaAmbiente",
    "ArcaConfig",
    "ArcaError",
    "ArcaAuthError",
    "ArcaValidationError",
    "ArcaConnectionError",
    "ArcaServiceError",
]
