"""Lecturas PDF/ZIP con las mismas guardas, sin escrituras ni llamadas ARCA."""

import asyncio
from datetime import date
import json
import logging
import tempfile
from zipfile import ZIP_STORED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import StreamingResponse

from app.api.deps import get_current_empresa_id
from app.core.database import get_db
from app.core.security import get_current_user, security
from app.models.comprobante import Comprobante
from app.schemas.descargas_pdf import SeleccionPDF
from app.services.comprobantes_consulta import filtrar_comprobantes
from app.services.pdf_service import pdf_service
from app.services.lecturas_historicas_service import (
    ERROR_HISTORIA_PDF,
    cargar_lecturas_historicas,
)

router = APIRouter()
logger = logging.getLogger(__name__)
ERROR_GENERACION_PDF_PUBLICO = (
    "No se pudo generar el PDF. Intentá nuevamente y, si el problema continúa, "
    "contactá al administrador."
)
_zip_lock = asyncio.Lock()
_PRIVADO = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Access-Control-Expose-Headers": "Content-Disposition",
}


def _validar_comprobante_autorizado_para_pdf(comprobante: Comprobante) -> None:
    if (
        comprobante.estado != "autorizado"
        or not comprobante.cae
        or comprobante.cae_vencimiento is None
    ):
        raise HTTPException(
            409,
            (
                "Solo se puede generar PDF fiscal de comprobantes autorizados "
                "con CAE y vencimiento de CAE persistidos."
            ),
        )


def _nombre_pdf(comprobante, lectura):
    letra = pdf_service._get_letra_comprobante(comprobante.tipo_comprobante)
    tipo = pdf_service._get_nombre_comprobante(comprobante.tipo_comprobante)
    return (
        f"{tipo}_{letra}_{lectura.punto_venta_numero:04d}-{comprobante.numero:08d}.pdf"
    )


async def _cargar_documento(db, comprobante_id, empresa_id, *, ocultar_ajenos=False):
    query = select(Comprobante).where(Comprobante.id == comprobante_id)
    if ocultar_ajenos:
        query = query.where(Comprobante.empresa_id == empresa_id)
    query = query.options(
        selectinload(Comprobante.empresa),
        selectinload(Comprobante.cliente),
        selectinload(Comprobante.punto_venta),
        selectinload(Comprobante.items),
    )
    comprobante = (await db.execute(query)).scalar_one_or_none()
    if comprobante is None:
        raise HTTPException(404, "Comprobante no encontrado")
    if comprobante.empresa_id != empresa_id:
        raise HTTPException(
            403, "El comprobante no pertenece a la empresa activa seleccionada"
        )
    lectura = (await cargar_lecturas_historicas(db, [comprobante]))[comprobante.id]
    # Rendering may not lazy-load; release the connection before native work.
    db.expunge_all()
    await db.rollback()
    return comprobante, lectura


async def _render_documento(comprobante, lectura):
    _validar_comprobante_autorizado_para_pdf(comprobante)
    if lectura.cobertura == "no_verificable":
        raise HTTPException(409, ERROR_HISTORIA_PDF)
    try:
        return await pdf_service.generar_pdf_comprobante(
            comprobante, comprobante.empresa, lectura
        )
    except OSError:
        logger.exception("Recursos no disponibles al generar PDF")
        raise HTTPException(503, ERROR_GENERACION_PDF_PUBLICO) from None
    except Exception:
        logger.exception("Error al generar PDF comprobante_id=%s", comprobante.id)
        raise HTTPException(500, ERROR_GENERACION_PDF_PUBLICO) from None


@router.get("/comprobante/{comprobante_id}")
async def descargar_pdf_comprobante(
    comprobante_id: int,
    db: AsyncSession = Depends(get_db),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    comprobante, lectura = await _cargar_documento(
        db, comprobante_id, empresa_activa_id
    )
    contenido = await _render_documento(comprobante, lectura)
    return Response(
        contenido,
        media_type="application/pdf",
        headers={
            **_PRIVADO,
            "Content-Disposition": f'attachment; filename="{_nombre_pdf(comprobante, lectura)}"',
        },
    )


@router.get("/comprobante/{comprobante_id}/preview")
async def preview_pdf_comprobante(
    comprobante_id: int,
    db: AsyncSession = Depends(get_db),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    comprobante, lectura = await _cargar_documento(
        db, comprobante_id, empresa_activa_id
    )
    contenido = await _render_documento(comprobante, lectura)
    return Response(
        contenido,
        media_type="application/pdf",
        headers={
            **_PRIVADO,
            "Content-Disposition": "inline",
        },
    )


@router.get("/seleccion")
async def seleccionar_resultados_pdf(
    desde: date | None = None,
    hasta: date | None = None,
    tipo: int | None = None,
    cliente_id: int | None = None,
    buscar: str | None = None,
    db: AsyncSession = Depends(get_db),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    stmt = filtrar_comprobantes(
        select(Comprobante.id),
        empresa_activa_id,
        desde=desde,
        hasta=hasta,
        tipo=tipo,
        cliente_id=cliente_id,
        buscar=buscar,
    ).order_by(Comprobante.id)
    ids = list((await db.scalars(stmt)).all())
    return Response(
        json.dumps({"ids": ids, "total": len(ids)}),
        media_type="application/json",
        headers=_PRIVADO,
    )


class _ZIPTemporal(StreamingResponse):
    """Own the unnamed temporary even if ASGI disconnects before iteration."""

    def __init__(self, archivo, cantidad):
        self.archivo = archivo
        size = archivo.tell()
        archivo.seek(0)

        def chunks():
            while data := archivo.read(64 * 1024):
                yield data

        super().__init__(
            chunks(),
            media_type="application/zip",
            headers={
                **_PRIVADO,
                "Content-Length": str(size),
                "Content-Disposition": f'attachment; filename="Comprobantes_{cantidad}.zip"',
            },
        )

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.archivo.close()


@router.post("/zip")
async def descargar_zip(
    seleccion: SeleccionPDF,
    request: Request,
    db: AsyncSession = Depends(get_db),
    empresa_activa_id: int = Depends(get_current_empresa_id),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    db.expunge_all()
    await db.rollback()

    async def revalidar_acceso():
        usuario = await get_current_user(credentials, db)
        empresa = await get_current_empresa_id(request, db, usuario)
        if empresa != empresa_activa_id:
            raise HTTPException(403, "El emisor seleccionado cambió")
        db.expunge_all()
        await db.rollback()

    async with _zip_lock:
        await revalidar_acceso()
        # Validate all membership before rendering or revealing document errors.
        for offset in range(0, len(seleccion.ids), 500):
            ids = seleccion.ids[offset : offset + 500]
            encontrados = set(
                (
                    await db.scalars(
                        select(Comprobante.id).where(
                            Comprobante.empresa_id == empresa_activa_id,
                            Comprobante.id.in_(ids),
                        )
                    )
                ).all()
            )
            if encontrados != set(ids):
                raise HTTPException(
                    404, "La selección contiene comprobantes no disponibles"
                )
        db.expunge_all()
        await db.rollback()
        archivo = tempfile.TemporaryFile(mode="w+b", prefix="factuflow-pdf-")
        try:
            fallidos = []
            nombres = set()
            with ZipFile(
                archivo, "w", compression=ZIP_STORED, allowZip64=True
            ) as paquete:
                for comprobante_id in seleccion.ids:
                    if await request.is_disconnected():
                        raise HTTPException(499, "Descarga cancelada")
                    comprobante, lectura = await _cargar_documento(
                        db,
                        comprobante_id,
                        empresa_activa_id,
                        ocultar_ajenos=True,
                    )
                    try:
                        pdf = await _render_documento(comprobante, lectura)
                    except HTTPException as exc:
                        if exc.status_code not in {409, 500}:
                            raise
                        fallidos.append(
                            {
                                "comprobante_id": comprobante.id,
                                "comprobante": _nombre_pdf(comprobante, lectura),
                                "mensaje": (
                                    "El PDF no está disponible; consultá al responsable de la instalación."
                                    if exc.status_code == 409
                                    else ERROR_GENERACION_PDF_PUBLICO
                                ),
                            }
                        )
                        continue
                    nombre = _nombre_pdf(comprobante, lectura)
                    if nombre in nombres:
                        nombre = f"{nombre[:-4]}_{comprobante.id}.pdf"
                    nombres.add(nombre)
                    paquete.writestr(nombre, pdf)
                    del pdf
            await revalidar_acceso()
            if fallidos:
                raise HTTPException(
                    409,
                    {
                        "mensaje": "No se descargó el ZIP porque faltan PDF de la selección.",
                        "fallidos": fallidos,
                    },
                )
            return _ZIPTemporal(archivo, len(seleccion.ids))
        except HTTPException:
            archivo.close()
            raise
        except Exception:
            archivo.close()
            logger.exception("No se pudo preparar el ZIP de comprobantes")
            raise HTTPException(
                500, "No se pudo preparar el ZIP. Intentá nuevamente."
            ) from None
        except BaseException:
            archivo.close()
            raise
