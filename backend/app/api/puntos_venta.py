"""Endpoints de Puntos de Venta."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.arca import get_wsfe_client
from app.api.deps import get_current_empresa_id, get_current_empresa_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.empresa import Empresa
from app.models.usuario import Usuario
from app.models.punto_venta import PuntoVenta
from app.schemas.punto_venta import (
    ElegibilidadReceResponse,
    ImportarPuntosVentaResponse,
    PuntoVentaCreate,
    PuntoVentaUpdate,
    PuntoVentaResponse,
    SincronizarPuntosVentaResponse,
)
from app.services.constancia_puntos_venta_service import (
    ConstanciaPuntosVentaError,
    extraer_texto_constancia_puntos_pdf,
    parsear_constancia_puntos_venta,
)
from app.services.elegibilidad_rece_service import (
    ElegibilidadReceError,
    ElegibilidadReceService,
)
from app.services.puntos_venta_arca_service import PuntosVentaArcaService

router = APIRouter()


async def _serializar_punto_venta(
    db: AsyncSession,
    punto_venta: PuntoVenta,
) -> PuntoVentaResponse:
    """Construye el DTO técnico y RECE para el ambiente configurado."""
    visible = await ElegibilidadReceService(db).obtener_estado_visible(
        punto_venta,
        ambiente=settings.arca_env,
    )
    acreditado = visible.estado_efectivo == "verificado_rece"
    usable = bool(punto_venta.usable_factuflow and acreditado)
    comprobacion_desactualizada = ElegibilidadReceService(
        db
    ).comprobacion_arca_desactualizada(punto_venta)
    return PuntoVentaResponse(
        id=int(punto_venta.id),
        numero=int(punto_venta.numero),
        nombre=punto_venta.nombre,
        sistema=punto_venta.sistema,
        domicilio=punto_venta.domicilio,
        domicilio_fuente=punto_venta.domicilio_fuente,
        nombre_fantasia=punto_venta.nombre_fantasia,
        nombre_fantasia_fuente=punto_venta.nombre_fantasia_fuente,
        es_webservice=bool(punto_venta.es_webservice),
        bloqueado=bool(punto_venta.bloqueado),
        fecha_baja=punto_venta.fecha_baja,
        fuente=punto_venta.fuente,
        empresa_id=int(punto_venta.empresa_id),
        activo=bool(punto_venta.activo),
        usar_en_factuflow=bool(punto_venta.usar_en_factuflow),
        usable_factuflow=usable,
        puede_intentar_emision=bool(acreditado and punto_venta.usable_factuflow),
        seleccionable_para_emision=bool(usable and not comprobacion_desactualizada),
        ultima_comprobacion_arca_en=punto_venta.ultima_comprobacion_arca_en,
        comprobacion_arca_desactualizada=comprobacion_desactualizada,
        revision_fiscal=int(punto_venta.revision_fiscal),
        elegibilidad_rece=ElegibilidadReceResponse(
            ambiente=visible.ambiente,
            estado=visible.estado,
            estado_efectivo=visible.estado_efectivo,
            fuente=visible.fuente,
            revision_id=visible.revision_id,
            revision=visible.revision,
            punto_revision_fiscal=visible.punto_revision_fiscal,
            verificado_en=visible.verificado_en,
            vigente_hasta=visible.vigente_hasta,
            motivo=visible.motivo,
        ),
        created_at=punto_venta.created_at,
    )


@router.get("", response_model=list[PuntoVentaResponse])
async def list_puntos_venta(
    db: AsyncSession = Depends(get_db),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """
    Listar puntos de venta.

    Args:
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Lista de puntos de venta
    """
    query = select(PuntoVenta).where(PuntoVenta.empresa_id == empresa_id)

    result = await db.execute(query)
    puntos_venta = result.scalars().all()

    return [await _serializar_punto_venta(db, punto) for punto in puntos_venta]


@router.post("", response_model=PuntoVentaResponse, status_code=status.HTTP_201_CREATED)
async def create_punto_venta(
    punto_venta_data: PuntoVentaCreate,
    db: AsyncSession = Depends(get_db),
    admin: Usuario = Depends(get_current_admin_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """
    Crear un nuevo punto de venta.

    Args:
        punto_venta_data: Datos del punto de venta
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Punto de venta creado

    Raises:
        HTTPException: Si ya existe un punto de venta con ese número
    """
    del punto_venta_data, db, admin, empresa_id
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Los puntos de venta técnicos se incorporan con Comprobar con ARCA. "
            "No se pueden crear manualmente."
        ),
    )


@router.post("/importar-constancia", response_model=ImportarPuntosVentaResponse)
async def importar_constancia_puntos_venta(
    file: UploadFile = File(...),
    confirmar_procedencia_produccion: bool = Form(
        False,
        deprecated=True,
        description="Parámetro de compatibilidad sin efecto desde PF-19D.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Importa únicamente datos descriptivos desde una constancia opcional."""
    del confirmar_procedencia_produccion
    if file.content_type not in {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subí una constancia en formato PDF.",
        )

    contenido = await file.read()
    if len(contenido) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El PDF supera el límite de 5 MB.",
        )

    empresa = await db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emisor no encontrado",
        )
    try:
        datos = parsear_constancia_puntos_venta(
            extraer_texto_constancia_puntos_pdf(contenido)
        )
    except ConstanciaPuntosVentaError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    numeros = [punto.numero for punto in datos.puntos_venta]
    if any(numero < 1 or numero > 99999 for numero in numeros):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La constancia contiene un número de punto de venta inválido.",
        )
    if len(set(numeros)) != len(numeros):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La constancia contiene puntos de venta duplicados.",
        )
    if datos.cuit and datos.cuit != empresa.cuit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La constancia no corresponde al CUIT del emisor activo.",
        )

    existentes = {
        int(punto.numero): punto
        for punto in (
            await db.execute(
                select(PuntoVenta).where(PuntoVenta.empresa_id == empresa_id)
            )
        )
        .scalars()
        .all()
    }
    elegibilidad = ElegibilidadReceService(db)
    cambios: list[tuple[PuntoVenta, dict[str, object]]] = []
    importados: list[PuntoVenta] = []
    creados = 0
    actualizados = 0

    try:
        for detalle in datos.puntos_venta:
            punto = existentes.get(detalle.numero)
            descriptivos: dict[str, object] = {}
            if detalle.domicilio:
                descriptivos.update(
                    domicilio=detalle.domicilio,
                    domicilio_fuente="constancia_arca",
                )
            if detalle.nombre_fantasia:
                descriptivos.update(
                    nombre_fantasia=detalle.nombre_fantasia,
                    nombre_fantasia_fuente="constancia_arca",
                )
            if punto is None:
                punto = PuntoVenta(
                    numero=detalle.numero,
                    sistema=detalle.sistema,
                    fuente="constancia_arca",
                    es_webservice=False,
                    activo=False,
                    usar_en_factuflow=False,
                    empresa_id=empresa_id,
                    **descriptivos,
                )
                db.add(punto)
                await elegibilidad.crear_contextos_iniciales_no_verificados(
                    punto,
                    creado_por_usuario_id=int(current_user.id),
                )
                creados += 1
            else:
                cambios_reales = {
                    campo: valor
                    for campo, valor in descriptivos.items()
                    if getattr(punto, campo) != valor
                }
                if cambios_reales:
                    cambios.append((punto, cambios_reales))
                    actualizados += 1
            importados.append(punto)

        if cambios:
            await elegibilidad.aplicar_cambios_puntos_atomicos(
                cambios,
                fuente="edicion",
                actor_usuario_id=int(current_user.id),
            )
        else:
            await db.commit()
        for punto in importados:
            await db.refresh(punto)
    except ElegibilidadReceError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Los puntos de venta cambiaron mientras se procesaba la constancia. "
                "Recargá y volvé a intentarlo."
            ),
        ) from exc

    respuestas = [await _serializar_punto_venta(db, punto) for punto in importados]
    verificados = sum(
        punto.elegibilidad_rece.estado_efectivo == "verificado_rece"
        for punto in respuestas
    )
    listos = sum(punto.seleccionable_para_emision for punto in respuestas)
    no_disponibles = sum(
        not punto.es_webservice or not punto.usar_en_factuflow for punto in respuestas
    )
    requieren_revision = max(0, len(respuestas) - listos - no_disponibles)
    warnings = list(datos.warnings)
    if creados:
        warnings.append(
            f"{creados} punto(s) de otros sistemas quedaron sólo como información."
        )

    return ImportarPuntosVentaResponse(
        total_constancia=len(datos.puntos_venta),
        creados=creados,
        actualizados=actualizados,
        omitidos=len(datos.warnings),
        desactivados_ausentes=0,
        verificados_rece=verificados,
        pendientes_comprobacion=0,
        no_verificados_rece=len(respuestas) - verificados,
        listos_para_emitir=listos,
        no_disponibles_factuflow=no_disponibles,
        requieren_revision=requieren_revision,
        documento_emitido_en=datos.documento_emitido_en,
        vigente_hasta=None,
        warnings=warnings,
    )


@router.post("/sincronizar-arca", response_model=SincronizarPuntosVentaResponse)
async def sincronizar_puntos_venta_arca(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
) -> SincronizarPuntosVentaResponse:
    """Comprueba y acredita la autoridad técnica autenticada de WSFE."""
    try:
        wsfe_client = await get_wsfe_client(db, current_user, empresa_id)
        resultado = await PuntosVentaArcaService(db).sincronizar(
            empresa_id=empresa_id,
            actor_usuario_id=current_user.id,
            wsfe_client=wsfe_client,
        )
    except HTTPException:
        raise
    except ElegibilidadReceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.mensaje,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo comprobar el estado técnico de puntos de venta.",
        ) from exc

    return SincronizarPuntosVentaResponse(
        **resultado,
    )


@router.put("/{punto_venta_id}", response_model=PuntoVentaResponse)
async def update_punto_venta(
    punto_venta_id: int,
    punto_venta_data: PuntoVentaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_empresa_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """
    Actualizar un punto de venta.

    Args:
        punto_venta_id: ID del punto de venta
        punto_venta_data: Datos a actualizar
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Returns:
        Punto de venta actualizado

    Raises:
        HTTPException: Si el punto de venta no existe o no pertenece a la empresa
    """
    result = await db.execute(select(PuntoVenta).where(PuntoVenta.id == punto_venta_id))
    punto_venta = result.scalar_one_or_none()

    if not punto_venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Punto de venta no encontrado"
        )

    # Verificar permisos
    if punto_venta.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar este punto de venta",
        )

    update_data = punto_venta_data.model_dump(exclude_unset=True)
    campos_tecnicos = {
        "numero",
        "sistema",
        "es_webservice",
        "bloqueado",
        "fecha_baja",
        "fuente",
        "activo",
    }
    if set(update_data).intersection(campos_tecnicos):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Los datos técnicos del punto los informa ARCA y no se pueden "
                "editar manualmente. Seleccioná Comprobar con ARCA para actualizarlos."
            ),
        )
    if update_data.get("usar_en_factuflow") is True and not punto_venta.es_webservice:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "ARCA no informa este punto como compatible con CAE. "
                "No se puede habilitar para usar en FactuFlow."
            ),
        )
    if "domicilio" in update_data:
        update_data["domicilio_fuente"] = "manual" if update_data["domicilio"] else None
    if "nombre_fantasia" in update_data:
        update_data["nombre_fantasia_fuente"] = (
            "manual" if update_data["nombre_fantasia"] else None
        )

    try:
        await ElegibilidadReceService(db).aplicar_cambios_punto(
            punto_venta,
            update_data,
            fuente="edicion",
            actor_usuario_id=current_user.id,
        )
    except ElegibilidadReceError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El punto de venta cambió de forma concurrente. "
                "Recargá y volvé a intentarlo."
            ),
        ) from exc

    return await _serializar_punto_venta(db, punto_venta)


@router.delete("/{punto_venta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_punto_venta(
    punto_venta_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """
    Desactivar un punto de venta.

    Args:
        punto_venta_id: ID del punto de venta
        db: Sesión de base de datos
        current_user: Usuario autenticado

    Raises:
        HTTPException: Si el punto de venta no existe o no pertenece a la empresa
    """
    result = await db.execute(select(PuntoVenta).where(PuntoVenta.id == punto_venta_id))
    punto_venta = result.scalar_one_or_none()

    if not punto_venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Punto de venta no encontrado"
        )

    # Verificar permisos
    if punto_venta.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este punto de venta",
        )

    # Compatibilidad: eliminar equivale a dejar de usar, sin borrar ni alterar ARCA.
    try:
        await ElegibilidadReceService(db).aplicar_cambios_punto(
            punto_venta,
            {"usar_en_factuflow": False},
            fuente="edicion",
            actor_usuario_id=current_user.id,
        )
    except ElegibilidadReceError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
