"""Servicio de Facturación - Emisión de Comprobantes."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal, Optional

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import desc, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from app.arca.config import ArcaAmbiente
from app.arca.exceptions import (
    ArcaErrorGlobalEstructurado,
    ArcaServiceError,
    ArcaValidationError,
    clasificar_error_global_fecae,
)
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
from app.models.elegibilidad_rece import PuntoVentaGuardaEmisionRece
from app.models.idempotencia_fiscal import IntentoEmisionFiscal, OperacionIdempotente
from app.models.lote_comprobante import (
    LoteComprobante,
    LoteComprobanteFila,
    LoteComprobanteGrupo,
)
from app.models.punto_venta import PuntoVenta
from app.services.certificados_service import requerir_material_certificado
from app.services.contencion_fiscal_service import (
    CATEGORIA_BLOQUEO_PREAUTORIZACION,
    DETALLE_BLOQUEO_PREAUTORIZACION,
    MENSAJE_BLOQUEO_PREAUTORIZACION,
    obtener_bloqueo_preautorizacion,
)
from app.services.idempotencia_fiscal_service import IdempotenciaFiscalService
from app.services.elegibilidad_rece_service import (
    ContextoElegibilidadRece,
    ElegibilidadReceError,
    ElegibilidadReceService,
)
from app.schemas.comprobante import (
    ErrorArcaFiscalResponse,
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
    guarda_actual_iniciada: bool = False
    resultado_recuperacion_pre_arca: Literal[
        "recuperada_pre_arca",
        "requiere_reconciliacion",
        "no_recuperable",
    ] | None = None
    guarda_rece_id: int | None = None
    guarda_rece_token: str | None = None

    def __post_init__(self) -> None:
        """Conserva compatibilidad al construir una fase ya iniciada."""
        if self.iniciada:
            self.guarda_actual_iniciada = True

    @property
    def recuperacion_pre_arca_exitosa(self) -> bool | None:
        """Expone el resultado booleano histórico sin perder el triestado."""
        if self.resultado_recuperacion_pre_arca is None:
            return None
        return self.resultado_recuperacion_pre_arca == "recuperada_pre_arca"

    @property
    def recuperacion_requiere_reconciliacion(self) -> bool:
        """Indica que la recuperación conservó evidencia fiscal incierta."""
        return self.resultado_recuperacion_pre_arca == "requiere_reconciliacion"

    def marcar_iniciada(self) -> None:
        """Marca el cruce irreversible hacia la solicitud fiscal."""
        self.iniciada = True
        self.guarda_actual_iniciada = True

    def registrar_recuperacion_pre_arca(
        self,
        resultado: Literal[
            "recuperada_pre_arca",
            "requiere_reconciliacion",
            "no_recuperable",
        ],
    ) -> None:
        """Registra sin colapsar si el recovery abrió replay o inmovilizó."""
        self.resultado_recuperacion_pre_arca = resultado

    def registrar_guarda_pre_arca(
        self,
        guarda: PuntoVentaGuardaEmisionRece,
    ) -> None:
        """Conserva identidad y token de la única guarda creada por esta llamada."""
        self.guarda_rece_id = int(guarda.id)
        self.guarda_rece_token = str(guarda.token)
        self.guarda_actual_iniciada = False
        self.resultado_recuperacion_pre_arca = None

    def adoptar_guarda(self, otra_fase: "FaseSolicitudArca") -> None:
        """Propaga la guarda creada por un subflujo de la misma llamada."""
        if (
            otra_fase.guarda_rece_id is not None
            and otra_fase.guarda_rece_token is not None
        ):
            self.guarda_rece_id = otra_fase.guarda_rece_id
            self.guarda_rece_token = otra_fase.guarda_rece_token
            self.guarda_actual_iniciada = otra_fase.guarda_actual_iniciada
            self.resultado_recuperacion_pre_arca = (
                otra_fase.resultado_recuperacion_pre_arca
            )
        self.iniciada = self.iniciada or otra_fase.iniciada


@dataclass(frozen=True)
class DiagnosticoNumeracion:
    """Describe la relación entre la historia local y la numeración de ARCA."""

    ultimo_local: int
    ultimo_arca: int
    proximo_local: int
    proximo_arca: int
    proximo_numero: int | None
    estado: Literal["alineada", "arca_adelantada", "local_adelantada"]

    @property
    def emision_habilitada(self) -> bool:
        """Indica si el diagnóstico ofrece un próximo número fiscal seguro."""
        return self.proximo_numero is not None


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
        contexto_rece: ContextoElegibilidadRece | None = None,
        contextos_operacion: list[ContextoElegibilidadRece] | None = None,
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
                contexto_rece=contexto_rece,
                contextos_operacion=contextos_operacion,
                fase_solicitud_arca=fase_solicitud_arca,
            )

    async def emitir_comprobantes_lote(
        self,
        requests: list[EmitirComprobanteRequest],
        max_registros: int | None = None,
        contextos: list[dict[str, object]] | None = None,
        fase_solicitud_arca: FaseSolicitudArca | None = None,
        commit_rechazo_global: bool = True,
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
                commit_rechazo_global=commit_rechazo_global,
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

    async def verificar_numeracion_segura_para_emision(
        self,
        *,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
    ) -> dict[str, int | str]:
        """Diagnostica contra ARCA una numeración segura para emitir después."""
        empresa = await self._obtener_empresa(empresa_id)
        if not empresa:
            raise ValidationError("Empresa no encontrada")

        punto_venta = await self._obtener_punto_venta(punto_venta_id, empresa_id)
        if punto_venta is None:
            raise ValidationError("Punto de venta no encontrado para la empresa activa")

        await ElegibilidadReceService(self.db).exigir_contexto_preautorizacion(
            empresa_id=empresa_id,
            punto_venta_id=punto_venta.id,
            ambiente=settings.arca_env,
            tipo_comprobante=tipo_comprobante,
        )

        certificado = await self._obtener_certificado_activo(empresa_id)
        await self.db.commit()
        ticket = await self._obtener_ticket_acceso(empresa, certificado)
        wsfe_client = WSFEv1Client(
            ambiente=self._get_arca_ambiente(),
            ticket=ticket,
            cuit=empresa.cuit,
        )
        await self._validar_punto_venta_habilitado(wsfe_client, punto_venta.numero)
        diagnostico = await self._obtener_diagnostico_numeracion(
            empresa_id,
            punto_venta_id,
            tipo_comprobante,
            wsfe_client=wsfe_client,
            punto_venta_numero=punto_venta.numero,
        )
        if diagnostico.estado == "local_adelantada":
            raise ValidationError(
                "La numeración local está adelantada respecto de ARCA. "
                "Revisá los comprobantes emitidos antes de continuar."
            )
        if (
            diagnostico.estado not in {"alineada", "arca_adelantada"}
            or diagnostico.proximo_numero is None
        ):
            raise ValidationError("No se pudo determinar una numeración fiscal segura")
        return {
            "empresa_id": empresa_id,
            "punto_venta_id": punto_venta_id,
            "punto_venta_numero": punto_venta.numero,
            "tipo_comprobante": tipo_comprobante,
            "ultimo_local": diagnostico.ultimo_local,
            "ultimo_arca": diagnostico.ultimo_arca,
            "proximo_local": diagnostico.proximo_local,
            "proximo_arca": diagnostico.proximo_arca,
            "proximo_numero": diagnostico.proximo_numero,
            "estado": diagnostico.estado,
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

        if self._bloqueo_preautorizacion(
            empresa_id=intento.empresa_id,
            punto_venta_id=intento.punto_venta_id,
            punto_venta_numero=intento.punto_venta_numero,
            tipo_comprobante=intento.tipo_comprobante,
        ):
            return self._respuesta_intento_requiere_reconciliacion(intento)

        if await self._guarda_activa_bloquea_reconciliacion_stale(intento):
            await self.db.refresh(intento)
            return self._respuesta_intento_requiere_reconciliacion(intento)
        await self.db.refresh(intento)

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
        contextos: list[dict[str, object]] | None = None,
        fase_solicitud_arca: FaseSolicitudArca | None = None,
        commit_rechazo_global: bool = True,
    ) -> list[EmitirComprobanteResponse]:
        """Ejecuta la emisión batch asumiendo que el lock local ya fue tomado."""
        fase_solicitud_arca = fase_solicitud_arca or FaseSolicitudArca()
        arca_iniciada_en_esta_llamada = False
        elegibilidad = ElegibilidadReceService(self.db)
        guarda: PuntoVentaGuardaEmisionRece | None = None
        intentos: list[IntentoEmisionFiscal] = []
        intento_ids_durables: list[int] = []
        guarda_id_durable: int | None = None
        resultados_arca = []
        try:
            requests = [self.normalizar_receptor(request) for request in requests]
            self._validar_lote_homogeneo(requests, max_registros=max_registros)
            if contextos is None or len(contextos) != len(requests):
                raise ElegibilidadReceError(
                    "El sublote no tiene operación y snapshots RECE completos."
                )

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
            punto_venta_numero = punto_venta.numero
            try:
                contextos_sublote = [
                    contexto["contexto_rece"] for contexto in contextos
                ]
                if not all(
                    isinstance(contexto, ContextoElegibilidadRece)
                    for contexto in contextos_sublote
                ):
                    raise ElegibilidadReceError(
                        "El sublote no conserva snapshots RECE tipados."
                    )
                contexto_rece = contextos_sublote[0]
                if any(contexto != contexto_rece for contexto in contextos_sublote):
                    raise ElegibilidadReceError(
                        "Un sublote ARCA no puede mezclar snapshots RECE distintos."
                    )
                operacion_ids = {contexto.get("operacion_id") for contexto in contextos}
                if len(operacion_ids) != 1 or not isinstance(
                    next(iter(operacion_ids)), int
                ):
                    raise ElegibilidadReceError(
                        "El sublote no pertenece a una única operación durable."
                    )
                operacion_id = int(next(iter(operacion_ids)))
                contextos_operacion = contextos[0].get("contextos_operacion")
                if not isinstance(contextos_operacion, list) or not all(
                    isinstance(contexto, ContextoElegibilidadRece)
                    for contexto in contextos_operacion
                ):
                    raise ElegibilidadReceError(
                        "La operación no conserva su membresía RECE completa."
                    )
                digest_operacion = elegibilidad.calcular_digest_contextos(
                    contextos_operacion
                )
                if any(
                    not isinstance(contexto.get("contextos_operacion"), list)
                    or elegibilidad.calcular_digest_contextos(
                        contexto["contextos_operacion"]
                    )
                    != digest_operacion
                    for contexto in contextos
                ):
                    raise ElegibilidadReceError(
                        "Los comprobantes no comparten la membresía RECE confirmada."
                    )
                actual = await elegibilidad.exigir_contexto_preautorizacion(
                    empresa_id=primer_request.empresa_id,
                    punto_venta_id=punto_venta.id,
                    ambiente=contexto_rece.ambiente,
                    tipo_comprobante=primer_request.tipo_comprobante,
                )
                if actual != contexto_rece:
                    raise ElegibilidadReceError(
                        "La acreditación RECE cambió después de confirmar el sublote."
                    )
                await elegibilidad.validar_operacion_para_continuar(
                    operacion_id=operacion_id,
                    empresa_id=primer_request.empresa_id,
                    contextos_esperados=contextos_operacion,
                )
            except (KeyError, TypeError, ValueError, ElegibilidadReceError) as exc:
                error = (
                    exc
                    if isinstance(exc, ElegibilidadReceError)
                    else ElegibilidadReceError(
                        "El sublote no tiene un contexto RECE válido."
                    )
                )
                return [
                    self._respuesta_rechazo_elegibilidad(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        totales=totales,
                        error=error,
                    )
                    for request, totales in zip(requests, totales_por_request)
                ]

            certificado = await self._obtener_certificado_activo(
                primer_request.empresa_id
            )

            await self.db.commit()
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
            diagnostico = await self._obtener_diagnostico_numeracion(
                primer_request.empresa_id,
                primer_request.punto_venta_id,
                primer_request.tipo_comprobante,
                wsfe_client,
                punto_venta_numero,
            )
            if diagnostico.estado == "local_adelantada":
                raise ValidationError(
                    "La numeración local está adelantada respecto de ARCA. "
                    "Revisá los comprobantes emitidos antes de continuar."
                )
            if diagnostico.proximo_numero is None:
                raise ValidationError(
                    "No se pudo determinar una numeración fiscal segura"
                )
            proximo = diagnostico.proximo_numero

            idempotencia = IdempotenciaFiscalService(self.db)
            try:
                async with elegibilidad.bloqueo_local_punto(
                    empresa_id=primer_request.empresa_id,
                    punto_venta_id=punto_venta.id,
                ):
                    await self._tomar_lock_numeracion(
                        primer_request.empresa_id,
                        primer_request.punto_venta_id,
                        primer_request.tipo_comprobante,
                    )
                    actual = await elegibilidad.exigir_contexto_preautorizacion(
                        empresa_id=primer_request.empresa_id,
                        punto_venta_id=punto_venta.id,
                        ambiente=contexto_rece.ambiente,
                        tipo_comprobante=primer_request.tipo_comprobante,
                        bloquear=True,
                    )
                    if actual != contexto_rece:
                        raise ElegibilidadReceError(
                            "La acreditación RECE cambió antes de reservar el sublote."
                        )
                    await elegibilidad.validar_operacion_para_continuar(
                        operacion_id=operacion_id,
                        empresa_id=primer_request.empresa_id,
                        contextos_esperados=contextos_operacion,
                    )
                    guarda = await elegibilidad.crear_guarda_pre_arca(
                        operacion_id=operacion_id,
                        contexto=contexto_rece,
                        contextos_operacion=contextos_operacion,
                    )
                    for index, (request, totales, metadata) in enumerate(
                        zip(requests, totales_por_request, contextos)
                    ):
                        if not isinstance(
                            metadata.get("lote_id"), int
                        ) or not isinstance(metadata.get("grupo_id"), int):
                            raise ElegibilidadReceError(
                                "El intento batch no pertenece a un lote y grupo durables."
                            )
                        intento = await idempotencia.crear_intento_emision(
                            request=request,
                            punto_venta=punto_venta,
                            numero_planificado=proximo + index,
                            total=totales["total"],
                            operacion_id=operacion_id,
                            usuario_id=metadata.get("usuario_id"),
                            lote_id=metadata.get("lote_id"),
                            grupo_id=metadata.get("grupo_id"),
                            contexto_rece=contexto_rece,
                            guarda_rece_id=guarda.id,
                            commit=False,
                        )
                        intentos.append(intento)
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
                    fase_solicitud_arca.registrar_guarda_pre_arca(guarda)
                    intento_ids_durables = [int(intento.id) for intento in intentos]
                    guarda_id_durable = int(guarda.id)
                    await self.db.commit()
            except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
                await self._rollback_seguro("reservas_batch_pre_arca")
                raise
            except Exception:
                logger.exception(
                    "Fallo preparando reservas fiscales del sublote antes de ARCA"
                )
                await self._rollback_seguro("reservas_batch_pre_arca_fallidas")
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

            respuestas_pre_arca = (
                await self._confirmar_reservas_batch_antes_de_solicitar_cae(
                    requests=requests,
                    totales_por_request=totales_por_request,
                    wsfe_client=wsfe_client,
                    punto_venta_numero=punto_venta_numero,
                    primer_numero_planificado=proximo,
                )
            )
            if respuestas_pre_arca is not None:
                await self._persistir_intentos_y_guarda_rece(
                    idempotencia=idempotencia,
                    intentos=intentos,
                    respuestas=respuestas_pre_arca,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    contexto="preflight_numeracion_batch_antes_arca",
                )
                return respuestas_pre_arca

            try:
                await elegibilidad.marcar_arca_iniciada(
                    guarda=guarda,
                    contexto=contexto_rece,
                    tipo_comprobante=primer_request.tipo_comprobante,
                )
                fase_solicitud_arca.marcar_iniciada()
                arca_iniciada_en_esta_llamada = True
                resultados_arca_sin_ordenar = await wsfe_client.fe_cae_solicitar_lote(
                    arca_requests
                )
                resultados_arca = self._ordenar_resultados_arca_batch_por_numero(
                    arca_requests,
                    resultados_arca_sin_ordenar,
                )
            except ElegibilidadReceError as exc:
                await self._rollback_seguro(
                    "revalidacion_rece_batch_inmediatamente_antes_arca"
                )
                intentos, guarda = await self._recargar_intentos_y_guarda_rece(
                    intento_ids=intento_ids_durables,
                    guarda_id=guarda_id_durable,
                )
                respuestas_bloqueadas = [
                    self._respuesta_rechazo_elegibilidad(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        totales=totales,
                        error=exc,
                    )
                    for request, totales in zip(requests, totales_por_request)
                ]
                await self._persistir_intentos_y_guarda_rece(
                    idempotencia=idempotencia,
                    intentos=intentos,
                    respuestas=respuestas_bloqueadas,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    contexto="revalidacion_rece_batch_inmediatamente_antes_arca",
                )
                return respuestas_bloqueadas
            except ArcaErrorGlobalEstructurado as exc:
                if clasificar_error_global_fecae(exc) != "rechazo_global_excluyente":
                    respuestas_inciertas = [
                        self._respuesta_batch_sin_detalle_requiere_reconciliacion(
                            request=request,
                            punto_venta_numero=punto_venta_numero,
                            numero=arca_request.cbte_desde,
                            totales=totales,
                            error=(
                                "ARCA devolvió una respuesta global que no cumple "
                                "el contrato terminal verificable."
                            ),
                            errores_arca=self._errores_globales_sanitarios(exc),
                        )
                        for request, arca_request, totales in zip(
                            requests,
                            arca_requests,
                            totales_por_request,
                        )
                    ]
                    await self._persistir_intentos_y_guarda_rece(
                        idempotencia=idempotencia,
                        intentos=intentos,
                        respuestas=respuestas_inciertas,
                        guarda=guarda,
                        fase="reconciliacion",
                        contexto="respuesta_global_incierta_arca",
                        commit=commit_rechazo_global,
                    )
                    return respuestas_inciertas

                respuestas_globales = [
                    self._respuesta_rechazo_global_excluyente(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=arca_request.cbte_desde,
                        totales=totales,
                    )
                    for request, arca_request, totales in zip(
                        requests,
                        arca_requests,
                        totales_por_request,
                    )
                ]
                await self._cerrar_rechazo_global_intentos_y_guarda(
                    idempotencia=idempotencia,
                    intentos=intentos,
                    respuestas=respuestas_globales,
                    guarda=guarda,
                    commit=commit_rechazo_global,
                )
                return respuestas_globales
            except (ArcaServiceError, ArcaValidationError) as exc:
                logger.error("Error al solicitar CAE por sublote: %s", str(exc))
                respuestas_inciertas = [
                    self._respuesta_batch_sin_detalle_requiere_reconciliacion(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=arca_request.cbte_desde,
                        totales=totales,
                        error="ARCA no devolvió un resultado terminal verificable.",
                    )
                    for request, arca_request, totales in zip(
                        requests,
                        arca_requests,
                        totales_por_request,
                    )
                ]
                await self._persistir_intentos_y_guarda_rece(
                    idempotencia=idempotencia,
                    intentos=intentos,
                    respuestas=respuestas_inciertas,
                    guarda=guarda,
                    fase="reconciliacion",
                    contexto="respuesta_incierta_arca",
                    commit=commit_rechazo_global,
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
                if persistencia_bloqueada:
                    respuestas.append(
                        self._respuesta_post_arca_requiere_reconciliacion(
                            request=request,
                            punto_venta_numero=punto_venta_numero,
                            numero=arca_request.cbte_desde,
                            totales=totales,
                            resultado_arca=resultado,
                            mensaje=(
                                "El sublote requiere reconciliación porque su "
                                "persistencia local dejó de ser atómica"
                            ),
                            errores=[
                                "No reintentes hasta reconciliar todo el sublote."
                            ],
                        )
                    )
                    continue
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
                        persistencia_bloqueada = True
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
                        commit=False,
                    )
                except IntegrityError:
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
                            ERROR_INTERNO_EMISION_PUBLICO,
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
                            commit=False,
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

            if persistencia_bloqueada:
                await self._rollback_seguro("sublote_post_arca_reconciliacion")
                respuestas = []
                for request, arca_request, totales, resultado in zip(
                    requests,
                    arca_requests,
                    totales_por_request,
                    resultados_arca,
                ):
                    respuesta = self._respuesta_post_arca_requiere_reconciliacion(
                        request=request,
                        punto_venta_numero=punto_venta_numero,
                        numero=arca_request.cbte_desde,
                        totales=totales,
                        resultado_arca=resultado,
                        mensaje=(
                            "El resultado ARCA del sublote no pudo persistirse "
                            "atómicamente"
                        ),
                        errores=["No reintentes hasta reconciliar todo el sublote."],
                    )
                    respuestas.append(respuesta)
                intentos, guarda = await self._recargar_intentos_y_guarda_rece(
                    intento_ids=intento_ids_durables,
                    guarda_id=guarda_id_durable,
                )
                await self._persistir_intentos_y_guarda_rece(
                    idempotencia=idempotencia,
                    intentos=intentos,
                    respuestas=respuestas,
                    guarda=guarda,
                    fase="reconciliacion",
                    contexto="persistencia_batch_post_arca",
                    commit=commit_rechazo_global,
                )
                return respuestas

            await self._persistir_intentos_y_guarda_rece(
                idempotencia=idempotencia,
                intentos=intentos,
                respuestas=respuestas,
                guarda=guarda,
                fase="cerrada_terminal",
                contexto="cierre_terminal_batch",
                commit=commit_rechazo_global,
            )
            return respuestas

        except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
            raise
        except ElegibilidadReceError as exc:
            respuestas_elegibilidad = [
                self._respuesta_rechazo_elegibilidad(
                    request=request,
                    punto_venta_numero=0,
                    totales={"total": Decimal("0")},
                    error=exc,
                )
                for request in requests
            ]
            if guarda is not None and intentos:
                await self._persistir_intentos_y_guarda_rece(
                    idempotencia=idempotencia,
                    intentos=intentos,
                    respuestas=respuestas_elegibilidad,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    contexto="elegibilidad_batch_pre_arca",
                )
            return respuestas_elegibilidad
        except ValidationError as e:
            logger.warning("Error de validación en sublote: %s", str(e))
            respuestas_validacion = [
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
            if guarda is not None and intentos:
                await self._persistir_intentos_y_guarda_rece(
                    idempotencia=idempotencia,
                    intentos=intentos,
                    respuestas=respuestas_validacion,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    contexto="validacion_batch_pre_arca",
                )
            return respuestas_validacion
        except Exception:
            logger.exception("Error inesperado al emitir sublote")
            if arca_iniciada_en_esta_llamada:
                resultados_por_numero = {
                    int(resultado.numero_comprobante): resultado
                    for resultado in resultados_arca
                }
                respuestas = []
                for index, (request, totales) in enumerate(
                    zip(requests, totales_por_request)
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
                    respuestas.append(respuesta)
                if guarda is not None and intentos:
                    await self._persistir_intentos_y_guarda_rece(
                        idempotencia=idempotencia,
                        intentos=intentos,
                        respuestas=respuestas,
                        guarda=guarda,
                        fase="reconciliacion",
                        contexto="excepcion_inesperada_post_arca",
                        commit=commit_rechazo_global,
                    )
                return respuestas
            respuestas_inesperadas = [
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
            if guarda is not None and intentos:
                await self._persistir_intentos_y_guarda_rece(
                    idempotencia=idempotencia,
                    intentos=intentos,
                    respuestas=respuestas_inesperadas,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    contexto="excepcion_inesperada_batch_pre_arca",
                )
            return respuestas_inesperadas

    async def _emitir_comprobante_locked(
        self,
        request: EmitirComprobanteRequest,
        commit: bool = True,
        operacion_id: int | None = None,
        usuario_id: int | None = None,
        lote_id: int | None = None,
        grupo_id: int | None = None,
        contexto_rece: ContextoElegibilidadRece | None = None,
        contextos_operacion: list[ContextoElegibilidadRece] | None = None,
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
        elegibilidad = ElegibilidadReceService(self.db)
        intento: IntentoEmisionFiscal | None = None
        guarda = None
        intento_id_durable: int | None = None
        guarda_id_durable: int | None = None
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
            if operacion_id is None or contexto_rece is None:
                return self._respuesta_rechazo_elegibilidad(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    totales=totales,
                    error=ElegibilidadReceError(
                        "La emisión no tiene una operación y snapshot RECE durables."
                    ),
                )
            contextos_operacion = contextos_operacion or [contexto_rece]
            if contexto_rece not in contextos_operacion:
                return self._respuesta_rechazo_elegibilidad(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    totales=totales,
                    error=ElegibilidadReceError(
                        "El punto de venta no pertenece a la membresía de la operación."
                    ),
                )
            try:
                actual = await elegibilidad.exigir_contexto_preautorizacion(
                    empresa_id=request.empresa_id,
                    punto_venta_id=punto_venta.id,
                    ambiente=contexto_rece.ambiente,
                    tipo_comprobante=request.tipo_comprobante,
                )
                if actual != contexto_rece:
                    raise ElegibilidadReceError(
                        "La acreditación RECE cambió después de confirmar la emisión."
                    )
                await elegibilidad.validar_operacion_para_continuar(
                    operacion_id=operacion_id,
                    empresa_id=request.empresa_id,
                    contextos_esperados=contextos_operacion,
                )
            except ElegibilidadReceError as exc:
                return self._respuesta_rechazo_elegibilidad(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    totales=totales,
                    error=exc,
                )

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
            await self.db.commit()
            ticket = await self._obtener_ticket_acceso(empresa, certificado)
            wsfe_client = WSFEv1Client(
                ambiente=self._get_arca_ambiente(),
                ticket=ticket,
                cuit=empresa.cuit,
            )
            await self._validar_punto_venta_habilitado(wsfe_client, punto_venta_numero)
            diagnostico = await self._obtener_diagnostico_numeracion(
                request.empresa_id,
                request.punto_venta_id,
                request.tipo_comprobante,
                wsfe_client,
                punto_venta_numero,
            )
            if diagnostico.estado == "local_adelantada":
                raise ValidationError(
                    "La numeración local está adelantada respecto de ARCA. "
                    "Revisá los comprobantes emitidos antes de continuar."
                )
            if diagnostico.proximo_numero is None:
                raise ValidationError(
                    "No se pudo determinar una numeración fiscal segura"
                )
            proximo = diagnostico.proximo_numero

            # 5. Crear guarda e intento en una única transacción durable.
            try:
                async with elegibilidad.bloqueo_local_punto(
                    empresa_id=request.empresa_id,
                    punto_venta_id=punto_venta.id,
                ):
                    await self._tomar_lock_numeracion(
                        request.empresa_id,
                        request.punto_venta_id,
                        request.tipo_comprobante,
                    )
                    actual = await elegibilidad.exigir_contexto_preautorizacion(
                        empresa_id=request.empresa_id,
                        punto_venta_id=punto_venta.id,
                        ambiente=contexto_rece.ambiente,
                        tipo_comprobante=request.tipo_comprobante,
                        bloquear=True,
                    )
                    if actual != contexto_rece:
                        raise ElegibilidadReceError(
                            "La acreditación RECE cambió antes de reservar la emisión."
                        )
                    await elegibilidad.validar_operacion_para_continuar(
                        operacion_id=operacion_id,
                        empresa_id=request.empresa_id,
                        contextos_esperados=contextos_operacion,
                    )
                    guarda = await elegibilidad.crear_guarda_pre_arca(
                        operacion_id=operacion_id,
                        contexto=contexto_rece,
                        contextos_operacion=contextos_operacion,
                    )
                    intento = await idempotencia.crear_intento_emision(
                        request=request,
                        punto_venta=punto_venta,
                        numero_planificado=proximo,
                        total=totales["total"],
                        operacion_id=operacion_id,
                        usuario_id=usuario_id,
                        lote_id=lote_id,
                        grupo_id=grupo_id,
                        contexto_rece=contexto_rece,
                        guarda_rece_id=guarda.id,
                        commit=False,
                    )
                    fase_solicitud_arca.registrar_guarda_pre_arca(guarda)
                    intento_id_durable = int(intento.id)
                    guarda_id_durable = int(guarda.id)
                    await self.db.commit()
            except ElegibilidadReceError as exc:
                await self.db.rollback()
                return self._respuesta_rechazo_elegibilidad(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    totales=totales,
                    error=exc,
                )
            except IntegrityError:
                await self.db.rollback()
                return self._respuesta_rechazo_elegibilidad(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    totales=totales,
                    error=ElegibilidadReceError(
                        "El punto de venta ya tiene una solicitud fiscal activa.",
                        categoria="conflicto_guarda_rece_activa",
                    ),
                )

            arca_request = self._armar_request_arca(
                request, proximo, totales, punto_venta_numero
            )
            respuesta_pre_arca = await self._confirmar_reserva_antes_de_solicitar_cae(
                request=request,
                wsfe_client=wsfe_client,
                punto_venta_numero=punto_venta_numero,
                numero_planificado=proximo,
                total=totales["total"],
            )
            if respuesta_pre_arca is not None:
                await self._persistir_intento_y_guarda_rece(
                    idempotencia=idempotencia,
                    intento=intento,
                    respuesta=respuesta_pre_arca,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    commit=commit,
                    contexto="preflight_numeracion_antes_arca",
                )
                return respuesta_pre_arca

            # 6. Solicitar CAE
            resultado = None
            try:
                await elegibilidad.marcar_arca_iniciada(
                    guarda=guarda,
                    contexto=contexto_rece,
                    tipo_comprobante=request.tipo_comprobante,
                )
                fase_solicitud_arca.marcar_iniciada()
                arca_iniciada_en_esta_llamada = True
                resultado = await wsfe_client.fe_cae_solicitar(arca_request)

            except ElegibilidadReceError as exc:
                await self._rollback_seguro(
                    "revalidacion_rece_inmediatamente_antes_arca"
                )
                [intento], guarda = await self._recargar_intentos_y_guarda_rece(
                    intento_ids=[intento_id_durable],
                    guarda_id=guarda_id_durable,
                )
                respuesta = self._respuesta_rechazo_elegibilidad(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    totales=totales,
                    error=exc,
                )
                await self._persistir_intento_y_guarda_rece(
                    idempotencia=idempotencia,
                    intento=intento,
                    respuesta=respuesta,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    commit=commit,
                    contexto="revalidacion_rece_inmediatamente_antes_arca",
                )
                return respuesta
            except ArcaErrorGlobalEstructurado as exc:
                if clasificar_error_global_fecae(exc) != "rechazo_global_excluyente":
                    respuesta = EmitirComprobanteResponse(
                        exito=False,
                        tipo_comprobante=request.tipo_comprobante,
                        punto_venta=punto_venta_numero,
                        numero=proximo,
                        fecha=request.fecha_emision,
                        total=totales["total"],
                        mensaje=(
                            "FactuFlow no pudo confirmar el resultado de la "
                            "solicitud a ARCA"
                        ),
                        errores=[
                            "ARCA devolvió una respuesta global que no cumple el "
                            "contrato terminal verificable. No reintentes hasta "
                            "reconciliar."
                        ],
                        requiere_reconciliacion=True,
                        categoria_error="arca_respuesta_incierta",
                        errores_arca=self._errores_globales_sanitarios(exc),
                    )
                    await self._persistir_intento_y_guarda_rece(
                        idempotencia=idempotencia,
                        intento=intento,
                        respuesta=respuesta,
                        guarda=guarda,
                        fase="reconciliacion",
                        commit=commit,
                        contexto="respuesta_global_incierta_arca",
                    )
                    return respuesta

                respuesta = self._respuesta_rechazo_global_excluyente(
                    request=request,
                    punto_venta_numero=punto_venta_numero,
                    numero=proximo,
                    totales=totales,
                )
                await self._cerrar_rechazo_global_intentos_y_guarda(
                    idempotencia=idempotencia,
                    intentos=[intento],
                    respuestas=[respuesta],
                    guarda=guarda,
                    commit=commit,
                )
                return respuesta
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
                        "ARCA no devolvió un resultado terminal verificable.",
                    ],
                    requiere_reconciliacion=True,
                    categoria_error="arca_respuesta_incierta",
                )
                await self._persistir_intento_y_guarda_rece(
                    idempotencia=idempotencia,
                    intento=intento,
                    respuesta=respuesta,
                    guarda=guarda,
                    fase="reconciliacion",
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
                await self._persistir_intento_y_guarda_rece(
                    idempotencia=idempotencia,
                    intento=intento,
                    respuesta=respuesta_no_aprobada,
                    guarda=guarda,
                    fase="cerrada_terminal",
                    commit=commit,
                    contexto="arca_no_aprobado",
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
                    commit=False,
                )
            except IntegrityError:
                await self._rollback_seguro("integrity_individual_post_arca")
                [intento], guarda = await self._recargar_intentos_y_guarda_rece(
                    intento_ids=[intento_id_durable],
                    guarda_id=guarda_id_durable,
                )
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
                        ERROR_INTERNO_EMISION_PUBLICO,
                    ],
                )
                await self._persistir_intento_y_guarda_rece(
                    idempotencia=idempotencia,
                    intento=intento,
                    respuesta=respuesta,
                    guarda=guarda,
                    fase="reconciliacion",
                    commit=commit,
                    contexto="conflicto_numeracion_post_arca",
                )
                return respuesta
            except Exception:
                await self._rollback_seguro("persistencia_individual_post_arca")
                [intento], guarda = await self._recargar_intentos_y_guarda_rece(
                    intento_ids=[intento_id_durable],
                    guarda_id=guarda_id_durable,
                )
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
                await self._persistir_intento_y_guarda_rece(
                    idempotencia=idempotencia,
                    intento=intento,
                    respuesta=respuesta,
                    guarda=guarda,
                    fase="reconciliacion",
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
            await self._persistir_intento_y_guarda_rece(
                idempotencia=idempotencia,
                intento=intento,
                respuesta=respuesta,
                guarda=guarda,
                fase="cerrada_terminal",
                commit=commit,
                contexto="cierre_exitoso_post_arca",
            )
            return respuesta

        except DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS:
            raise
        except ValidationError as e:
            logger.warning(f"Error de validación: {str(e)}")
            respuesta_validacion = EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=0,
                numero=0,
                fecha=request.fecha_emision,
                total=Decimal("0"),
                mensaje="Error de validación",
                errores=[str(e)],
            )
            if intento is not None and guarda is not None:
                await self._persistir_intento_y_guarda_rece(
                    idempotencia=idempotencia,
                    intento=intento,
                    respuesta=respuesta_validacion,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    commit=True,
                    contexto="validacion_individual_pre_arca",
                )
            return respuesta_validacion
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
                if intento is not None and guarda is not None:
                    await self._persistir_intento_y_guarda_rece(
                        idempotencia=idempotencia,
                        intento=intento,
                        respuesta=respuesta,
                        guarda=guarda,
                        fase="reconciliacion",
                        commit=commit,
                        contexto="excepcion_inesperada_post_arca",
                    )
                return respuesta
            respuesta_inesperada = EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=0,
                numero=0,
                fecha=request.fecha_emision,
                total=Decimal("0"),
                mensaje="Error inesperado",
                errores=[ERROR_INTERNO_EMISION_PUBLICO],
            )
            if intento is not None and guarda is not None:
                await self._persistir_intento_y_guarda_rece(
                    idempotencia=idempotencia,
                    intento=intento,
                    respuesta=respuesta_inesperada,
                    guarda=guarda,
                    fase="cerrada_pre_arca",
                    commit=True,
                    contexto="excepcion_inesperada_individual_pre_arca",
                )
            return respuesta_inesperada

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

    async def obtener_diagnostico_numeracion(
        self,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
    ) -> DiagnosticoNumeracion:
        """Obtiene el diagnóstico local/ARCA para una emisión individual."""
        punto_venta = await self._obtener_punto_venta(punto_venta_id, empresa_id)
        if not punto_venta:
            raise ValidationError("Punto de venta no encontrado")

        await ElegibilidadReceService(self.db).exigir_contexto_preautorizacion(
            empresa_id=empresa_id,
            punto_venta_id=punto_venta.id,
            ambiente=settings.arca_env,
            tipo_comprobante=tipo_comprobante,
        )

        empresa = await self._obtener_empresa(empresa_id)
        if not empresa:
            raise ValidationError("Empresa no encontrada")
        certificado = await self._obtener_certificado_activo(empresa_id)
        await self.db.commit()
        ticket = await self._obtener_ticket_acceso(empresa, certificado)
        wsfe_client = WSFEv1Client(
            ambiente=self._get_arca_ambiente(),
            ticket=ticket,
            cuit=empresa.cuit,
        )
        return await self._obtener_diagnostico_numeracion(
            empresa_id,
            punto_venta_id,
            tipo_comprobante,
            wsfe_client,
            punto_venta.numero,
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

        await ElegibilidadReceService(self.db).exigir_contexto_preautorizacion(
            empresa_id=empresa_id,
            punto_venta_id=punto_venta.id,
            ambiente=settings.arca_env,
            tipo_comprobante=tipo_comprobante,
        )

        empresa = await self._obtener_empresa(empresa_id)
        certificado = await self._obtener_certificado_activo(empresa_id)
        await self.db.commit()
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

    async def _confirmar_reserva_antes_de_solicitar_cae(
        self,
        *,
        request: EmitirComprobanteRequest,
        wsfe_client: WSFEv1Client,
        punto_venta_numero: int,
        numero_planificado: int,
        total: Decimal,
    ) -> EmitirComprobanteResponse | None:
        """Revalida la numeración después de reservar y antes de solicitar CAE."""
        try:
            ultimo_arca = await wsfe_client.fe_comp_ultimo_autorizado(
                punto_venta_numero,
                request.tipo_comprobante,
            )
        except Exception:
            logger.exception(
                "No se pudo reconfirmar numeración antes de ARCA. "
                "empresa=%s pv=%s tipo=%s numero=%s",
                request.empresa_id,
                punto_venta_numero,
                request.tipo_comprobante,
                numero_planificado,
            )
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=punto_venta_numero,
                numero=numero_planificado,
                fecha=request.fecha_emision,
                total=total,
                mensaje="No se pudo reconfirmar la numeración fiscal antes de emitir",
                errores=[
                    "No se envió ninguna solicitud de CAE. Actualizá la numeración y volvé a confirmar la emisión."
                ],
                categoria_error="preflight_arca_no_disponible",
            )

        proximo_arca = ultimo_arca + 1
        if proximo_arca == numero_planificado:
            return None

        logger.warning(
            "La numeración ARCA cambió después de reservar el intento. "
            "empresa=%s pv=%s tipo=%s reservado=%s proximo_arca=%s",
            request.empresa_id,
            punto_venta_numero,
            request.tipo_comprobante,
            numero_planificado,
            proximo_arca,
        )
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero_planificado,
            fecha=request.fecha_emision,
            total=total,
            mensaje="La numeración de ARCA cambió antes de solicitar el CAE",
            errores=[
                "No se envió ninguna solicitud de CAE. Actualizá el próximo número y volvé a confirmar la emisión."
            ],
            categoria_error="numeracion_arca_cambio_pre_arca",
        )

    async def _confirmar_reservas_batch_antes_de_solicitar_cae(
        self,
        *,
        requests: list[EmitirComprobanteRequest],
        totales_por_request: list[dict],
        wsfe_client: WSFEv1Client,
        punto_venta_numero: int,
        primer_numero_planificado: int,
    ) -> list[EmitirComprobanteResponse] | None:
        """Revalida el inicio del rango batch después de reservarlo completo."""
        respuesta_base = await self._confirmar_reserva_antes_de_solicitar_cae(
            request=requests[0],
            wsfe_client=wsfe_client,
            punto_venta_numero=punto_venta_numero,
            numero_planificado=primer_numero_planificado,
            total=totales_por_request[0]["total"],
        )
        if respuesta_base is None:
            return None

        return [
            EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=punto_venta_numero,
                numero=primer_numero_planificado + index,
                fecha=request.fecha_emision,
                total=totales["total"],
                mensaje=respuesta_base.mensaje,
                errores=list(respuesta_base.errores),
                categoria_error=respuesta_base.categoria_error,
            )
            for index, (request, totales) in enumerate(
                zip(requests, totales_por_request)
            )
        ]

    def _respuesta_batch_sin_detalle_requiere_reconciliacion(
        self,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
        error: str,
        errores_arca: list[ErrorArcaFiscalResponse] | None = None,
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
            errores_arca=errores_arca or [],
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

    async def _obtener_diagnostico_numeracion(
        self,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
        wsfe_client: Optional[WSFEv1Client] = None,
        punto_venta_numero: Optional[int] = None,
    ) -> DiagnosticoNumeracion:
        """Compara la historia local con ARCA sin ocultar desfases legítimos."""
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
        ultimo_local = ultimo.numero if ultimo else 0
        proximo_local = ultimo_local + 1

        if not wsfe_client or punto_venta_numero is None:
            return DiagnosticoNumeracion(
                ultimo_local=ultimo_local,
                ultimo_arca=ultimo_local,
                proximo_local=proximo_local,
                proximo_arca=proximo_local,
                proximo_numero=proximo_local,
                estado="alineada",
            )

        ultimo_arca = await wsfe_client.fe_comp_ultimo_autorizado(
            punto_venta_numero,
            tipo_comprobante,
        )
        proximo_arca = ultimo_arca + 1

        if proximo_local > proximo_arca:
            logger.error(
                "La numeración local está adelantada respecto de ARCA. "
                "empresa=%s pv=%s tipo=%s ultimo_local=%s ultimo_arca=%s",
                empresa_id,
                punto_venta_numero,
                tipo_comprobante,
                ultimo_local,
                ultimo_arca,
            )
            return DiagnosticoNumeracion(
                ultimo_local=ultimo_local,
                ultimo_arca=ultimo_arca,
                proximo_local=proximo_local,
                proximo_arca=proximo_arca,
                proximo_numero=None,
                estado="local_adelantada",
            )

        if proximo_local < proximo_arca:
            logger.info(
                "ARCA registra historia anterior ausente localmente. "
                "empresa=%s pv=%s tipo=%s ultimo_local=%s ultimo_arca=%s",
                empresa_id,
                punto_venta_numero,
                tipo_comprobante,
                ultimo_local,
                ultimo_arca,
            )
            return DiagnosticoNumeracion(
                ultimo_local=ultimo_local,
                ultimo_arca=ultimo_arca,
                proximo_local=proximo_local,
                proximo_arca=proximo_arca,
                proximo_numero=proximo_arca,
                estado="arca_adelantada",
            )

        return DiagnosticoNumeracion(
            ultimo_local=ultimo_local,
            ultimo_arca=ultimo_arca,
            proximo_local=proximo_local,
            proximo_arca=proximo_arca,
            proximo_numero=proximo_arca,
            estado="alineada",
        )

    async def _obtener_proximo_numero(
        self,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int,
        wsfe_client: Optional[WSFEv1Client] = None,
        punto_venta_numero: Optional[int] = None,
    ) -> int:
        """Obtiene un próximo número exigiendo alineación local y ARCA."""
        diagnostico = await self._obtener_diagnostico_numeracion(
            empresa_id,
            punto_venta_id,
            tipo_comprobante,
            wsfe_client,
            punto_venta_numero,
        )
        if diagnostico.estado == "local_adelantada":
            raise ValidationError(
                "La numeración local está adelantada respecto de ARCA. "
                "Revisá los comprobantes emitidos antes de continuar."
            )
        if diagnostico.estado == "arca_adelantada":
            raise ReconciliacionNumeracionError(
                ultimo_local=diagnostico.ultimo_local,
                ultimo_arca=diagnostico.ultimo_arca,
                proximo_local=diagnostico.proximo_local,
                proximo_arca=diagnostico.proximo_arca,
            )
        if diagnostico.proximo_numero is None:
            raise ValidationError("No se pudo determinar una numeración fiscal segura")
        return diagnostico.proximo_numero

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
        """Construye respuesta idempotente para un intento terminal verificable."""
        if (
            intento.estado == "rechazado_arca"
            and intento.categoria_error == "arca_rechazo_global_excluyente"
        ):
            errores_raw = intento.errores_arca_json
            if not isinstance(errores_raw, list) or len(errores_raw) != 1:
                return None
            try:
                error_arca = ErrorArcaFiscalResponse.model_validate(errores_raw[0])
            except PydanticValidationError:
                return None
            if (
                not isinstance(error_arca.codigo, int)
                or isinstance(error_arca.codigo, bool)
                or error_arca.codigo != 10005
                or error_arca.alcance != "global"
                or error_arca.mensaje
                != "El punto de venta no está dado de alta como RECE en ARCA."
            ):
                return None
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=intento.tipo_comprobante,
                punto_venta=intento.punto_venta_numero,
                numero=intento.numero_planificado or 0,
                fecha=intento.fecha_emision,
                total=Decimal(str(intento.total)),
                mensaje="ARCA rechazó el requerimiento completo antes de autorizar.",
                errores=[
                    "Revisá la habilitación RECE del punto de venta antes de iniciar otra emisión."
                ],
                errores_arca=[error_arca],
                requiere_reconciliacion=False,
                categoria_error="arca_rechazo_global_excluyente",
            )
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
        if await self._guarda_activa_bloquea_reconciliacion_stale(intento):
            return intento
        await self.db.refresh(intento)
        try:
            consulta_arca = await wsfe_client.fe_comp_consultar(
                punto_venta=punto_venta_numero,
                tipo_cbte=intento.tipo_comprobante,
                numero=intento.numero_planificado,
            )
        except ArcaServiceError as exc:
            if await self._guarda_activa_bloquea_reconciliacion_stale(
                intento,
                retener_locks=True,
            ):
                await self.db.refresh(intento)
                return intento
            await self.db.refresh(intento)
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

        if await self._guarda_activa_bloquea_reconciliacion_stale(
            intento,
            retener_locks=True,
        ):
            await self.db.refresh(intento)
            return intento
        await self.db.refresh(intento)
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

    async def _guarda_activa_bloquea_reconciliacion_stale(
        self,
        intento: IntentoEmisionFiscal,
        *,
        retener_locks: bool = False,
    ) -> bool:
        """Reserva solo un intento legacy; cualquier snapshot RECE queda inmóvil."""
        intento_id = int(intento.id)
        operacion_id = intento.operacion_id
        if operacion_id is None:
            await self.db.rollback()
            intento_actual = (
                await self.db.execute(
                    select(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.id == intento_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            bloquea = (
                intento_actual is None
                or intento_actual.estado != "en_proceso"
                or intento_actual.operacion_id is not None
                or any(
                    valor is not None
                    for valor in (
                        intento_actual.ambiente,
                        intento_actual.punto_venta_elegibilidad_revision_id,
                        intento_actual.punto_venta_revision_fiscal,
                        intento_actual.guarda_rece_id,
                    )
                )
            )
            if bloquea or not retener_locks:
                await self.db.commit()
            return bloquea
        await self.db.rollback()
        fila_operacion = (
            await self.db.execute(
                select(
                    OperacionIdempotente,
                    OperacionIdempotente.response_json.is_(None).label(
                        "respuesta_es_sql_null"
                    ),
                )
                .where(
                    OperacionIdempotente.id == operacion_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        intentos_operacion = list(
            (
                await self.db.execute(
                    select(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.operacion_id == operacion_id)
                    .order_by(IntentoEmisionFiscal.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        guardas = list(
            (
                await self.db.execute(
                    select(PuntoVentaGuardaEmisionRece)
                    .where(PuntoVentaGuardaEmisionRece.operacion_id == operacion_id)
                    .order_by(PuntoVentaGuardaEmisionRece.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        intento_actual = next(
            (
                intento_operacion
                for intento_operacion in intentos_operacion
                if int(intento_operacion.id) == intento_id
            ),
            None,
        )
        operacion = fila_operacion[0] if fila_operacion is not None else None
        snapshot_rece_presente = intento_actual is not None and any(
            valor is not None
            for valor in (
                intento_actual.ambiente,
                intento_actual.punto_venta_elegibilidad_revision_id,
                intento_actual.punto_venta_revision_fiscal,
                intento_actual.guarda_rece_id,
            )
        )
        bloquea = (
            operacion is None
            or operacion.estado != "en_proceso"
            or operacion.tipo_operacion != "emitir_comprobante"
            # JSON literal null es indistinguible de None al deserializar y
            # existía antes de PF-19B. Solo se admite en esta clasificación
            # legacy exacta; el ownership moderno sigue exigiendo SQL NULL.
            or operacion.response_json is not None
            or operacion.rece_snapshot_hash is not None
            or intento_actual is None
            or intento_actual.estado != "en_proceso"
            or snapshot_rece_presente
            or len(intentos_operacion) != 1
            or bool(guardas)
        )
        if bloquea or not retener_locks:
            await self.db.commit()
        return bloquea

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

        try:
            request = EmitirComprobanteRequest.model_validate(grupo.payload_json)
        except PydanticValidationError:
            logger.warning(
                "El payload fiscal del intento autorizado %s no cumple el contrato vigente",
                intento.id,
            )
            return None
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

    def _bloqueo_preautorizacion(
        self,
        *,
        empresa_id: int,
        punto_venta_id: int,
        punto_venta_numero: int,
        tipo_comprobante: int,
    ) -> bool:
        """Indica si la tupla fiscal está contenida por configuración explícita."""
        bloqueo = obtener_bloqueo_preautorizacion(
            ambiente=self._get_arca_ambiente().value,
            empresa_id=empresa_id,
            punto_venta_id=punto_venta_id,
            punto_venta=punto_venta_numero,
            tipo_comprobante=tipo_comprobante,
        )
        if bloqueo is None:
            return False

        if bloqueo.punto_venta != punto_venta_numero:
            logger.warning(
                "event=arca_punto_bloqueado_renumerado ambiente=%s empresa_id=%s "
                "punto_venta_id=%s numero_configurado=%s numero_actual=%s",
                bloqueo.ambiente,
                empresa_id,
                punto_venta_id,
                bloqueo.punto_venta,
                punto_venta_numero,
            )

        logger.warning(
            "event=arca_preautorizacion_bloqueada ambiente=%s empresa_id=%s "
            "punto_venta=%s tipo_comprobante=%s motivo=%s",
            bloqueo.ambiente,
            empresa_id,
            punto_venta_numero,
            tipo_comprobante,
            bloqueo.motivo,
        )
        return True

    def _validar_sin_bloqueo_preautorizacion(
        self,
        *,
        empresa_id: int,
        punto_venta_id: int,
        punto_venta_numero: int,
        tipo_comprobante: int,
    ) -> None:
        """Falla cerrado antes de consultas ARCA si la tupla está bloqueada."""
        if self._bloqueo_preautorizacion(
            empresa_id=empresa_id,
            punto_venta_id=punto_venta_id,
            punto_venta_numero=punto_venta_numero,
            tipo_comprobante=tipo_comprobante,
        ):
            raise ValidationError(
                f"{MENSAJE_BLOQUEO_PREAUTORIZACION}. "
                f"{DETALLE_BLOQUEO_PREAUTORIZACION}"
            )

    @staticmethod
    def _respuesta_bloqueo_preautorizacion(
        *,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        totales: dict,
    ) -> EmitirComprobanteResponse:
        """Devuelve un aborto local verificable sin iniciar una solicitud de CAE."""
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=0,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje=MENSAJE_BLOQUEO_PREAUTORIZACION,
            errores=[DETALLE_BLOQUEO_PREAUTORIZACION],
            requiere_reconciliacion=False,
            categoria_error=CATEGORIA_BLOQUEO_PREAUTORIZACION,
        )

    @staticmethod
    def _respuesta_rechazo_elegibilidad(
        *,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        totales: dict,
        error: ElegibilidadReceError,
    ) -> EmitirComprobanteResponse:
        """Devuelve un rechazo local RECE/PF-19A sin iniciar llamadas ARCA."""
        detalle = (
            DETALLE_BLOQUEO_PREAUTORIZACION
            if error.categoria == CATEGORIA_BLOQUEO_PREAUTORIZACION
            else "Revalidá la acreditación RECE del punto de venta."
        )
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=0,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje=error.mensaje,
            errores=[detalle],
            requiere_reconciliacion=False,
            categoria_error=error.categoria,
        )

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
        ambiente = settings.arca_env.strip().lower()
        if ambiente == ArcaAmbiente.PRODUCCION.value:
            return ArcaAmbiente.PRODUCCION
        if ambiente == ArcaAmbiente.HOMOLOGACION.value:
            return ArcaAmbiente.HOMOLOGACION
        raise ValidationError("El ambiente ARCA configurado no es válido")

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
            commit=False,
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

    async def _recargar_intentos_y_guarda_rece(
        self,
        *,
        intento_ids: list[int | None],
        guarda_id: int | None,
    ) -> tuple[list[IntentoEmisionFiscal], PuntoVentaGuardaEmisionRece]:
        """Rehidrata el grafo durable después de un rollback post-ARCA."""
        if (
            guarda_id is None
            or not intento_ids
            or any(intento_id is None for intento_id in intento_ids)
        ):
            raise SQLAlchemyTimeoutError(
                "No se conservan las identidades del grafo fiscal durable."
            )
        ids_durables = [int(intento_id) for intento_id in intento_ids]
        intentos_por_id = {
            intento.id: intento
            for intento in (
                await self.db.execute(
                    select(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.id.in_(ids_durables))
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        }
        intentos = [
            intentos_por_id[intento_id]
            for intento_id in ids_durables
            if intento_id in intentos_por_id
        ]
        guarda = (
            await self.db.execute(
                select(PuntoVentaGuardaEmisionRece)
                .where(PuntoVentaGuardaEmisionRece.id == guarda_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if len(intentos) != len(ids_durables) or guarda is None:
            raise SQLAlchemyTimeoutError(
                "No se pudo recargar el grafo fiscal durable del sublote."
            )
        return intentos, guarda

    async def _persistir_intento_y_guarda_rece(
        self,
        *,
        idempotencia: IdempotenciaFiscalService,
        intento: IntentoEmisionFiscal,
        respuesta: EmitirComprobanteResponse,
        guarda: PuntoVentaGuardaEmisionRece,
        fase: Literal["cerrada_pre_arca", "cerrada_terminal", "reconciliacion"],
        commit: bool,
        contexto: str,
    ) -> None:
        """Persiste intento y fase de guarda en una única transacción."""
        elegibilidad = ElegibilidadReceService(self.db)
        try:
            if fase == "reconciliacion":
                (
                    intentos_bloqueados,
                    guarda,
                ) = await self._inmovilizar_grafo_reconciliacion(
                    intentos=[intento],
                    guarda=guarda,
                )
                intento = intentos_bloqueados[0]
            await idempotencia.actualizar_intento_desde_respuesta(
                intento,
                respuesta,
                commit=False,
            )
            if fase == "cerrada_pre_arca":
                await elegibilidad.cerrar_pre_arca(guarda, commit=False)
            elif fase == "cerrada_terminal":
                await elegibilidad.cerrar_terminal(guarda, commit=False)
            else:
                await elegibilidad.marcar_requiere_reconciliacion(
                    guarda,
                    commit=False,
                )
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()
        except Exception as exc:
            await self._rollback_seguro(f"intento_guarda_rece:{contexto}")
            logger.error(
                "No se pudo cerrar intento y guarda RECE contexto=%s tipo_error=%s",
                contexto,
                type(exc).__name__,
            )
            if isinstance(exc, DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS):
                raise
            raise SQLAlchemyTimeoutError(
                "No se pudo confirmar el cierre fiscal durable."
            ) from exc

    async def _persistir_intentos_y_guarda_rece(
        self,
        *,
        idempotencia: IdempotenciaFiscalService,
        intentos: list[IntentoEmisionFiscal],
        respuestas: list[EmitirComprobanteResponse],
        guarda: PuntoVentaGuardaEmisionRece,
        fase: Literal["cerrada_pre_arca", "cerrada_terminal", "reconciliacion"],
        contexto: str,
        commit: bool = True,
    ) -> None:
        """Cierra todos los intentos batch y su guarda en un único commit."""
        if len(intentos) != len(respuestas) or not intentos:
            raise SQLAlchemyTimeoutError(
                "El sublote fiscal no conserva todos sus intentos durables."
            )
        elegibilidad = ElegibilidadReceService(self.db)
        try:
            if fase == "reconciliacion":
                intentos, guarda = await self._inmovilizar_grafo_reconciliacion(
                    intentos=intentos,
                    guarda=guarda,
                )
            for intento, respuesta in zip(intentos, respuestas):
                await idempotencia.actualizar_intento_desde_respuesta(
                    intento,
                    respuesta,
                    commit=False,
                )
            if fase == "cerrada_pre_arca":
                await elegibilidad.cerrar_pre_arca(guarda, commit=False)
            elif fase == "cerrada_terminal":
                await elegibilidad.cerrar_terminal(guarda, commit=False)
            else:
                await elegibilidad.marcar_requiere_reconciliacion(
                    guarda,
                    commit=False,
                )
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()
        except Exception as exc:
            await self._rollback_seguro(f"intentos_guarda_rece:{contexto}")
            logger.error(
                "No se pudo cerrar sublote y guarda RECE contexto=%s tipo_error=%s",
                contexto,
                type(exc).__name__,
            )
            if isinstance(exc, DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS):
                raise
            raise SQLAlchemyTimeoutError(
                "No se pudo confirmar el cierre fiscal durable del sublote."
            ) from exc

    async def _cerrar_rechazo_global_intentos_y_guarda(
        self,
        *,
        idempotencia: IdempotenciaFiscalService,
        intentos: list[IntentoEmisionFiscal],
        respuestas: list[EmitirComprobanteResponse],
        guarda: PuntoVentaGuardaEmisionRece,
        commit: bool,
    ) -> None:
        """Cierra un 10005 exacto bajo locks sin publicar la operación del caller."""
        intento_ids = [getattr(intento, "id", None) for intento in intentos]
        operacion_ids = {getattr(intento, "operacion_id", None) for intento in intentos}
        if (
            not intentos
            or len(intentos) != len(respuestas)
            or any(
                not isinstance(intento_id, int) or isinstance(intento_id, bool)
                for intento_id in intento_ids
            )
            or len(set(intento_ids)) != len(intento_ids)
            or len(operacion_ids) != 1
            or None in operacion_ids
            or not isinstance(getattr(guarda, "id", None), int)
            or isinstance(getattr(guarda, "id", None), bool)
        ):
            raise SQLAlchemyTimeoutError(
                "El rechazo global no conserva un grafo fiscal exacto."
            )

        operacion_id = int(next(iter(operacion_ids)))
        try:
            fila_operacion = (
                await self.db.execute(
                    select(
                        OperacionIdempotente,
                        OperacionIdempotente.response_json.is_(None).label(
                            "respuesta_es_sql_null"
                        ),
                    )
                    .where(OperacionIdempotente.id == operacion_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).one_or_none()
            if fila_operacion is None:
                raise SQLAlchemyTimeoutError(
                    "La operación del rechazo global ya no existe."
                )
            operacion = fila_operacion[0]
            respuesta_es_sql_null = fila_operacion[1] is True

            intentos_operacion = list(
                (
                    await self.db.execute(
                        select(IntentoEmisionFiscal)
                        .where(IntentoEmisionFiscal.operacion_id == operacion_id)
                        .order_by(IntentoEmisionFiscal.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                )
                .scalars()
                .all()
            )
            guardas_operacion = list(
                (
                    await self.db.execute(
                        select(PuntoVentaGuardaEmisionRece)
                        .where(PuntoVentaGuardaEmisionRece.operacion_id == operacion_id)
                        .order_by(PuntoVentaGuardaEmisionRece.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                )
                .scalars()
                .all()
            )
            intentos_por_id = {
                int(intento.id): intento for intento in intentos_operacion
            }
            guardas_por_id = {int(item.id): item for item in guardas_operacion}
            intentos_bloqueados = [
                intentos_por_id[int(intento_id)]
                for intento_id in intento_ids
                if int(intento_id) in intentos_por_id
            ]
            guarda_bloqueada = guardas_por_id.get(int(guarda.id))
            intentos_de_guarda = [
                intento
                for intento in intentos_operacion
                if intento.guarda_rece_id == guarda.id
            ]
            identidad_valida = (
                len(intentos_bloqueados) == len(intentos)
                and {int(item.id) for item in intentos_de_guarda}
                == {int(item) for item in intento_ids}
                and guarda_bloqueada is not None
                and guarda_bloqueada.operacion_id == operacion_id
                and guarda_bloqueada.empresa_id == operacion.empresa_id
                and guarda_bloqueada.fase == "arca_iniciada"
                and all(
                    intento.estado == "en_proceso"
                    and intento.operacion_id == operacion_id
                    and intento.empresa_id == operacion.empresa_id
                    and intento.guarda_rece_id == guarda_bloqueada.id
                    and intento.punto_venta_id == guarda_bloqueada.punto_venta_id
                    and intento.ambiente == guarda_bloqueada.ambiente
                    and intento.punto_venta_elegibilidad_revision_id
                    == guarda_bloqueada.elegibilidad_revision_id
                    and intento.punto_venta_revision_fiscal
                    == guarda_bloqueada.punto_venta_revision_fiscal
                    for intento in intentos_bloqueados
                )
            )
            if not identidad_valida:
                raise SQLAlchemyTimeoutError(
                    "El grafo fiscal cambió antes de cerrar el rechazo global."
                )

            lote = None
            metadata = None
            material_rece = None
            owner_lote = None
            if operacion.lote_id is not None:
                lote = (
                    await self.db.execute(
                        select(LoteComprobante)
                        .where(
                            LoteComprobante.id == operacion.lote_id,
                            LoteComprobante.empresa_id == operacion.empresa_id,
                        )
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                metadata = lote.metadata_json if lote is not None else None
                if isinstance(metadata, dict):
                    material_rece = metadata.get("pf19b_rece_material")
                    owner_lote = metadata.get("operacion_idempotente_id")

            grupos_material: list[LoteComprobanteGrupo] = []
            if lote is not None and IdempotenciaFiscalService.material_rece_valido(
                material_rece,
                empresa_id=int(operacion.empresa_id),
            ):
                grupos_material = list(
                    (
                        await self.db.execute(
                            select(LoteComprobanteGrupo)
                            .where(
                                LoteComprobanteGrupo.lote_id == lote.id,
                                LoteComprobanteGrupo.id.in_(material_rece["grupo_ids"]),
                            )
                            .order_by(LoteComprobanteGrupo.id)
                            .with_for_update()
                            .execution_options(populate_existing=True)
                        )
                    )
                    .scalars()
                    .all()
                )
            material_coincide = (
                lote is not None
                and IdempotenciaFiscalService.material_rece_coincide_grupos(
                    material_rece,
                    empresa_id=int(operacion.empresa_id),
                    grupos=grupos_material,
                )
            )
            material_por_grupo = {
                item["grupo_id"]: item
                for item in (material_rece or {}).get("grupos", [])
                if isinstance(item, dict)
                and isinstance(item.get("grupo_id"), int)
                and not isinstance(item.get("grupo_id"), bool)
            }
            grupos_por_id = {int(grupo.id): grupo for grupo in grupos_material}
            payload_hash_por_grupo = {
                grupo_id: IdempotenciaFiscalService.calcular_payload_hash(
                    IdempotenciaFiscalService.payload_sin_confirmacion_duplicado(
                        self.normalizar_receptor(
                            EmitirComprobanteRequest.model_validate(
                                grupo.payload_json or {}
                            )
                        ).model_dump(mode="json")
                    )
                )
                for grupo_id, grupo in grupos_por_id.items()
            }

            lote_ids_intentos = {intento.lote_id for intento in intentos_bloqueados}
            if operacion.tipo_operacion == "emitir_comprobante":
                ownership_valido = (
                    respuesta_es_sql_null
                    and operacion.lote_id is None
                    and lote_ids_intentos == {None}
                )
            elif operacion.tipo_operacion in {
                "procesar_lote",
                "reintentar_fallidos_lote",
            }:
                ownership_lote_valido = (
                    lote is not None
                    and lote_ids_intentos == {int(lote.id)}
                    and isinstance(owner_lote, int)
                    and not isinstance(owner_lote, bool)
                    and owner_lote == operacion_id
                    and material_coincide
                    and all(
                        isinstance(intento.grupo_id, int)
                        and not isinstance(intento.grupo_id, bool)
                        and (item_material := material_por_grupo.get(intento.grupo_id))
                        is not None
                        and intento.empresa_id == item_material["empresa_id"]
                        and intento.punto_venta_id == item_material["punto_venta_id"]
                        and intento.punto_venta_numero
                        == item_material["punto_venta_numero"]
                        and intento.ambiente == item_material["ambiente"]
                        and intento.punto_venta_elegibilidad_revision_id
                        == item_material["elegibilidad_revision_id"]
                        and intento.punto_venta_revision_fiscal
                        == item_material["punto_venta_revision_fiscal"]
                        and intento.tipo_comprobante
                        == item_material["tipo_comprobante"]
                        and intento.grupo_id in grupos_por_id
                        and intento.payload_hash
                        == payload_hash_por_grupo.get(intento.grupo_id)
                        for intento in intentos_bloqueados
                    )
                )
                ownership_valido = ownership_lote_valido and respuesta_es_sql_null
                if not respuesta_es_sql_null:
                    ownership_valido = (
                        ownership_lote_valido
                        and operacion.tipo_operacion == "procesar_lote"
                        and IdempotenciaFiscalService.respuesta_worker_en_progreso_valida(
                            operacion.response_json,
                            lote_id=int(lote.id),
                            empresa_id=int(lote.empresa_id),
                            operacion_id=operacion_id,
                            material_rece=material_rece,
                        )
                    )
            else:
                ownership_valido = False
            if (
                operacion.estado != "en_proceso"
                or not isinstance(operacion.rece_snapshot_hash, str)
                or len(operacion.rece_snapshot_hash) != 64
                or not ownership_valido
            ):
                raise SQLAlchemyTimeoutError(
                    "La operación perdió ownership antes del rechazo global."
                )

            for intento, respuesta in zip(intentos_bloqueados, respuestas):
                error_arca = (
                    respuesta.errores_arca[0]
                    if len(respuesta.errores_arca) == 1
                    else None
                )
                respuesta_valida = (
                    respuesta.exito is False
                    and respuesta.requiere_reconciliacion is False
                    and respuesta.categoria_error == "arca_rechazo_global_excluyente"
                    and respuesta.cae is None
                    and respuesta.comprobante_id is None
                    and error_arca is not None
                    and isinstance(error_arca.codigo, int)
                    and not isinstance(error_arca.codigo, bool)
                    and error_arca.codigo == 10005
                    and error_arca.alcance == "global"
                    and error_arca.mensaje
                    == "El punto de venta no está dado de alta como RECE en ARCA."
                    and respuesta.tipo_comprobante == intento.tipo_comprobante
                    and respuesta.punto_venta == intento.punto_venta_numero
                    and respuesta.numero == intento.numero_planificado
                    and respuesta.fecha == intento.fecha_emision
                    and Decimal(str(respuesta.total)).quantize(Decimal("0.01"))
                    == Decimal(str(intento.total)).quantize(Decimal("0.01"))
                )
                if not respuesta_valida:
                    raise SQLAlchemyTimeoutError(
                        "La respuesta global no coincide con el intento bloqueado."
                    )
                await idempotencia.actualizar_intento_desde_respuesta(
                    intento,
                    respuesta,
                    commit=False,
                )
            await ElegibilidadReceService(self.db).cerrar_terminal(
                guarda_bloqueada,
                commit=False,
            )
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()
        except Exception as exc:
            await self._rollback_seguro("rechazo_global_terminal")
            if isinstance(exc, DATABASE_TEMPORARILY_UNAVAILABLE_ERRORS):
                raise
            if isinstance(exc, SQLAlchemyTimeoutError):
                raise
            raise SQLAlchemyTimeoutError(
                "No se pudo confirmar el rechazo global de forma durable."
            ) from exc

    async def _inmovilizar_grafo_reconciliacion(
        self,
        *,
        intentos: list[IntentoEmisionFiscal],
        guarda: PuntoVentaGuardaEmisionRece,
    ) -> tuple[list[IntentoEmisionFiscal], PuntoVentaGuardaEmisionRece]:
        """Bloquea y valida el grafo post-ARCA antes de inmovilizar su operación."""
        intento_ids = [intento.id for intento in intentos]
        operacion_ids = {intento.operacion_id for intento in intentos}
        if (
            not intentos
            or any(
                not isinstance(intento_id, int) or isinstance(intento_id, bool)
                for intento_id in intento_ids
            )
            or len(set(intento_ids)) != len(intento_ids)
            or len(operacion_ids) != 1
            or None in operacion_ids
            or not isinstance(guarda.id, int)
            or isinstance(guarda.id, bool)
            or guarda.operacion_id not in operacion_ids
        ):
            raise SQLAlchemyTimeoutError(
                "El grafo fiscal no conserva una operación reconciliable única."
            )

        operacion_id = int(next(iter(operacion_ids)))
        fila_operacion = (
            await self.db.execute(
                select(
                    OperacionIdempotente,
                    OperacionIdempotente.response_json.is_(None).label(
                        "respuesta_es_sql_null"
                    ),
                )
                .where(OperacionIdempotente.id == operacion_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if fila_operacion is None:
            raise SQLAlchemyTimeoutError(
                "La operación fiscal reconciliable ya no existe."
            )
        operacion = fila_operacion[0]
        respuesta_es_sql_null = fila_operacion[1] is True

        intentos_bloqueados = list(
            (
                await self.db.execute(
                    select(IntentoEmisionFiscal)
                    .where(IntentoEmisionFiscal.id.in_(intento_ids))
                    .order_by(IntentoEmisionFiscal.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        guardas_bloqueadas = list(
            (
                await self.db.execute(
                    select(PuntoVentaGuardaEmisionRece)
                    .where(PuntoVentaGuardaEmisionRece.operacion_id == operacion_id)
                    .order_by(PuntoVentaGuardaEmisionRece.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        )
        intentos_por_id = {int(intento.id): intento for intento in intentos_bloqueados}
        guardas_por_id = {int(item.id): item for item in guardas_bloqueadas}
        guarda_bloqueada = guardas_por_id.get(int(guarda.id))
        intentos_ordenados = [
            intentos_por_id[int(intento_id)]
            for intento_id in intento_ids
            if int(intento_id) in intentos_por_id
        ]
        lote_ids = {intento.lote_id for intento in intentos_ordenados}
        identidad_valida = (
            len(intentos_ordenados) == len(intento_ids)
            and guarda_bloqueada is not None
            and guarda_bloqueada.operacion_id == operacion_id
            and guarda_bloqueada.empresa_id == operacion.empresa_id
            and guarda_bloqueada.fase == "arca_iniciada"
            and len(lote_ids) == 1
            and next(iter(lote_ids)) == operacion.lote_id
            and all(
                intento.operacion_id == operacion_id
                and intento.empresa_id == operacion.empresa_id
                and intento.guarda_rece_id == guarda_bloqueada.id
                and intento.estado == "en_proceso"
                and intento.punto_venta_id == guarda_bloqueada.punto_venta_id
                and intento.ambiente == guarda_bloqueada.ambiente
                and intento.punto_venta_elegibilidad_revision_id
                == guarda_bloqueada.elegibilidad_revision_id
                and intento.punto_venta_revision_fiscal
                == guarda_bloqueada.punto_venta_revision_fiscal
                for intento in intentos_ordenados
            )
        )
        if not identidad_valida:
            raise SQLAlchemyTimeoutError(
                "El grafo fiscal cambió antes de inmovilizar la operación."
            )

        material_rece = None
        lote_background: bool | None = None
        if operacion.lote_id is not None:
            lote_background = False
        if not respuesta_es_sql_null:
            if operacion.tipo_operacion != "procesar_lote" or operacion.lote_id is None:
                raise SQLAlchemyTimeoutError(
                    "La operación fiscal conserva una respuesta incompatible."
                )
            lote = (
                await self.db.execute(
                    select(LoteComprobante)
                    .where(
                        LoteComprobante.id == operacion.lote_id,
                        LoteComprobante.empresa_id == operacion.empresa_id,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            metadata = lote.metadata_json if lote is not None else None
            owner = (
                metadata.get("operacion_idempotente_id")
                if isinstance(metadata, dict)
                else None
            )
            material_rece = (
                metadata.get("pf19b_rece_material")
                if isinstance(metadata, dict)
                else None
            )
            if (
                not isinstance(owner, int)
                or isinstance(owner, bool)
                or owner != operacion_id
                or not isinstance(material_rece, dict)
            ):
                raise SQLAlchemyTimeoutError(
                    "El lote perdió el ownership fiscal antes de reconciliarse."
                )
            lote_background = True

        hash_valido = (
            isinstance(operacion.rece_snapshot_hash, str)
            and len(operacion.rece_snapshot_hash) == 64
        )
        if operacion.tipo_operacion == "emitir_comprobante":
            ownership_valido = (
                operacion.lote_id is None
                and lote_background is None
                and respuesta_es_sql_null
            )
        elif operacion.tipo_operacion == "reintentar_fallidos_lote":
            ownership_valido = (
                operacion.lote_id is not None
                and lote_background is False
                and respuesta_es_sql_null
            )
        elif operacion.tipo_operacion == "procesar_lote":
            ownership_valido = operacion.lote_id is not None and (
                (lote_background is False and respuesta_es_sql_null)
                or (
                    lote_background is True
                    and material_rece is not None
                    and IdempotenciaFiscalService.respuesta_worker_en_progreso_valida(
                        operacion.response_json,
                        lote_id=int(operacion.lote_id),
                        empresa_id=int(operacion.empresa_id),
                        operacion_id=operacion_id,
                        material_rece=material_rece,
                    )
                )
            )
        else:
            ownership_valido = False
        if (
            operacion.estado not in {"en_proceso", "requiere_reconciliacion"}
            or not hash_valido
            or not ownership_valido
        ):
            raise SQLAlchemyTimeoutError(
                "La operación fiscal perdió su ownership reconciliable."
            )

        if operacion.estado == "en_proceso":
            publicada = await self.db.execute(
                update(OperacionIdempotente)
                .where(
                    OperacionIdempotente.id == operacion_id,
                    OperacionIdempotente.estado == "en_proceso",
                    OperacionIdempotente.updated_at == operacion.updated_at,
                )
                .values(estado="requiere_reconciliacion")
            )
            if publicada.rowcount != 1:
                raise SQLAlchemyTimeoutError(
                    "La operación fiscal cambió durante la reconciliación."
                )
        return intentos_ordenados, guarda_bloqueada

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

    def _respuesta_batch_reserva_pre_arca_fallida(
        self,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
        error: str,
    ) -> EmitirComprobanteResponse:
        """Arma una respuesta fallida cuando el sublote no llegó a solicitar CAE."""
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje=("FactuFlow revirtió la preparación local antes de solicitar CAE"),
            errores=[
                (
                    "No se solicitó CAE; la transacción local se revirtió por "
                    "completo y no quedó una reserva fiscal durable."
                ),
                error,
            ],
            categoria_error="pre_arca_reserva_fallida",
        )

    @staticmethod
    def _errores_globales_sanitarios(
        exc: ArcaErrorGlobalEstructurado,
    ) -> list[ErrorArcaFiscalResponse]:
        """Conserva códigos globales enteros sin publicar mensajes externos."""
        return [
            ErrorArcaFiscalResponse(
                codigo=mensaje.codigo,
                alcance="global",
                mensaje="ARCA informó un error global para el requerimiento.",
            )
            for mensaje in exc.errores
            if isinstance(mensaje.codigo, int) and not isinstance(mensaje.codigo, bool)
        ]

    @staticmethod
    def _respuesta_rechazo_global_excluyente(
        *,
        request: EmitirComprobanteRequest,
        punto_venta_numero: int,
        numero: int,
        totales: dict,
    ) -> EmitirComprobanteResponse:
        """Devuelve el único rechazo global terminal reconocido por PF-19C."""
        return EmitirComprobanteResponse(
            exito=False,
            tipo_comprobante=request.tipo_comprobante,
            punto_venta=punto_venta_numero,
            numero=numero,
            fecha=request.fecha_emision,
            total=totales["total"],
            mensaje="ARCA rechazó el requerimiento completo antes de autorizar.",
            errores=[
                "Revisá la habilitación RECE del punto de venta antes de iniciar otra emisión."
            ],
            errores_arca=[
                ErrorArcaFiscalResponse(
                    codigo=10005,
                    alcance="global",
                    mensaje=(
                        "El punto de venta no está dado de alta como RECE en ARCA."
                    ),
                )
            ],
            requiere_reconciliacion=False,
            categoria_error="arca_rechazo_global_excluyente",
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
