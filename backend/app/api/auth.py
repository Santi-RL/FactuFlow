"""Endpoints de autenticación."""

from datetime import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.bootstrap import BOOTSTRAP_LOCK, tomar_lock_bootstrap
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)
from app.models.usuario import Usuario
from app.schemas.usuario import (
    SetupStatus,
    Token,
    UsuarioCreate,
    UsuarioLogin,
    UsuarioResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _credentials_exception() -> HTTPException:
    """Construye una respuesta genérica para credenciales inválidas."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _normalizar_email(email: str) -> str:
    """Normaliza emails para búsquedas y altas de usuarios."""
    return email.strip().lower()


async def _count_usuarios(db: AsyncSession) -> int:
    """Cuenta usuarios existentes para resolver el estado de instalación."""
    result = await db.execute(select(func.count(Usuario.id)))
    return result.scalar() or 0


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
    email_raw = str(credentials.email).strip()
    email = _normalizar_email(email_raw)

    # Buscar usuario por email exacto primero para instalaciones legacy.
    result = await db.execute(select(Usuario).where(Usuario.email == email_raw))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(
            select(Usuario).where(func.lower(Usuario.email) == email)
        )
        usuarios = result.scalars().all()
        if len(usuarios) > 1:
            logger.error(
                "Login ambiguo por emails duplicados en distinta capitalización"
            )
            raise _credentials_exception()
        user = usuarios[0] if usuarios else None

    if not user or not verify_password(credentials.password, user.hashed_password):
        logger.warning("Login rechazado para email=%s", email)
        raise _credentials_exception()

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


@router.get("/setup-status", response_model=SetupStatus)
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    """
    Indicar si el sistema todavía requiere configuración inicial.

    Returns:
        Estado de setup requerido
    """
    user_count = await _count_usuarios(db)
    return SetupStatus(setup_required=user_count == 0)


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
    async with BOOTSTRAP_LOCK:
        await tomar_lock_bootstrap(db)

        # Verificar si ya existe algún usuario dentro del lock de bootstrap
        user_count = await _count_usuarios(db)

        if user_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe al menos un usuario en el sistema. Use /api/auth/login para iniciar sesión.",
            )

        # Crear usuario administrador
        hashed_password = get_password_hash(user_data.password)

        new_user = Usuario(
            email=_normalizar_email(str(user_data.email)),
            hashed_password=hashed_password,
            nombre=user_data.nombre,
            es_admin=True,  # Primer usuario siempre es admin
            activo=True,
            empresa_id=user_data.empresa_id,
            password_changed_at=datetime.utcnow(),
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
    logger.info("Setup inicial completado con usuario admin id=%s", new_user.id)

    return new_user
