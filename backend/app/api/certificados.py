"""Endpoints de Certificados."""

import logging
from datetime import date
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    status,
    Query,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_empresa_user
from app.models.usuario import Usuario
from app.models.certificado import Certificado
from app.models.empresa import Empresa
from app.core.config import settings
from app.schemas.certificado import (
    CertificadoResponse,
    GenerarCSRRequest,
    GenerarCSRResponse,
    SubirCertificadoRequest,
    VerificacionResponse,
    CertificadoAlerta,
)
from app.services.certificados_service import CertificadosService
from app.arca.wsaa import WSAAClient
from app.arca.config import ArcaAmbiente
from app.arca.exceptions import ArcaCertificateError, ArcaAuthError, ArcaConnectionError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[CertificadoResponse])
async def list_certificados(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Listar certificados.

    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Lista de certificados
    """
    query = select(Certificado)

    if not current_user.es_admin:
        query = query.where(Certificado.empresa_id == current_user.empresa_id)

    result = await db.execute(query)
    certificados = result.scalars().all()

    return certificados


@router.get("/keys", response_model=list[str])
async def list_keys(
    cuit: str = Query(..., pattern=r"^\d{11}$"),
    ambiente: str = Query(..., pattern=r"^(homologacion|produccion)$"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Listar claves privadas disponibles para un CUIT y ambiente.

    Args:
        cuit: CUIT asociado
        ambiente: "homologacion" o "produccion"
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Lista de nombres de archivos .key disponibles
    """
    if not current_user.es_admin:
        result = await db.execute(
            select(Empresa.cuit).where(Empresa.id == current_user.empresa_id)
        )
        empresa_cuit = result.scalar_one_or_none()
        if empresa_cuit != cuit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para listar claves de otro CUIT",
            )

    certs_path = Path(settings.certs_path)
    if not certs_path.exists():
        return []

    pattern = f"{cuit}_{ambiente}_*.key"
    keys = sorted([p.name for p in certs_path.glob(pattern)], reverse=True)
    return keys


@router.get("/alertas-vencimiento", response_model=List[CertificadoAlerta])
async def obtener_alertas_vencimiento(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene certificados próximos a vencer para mostrar alertas.

    Devuelve certificados que:
    - Están activos
    - Vencen en los próximos 30 días o ya vencieron

    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Lista de certificados con alertas de vencimiento
    """
    query = select(Certificado).where(Certificado.activo)

    if not current_user.es_admin:
        query = query.where(Certificado.empresa_id == current_user.empresa_id)

    result = await db.execute(query)
    certificados = result.scalars().all()

    # Filtrar y calcular alertas
    alertas = []
    service = CertificadosService()
    hoy = date.today()

    for cert in certificados:
        dias_restantes = (cert.fecha_vencimiento - hoy).days

        # Solo incluir si está próximo a vencer o ya venció
        if dias_restantes <= 30:
            alertas.append(
                CertificadoAlerta(
                    id=cert.id,
                    cuit=cert.cuit,
                    nombre=cert.nombre,
                    dias_restantes=dias_restantes,
                    fecha_vencimiento=cert.fecha_vencimiento,
                    ambiente=cert.ambiente,
                    tipo_alerta=service.get_tipo_alerta(dias_restantes),
                )
            )

    # Ordenar por días restantes (más urgente primero)
    alertas.sort(key=lambda x: x.dias_restantes)

    return alertas


@router.get("/{certificado_id}", response_model=CertificadoResponse)
async def get_certificado(
    certificado_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtener un certificado por ID.

    Args:
        certificado_id: ID del certificado
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Certificado

    Raises:
        HTTPException: Si el certificado no existe o no pertenece a la empresa
    """
    result = await db.execute(
        select(Certificado).where(Certificado.id == certificado_id)
    )
    certificado = result.scalar_one_or_none()

    if not certificado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificado no encontrado"
        )

    # Verificar permisos
    if not current_user.es_admin and certificado.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este certificado",
        )

    return certificado


@router.delete("/{certificado_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certificado(
    certificado_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Eliminar un certificado.

    Args:
        certificado_id: ID del certificado
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Raises:
        HTTPException: Si el certificado no existe o no pertenece a la empresa
    """
    result = await db.execute(
        select(Certificado).where(Certificado.id == certificado_id)
    )
    certificado = result.scalar_one_or_none()

    if not certificado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificado no encontrado"
        )

    # Verificar permisos
    if not current_user.es_admin and certificado.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este certificado",
        )

    await db.delete(certificado)
    await db.commit()


@router.post("/generar-csr", response_model=GenerarCSRResponse)
async def generar_csr(
    data: GenerarCSRRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Genera clave privada RSA 2048 y CSR para un CUIT.

    Este endpoint:
    - Genera una clave privada RSA de 2048 bits
    - Crea un CSR (Certificate Signing Request) con datos de ARCA
    - Guarda la clave privada encriptada en el servidor
    - Devuelve el CSR para que el usuario lo suba al portal de ARCA

    Args:
        data: Datos para generar el CSR (CUIT, nombre empresa, ambiente)
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        CSR en formato PEM y nombre del archivo de clave

    Raises:
        HTTPException: Si hay error en la generación
    """
    try:
        logger.info(f"Generando CSR para CUIT: {data.cuit}")

        service = CertificadosService()
        key_path, csr_pem, key_filename = await service.generar_clave_y_csr(
            cuit=data.cuit, nombre_empresa=data.nombre_empresa, ambiente=data.ambiente
        )

        return GenerarCSRResponse(
            csr=csr_pem,
            key_filename=key_filename,
            mensaje="CSR generado exitosamente. Descargá el archivo y subilo al portal de ARCA.",
        )

    except ArcaCertificateError as e:
        logger.error(f"Error generando CSR: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error inesperado generando CSR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al generar CSR",
        )


@router.post("/subir-certificado", response_model=CertificadoResponse)
async def subir_certificado(
    file: UploadFile = File(...),
    cuit: str = Form(...),
    nombre: str = Form(...),
    ambiente: str = Form(...),
    key_filename: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Recibe el certificado .crt del portal de ARCA y lo valida.

    Este endpoint:
    - Valida el formato del certificado
    - Verifica que coincida con la clave privada generada
    - Extrae fechas de validez
    - Guarda el certificado en el sistema de archivos
    - Crea el registro en la base de datos

    Args:
        file: Archivo del certificado (.crt, .cer, .pem)
        cuit: CUIT asociado al certificado
        nombre: Nombre descriptivo para el certificado
        ambiente: "homologacion" o "produccion"
        key_filename: Nombre del archivo de clave privada generado previamente
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Certificado creado con información completa

    Raises:
        HTTPException: Si el certificado es inválido o no coincide con la clave
    """
    try:
        logger.info(f"Subiendo certificado para CUIT: {cuit}")

        # Validar extensión del archivo
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nombre de archivo inválido",
            )

        extension = file.filename.split(".")[-1].lower()
        if extension not in ["crt", "cer", "pem"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de archivo inválido. Se acepta .crt, .cer o .pem",
            )

        # Validar ambiente
        if ambiente not in ["homologacion", "produccion"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ambiente debe ser 'homologacion' o 'produccion'",
            )

        # Leer contenido del archivo
        contenido = await file.read()

        # Guardar certificado temporalmente
        service = CertificadosService()
        cert_path = await service.guardar_certificado(contenido, cuit, ambiente)

        # Construir path de la clave privada
        key_path = service.certs_path / key_filename

        if not key_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clave privada no encontrada. Por favor generá el CSR nuevamente.",
            )

        # Validar certificado contra clave privada
        cert_info = await service.validar_certificado(
            str(cert_path), str(key_path), cuit
        )

        # Crear registro en BD
        certificado = Certificado(
            nombre=nombre,
            cuit=cuit,
            fecha_emision=cert_info.fecha_emision,
            fecha_vencimiento=cert_info.fecha_vencimiento,
            archivo_crt=cert_path,
            archivo_key=str(key_path),
            activo=True,
            ambiente=ambiente,
            empresa_id=current_user.empresa_id,
        )

        db.add(certificado)
        await db.commit()
        await db.refresh(certificado)

        logger.info(f"Certificado guardado exitosamente. ID: {certificado.id}")

        return certificado

    except ArcaCertificateError as e:
        logger.error(f"Error de validación de certificado: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado subiendo certificado: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar el certificado",
        )


@router.post(
    "/verificar-conexion/{certificado_id}", response_model=VerificacionResponse
)
async def verificar_conexion(
    certificado_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Prueba la conexión con ARCA usando el certificado.

    Este endpoint:
    - Intenta autenticarse con WSAA usando el certificado
    - Verifica el estado de los servidores de ARCA
    - Devuelve resultado de la verificación

    Args:
        certificado_id: ID del certificado a verificar
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Resultado de la verificación con detalles

    Raises:
        HTTPException: Si el certificado no existe o hay error de permisos
    """
    # Obtener certificado
    result = await db.execute(
        select(Certificado).where(Certificado.id == certificado_id)
    )
    certificado = result.scalar_one_or_none()

    if not certificado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificado no encontrado"
        )

    # Verificar permisos
    if not current_user.es_admin and certificado.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para verificar este certificado",
        )

    try:
        logger.info(f"Verificando conexión con certificado ID: {certificado_id}")

        # Determinar ambiente
        ambiente = (
            ArcaAmbiente.HOMOLOGACION
            if certificado.ambiente == "homologacion"
            else ArcaAmbiente.PRODUCCION
        )

        # Crear cliente WSAA
        wsaa_client = WSAAClient(ambiente=ambiente)

        # Intentar login
        ticket = await wsaa_client.login(
            cert_path=certificado.archivo_crt,
            key_path=certificado.archivo_key,
            cuit=certificado.cuit,
            servicio="wsfe",
        )

        # Si llegamos aquí, la conexión fue exitosa
        return VerificacionResponse(
            exito=True,
            mensaje="Conexión exitosa con ARCA",
            estado_servidores={
                "aplicacion": "OK",
                "base_datos": "OK",
                "autenticacion": "OK",
            },
        )

    except ArcaAuthError as e:
        logger.error(f"Error de autenticación ARCA: {str(e)}")
        return VerificacionResponse(
            exito=False, mensaje="Error de autenticación", error=str(e)
        )

    except ArcaConnectionError as e:
        logger.error(f"Error de conexión ARCA: {str(e)}")
        return VerificacionResponse(
            exito=False,
            mensaje="Error de conexión con ARCA",
            error="No se pudo conectar con los servidores de ARCA. Por favor, intentá más tarde.",
        )

    except Exception as e:
        logger.error(f"Error inesperado verificando conexión: {str(e)}")
        return VerificacionResponse(
            exito=False,
            mensaje="Error inesperado",
            error="Ocurrió un error al verificar la conexión. Por favor, intentá nuevamente.",
        )
