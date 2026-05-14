"""Servicio de Facturación - Emisión de Comprobantes."""

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import desc, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.arca.config import ArcaAmbiente
from app.arca.exceptions import ArcaServiceError, ArcaValidationError
from app.arca.models import CbteAsocItem, ComprobanteRequest, IvaItem
from app.arca.utils import clean_cuit, validate_cuit
from app.arca.wsaa import WSAAClient
from app.arca.wsfev1 import WSFEv1Client
from app.core.config import settings
from app.models.certificado import Certificado
from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.punto_venta import PuntoVenta
from app.services.certificados_service import resolve_cert_storage_path
from app.schemas.comprobante import (
    EmitirComprobanteRequest,
    EmitirComprobanteResponse,
    ItemComprobanteCreate,
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Error de validación de datos."""

    pass


class FacturacionService:
    """Servicio para emisión de comprobantes electrónicos."""

    _number_locks: dict[tuple[int, int, int], asyncio.Lock] = {}
    _number_locks_guard = asyncio.Lock()
    CONSUMIDOR_FINAL_IDENTIFICACION_MINIMA = Decimal("10000000")
    TIPOS_COMPROBANTE_C = {11, 12, 13}

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
        self, request: EmitirComprobanteRequest
    ) -> EmitirComprobanteResponse:
        """Serializa la emisión por empresa, punto de venta y tipo."""
        lock = await self._get_number_lock(
            request.empresa_id, request.punto_venta_id, request.tipo_comprobante
        )
        async with lock:
            return await self._emitir_comprobante_locked(request)

    async def _emitir_comprobante_locked(
        self, request: EmitirComprobanteRequest
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
            punto_venta = await self._obtener_punto_venta(request.punto_venta_id)
            certificado = await self._obtener_certificado_activo(request.empresa_id)

            # 4. Autenticar contra ARCA y reconciliar numeración
            ticket = await self._obtener_ticket_acceso(empresa, certificado)
            wsfe_client = WSFEv1Client(
                ambiente=self._get_arca_ambiente(),
                ticket=ticket,
                cuit=empresa.cuit,
            )
            await self._validar_punto_venta_habilitado(wsfe_client, punto_venta.numero)
            proximo = await self._obtener_proximo_numero(
                request.empresa_id,
                request.punto_venta_id,
                request.tipo_comprobante,
                wsfe_client,
                punto_venta.numero,
            )

            # 5. Armar request para ARCA
            arca_request = self._armar_request_arca(
                request, proximo, totales, punto_venta.numero
            )

            # 6. Solicitar CAE
            try:
                resultado = await wsfe_client.fe_cae_solicitar(arca_request)

            except (ArcaServiceError, ArcaValidationError) as e:
                logger.error(f"Error al solicitar CAE: {str(e)}")
                return EmitirComprobanteResponse(
                    exito=False,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=punto_venta.numero,
                    numero=proximo,
                    fecha=request.fecha_emision,
                    total=totales["total"],
                    mensaje="Error al solicitar CAE a ARCA",
                    errores=[str(e)],
                )

            # 7. Guardar en BD
            try:
                comprobante = await self._guardar_comprobante(
                    request, proximo, totales, resultado, punto_venta
                )
            except IntegrityError as exc:
                await self.db.rollback()
                logger.exception(
                    "Conflicto de numeración al guardar comprobante autorizado. "
                    "empresa=%s pv=%s tipo=%s numero=%s",
                    request.empresa_id,
                    punto_venta.numero,
                    request.tipo_comprobante,
                    proximo,
                )
                return EmitirComprobanteResponse(
                    exito=False,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=punto_venta.numero,
                    numero=proximo,
                    fecha=request.fecha_emision,
                    total=totales["total"],
                    mensaje="La numeración ya fue registrada localmente",
                    errores=[
                        "ARCA pudo haber autorizado el comprobante, pero no se pudo guardar por conflicto de numeración. Consultá ARCA y reconciliá antes de reintentar.",
                        str(exc.orig),
                    ],
                )

            # 8. Retornar resultado
            logger.info(
                "Comprobante emitido: empresa=%s tipo=%s pv=%s numero=%s cae=%s total=%s",
                request.empresa_id,
                request.tipo_comprobante,
                punto_venta.numero,
                proximo,
                resultado.cae,
                totales["total"],
            )
            return EmitirComprobanteResponse(
                exito=True,
                comprobante_id=comprobante.id,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=punto_venta.numero,
                numero=proximo,
                fecha=comprobante.fecha_emision,
                cae=resultado.cae,
                cae_vencimiento=self._parse_fecha_cae(resultado.cae_vencimiento),
                total=totales["total"],
                mensaje="Comprobante emitido exitosamente",
            )

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
        except Exception as e:
            logger.error(f"Error inesperado al emitir comprobante: {str(e)}")
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=0,
                numero=0,
                fecha=request.fecha_emision,
                total=Decimal("0"),
                mensaje="Error inesperado",
                errores=[f"Error interno: {str(e)}"],
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
        punto_venta = await self._obtener_punto_venta(punto_venta_id)
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

        # Validar que exista el punto de venta
        punto_venta = await self._obtener_punto_venta(request.punto_venta_id)
        if not punto_venta:
            raise ValidationError("Punto de venta no encontrado")

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

        if proximo_local != proximo_arca:
            logger.warning(
                "Desfase de numeración detectado. empresa=%s pv=%s tipo=%s local=%s arca=%s",
                empresa_id,
                punto_venta_numero,
                tipo_comprobante,
                proximo_local,
                proximo_arca,
            )

        return max(proximo_local, proximo_arca)

    async def _obtener_empresa(self, empresa_id: int) -> Optional[Empresa]:
        """Obtiene una empresa por ID."""
        stmt = select(Empresa).where(Empresa.id == empresa_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _obtener_punto_venta(self, punto_venta_id: int) -> Optional[PuntoVenta]:
        """Obtiene un punto de venta por ID."""
        stmt = select(PuntoVenta).where(PuntoVenta.id == punto_venta_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _obtener_certificado_activo(self, empresa_id: int) -> Certificado:
        """Obtiene el certificado activo para la empresa y el ambiente actual."""
        stmt = select(Certificado).where(
            Certificado.empresa_id == empresa_id,
            Certificado.activo.is_(True),
            Certificado.ambiente == self._get_arca_ambiente().value,
        )
        result = await self.db.execute(stmt)
        certificado = result.scalar_one_or_none()
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

    def _resolve_cert_path(self, stored_path: str) -> str:
        """Resuelve paths absolutos o relativos de certificados."""
        return resolve_cert_storage_path(stored_path)

    async def _obtener_ticket_acceso(self, empresa: Empresa, certificado: Certificado):
        """Obtiene ticket WSAA para la empresa."""
        wsaa_client = WSAAClient(self._get_arca_ambiente())
        return await wsaa_client.login(
            cert_path=self._resolve_cert_path(certificado.archivo_crt),
            key_path=self._resolve_cert_path(certificado.archivo_key),
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
            moneda_cotiz=float(request.cotizacion),
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

    async def _guardar_comprobante(
        self,
        request: EmitirComprobanteRequest,
        numero: int,
        totales: dict,
        resultado_arca,
        punto_venta: PuntoVenta,
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
