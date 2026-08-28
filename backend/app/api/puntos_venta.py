"""Endpoints de Puntos de Venta."""

import hashlib
from contextlib import AsyncExitStack
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.arca import get_wsfe_client
from app.api.deps import get_current_empresa_id
from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_empresa_user
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
    AtestacionPuntoRece,
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
        nombre_fantasia=punto_venta.nombre_fantasia,
        es_webservice=bool(punto_venta.es_webservice),
        bloqueado=bool(punto_venta.bloqueado),
        fecha_baja=punto_venta.fecha_baja,
        fuente=punto_venta.fuente,
        empresa_id=int(punto_venta.empresa_id),
        activo=bool(punto_venta.activo),
        usable_factuflow=usable,
        puede_intentar_emision=bool(
            acreditado
            and (
                punto_venta.usable_factuflow
                or punto_venta.ultima_comprobacion_arca_en is None
            )
        ),
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
    # Verificar que no exista otro punto de venta con ese número en la empresa
    result = await db.execute(
        select(PuntoVenta).where(
            PuntoVenta.empresa_id == empresa_id,
            PuntoVenta.numero == punto_venta_data.numero,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un punto de venta con el número {punto_venta_data.numero}",
        )

    # Crear punto de venta
    nuevo_punto_venta = PuntoVenta(
        **punto_venta_data.model_dump(), empresa_id=empresa_id
    )

    db.add(nuevo_punto_venta)
    try:
        await ElegibilidadReceService(db).crear_contextos_iniciales_no_verificados(
            nuevo_punto_venta,
            creado_por_usuario_id=admin.id,
        )
        await db.commit()
        await db.refresh(nuevo_punto_venta)
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
                "El punto de venta ya existe o cambió de forma concurrente. "
                "Recargá y volvé a intentarlo."
            ),
        ) from exc
    return await _serializar_punto_venta(db, nuevo_punto_venta)


@router.post("/importar-constancia", response_model=ImportarPuntosVentaResponse)
async def importar_constancia_puntos_venta(
    file: UploadFile = File(...),
    confirmar_procedencia_produccion: bool = Form(
        False,
        deprecated=True,
        description="Parámetro de compatibilidad deprecado; la UI usa siempre true.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
    empresa_id: int = Depends(get_current_empresa_id),
):
    """Importar detalle de puntos de venta desde constancia ARCA."""

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
            detail="El PDF supera el límite de 5 MB.",
        )

    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emisor no encontrado",
        )

    try:
        texto = extraer_texto_constancia_puntos_pdf(contenido)
        datos = parsear_constancia_puntos_venta(texto)
    except ConstanciaPuntosVentaError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    warnings = list(datos.warnings)
    numeros_constancia = [punto.numero for punto in datos.puntos_venta]
    if any(numero < 1 or numero > 99999 for numero in numeros_constancia):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La constancia contiene un número de punto de venta inválido.",
        )
    if len(set(numeros_constancia)) != len(numeros_constancia):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La constancia contiene puntos de venta duplicados.",
        )
    if datos.cuit and datos.cuit != empresa.cuit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La constancia no corresponde al CUIT del emisor activo.",
        )
    elegibilidad_service = ElegibilidadReceService(db)
    evidencia_sha256: str | None = None
    if confirmar_procedencia_produccion:
        if datos.warnings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La constancia no pudo interpretarse de forma completa y no "
                    "puede acreditar RECE."
                ),
            )
        if datos.cuit is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La constancia no contiene el CUIT necesario para acreditar RECE."
                ),
            )
        if datos.documento_emitido_en is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "La constancia no contiene una fecha documental válida para "
                    "acreditar RECE."
                ),
            )
        evidencia_sha256 = hashlib.sha256(contenido).hexdigest()
        try:
            elegibilidad_service.validar_documento_constancia_productiva(
                empresa_id=empresa_id,
                empresa_cuit=empresa.cuit,
                evidencia_sha256=evidencia_sha256,
                documento_emitido_en=datos.documento_emitido_en,
                actor_usuario_id=current_user.id,
            )
        except ElegibilidadReceError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

    estado_arca = await _obtener_estado_puntos_arca(db, current_user, empresa_id)
    estado_arca_disponible = estado_arca is not None
    comprobado_en = datetime.utcnow() if estado_arca_disponible else None
    if not estado_arca_disponible:
        estado_arca = {}
        warnings.append(
            "No se pudo consultar el estado técnico de puntos de venta en ARCA. "
            "Se conservaron los estados existentes y los puntos nuevos quedaron "
            "inactivos hasta comprobar con ARCA."
        )

    result = await db.execute(
        select(PuntoVenta).where(PuntoVenta.empresa_id == empresa_id)
    )
    existentes = {pv.numero: pv for pv in result.scalars().all()}
    numeros_presentes = set(numeros_constancia)
    constancia_completa = datos.cuit is not None and not datos.warnings
    ausentes = (
        [
            punto
            for numero, punto in existentes.items()
            if numero not in numeros_presentes
        ]
        if constancia_completa
        else []
    )
    invalidaciones_ausentes = [(punto, {"activo": False}) for punto in ausentes]

    creados = 0
    actualizados = 0
    omitidos = len(datos.warnings)
    no_informados_por_wsfe = 0
    cambios_existentes: list[tuple[PuntoVenta, dict[str, object]]] = []
    atestaciones: list[AtestacionPuntoRece] = []
    resultados: dict[int, str] = {}
    try:
        async with AsyncExitStack() as stack:
            if confirmar_procedencia_produccion:
                await stack.enter_async_context(
                    elegibilidad_service.bloquear_frontera_atestacion_productiva(
                        empresa_id=empresa_id,
                        empresa_cuit=empresa.cuit,
                        actor_usuario_id=current_user.id,
                    )
                )

            for punto in datos.puntos_venta:
                pv = existentes.get(punto.numero)
                arca_status = estado_arca.get(punto.numero)
                if arca_status is not None:
                    bloqueado = bool(arca_status.get("bloqueado", False))
                    fecha_baja = arca_status.get("fecha_baja")
                    activo = not bloqueado and not fecha_baja
                elif estado_arca_disponible:
                    bloqueado = bool(pv.bloqueado) if pv else False
                    fecha_baja = pv.fecha_baja if pv else None
                    activo = False
                    no_informados_por_wsfe += 1
                elif pv:
                    bloqueado = pv.bloqueado
                    fecha_baja = pv.fecha_baja
                    activo = pv.activo
                else:
                    bloqueado = False
                    fecha_baja = None
                    activo = estado_arca_disponible
                nombre = punto.nombre_fantasia or punto.sistema

                payload = {
                    "nombre": nombre,
                    "sistema": punto.sistema,
                    "domicilio": punto.domicilio,
                    "nombre_fantasia": punto.nombre_fantasia,
                    "es_webservice": punto.es_webservice,
                    "bloqueado": bloqueado,
                    "fecha_baja": fecha_baja,
                    "fuente": "constancia_arca",
                    "activo": activo,
                    "ultima_comprobacion_arca_en": (
                        comprobado_en
                        if estado_arca_disponible
                        else (
                            pv.ultima_comprobacion_arca_en if pv is not None else None
                        )
                    ),
                }

                if pv:
                    if confirmar_procedencia_produccion:
                        atestaciones.append(
                            AtestacionPuntoRece(
                                punto_venta=pv,
                                cambios=payload,
                                sistema_constancia=punto.sistema,
                            )
                        )
                    else:
                        cambios_existentes.append((pv, payload))
                    actualizados += 1
                    continue

                nuevo_punto = PuntoVenta(
                    numero=punto.numero,
                    empresa_id=empresa_id,
                    **payload,
                )
                db.add(nuevo_punto)
                await elegibilidad_service.crear_contextos_iniciales_no_verificados(
                    nuevo_punto,
                    creado_por_usuario_id=current_user.id,
                    fuente="sincronizacion_wsfe",
                )
                if confirmar_procedencia_produccion:
                    atestaciones.append(
                        AtestacionPuntoRece(
                            punto_venta=nuevo_punto,
                            cambios=payload,
                            sistema_constancia=punto.sistema,
                        )
                    )
                creados += 1

            if confirmar_procedencia_produccion:
                assert datos.documento_emitido_en is not None
                assert evidencia_sha256 is not None
                resultados = (
                    await elegibilidad_service.atestiguar_constancia_productiva(
                        atestaciones,
                        invalidaciones_ausentes=invalidaciones_ausentes,
                        empresa_id=empresa_id,
                        empresa_cuit=empresa.cuit,
                        evidencia_sha256=evidencia_sha256,
                        documento_emitido_en=datos.documento_emitido_en,
                        actor_usuario_id=current_user.id,
                    )
                )
            elif cambios_existentes or invalidaciones_ausentes:
                await elegibilidad_service.aplicar_cambios_puntos_atomicos(
                    cambios_existentes + invalidaciones_ausentes,
                    fuente="edicion",
                    actor_usuario_id=current_user.id,
                    forzar_revision_ids={int(punto.id) for punto in ausentes},
                )
            else:
                await db.commit()
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

    if confirmar_procedencia_produccion:
        verificados_rece = sum(
            estado == "verificado_rece" for estado in resultados.values()
        )
        pendientes_comprobacion = sum(
            resultados.get(int(atestacion.punto_venta.id)) == "verificado_rece"
            and atestacion.punto_venta.ultima_comprobacion_arca_en is None
            for atestacion in atestaciones
        )
        no_verificados_rece = len(resultados) - verificados_rece
        if no_verificados_rece:
            warnings.append(
                f"{no_verificados_rece} punto(s) no coincidieron con una modalidad "
                "Web Services exacta admitida y quedaron sin acreditar."
            )
    else:
        verificados_rece = 0
        pendientes_comprobacion = 0
        no_verificados_rece = len(datos.puntos_venta)
    if ausentes:
        warnings.append(
            f"{len(ausentes)} punto(s) existentes no figuraron en la constancia "
            "completa y quedaron inactivos y sin acreditación RECE."
        )
    elif not constancia_completa:
        warnings.append(
            "No se desactivaron puntos ausentes porque la constancia no pudo "
            "validarse como completa."
        )
    if no_informados_por_wsfe:
        warnings.append(
            f"{no_informados_por_wsfe} punto(s) de la constancia no figuraron en "
            "la consulta técnica WSFE y quedaron inactivos."
        )

    return ImportarPuntosVentaResponse(
        total_constancia=len(datos.puntos_venta),
        creados=creados,
        actualizados=actualizados,
        omitidos=omitidos,
        desactivados_ausentes=len(ausentes),
        verificados_rece=verificados_rece,
        pendientes_comprobacion=pendientes_comprobacion,
        no_verificados_rece=no_verificados_rece,
        documento_emitido_en=datos.documento_emitido_en,
        vigente_hasta=None,
        warnings=warnings,
    )


async def _obtener_estado_puntos_arca(
    db: AsyncSession,
    current_user: Usuario,
    empresa_id: int,
) -> dict[int, dict[str, str | bool | None]] | None:
    """Obtener estado tecnico ARCA de puntos webservice si esta disponible."""

    try:
        wsfe_client = await get_wsfe_client(db, current_user, empresa_id)
        puntos = list(await wsfe_client.fe_param_get_ptos_venta())
    except Exception:
        return None
    if not puntos:
        return None

    try:
        numeros = [int(punto.numero) for punto in puntos]
        bloqueos = [str(punto.bloqueado).strip().upper() for punto in puntos]
    except (AttributeError, TypeError, ValueError):
        return None
    if (
        len(set(numeros)) != len(numeros)
        or any(numero < 1 or numero > 99999 for numero in numeros)
        or any(bloqueo not in {"S", "N"} for bloqueo in bloqueos)
    ):
        return None

    return {
        int(punto.numero): {
            "bloqueado": str(punto.bloqueado).strip().upper() == "S",
            "fecha_baja": (
                None
                if not (punto.fecha_baja or "").strip()
                or (punto.fecha_baja or "").strip().upper() == "NULL"
                else (punto.fecha_baja or "").strip()
            ),
        }
        for punto in puntos
    }


@router.post("/sincronizar-arca", response_model=SincronizarPuntosVentaResponse)
async def sincronizar_puntos_venta_arca(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_admin_user),
    empresa_id: int = Depends(get_current_empresa_id),
) -> SincronizarPuntosVentaResponse:
    """Comprueba el estado técnico WSFE sin promover elegibilidad RECE."""
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

    # Actualizar campos
    update_data = punto_venta_data.model_dump(exclude_unset=True)
    if not current_user.es_admin and (
        set(update_data) - ElegibilidadReceService.CAMPOS_DESCRIPTIVOS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo un administrador puede cambiar los datos fiscales o "
                "técnicos de un punto de venta."
            ),
        )
    if "numero" in update_data and update_data["numero"] != punto_venta.numero:
        result = await db.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == empresa_id,
                PuntoVenta.numero == update_data["numero"],
                PuntoVenta.id != punto_venta.id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Ya existe un punto de venta con el número "
                    f"{update_data['numero']}"
                ),
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

    await db.commit()
    await db.refresh(punto_venta)

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

    # Desactivar
    try:
        await ElegibilidadReceService(db).aplicar_cambios_punto(
            punto_venta,
            {"activo": False},
            fuente="edicion",
            actor_usuario_id=current_user.id,
        )
    except ElegibilidadReceError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    await db.commit()
