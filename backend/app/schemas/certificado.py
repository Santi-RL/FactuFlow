"""Schemas para Certificado."""

from datetime import datetime, date
from typing import Optional, Literal
from pydantic import BaseModel, Field, computed_field


class CertificadoBase(BaseModel):
    """Base schema para Certificado."""

    nombre: str = Field(..., min_length=1, max_length=255)
    cuit: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    fecha_emision: date
    fecha_vencimiento: date
    ambiente: str = Field(..., pattern=r"^(homologacion|produccion)$")


class CertificadoCreate(CertificadoBase):
    """Schema para crear Certificado."""

    archivo_crt: str
    archivo_key: str


class CertificadoUpdate(BaseModel):
    """Schema para actualizar Certificado."""

    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    activo: Optional[bool] = None


class CertificadoResponse(CertificadoBase):
    """Schema de respuesta de Certificado."""

    id: int
    empresa_id: int
    archivo_crt: str
    archivo_key: str
    activo: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def dias_restantes(self) -> int:
        """Calcula días restantes hasta el vencimiento."""
        delta = self.fecha_vencimiento - date.today()
        return delta.days

    @computed_field
    @property
    def estado(self) -> Literal["valido", "por_vencer", "vencido"]:
        """Calcula el estado del certificado."""
        dias = self.dias_restantes
        if dias <= 0:
            return "vencido"
        elif dias <= 30:
            return "por_vencer"
        return "valido"

    class Config:
        from_attributes = True


# Schemas para wizard de certificados


class GenerarCSRRequest(BaseModel):
    """Request para generar CSR."""

    cuit: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    nombre_empresa: str = Field(..., min_length=1, max_length=255)
    ambiente: Literal["homologacion", "produccion"]


class GenerarCSRResponse(BaseModel):
    """Response de generación de CSR."""

    csr: str = Field(..., description="Contenido del CSR en formato PEM")
    key_filename: str = Field(..., description="Nombre del archivo de clave privada")
    mensaje: str


class SubirCertificadoRequest(BaseModel):
    """Request para subir certificado."""

    cuit: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    nombre: str = Field(..., min_length=1, max_length=255)
    ambiente: Literal["homologacion", "produccion"]
    key_filename: str = Field(
        ..., description="Nombre del archivo de clave privada generado"
    )


class VerificacionResponse(BaseModel):
    """Response de verificación de conexión."""

    exito: bool
    mensaje: str
    estado_servidores: Optional[dict] = Field(
        None, description="Estado de servidores ARCA (app, db, auth)"
    )
    error: Optional[str] = None


class CertificadoAlerta(BaseModel):
    """Schema para alertas de vencimiento."""

    id: int
    cuit: str
    nombre: str
    dias_restantes: int
    fecha_vencimiento: date
    ambiente: str
    tipo_alerta: Literal["info", "warning", "danger"]
