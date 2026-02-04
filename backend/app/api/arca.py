"""Endpoints de API para integración con ARCA."""

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_empresa_user
from app.models.usuario import Usuario
from app.models.certificado import Certificado
from app.arca.config import ArcaAmbiente
from app.arca.wsaa import WSAAClient
from app.arca.wsfev1 import WSFEv1Client
from app.arca.models import (
    ComprobanteRequest,
    CAEResponse,
    ComprobanteResponse,
    TipoComprobante,
    TipoDocumento,
    TipoIva,
    TipoConcepto,
    TipoMoneda,
    Cotizacion,
    PuntoVenta,
)
from app.arca.exceptions import (
    ArcaError,
    ArcaAuthError,
    ArcaConnectionError,
    ArcaValidationError,
    ArcaServiceError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_ambiente() -> ArcaAmbiente:
    """
    Obtiene el ambiente de ARCA desde la configuración.

    Returns:
        ArcaAmbiente (homologacion o produccion)
    """
    ambiente_str = settings.afip_env.lower()

    if ambiente_str == "produccion":
        return ArcaAmbiente.PRODUCCION
    return ArcaAmbiente.HOMOLOGACION


async def get_certificado_activo(
    db: AsyncSession, current_user: Usuario
) -> Certificado:
    """
    Obtiene el certificado activo para la empresa del usuario.

    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Certificado activo

    Raises:
        HTTPException: Si no hay certificado activo
    """
    ambiente = get_ambiente()

    result = await db.execute(
        select(Certificado).where(
            Certificado.empresa_id == current_user.empresa_id,
            Certificado.activo == True,
            Certificado.ambiente == ambiente.value,
        )
    )

    certificado = result.scalar_one_or_none()

    if not certificado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró un certificado activo para el ambiente {ambiente.value}",
        )

    return certificado


async def get_wsfe_client(db: AsyncSession, current_user: Usuario) -> WSFEv1Client:
    """
    Crea un cliente WSFEv1 autenticado.

    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Cliente WSFEv1 autenticado

    Raises:
        HTTPException: Si hay error en la autenticación
    """
    try:
        # Obtener certificado activo
        certificado = await get_certificado_activo(db, current_user)

        # Construir paths de certificado
        certs_path = Path(settings.afip_certs_path)
        cert_path = certs_path / certificado.archivo_crt
        key_path = certs_path / certificado.archivo_key

        # Validar que existan los archivos
        if not cert_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Archivo de certificado no encontrado: {cert_path}",
            )

        if not key_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Archivo de clave privada no encontrado: {key_path}",
            )

        # Obtener ambiente
        ambiente = get_ambiente()

        # Autenticar con WSAA
        wsaa_client = WSAAClient(ambiente=ambiente)
        ticket = await wsaa_client.login(
            cert_path=str(cert_path),
            key_path=str(key_path),
            cuit=certificado.cuit,
            servicio="wsfe",
        )

        # Crear cliente WSFEv1
        wsfe_client = WSFEv1Client(
            ambiente=ambiente, ticket=ticket, cuit=certificado.cuit
        )

        return wsfe_client

    except ArcaAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error de autenticación con ARCA: {e.mensaje}",
        )
    except ArcaConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error de conexión con ARCA: {e.mensaje}",
        )
    except ArcaError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error de ARCA: {e.mensaje}",
        )


# ==================== Endpoints ====================


@router.get("/test-conexion")
async def test_conexion_arca(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Prueba la conexión con los webservices de ARCA usando FEDummy.

    Este endpoint verifica que:
    - Los certificados sean válidos
    - La autenticación con WSAA funcione
    - El servicio WSFEv1 esté disponible

    Returns:
        Información del servidor de ARCA
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        result = await wsfe_client.fe_dummy()

        return {
            "status": "ok",
            "message": "Conexión exitosa con ARCA",
            "ambiente": get_ambiente().value,
            "servidor": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en test de conexión: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al probar conexión: {str(e)}",
        )


@router.get("/tipos-comprobante", response_model=List[TipoComprobante])
async def get_tipos_comprobante(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene los tipos de comprobante disponibles en ARCA.

    Returns:
        Lista de tipos de comprobante
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        tipos = await wsfe_client.fe_param_get_tipos_cbte()
        return tipos

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tipos de comprobante: {e.mensaje}",
        )


@router.get("/tipos-documento", response_model=List[TipoDocumento])
async def get_tipos_documento(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene los tipos de documento disponibles en ARCA.

    Returns:
        Lista de tipos de documento
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        tipos = await wsfe_client.fe_param_get_tipos_doc()
        return tipos

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tipos de documento: {e.mensaje}",
        )


@router.get("/tipos-iva", response_model=List[TipoIva])
async def get_tipos_iva(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene las alícuotas de IVA disponibles en ARCA.

    Returns:
        Lista de tipos de IVA
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        tipos = await wsfe_client.fe_param_get_tipos_iva()
        return tipos

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tipos de IVA: {e.mensaje}",
        )


@router.get("/tipos-concepto", response_model=List[TipoConcepto])
async def get_tipos_concepto(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene los tipos de concepto disponibles en ARCA.

    Returns:
        Lista de tipos de concepto
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        tipos = await wsfe_client.fe_param_get_tipos_concepto()
        return tipos

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tipos de concepto: {e.mensaje}",
        )


@router.get("/tipos-monedas", response_model=List[TipoMoneda])
async def get_tipos_monedas(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene los tipos de moneda disponibles en ARCA.

    Returns:
        Lista de tipos de moneda
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        tipos = await wsfe_client.fe_param_get_tipos_monedas()
        return tipos

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tipos de moneda: {e.mensaje}",
        )


@router.get("/cotizacion/{moneda_id}", response_model=Cotizacion)
async def get_cotizacion(
    moneda_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene la cotización de una moneda.

    Args:
        moneda_id: ID de la moneda (ej: "DOL" para dólares)

    Returns:
        Cotización actual de la moneda
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        cotizacion = await wsfe_client.fe_param_get_cotizacion(moneda_id)
        return cotizacion

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener cotización: {e.mensaje}",
        )


@router.get("/puntos-venta", response_model=List[PuntoVenta])
async def get_puntos_venta(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene los puntos de venta habilitados para la empresa.

    Returns:
        Lista de puntos de venta
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        puntos = await wsfe_client.fe_param_get_ptos_venta()
        return puntos

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener puntos de venta: {e.mensaje}",
        )


@router.get("/ultimo-comprobante/{punto_venta}/{tipo_cbte}")
async def get_ultimo_comprobante(
    punto_venta: int,
    tipo_cbte: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Obtiene el último número de comprobante autorizado.

    Args:
        punto_venta: Punto de venta
        tipo_cbte: Tipo de comprobante

    Returns:
        Último número de comprobante
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        ultimo = await wsfe_client.fe_comp_ultimo_autorizado(punto_venta, tipo_cbte)

        return {
            "punto_venta": punto_venta,
            "tipo_cbte": tipo_cbte,
            "ultimo_comprobante": ultimo,
            "proximo_comprobante": ultimo + 1,
        }

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener último comprobante: {e.mensaje}",
        )


@router.post("/solicitar-cae", response_model=CAEResponse)
async def solicitar_cae(
    comprobante: ComprobanteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Solicita CAE (Código de Autorización Electrónica) para un comprobante.

    Args:
        comprobante: Datos del comprobante

    Returns:
        CAE y datos del comprobante autorizado
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        cae_response = await wsfe_client.fe_cae_solicitar(comprobante)

        return cae_response

    except HTTPException:
        raise
    except ArcaValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error de validación: {e.mensaje}",
        )
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al solicitar CAE: {e.mensaje}",
        )


@router.get(
    "/consultar-comprobante/{punto_venta}/{tipo_cbte}/{numero}",
    response_model=ComprobanteResponse,
)
async def consultar_comprobante(
    punto_venta: int,
    tipo_cbte: int,
    numero: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
):
    """
    Consulta un comprobante emitido previamente.

    Args:
        punto_venta: Punto de venta
        tipo_cbte: Tipo de comprobante
        numero: Número de comprobante

    Returns:
        Datos del comprobante consultado
    """
    try:
        wsfe_client = await get_wsfe_client(db, current_user)
        comprobante = await wsfe_client.fe_comp_consultar(
            punto_venta=punto_venta, tipo_cbte=tipo_cbte, numero=numero
        )

        return comprobante

    except HTTPException:
        raise
    except ArcaServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar comprobante: {e.mensaje}",
        )
