"""Servicio para perfiles de carga masiva por emisor."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.perfil_carga_masiva import PerfilCargaMasiva
from app.services.formatos_importacion_service import FormatosImportacionService


class PerfilCargaMasivaError(Exception):
    """Error funcional al administrar perfiles de carga masiva."""


class PerfilesCargaMasivaService:
    """Administra perfiles reutilizables para emisión masiva."""

    MODOS_CONCEPTO = {"productos", "servicios", "archivo", ""}
    MODOS_DESCRIPCION = {"archivo", "fija", ""}
    MODOS_FECHA_EMISION = {
        "archivo",
        "manual",
        "ultimo_dia_mes_anterior",
        "personalizada",
    }
    MODOS_PERIODO = {
        "archivo",
        "manual",
        "mes_anterior_completo",
        "mes_actual_completo",
        "personalizado",
    }
    MODOS_VENCIMIENTO = {
        "archivo",
        "manual",
        "mismo_dia_emision",
        "emision_mas_dias",
        "personalizada",
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.formatos_service = FormatosImportacionService(db)

    async def listar(self, empresa_id: int) -> list[PerfilCargaMasiva]:
        """Lista perfiles activos del emisor activo."""
        result = await self.db.execute(
            select(PerfilCargaMasiva)
            .where(
                PerfilCargaMasiva.empresa_id == empresa_id,
                PerfilCargaMasiva.activo.is_(True),
            )
            .order_by(
                PerfilCargaMasiva.es_predeterminado.desc(),
                PerfilCargaMasiva.nombre,
            )
        )
        return list(result.scalars().all())

    async def obtener(self, perfil_id: int, empresa_id: int) -> PerfilCargaMasiva:
        """Obtiene un perfil perteneciente al emisor activo."""
        result = await self.db.execute(
            select(PerfilCargaMasiva).where(
                PerfilCargaMasiva.id == perfil_id,
                PerfilCargaMasiva.empresa_id == empresa_id,
                PerfilCargaMasiva.activo.is_(True),
            )
        )
        perfil = result.scalar_one_or_none()
        if perfil is None:
            raise PerfilCargaMasivaError("Perfil de carga masiva no encontrado")
        return perfil

    async def crear(
        self,
        empresa_id: int,
        nombre: str,
        descripcion: str | None,
        configuracion: dict[str, Any],
        es_predeterminado: bool = False,
        activo: bool = True,
    ) -> PerfilCargaMasiva:
        """Crea un perfil para el emisor activo."""
        await self._validar_configuracion(configuracion, empresa_id)
        perfil = PerfilCargaMasiva(
            empresa_id=empresa_id,
            nombre=nombre.strip(),
            descripcion=descripcion.strip() if descripcion else None,
            configuracion_json=configuracion,
            es_predeterminado=es_predeterminado,
            activo=activo,
        )
        self.db.add(perfil)
        if es_predeterminado:
            await self._desmarcar_predeterminados(empresa_id, excepto=perfil)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise PerfilCargaMasivaError(
                "Ya existe un perfil de carga masiva con ese nombre para el emisor activo"
            ) from exc
        await self.db.refresh(perfil)
        return perfil

    async def actualizar(
        self,
        perfil_id: int,
        empresa_id: int,
        data: dict[str, Any],
    ) -> PerfilCargaMasiva:
        """Actualiza un perfil del emisor activo."""
        perfil = await self.obtener(perfil_id, empresa_id)
        if "configuracion_json" in data and data["configuracion_json"] is not None:
            await self._validar_configuracion(data["configuracion_json"], empresa_id)

        if "nombre" in data and data["nombre"] is not None:
            perfil.nombre = data["nombre"].strip()
        if "descripcion" in data:
            descripcion = data["descripcion"]
            perfil.descripcion = descripcion.strip() if descripcion else None
        if "configuracion_json" in data and data["configuracion_json"] is not None:
            perfil.configuracion_json = data["configuracion_json"]
        if "activo" in data and data["activo"] is not None:
            perfil.activo = bool(data["activo"])
        if "es_predeterminado" in data and data["es_predeterminado"] is not None:
            perfil.es_predeterminado = bool(data["es_predeterminado"])
            if perfil.es_predeterminado:
                await self._desmarcar_predeterminados(empresa_id, excepto=perfil)

        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise PerfilCargaMasivaError(
                "Ya existe un perfil de carga masiva con ese nombre para el emisor activo"
            ) from exc
        await self.db.refresh(perfil)
        return perfil

    async def eliminar(self, perfil_id: int, empresa_id: int) -> None:
        """Elimina un perfil del emisor activo."""
        perfil = await self.obtener(perfil_id, empresa_id)
        await self.db.delete(perfil)
        await self.db.commit()

    async def marcar_predeterminado(
        self, perfil_id: int, empresa_id: int
    ) -> PerfilCargaMasiva:
        """Marca un perfil como predeterminado del emisor activo."""
        perfil = await self.obtener(perfil_id, empresa_id)
        perfil.es_predeterminado = True
        await self._desmarcar_predeterminados(empresa_id, excepto=perfil)
        await self.db.commit()
        await self.db.refresh(perfil)
        return perfil

    async def snapshot(self, perfil_id: int, empresa_id: int) -> dict[str, Any]:
        """Devuelve una copia persistible del perfil usado en un lote."""
        perfil = await self.obtener(perfil_id, empresa_id)
        return {
            "id": perfil.id,
            "nombre": perfil.nombre,
            "configuracion_json": perfil.configuracion_json,
        }

    async def _desmarcar_predeterminados(
        self, empresa_id: int, excepto: PerfilCargaMasiva
    ) -> None:
        """Desmarca otros perfiles predeterminados del mismo emisor."""
        result = await self.db.execute(
            select(PerfilCargaMasiva).where(
                PerfilCargaMasiva.empresa_id == empresa_id,
                PerfilCargaMasiva.id != (excepto.id or 0),
                PerfilCargaMasiva.es_predeterminado.is_(True),
            )
        )
        for perfil in result.scalars().all():
            perfil.es_predeterminado = False

    async def _validar_configuracion(
        self, configuracion: dict[str, Any], empresa_id: int
    ) -> None:
        """Valida el shape mínimo y referencias de un perfil."""
        if not isinstance(configuracion, dict):
            raise PerfilCargaMasivaError("La configuración del perfil es inválida")

        version_id = configuracion.get("formato_importacion_version_id")
        if version_id not in (None, ""):
            try:
                await self.formatos_service.obtener_version(int(version_id), empresa_id)
            except Exception as exc:
                raise PerfilCargaMasivaError(str(exc)) from exc

        if configuracion.get("concepto_modo", "") not in self.MODOS_CONCEPTO:
            raise PerfilCargaMasivaError(
                "El concepto fiscal ARCA del perfil es inválido"
            )
        if configuracion.get("descripcion_item_modo", "") not in self.MODOS_DESCRIPCION:
            raise PerfilCargaMasivaError(
                "La política de descripción facturada del perfil es inválida"
            )

        self._validar_modo_anidado(
            configuracion,
            "fecha_emision",
            self.MODOS_FECHA_EMISION,
            "fecha de emisión",
        )
        self._validar_modo_anidado(
            configuracion,
            "periodo_servicio",
            self.MODOS_PERIODO,
            "periodo de servicios",
        )
        self._validar_modo_anidado(
            configuracion,
            "fecha_vto_pago",
            self.MODOS_VENCIMIENTO,
            "vencimiento de pago",
        )

        fecha_emision = configuracion.get("fecha_emision") or {}
        periodo = configuracion.get("periodo_servicio") or {}
        vencimiento = configuracion.get("fecha_vto_pago") or {}

        if fecha_emision.get("modo") == "personalizada" and not fecha_emision.get(
            "fecha"
        ):
            raise PerfilCargaMasivaError(
                "La fecha de emisión personalizada requiere una fecha explícita"
            )

        if periodo.get("modo") == "personalizado" and (
            not periodo.get("desde") or not periodo.get("hasta")
        ):
            raise PerfilCargaMasivaError(
                "El periodo personalizado requiere fecha desde y fecha hasta"
            )

        if vencimiento.get("modo") == "personalizada" and not vencimiento.get("fecha"):
            raise PerfilCargaMasivaError(
                "El vencimiento personalizado requiere una fecha explícita"
            )

        if vencimiento.get("modo") in {"mismo_dia_emision", "emision_mas_dias"}:
            if fecha_emision.get("modo") not in {
                "ultimo_dia_mes_anterior",
                "personalizada",
            }:
                raise PerfilCargaMasivaError(
                    "El vencimiento relativo requiere una fecha de emisión fija "
                    "o relativa concreta"
                )

        if vencimiento.get("modo") == "emision_mas_dias":
            try:
                dias = int(vencimiento.get("dias", 0))
            except (TypeError, ValueError) as exc:
                raise PerfilCargaMasivaError(
                    "Los días de vencimiento deben ser un número entero"
                ) from exc
            if dias < 0:
                raise PerfilCargaMasivaError(
                    "Los días de vencimiento no pueden ser negativos"
                )

    def _validar_modo_anidado(
        self,
        configuracion: dict[str, Any],
        key: str,
        modos_validos: set[str],
        nombre: str,
    ) -> None:
        """Valida una regla anidada opcional con campo modo."""
        regla = configuracion.get(key)
        if regla in (None, ""):
            return
        if not isinstance(regla, dict):
            raise PerfilCargaMasivaError(f"La regla de {nombre} es inválida")
        if regla.get("modo", "") not in modos_validos:
            raise PerfilCargaMasivaError(f"La regla de {nombre} es inválida")
