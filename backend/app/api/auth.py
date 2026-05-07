"""Endpoints de autenticación."""

from datetime import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioLogin, Token, UsuarioCreate, UsuarioResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token)
async def login(credentials: UsuarioLogin, db: AsyncSession = Depends(get_db)):
    """
    Login de usuario con email y contraseña.

    Args:
        credentials: Credenciales de login (email, password)
        db: Sesión de base de datos

    Returns:
        Token JWT y datos del usuario

    Raises:
        HTTPException: Si las credenciales son incorrectas
    """
    # Buscar usuario por email
    result = await db.execute(select(Usuario).where(Usuario.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        logger.warning("Login rechazado para email=%s", credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.activo:
        logger.warning("Intento de login con usuario inactivo email=%s", user.email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo"
        )

    # Actualizar último login
    user.ultimo_login = datetime.utcnow()
    await db.commit()

    # Crear token
    access_token = create_access_token(data={"sub": user.email})
    logger.info("Login exitoso usuario_id=%s empresa_id=%s", user.id, user.empresa_id)

    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UsuarioResponse)
async def get_me(current_user: Usuario = Depends(get_current_user)):
    """
    Obtener datos del usuario actual.

    Args:
        current_user: Usuario autenticado

    Returns:
        Datos del usuario actual
    """
    return current_user


@router.post(
    "/setup", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED
)
async def setup_initial_user(
    user_data: UsuarioCreate, db: AsyncSession = Depends(get_db)
):
    """
    Crear primer usuario administrador.
    Solo funciona si no existe ningún usuario en el sistema.

    Args:
        user_data: Datos del usuario a crear
        db: Sesión de base de datos

    Returns:
        Usuario creado

    Raises:
        HTTPException: Si ya existe al menos un usuario
    """
    # Verificar si ya existe algún usuario
    result = await db.execute(select(func.count(Usuario.id)))
    user_count = result.scalar()

    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe al menos un usuario en el sistema. Use /api/auth/login para iniciar sesión.",
        )

    # Crear usuario administrador
    hashed_password = get_password_hash(user_data.password)

    new_user = Usuario(
        email=user_data.email,
        hashed_password=hashed_password,
        nombre=user_data.nombre,
        es_admin=True,  # Primer usuario siempre es admin
        activo=True,
        empresa_id=user_data.empresa_id,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    logger.info("Setup inicial completado con usuario admin id=%s", new_user.id)

    return new_user
