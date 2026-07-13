"""Servicio de Facturación - Emisión de Comprobantes."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import desc, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.arca.config import ArcaAmbiente
from app.arca.exceptions import ArcaServiceError, ArcaValidationError
from app.arca.models import CbteAsocItem, ComprobanteRequest, IvaItem
from app.arca.utils import clean_cuit, validate_cuit
from app.arca.wsaa import WSAAClient
from app.arca.wsfev1 import WSFEv1Client
from app.core.config import settings
from app.core.database import DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS
from app.models.certificado import Certificado
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.services.certificados_service import requerir_material_certificado
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.schemas.comprobante import (
    EmitirComprobanteRequest,
    EmitirComprobanteResponse,
    ItemComprobanteCreate,
)

logger = logging.getLogger(__name__)

ERROR_INTERNO_EMISION_PUBLICO = (
    "No se pudo completar la operación. "
    "El detalle técnico quedó registrado en logs privados."
)


@dataclass
class FaseSolicitudArca:
    """Registra de forma monotónica si la operación ya invocó FECAESolicitar."""

    iniciada: bool = False
    recuperacion_pre_arca_exitosa: bool | None = None

    def marcar_iniciada(self) -> None:
        """Marca el cruce irreversible hacia la solicitud fiscal."""
        self.iniciada = True

    def registrar_recuperacion_pre_arca(self, exitosa: bool) -> None:
        """Registra el resultado interno de una recuperación anterior a ARCA."""
        self.recuperacion_pre_arca_exitosa = exitosa


class ValidationError(Exception):
    """Error de validación de datos."""

    pass


class ReconciliacionNumeracionError(ValidationError):
    """Error cuando ARCA registra comprobantes ausentes en FactuFlow."""

    def __init__(
        self,
        ultimo_local: int,
        ultimo_arca: int,
        proximo_local: int,
        proximo_arca: int,
    ) -> None:
        """Inicializa el detalle del desfase de numeración."""
        self.ultimo_local = ultimo_local
        self.ultimo_arca = ultimo_arca
        self.proximo_local = proximo_local
        self.proximo_arca = proximo_arca
        super().__init__(
            "ARCA registra comprobantes autorizados que no existen en FactuFlow. "
            "Reconciliá la numeración antes de emitir nuevos comprobantes."
        )


class FacturacionService:
    """Servicio para emisión de comprobantes electrónicos."""

    _number_locks: dict[tuple[int, int, int], asyncio.Lock] = {}
    _number_locks_guard = asyncio.Lock()
    CONSUMIDOR_FINAL_IDENTIFICACION_MINIMA = Decimal("10000000")
    TIPOS_COMPROBANTE_C = {11, 12, 13}
    TIPOS_COMPROBANTE_FCE_MIPYME = {
        201,
        202,
        203,
        206,
        207,
        208,
        211,
        212,
        213,
    }

    TIPO_DOCUMENTO_CODIGO_A_NOMBRE = {
        80: "CUIT",
        86: "CUIL",
        96: "DNI",
        89: "LE",
        90: "LC",
        94: "Pasaporte",
        99: "CI",
    }
    CONDICION_IVA_MAP = {
        "Responsable Inscripto": "RI",
        "RI": "RI",
        "Monotributo": "Monotributo",
        "Exento": "Exento",
        "Consumidor Final": "CF",
        "CF": "CF",
        "Responsable No Inscripto": "RI",
    }
    CONDICION_IVA_RECEPTOR_ID_MAP = {
        "RI": 1,
        "Monotributo": 6,
        "Exento": 4,
        "CF": 5,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def emitir_comprobante(
        self,
        request: EmitirComprobanteRequest,
        commit: bool = True,
        operacion_id: int | None = None,
        usuario_id: int | None = None,
        lote_id: int | None = None,
        grupo_id: int | None = None,
        fase_solicitud_arca: FaseSolicitudArca | None = None,
    ) -> EmitirComprobanteResponse:
        """Serializa la emisión por empresa, punto de venta y tipo."""
        lock = await self._get_number_lock(
            request.empresa_id, request.punto_venta_id, request.tipo_comprobante
        )
        async with lock:
            return await self._emitir_comprobante_locked(
                request,
                commit=commit,
                operacion_id=operacion_id,
                usuario_id=usuario_id,
                lote_id=lote_id,
                grupo_id=grupo_id,
                fase_solicitud_arca=fase_solicitud_arca,
            )

    async def emitir_comprobantes_lote(
        self,
        requests: list[EmitirComprobanteRequest],
        max_registros: int | None = None,
        contextos: list[dict[str, int | None]] | None = None,
        fase_solicitud_arca: FaseSolicitudArca | None = None,
    ) -> list[EmitirComprobanteResponse]:
        """Emite un sublote homogéneo de comprobantes en un request ARCA."""
        if not requests:
            return []

        lock = await self._get_number_lock(
            requests[0].empresa_id,
            requests[0].punto_venta_id,
            requests[0].tipo_comprobante,
        )
        async with lock:
            return await self._emitir_comprobantes_lote_locked(
                requests,
                max_registros=max_registros,
                contextos=contextos,
                fase_solicitud_arca=fase_solicitud_arca,
            )

    async def obtener_registros_maximos_por_request(self, empresa_id: int) -> int:
        """Consulta en ARCA el máximo de comprobantes permitido por request."""
        empresa = await self._obtener_empresa(empresa_id)
        if not empresa:
            raise ValidationError("Empresa no encontrada")

        certificado = await self._obtener_certificado_activo(empresa_id)
        ticket = await self._obtener_ticket_acceso(empresa, certificado)
        wsfe_client = WSFEv1Client(
            ambiente=self._get_arca_ambiente(),
            ticket=ticket,
            cuit=empresa.cuit,
        )
        return await wsfe_client.fe_comp_tot_x_request()

    async def verificar_numeracion_alineada_para_emision(
        self,
        *,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
    ) -> dict[str, int]:
        """Verifica contra ARCA que la próxima numeración local sea segura."""
        empresa = await self._obtener_empresa(empresa_id)
        if not empresa:
            raise ValidationError("Empresa no encontrada")

        punto_venta = await self._obtener_punto_venta(punto_venta_id, empresa_id)
        if punto_venta is None:
            raise ValidationError("Punto de venta no encontrado para la empresa activa")

        certificado = await self._obtener_certificado_activo(empresa_id)
        ticket = await self._obtener_ticket_acceso(empresa, certificado)
        wsfe_client = WSFEv1Client(
            ambiente=self._get_arca_ambiente(),
            ticket=ticket,
            cuit=empresa.cuit,
        )
        await self._validar_punto_venta_habilitado(wsfe_client, punto_venta.numero)
        proximo_numero = await self._obtener_proximo_numero(
            empresa_id,
            punto_venta_id,
            tipo_comprobante,
            wsfe_client=wsfe_client,
            punto_venta_numero=punto_venta.numero,
        )
        return {
            "empresa_id": empresa_id,
            "punto_venta_id": punto_venta_id,
            "punto_venta_numero": punto_venta.numero,
            "tipo_comprobante": tipo_comprobante,
            "proximo_numero": proximo_numero,
        }

    async def resolver_operacion_idempotente_incompleta(
        self,
        operacion_id: int,
    ) -> EmitirComprobanteResponse | None:
        """Resuelve una operación sin respuesta antes de permitir un retry."""
        result = await self.db.execute(
            select(IntentoEmisionFiscal)
            .where(IntentoEmisionFiscal.operacion_id == operacion_id)
            .order_by(IntentoEmisionFiscal.id)
        )
        intentos = list(result.scalars().all())
        if not intentos:
            operacion = await self.db.get(OperacionIdempotente, operacion_id)
            stale_before = datetime.utcnow() - timedelta(
                minutes=settings.fiscal_attempt_stale_minutes
            )
            if operacion is not None and operacion.created_at < stale_before:
                return None
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=0,
                punto_venta=0,
                numero=0,
                fecha=date(1970, 1, 1),
                total=Decimal("0"),
                mensaje="La operación fiscal ya está en proceso.",
                errores=[
                    "Esperá el resultado o revisá el estado antes de volver a solicitar CAE."
                ],
                categoria_error="idempotencia_en_proceso",
            )

        intento = intentos[0]
        respuesta = await self._respuesta_desde_intento_resuelto(intento)
        if respuesta is not None:
            return respuesta

        if intento.estado != "en_proceso":
            return self._respuesta_intento_requiere_reconciliacion(intento)

        stale_before = datetime.utcnow() - timedelta(
            minutes=settings.fiscal_attempt_stale_minutes
        )
        if intento.created_at >= stale_before:
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=intento.tipo_comprobante,
                punto_venta=intento.punto_venta_numero,
                numero=intento.numero_planificado or 0,
                fecha=intento.fecha_emision,
                total=Decimal(str(intento.total)),
                mensaje="La operación fiscal ya está en proceso.",
                errores=[
                    "Esperá el resultado o revisá el estado antes de volver a solicitar CAE."
                ],
                categoria_error="idempotencia_en_proceso",
            )

        empresa = await self._obtener_empresa(intento.empresa_id)
        if empresa is None:
            return self._respuesta_intento_requiere_reconciliacion(intento)
        certificado = await self._obtener_certificado_activo(intento.empresa_id)
        ticket = await self._obtener_ticket_acceso(empresa, certificado)
        wsfe_client = WSFEv1Client(
            ambiente=self._get_arca_ambiente(),
            ticket=ticket,
            cuit=empresa.cuit,
        )
        reconciliado = await self._reconciliar_intento_stale(
            intento=intento,
            wsfe_client=wsfe_client,
            punto_venta_numero=intento.punto_venta_numero,
        )
        await self.db.refresh(intento)

        if intento.estado == "fallido_verificado":
            return None
        respuesta = await self._respuesta_desde_intento_resuelto(intento)
        if respuesta is not None:
            return respuesta
        if reconciliado is not None or intento.estado == "requiere_reconciliacion":
            return self._respuesta_intento_requiere_reconciliacion(intento)
        return None

    async def _emitir_comprobantes_lote_locked(
        self,
        requests: list[EmitirComprobanteRequest],
        max_registros: int | None = None,
        contextos: list[dict[str, int | None]] | None = None,
        fase_solicitud_arca: FaseSolicitudArca | None = None,
    ) -> list[EmitirComprobanteResponse]:
        """Ejecuta la emisión batch asumiendo que el lock local ya fue tomado."""
        fase_solicitud_arca = fase_solicitud_arca or FaseSolicitudArca()
        arca_iniciada_en_esta_llamada = False
        try:
            requests = [self.normalizar_receptor(request) for request in requests]
            self._validar_lote_homogeneo(requests, max_registros=max_registros)
            contextos = contextos or [{} for _ in requests]
            if len(contextos) != len(requests):
                contextos = [{} for _ in requests]

            for request in requests:
                await self._validar_datos(request)

            primer_request = requests[0]
            await self._tomar_lock_numeracion(
                primer_request.empresa_id,
                primer_request.punto_venta_id,
                primer_request.tipo_comprobante,
            )

            totales_por_request = [
                self._calcular_totales(request.items) for request in requests
            ]
            empresa = await self._obtener_empresa(primer_request.empresa_id)
            punto_venta = await self._obtener_punto_venta(
                primer_request.punto_venta_id,
                primer_request.empresa_id,
            )
            certificado = await self._obtener_certificado_activo(
                primer_request.empresa_id
            )
            punto_venta_numero = punto_venta.numero

            ticket = await self._obtener_ticket_acceso(empresa, certificado)
            wsfe_client = WSFEv1Client(
                ambiente=self._get_arca_ambiente(),
                ticket=ticket,
                cuit=empresa.cuit,
            )
            await self._validar_punto_venta_habilitado(
                wsfe_client,
                punto_venta_numero,
            )
            try:
                proximo = await self._obtener_proximo_numero(
                    primer_request.empresa_id,
                    primer_request.punto_venta_id,
                    primer_request.tipo_comprobante,
                    wsfe_client,
                    punto_venta_numero,
                )
            except ReconciliacionNumeracionError as exc:
                return [
                    self._respuesta_numeracion_arca_adelantada(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=exc.ultimo_arca,
                        totales=totales,
                        exc=exc,
                    )
                    for request, totales in zip(requests, totales_por_request)
                ]

            idempotencia = IdempotenciaFiscalService(self.db)
            intentos: list[IntentoEmisionFiscal | None] = []
            intento_ids: list[int] = []
            try:
                for index, (request, totales, contexto) in enumerate(
                    zip(requests, totales_por_request, contextos)
                ):
                    intento = await idempotencia.crear_intento_emision(
                        request=request,
                        punto_venta=punto_venta,
                        numero_planificado=proximo + index,
                        total=totales["total"],
                        operacion_id=contexto.get("operacion_id"),
                        usuario_id=contexto.get("usuario_id"),
                        lote_id=contexto.get("lote_id"),
                        grupo_id=contexto.get("grupo_id"),
                    )
                    intentos.append(intento)
                    if intento.id is not None:
                        intento_ids.append(intento.id)
                arca_requests = [
                    self._armar_request_arca(
                        request,
                        proximo + index,
                        totales,
                        punto_venta_numero,
                    )
                    for index, (request, totales) in enumerate(
                        zip(requests, totales_por_request)
                    )
                ]
            except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
                await self._rollback_seguro("reservas_batch_pre_arca")
                raise
            except Exception:
                logger.exception(
                    "Fallo preparando reservas fiscales del sublote antes de ARCA"
                )
                await self._rollback_seguro("reservas_batch_pre_arca_fallidas")
                await self._marcar_intentos_batch_pre_arca_fallidos(
                    intento_ids,
                    ERROR_INTERNO_EMISION_PUBLICO,
                )
                return [
                    self._respuesta_batch_reserva_pre_arca_fallida(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=proximo + index,
                        totales=totales,
                        error=ERROR_INTERNO_EMISION_PUBLICO,
                    )
                    for index, (request, totales) in enumerate(
                        zip(requests, totales_por_request)
                    )
                ]

            resultados_arca = []
            try:
                fase_solicitud_arca.marcar_iniciada()
                arca_iniciada_en_esta_llamada = True
                resultados_arca_sin_ordenar = await wsfe_client.fe_cae_solicitar_lote(
                    arca_requests
                )
                resultados_arca = self._ordenar_resultados_arca_batch_por_numero(
                    arca_requests,
                    resultados_arca_sin_ordenar,
                )
            except (ArcaServiceError, ArcaValidationError) as exc:
                logger.error("Error al solicitar CAE por sublote: %s", str(exc))
                respuestas_inciertas = [
                    self._respuesta_batch_sin_detalle_requiere_reconciliacion(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=arca_request.cbte_desde,
                        totales=totales,
                        error=str(exc),
                    )
                    for request, arca_request, totales in zip(
                        requests,
                        arca_requests,
                        totales_por_request,
                    )
                ]
                for intento, respuesta in zip(intentos, respuestas_inciertas):
                    await self._actualizar_intento_batch_preservando_respuesta(
                        idempotencia,
                        intento,
                        respuesta,
                        contexto="respuesta_incierta_arca",
                    )
                return respuestas_inciertas

            respuestas: list[EmitirComprobanteResponse] = []
            persistencia_bloqueada = False
            for request, arca_request, totales, resultado, intento in zip(
                requests,
                arca_requests,
                totales_por_request,
                resultados_arca,
                intentos,
            ):
                respuesta_no_aprobada = self._respuesta_si_arca_no_autorizo(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    numero=arca_request.cbte_desde,
                    totales=totales,
                    resultado_arca=resultado,
                )
                if respuesta_no_aprobada is not None:
                    intento_actualizado = (
                        await self._actualizar_intento_batch_preservando_respuesta(
                            idempotencia,
                            intento,
                            respuesta_no_aprobada,
                            contexto="arca_no_aprobado",
                        )
                    )
                    if not intento_actualizado:
                        respuesta_no_aprobada = self._respuesta_post_arca_requiere_reconciliacion(
                            request=request,
                            punto_venta_numero=punto_venta_numero,
                            numero=arca_request.cbte_desde,
                            totales=totales,
                            resultado_arca=resultado,
                            mensaje=(
                                "ARCA rechazó el comprobante, pero FactuFlow "
                                "no pudo cerrar el intento fiscal"
                            ),
                            errores=[
                                "No reintentes esta emisión hasta reconciliar el intento fiscal."
                            ],
                        )
                    respuestas.append(respuesta_no_aprobada)
                    continue

                if persistencia_bloqueada:
                    respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=arca_request.cbte_desde,
                        totales=totales,
                        resultado_arca=resultado,
                        mensaje=(
                            "ARCA autorizó el comprobante, pero FactuFlow "
                            "detuvo la persistencia del sublote por una "
                            "reconciliación pendiente"
                        ),
                        errores=[
                            "No reintentes esta emisión hasta consultar ARCA y reconciliar el comprobante localmente."
                        ],
                    )
                    await self._actualizar_intento_batch_preservando_respuesta(
                        idempotencia,
                        intento,
                        respuesta,
                        contexto="persistencia_bloqueada",
                    )
                    respuestas.append(respuesta)
                    continue

                try:
                    comprobante = await self._guardar_comprobante(
                        request,
                        arca_request.cbte_desde,
                        totales,
                        resultado,
                        punto_venta,
                    )
                except IntegrityError as exc:
                    await self._rollback_seguro("integrity_batch_post_arca")
                    persistencia_bloqueada = True
                    logger.exception(
                        "Conflicto de numeración al guardar comprobante batch autorizado. "
                        "empresa=%s pv=%s tipo=%s numero=%s",
                        request.empresa_id,
                        punto_venta_numero,
                        request.tipo_comprobante,
                        arca_request.cbte_desde,
                    )
                    respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=arca_request.cbte_desde,
                        totales=totales,
                        resultado_arca=resultado,
                        mensaje=(
                            "ARCA autorizó el comprobante, pero no se pudo guardar por conflicto de numeración"
                        ),
                        errores=[
                            "No reintentes esta emisión hasta consultar ARCA y reconciliar el comprobante localmente.",
                            str(exc.orig),
                        ],
                    )
                    await self._actualizar_intento_batch_preservando_respuesta(
                        idempotencia,
                        intento,
                        respuesta,
                        contexto="conflicto_numeracion_post_arca",
                    )
                    respuestas.append(respuesta)
                except Exception:
                    await self._rollback_seguro("persistencia_batch_post_arca")
                    persistencia_bloqueada = True
                    logger.exception(
                        "Fallo posterior a CAE autorizado en sublote. empresa=%s pv=%s tipo=%s numero=%s",
                        request.empresa_id,
                        punto_venta_numero,
                        request.tipo_comprobante,
                        arca_request.cbte_desde,
                    )
                    respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=arca_request.cbte_desde,
                        totales=totales,
                        resultado_arca=resultado,
                        mensaje=(
                            "ARCA autorizó el comprobante, pero FactuFlow no pudo guardarlo"
                        ),
                        errores=[
                            "No reintentes esta emisión hasta consultar ARCA y reconciliar el comprobante localmente.",
                            ERROR_INTERNO_EMISION_PUBLICO,
                        ],
                    )
                    await self._actualizar_intento_batch_preservando_respuesta(
                        idempotencia,
                        intento,
                        respuesta,
                        contexto="fallo_persistencia_post_arca",
                    )
                    respuestas.append(respuesta)
                else:
                    logger.info(
                        "Comprobante batch emitido: empresa=%s tipo=%s pv=%s numero=%s cae=%s total=%s",
                        request.empresa_id,
                        request.tipo_comprobante,
                        punto_venta_numero,
                        resultado.numero_comprobante,
                        resultado.cae,
                        totales["total"],
                    )
                    respuesta = EmitirComprobanteResponse(
                        exito=True,
                        comprobante_id=comprobante.id,
                        tipo_comprobante=request.tipo_comprobante,
                        punto_venta=punto_venta_numero,
                        numero=arca_request.cbte_desde,
                        fecha=comprobante.fecha_emision,
                        cae=resultado.cae,
                        cae_vencimiento=self._parse_fecha_cae(
                            resultado.cae_vencimiento
                        ),
                        total=totales["total"],
                        mensaje="Comprobante emitido exitosamente",
                    )
                    try:
                        await idempotencia.actualizar_intento_desde_respuesta(
                            intento,
                            respuesta,
                        )
                    except Exception:
                        await self._rollback_seguro("cierre_intento_batch_post_arca")
                        persistencia_bloqueada = True
                        logger.exception(
                            "Fallo al cerrar intento fiscal batch autorizado. "
                            "empresa=%s pv=%s tipo=%s numero=%s",
                            request.empresa_id,
                            punto_venta_numero,
                            request.tipo_comprobante,
                            arca_request.cbte_desde,
                        )
                        respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                            request=request,
                            punto_venta_numero=punto_venta_numero,
                            numero=arca_request.cbte_desde,
                            totales=totales,
                            resultado_arca=resultado,
                            mensaje=(
                                "ARCA autorizó el comprobante y FactuFlow lo guardó, "
                                "pero no pudo cerrar el intento fiscal"
                            ),
                            errores=[
                                "No reintentes esta emisión hasta reconciliar el intento fiscal y verificar el comprobante local.",
                                ERROR_INTERNO_EMISION_PUBLICO,
                            ],
                        )
                    respuestas.append(respuesta)

            return respuestas

        except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
            raise
        except ValidationError as e:
            logger.warning("Error de validación en sublote: %s", str(e))
            return [
                EmitirComprobanteResponse(
                    exito=False,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=0,
                    numero=0,
                    fecha=request.fecha_emision,
                    total=Decimal("0"),
                    mensaje="Error de validación",
                    errores=[str(e)],
                )
                for request in requests
            ]
        except Exception:
            logger.exception("Error inesperado al emitir sublote")
            if arca_iniciada_en_esta_llamada:
                resultados_por_numero = {
                    int(resultado.numero_comprobante): resultado
                    for resultado in resultados_arca
                }
                respuestas = []
                for index, (request, totales, intento) in enumerate(
                    zip(requests, totales_por_request, intentos)
                ):
                    numero = proximo + index
                    resultado_arca = resultados_por_numero.get(numero)
                    respuesta = None
                    if resultado_arca is not None:
                        respuesta = self._respuesta_si_arca_no_autorizo(
                            request=request,
                            punto_venta_numero=punto_venta_numero,
                            numero=numero,
                            totales=totales,
                            resultado_arca=resultado_arca,
                        )
                    if respuesta is None:
                        respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                            request=request,
                            punto_venta_numero=punto_venta_numero,
                            numero=numero,
                            totales=totales,
                            resultado_arca=resultado_arca,
                            mensaje=(
                                "FactuFlow no pudo confirmar el resultado del "
                                "sublote enviado a ARCA"
                            ),
                            errores=[
                                "No reintentes esta emisión hasta consultar ARCA y reconciliar el comprobante.",
                                ERROR_INTERNO_EMISION_PUBLICO,
                            ],
                            categoria_error="arca_respuesta_incierta",
                        )
                    intento_actualizado = (
                        await self._actualizar_intento_batch_preservando_respuesta(
                            idempotencia,
                            intento,
                            respuesta,
                            contexto="excepcion_inesperada_post_arca",
                        )
                    )
                    if (
                        not intento_actualizado
                        and not respuesta.requiere_reconciliacion
                    ):
                        respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                            request=request,
                            punto_venta_numero=punto_venta_numero,
                            numero=numero,
                            totales=totales,
                            resultado_arca=resultado_arca,
                            mensaje=(
                                "ARCA rechazó el comprobante, pero FactuFlow "
                                "no pudo cerrar el intento fiscal"
                            ),
                            errores=[
                                "No reintentes esta emisión hasta reconciliar el intento fiscal."
                            ],
                        )
                    respuestas.append(respuesta)
                return respuestas
            return [
                EmitirComprobanteResponse(
                    exito=False,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=0,
                    numero=0,
                    fecha=request.fecha_emision,
                    total=Decimal("0"),
                    mensaje="Error inesperado",
                    errores=[ERROR_INTERNO_EMISION_PUBLICO],
                )
                for request in requests
            ]

    async def _emitir_comprobante_locked(
        self,
        request: EmitirComprobanteRequest,
        commit: bool = True,
        operacion_id: int | None = None,
        usuario_id: int | None = None,
        lote_id: int | None = None,
        grupo_id: int | None = None,
        fase_solicitud_arca: FaseSolicitudArca | None = None,
    ) -> EmitirComprobanteResponse:
        """
        Flujo completo de emisión de comprobante.

        Pasos:
        1. Validar datos según tipo de comprobante
        2. Obtener próximo número
        3. Calcular totales
        4. Armar request para ARCA
        5. Solicitar CAE
        6. Guardar en BD
        7. Retornar resultado
        """
        fase_solicitud_arca = fase_solicitud_arca or FaseSolicitudArca()
        arca_iniciada_en_esta_llamada = False
        try:
            request = self.normalizar_receptor(request)
            # 1. Validar datos
            await self._validar_datos(request)
            await self._tomar_lock_numeracion(
                request.empresa_id,
                request.punto_venta_id,
                request.tipo_comprobante,
            )

            # 2. Calcular totales
            totales = self._calcular_totales(request.items)

            # 3. Obtener empresa y punto de venta
            empresa = await self._obtener_empresa(request.empresa_id)
            punto_venta = await self._obtener_punto_venta(
                request.punto_venta_id, request.empresa_id
            )
            punto_venta_numero = punto_venta.numero
            certificado = await self._obtener_certificado_activo(request.empresa_id)
            idempotencia = IdempotenciaFiscalService(self.db)

            if not request.confirmacion_duplicado_logico:
                duplicado = await idempotencia.buscar_duplicado_logico(
                    request=request,
                    punto_venta=punto_venta,
                    total=totales["total"],
                )
                if duplicado is not None:
                    return self._respuesta_duplicado_logico(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=duplicado.numero,
                        totales=totales,
                        comprobante_id=duplicado.id,
                    )

            # 4. Autenticar contra ARCA y reconciliar numeración
            ticket = await self._obtener_ticket_acceso(empresa, certificado)
            wsfe_client = WSFEv1Client(
                ambiente=self._get_arca_ambiente(),
                ticket=ticket,
                cuit=empresa.cuit,
            )
            await self._validar_punto_venta_habilitado(wsfe_client, punto_venta_numero)
            try:
                proximo = await self._obtener_proximo_numero(
                    request.empresa_id,
                    request.punto_venta_id,
                    request.tipo_comprobante,
                    wsfe_client,
                    punto_venta_numero,
                )
            except ReconciliacionNumeracionError as exc:
                return EmitirComprobanteResponse(
                    exito=False,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=punto_venta_numero,
                    numero=exc.ultimo_arca,
                    fecha=request.fecha_emision,
                    total=totales["total"],
                    mensaje="ARCA registra comprobantes que no están guardados en FactuFlow",
                    errores=[
                        str(exc),
                        (
                            f"Último local: {exc.ultimo_local}; "
                            f"último ARCA: {exc.ultimo_arca}."
                        ),
                    ],
                    requiere_reconciliacion=True,
                    categoria_error="numeracion_arca_adelantada",
                )

            # 5. Armar request para ARCA
            intento = await idempotencia.crear_intento_emision(
                request=request,
                punto_venta=punto_venta,
                numero_planificado=proximo,
                total=totales["total"],
                operacion_id=operacion_id,
                usuario_id=usuario_id,
                lote_id=lote_id,
                grupo_id=grupo_id,
            )
            arca_request = self._armar_request_arca(
                request, proximo, totales, punto_venta_numero
            )

            # 6. Solicitar CAE
            resultado = None
            try:
                fase_solicitud_arca.marcar_iniciada()
                arca_iniciada_en_esta_llamada = True
                resultado = await wsfe_client.fe_cae_solicitar(arca_request)

            except (ArcaServiceError, ArcaValidationError) as e:
                logger.error(f"Error al solicitar CAE: {str(e)}")
                respuesta = EmitirComprobanteResponse(
                    exito=False,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=punto_venta_numero,
                    numero=proximo,
                    fecha=request.fecha_emision,
                    total=totales["total"],
                    mensaje="FactuFlow no pudo confirmar el resultado de la solicitud a ARCA",
                    errores=[
                        "No reintentes esta emisión hasta consultar ARCA y reconciliar la numeración localmente.",
                        str(e),
                    ],
                    requiere_reconciliacion=True,
                    categoria_error="arca_respuesta_incierta",
                )
                await self._actualizar_intento_preservando_respuesta(
                    idempotencia,
                    intento,
                    respuesta,
                    commit=commit,
                    contexto="respuesta_incierta_arca",
                )
                return respuesta

            respuesta_no_aprobada = self._respuesta_si_arca_no_autorizo(
                request=request,
                punto_venta_numero=punto_venta_numero,
                numero=proximo,
                totales=totales,
                resultado_arca=resultado,
            )
            if respuesta_no_aprobada is not None:
                intento_actualizado = (
                    await self._actualizar_intento_preservando_respuesta(
                        idempotencia,
                        intento,
                        respuesta_no_aprobada,
                        commit=commit,
                        contexto="arca_no_aprobado",
                    )
                )
                if not intento_actualizado:
                    return self._respuesta_post_arca_requiere_reconciliacion(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=proximo,
                        totales=totales,
                        resultado_arca=resultado,
                        mensaje=(
                            "ARCA rechazó el comprobante, pero FactuFlow no pudo "
                            "cerrar el intento fiscal"
                        ),
                        errores=[
                            "No reintentes esta emisión hasta reconciliar el intento fiscal."
                        ],
                    )
                return respuesta_no_aprobada

            # 7. Guardar en BD
            try:
                comprobante = await self._guardar_comprobante(
                    request,
                    proximo,
                    totales,
                    resultado,
                    punto_venta,
                    commit=commit,
                )
            except IntegrityError as exc:
                await self._rollback_seguro("integrity_individual_post_arca")
                logger.exception(
                    "Conflicto de numeración al guardar comprobante autorizado. "
                    "empresa=%s pv=%s tipo=%s numero=%s",
                    request.empresa_id,
                    punto_venta_numero,
                    request.tipo_comprobante,
                    proximo,
                )
                respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    numero=proximo,
                    totales=totales,
                    resultado_arca=resultado,
                    mensaje="ARCA autorizó el comprobante, pero no se pudo guardar por conflicto de numeración",
                    errores=[
                        "No reintentes esta emisión hasta consultar ARCA y reconciliar el comprobante localmente.",
                        str(exc.orig),
                    ],
                )
                await self._actualizar_intento_preservando_respuesta(
                    idempotencia,
                    intento,
                    respuesta,
                    commit=commit,
                    contexto="conflicto_numeracion_post_arca",
                )
                return respuesta
            except Exception:
                await self._rollback_seguro("persistencia_individual_post_arca")
                logger.exception(
                    "Fallo posterior a CAE autorizado. empresa=%s pv=%s tipo=%s numero=%s",
                    request.empresa_id,
                    punto_venta_numero,
                    request.tipo_comprobante,
                    proximo,
                )
                respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    numero=proximo,
                    totales=totales,
                    resultado_arca=resultado,
                    mensaje="ARCA autorizó el comprobante, pero FactuFlow no pudo guardarlo",
                    errores=[
                        "No reintentes esta emisión hasta consultar ARCA y reconciliar el comprobante localmente.",
                        ERROR_INTERNO_EMISION_PUBLICO,
                    ],
                )
                await self._actualizar_intento_preservando_respuesta(
                    idempotencia,
                    intento,
                    respuesta,
                    commit=commit,
                    contexto="fallo_persistencia_post_arca",
                )
                return respuesta

            # 8. Retornar resultado
            logger.info(
                "Comprobante emitido: empresa=%s tipo=%s pv=%s numero=%s cae=%s total=%s",
                request.empresa_id,
                request.tipo_comprobante,
                punto_venta_numero,
                proximo,
                resultado.cae,
                totales["total"],
            )
            respuesta = EmitirComprobanteResponse(
                exito=True,
                comprobante_id=comprobante.id,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=punto_venta_numero,
                numero=proximo,
                fecha=comprobante.fecha_emision,
                cae=resultado.cae,
                cae_vencimiento=self._parse_fecha_cae(resultado.cae_vencimiento),
                total=totales["total"],
                mensaje="Comprobante emitido exitosamente",
            )
            intento_actualizado = await self._actualizar_intento_preservando_respuesta(
                idempotencia,
                intento,
                respuesta,
                commit=commit,
                contexto="cierre_exitoso_post_arca",
            )
            if not intento_actualizado:
                return self._respuesta_post_arca_requiere_reconciliacion(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    numero=proximo,
                    totales=totales,
                    resultado_arca=resultado,
                    mensaje=(
                        "ARCA autorizó el comprobante y FactuFlow lo guardó, "
                        "pero no pudo cerrar el intento fiscal"
                    ),
                    errores=[
                        "No reintentes esta emisión hasta reconciliar el intento fiscal y verificar el comprobante local."
                    ],
                )
            return respuesta

        except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
            raise
        except ValidationError as e:
            logger.warning(f"Error de validación: {str(e)}")
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=0,
                numero=0,
                fecha=request.fecha_emision,
                total=Decimal("0"),
                mensaje="Error de validación",
                errores=[str(e)],
            )
        except Exception:
            logger.exception("Error inesperado al emitir comprobante")
            if arca_iniciada_en_esta_llamada:
                respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    numero=proximo,
                    totales=totales,
                    resultado_arca=resultado,
                    mensaje=(
                        "FactuFlow no pudo confirmar el resultado de la solicitud "
                        "enviada a ARCA"
                    ),
                    errores=[
                        "No reintentes esta emisión hasta consultar ARCA y reconciliar el comprobante.",
                        ERROR_INTERNO_EMISION_PUBLICO,
                    ],
                    categoria_error="arca_respuesta_incierta",
                )
                await self._actualizar_intento_preservando_respuesta(
                    idempotencia,
                    intento,
                    respuesta,
                    commit=commit,
                    contexto="excepcion_inesperada_post_arca",
                )
                return respuesta
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=0,
                numero=0,
                fecha=request.fecha_emision,
                total=Decimal("0"),
                mensaje="Error inesperado",
                errores=[ERROR_INTERNO_EMISION_PUBLICO],
            )

    @classmethod
    async def _get_number_lock(
        cls, empresa_id: int, punto_venta_id: int, tipo_comprobante: int
    ) -> asyncio.Lock:
        """Obtiene un lock en memoria para evitar emisiones concurrentes locales."""
        key = (empresa_id, punto_venta_id, tipo_comprobante)
        async with cls._number_locks_guard:
            if key not in cls._number_locks:
                cls._number_locks[key] = asyncio.Lock()
            return cls._number_locks[key]

    async def _tomar_lock_numeracion(
        self, empresa_id: int, punto_venta_id: int, tipo_comprobante: int
    ) -> None:
        """Toma un advisory lock transaccional cuando la base es PostgreSQL."""
        bind = self.db.get_bind()
        if bind.dialect.name != "postgresql":
            return

        lock_key = f"factuflow:cbte:{empresa_id}:{punto_venta_id}:{tipo_comprobante}"
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": lock_key},
        )

    async def obtener_proximo_numero(
        self,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
        usar_arca: bool = True,
    ) -> int:
        """Obtiene el próximo número de comprobante disponible."""
        punto_venta = await self._obtener_punto_venta(punto_venta_id, empresa_id)
        if not punto_venta:
            raise ValidationError("Punto de venta no encontrado")

        if not usar_arca:
            return await self._obtener_proximo_numero(
                empresa_id, punto_venta_id, tipo_comprobante
            )

        empresa = await self._obtener_empresa(empresa_id)
        certificado = await self._obtener_certificado_activo(empresa_id)
        ticket = await self._obtener_ticket_acceso(empresa, certificado)
        wsfe_client = WSFEv1Client(
            ambiente=self._get_arca_ambiente(),
            ticket=ticket,
            cuit=empresa.cuit,
        )
        return await self._obtener_proximo_numero(
            empresa_id,
            punto_venta_id,
            tipo_comprobante,
            wsfe_client,
            punto_venta.numero,
        )

    @staticmethod
    def _validar_lote_homogeneo(
        requests: list[EmitirComprobanteRequest],
        max_registros: int | None = None,
    ) -> None:
        """Valida que un sublote pueda viajar en un único request WSFE."""
        if not requests:
            raise ValidationError("El sublote no tiene comprobantes para emitir")

        if max_registros is not None and max_registros > 0:
            if len(requests) > max_registros:
                raise ValidationError(
                    "El sublote supera la cantidad máxima permitida por ARCA"
                )

        primer = requests[0]
        for request in requests:
            if (
                request.empresa_id != primer.empresa_id
                or request.punto_venta_id != primer.punto_venta_id
                or request.tipo_comprobante != primer.tipo_comprobante
            ):
                raise ValidationError(
                    "Un sublote ARCA solo puede mezclar comprobantes del mismo "
                    "emisor, punto de venta y tipo"
                )

            if (
                request.tipo_comprobante
                in FacturacionService.TIPOS_COMPROBANTE_FCE_MIPYME
            ):
                raise ValidationError(
                    "Los comprobantes FCE/MiPyME deben emitirse de a uno según "
                    "la documentación ARCA"
                )

    def _respuesta_numeracion_arca_adelantada(
        self,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
        exc: ReconciliacionNumeracionError,
    ) -> EmitirComprobanteResponse:
        """Arma respuesta cuando ARCA tiene numeración ausente localmente."""
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje="ARCA registra comprobantes que no están guardados en FactuFlow",
            errores=[
                str(exc),
                (
                    f"Último local: {exc.ultimo_local}; "
                    f"último ARCA: {exc.ultimo_arca}."
                ),
            ],
            requiere_reconciliacion=True,
            categoria_error="numeracion_arca_adelantada",
        )

    def _respuesta_batch_sin_detalle_requiere_reconciliacion(
        self,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
        error: str,
    ) -> EmitirComprobanteResponse:
        """Arma respuesta no reintentable cuando un sublote no devuelve detalle."""
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje=(
                "FactuFlow no pudo confirmar el resultado del sublote enviado a ARCA"
            ),
            errores=[
                "No reintentes esta emisión hasta consultar ARCA y reconciliar la numeración localmente.",
                error,
            ],
            requiere_reconciliacion=True,
            categoria_error="arca_batch_sin_respuesta",
        )

    def _respuesta_duplicado_logico(
        self,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
        comprobante_id: int,
    ) -> EmitirComprobanteResponse:
        """Arma una advertencia de duplicado lógico probable."""
        return EmitirComprobanteResponse(
            exito=False,
            comprobante_id=comprobante_id,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje="Existe un comprobante local muy similar ya autorizado",
            errores=[
                "Si corresponde emitirlo igualmente, confirmá el duplicado probable antes de solicitar CAE."
            ],
            categoria_error="duplicado_logico",
        )

    def _calcular_totales(self, items: list[ItemComprobanteCreate]) -> dict:
        """
        Calcula subtotal, IVA y total.

        Returns:
            Dict con subtotal, iva_21, iva_10_5, iva_27, total
        """
        subtotal = Decimal("0")
        base_21 = Decimal("0")
        base_10_5 = Decimal("0")
        base_27 = Decimal("0")
        base_0 = Decimal("0")
        iva_21 = Decimal("0")
        iva_10_5 = Decimal("0")
        iva_27 = Decimal("0")

        for item in items:
            # Calcular subtotal del item
            item_subtotal = item.cantidad * item.precio_unitario

            # Aplicar descuento si hay
            if item.descuento_porcentaje > 0:
                descuento = item_subtotal * (item.descuento_porcentaje / 100)
                item_subtotal -= descuento

            subtotal += item_subtotal

            # Calcular IVA según alícuota
            if item.iva_porcentaje == Decimal("21"):
                base_21 += item_subtotal
                iva_21 += item_subtotal * Decimal("0.21")
            elif item.iva_porcentaje == Decimal("10.5"):
                base_10_5 += item_subtotal
                iva_10_5 += item_subtotal * Decimal("0.105")
            elif item.iva_porcentaje == Decimal("27"):
                base_27 += item_subtotal
                iva_27 += item_subtotal * Decimal("0.27")
            else:
                base_0 += item_subtotal

        total = subtotal + iva_21 + iva_10_5 + iva_27

        return {
            "subtotal": subtotal.quantize(Decimal("0.01")),
            "base_21": base_21.quantize(Decimal("0.01")),
            "base_10_5": base_10_5.quantize(Decimal("0.01")),
            "base_27": base_27.quantize(Decimal("0.01")),
            "base_0": base_0.quantize(Decimal("0.01")),
            "iva_21": iva_21.quantize(Decimal("0.01")),
            "iva_10_5": iva_10_5.quantize(Decimal("0.01")),
            "iva_27": iva_27.quantize(Decimal("0.01")),
            "total": total.quantize(Decimal("0.01")),
        }

    async def _validar_datos(self, request: EmitirComprobanteRequest):
        """
        Valida datos según reglas de negocio y ARCA.

        Raises:
            ValidationError: Si hay error de validación
        """
        # Factura A requiere CUIT del receptor
        if request.tipo_comprobante in [1, 2, 3]:
            if request.tipo_documento != 80:
                raise ValidationError(
                    "Para comprobantes tipo A, el receptor debe tener CUIT (tipo documento 80)"
                )

        if request.numero_documento.strip() == "":
            raise ValidationError("El número de documento del receptor es obligatorio")
        if request.razon_social.strip() == "":
            raise ValidationError("La razón social del receptor es obligatoria")

        if request.tipo_comprobante in self.TIPOS_COMPROBANTE_C:
            for item in request.items:
                if item.iva_porcentaje != Decimal("0"):
                    raise ValidationError(
                        "Para comprobantes tipo C, los ítems deben tener IVA 0"
                    )

        if request.concepto == 1 and any(
            (
                request.fecha_servicio_desde,
                request.fecha_servicio_hasta,
                request.fecha_vto_pago,
            )
        ):
            raise ValidationError(
                "Las fechas de servicio no corresponden a un comprobante de productos"
            )

        # Servicios requieren fechas
        if request.concepto in [2, 3]:
            if not request.fecha_servicio_desde:
                raise ValidationError("Para servicios debe indicar fecha desde")
            if not request.fecha_servicio_hasta:
                raise ValidationError("Para servicios debe indicar fecha hasta")
            if not request.fecha_vto_pago:
                raise ValidationError(
                    "Para servicios debe indicar fecha de vencimiento de pago"
                )

        self._validar_fecha_emision_arca(request.fecha_emision, request.concepto)

        # Validar que exista la empresa
        empresa = await self._obtener_empresa(request.empresa_id)
        if not empresa:
            raise ValidationError("Empresa no encontrada")

        # Validar que exista el punto de venta en la empresa activa
        punto_venta = await self._obtener_punto_venta(
            request.punto_venta_id, request.empresa_id
        )
        if not punto_venta:
            raise ValidationError("Punto de venta no encontrado para la empresa activa")

        if request.cliente_id is not None:
            cliente = await self._obtener_cliente(
                request.cliente_id, request.empresa_id
            )
            if not cliente:
                raise ValidationError("Cliente no encontrado para la empresa activa")

        # Validar items
        if not request.items or len(request.items) == 0:
            raise ValidationError("Debe incluir al menos un ítem")

        # Validar CUIT cuando aplica
        if request.tipo_documento == 80 and not validate_cuit(request.numero_documento):
            raise ValidationError("El CUIT informado es inválido")

    def normalizar_receptor(
        self, request: EmitirComprobanteRequest
    ) -> EmitirComprobanteRequest:
        """Normaliza y valida datos mínimos del receptor según tipo e importe."""
        total = self._calcular_totales(request.items)["total"]
        condicion_iva = self._normalizar_condicion_iva(request.condicion_iva)
        numero_documento = clean_cuit(request.numero_documento)
        razon_social = request.razon_social.strip()
        domicilio = request.domicilio.strip() if request.domicilio else None
        es_consumidor_final = condicion_iva == "CF" or request.tipo_documento == 99
        es_comprobante_a = request.tipo_comprobante in [1, 2, 3]

        if es_comprobante_a:
            if request.tipo_documento != 80:
                raise ValidationError(
                    "Para comprobantes tipo A, el receptor debe tener CUIT (tipo documento 80)"
                )
            if not numero_documento:
                raise ValidationError("El CUIT del receptor es obligatorio")
            if not razon_social:
                raise ValidationError("La razón social del receptor es obligatoria")
            return request.model_copy(
                update={
                    "numero_documento": numero_documento,
                    "razon_social": razon_social,
                    "condicion_iva": condicion_iva,
                    "domicilio": domicilio,
                }
            )

        if not numero_documento:
            if not es_consumidor_final:
                raise ValidationError(
                    "El documento del receptor es obligatorio salvo consumidor final bajo el umbral legal"
                )
            if total >= self.CONSUMIDOR_FINAL_IDENTIFICACION_MINIMA:
                raise ValidationError(
                    "Para consumidor final con importe igual o superior a $10.000.000 se debe informar CUIT, CUIL, CDI, DNI, pasaporte u otro documento válido"
                )
            numero_documento = "0"
            razon_social = razon_social or "A CONSUMIDOR FINAL"
            condicion_iva = "CF"
            return request.model_copy(
                update={
                    "tipo_documento": 99,
                    "numero_documento": numero_documento,
                    "razon_social": razon_social,
                    "condicion_iva": condicion_iva,
                    "domicilio": domicilio,
                }
            )

        if request.tipo_documento == 80 and not validate_cuit(numero_documento):
            raise ValidationError("El CUIT informado es inválido")

        if es_consumidor_final:
            razon_social = razon_social or "A CONSUMIDOR FINAL"
            condicion_iva = "CF"
        elif not razon_social:
            raise ValidationError("La razón social del receptor es obligatoria")

        return request.model_copy(
            update={
                "numero_documento": numero_documento,
                "razon_social": razon_social,
                "condicion_iva": condicion_iva,
                "domicilio": domicilio,
            }
        )

    async def _obtener_proximo_numero(
        self,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
        wsfe_client: Optional[WSFEv1Client] = None,
        punto_venta_numero: Optional[int] = None,
    ) -> int:
        """Obtiene el próximo número de comprobante disponible."""
        intento_bloqueante = await self._resolver_intento_bloqueante(
            empresa_id=empresa_id,
            punto_venta_id=punto_venta_id,
            tipo_comprobante=tipo_comprobante,
            wsfe_client=wsfe_client,
            punto_venta_numero=punto_venta_numero,
        )
        if intento_bloqueante is not None:
            raise ValidationError(
                "Existe una emisión en proceso o pendiente de reconciliación "
                "para este emisor, punto de venta y tipo de comprobante. "
                "Consultá ARCA y reconciliá antes de emitir nuevos comprobantes."
            )

        # Buscar el último comprobante del mismo tipo y punto de venta
        stmt = (
            select(Comprobante)
            .where(
                Comprobante.empresa_id == empresa_id,
                Comprobante.punto_venta_id == punto_venta_id,
                Comprobante.tipo_comprobante == tipo_comprobante,
            )
            .order_by(desc(Comprobante.numero))
            .limit(1)
        )

        result = await self.db.execute(stmt)
        ultimo = result.scalar_one_or_none()
        proximo_local = ultimo.numero + 1 if ultimo else 1

        if not wsfe_client or punto_venta_numero is None:
            return proximo_local

        ultimo_arca = await wsfe_client.fe_comp_ultimo_autorizado(
            punto_venta_numero,
            tipo_comprobante,
        )
        proximo_arca = ultimo_arca + 1

        if proximo_local > proximo_arca:
            raise ValidationError(
                "La numeración local está adelantada respecto de ARCA. Revisá los comprobantes emitidos antes de continuar."
            )

        if proximo_local < proximo_arca:
            logger.error(
                "ARCA registra comprobantes ausentes localmente. "
                "empresa=%s pv=%s tipo=%s ultimo_local=%s ultimo_arca=%s",
                empresa_id,
                punto_venta_numero,
                tipo_comprobante,
                proximo_local - 1,
                ultimo_arca,
            )
            raise ReconciliacionNumeracionError(
                ultimo_local=proximo_local - 1,
                ultimo_arca=ultimo_arca,
                proximo_local=proximo_local,
                proximo_arca=proximo_arca,
            )

        return max(proximo_local, proximo_arca)

    async def _resolver_intento_bloqueante(
        self,
        *,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
        wsfe_client: Optional[WSFEv1Client],
        punto_venta_numero: Optional[int],
    ) -> IntentoEmisionFiscal | None:
        """Reconcilia intentos vencidos antes de bloquear nueva numeración."""
        while True:
            intento = await IdempotenciaFiscalService(
                self.db
            ).existe_intento_bloqueante(
                empresa_id,
                punto_venta_id,
                tipo_comprobante,
            )
            if intento is None:
                return None
            if intento.estado != "en_proceso" or intento.numero_planificado is None:
                return intento

            stale_before = datetime.utcnow() - timedelta(
                minutes=settings.fiscal_attempt_stale_minutes
            )
            if intento.created_at >= stale_before:
                return intento
            if wsfe_client is None or punto_venta_numero is None:
                return intento

            reconciliado = await self._reconciliar_intento_stale(
                intento=intento,
                wsfe_client=wsfe_client,
                punto_venta_numero=punto_venta_numero,
            )
            if reconciliado is not None:
                return reconciliado

    async def _respuesta_desde_intento_resuelto(
        self,
        intento: IntentoEmisionFiscal,
    ) -> EmitirComprobanteResponse | None:
        """Construye respuesta idempotente para un intento ya autorizado."""
        if intento.estado != "autorizado" or not intento.comprobante_id:
            return None

        comprobante = await self.db.get(Comprobante, intento.comprobante_id)
        if comprobante is None:
            return None

        return EmitirComprobanteResponse(
            exito=True,
            comprobante_id=comprobante.id,
            tipo_comprobante=comprobante.tipo_comprobante,
            punto_venta=intento.punto_venta_numero,
            numero=comprobante.numero,
            fecha=comprobante.fecha_emision,
            cae=comprobante.cae,
            cae_vencimiento=comprobante.cae_vencimiento,
            total=Decimal(str(comprobante.total)),
            mensaje="Comprobante emitido exitosamente",
        )

    def _respuesta_intento_requiere_reconciliacion(
        self,
        intento: IntentoEmisionFiscal,
    ) -> EmitirComprobanteResponse:
        """Construye respuesta no reintentable para un intento incierto."""
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=intento.tipo_comprobante,
            punto_venta=intento.punto_venta_numero,
            numero=intento.numero_planificado or 0,
            fecha=intento.fecha_emision,
            cae=intento.cae,
            cae_vencimiento=intento.cae_vencimiento,
            total=Decimal(str(intento.total)),
            mensaje=(
                intento.mensaje
                or "La operación fiscal requiere reconciliación antes de continuar."
            ),
            errores=[
                "No vuelvas a solicitar CAE hasta verificar el comprobante en ARCA."
            ],
            requiere_reconciliacion=True,
            categoria_error=intento.categoria_error or "idempotencia_en_proceso",
        )

    async def _reconciliar_intento_stale(
        self,
        *,
        intento: IntentoEmisionFiscal,
        wsfe_client: WSFEv1Client,
        punto_venta_numero: int,
    ) -> IntentoEmisionFiscal | None:
        """Consulta ARCA por un intento vencido antes de liberar la reserva."""
        try:
            consulta_arca = await wsfe_client.fe_comp_consultar(
                punto_venta=punto_venta_numero,
                tipo_cbte=intento.tipo_comprobante,
                numero=intento.numero_planificado,
            )
        except ArcaServiceError as exc:
            if self._arca_indica_comprobante_inexistente(exc):
                intento.estado = "fallido_verificado"
                intento.categoria_error = "arca_no_registrado"
                intento.mensaje = (
                    "ARCA no registra el comprobante planificado; "
                    "la numeración local queda liberada."
                )
                self.db.add(intento)
                await self.db.commit()
                return None

            intento.estado = "requiere_reconciliacion"
            intento.categoria_error = "arca_consulta_incierta"
            intento.mensaje = (
                "No se pudo verificar en ARCA si el comprobante planificado "
                "fue autorizado."
            )
            self.db.add(intento)
            await self.db.commit()
            return intento

        if not await self._validar_consulta_intento_stale(intento, consulta_arca):
            intento.estado = "requiere_reconciliacion"
            intento.categoria_error = "arca_consulta_inconsistente"
            intento.mensaje = (
                "ARCA devolvió datos distintos para el comprobante planificado."
            )
            self.db.add(intento)
            await self.db.commit()
            return intento

        comprobante = await self._crear_o_vincular_intento_autorizado(
            intento=intento,
            consulta_arca=consulta_arca,
        )
        if comprobante is None:
            intento.estado = "requiere_reconciliacion"
            intento.categoria_error = "arca_autorizado_sin_payload_local"
            intento.cae = str(consulta_arca.cae)
            intento.cae_vencimiento = self._parse_fecha_cae(
                str(consulta_arca.cae_vencimiento)
            )
            intento.mensaje = (
                "ARCA confirma CAE para el intento, pero FactuFlow no tiene "
                "datos completos para reconstruir automáticamente el comprobante."
            )
            self.db.add(intento)
            await self.db.commit()
            return intento

        intento.estado = "autorizado"
        intento.comprobante_id = comprobante.id
        intento.cae = comprobante.cae
        intento.cae_vencimiento = comprobante.cae_vencimiento
        intento.mensaje = "Intento vencido reconciliado contra ARCA."
        self.db.add(intento)
        await self.db.commit()
        return None

    async def _validar_consulta_intento_stale(
        self,
        intento: IntentoEmisionFiscal,
        consulta_arca,
    ) -> bool:
        """Valida que la consulta ARCA coincida con el snapshot del intento."""
        empresa = await self._obtener_empresa(intento.empresa_id)
        if empresa is None:
            return False

        try:
            fecha_arca = datetime.strptime(
                str(consulta_arca.fecha_cbte), "%Y%m%d"
            ).date()
            total_arca = Decimal(str(consulta_arca.imp_total)).quantize(Decimal("0.01"))
            tipo_doc_arca = int(consulta_arca.tipo_doc)
            nro_doc_arca = clean_cuit(str(consulta_arca.nro_doc or ""))
        except (TypeError, ValueError):
            return False

        return all(
            [
                consulta_arca.resultado == "A",
                bool(str(consulta_arca.cae or "").strip()),
                bool(str(consulta_arca.cae_vencimiento or "").strip()),
                clean_cuit(str(consulta_arca.cuit_emisor)) == clean_cuit(empresa.cuit),
                int(consulta_arca.tipo_cbte) == int(intento.tipo_comprobante),
                int(consulta_arca.punto_venta) == int(intento.punto_venta_numero),
                int(consulta_arca.numero) == int(intento.numero_planificado),
                fecha_arca == intento.fecha_emision,
                total_arca == Decimal(str(intento.total)).quantize(Decimal("0.01")),
                tipo_doc_arca == int(intento.receptor_tipo_documento or 0),
                nro_doc_arca
                == clean_cuit(str(intento.receptor_numero_documento or "")),
            ]
        )

    async def _crear_o_vincular_intento_autorizado(
        self,
        *,
        intento: IntentoEmisionFiscal,
        consulta_arca,
    ) -> Comprobante | None:
        """Crea o vincula el comprobante confirmado por ARCA para un intento."""
        existente = await self.db.scalar(
            select(Comprobante).where(
                Comprobante.empresa_id == intento.empresa_id,
                Comprobante.punto_venta_id == intento.punto_venta_id,
                Comprobante.tipo_comprobante == intento.tipo_comprobante,
                Comprobante.numero == intento.numero_planificado,
            )
        )
        if existente is not None:
            if (
                existente.estado == "autorizado"
                and existente.cae == str(consulta_arca.cae)
                and existente.fecha_emision == intento.fecha_emision
                and Decimal(str(existente.total)).quantize(Decimal("0.01"))
                == Decimal(str(intento.total)).quantize(Decimal("0.01"))
            ):
                return existente
            return None

        if intento.grupo_id is None:
            return None

        grupo = await self.db.get(LoteComprobanteGrupo, intento.grupo_id)
        if grupo is None or not grupo.payload_json:
            return None

        punto_venta = await self._obtener_punto_venta(
            intento.punto_venta_id,
            intento.empresa_id,
        )
        if punto_venta is None:
            return None

        request = EmitirComprobanteRequest.model_validate(grupo.payload_json)
        totales = self._calcular_totales(request.items)
        if Decimal(str(totales["total"])).quantize(Decimal("0.01")) != Decimal(
            str(intento.total)
        ).quantize(Decimal("0.01")):
            return None

        comprobante = await self._guardar_comprobante(
            request,
            intento.numero_planificado,
            totales,
            consulta_arca,
            punto_venta,
            commit=False,
        )
        grupo.estado = "autorizado"
        grupo.cae = comprobante.cae
        grupo.numero_asignado = comprobante.numero
        grupo.comprobante_id = comprobante.id
        grupo.mensajes_json = [
            "Comprobante reconciliado automáticamente contra ARCA.",
            f"CAE {comprobante.cae}",
        ]
        await self.db.execute(
            update(LoteComprobanteFila)
            .where(LoteComprobanteFila.grupo_id == grupo.id)
            .values(estado="autorizado", mensajes_json=grupo.mensajes_json)
        )
        lote = await self.db.get(LoteComprobante, grupo.lote_id)
        if lote is not None:
            lote.mensaje_resumen = "Se reconciliaron comprobantes autorizados por ARCA."
            from app.services.lote_comprobantes_service import LoteComprobantesService

            await LoteComprobantesService(self.db)._actualizar_estado_lote(lote)
            if (
                lote.estado
                in {
                    "completado",
                    "cerrado_reconciliado",
                    "autorizado_parcial",
                }
                and lote.finished_at is None
            ):
                lote.finished_at = datetime.utcnow()
        return comprobante

    @staticmethod
    def _arca_indica_comprobante_inexistente(exc: ArcaServiceError) -> bool:
        """Detecta respuestas ARCA explícitas de comprobante inexistente."""
        codigo = str(exc.codigo or "").strip()
        mensaje = str(exc.mensaje or "").strip().lower()
        if codigo in {"602", "10016"}:
            return True
        return mensaje in {
            "comprobante inexistente",
            "el comprobante consultado es inexistente",
            "comprobante consultado inexistente",
            "sin resultados para el comprobante consultado",
        }

    async def _obtener_empresa(self, empresa_id: int) -> Optional[Empresa]:
        """Obtiene una empresa por ID."""
        stmt = select(Empresa).where(Empresa.id == empresa_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _obtener_punto_venta(
        self, punto_venta_id: int, empresa_id: int | None = None
    ) -> Optional[PuntoVenta]:
        """Obtiene un punto de venta por ID."""
        stmt = select(PuntoVenta).where(PuntoVenta.id == punto_venta_id)
        if empresa_id is not None:
            stmt = stmt.where(PuntoVenta.empresa_id == empresa_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _obtener_cliente(
        self, cliente_id: int, empresa_id: int
    ) -> Optional[Cliente]:
        """Obtiene un cliente por ID dentro de una empresa."""
        stmt = select(Cliente).where(
            Cliente.id == cliente_id,
            Cliente.empresa_id == empresa_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _obtener_certificado_activo(self, empresa_id: int) -> Certificado:
        """Obtiene el certificado activo para la empresa y el ambiente actual."""
        stmt = (
            select(Certificado)
            .where(
                Certificado.empresa_id == empresa_id,
                Certificado.activo.is_(True),
                Certificado.ambiente == self._get_arca_ambiente().value,
            )
            .order_by(Certificado.fecha_vencimiento.desc(), Certificado.id.desc())
        )
        result = await self.db.execute(stmt)
        certificado = result.scalars().first()
        if certificado is None:
            raise ValidationError(
                "No hay un certificado activo configurado para la empresa en el ambiente actual"
            )
        return certificado

    def _get_arca_ambiente(self) -> ArcaAmbiente:
        """Resuelve el ambiente ARCA configurado."""
        if settings.arca_env.lower() == ArcaAmbiente.PRODUCCION.value:
            return ArcaAmbiente.PRODUCCION
        return ArcaAmbiente.HOMOLOGACION

    async def _obtener_ticket_acceso(self, empresa: Empresa, certificado: Certificado):
        """Obtiene ticket WSAA para la empresa con material local utilizable."""
        cert_path, key_path = requerir_material_certificado(
            certificado.archivo_crt,
            certificado.archivo_key,
        )
        wsaa_client = WSAAClient(self._get_arca_ambiente())
        return await wsaa_client.login(
            cert_path=str(cert_path),
            key_path=str(key_path),
            cuit=clean_cuit(empresa.cuit),
            servicio="wsfe",
        )

    async def _validar_punto_venta_habilitado(
        self, wsfe_client: WSFEv1Client, punto_venta_numero: int
    ) -> None:
        """Verifica que el punto de venta exista y no esté bloqueado en ARCA."""
        puntos = await wsfe_client.fe_param_get_ptos_venta()
        if not puntos and self._get_arca_ambiente() == ArcaAmbiente.HOMOLOGACION:
            logger.warning(
                "ARCA no devolvió puntos de venta en homologación; se omite validación estricta para pv=%s",
                punto_venta_numero,
            )
            return
        for punto in puntos:
            if punto.numero == punto_venta_numero and self._es_punto_arca_habilitado(
                punto.bloqueado
            ):
                return
        raise ValidationError(
            f"El punto de venta {punto_venta_numero} no está habilitado en ARCA para esta empresa"
        )

    @staticmethod
    def _es_punto_arca_habilitado(bloqueado: object) -> bool:
        """Interpreta el indicador `Bloqueado` devuelto por ARCA."""
        if isinstance(bloqueado, bool):
            return not bloqueado

        texto = str(bloqueado).strip().upper()
        return texto in {"N", "NO", "FALSE", "0"}

    def _armar_request_arca(
        self,
        request: EmitirComprobanteRequest,
        numero: int,
        totales: dict,
        punto_venta_numero: int,
    ) -> ComprobanteRequest:
        """
        Arma el request para el servicio ARCA (WSFEv1).

        Args:
            request: Request de emisión
            numero: Número de comprobante
            totales: Dict con totales calculados
            punto_venta_numero: Número del punto de venta

        Returns:
            ComprobanteRequest para ARCA
        """
        # Limpiar número de documento (solo dígitos)
        nro_doc = "".join(filter(str.isdigit, request.numero_documento))

        # Calcular IVA para ARCA. Para comprobantes C no se informa objeto Iva.
        iva_items = []
        informa_iva = request.tipo_comprobante not in self.TIPOS_COMPROBANTE_C

        if informa_iva and totales["iva_21"] > 0:
            iva_items.append(
                IvaItem(
                    id=5,
                    base_imp=totales["base_21"],
                    importe=totales["iva_21"],
                )
            )

        if informa_iva and totales["iva_10_5"] > 0:
            iva_items.append(
                IvaItem(
                    id=4,  # 10.5%
                    base_imp=totales["base_10_5"],
                    importe=totales["iva_10_5"],
                )
            )

        if informa_iva and totales["iva_27"] > 0:
            iva_items.append(
                IvaItem(
                    id=6,
                    base_imp=totales["base_27"],
                    importe=totales["iva_27"],
                )
            )

        if informa_iva and not iva_items:
            iva_items.append(
                IvaItem(id=3, base_imp=totales["base_0"], importe=Decimal("0"))
            )

        # Crear request
        cbtes_asoc = [
            CbteAsocItem(
                tipo=asociado.tipo_comprobante,
                punto_venta=asociado.punto_venta,
                numero=asociado.numero,
                cuit=asociado.cuit,
                fecha_cbte=asociado.fecha.strftime("%Y%m%d")
                if asociado.fecha
                else None,
            )
            for asociado in request.comprobantes_asociados
        ]

        return ComprobanteRequest(
            punto_venta=punto_venta_numero,
            tipo_cbte=request.tipo_comprobante,
            concepto=request.concepto,
            tipo_doc=request.tipo_documento,
            nro_doc=int(nro_doc),
            cbte_desde=numero,
            cbte_hasta=numero,
            fecha_cbte=request.fecha_emision.strftime("%Y%m%d"),
            imp_total=totales["total"],
            imp_tot_conc=Decimal("0"),  # No implementado aún
            imp_neto=totales["subtotal"],
            imp_op_ex=Decimal("0"),  # No implementado aún
            imp_iva=totales["iva_21"] + totales["iva_10_5"] + totales["iva_27"],
            imp_trib=Decimal("0"),  # No implementado aún
            moneda_id=request.moneda,
            moneda_cotiz=request.cotizacion,
            condicion_iva_receptor_id=self._obtener_condicion_iva_receptor_id(
                request.condicion_iva
            ),
            fecha_serv_desde=(
                request.fecha_servicio_desde.strftime("%Y%m%d")
                if request.fecha_servicio_desde
                else None
            ),
            fecha_serv_hasta=(
                request.fecha_servicio_hasta.strftime("%Y%m%d")
                if request.fecha_servicio_hasta
                else None
            ),
            fecha_vto_pago=(
                request.fecha_vto_pago.strftime("%Y%m%d")
                if request.fecha_vto_pago
                else None
            ),
            iva=iva_items,
            cbtes_asoc=cbtes_asoc,
        )

    def _respuesta_post_arca_requiere_reconciliacion(
        self,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
        resultado_arca,
        mensaje: str,
        errores: list[str],
        categoria_error: str = "post_arca_persistencia",
    ) -> EmitirComprobanteResponse:
        """Arma una respuesta no reintentable después de iniciar ARCA."""
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero,
            fecha=request.fecha_emision,
            cae=getattr(resultado_arca, "cae", None),
            cae_vencimiento=self._parse_fecha_cae(
                getattr(resultado_arca, "cae_vencimiento", None)
            ),
            total=totales["total"],
            mensaje=mensaje,
            errores=errores,
            requiere_reconciliacion=True,
            categoria_error=categoria_error,
        )

    async def _actualizar_intento_batch_preservando_respuesta(
        self,
        idempotencia: IdempotenciaFiscalService,
        intento: IntentoEmisionFiscal | None,
        respuesta: EmitirComprobanteResponse,
        contexto: str,
    ) -> bool:
        """Actualiza un intento batch sin ocultar una respuesta fiscal segura."""
        return await self._actualizar_intento_preservando_respuesta(
            idempotencia,
            intento,
            respuesta,
            contexto=contexto,
        )

    async def _actualizar_intento_preservando_respuesta(
        self,
        idempotencia: IdempotenciaFiscalService,
        intento: IntentoEmisionFiscal | None,
        respuesta: EmitirComprobanteResponse,
        *,
        contexto: str,
        commit: bool = True,
    ) -> bool:
        """Actualiza un intento sin ocultar una respuesta fiscal ya obtenida."""
        try:
            await idempotencia.actualizar_intento_desde_respuesta(
                intento,
                respuesta,
                commit=commit,
            )
        except Exception as exc:
            await self._rollback_seguro(f"actualizar_intento:{contexto}")
            logger.error(
                "No se pudo actualizar intento fiscal contexto=%s tipo_error=%s",
                contexto,
                type(exc).__name__,
            )
            return False
        return True

    async def _rollback_seguro(self, contexto: str) -> None:
        """Intenta rollback sin tapar el resultado fiscal ni registrar detalles."""
        try:
            await self.db.rollback()
        except Exception as exc:
            logger.error(
                "Falló rollback fiscal contexto=%s tipo_error=%s",
                contexto,
                type(exc).__name__,
            )

    async def _marcar_intentos_batch_pre_arca_fallidos(
        self,
        intento_ids: list[int],
        error: str,
    ) -> None:
        """Cierra intentos batch que nunca llegaron a enviarse a ARCA."""
        if not intento_ids:
            return

        mensaje = (
            "FactuFlow no llegó a enviar el sublote a ARCA porque falló la "
            f"preparación local. Detalle: {error}"
        )
        await self.db.execute(
            update(IntentoEmisionFiscal)
            .where(
                IntentoEmisionFiscal.id.in_(intento_ids),
                IntentoEmisionFiscal.estado == "en_proceso",
            )
            .values(
                estado="fallido_verificado",
                categoria_error="pre_arca_reserva_fallida",
                mensaje=mensaje,
            )
        )
        await self.db.commit()

    def _respuesta_batch_reserva_pre_arca_fallida(
        self,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
        error: str,
    ) -> EmitirComprobanteResponse:
        """Arma una respuesta fallida cuando el sublote no llegó a ARCA."""
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje="FactuFlow no pudo preparar el sublote antes de contactar ARCA",
            errores=[
                "No se envió esta solicitud a ARCA; la reserva local quedó cerrada como fallida verificada.",
                error,
            ],
            categoria_error="pre_arca_reserva_fallida",
        )

    def _ordenar_resultados_arca_batch_por_numero(
        self,
        arca_requests: list[ComprobanteRequest],
        resultados_arca: list,
    ) -> list:
        """Valida y ordena respuestas batch de ARCA por número solicitado."""
        if len(resultados_arca) != len(arca_requests):
            raise ArcaServiceError(
                "ARCA devolvió una cantidad de resultados distinta a la solicitada"
            )

        resultados_por_numero = {}
        for resultado in resultados_arca:
            numero_raw = getattr(resultado, "numero_comprobante", None)
            if numero_raw is None:
                raise ArcaServiceError(
                    "ARCA devolvió un resultado de batch sin número de comprobante"
                )
            try:
                numero = int(numero_raw)
            except (TypeError, ValueError) as exc:
                raise ArcaServiceError(
                    f"ARCA devolvió un número de comprobante inválido: {numero_raw}"
                ) from exc
            if numero in resultados_por_numero:
                raise ArcaServiceError(
                    f"ARCA devolvió un número de comprobante duplicado: {numero}"
                )
            resultados_por_numero[numero] = resultado

        numeros_solicitados = [int(request.cbte_desde) for request in arca_requests]
        solicitados_set = set(numeros_solicitados)
        recibidos_set = set(resultados_por_numero)
        if solicitados_set != recibidos_set:
            partes = []
            faltantes = sorted(solicitados_set - recibidos_set)
            extras = sorted(recibidos_set - solicitados_set)
            if faltantes:
                partes.append(f"faltantes: {faltantes}")
            if extras:
                partes.append(f"no solicitados: {extras}")
            raise ArcaServiceError(
                "ARCA devolvió resultados para números distintos a los solicitados "
                f"({'; '.join(partes)})"
            )

        return [resultados_por_numero[numero] for numero in numeros_solicitados]

    def _respuesta_si_arca_no_autorizo(
        self,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
        resultado_arca,
    ) -> EmitirComprobanteResponse | None:
        """Devuelve error si WSFE no aprobó la emisión con CAE válido."""
        aprobado = bool(getattr(resultado_arca, "is_aprobado", True))
        cae = getattr(resultado_arca, "cae", None)
        cae_vencimiento = getattr(resultado_arca, "cae_vencimiento", None)
        if aprobado and cae and cae_vencimiento:
            return None

        errores = self._mensajes_resultado_arca(resultado_arca)
        if not errores:
            resultado = getattr(resultado_arca, "resultado", "desconocido")
            errores = [
                f"ARCA devolvió resultado {resultado} sin CAE válido para persistir."
            ]

        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje="ARCA no aprobó el comprobante",
            errores=errores,
            categoria_error="arca_no_aprobado",
        )

    @staticmethod
    def _mensajes_resultado_arca(resultado_arca) -> list[str]:
        """Extrae errores y observaciones legibles de una respuesta WSFE."""
        mensajes: list[str] = []
        for attr in ("errores", "observaciones"):
            for item in getattr(resultado_arca, attr, None) or []:
                code = getattr(item, "code", None)
                msg = getattr(item, "msg", None)
                if code is not None and msg:
                    mensajes.append(f"{code}: {msg}")
                elif msg:
                    mensajes.append(str(msg))
        return mensajes

    async def _guardar_comprobante(
        self,
        request: EmitirComprobanteRequest,
        numero: int,
        totales: dict,
        resultado_arca,
        punto_venta: PuntoVenta,
        origen_emision: str = "factuflow",
        commit: bool = True,
    ) -> Comprobante:
        """
        Guarda el comprobante en la base de datos.

        Args:
            request: Request de emisión
            numero: Número de comprobante
            totales: Dict con totales calculados
            resultado_arca: Respuesta de ARCA con CAE
            punto_venta: Punto de venta

        Returns:
            Comprobante guardado
        """
        tipo_documento = self._normalizar_tipo_documento(request.tipo_documento)
        numero_documento = clean_cuit(request.numero_documento)
        if not resultado_arca.cae or not resultado_arca.cae_vencimiento:
            raise ValueError("No se puede guardar un comprobante sin CAE autorizado")

        # Obtener o crear cliente solo cuando el flujo lo pida explícitamente.
        cliente_id = request.cliente_id
        if not cliente_id and request.guardar_cliente:
            result = await self.db.execute(
                select(Cliente).where(
                    Cliente.empresa_id == request.empresa_id,
                    Cliente.tipo_documento == tipo_documento,
                    Cliente.numero_documento == numero_documento,
                )
            )
            cliente = result.scalar_one_or_none()

            if cliente is None:
                cliente = Cliente(
                    empresa_id=request.empresa_id,
                    razon_social=request.razon_social,
                    tipo_documento=tipo_documento,
                    numero_documento=numero_documento,
                    condicion_iva=self._normalizar_condicion_iva(request.condicion_iva),
                    domicilio=request.domicilio,
                )
                self.db.add(cliente)
                await self.db.flush()

            cliente_id = cliente.id

        # Crear comprobante
        comprobante = Comprobante(
            tipo_comprobante=request.tipo_comprobante,
            concepto=request.concepto,
            numero=numero,
            fecha_emision=request.fecha_emision,
            fecha_servicio_desde=request.fecha_servicio_desde,
            fecha_servicio_hasta=request.fecha_servicio_hasta,
            fecha_vto_pago=request.fecha_vto_pago,
            fecha_vencimiento=request.fecha_vto_pago,
            subtotal=totales["subtotal"],
            descuento=Decimal("0"),
            iva_21=totales["iva_21"],
            iva_10_5=totales["iva_10_5"],
            iva_27=totales["iva_27"],
            otros_impuestos=Decimal("0"),
            total=totales["total"],
            cae=resultado_arca.cae,
            cae_vencimiento=self._parse_fecha_cae(resultado_arca.cae_vencimiento),
            estado="autorizado",
            origen_emision=origen_emision,
            moneda=request.moneda,
            cotizacion=request.cotizacion,
            observaciones=request.observaciones,
            empresa_id=request.empresa_id,
            punto_venta_id=punto_venta.id,
            cliente_id=cliente_id,
            receptor_tipo_documento=request.tipo_documento,
            receptor_numero_documento=numero_documento,
            receptor_razon_social=request.razon_social,
            receptor_condicion_iva=self._normalizar_condicion_iva(
                request.condicion_iva
            ),
            receptor_domicilio=request.domicilio,
        )

        self.db.add(comprobante)
        await self.db.flush()

        # Crear items
        for idx, item_data in enumerate(request.items):
            # Calcular subtotal del item
            item_subtotal = item_data.cantidad * item_data.precio_unitario
            if item_data.descuento_porcentaje > 0:
                descuento = item_subtotal * (item_data.descuento_porcentaje / 100)
                item_subtotal -= descuento

            item = ComprobanteItem(
                codigo=item_data.codigo,
                descripcion=item_data.descripcion,
                cantidad=item_data.cantidad,
                unidad=item_data.unidad,
                precio_unitario=item_data.precio_unitario,
                descuento_porcentaje=item_data.descuento_porcentaje,
                iva_porcentaje=item_data.iva_porcentaje,
                subtotal=item_subtotal.quantize(Decimal("0.01")),
                orden=item_data.orden if item_data.orden > 0 else idx,
                comprobante_id=comprobante.id,
            )
            self.db.add(item)

        if commit:
            await self.db.commit()
            await self.db.refresh(comprobante)

        return comprobante

    def _validar_fecha_emision_arca(self, fecha_emision: date, concepto: int) -> None:
        """Valida la ventana de fecha de comprobante admitida por WSFE."""
        hoy = date.today()
        dias = 10 if concepto in {2, 3} else 5
        desde = hoy - timedelta(days=dias)
        hasta = hoy + timedelta(days=dias)
        if desde <= fecha_emision <= hasta:
            return

        tipo = "servicios" if concepto in {2, 3} else "productos"
        raise ValidationError(
            "La fecha de emisión "
            f"{fecha_emision.strftime('%d/%m/%Y')} queda fuera de la ventana "
            f"ARCA para {tipo}: debe estar entre "
            f"{desde.strftime('%d/%m/%Y')} y {hasta.strftime('%d/%m/%Y')}."
        )

    def _normalizar_tipo_documento(self, tipo_documento: int | str) -> str:
        """Convierte el tipo de documento a la representación persistida."""
        if isinstance(tipo_documento, str):
            return tipo_documento
        return self.TIPO_DOCUMENTO_CODIGO_A_NOMBRE.get(tipo_documento, "CI")

    def _normalizar_condicion_iva(self, condicion_iva: str) -> str:
        """Normaliza condición de IVA desde UI/API a código persistido."""
        return self.CONDICION_IVA_MAP.get(condicion_iva, condicion_iva)

    def _obtener_condicion_iva_receptor_id(self, condicion_iva: str) -> int | None:
        """Mapea la condición IVA del receptor al ID requerido por WSFE."""
        condicion_normalizada = self._normalizar_condicion_iva(condicion_iva)
        return self.CONDICION_IVA_RECEPTOR_ID_MAP.get(condicion_normalizada)

    def _parse_fecha_cae(self, fecha_str: Optional[str]) -> Optional[date]:
        """
        Parsea fecha de CAE desde string YYYYMMDD.

        Args:
            fecha_str: Fecha en formato YYYYMMDD

        Returns:
            date o None
        """
        if not fecha_str:
            return None

        try:
            # Formato: YYYYMMDD
            return date(int(fecha_str[0:4]), int(fecha_str[4:6]), int(fecha_str[6:8]))
        except (ValueError, IndexError):
            logger.warning(f"No se pudo parsear fecha CAE: {fecha_str}")
            return None
