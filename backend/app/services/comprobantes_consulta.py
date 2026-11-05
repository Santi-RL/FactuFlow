"""Predicados compartidos del listado y la selección de documentos, sin escrituras."""

from sqlalchemy import String, cast, or_

from app.models.cliente import Cliente
from app.models.comprobante import Comprobante


def filtrar_comprobantes(
    stmt, empresa_id, *, desde=None, hasta=None, tipo=None, cliente_id=None, buscar=None
):
    stmt = stmt.where(Comprobante.empresa_id == empresa_id)
    if desde:
        stmt = stmt.where(Comprobante.fecha_emision >= desde)
    if hasta:
        stmt = stmt.where(Comprobante.fecha_emision <= hasta)
    if tipo:
        stmt = stmt.where(Comprobante.tipo_comprobante == tipo)
    if cliente_id:
        stmt = stmt.where(Comprobante.cliente_id == cliente_id)
    if buscar:
        stmt = stmt.where(
            or_(
                cast(Comprobante.numero, String).like(f"%{buscar}%"),
                Comprobante.receptor_razon_social.like(f"%{buscar}%"),
                Comprobante.receptor_numero_documento.like(f"%{buscar}%"),
                Comprobante.cliente.has(
                    or_(
                        Cliente.razon_social.like(f"%{buscar}%"),
                        Cliente.numero_documento.like(f"%{buscar}%"),
                    )
                ),
            )
        )
    return stmt
