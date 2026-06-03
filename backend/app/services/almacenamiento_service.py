"""Servicio administrativo para medir y liberar almacenamiento."""

from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from secrets import token_hex
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.certificado import Certificado
from app.models.comprobante import Comprobante
from app.models.empresa import Empresa
from app.models.evento_sistema import EventoSistema, ExportacionAlmacenamiento
from app.models.lote_comprobante import LoteComprobante, LoteComprobanteFila
from app.services.certificados_service import (
    MANAGED_CERT_FILENAME_RE,
    resolve_cert_storage_path,
)
from app.services.lote_comprobantes_service import (
    LoteComprobanteError,
    LoteComprobantesService,
)


class AlmacenamientoError(Exception):
    """Error controlado del gestor de almacenamiento."""


@dataclass(frozen=True)
class StorageFileCandidate:
    """Archivo administrado seleccionable sin exponer rutas absolutas."""

    id: str
    path: Path
    nombre: str
    categoria: str
    bytes_usados: int
    descripcion: str
    created_at: datetime | None = None


class AlmacenamientoService:
    """Calcula uso de almacenamiento y ejecuta limpiezas seguras."""

    ESTADOS_LOTE_CERRADO = {
        "completado",
        "cerrado_reconciliado",
        "cerrado_con_descartes",
    }
    BYTES_ESTIMADOS_POR_FILA = 2048
    CONFIRMACION_LIBERACION = "YA_LO_DESCARGUE"

    def __init__(self, db: AsyncSession):
        """Inicializa el servicio con una sesión de base de datos."""
        self.db = db

    async def obtener_resumen(self) -> dict[str, Any]:
        """Devuelve el resumen seguro de uso por categoría y emisor."""
        categorias: list[dict[str, Any]] = []
        db_bytes = await self._database_size_bytes()
        lotes = await self._resumen_lotes()
        certs = await self.listar_certificados_huerfanos()
        logs = self.listar_logs_antiguos()
        active_log_bytes = self._active_log_size()
        temporales = self.listar_temporales()
        cache_bytes = self._safe_file_size(Path(settings.arca_token_cache_path))

        categorias.append(
            self._categoria(
                "base",
                "Base de datos",
                db_bytes,
                0,
                lotes["lotes"],
                "Incluye datos fiscales, usuarios, emisores, comprobantes y lotes.",
            )
        )
        categorias.append(
            self._categoria(
                "lotes",
                "Detalle de lotes",
                lotes["bytes_estimados"],
                lotes["bytes_recuperables"],
                lotes["filas_persistidas"],
                "Estimación lógica del detalle importado desde Excel.",
            )
        )
        categorias.append(
            self._categoria(
                "certificados",
                "Certificados",
                self._directory_size(Path(settings.certs_path)),
                sum(item.bytes_usados for item in certs),
                len(certs),
                "Solo se limpian archivos gestionados y no referenciados.",
            )
        )
        categorias.append(
            self._categoria(
                "logs",
                "Logs",
                active_log_bytes + sum(item.bytes_usados for item in logs),
                sum(item.bytes_usados for item in logs),
                len(logs) + (1 if active_log_bytes else 0),
                "Incluye el log activo; solo los rotados son recuperables.",
            )
        )
        categorias.append(
            self._categoria(
                "temporales",
                "Temporales",
                sum(item.bytes_usados for item in temporales),
                sum(item.bytes_usados for item in temporales),
                len(temporales),
                "Archivos descargables o temporales no vitales.",
            )
        )
        categorias.append(
            self._categoria(
                "cache",
                "Caché ARCA",
                cache_bytes,
                0,
                1 if cache_bytes else 0,
                "Caché operativo de tokens; no se limpia desde este gestor.",
            )
        )

        total_usado = (
            db_bytes
            + self._directory_size(Path(settings.certs_path))
            + active_log_bytes
            + sum(item.bytes_usados for item in logs)
            + sum(item.bytes_usados for item in temporales)
            + cache_bytes
        )
        total_recuperable = sum(item["bytes_recuperables"] for item in categorias)
        disk = self._disk_usage()
        estado = self._estado_general(total_usado, disk)

        return {
            "generated_at": datetime.utcnow(),
            "estado": estado,
            "total_bytes_usados": total_usado,
            "total_bytes_recuperables": total_recuperable,
            "storage_limit_bytes": settings.storage_limit_bytes,
            "disk_total_bytes": disk["total"],
            "disk_used_bytes": disk["used"],
            "disk_free_bytes": disk["free"],
            "categorias": categorias,
            "emisores": await self._resumen_emisores(),
        }

    async def listar_lotes_compactables(self) -> list[dict[str, Any]]:
        """Lista lotes cerrados que conservan filas compactables."""
        filas = (
            select(
                LoteComprobante.id.label("lote_id"),
                func.count(LoteComprobanteFila.id).label("filas"),
            )
            .join(
                LoteComprobanteFila,
                LoteComprobanteFila.lote_id == LoteComprobante.id,
            )
            .where(
                LoteComprobante.estado.in_(self.ESTADOS_LOTE_CERRADO),
                LoteComprobante.compactado_at.is_(None),
            )
            .group_by(LoteComprobante.id)
            .subquery()
        )
        result = await self.db.execute(
            select(LoteComprobante, Empresa, filas.c.filas)
            .join(Empresa, Empresa.id == LoteComprobante.empresa_id)
            .join(filas, filas.c.lote_id == LoteComprobante.id)
            .order_by(LoteComprobante.created_at.desc())
        )
        items = []
        for lote, empresa, filas_persistidas in result.all():
            filas_count = int(filas_persistidas or 0)
            items.append(
                {
                    "id": lote.id,
                    "empresa_id": lote.empresa_id,
                    "etiqueta_emisor": self._empresa_label(empresa),
                    "estado": lote.estado,
                    "total_filas": lote.total_filas,
                    "total_grupos": lote.total_grupos,
                    "filas_persistidas": filas_count,
                    "bytes_recuperables": filas_count * self.BYTES_ESTIMADOS_POR_FILA,
                    "created_at": lote.created_at,
                    "finished_at": lote.finished_at,
                }
            )
        return items

    def listar_logs_antiguos(self) -> list[StorageFileCandidate]:
        """Lista logs antiguos o rotados que pueden exportarse o limpiarse."""
        log_file = Path(settings.log_file).resolve() if settings.log_file else None
        if log_file is None:
            return []

        log_dir = log_file.parent
        if not log_dir.exists():
            return []

        cutoff = datetime.utcnow() - timedelta(
            days=max(settings.storage_log_retention_days, 1)
        )
        candidatos: list[StorageFileCandidate] = []
        for path in sorted(log_dir.iterdir()):
            if not path.is_file() or path.resolve() == log_file:
                continue
            if not self._is_log_antiguo_administrado(path, log_file):
                continue
            modified_at = datetime.utcfromtimestamp(path.stat().st_mtime)
            if modified_at > cutoff:
                continue
            candidatos.append(
                StorageFileCandidate(
                    id=path.name,
                    path=path.resolve(),
                    nombre=path.name,
                    categoria="logs",
                    bytes_usados=path.stat().st_size,
                    descripcion="Log antiguo o rotado",
                    created_at=modified_at,
                )
            )
        return candidatos

    def listar_temporales(self) -> list[StorageFileCandidate]:
        """Lista archivos temporales administrados, excluyendo exportaciones."""
        base = self._storage_tmp_path(create=False)
        if not base.exists():
            return []

        exportaciones_dir = self._exportaciones_path(create=False)
        candidatos: list[StorageFileCandidate] = []
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if exportaciones_dir.exists():
                try:
                    resolved.relative_to(exportaciones_dir)
                    continue
                except ValueError:
                    pass
            rel = resolved.relative_to(base).as_posix()
            candidatos.append(
                StorageFileCandidate(
                    id=rel,
                    path=resolved,
                    nombre=rel,
                    categoria="temporales",
                    bytes_usados=resolved.stat().st_size,
                    descripcion="Archivo temporal administrado",
                    created_at=datetime.utcfromtimestamp(resolved.stat().st_mtime),
                )
            )
        return candidatos

    async def listar_certificados_huerfanos(self) -> list[StorageFileCandidate]:
        """Lista archivos de certificado gestionados y no referenciados."""
        base = Path(settings.certs_path).resolve()
        if not base.exists():
            return []

        referenciados = await self._certificados_referenciados()
        candidatos: list[StorageFileCandidate] = []
        for path in sorted(base.iterdir()):
            if not path.is_file():
                continue
            match = MANAGED_CERT_FILENAME_RE.fullmatch(path.name)
            if not match:
                continue
            resolved = path.resolve()
            if resolved in referenciados:
                continue
            extension = match.group("extension")
            ambiente = match.group("ambiente")
            candidatos.append(
                StorageFileCandidate(
                    id=self._certificado_opaque_id(path.name),
                    path=resolved,
                    nombre=f"Archivo gestionado {ambiente}.{extension}",
                    categoria="certificados",
                    bytes_usados=resolved.stat().st_size,
                    descripcion="No está referenciado por certificados cargados",
                    created_at=datetime.utcfromtimestamp(resolved.stat().st_mtime),
                )
            )
        return candidatos

    async def crear_exportacion(
        self, seleccion: dict[str, Any], usuario_id: int
    ) -> ExportacionAlmacenamiento:
        """Crea un ZIP de resguardo con la selección indicada."""
        lote_ids = self._unique_ints(seleccion.get("lote_ids") or [])
        log_ids = self._unique_strings(seleccion.get("log_ids") or [])
        temporal_ids = self._unique_strings(seleccion.get("temporal_ids") or [])
        if not lote_ids and not log_ids and not temporal_ids:
            raise AlmacenamientoError("Seleccioná al menos un elemento para exportar")

        lotes = await self._lotes_compactables_por_id(lote_ids)
        logs = self._candidates_by_id(self.listar_logs_antiguos(), log_ids, "logs")
        temporales = self._candidates_by_id(
            self.listar_temporales(), temporal_ids, "temporales"
        )

        token = token_hex(32)
        filename = (
            f"factuflow-resguardo-{datetime.utcnow():%Y%m%d-%H%M%S}-{token[:8]}.zip"
        )
        export_path = self._exportaciones_path(create=True) / filename
        manifest = {
            "version": 1,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "selection": {
                "lote_ids": [lote.id for lote in lotes],
                "log_ids": [item.id for item in logs],
                "temporal_ids": [item.id for item in temporales],
            },
            "items": [],
        }

        with zipfile.ZipFile(
            export_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            await self._agregar_lotes_exportacion(archive, manifest, lotes)
            self._agregar_archivos_exportacion(archive, manifest, logs)
            self._agregar_archivos_exportacion(archive, manifest, temporales)
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
            )

        checksum = self._sha256_file(export_path)
        exportacion = ExportacionAlmacenamiento(
            token=token,
            estado="pendiente_descarga",
            categoria="mixta",
            archivo_nombre=filename,
            checksum_sha256=checksum,
            size_bytes=export_path.stat().st_size,
            seleccion_json=manifest["selection"],
            manifest_json=manifest,
            usuario_id=usuario_id,
        )
        self.db.add(exportacion)
        self._registrar_evento(
            accion="crear_exportacion",
            categoria="almacenamiento",
            usuario_id=usuario_id,
            descripcion="Se preparó un resguardo descargable antes de liberar espacio.",
            bytes_afectados=exportacion.size_bytes,
            metadata={"items": len(manifest["items"])},
        )
        await self.db.commit()
        await self.db.refresh(exportacion)
        return exportacion

    async def obtener_exportacion_por_token(
        self, token: str
    ) -> ExportacionAlmacenamiento:
        """Obtiene una exportación por token opaco."""
        result = await self.db.execute(
            select(ExportacionAlmacenamiento).where(
                ExportacionAlmacenamiento.token == token
            )
        )
        exportacion = result.scalar_one_or_none()
        if exportacion is None:
            raise AlmacenamientoError("Exportación no encontrada")
        return exportacion

    async def preparar_descarga_exportacion(
        self, token: str
    ) -> tuple[ExportacionAlmacenamiento, str]:
        """Prepara una descarga y devuelve su token de confirmación."""
        exportacion = await self.obtener_exportacion_por_token(token)
        path = self.exportacion_path(exportacion)
        if not path.is_file():
            raise AlmacenamientoError("El archivo de resguardo ya no está disponible")
        download_token = token_hex(16)
        manifest = dict(exportacion.manifest_json or {})
        manifest["download_confirmation_token"] = download_token
        exportacion.manifest_json = manifest
        await self.db.commit()
        await self.db.refresh(exportacion)
        return exportacion, download_token

    async def confirmar_descarga_exportacion(
        self,
        token: str,
        checksum_sha256: str,
        download_token: str,
        usuario_id: int,
    ) -> ExportacionAlmacenamiento:
        """Registra la confirmación explícita posterior a la descarga del ZIP."""
        exportacion = await self.obtener_exportacion_por_token(token)
        if checksum_sha256 != exportacion.checksum_sha256:
            raise AlmacenamientoError("El checksum del resguardo no coincide")
        manifest = dict(exportacion.manifest_json or {})
        expected_download_token = manifest.get("download_confirmation_token")
        if not expected_download_token or download_token != expected_download_token:
            raise AlmacenamientoError("La confirmación de descarga no coincide")
        if exportacion.downloaded_at is None:
            exportacion.downloaded_at = datetime.utcnow()
            exportacion.estado = "descargada"
            manifest["download_confirmation_token"] = None
            exportacion.manifest_json = manifest
            self._registrar_evento(
                accion="descargar_exportacion",
                categoria="almacenamiento",
                usuario_id=usuario_id,
                descripcion="Se inició la descarga del resguardo de almacenamiento.",
                bytes_afectados=exportacion.size_bytes,
                metadata={"token": exportacion.token[:8]},
            )
            await self.db.commit()
            await self.db.refresh(exportacion)
        return exportacion

    async def confirmar_liberacion(
        self, token: str, confirmacion: str, usuario_id: int
    ) -> dict[str, Any]:
        """Libera espacio solo después de una confirmación manual."""
        if confirmacion != self.CONFIRMACION_LIBERACION:
            raise AlmacenamientoError(
                "La confirmación no coincide. Descargá el resguardo y confirmá nuevamente."
            )
        if not settings.storage_enable_cleanup:
            raise AlmacenamientoError(
                "La limpieza está deshabilitada por configuración"
            )

        exportacion = await self.obtener_exportacion_por_token(token)
        if exportacion.downloaded_at is None:
            raise AlmacenamientoError(
                "Primero descargá el resguardo antes de liberar espacio"
            )
        if exportacion.released_at is not None:
            return {"bytes": 0, "items": 0, "mensaje": "La exportación ya fue liberada"}

        seleccion = exportacion.seleccion_json or {}
        bytes_afectados = 0
        items_afectados = 0
        lote_ids = self._unique_ints(seleccion.get("lote_ids") or [])
        log_candidates = self._candidates_by_id(
            self.listar_logs_antiguos(),
            seleccion.get("log_ids") or [],
            "logs",
            exportacion.manifest_json,
        )
        temporal_candidates = self._candidates_by_id(
            self.listar_temporales(),
            seleccion.get("temporal_ids") or [],
            "temporales",
            exportacion.manifest_json,
        )
        lotes = await self._validar_lotes_liberables(lote_ids)
        lote_service = LoteComprobantesService(self.db)
        for lote in lotes:
            lote_id = lote.id
            filas = await self._contar_filas_lote(lote_id)
            try:
                await lote_service.compactar_lote(
                    lote_id,
                    lote.empresa_id,
                    usuario_id,
                    commit=False,
                )
            except LoteComprobanteError as exc:
                await self.db.rollback()
                raise AlmacenamientoError(
                    f"No se pudo compactar el lote #{lote_id}: {exc}"
                ) from exc
            bytes_afectados += filas * self.BYTES_ESTIMADOS_POR_FILA
            items_afectados += 1

        for candidate in log_candidates:
            bytes_afectados += self._unlink_candidate(candidate)
            items_afectados += 1
        for candidate in temporal_candidates:
            bytes_afectados += self._unlink_candidate(candidate)
            items_afectados += 1

        export_path = self.exportacion_path(exportacion)
        if export_path.exists():
            bytes_afectados += self._safe_file_size(export_path)
            export_path.unlink()

        exportacion.released_at = datetime.utcnow()
        exportacion.estado = "liberada"
        self._registrar_evento(
            accion="confirmar_liberacion",
            categoria="almacenamiento",
            usuario_id=usuario_id,
            descripcion="Se liberó espacio después de confirmar la descarga del resguardo.",
            bytes_afectados=bytes_afectados,
            metadata={"items": items_afectados, "token": exportacion.token[:8]},
        )
        await self.db.commit()
        return {
            "bytes": bytes_afectados,
            "items": items_afectados,
            "mensaje": "Espacio liberado correctamente.",
        }

    async def limpiar_certificados_huerfanos(
        self, ids: list[str], usuario_id: int
    ) -> dict[str, Any]:
        """Elimina certificados huérfanos gestionados por FactuFlow."""
        if not settings.storage_enable_cleanup:
            raise AlmacenamientoError(
                "La limpieza está deshabilitada por configuración"
            )
        ids_unicos = self._unique_strings(ids)
        if not ids_unicos:
            raise AlmacenamientoError("Seleccioná certificados huérfanos para limpiar")

        candidatos = self._candidates_by_id(
            await self.listar_certificados_huerfanos(), ids_unicos, "certificados"
        )
        bytes_afectados = 0
        items_afectados = 0
        for candidate in candidatos:
            bytes_afectados += self._unlink_candidate(candidate)
            items_afectados += 1
        self._registrar_evento(
            accion="limpiar_certificados_huerfanos",
            categoria="certificados",
            usuario_id=usuario_id,
            descripcion="Se eliminaron certificados gestionados no referenciados.",
            bytes_afectados=bytes_afectados,
            metadata={"items": items_afectados},
        )
        await self.db.commit()
        return {
            "bytes": bytes_afectados,
            "items": items_afectados,
            "mensaje": "Certificados huérfanos eliminados correctamente.",
        }

    def exportacion_path(self, exportacion: ExportacionAlmacenamiento) -> Path:
        """Resuelve el path interno de una exportación persistida."""
        filename = Path(exportacion.archivo_nombre).name
        if filename != exportacion.archivo_nombre:
            raise AlmacenamientoError("Nombre de exportación inválido")
        path = self._exportaciones_path(create=False) / filename
        return self._ensure_inside(self._exportaciones_path(create=False), path)

    async def _agregar_lotes_exportacion(
        self,
        archive: zipfile.ZipFile,
        manifest: dict[str, Any],
        lotes: list[LoteComprobante],
    ) -> None:
        """Agrega resúmenes y observados de lotes al ZIP."""
        lote_service = LoteComprobantesService(self.db)
        for lote in lotes:
            prefix = f"lotes/lote-{lote.id}"
            resumen = {
                "lote_id": lote.id,
                "empresa_id": lote.empresa_id,
                "estado": lote.estado,
                "total_filas": lote.total_filas,
                "total_grupos": lote.total_grupos,
                "grupos_emitidos": lote.grupos_emitidos,
                "grupos_fallidos": lote.grupos_fallidos,
                "created_at": lote.created_at.isoformat(),
                "finished_at": (
                    lote.finished_at.isoformat() if lote.finished_at else None
                ),
            }
            archive.writestr(
                f"{prefix}/resumen.json",
                json.dumps(resumen, ensure_ascii=False, indent=2),
            )
            observado = await lote_service.generar_archivo_observado(
                lote.id, lote.empresa_id
            )
            archive.writestr(f"{prefix}/observado.xlsx", observado)
            manifest["items"].append(
                {
                    "categoria": "lotes",
                    "id": lote.id,
                    "archivos": [
                        f"{prefix}/resumen.json",
                        f"{prefix}/observado.xlsx",
                    ],
                }
            )

    def _agregar_archivos_exportacion(
        self,
        archive: zipfile.ZipFile,
        manifest: dict[str, Any],
        files: list[StorageFileCandidate],
    ) -> None:
        """Agrega archivos administrados al ZIP."""
        for candidate in files:
            safe_id = candidate.id.replace("\\", "/")
            archive_name = f"{candidate.categoria}/{safe_id}"
            archive.write(candidate.path, archive_name)
            manifest["items"].append(
                {
                    "categoria": candidate.categoria,
                    "id": candidate.id,
                    "bytes": candidate.bytes_usados,
                    "sha256": self._sha256_file(candidate.path),
                    "modified_at": (
                        candidate.created_at.isoformat()
                        if candidate.created_at
                        else None
                    ),
                    "archivo": archive_name,
                }
            )

    async def _lotes_compactables_por_id(
        self, lote_ids: list[int]
    ) -> list[LoteComprobante]:
        """Obtiene lotes compactables desde una selección explícita."""
        if not lote_ids:
            return []
        result = await self.db.execute(
            select(LoteComprobante)
            .join(
                LoteComprobanteFila, LoteComprobanteFila.lote_id == LoteComprobante.id
            )
            .where(
                LoteComprobante.id.in_(lote_ids),
                LoteComprobante.estado.in_(self.ESTADOS_LOTE_CERRADO),
                LoteComprobante.compactado_at.is_(None),
            )
            .group_by(LoteComprobante.id)
        )
        lotes = result.scalars().all()
        encontrados = {lote.id for lote in lotes}
        faltantes = set(lote_ids) - encontrados
        if faltantes:
            raise AlmacenamientoError(
                "Uno o más lotes seleccionados ya no pueden compactarse"
            )
        return list(lotes)

    async def _lote_resumen(self, lote_id: int) -> LoteComprobante | None:
        """Obtiene un lote sin cargar relaciones pesadas."""
        result = await self.db.execute(
            select(LoteComprobante).where(LoteComprobante.id == lote_id)
        )
        return result.scalar_one_or_none()

    async def _validar_lotes_liberables(
        self, lote_ids: list[int]
    ) -> list[LoteComprobante]:
        """Verifica que todos los lotes seleccionados sigan compactables."""
        lotes: list[LoteComprobante] = []
        for lote_id in lote_ids:
            lote = await self._lote_resumen(lote_id)
            if lote is None:
                raise AlmacenamientoError(
                    "Uno o más lotes seleccionados ya no están disponibles"
                )
            if lote.estado not in self.ESTADOS_LOTE_CERRADO:
                raise AlmacenamientoError(
                    f"No se pudo compactar el lote #{lote_id}: solo se pueden compactar lotes cerrados"
                )
            if lote.compactado_at is not None:
                raise AlmacenamientoError(
                    f"No se pudo compactar el lote #{lote_id}: ya fue compactado"
                )
            lotes.append(lote)
        return lotes

    async def _contar_filas_lote(self, lote_id: int) -> int:
        """Cuenta filas persistidas de un lote."""
        result = await self.db.execute(
            select(func.count(LoteComprobanteFila.id)).where(
                LoteComprobanteFila.lote_id == lote_id
            )
        )
        return int(result.scalar_one() or 0)

    async def _resumen_lotes(self) -> dict[str, int]:
        """Calcula totales lógicos de lotes."""
        lotes_result = await self.db.execute(select(func.count(LoteComprobante.id)))
        filas_result = await self.db.execute(select(func.count(LoteComprobanteFila.id)))
        lotes = int(lotes_result.scalar_one() or 0)
        filas_persistidas = int(filas_result.scalar_one() or 0)
        compactables = await self.listar_lotes_compactables()
        filas_recuperables = sum(item["filas_persistidas"] for item in compactables)
        return {
            "lotes": lotes,
            "filas_persistidas": filas_persistidas,
            "bytes_estimados": filas_persistidas * self.BYTES_ESTIMADOS_POR_FILA,
            "bytes_recuperables": filas_recuperables * self.BYTES_ESTIMADOS_POR_FILA,
        }

    async def _resumen_emisores(self) -> list[dict[str, Any]]:
        """Calcula uso lógico por emisor sin exponer datos privados."""
        lotes_subquery = (
            select(
                LoteComprobante.empresa_id.label("empresa_id"),
                func.count(LoteComprobante.id).label("lotes"),
            )
            .group_by(LoteComprobante.empresa_id)
            .subquery()
        )
        filas_subquery = (
            select(
                LoteComprobante.empresa_id.label("empresa_id"),
                func.count(LoteComprobanteFila.id).label("filas"),
            )
            .join(
                LoteComprobanteFila,
                LoteComprobanteFila.lote_id == LoteComprobante.id,
            )
            .group_by(LoteComprobante.empresa_id)
            .subquery()
        )
        comprobantes_subquery = (
            select(
                Comprobante.empresa_id.label("empresa_id"),
                func.count(Comprobante.id).label("comprobantes"),
            )
            .group_by(Comprobante.empresa_id)
            .subquery()
        )
        result = await self.db.execute(
            select(
                Empresa,
                func.coalesce(lotes_subquery.c.lotes, 0),
                func.coalesce(filas_subquery.c.filas, 0),
                func.coalesce(comprobantes_subquery.c.comprobantes, 0),
            )
            .outerjoin(lotes_subquery, lotes_subquery.c.empresa_id == Empresa.id)
            .outerjoin(filas_subquery, filas_subquery.c.empresa_id == Empresa.id)
            .outerjoin(
                comprobantes_subquery,
                comprobantes_subquery.c.empresa_id == Empresa.id,
            )
            .order_by(Empresa.razon_social)
        )
        compactables = await self.listar_lotes_compactables()
        recuperable_por_empresa: dict[int, int] = {}
        for item in compactables:
            recuperable_por_empresa[item["empresa_id"]] = (
                recuperable_por_empresa.get(item["empresa_id"], 0)
                + item["filas_persistidas"]
            )

        emisores = []
        for empresa, lotes, filas, comprobantes in result.all():
            filas_int = int(filas or 0)
            recuperables = recuperable_por_empresa.get(empresa.id, 0)
            emisores.append(
                {
                    "empresa_id": empresa.id,
                    "etiqueta": self._empresa_label(empresa),
                    "lotes": int(lotes or 0),
                    "filas_persistidas": filas_int,
                    "filas_compactables": recuperables,
                    "comprobantes": int(comprobantes or 0),
                    "bytes_estimados": filas_int * self.BYTES_ESTIMADOS_POR_FILA,
                    "bytes_recuperables": recuperables * self.BYTES_ESTIMADOS_POR_FILA,
                }
            )
        return emisores

    async def _database_size_bytes(self) -> int:
        """Obtiene tamaño físico de base cuando el motor lo permite."""
        dialect = self.db.get_bind().dialect.name
        if dialect == "postgresql":
            try:
                result = await self.db.execute(
                    text("select pg_database_size(current_database())")
                )
                return int(result.scalar_one() or 0)
            except Exception:
                return 0
        if dialect == "sqlite":
            return self._sqlite_database_size()
        return 0

    def _sqlite_database_size(self) -> int:
        """Calcula tamaño de la base SQLite cuando existe en filesystem."""
        url = settings.database_url
        if not url.startswith("sqlite"):
            return 0
        raw_path = url.split("///", 1)[-1]
        if raw_path in {":memory:", ""}:
            return 0
        return self._safe_file_size(Path(raw_path))

    async def _certificados_referenciados(self) -> set[Path]:
        """Resuelve archivos de certificados referenciados en base."""
        result = await self.db.execute(
            select(Certificado.archivo_crt, Certificado.archivo_key)
        )
        paths: set[Path] = set()
        for crt, key in result.all():
            for value in (crt, key):
                try:
                    paths.add(Path(resolve_cert_storage_path(value)).resolve())
                except Exception:
                    continue
        return paths

    def _candidates_by_id(
        self,
        candidates: list[StorageFileCandidate],
        ids: list[str],
        categoria: str,
        manifest: dict[str, Any] | None = None,
    ) -> list[StorageFileCandidate]:
        """Resuelve IDs contra candidatos calculados por el servidor."""
        unique_ids = self._unique_strings(ids)
        by_id = {item.id: item for item in candidates}
        missing = [item_id for item_id in unique_ids if item_id not in by_id]
        if missing:
            raise AlmacenamientoError(
                f"Uno o más elementos de {categoria} ya no están disponibles"
            )
        resolved = [by_id[item_id] for item_id in unique_ids]
        if manifest is not None:
            self._validar_identidad_manifest(resolved, categoria, manifest)
        return resolved

    def _validar_identidad_manifest(
        self,
        candidates: list[StorageFileCandidate],
        categoria: str,
        manifest: dict[str, Any],
    ) -> None:
        """Evita borrar archivos que cambiaron después del resguardo ZIP."""
        manifest_items = {
            item.get("id"): item
            for item in manifest.get("items", [])
            if item.get("categoria") == categoria and item.get("id")
        }
        for candidate in candidates:
            saved = manifest_items.get(candidate.id)
            if not saved or not saved.get("sha256"):
                raise AlmacenamientoError(
                    "El resguardo no permite validar la identidad de un archivo seleccionado"
                )
            if candidate.bytes_usados != int(saved.get("bytes") or 0):
                raise AlmacenamientoError(
                    f"El archivo {candidate.nombre} cambió después de crear el ZIP"
                )
            if self._sha256_file(candidate.path) != saved["sha256"]:
                raise AlmacenamientoError(
                    f"El archivo {candidate.nombre} cambió después de crear el ZIP"
                )

    def _unlink_candidate(self, candidate: StorageFileCandidate) -> int:
        """Elimina un archivo candidato ya validado y devuelve sus bytes."""
        bytes_usados = self._safe_file_size(candidate.path)
        if candidate.path.exists():
            candidate.path.unlink()
        return bytes_usados

    def _categoria(
        self,
        clave: str,
        nombre: str,
        bytes_usados: int,
        bytes_recuperables: int,
        items: int,
        descripcion: str,
    ) -> dict[str, Any]:
        """Arma una categoría con estado simple."""
        estado = "correcto"
        if bytes_recuperables > 0:
            estado = "necesita_atencion"
        return {
            "clave": clave,
            "nombre": nombre,
            "bytes_usados": int(bytes_usados or 0),
            "bytes_recuperables": int(bytes_recuperables or 0),
            "items": int(items or 0),
            "estado": estado,
            "descripcion": descripcion,
        }

    def _estado_general(self, total_usado: int, disk: dict[str, int | None]) -> str:
        """Calcula estado general por límite configurado y disco real."""
        ratios: list[float] = []
        if settings.storage_limit_bytes and settings.storage_limit_bytes > 0:
            ratios.append(total_usado / settings.storage_limit_bytes)
        if disk["total"]:
            ratios.append((disk["used"] or 0) / disk["total"])
        if not ratios:
            return "correcto"
        ratio = max(ratios)
        if ratio >= 0.9:
            return "critico"
        if ratio >= 0.75:
            return "necesita_atencion"
        return "correcto"

    def _disk_usage(self) -> dict[str, int | None]:
        """Obtiene uso real de disco para la ruta administrada."""
        path = self._storage_tmp_path(create=False)
        target = path if path.exists() else path.parent
        try:
            usage = shutil.disk_usage(target)
        except OSError:
            return {"total": None, "used": None, "free": None}
        return {"total": usage.total, "used": usage.used, "free": usage.free}

    def _active_log_size(self) -> int:
        """Devuelve el tamaño del log activo configurado."""
        if not settings.log_file:
            return 0
        return self._safe_file_size(Path(settings.log_file))

    def _is_log_antiguo_administrado(self, path: Path, active_log: Path) -> bool:
        """Indica si un archivo pertenece a logs administrados por FactuFlow."""
        return path.name.startswith(f"{active_log.name}.")

    def _storage_tmp_path(self, create: bool) -> Path:
        """Resuelve la carpeta temporal administrada."""
        path = Path(settings.storage_tmp_path).resolve()
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def _exportaciones_path(self, create: bool) -> Path:
        """Resuelve la carpeta de exportaciones temporales."""
        path = self._storage_tmp_path(create=create) / "exportaciones"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def _ensure_inside(self, base: Path, path: Path) -> Path:
        """Verifica que un path quede dentro de la base administrada."""
        base_resolved = base.resolve()
        resolved = path.resolve()
        try:
            resolved.relative_to(base_resolved)
        except ValueError as exc:
            raise AlmacenamientoError("Path fuera del directorio administrado") from exc
        return resolved

    def _directory_size(self, path: Path) -> int:
        """Suma tamaño de archivos dentro de una carpeta conocida."""
        resolved = path.resolve()
        if not resolved.exists():
            return 0
        total = 0
        for child in resolved.rglob("*"):
            if child.is_file():
                total += self._safe_file_size(child)
        return total

    def _safe_file_size(self, path: Path) -> int:
        """Devuelve tamaño de archivo si existe."""
        try:
            return path.resolve().stat().st_size if path.resolve().is_file() else 0
        except OSError:
            return 0

    def _sha256_file(self, path: Path) -> str:
        """Calcula SHA-256 de un archivo local."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _certificado_opaque_id(self, filename: str) -> str:
        """Genera un identificador opaco para archivos de certificado."""
        return hmac.new(
            settings.secret_key.encode("utf-8"),
            f"certificado:{filename}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _registrar_evento(
        self,
        accion: str,
        categoria: str,
        usuario_id: int,
        descripcion: str,
        bytes_afectados: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Registra un evento de sistema con metadata sanitizada."""
        self.db.add(
            EventoSistema(
                accion=accion,
                categoria=categoria,
                estado="exitoso",
                descripcion=descripcion,
                bytes_afectados=bytes_afectados,
                usuario_id=usuario_id,
                metadata_json=metadata or {},
            )
        )

    def _empresa_label(self, empresa: Empresa) -> str:
        """Devuelve una etiqueta de emisor sin CUIT completo."""
        cuit = "".join(filter(str.isdigit, empresa.cuit or ""))
        suffix = cuit[-4:] if len(cuit) >= 4 else "----"
        return f"{empresa.razon_social} (...{suffix})"

    def _unique_ints(self, values: list[Any]) -> list[int]:
        """Normaliza enteros positivos sin duplicados."""
        result: list[int] = []
        seen: set[int] = set()
        for value in values:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                raise AlmacenamientoError("La selección contiene IDs inválidos")
            if parsed <= 0:
                raise AlmacenamientoError("La selección contiene IDs inválidos")
            if parsed not in seen:
                result.append(parsed)
                seen.add(parsed)
        return result

    def _unique_strings(self, values: list[Any]) -> list[str]:
        """Normaliza identificadores de archivo sin permitir paths absolutos."""
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text_value = str(value).strip()
            if (
                not text_value
                or Path(text_value).is_absolute()
                or ".." in Path(text_value).parts
            ):
                raise AlmacenamientoError("La selección contiene archivos inválidos")
            if text_value not in seen:
                result.append(text_value)
                seen.add(text_value)
        return result
