"""Servicios para validación y procesamiento de comprobantes masivos."""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.arca.config import ArcaAmbiente
from app.arca.utils import clean_cuit, validate_cuit
from app.core.config import settings
from app.models.certificado import Certificado
from app.models.empresa import Empresa
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.models.usuario import Usuario
from app.schemas.comprobante import EmitirComprobanteRequest, ItemComprobanteCreate
from app.services.facturacion_service import FacturacionService, ValidationError

logger = logging.getLogger(__name__)


class LoteComprobanteError(Exception):
    """Error funcional durante la validación o emisión del lote."""


class LoteComprobantesService:
    """Servicio de carga y emisión masiva de comprobantes."""

    ESTADOS_TERMINALES = {"completado", "autorizado_parcial", "fallido"}
    ESTADOS_PROCESABLES = {"validado", "en_cola", "procesando"}
    ALICUOTAS_IVA_PERMITIDAS = {
        Decimal("0"),
        Decimal("10.5"),
        Decimal("21"),
        Decimal("27"),
    }

    TEMPLATE_COLUMNS = [
        "comprobante_ref",
        "empresa_cuit",
        "punto_venta_numero",
        "tipo_comprobante",
        "concepto",
        "cliente_tipo_documento",
        "cliente_numero_documento",
        "cliente_razon_social",
        "cliente_condicion_iva",
        "cliente_domicilio",
        "fecha_servicio_desde",
        "fecha_servicio_hasta",
        "fecha_vto_pago",
        "item_codigo",
        "item_descripcion",
        "item_cantidad",
        "item_unidad",
        "item_precio_unitario",
        "item_descuento_porcentaje",
        "item_iva_porcentaje",
        "observaciones",
    ]
    HEADER_FIELDS = [
        "empresa_cuit",
        "punto_venta_numero",
        "tipo_comprobante",
        "concepto",
        "cliente_tipo_documento",
        "cliente_numero_documento",
        "cliente_razon_social",
        "cliente_condicion_iva",
        "cliente_domicilio",
        "fecha_servicio_desde",
        "fecha_servicio_hasta",
        "fecha_vto_pago",
        "observaciones",
    ]
    TIPO_DOCUMENTO_MAP = {
        "CUIT": 80,
        "80": 80,
        "CUIL": 86,
        "86": 86,
        "DNI": 96,
        "96": 96,
        "LE": 89,
        "89": 89,
        "LC": 90,
        "90": 90,
        "PASAPORTE": 94,
        "94": 94,
        "CI": 99,
        "99": 99,
        "CONSUMIDOR FINAL": 99,
    }
    CONDICION_IVA_MAP = {
        "RESPONSABLE INSCRIPTO": "RI",
        "RI": "RI",
        "MONOTRIBUTO": "Monotributo",
        "EXENTO": "Exento",
        "CONSUMIDOR FINAL": "CF",
        "CF": "CF",
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.facturacion_service = FacturacionService(db)

    async def generar_plantilla(self, empresa: Empresa) -> bytes:
        """Genera la plantilla fija de Excel para emisión masiva."""
        workbook = Workbook()
        instrucciones = workbook.active
        instrucciones.title = "Instrucciones"
        instrucciones["A1"] = "Plantilla de emisión masiva FactuFlow"
        instrucciones["A1"].font = Font(bold=True, size=14)
        instrucciones["A3"] = "1. Completá una fila por ítem."
        instrucciones[
            "A4"
        ] = "2. Repetí los datos del comprobante en todas las filas que compartan el mismo comprobante_ref."
        instrucciones[
            "A5"
        ] = "3. El lote debe corresponder a una única empresa. Usá el CUIT activo en la columna empresa_cuit."
        instrucciones[
            "A6"
        ] = "4. Si el comprobante es de servicios, completá las fechas de servicio y vencimiento."
        instrucciones[
            "A7"
        ] = "5. Para consumidor final de bajo importe podés dejar documento, nombre y domicilio vacíos."
        instrucciones[
            "A8"
        ] = "6. Si informás documento, tipos sugeridos: CUIT, DNI, CUIL, Pasaporte."
        instrucciones[
            "A9"
        ] = "7. Condición IVA sugerida: Responsable Inscripto, Monotributo, Exento, Consumidor Final."

        hoja = workbook.create_sheet("Comprobantes")
        hoja.append(self.TEMPLATE_COLUMNS)
        for cell in hoja[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="D9EAF7")

        hoja.append(
            [
                "LOTE-001",
                empresa.cuit,
                1,
                6,
                1,
                "",
                "",
                "",
                "Consumidor Final",
                "",
                "",
                "",
                "",
                "SERV-001",
                "Servicio mensual",
                1,
                "unidad",
                1000,
                0,
                21,
                "Factura generada por lote",
            ]
        )
        hoja.append(
            [
                "LOTE-001",
                empresa.cuit,
                1,
                6,
                1,
                "",
                "",
                "",
                "Consumidor Final",
                "",
                "",
                "",
                "",
                "SERV-002",
                "Soporte adicional",
                2,
                "hora",
                500,
                0,
                21,
                "Factura generada por lote",
            ]
        )

        stream = BytesIO()
        workbook.save(stream)
        return stream.getvalue()

    async def validar_y_registrar_lote(
        self,
        file_bytes: bytes,
        filename: str,
        empresa: Empresa,
        usuario: Usuario,
    ) -> LoteComprobante:
        """Valida un archivo Excel y persiste el lote con su detalle."""
        if not file_bytes:
            raise LoteComprobanteError("El archivo está vacío")

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        await self._validar_idempotencia(empresa.id, file_hash)

        filas_excel = self._leer_excel(file_bytes)
        if len(filas_excel) > settings.batch_max_rows:
            raise LoteComprobanteError(
                f"El archivo supera el máximo permitido de {settings.batch_max_rows} filas"
            )
        self._validar_empresa_del_lote(filas_excel, empresa)

        puntos_venta = await self._obtener_puntos_venta(empresa.id)
        certificado = await self._obtener_certificado_activo(empresa.id)
        if certificado is None:
            raise LoteComprobanteError(
                "No hay un certificado activo para la empresa en el ambiente configurado"
            )
        logger.info(
            "Validando lote '%s' para empresa %s (%s) con %s filas",
            filename,
            empresa.id,
            empresa.cuit,
            len(filas_excel),
        )

        lote = LoteComprobante(
            nombre_archivo=filename,
            archivo_hash=file_hash,
            estado="cargado",
            modo_procesamiento="sincronico",
            procesamiento_async=False,
            total_filas=len(filas_excel),
            empresa_id=empresa.id,
            usuario_id=usuario.id,
            metadata_json={"empresa_cuit": empresa.cuit},
        )
        self.db.add(lote)
        await self.db.flush()

        grupos_por_ref: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
        for fila_excel, row in enumerate(filas_excel, start=2):
            comprobante_ref = str(row["comprobante_ref"]).strip()
            if not comprobante_ref:
                raise LoteComprobanteError(
                    "Todas las filas deben incluir comprobante_ref"
                )
            grupos_por_ref[comprobante_ref].append((fila_excel, row))

        if len(grupos_por_ref) > settings.batch_max_groups:
            raise LoteComprobanteError(
                f"El archivo supera el máximo permitido de {settings.batch_max_groups} comprobantes"
            )

        orden = 0
        for comprobante_ref, row_group in grupos_por_ref.items():
            group_result = self._validar_grupo(
                comprobante_ref=comprobante_ref,
                rows=row_group,
                empresa=empresa,
                puntos_venta=puntos_venta,
            )
            orden += 1
            grupo = LoteComprobanteGrupo(
                lote_id=lote.id,
                comprobante_ref=comprobante_ref,
                orden=orden,
                estado=group_result["estado"],
                tipo_comprobante=group_result.get("tipo_comprobante"),
                punto_venta_numero=group_result.get("punto_venta_numero"),
                cliente_documento=group_result.get("cliente_documento"),
                cliente_razon_social=group_result.get("cliente_razon_social"),
                total_estimado=group_result.get("total_estimado", Decimal("0")),
                payload_json=group_result.get("payload"),
                mensajes_json=group_result["mensajes"],
            )
            self.db.add(grupo)
            await self.db.flush()

            for fila_excel, row in row_group:
                fila = LoteComprobanteFila(
                    lote_id=lote.id,
                    grupo_id=grupo.id,
                    fila_excel=fila_excel,
                    comprobante_ref=comprobante_ref,
                    estado=grupo.estado,
                    datos_json=row,
                    mensajes_json=group_result["mensajes"],
                )
                self.db.add(fila)

        await self.db.flush()
        await self._actualizar_estado_lote(lote)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise LoteComprobanteError(
                "Ese archivo ya fue cargado previamente. Revisá el lote existente antes de volver a subirlo."
            ) from exc
        await self.db.refresh(lote)
        logger.info(
            "Lote %s validado: %s grupos, %s validos, %s con error",
            lote.id,
            lote.total_grupos,
            lote.grupos_validos,
            lote.grupos_con_error,
        )
        return lote

    async def encolar_lote(self, lote_id: int, empresa_id: int) -> LoteComprobante:
        """Deja un lote validado en cola persistente para el worker."""
        lote = await self.obtener_lote(lote_id, empresa_id)
        if lote.estado in self.ESTADOS_TERMINALES:
            return lote
        if lote.grupos_validos == 0:
            raise LoteComprobanteError(
                "El lote no tiene comprobantes válidos para emitir"
            )

        lote.estado = "en_cola"
        lote.procesamiento_async = True
        lote.modo_procesamiento = "background"
        lote.mensaje_resumen = (
            "El lote quedó en cola para procesamiento en segundo plano."
        )
        await self.db.commit()
        await self.db.refresh(lote)
        return lote

    async def listar_lotes(
        self, empresa_id: int, limit: int = 20
    ) -> list[LoteComprobante]:
        """Lista lotes recientes de una empresa."""
        result = await self.db.execute(
            select(LoteComprobante)
            .where(LoteComprobante.empresa_id == empresa_id)
            .order_by(LoteComprobante.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def obtener_lote(self, lote_id: int, empresa_id: int) -> LoteComprobante:
        """Obtiene un lote con grupos y filas."""
        result = await self.db.execute(
            select(LoteComprobante)
            .options(
                selectinload(LoteComprobante.grupos),
                selectinload(LoteComprobante.filas),
            )
            .where(
                LoteComprobante.id == lote_id,
                LoteComprobante.empresa_id == empresa_id,
            )
        )
        lote = result.scalar_one_or_none()
        if lote is None:
            raise LoteComprobanteError("No se encontró el lote solicitado")
        return lote

    async def procesar_lote(
        self, lote_id: int, empresa_id: int, reanudar: bool = False
    ) -> LoteComprobante:
        """Procesa un lote válido, en forma sincrónica o desde background."""
        lote = await self.obtener_lote(lote_id, empresa_id)

        if lote.estado == "procesando" and not reanudar:
            return lote
        if lote.estado in self.ESTADOS_TERMINALES:
            return lote
        if lote.estado not in self.ESTADOS_PROCESABLES:
            raise LoteComprobanteError(
                "El lote debe estar validado o en cola antes de emitir"
            )

        lote.procesamiento_async = lote.total_grupos > settings.batch_sync_limit
        lote.modo_procesamiento = (
            "background" if lote.procesamiento_async else "sincronico"
        )
        lote.estado = "procesando"
        lote.started_at = datetime.utcnow()
        await self.db.commit()
        logger.info(
            "Procesando lote %s de empresa %s en modo %s",
            lote.id,
            empresa_id,
            lote.modo_procesamiento,
        )

        grupos = await self._obtener_grupos_emitibles(lote_id)
        for grupo in grupos:
            try:
                payload = grupo.payload_json or {}
                request = EmitirComprobanteRequest.model_validate(payload)
                resultado = await self.facturacion_service.emitir_comprobante(request)
                if resultado.exito:
                    grupo.estado = "autorizado"
                    grupo.cae = resultado.cae
                    grupo.numero_asignado = resultado.numero
                    grupo.comprobante_id = resultado.comprobante_id
                    grupo.mensajes_json = [
                        resultado.mensaje,
                        f"CAE {resultado.cae}",
                    ]
                    await self._marcar_filas(grupo, "autorizado", grupo.mensajes_json)
                else:
                    grupo.estado = "fallido"
                    grupo.mensajes_json = resultado.errores or [resultado.mensaje]
                    await self._marcar_filas(grupo, "fallido", grupo.mensajes_json)
            except Exception as exc:  # pragma: no cover - fallback defensivo
                logger.exception("Error procesando grupo %s", grupo.comprobante_ref)
                grupo.estado = "fallido"
                grupo.mensajes_json = [str(exc)]
                await self._marcar_filas(grupo, "fallido", grupo.mensajes_json)

            await self.db.commit()

        lote = await self.obtener_lote(lote_id, empresa_id)
        lote.finished_at = datetime.utcnow()
        lote.estado = "cargado"
        await self._actualizar_estado_lote(lote)
        await self.db.commit()
        await self.db.refresh(lote)
        logger.info(
            "Lote %s finalizado con estado %s: emitidos=%s fallidos=%s",
            lote.id,
            lote.estado,
            lote.grupos_emitidos,
            lote.grupos_fallidos,
        )
        return lote

    async def generar_archivo_observado(self, lote_id: int, empresa_id: int) -> bytes:
        """Genera un archivo observado con resultados por fila."""
        lote = await self.obtener_lote(lote_id, empresa_id)
        filas_por_numero = {fila.fila_excel: fila for fila in lote.filas}
        workbook = Workbook()
        hoja = workbook.active
        hoja.title = "Resultados"
        salida_headers = self.TEMPLATE_COLUMNS + [
            "resultado_estado",
            "resultado_mensajes",
        ]
        hoja.append(salida_headers)
        for cell in hoja[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="D9EAF7")

        for fila_numero in sorted(filas_por_numero):
            fila = filas_por_numero[fila_numero]
            row = [fila.datos_json.get(col) for col in self.TEMPLATE_COLUMNS]
            row.extend([fila.estado, " | ".join(fila.mensajes_json or [])])
            hoja.append(row)
            fill_color = "E2F0D9" if fila.estado == "autorizado" else "FDE9D9"
            for cell in hoja[hoja.max_row]:
                cell.fill = PatternFill("solid", fgColor=fill_color)

        stream = BytesIO()
        workbook.save(stream)
        return stream.getvalue()

    def _leer_excel(self, file_bytes: bytes) -> list[dict[str, Any]]:
        """Lee y normaliza las filas del Excel."""
        workbook = load_workbook(BytesIO(file_bytes), data_only=True)
        sheet = (
            workbook["Comprobantes"]
            if "Comprobantes" in workbook.sheetnames
            else workbook.active
        )
        headers = [self._normalize_header(cell.value) for cell in sheet[1]]

        missing = [col for col in self.TEMPLATE_COLUMNS if col not in headers]
        if missing:
            raise LoteComprobanteError(
                f"Faltan columnas obligatorias en la plantilla: {', '.join(missing)}"
            )

        filas: list[dict[str, Any]] = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if all(cell in (None, "") for cell in row):
                continue
            row_dict = {
                headers[idx]: self._normalize_cell_value(value)
                for idx, value in enumerate(row)
                if idx < len(headers) and headers[idx]
            }
            filas.append(row_dict)

        if not filas:
            raise LoteComprobanteError("La plantilla no contiene filas para procesar")
        return filas

    def _validar_empresa_del_lote(
        self, filas_excel: list[dict[str, Any]], empresa: Empresa
    ) -> None:
        """Verifica que todo el lote pertenezca a la empresa activa."""
        cuit_esperado = clean_cuit(empresa.cuit)
        cuit_detectados = {
            clean_cuit(row.get("empresa_cuit", ""))
            for row in filas_excel
            if clean_cuit(row.get("empresa_cuit", ""))
        }

        if cuit_detectados != {cuit_esperado}:
            raise LoteComprobanteError(
                "El archivo mezcla empresas o no coincide con la empresa activa. Revisa la columna empresa_cuit y vuelve a subir el lote."
            )

    async def _validar_idempotencia(self, empresa_id: int, archivo_hash: str) -> None:
        """Evita crear el mismo lote más de una vez de forma accidental."""
        result = await self.db.execute(
            select(LoteComprobante).where(
                LoteComprobante.empresa_id == empresa_id,
                LoteComprobante.archivo_hash == archivo_hash,
            )
        )
        lote_existente = result.scalar_one_or_none()
        if lote_existente is not None:
            raise LoteComprobanteError(
                "Ese archivo ya fue cargado previamente. Revisá el lote existente antes de volver a subirlo."
            )

    async def _obtener_puntos_venta(self, empresa_id: int) -> dict[int, PuntoVenta]:
        """Obtiene los puntos de venta activos de la empresa indexados por número."""
        result = await self.db.execute(
            select(PuntoVenta).where(
                PuntoVenta.empresa_id == empresa_id,
                PuntoVenta.activo.is_(True),
                PuntoVenta.es_webservice.is_(True),
                PuntoVenta.bloqueado.is_(False),
                PuntoVenta.fecha_baja.is_(None),
            )
        )
        puntos = result.scalars().all()
        return {punto.numero: punto for punto in puntos}

    async def _obtener_certificado_activo(self, empresa_id: int) -> Certificado | None:
        """Obtiene el certificado activo para el ambiente actual."""
        ambiente = (
            ArcaAmbiente.PRODUCCION.value
            if settings.arca_env.lower() == ArcaAmbiente.PRODUCCION.value
            else ArcaAmbiente.HOMOLOGACION.value
        )
        result = await self.db.execute(
            select(Certificado).where(
                Certificado.empresa_id == empresa_id,
                Certificado.activo.is_(True),
                Certificado.ambiente == ambiente,
            )
        )
        return result.scalar_one_or_none()

    def _validar_grupo(
        self,
        comprobante_ref: str,
        rows: list[tuple[int, dict[str, Any]]],
        empresa: Empresa,
        puntos_venta: dict[int, PuntoVenta],
    ) -> dict[str, Any]:
        """Valida un grupo de filas que forman un comprobante."""
        mensajes: list[str] = []
        header = rows[0][1]

        for _, row in rows[1:]:
            for field in self.HEADER_FIELDS:
                if (
                    str(row.get(field, "")).strip()
                    != str(header.get(field, "")).strip()
                ):
                    mensajes.append(
                        f"El campo {field} no coincide en todas las filas del comprobante {comprobante_ref}"
                    )
                    break

        empresa_cuit = clean_cuit(header.get("empresa_cuit", ""))
        if empresa_cuit != empresa.cuit:
            mensajes.append(
                f"El comprobante {comprobante_ref} no pertenece a la empresa activa ({empresa.cuit})"
            )

        punto_venta_numero = self._parse_int(header.get("punto_venta_numero"))
        if punto_venta_numero is None or punto_venta_numero not in puntos_venta:
            mensajes.append(
                f"El punto de venta del comprobante {comprobante_ref} no existe o no está activo"
            )

        tipo_comprobante = self._parse_int(header.get("tipo_comprobante"))
        if tipo_comprobante not in {1, 2, 3, 6, 7, 8, 11, 12, 13}:
            mensajes.append(
                f"El tipo de comprobante del grupo {comprobante_ref} no está soportado"
            )

        concepto = self._parse_int(header.get("concepto"))
        if concepto not in {1, 2, 3}:
            mensajes.append(
                f"El concepto del comprobante {comprobante_ref} debe ser 1, 2 o 3"
            )

        tipo_documento = self._parse_tipo_documento(
            header.get("cliente_tipo_documento")
        )
        numero_documento = clean_cuit(header.get("cliente_numero_documento", ""))
        condicion_iva = self._parse_condicion_iva(header.get("cliente_condicion_iva"))

        fecha_servicio_desde = self._parse_date(header.get("fecha_servicio_desde"))
        fecha_servicio_hasta = self._parse_date(header.get("fecha_servicio_hasta"))
        fecha_vto_pago = self._parse_date(header.get("fecha_vto_pago"))
        if concepto in {2, 3}:
            if (
                not fecha_servicio_desde
                or not fecha_servicio_hasta
                or not fecha_vto_pago
            ):
                mensajes.append(
                    f"El comprobante {comprobante_ref} requiere fechas de servicio y vencimiento"
                )

        items: list[ItemComprobanteCreate] = []
        for index, (_, row) in enumerate(rows):
            descripcion = str(row.get("item_descripcion", "")).strip()
            if not descripcion:
                mensajes.append(
                    f"Todas las filas del comprobante {comprobante_ref} deben informar item_descripcion"
                )
                continue

            cantidad = self._parse_decimal(row.get("item_cantidad"))
            precio_unitario = self._parse_decimal(row.get("item_precio_unitario"))
            descuento = self._parse_decimal(
                row.get("item_descuento_porcentaje"), Decimal("0")
            )
            iva = self._parse_decimal(row.get("item_iva_porcentaje"), Decimal("0"))
            if cantidad is None or cantidad <= 0:
                mensajes.append(
                    f"La cantidad del ítem '{descripcion}' en {comprobante_ref} debe ser mayor a cero"
                )
                continue
            if precio_unitario is None or precio_unitario < 0:
                mensajes.append(
                    f"El precio unitario del ítem '{descripcion}' en {comprobante_ref} es inválido"
                )
                continue
            if iva is None or iva not in self.ALICUOTAS_IVA_PERMITIDAS:
                mensajes.append(
                    f"La alícuota de IVA del ítem '{descripcion}' en {comprobante_ref} debe ser 0, 10.5, 21 o 27"
                )
                continue

            items.append(
                ItemComprobanteCreate(
                    codigo=str(row.get("item_codigo", "")).strip() or None,
                    descripcion=descripcion,
                    cantidad=cantidad,
                    unidad=str(row.get("item_unidad", "")).strip() or "unidad",
                    precio_unitario=precio_unitario,
                    descuento_porcentaje=descuento or Decimal("0"),
                    iva_porcentaje=iva or Decimal("0"),
                    orden=index,
                )
            )

        if not items:
            mensajes.append(f"El comprobante {comprobante_ref} no tiene ítems válidos")

        if tipo_documento is None:
            tipo_documento_raw = str(header.get("cliente_tipo_documento", "")).strip()
            if not tipo_documento_raw and not numero_documento:
                tipo_documento = 99
            else:
                mensajes.append(
                    f"El tipo de documento del receptor en {comprobante_ref} es inválido"
                )

        if (
            tipo_documento == 80
            and numero_documento
            and not validate_cuit(numero_documento)
        ):
            mensajes.append(f"El CUIT del receptor en {comprobante_ref} no es válido")

        if tipo_comprobante in {1, 2, 3} and tipo_documento != 80:
            mensajes.append(
                f"Los comprobantes tipo A requieren que el receptor tenga CUIT en {comprobante_ref}"
            )

        if condicion_iva is None:
            condicion_raw = str(header.get("cliente_condicion_iva", "")).strip()
            if not condicion_raw and tipo_documento == 99:
                condicion_iva = "CF"
            else:
                mensajes.append(
                    f"La condición IVA del receptor en {comprobante_ref} no es válida"
                )

        payload: EmitirComprobanteRequest | None = None
        if not mensajes:
            try:
                payload = self.facturacion_service.normalizar_receptor(
                    EmitirComprobanteRequest(
                        empresa_id=empresa.id,
                        punto_venta_id=puntos_venta[punto_venta_numero].id,
                        tipo_comprobante=tipo_comprobante,
                        concepto=concepto,
                        tipo_documento=tipo_documento,
                        numero_documento=numero_documento,
                        razon_social=str(
                            header.get("cliente_razon_social", "")
                        ).strip(),
                        condicion_iva=condicion_iva,
                        domicilio=str(header.get("cliente_domicilio", "")).strip()
                        or None,
                        fecha_servicio_desde=fecha_servicio_desde,
                        fecha_servicio_hasta=fecha_servicio_hasta,
                        fecha_vto_pago=fecha_vto_pago,
                        observaciones=str(header.get("observaciones", "")).strip()
                        or None,
                        moneda="PES",
                        cotizacion=Decimal("1"),
                        guardar_cliente=False,
                        items=items,
                    )
                )
            except ValidationError as exc:
                mensajes.append(f"{comprobante_ref}: {exc}")

        if mensajes:
            return {
                "estado": "con_error",
                "mensajes": sorted(set(mensajes)),
                "tipo_comprobante": tipo_comprobante,
                "punto_venta_numero": punto_venta_numero,
                "cliente_documento": numero_documento,
                "cliente_razon_social": header.get("cliente_razon_social", ""),
                "total_estimado": Decimal("0"),
            }

        assert payload is not None
        totales = self.facturacion_service._calcular_totales(items)
        return {
            "estado": "validado",
            "mensajes": ["Validado correctamente. Listo para emitir."],
            "payload": payload.model_dump(mode="json"),
            "tipo_comprobante": tipo_comprobante,
            "punto_venta_numero": punto_venta_numero,
            "cliente_documento": payload.numero_documento,
            "cliente_razon_social": payload.razon_social,
            "total_estimado": totales["total"],
        }

    async def _actualizar_estado_lote(self, lote: LoteComprobante) -> None:
        """Recalcula contadores y estado del lote."""
        grupos = await self._obtener_grupos_lote(lote.id)
        lote.total_grupos = len(grupos)
        lote.grupos_validos = len([g for g in grupos if g.estado == "validado"])
        lote.grupos_con_error = len([g for g in grupos if g.estado == "con_error"])
        lote.grupos_emitidos = len([g for g in grupos if g.estado == "autorizado"])
        lote.grupos_fallidos = len([g for g in grupos if g.estado == "fallido"])

        if lote.estado == "procesando":
            lote.mensaje_resumen = "Procesando comprobantes..."
            return
        if lote.estado == "en_cola":
            lote.mensaje_resumen = "El lote está en cola para procesamiento."
            return

        if lote.grupos_emitidos and (lote.grupos_fallidos or lote.grupos_con_error):
            lote.estado = "autorizado_parcial"
            lote.mensaje_resumen = "El lote se procesó parcialmente. Revisá los comprobantes fallidos o con error."
        elif lote.grupos_emitidos == lote.total_grupos and lote.total_grupos > 0:
            lote.estado = "completado"
            lote.mensaje_resumen = "Todos los comprobantes del lote fueron emitidos."
        elif lote.grupos_con_error:
            lote.estado = "con_errores"
            lote.mensaje_resumen = (
                "El lote tiene comprobantes con errores de validación."
            )
        elif lote.grupos_validos:
            lote.estado = "validado"
            lote.mensaje_resumen = "El lote se validó correctamente y puede emitirse."
        elif lote.grupos_fallidos:
            lote.estado = "fallido"
            lote.mensaje_resumen = "No se pudo emitir ningún comprobante del lote."
        else:
            lote.estado = "cargado"
            lote.mensaje_resumen = "El lote fue cargado."

    async def _obtener_grupos_lote(self, lote_id: int) -> list[LoteComprobanteGrupo]:
        result = await self.db.execute(
            select(LoteComprobanteGrupo)
            .options(selectinload(LoteComprobanteGrupo.filas))
            .where(LoteComprobanteGrupo.lote_id == lote_id)
            .order_by(LoteComprobanteGrupo.orden)
        )
        return list(result.scalars().all())

    async def _obtener_grupos_emitibles(
        self, lote_id: int
    ) -> list[LoteComprobanteGrupo]:
        result = await self.db.execute(
            select(LoteComprobanteGrupo)
            .options(selectinload(LoteComprobanteGrupo.filas))
            .where(
                LoteComprobanteGrupo.lote_id == lote_id,
                LoteComprobanteGrupo.estado == "validado",
            )
            .order_by(LoteComprobanteGrupo.orden)
        )
        return list(result.scalars().all())

    async def _marcar_filas(
        self, grupo: LoteComprobanteGrupo, estado: str, mensajes: list[str]
    ) -> None:
        for fila in grupo.filas:
            fila.estado = estado
            fila.mensajes_json = mensajes

    def _normalize_header(self, value: Any) -> str:
        return str(value or "").strip().lower()

    def _normalize_cell_value(self, value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    def _parse_int(self, value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_decimal(
        self, value: Any, default: Decimal | None = None
    ) -> Decimal | None:
        if value in (None, ""):
            return default
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _parse_date(self, value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        try:
            return datetime.fromisoformat(str(value)).date()
        except ValueError:
            return None

    def _parse_tipo_documento(self, value: Any) -> int | None:
        normalized = str(value or "").strip().upper()
        return self.TIPO_DOCUMENTO_MAP.get(normalized)

    def _parse_condicion_iva(self, value: Any) -> str | None:
        normalized = str(value or "").strip().upper()
        return self.CONDICION_IVA_MAP.get(normalized)
