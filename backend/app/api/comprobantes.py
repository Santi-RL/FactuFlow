"""API de Comprobantes - Endpoints para emisión y gestión de facturas."""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_empresa_id, get_current_empresa_user, get_db
from app.core.database import DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS
from app.models.cliente import Cliente
from app.models.comprobante import Comprobante
from app.models.idempotencia_fiscal import OperacionIdempotente
from app.models.usuario import Usuario
from app.schemas.comprobante import (
    EmitirComprobanteRequest,
    EmitirComprobanteResponse,
    ComprobanteDetalleResponse,
    ComprobanteListResponse,
    PaginatedComprobantesResponse,
    ProximoNumeroResponse,
    ItemComprobanteResponse,
)
from app.services.facturacion_service import (
    FacturacionService,
    FaseSolicitudArca,
    ReconciliacionNumeracionError,
    ValidationError,
)
from app.services.idempotencia_fiscal_service import (
    CreacionOperacionAmbiguaError,
    IdempotenciaFiscalError,
    IdempotenciaFiscalService,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _error_db_post_arca(
    resultado: EmitirComprobanteResponse | None = None,
) -> HTTPException:
    """Devuelve un conflicto sanitizado cuando la DB cae después de FECAE."""
    detail = {
        "mensaje": (
            "La solicitud fiscal pudo haber sido procesada por ARCA, pero "
            "FactuFlow no pudo cerrar la persistencia local."
        ),
        "errores": [
            "No reintentes la emisión. Reconciliá el comprobante antes de continuar."
        ],
        "requiere_reconciliacion": True,
        "categoria_error": "post_arca_persistencia",
    }
    if resultado is not None:
        detail.update(
            {
                "tipo_comprobante": resultado.tipo_comprobante,
                "punto_venta": resultado.punto_venta,
                "numero": resultado.numero,
                "fecha": resultado.fecha.isoformat(),
                "total": str(resultado.total),
                "cae": resultado.cae,
                "cae_vencimiento": (
                    resultado.cae_vencimiento.isoformat()
                    if resultado.cae_vencimiento
                    else None
                ),
            }
        )
    return HTTPException(status_code=409, detail=detail)


def _respuesta_inesperada_post_arca(
    request: EmitirComprobanteRequest,
    resultado: EmitirComprobanteResponse | None,
) -> EmitirComprobanteResponse:
    """Construye un replay sanitizado si una excepción cruza la frontera ARCA."""
    return EmitirComprobanteResponse(
        exito=False,
        comprobante_id=resultado.comprobante_id if resultado else None,
        tipo_comprobante=(
            resultado.tipo_comprobante if resultado else request.tipo_comprobante
        ),
        punto_venta=resultado.punto_venta if resultado else 0,
        numero=resultado.numero if resultado else 0,
        fecha=resultado.fecha if resultado else request.fecha_emision,
        cae=resultado.cae if resultado else None,
        cae_vencimiento=resultado.cae_vencimiento if resultado else None,
        total=resultado.total if resultado else 0,
        mensaje=(
            "La solicitud fiscal pudo haber sido procesada por ARCA, pero "
            "FactuFlow no pudo confirmar su cierre local."
        ),
        errores=[
            "No reintentes con otra clave. Conservá esta operación y reconciliá el comprobante."
        ],
        requiere_reconciliacion=True,
        categoria_error=(
            "post_arca_persistencia" if resultado else "arca_respuesta_incierta"
        ),
    )


async def _guardar_respuesta_inesperada_post_arca(
    db: AsyncSession,
    idempotencia: IdempotenciaFiscalService,
    operacion: OperacionIdempotente,
    respuesta: EmitirComprobanteResponse,
) -> None:
    """Intenta persistir el replay incierto sin reemplazar la respuesta HTTP segura."""
    try:
        await db.rollback()
        await idempotencia.guardar_respuesta_operacion(
            operacion,
            response_json=respuesta,
            estado="requiere_reconciliacion",
        )
    except Exception as persistencia_exc:
        logger.error(
            "event=post_arca_response_persistence_failed tipo_error=%s",
            type(persistencia_exc).__name__,
        )
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "event=post_arca_response_rollback_failed tipo_error=%s",
                type(rollback_exc).__name__,
            )


def _error_db_pre_arca_bloqueado() -> HTTPException:
    """Devuelve un conflicto seguro si no pudo abrirse un replay pre-ARCA."""
    return HTTPException(
        status_code=409,
        detail={
            "mensaje": "No se pudo dejar la operación lista para reintento seguro.",
            "errores": [
                "Conservá la misma clave de idempotencia y revisá el estado antes de continuar."
            ],
            "categoria_error": "pre_arca_estado_bloqueado",
        },
    )


async def _reclamar_operacion_pre_arca_segura(
    db: AsyncSession,
    idempotencia: IdempotenciaFiscalService,
    operacion: OperacionIdempotente,
) -> tuple[OperacionIdempotente, bool]:
    """Ejecuta el CAS de replay sin abrir un estado optimista ambiguo."""
    try:
        return await idempotencia.reclamar_operacion_interrumpida_pre_arca(operacion)
    except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "event=pre_arca_replay_rollback_failed tipo_error=%s",
                type(rollback_exc).__name__,
            )
        raise _error_db_pre_arca_bloqueado()


async def _recuperar_operacion_pre_arca(
    db: AsyncSession,
    idempotencia: IdempotenciaFiscalService,
    operacion_id: int,
) -> bool:
    """Intenta abrir un replay durable sin reemplazar el error primario."""
    try:
        await db.rollback()
        return await idempotencia.marcar_operacion_interrumpida_pre_arca(operacion_id)
    except Exception as recovery_exc:
        logger.error(
            "event=pre_arca_operation_recovery_failed tipo_error=%s",
            type(recovery_exc).__name__,
        )
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "event=pre_arca_operation_recovery_rollback_failed tipo_error=%s",
                type(rollback_exc).__name__,
            )
        return False


def _estado_operacion_desde_resultado(resultado: EmitirComprobanteResponse) -> str:
    """Mapea una respuesta fiscal al estado de operación idempotente."""
    if resultado.exito:
        return "finalizado"
    if resultado.categoria_error == "duplicado_logico":
        return "requiere_confirmacion_duplicado"
    if resultado.requiere_reconciliacion:
        return "requiere_reconciliacion"
    return "fallido"


def _raise_resultado_no_exitoso(resultado: EmitirComprobanteResponse) -> None:
    """Convierte un resultado no exitoso en el HTTPException correspondiente."""
    if resultado.requiere_reconciliacion or resultado.categoria_error in {
        "duplicado_logico",
        "arca_respuesta_incierta",
        "idempotencia_en_proceso",
    }:
        raise HTTPException(status_code=409, detail=jsonable_encoder(resultado))
    raise HTTPException(
        status_code=400,
        detail={"mensaje": resultado.mensaje, "errores": resultado.errores},
    )


async def _resolver_operacion_emitir(
    *,
    db: AsyncSession,
    request: EmitirComprobanteRequest,
    empresa_id: int,
    usuario_id: int | None,
    idempotency_key: str | None,
) -> tuple[IdempotenciaFiscalService, OperacionIdempotente, bool]:
    """Obtiene o crea la operación idempotente para emisión individual."""
    idempotencia = IdempotenciaFiscalService(db)
    payload = request.model_dump(mode="json")
    payload_hash = idempotencia.calcular_payload_hash(
        idempotencia.payload_sin_confirmacion_duplicado(payload)
    )
    try:
        operacion, creada = await idempotencia.obtener_o_crear_operacion(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            idempotency_key=idempotency_key,
            tipo_operacion="emitir_comprobante",
            payload_hash=payload_hash,
        )
    except IdempotenciaFiscalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except CreacionOperacionAmbiguaError as exc:
        try:
            recuperada = await idempotencia.recuperar_creacion_ambigua_pre_arca(
                empresa_id=empresa_id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                tipo_operacion="emitir_comprobante",
                lote_id=None,
            )
        except Exception as recovery_exc:
            logger.error(
                "event=pre_arca_ambiguous_create_recovery_failed tipo_error=%s",
                type(recovery_exc).__name__,
            )
            recuperada = False
        if not recuperada:
            raise _error_db_pre_arca_bloqueado()
        raise exc.error_original
    return idempotencia, operacion, creada


@router.get("/", response_model=PaginatedComprobantesResponse)
async def listar_comprobantes(
    desde: Optional[date] = Query(None, description="Fecha desde (filtro)"),
    hasta: Optional[date] = Query(None, description="Fecha hasta (filtro)"),
    tipo: Optional[int] = Query(None, description="Tipo de comprobante (filtro)"),
    cliente_id: Optional[int] = Query(None, description="ID del cliente (filtro)"),
    buscar: Optional[str] = Query(None, description="Búsqueda por número o cliente"),
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(20, ge=1, le=100, description="Resultados por página"),
    db: AsyncSession = Depends(get_db),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """
    Lista comprobantes con filtros y paginación.

    Filtros disponibles:
    - desde/hasta: Rango de fechas
    - tipo: Tipo de comprobante
    - cliente_id: Cliente específico
    - buscar: Búsqueda por número o nombre de cliente
    """
    # Base query
    stmt = (
        select(Comprobante)
        .where(Comprobante.empresa_id == empresa_activa_id)
        .options(joinedload(Comprobante.cliente), joinedload(Comprobante.punto_venta))
    )

    # Aplicar filtros
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

    # Contar total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Aplicar paginación
    stmt = stmt.order_by(Comprobante.fecha_emision.desc(), Comprobante.numero.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    # Ejecutar query
    result = await db.execute(stmt)
    comprobantes = result.scalars().all()

    # Mapear a response
    items = [
        ComprobanteListResponse(
            id=c.id,
            tipo_comprobante=c.tipo_comprobante,
            numero=c.numero,
            fecha_emision=c.fecha_emision,
            total=c.total,
            estado=c.estado,
            origen_emision=c.origen_emision,
            cae=c.cae,
            cliente_nombre=(
                c.receptor_razon_social
                or (c.cliente.razon_social if c.cliente else "Desconocido")
            ),
            cliente_documento=(
                c.receptor_numero_documento
                or (c.cliente.numero_documento if c.cliente else "N/A")
            ),
            punto_venta_numero=c.punto_venta.numero if c.punto_venta else 0,
        )
        for c in comprobantes
    ]

    return PaginatedComprobantesResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.get("/{comprobante_id}", response_model=ComprobanteDetalleResponse)
async def obtener_comprobante(
    comprobante_id: int,
    db: AsyncSession = Depends(get_db),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """
    Obtiene detalle completo de un comprobante.

    Incluye todos los items, datos del cliente y punto de venta.
    """
    stmt = (
        select(Comprobante)
        .where(Comprobante.id == comprobante_id)
        .options(
            joinedload(Comprobante.items),
            joinedload(Comprobante.cliente),
            joinedload(Comprobante.punto_venta),
        )
    )

    result = await db.execute(stmt)
    comprobante = result.unique().scalar_one_or_none()

    if not comprobante:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    if comprobante.empresa_id != empresa_activa_id:
        raise HTTPException(
            status_code=403,
            detail="El comprobante no pertenece a la empresa activa seleccionada",
        )

    # Mapear items
    items = [
        ItemComprobanteResponse(
            id=item.id,
            codigo=item.codigo,
            descripcion=item.descripcion,
            cantidad=item.cantidad,
            unidad=item.unidad,
            precio_unitario=item.precio_unitario,
            descuento_porcentaje=item.descuento_porcentaje,
            iva_porcentaje=item.iva_porcentaje,
            subtotal=item.subtotal,
            orden=item.orden,
            comprobante_id=item.comprobante_id,
        )
        for item in sorted(comprobante.items, key=lambda x: x.orden)
    ]

    return ComprobanteDetalleResponse(
        id=comprobante.id,
        tipo_comprobante=comprobante.tipo_comprobante,
        concepto=comprobante.concepto,
        numero=comprobante.numero,
        fecha_emision=comprobante.fecha_emision,
        fecha_vencimiento=comprobante.fecha_vencimiento,
        subtotal=comprobante.subtotal,
        descuento=comprobante.descuento,
        iva_21=comprobante.iva_21,
        iva_10_5=comprobante.iva_10_5,
        iva_27=comprobante.iva_27,
        otros_impuestos=comprobante.otros_impuestos,
        total=comprobante.total,
        cae=comprobante.cae,
        cae_vencimiento=comprobante.cae_vencimiento,
        estado=comprobante.estado,
        origen_emision=comprobante.origen_emision,
        moneda=comprobante.moneda,
        cotizacion=comprobante.cotizacion,
        observaciones=comprobante.observaciones,
        empresa_id=comprobante.empresa_id,
        punto_venta_id=comprobante.punto_venta_id,
        cliente_id=comprobante.cliente_id,
        receptor_tipo_documento=comprobante.receptor_tipo_documento,
        receptor_numero_documento=comprobante.receptor_numero_documento,
        receptor_razon_social=comprobante.receptor_razon_social,
        receptor_condicion_iva=comprobante.receptor_condicion_iva,
        receptor_domicilio=comprobante.receptor_domicilio,
        items=items,
        cliente_nombre=(
            comprobante.receptor_razon_social
            or (comprobante.cliente.razon_social if comprobante.cliente else None)
        ),
        cliente_cuit=(
            comprobante.receptor_numero_documento
            or (comprobante.cliente.numero_documento if comprobante.cliente else None)
        ),
        punto_venta_numero=(
            comprobante.punto_venta.numero if comprobante.punto_venta else None
        ),
    )


@router.post("/emitir", response_model=EmitirComprobanteResponse)
async def emitir_comprobante(
    request: EmitirComprobanteRequest,
    x_idempotency_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """
    Emite un comprobante electrónico.

    Flujo:
    1. Valida datos según tipo de comprobante
    2. Obtiene próximo número
    3. Calcula totales e IVA
    4. Solicita CAE a ARCA
    5. Guarda en base de datos
    6. Retorna comprobante con CAE

    Tipos de comprobante soportados:
    - 1: Factura A
    - 2: Nota de Débito A
    - 3: Nota de Crédito A
    - 6: Factura B
    - 7: Nota de Débito B
    - 8: Nota de Crédito B
    - 11: Factura C
    - 12: Nota de Débito C
    - 13: Nota de Crédito C
    """
    if not request.confirmacion_fecha_fiscal:
        raise HTTPException(
            status_code=400,
            detail=(
                "Antes de emitir debes confirmar la fecha fiscal. "
                "Está seguro que quiere emitir comprobantes con fecha "
                "XX/XX/XX? Recuerde que luego no podrá emitir comprobantes "
                "con fecha anterior para ese mismo punto de venta."
            ),
        )

    service = FacturacionService(db)
    fase_solicitud_arca = FaseSolicitudArca()
    request = request.model_copy(update={"empresa_id": empresa_activa_id})
    idempotencia, operacion, creada = await _resolver_operacion_emitir(
        db=db,
        request=request,
        empresa_id=empresa_activa_id,
        usuario_id=current_user.id,
        idempotency_key=x_idempotency_key,
    )

    confirmacion_duplicado_autorizada = False
    continuar_operacion = creada
    if not creada and operacion.estado == "interrumpida_pre_arca":
        operacion, continuar_operacion = await _reclamar_operacion_pre_arca_segura(
            db,
            idempotencia,
            operacion,
        )
    if not continuar_operacion:
        if operacion.response_json is not None:
            if (
                IdempotenciaFiscalService.requiere_confirmacion_duplicado(
                    operacion.response_json
                )
                and request.confirmacion_duplicado_logico
            ):
                operacion, tomada = await idempotencia.marcar_operacion_en_proceso(
                    operacion
                )
                if tomada:
                    confirmacion_duplicado_autorizada = True
                elif operacion.response_json is not None:
                    resultado_guardado = EmitirComprobanteResponse.model_validate(
                        operacion.response_json
                    )
                    if not resultado_guardado.exito:
                        _raise_resultado_no_exitoso(resultado_guardado)
                    return resultado_guardado
                else:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "mensaje": "La operación fiscal ya está en proceso o requiere verificación.",
                            "errores": [
                                "No vuelvas a solicitar CAE con otra clave hasta revisar el estado de ARCA y de FactuFlow."
                            ],
                            "categoria_error": "idempotencia_en_proceso",
                        },
                    )
            else:
                resultado_guardado = EmitirComprobanteResponse.model_validate(
                    operacion.response_json
                )
                if not resultado_guardado.exito:
                    _raise_resultado_no_exitoso(resultado_guardado)
                return resultado_guardado
        else:
            resultado_actual = await service.resolver_operacion_idempotente_incompleta(
                operacion.id
            )
            if resultado_actual is not None:
                if resultado_actual.categoria_error != "idempotencia_en_proceso":
                    await idempotencia.guardar_respuesta_operacion(
                        operacion,
                        response_json=resultado_actual,
                        estado=_estado_operacion_desde_resultado(resultado_actual),
                    )
                if not resultado_actual.exito:
                    _raise_resultado_no_exitoso(resultado_actual)
                return resultado_actual
    if request.confirmacion_duplicado_logico != confirmacion_duplicado_autorizada:
        request = request.model_copy(
            update={
                "confirmacion_duplicado_logico": (confirmacion_duplicado_autorizada)
            }
        )

    resultado: EmitirComprobanteResponse | None = None
    try:
        resultado = await service.emitir_comprobante(
            request,
            operacion_id=operacion.id,
            usuario_id=current_user.id,
            fase_solicitud_arca=fase_solicitud_arca,
        )
        await idempotencia.guardar_respuesta_operacion(
            operacion,
            response_json=resultado,
            estado=_estado_operacion_desde_resultado(resultado),
        )

        if not resultado.exito:
            _raise_resultado_no_exitoso(resultado)

        return resultado
    except HTTPException:
        raise
    except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
        if not fase_solicitud_arca.iniciada:
            recuperada = await _recuperar_operacion_pre_arca(
                db,
                idempotencia,
                operacion.id,
            )
            fase_solicitud_arca.registrar_recuperacion_pre_arca(recuperada)
            if recuperada:
                raise
            raise _error_db_pre_arca_bloqueado()
        raise _error_db_post_arca(resultado)
    except Exception as exc:
        logger.exception("Error inesperado al emitir comprobante")
        if fase_solicitud_arca.iniciada:
            respuesta_incierta = _respuesta_inesperada_post_arca(request, resultado)
            await _guardar_respuesta_inesperada_post_arca(
                db,
                idempotencia,
                operacion,
                respuesta_incierta,
            )
            raise HTTPException(
                status_code=409,
                detail=jsonable_encoder(respuesta_incierta),
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={
                "mensaje": "Error interno al emitir comprobante",
                "errores": [
                    "No se pudo completar la operación. Revisa los logs antes de reintentar."
                ],
            },
        ) from exc


@router.get(
    "/proximo-numero/{punto_venta}/{tipo}", response_model=ProximoNumeroResponse
)
async def obtener_proximo_numero(
    punto_venta: int,
    tipo: int,
    db: AsyncSession = Depends(get_db),
    empresa_activa_id: int = Depends(get_current_empresa_id),
):
    """
    Obtiene el próximo número de comprobante disponible.

    Este endpoint es útil para mostrar al usuario qué número se
    asignará al comprobante antes de emitirlo.
    """
    # Buscar punto de venta
    from app.models.punto_venta import PuntoVenta

    stmt = select(PuntoVenta).where(
        and_(
            PuntoVenta.numero == punto_venta, PuntoVenta.empresa_id == empresa_activa_id
        )
    )
    result = await db.execute(stmt)
    pv = result.scalar_one_or_none()

    if not pv:
        raise HTTPException(status_code=404, detail="Punto de venta no encontrado")

    if not pv.usable_factuflow:
        raise HTTPException(
            status_code=400,
            detail=(
                "El punto de venta seleccionado no está habilitado para emitir "
                "por FactuFlow. Elegí un punto Web Services activo, no bloqueado "
                "y sin fecha de baja."
            ),
        )

    # Obtener próximo número
    service = FacturacionService(db)
    try:
        proximo = await service.obtener_proximo_numero(empresa_activa_id, pv.id, tipo)
    except ReconciliacionNumeracionError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "mensaje": "ARCA registra comprobantes que no están guardados en FactuFlow",
                "errores": [str(exc)],
                "requiere_reconciliacion": True,
                "categoria_error": "numeracion_arca_adelantada",
            },
        ) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ProximoNumeroResponse(
        punto_venta=punto_venta, tipo_comprobante=tipo, proximo_numero=proximo
    )
