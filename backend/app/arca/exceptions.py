"""Excepciones personalizadas para errores de ARCA."""

from dataclasses import dataclass
from typing import Literal


class ArcaError(Exception):
    """Error base para todos los errores de ARCA."""

    def __init__(self, mensaje: str, codigo: str | None = None):
        self.mensaje = mensaje
        self.codigo = codigo
        super().__init__(mensaje)


class ArcaAuthError(ArcaError):
    """Error de autenticación con WSAA."""

    def __init__(self, mensaje: str, codigo: str | None = None):
        super().__init__(f"Error de autenticación ARCA: {mensaje}", codigo)


class ArcaValidationError(ArcaError):
    """Error de validación de datos enviados a ARCA."""

    def __init__(self, mensaje: str, codigo: str | None = None):
        super().__init__(f"Error de validación ARCA: {mensaje}", codigo)


class ArcaConnectionError(ArcaError):
    """Error de conexión con los webservices de ARCA."""

    def __init__(self, mensaje: str, codigo: str | None = None):
        super().__init__(f"Error de conexión con ARCA: {mensaje}", codigo)


class ArcaServiceError(ArcaError):
    """Error del servicio web de ARCA."""

    def __init__(self, mensaje: str, codigo: str | None = None):
        super().__init__(f"Error del servicio ARCA: {mensaje}", codigo)


@dataclass(frozen=True)
class MensajeArcaEstructurado:
    """Conserva código y texto crudo de un error o evento WSFE."""

    codigo: object
    mensaje: str


@dataclass(frozen=True)
class CabeceraRespuestaFecae:
    """Conserva la cabecera recibida de ``FECAESolicitar`` sin coerciones."""

    cuit: object
    punto_venta: object
    tipo_comprobante: object
    cantidad: object
    resultado: object


class ArcaErrorGlobalEstructurado(ArcaServiceError):
    """Expone evidencia estructurada de un error global de ``FECAESolicitar``."""

    def __init__(
        self,
        *,
        cabecera: CabeceraRespuestaFecae | None,
        errores: tuple[MensajeArcaEstructurado, ...],
        eventos: tuple[MensajeArcaEstructurado, ...],
        detalles_presentes: bool,
        senales_cae_presentes: bool,
        request_cuit: int,
        request_punto_venta: int,
        request_tipo_comprobante: int,
        request_cantidad: int,
        request_rangos: tuple[tuple[int, int], ...],
    ) -> None:
        """Inicializa la evidencia sin usar mensajes libres para clasificar."""
        self.operacion = "FECAESolicitar"
        self.cabecera = cabecera
        self.errores = errores
        self.eventos = eventos
        self.detalles_presentes = detalles_presentes
        self.senales_cae_presentes = senales_cae_presentes
        self.request_cuit = request_cuit
        self.request_punto_venta = request_punto_venta
        self.request_tipo_comprobante = request_tipo_comprobante
        self.request_cantidad = request_cantidad
        self.request_rangos = request_rangos
        super().__init__(
            "ARCA devolvió errores globales estructurados al solicitar CAE"
        )


def clasificar_error_global_fecae(
    error: ArcaErrorGlobalEstructurado,
) -> Literal["rechazo_global_excluyente", "respuesta_incierta"]:
    """Clasifica exclusivamente el contrato exacto y documentado del código 10005."""
    cabecera = error.cabecera
    if error.operacion != "FECAESolicitar" or cabecera is None:
        return "respuesta_incierta"

    enteros_exactos = (
        (cabecera.cuit, error.request_cuit),
        (cabecera.punto_venta, error.request_punto_venta),
        (cabecera.tipo_comprobante, error.request_tipo_comprobante),
        (cabecera.cantidad, error.request_cantidad),
    )
    if any(
        not isinstance(recibido, int)
        or isinstance(recibido, bool)
        or recibido != esperado
        for recibido, esperado in enteros_exactos
    ):
        return "respuesta_incierta"
    if not isinstance(cabecera.resultado, str) or cabecera.resultado != "R":
        return "respuesta_incierta"
    if len(error.errores) != 1:
        return "respuesta_incierta"
    if (
        not isinstance(error.errores[0].codigo, int)
        or isinstance(error.errores[0].codigo, bool)
        or error.errores[0].codigo != 10005
    ):
        return "respuesta_incierta"
    if error.detalles_presentes or error.senales_cae_presentes:
        return "respuesta_incierta"
    if (
        not isinstance(error.request_cantidad, int)
        or isinstance(error.request_cantidad, bool)
        or error.request_cantidad < 1
        or len(error.request_rangos) != error.request_cantidad
        or len(set(error.request_rangos)) != len(error.request_rangos)
        or any(
            not isinstance(desde, int)
            or isinstance(desde, bool)
            or not isinstance(hasta, int)
            or isinstance(hasta, bool)
            or desde < 1
            or hasta != desde
            for desde, hasta in error.request_rangos
        )
    ):
        return "respuesta_incierta"
    return "rechazo_global_excluyente"


class ArcaCertificateError(ArcaError):
    """Error relacionado con certificados X.509."""

    def __init__(self, mensaje: str, codigo: str | None = None):
        super().__init__(f"Error de certificado: {mensaje}", codigo)
