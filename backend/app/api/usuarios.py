"""Endpoints de administración de usuarios."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bootstrap import USER_ADMIN_LOCK, tomar_lock_admin_usuarios
from app.core.database import get_db
from app.core.security import get_current_admin_user, get_password_hash
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.schemas.usuario import (
    UsuarioAdminCreate,
    UsuarioAdminUpdate,
    UsuarioPasswordReset,
    UsuarioResponse,
)

router = APIRouter()


def _normalizar_email(email: str) -> str:
    """Normaliza emails antes de persistir o comparar usuarios."""
    return email.strip().lower()


async def _get_usuario_or_404(db: AsyncSession, usuario_id: int) -> Usuario:
    """Obtiene un usuario por ID o responde 404."""
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    usuario = result.scalar_one_or_none()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return usuario


async def _validar_empresa_opcional(
    db: AsyncSession, empresa_id: int | None
) -> int | None:
    """Verifica que el emisor preferido exista cuando se informa."""
    if empresa_id is None:
        return None

    result = await db.execute(select(Empresa.id).where(Empresa.id == empresa_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La empresa asignada no existe",
        )
    return empresa_id


async def _get_usuario_by_email(db: AsyncSession, email: str) -> Usuario | None:
    """Busca un usuario por email normalizado."""
    result = await db.execute(select(Usuario).where(func.lower(Usuario.email) == email))
    return result.scalars().first()


async def _count_admins_activos(db: AsyncSession) -> int:
    """Cuenta administradores activos para evitar bloquear el sistema."""
    result = await db.execute(
        select(func.count(Usuario.id)).where(
            Usuario.es_admin.is_(True),
            Usuario.activo.is_(True),
        )
    )
    return result.scalar() or 0


async def _validar_no_quitar_ultimo_admin(
    db: AsyncSession,
    usuario: Usuario,
    *,
    nuevo_activo: bool | None = None,
    nuevo_es_admin: bool | None = None,
) -> None:
    """Impide que la operación deje el sistema sin administrador activo."""
    activo_final = usuario.activo if nuevo_activo is None else nuevo_activo
    es_admin_final = usuario.es_admin if nuevo_es_admin is None else nuevo_es_admin

    if usuario.activo and usuario.es_admin and (not activo_final or not es_admin_final):
        if await _count_admins_activos(db) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe quedar al menos un usuario administrador activo",
            )


@router.get("", response_model=list[UsuarioResponse])
async def list_usuarios(
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """
    Listar usuarios del sistema.

    Returns:
        Usuarios activos e inactivos, sin hashes de contraseña
    """
    result = await db.execute(
        select(Usuario).order_by(Usuario.activo.desc(), Usuario.nombre.asc())
    )
    return result.scalars().all()


@router.post("", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    usuario_data: UsuarioAdminCreate,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """
    Crear un usuario desde el menú de administración.

    Los usuarios comunes quedan habilitados para operar todos los emisores. El
    campo `empresa_id`, cuando existe, solo funciona como emisor preferido.
    """
    async with USER_ADMIN_LOCK:
        await tomar_lock_admin_usuarios(db)
        email = _normalizar_email(str(usuario_data.email))
        if await _get_usuario_by_email(db, email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un usuario con ese email",
            )

        empresa_id = await _validar_empresa_opcional(db, usuario_data.empresa_id)
        usuario = Usuario(
            email=email,
            hashed_password=get_password_hash(usuario_data.password),
            nombre=usuario_data.nombre,
            activo=usuario_data.activo,
            es_admin=usuario_data.es_admin,
            empresa_id=empresa_id,
            password_changed_at=datetime.utcnow(),
        )

        db.add(usuario)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un usuario con ese email",
            ) from exc
        await db.refresh(usuario)
        return usuario


@router.put("/{usuario_id}", response_model=UsuarioResponse)
async def update_usuario(
    usuario_id: int,
    usuario_data: UsuarioAdminUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin_user),
):
    """
    Actualizar datos, estado o rol de un usuario.

    Raises:
        HTTPException: Si se intenta dejar el sistema sin administrador activo
    """
    async with USER_ADMIN_LOCK:
        await tomar_lock_admin_usuarios(db)
        usuario = await _get_usuario_or_404(db, usuario_id)
        update_data = usuario_data.model_dump(exclude_unset=True)
        for campo in ("email", "nombre", "es_admin", "activo"):
            if campo in update_data and update_data[campo] is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El campo {campo} no puede ser nulo",
                )

        nuevo_activo = update_data.get("activo")
        nuevo_es_admin = update_data.get("es_admin")
        if usuario.id == admin.id:
            if "email" in update_data and _normalizar_email(
                str(update_data["email"])
            ) != _normalizar_email(usuario.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No puedes cambiar el email de tu propio usuario desde esta sesión",
                )
            if nuevo_activo is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No puedes desactivar tu propio usuario",
                )
            if nuevo_es_admin is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No puedes quitarte permisos de administrador",
                )

        await _validar_no_quitar_ultimo_admin(
            db,
            usuario,
            nuevo_activo=nuevo_activo,
            nuevo_es_admin=nuevo_es_admin,
        )

        if "email" in update_data:
            email = _normalizar_email(str(update_data["email"]))
            if email != _normalizar_email(usuario.email):
                usuario_existente = await _get_usuario_by_email(db, email)
                if usuario_existente and usuario_existente.id != usuario.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Ya existe un usuario con ese email",
                    )
                usuario.email = email

        if "nombre" in update_data:
            usuario.nombre = update_data["nombre"]
        if "empresa_id" in update_data:
            usuario.empresa_id = await _validar_empresa_opcional(
                db, update_data["empresa_id"]
            )
        if "es_admin" in update_data:
            usuario.es_admin = update_data["es_admin"]
        if "activo" in update_data:
            usuario.activo = update_data["activo"]

        await db.commit()
        await db.refresh(usuario)
        return usuario


@router.post("/{usuario_id}/desactivar", response_model=UsuarioResponse)
async def desactivar_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin_user),
):
    """
    Desactivar un usuario sin borrar su historial.

    Raises:
        HTTPException: Si el administrador intenta desactivarse a sí mismo
    """
    async with USER_ADMIN_LOCK:
        await tomar_lock_admin_usuarios(db)
        usuario = await _get_usuario_or_404(db, usuario_id)
        if usuario.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes desactivar tu propio usuario",
            )

        await _validar_no_quitar_ultimo_admin(db, usuario, nuevo_activo=False)
        usuario.activo = False
        await db.commit()
        await db.refresh(usuario)
        return usuario


@router.post("/{usuario_id}/reactivar", response_model=UsuarioResponse)
async def reactivar_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """Reactivar un usuario previamente desactivado."""
    usuario = await _get_usuario_or_404(db, usuario_id)
    usuario.activo = True
    await db.commit()
    await db.refresh(usuario)
    return usuario


@router.post("/{usuario_id}/reset-password", response_model=UsuarioResponse)
async def reset_password_usuario(
    usuario_id: int,
    password_data: UsuarioPasswordReset,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin_user),
):
    """Restablecer la contraseña de un usuario."""
    usuario = await _get_usuario_or_404(db, usuario_id)
    usuario.hashed_password = get_password_hash(password_data.password)
    usuario.password_changed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(usuario)
    return usuario
