"""Schemas para Usuario."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


def _normalizar_empresa_ids(value: list[int] | None) -> list[int] | None:
    """Valida una lista explícita sin ocultar duplicados del cliente."""
    if value is None:
        return None
    if any(empresa_id <= 0 for empresa_id in value):
        raise ValueError("Los IDs de emisores deben ser positivos")
    if len(value) != len(set(value)):
        raise ValueError("La lista de emisores no puede contener duplicados")
    return sorted(value)


class UsuarioBase(BaseModel):
    """Base schema para Usuario."""

    email: EmailStr
    nombre: str = Field(..., min_length=1, max_length=255)
    empresa_id: Optional[int] = None


class UsuarioCreate(UsuarioBase):
    """Schema para crear Usuario."""

    password: str = Field(..., min_length=6, max_length=100)
    es_admin: bool = False


class UsuarioAdminCreate(BaseModel):
    """Schema para que un administrador cree usuarios operativos."""

    email: EmailStr
    nombre: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=6, max_length=100)
    es_admin: bool = False
    activo: bool = True
    empresa_id: Optional[int] = None
    empresa_ids: Optional[list[int]] = None
    puede_crear_editar_emisores: bool = False

    _validar_empresa_ids = field_validator("empresa_ids")(_normalizar_empresa_ids)

    @model_validator(mode="after")
    def validar_contrato_empresas(self):
        if "empresa_ids" in self.model_fields_set and self.empresa_ids is None:
            raise ValueError("empresa_ids debe ser una lista")
        if {"empresa_id", "empresa_ids"}.issubset(self.model_fields_set):
            raise ValueError("No envíes empresa_id y empresa_ids al mismo tiempo")
        return self


class UsuarioUpdate(BaseModel):
    """Schema para actualizar Usuario."""

    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    activo: Optional[bool] = None
    empresa_id: Optional[int] = None


class UsuarioAdminUpdate(BaseModel):
    """Schema para administrar datos y rol de un usuario existente."""

    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    es_admin: Optional[bool] = None
    activo: Optional[bool] = None
    empresa_id: Optional[int] = None
    empresa_ids: Optional[list[int]] = None
    puede_crear_editar_emisores: Optional[bool] = None

    _validar_empresa_ids = field_validator("empresa_ids")(_normalizar_empresa_ids)

    @model_validator(mode="after")
    def validar_contrato_empresas(self):
        if "empresa_ids" in self.model_fields_set and self.empresa_ids is None:
            raise ValueError("empresa_ids debe ser una lista")
        if {"empresa_id", "empresa_ids"}.issubset(self.model_fields_set):
            raise ValueError("No envíes empresa_id y empresa_ids al mismo tiempo")
        return self


class UsuarioPasswordReset(BaseModel):
    """Schema para restablecer la contraseña de un usuario."""

    password: str = Field(..., min_length=6, max_length=100)


class UsuarioResponse(UsuarioBase):
    """Schema de respuesta de Usuario."""

    id: int
    activo: bool
    es_admin: bool
    empresa_ids: list[int] = Field(default_factory=list)
    puede_crear_editar_emisores: bool = False
    created_at: datetime
    ultimo_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UsuarioLogin(BaseModel):
    """Schema para login."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema de respuesta de token."""

    access_token: str
    token_type: str = "bearer"
    user: UsuarioResponse


class SetupStatus(BaseModel):
    """Estado de instalación inicial del sistema."""

    setup_required: bool
