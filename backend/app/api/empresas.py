"""Endpoints de Empresas."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.bootstrap import BOOTSTRAP_LOCK, tomar_lock_bootstrap
from app.core.security import (
    get_current_user,
    get_current_admin_user,
    get_current_user_optional,
)
from app.models.usuario import Usuario
from app.models.empresa import Empresa
from app.schemas.empresa import (
    ConstanciaArcaResponse,
    EmpresaCreate,
    EmpresaResponse,
    EmpresaUpdate,
)
from app.services.constancia_arca_service import (
    ConstanciaArcaError,
    extraer_texto_constancia_pdf,
    parsear_constancia_arca,
)

router = APIRouter()


@router.get("", response_model=list[EmpresaResponse])
async def list_empresas(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
):
    """
    Listar todas las empresas (solo admin).

    Args:
        db: Sesión de base de datos
        current_user: Usuario administrador autenticado

    Returns:
        Lista de empresas
    """
    result = await db.execute(select(Empresa))
    empresas = result.scalars().all()
    return empresas


@router.post("", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
async def create_empresa(
    empresa_data: EmpresaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario | None = Depends(get_current_user_optional),
):
    """
    Crear una nueva empresa (solo admin).

    Args:
        empresa_data: Datos de la empresa
        db: Sesión de base de datos
        current_user: Usuario autenticado (opcional en setup inicial)

    Returns:
        Empresa creada

    Raises:
        HTTPException: Si el CUIT ya existe
    """
    async with BOOTSTRAP_LOCK:
        await tomar_lock_bootstrap(db)

        # Permitir creación sin auth solo si no hay usuarios (setup inicial)
        result_users = await db.execute(select(func.count(Usuario.id)))
        user_count = result_users.scalar() or 0

        if user_count > 0:
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No se pudo validar las credenciales",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if not current_user.es_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos de administrador",
                )

        # Verificar que el CUIT no exista
        result = await db.execute(
            select(Empresa).where(Empresa.cuit == empresa_data.cuit)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una empresa con el CUIT {empresa_data.cuit}",
            )

        # Crear empresa
        nueva_empresa = Empresa(**empresa_data.model_dump())
        db.add(nueva_empresa)
        await db.commit()
        await db.refresh(nueva_empresa)

    return nueva_empresa


@router.post("/extraer-constancia", response_model=ConstanciaArcaResponse)
async def extraer_constancia_arca(
    file: UploadFile = File(...),
    _current_user: Usuario = Depends(get_current_admin_user),
):
    """
    Extraer datos fiscales desde una constancia de inscripcion ARCA.

    El endpoint no crea ni actualiza emisores. Solo devuelve datos detectados
    para que el usuario los revise y complete antes de guardar.
    """
    if file.content_type not in {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sube una constancia en formato PDF.",
        )

    contenido = await file.read()
    if len(contenido) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La constancia no puede superar 5 MB.",
        )

    try:
        texto = extraer_texto_constancia_pdf(contenido)
        datos = parsear_constancia_arca(texto)
    except ConstanciaArcaError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return datos.to_dict()


@router.get("/{empresa_id}", response_model=EmpresaResponse)
async def get_empresa(
    empresa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtener una empresa por ID.

    Args:
        empresa_id: ID de la empresa
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Empresa

    Raises:
        HTTPException: Si la empresa no existe o el usuario no tiene permiso
    """
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
        )

    # Verificar permisos: solo admin o usuario de la misma empresa
    if not current_user.es_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta empresa",
        )

    return empresa


@router.put("/{empresa_id}", response_model=EmpresaResponse)
async def update_empresa(
    empresa_id: int,
    empresa_data: EmpresaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualizar una empresa.

    Args:
        empresa_id: ID de la empresa
        empresa_data: Datos a actualizar
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Empresa actualizada

    Raises:
        HTTPException: Si la empresa no existe o el usuario no tiene permiso
    """
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
        )

    # Verificar permisos: solo admin o usuario de la misma empresa
    if not current_user.es_admin and current_user.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar esta empresa",
        )

    # Actualizar campos
    update_data = empresa_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(empresa, field, value)

    await db.commit()
    await db.refresh(empresa)

    return empresa


@router.delete("/{empresa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_empresa(
    empresa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
):
    """
    Eliminar una empresa (solo admin).

    Args:
        empresa_id: ID de la empresa
        db: Sesión de base de datos
        current_user: Usuario administrador autenticado

    Raises:
        HTTPException: Si la empresa no existe
    """
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()

    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
        )

    await db.delete(empresa)
    await db.commit()
