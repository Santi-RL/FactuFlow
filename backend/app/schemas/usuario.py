"""Schemas para Usuario."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


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


class UsuarioPasswordReset(BaseModel):
    """Schema para restablecer la contraseña de un usuario."""

    password: str = Field(..., min_length=6, max_length=100)


class UsuarioResponse(UsuarioBase):
    """Schema de respuesta de Usuario."""

    id: int
    activo: bool
    es_admin: bool
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
