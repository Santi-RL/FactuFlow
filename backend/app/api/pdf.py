"""API endpoints para generación de PDFs."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_empresa_id
from app.api.deps import get_current_empresa_user
from app.core.database import get_db
from app.models.comprobante import Comprobante
from app.models.usuario import Usuario
from app.services.pdf_service import pdf_service

router = APIRouter()


@router.get("/comprobante/{comprobante_id}")
async def descargar_pdf_comprobante(
    comprobante_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """
    Genera y descarga el PDF de un comprobante.

    Args:
        comprobante_id: ID del comprobante
        db: Sesión de base de datos

    Returns:
        PDF del comprobante
    """
    # Obtener comprobante con todas sus relaciones
    query = (
        select(Comprobante)
        .options(
            selectinload(Comprobante.empresa),
            selectinload(Comprobante.cliente),
            selectinload(Comprobante.punto_venta),
            selectinload(Comprobante.items),
        )
        .where(Comprobante.id == comprobante_id)
    )

    result = await db.execute(query)
    comprobante = result.scalar_one_or_none()

    if not comprobante:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    if not current_user.es_admin and comprobante.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=403, detail="No tienes acceso a este comprobante"
        )
    if current_user.es_admin and comprobante.empresa_id != empresa_activa_id:
        raise HTTPException(
            status_code=403,
            detail="El comprobante no pertenece a la empresa activa seleccionada",
        )

    # Generar PDF
    try:
        pdf_bytes = await pdf_service.generar_pdf_comprobante(
            comprobante, comprobante.empresa
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")

    # Nombre del archivo
    letra = pdf_service._get_letra_comprobante(comprobante.tipo_comprobante)
    tipo_nombre = pdf_service._get_nombre_comprobante(comprobante.tipo_comprobante)
    filename = (
        f"{tipo_nombre}_{letra}_{comprobante.punto_venta.numero:04d}-"
        f"{comprobante.numero:08d}.pdf"
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/comprobante/{comprobante_id}/preview")
async def preview_pdf_comprobante(
    comprobante_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """
    Muestra el PDF en el navegador (sin descargar).

    Args:
        comprobante_id: ID del comprobante
        db: Sesión de base de datos

    Returns:
        PDF del comprobante para preview
    """
    # Obtener comprobante con todas sus relaciones
    query = (
        select(Comprobante)
        .options(
            selectinload(Comprobante.empresa),
            selectinload(Comprobante.cliente),
            selectinload(Comprobante.punto_venta),
            selectinload(Comprobante.items),
        )
        .where(Comprobante.id == comprobante_id)
    )

    result = await db.execute(query)
    comprobante = result.scalar_one_or_none()

    if not comprobante:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    if not current_user.es_admin and comprobante.empresa_id != current_user.empresa_id:
        raise HTTPException(
            status_code=403, detail="No tienes acceso a este comprobante"
        )
    if current_user.es_admin and comprobante.empresa_id != empresa_activa_id:
        raise HTTPException(
            status_code=403,
            detail="El comprobante no pertenece a la empresa activa seleccionada",
        )

    # Generar PDF
    try:
        pdf_bytes = await pdf_service.generar_pdf_comprobante(
            comprobante, comprobante.empresa
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )
