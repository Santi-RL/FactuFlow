"""Servicio de Facturación - Emisión de Comprobantes."""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comprobante import Comprobante
from app.models.comprobante_item import ComprobanteItem
from app.models.empresa import Empresa
from app.models.punto_venta import PuntoVenta
from app.models.cliente import Cliente
from app.schemas.comprobante import (
    EmitirComprobanteRequest,
    EmitirComprobanteResponse,
    ItemComprobanteCreate,
)
from app.arca.wsaa import WSAAClient
from app.arca.wsfev1 import WSFEv1Client
from app.arca.models import ComprobanteRequest, IvaItem
from app.arca.config import ArcaAmbiente
from app.arca.exceptions import ArcaServiceError, ArcaValidationError


logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Error de validación de datos."""
    pass


class FacturacionService:
    """Servicio para emisión de comprobantes electrónicos."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def emitir_comprobante(
        self,
        request: EmitirComprobanteRequest
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
            # 1. Validar datos
            await self._validar_datos(request)
            
            # 2. Obtener próximo número
            proximo = await self._obtener_proximo_numero(
                request.empresa_id,
                request.punto_venta_id,
                request.tipo_comprobante
            )
            
            # 3. Calcular totales
            totales = self._calcular_totales(request.items)
            
            # 4. Obtener empresa y punto de venta
            empresa = await self._obtener_empresa(request.empresa_id)
            punto_venta = await self._obtener_punto_venta(request.punto_venta_id)
            
            # 5. Armar request para ARCA
            arca_request = self._armar_request_arca(
                request, proximo, totales, punto_venta.numero
            )
            
            # 6. Solicitar CAE
            try:
                # Obtener ticket de acceso
                wsaa_client = WSAAClient(
                    ambiente=ArcaAmbiente.HOMOLOGACION,  # TODO: Obtener de empresa
                    cuit=empresa.cuit
                )
                
                # TODO: Cargar certificado desde BD o filesystem
                # Por ahora usar método simplificado
                ticket = await wsaa_client.obtener_ticket_acceso(
                    service="wsfe",
                    cert_path=f"/app/certs/{empresa.cuit}.crt",
                    key_path=f"/app/certs/{empresa.cuit}.key"
                )
                
                # Cliente WSFEv1
                wsfe_client = WSFEv1Client(
                    ambiente=ArcaAmbiente.HOMOLOGACION,  # TODO: Obtener de empresa
                    ticket=ticket,
                    cuit=empresa.cuit
                )
                
                resultado = await wsfe_client.fe_cae_solicitar(arca_request)
                
            except (ArcaServiceError, ArcaValidationError) as e:
                logger.error(f"Error al solicitar CAE: {str(e)}")
                return EmitirComprobanteResponse(
                    exito=False,
                    tipo_comprobante=request.tipo_comprobante,
                    punto_venta=punto_venta.numero,
                    numero=proximo,
                    fecha=date.today(),
                    total=totales["total"],
                    mensaje="Error al solicitar CAE a ARCA",
                    errores=[str(e)]
                )
            
            # 7. Guardar en BD
            comprobante = await self._guardar_comprobante(
                request, proximo, totales, resultado, punto_venta
            )
            
            # 8. Retornar resultado
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
                mensaje="Comprobante emitido exitosamente"
            )
            
        except ValidationError as e:
            logger.warning(f"Error de validación: {str(e)}")
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=0,
                numero=0,
                fecha=date.today(),
                total=Decimal("0"),
                mensaje="Error de validación",
                errores=[str(e)]
            )
        except Exception as e:
            logger.error(f"Error inesperado al emitir comprobante: {str(e)}")
            return EmitirComprobanteResponse(
                exito=False,
                tipo_comprobante=request.tipo_comprobante,
                punto_venta=0,
                numero=0,
                fecha=date.today(),
                total=Decimal("0"),
                mensaje="Error inesperado",
                errores=[f"Error interno: {str(e)}"]
            )
    
    async def obtener_proximo_numero(
        self,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int
    ) -> int:
        """Obtiene el próximo número de comprobante disponible."""
        return await self._obtener_proximo_numero(
            empresa_id, punto_venta_id, tipo_comprobante
        )
    
    def _calcular_totales(self, items: list[ItemComprobanteCreate]) -> dict:
        """
        Calcula subtotal, IVA y total.
        
        Returns:
            Dict con subtotal, iva_21, iva_10_5, iva_27, total
        """
        subtotal = Decimal("0")
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
                iva_21 += item_subtotal * Decimal("0.21")
            elif item.iva_porcentaje == Decimal("10.5"):
                iva_10_5 += item_subtotal * Decimal("0.105")
            elif item.iva_porcentaje == Decimal("27"):
                iva_27 += item_subtotal * Decimal("0.27")
        
        total = subtotal + iva_21 + iva_10_5 + iva_27
        
        return {
            "subtotal": subtotal.quantize(Decimal("0.01")),
            "iva_21": iva_21.quantize(Decimal("0.01")),
            "iva_10_5": iva_10_5.quantize(Decimal("0.01")),
            "iva_27": iva_27.quantize(Decimal("0.01")),
            "total": total.quantize(Decimal("0.01"))
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
        
        # Servicios requieren fechas
        if request.concepto in [2, 3]:
            if not request.fecha_servicio_desde:
                raise ValidationError(
                    "Para servicios debe indicar fecha desde"
                )
            if not request.fecha_servicio_hasta:
                raise ValidationError(
                    "Para servicios debe indicar fecha hasta"
                )
            if not request.fecha_vto_pago:
                raise ValidationError(
                    "Para servicios debe indicar fecha de vencimiento de pago"
                )
        
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
    
    async def _obtener_proximo_numero(
        self,
        empresa_id: int,
        punto_venta_id: int,
        tipo_comprobante: int
    ) -> int:
        """Obtiene el próximo número de comprobante disponible."""
        # Buscar el último comprobante del mismo tipo y punto de venta
        stmt = (
            select(Comprobante)
            .where(
                Comprobante.empresa_id == empresa_id,
                Comprobante.punto_venta_id == punto_venta_id,
                Comprobante.tipo_comprobante == tipo_comprobante
            )
            .order_by(desc(Comprobante.numero))
            .limit(1)
        )
        
        result = await self.db.execute(stmt)
        ultimo = result.scalar_one_or_none()
        
        if ultimo:
            return ultimo.numero + 1
        else:
            return 1
    
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
    
    def _armar_request_arca(
        self,
        request: EmitirComprobanteRequest,
        numero: int,
        totales: dict,
        punto_venta_numero: int
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
        nro_doc = ''.join(filter(str.isdigit, request.numero_documento))
        
        # Calcular IVA para ARCA
        iva_items = []
        
        if totales["iva_21"] > 0:
            iva_items.append(
                IvaItem(
                    id=5,  # 21%
                    base_imp=totales["subtotal"],
                    importe=totales["iva_21"]
                )
            )
        
        if totales["iva_10_5"] > 0:
            iva_items.append(
                IvaItem(
                    id=4,  # 10.5%
                    base_imp=totales["subtotal"],
                    importe=totales["iva_10_5"]
                )
            )
        
        if totales["iva_27"] > 0:
            iva_items.append(
                IvaItem(
                    id=6,  # 27%
                    base_imp=totales["subtotal"],
                    importe=totales["iva_27"]
                )
            )
        
        # Si no hay IVA, agregar IVA 0
        if not iva_items:
            iva_items.append(
                IvaItem(
                    id=3,  # 0%
                    base_imp=totales["total"],
                    importe=Decimal("0")
                )
            )
        
        # Crear request
        return ComprobanteRequest(
            punto_venta=punto_venta_numero,
            tipo_cbte=request.tipo_comprobante,
            concepto=request.concepto,
            tipo_doc=request.tipo_documento,
            nro_doc=int(nro_doc),
            cbte_desde=numero,
            cbte_hasta=numero,
            fecha_cbte=date.today().strftime("%Y%m%d"),
            imp_total=totales["total"],
            imp_tot_conc=Decimal("0"),  # No implementado aún
            imp_neto=totales["subtotal"],
            imp_op_ex=Decimal("0"),  # No implementado aún
            imp_iva=totales["iva_21"] + totales["iva_10_5"] + totales["iva_27"],
            imp_trib=Decimal("0"),  # No implementado aún
            moneda_id=request.moneda,
            moneda_cotiz=float(request.cotizacion),
            fecha_serv_desde=request.fecha_servicio_desde.strftime("%Y%m%d") if request.fecha_servicio_desde else None,
            fecha_serv_hasta=request.fecha_servicio_hasta.strftime("%Y%m%d") if request.fecha_servicio_hasta else None,
            fecha_vto_pago=request.fecha_vto_pago.strftime("%Y%m%d") if request.fecha_vto_pago else None,
            iva=iva_items if iva_items else None
        )
    
    async def _guardar_comprobante(
        self,
        request: EmitirComprobanteRequest,
        numero: int,
        totales: dict,
        resultado_arca,
        punto_venta: PuntoVenta
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
        # Obtener o crear cliente
        cliente_id = request.cliente_id
        if not cliente_id:
            # Crear cliente rápido
            cliente = Cliente(
                empresa_id=request.empresa_id,
                nombre=request.razon_social,
                cuit=request.numero_documento if request.tipo_documento == 80 else None,
                dni=request.numero_documento if request.tipo_documento == 96 else None,
                tipo_documento=request.tipo_documento,
                condicion_iva=request.condicion_iva,
                domicilio=request.domicilio
            )
            self.db.add(cliente)
            await self.db.flush()
            cliente_id = cliente.id
        
        # Crear comprobante
        comprobante = Comprobante(
            tipo_comprobante=request.tipo_comprobante,
            numero=numero,
            fecha_emision=date.today(),
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
            cliente_id=cliente_id
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
                comprobante_id=comprobante.id
            )
            self.db.add(item)
        
        await self.db.commit()
        await self.db.refresh(comprobante)
        
        return comprobante
    
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
            return date(
                int(fecha_str[0:4]),
                int(fecha_str[4:6]),
                int(fecha_str[6:8])
            )
        except (ValueError, IndexError):
            logger.warning(f"No se pudo parsear fecha CAE: {fecha_str}")
            return None
