"""Excepciones personalizadas para errores de ARCA."""


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


class ArcaCertificateError(ArcaError):
    """Error relacionado con certificados X.509."""

    def __init__(self, mensaje: str, codigo: str | None = None):
        super().__init__(f"Error de certificado: {mensaje}", codigo)
