"""Autoridad central de accesos operativos por emisor."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.empresa import Empresa
from app.models.evento_sistema import EventoSistema
from app.models.usuario import Usuario
from app.models.usuario_emisor_acceso import UsuarioEmisorAcceso
from app.schemas.usuario import UsuarioResponse


async def listar_empresa_ids_asignados(db: AsyncSession, usuario_id: int) -> list[int]:
    """Devuelve las asignaciones explícitas ordenadas de un usuario."""
    result = await db.execute(
        select(UsuarioEmisorAcceso.empresa_id)
        .where(UsuarioEmisorAcceso.usuario_id == usuario_id)
        .order_by(UsuarioEmisorAcceso.empresa_id)
    )
    return [int(empresa_id) for empresa_id in result.scalars().all()]


async def mapear_empresa_ids_usuarios(
    db: AsyncSession, usuario_ids: Iterable[int]
) -> dict[int, list[int]]:
    """Carga asignaciones de varios usuarios sin consultas por fila."""
    ids = sorted({int(usuario_id) for usuario_id in usuario_ids})
    mapa = {usuario_id: [] for usuario_id in ids}
    if not ids:
        return mapa
    result = await db.execute(
        select(UsuarioEmisorAcceso.usuario_id, UsuarioEmisorAcceso.empresa_id)
        .where(UsuarioEmisorAcceso.usuario_id.in_(ids))
        .order_by(UsuarioEmisorAcceso.usuario_id, UsuarioEmisorAcceso.empresa_id)
    )
    for usuario_id, empresa_id in result.all():
        mapa[int(usuario_id)].append(int(empresa_id))
    return mapa


async def construir_usuario_response(
    db: AsyncSession, usuario: Usuario
) -> UsuarioResponse:
    """Expone asignaciones actuales sin convertir la respuesta en autoridad."""
    empresa_ids = await listar_empresa_ids_asignados(db, int(usuario.id))
    response = UsuarioResponse.model_validate(usuario)
    return response.model_copy(
        update={
            "empresa_ids": empresa_ids,
            "empresa_id": empresa_ids[0] if len(empresa_ids) == 1 else None,
        }
    )


def construir_usuario_response_con_ids(
    usuario: Usuario, empresa_ids: list[int]
) -> UsuarioResponse:
    """Construye respuestas administrativas a partir de una carga agrupada."""
    response = UsuarioResponse.model_validate(usuario)
    return response.model_copy(
        update={
            "empresa_ids": empresa_ids,
            "empresa_id": empresa_ids[0] if len(empresa_ids) == 1 else None,
        }
    )


async def puede_operar_empresa(
    db: AsyncSession, usuario: Usuario, empresa_id: int
) -> bool:
    """Resuelve la autoridad efectiva sin usar el campo singular legacy."""
    if usuario.es_admin:
        return True
    result = await db.execute(
        select(UsuarioEmisorAcceso.usuario_id).where(
            UsuarioEmisorAcceso.usuario_id == usuario.id,
            UsuarioEmisorAcceso.empresa_id == empresa_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def exigir_operacion_empresa(
    db: AsyncSession, usuario: Usuario, empresa_id: int
) -> None:
    """Rechaza el acceso por objeto antes de revelar si el emisor existe."""
    if await puede_operar_empresa(db, usuario, empresa_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tenés permiso para operar el emisor seleccionado",
    )


def exigir_creacion_empresa(usuario: Usuario) -> None:
    """Autoriza la creación global acotada de emisores."""
    if usuario.es_admin or usuario.puede_crear_editar_emisores:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tenés permiso para crear emisores",
    )


async def exigir_edicion_empresa(
    db: AsyncSession, usuario: Usuario, empresa_id: int
) -> None:
    """Exige capacidad global y asignación vigente para editar un emisor."""
    if usuario.es_admin:
        return
    if not usuario.puede_crear_editar_emisores:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permiso para editar emisores",
        )
    await exigir_operacion_empresa(db, usuario, empresa_id)


async def validar_empresa_ids(
    db: AsyncSession, empresa_ids: Iterable[int]
) -> list[int]:
    """Normaliza IDs y rechaza referencias inexistentes."""
    ids = sorted(int(empresa_id) for empresa_id in empresa_ids)
    if not ids:
        return []
    result = await db.execute(select(Empresa.id).where(Empresa.id.in_(ids)))
    existentes = {int(empresa_id) for empresa_id in result.scalars().all()}
    faltantes = [empresa_id for empresa_id in ids if empresa_id not in existentes]
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uno o más emisores asignados no existen",
        )
    return ids


async def reemplazar_accesos_usuario(
    db: AsyncSession,
    usuario: Usuario,
    empresa_ids: Iterable[int],
    *,
    actor_usuario_id: int | None,
    origen: str = "asignacion_admin",
) -> tuple[list[int], list[int]]:
    """Aplica la lista objetivo y sincroniza la compatibilidad singular."""
    objetivo = await validar_empresa_ids(db, empresa_ids)
    actuales = set(await listar_empresa_ids_asignados(db, int(usuario.id)))
    objetivo_set = set(objetivo)
    altas = sorted(objetivo_set - actuales)
    bajas = sorted(actuales - objetivo_set)

    if bajas:
        await db.execute(
            delete(UsuarioEmisorAcceso).where(
                UsuarioEmisorAcceso.usuario_id == usuario.id,
                UsuarioEmisorAcceso.empresa_id.in_(bajas),
            )
        )
    for empresa_id in altas:
        db.add(
            UsuarioEmisorAcceso(
                usuario_id=usuario.id,
                empresa_id=empresa_id,
                otorgado_por_usuario_id=actor_usuario_id,
                origen=origen,
            )
        )

    usuario.empresa_id = objetivo[0] if len(objetivo) == 1 else None
    return altas, bajas


def registrar_evento_autorizacion(
    db: AsyncSession,
    *,
    accion: str,
    actor_usuario_id: int | None,
    usuario_afectado_id: int | None,
    empresa_id: int | None = None,
    altas: int = 0,
    bajas: int = 0,
) -> None:
    """Agrega un evento administrativo sin datos fiscales o personales."""
    db.add(
        EventoSistema(
            accion=accion,
            categoria="autorizacion",
            estado="exitoso",
            descripcion="Se actualizó una autorización operativa por emisor.",
            bytes_afectados=0,
            usuario_id=actor_usuario_id,
            empresa_id=empresa_id,
            metadata_json={
                "usuario_afectado_id": usuario_afectado_id,
                "altas": altas,
                "bajas": bajas,
            },
        )
    )
