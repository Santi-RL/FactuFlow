"""
Módulo de integración con ARCA (Agencia de Recaudación y Control Aduanero).

Nota: Aunque el organismo cambió su nombre de AFIP a ARCA, los webservices
mantienen las URLs y nomenclaturas heredadas (ej: wsaa.afip.gov.ar) por
compatibilidad técnica.
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
