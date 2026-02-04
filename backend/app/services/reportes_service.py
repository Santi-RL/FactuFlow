"""Servicio para generación de reportes."""

from datetime import date, datetime
from typing import List, Dict, Any
from decimal import Decimal
from calendar import monthrange

from sqlalchemy import select, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comprobante import Comprobante
from app.models.cliente import Cliente


class ReportesService:
    """Servicio para generación de reportes de ventas e IVA."""
    
    async def obtener_comprobantes_por_periodo(
        self,
        db: AsyncSession,
        empresa_id: int,
        desde: date,
        hasta: date
    ) -> List[Comprobante]:
        """
        Obtiene todos los comprobantes de un período.
        
        Args:
            db: Sesión de base de datos
            empresa_id: ID de la empresa
            desde: Fecha desde
            hasta: Fecha hasta
            
        Returns:
            Lista de comprobantes
        """
        query = (
            select(Comprobante)
            .options(
                selectinload(Comprobante.cliente),
                selectinload(Comprobante.punto_venta),
                selectinload(Comprobante.items)
            )
            .where(
                and_(
                    Comprobante.empresa_id == empresa_id,
                    Comprobante.fecha_emision >= desde,
                    Comprobante.fecha_emision <= hasta,
                    Comprobante.estado == "autorizado"
                )
            )
            .order_by(Comprobante.fecha_emision, Comprobante.numero)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def generar_reporte_ventas(
        self,
        db: AsyncSession,
        empresa_id: int,
        desde: date,
        hasta: date
    ) -> Dict[str, Any]:
        """
        Genera reporte de ventas por período.
        
        Args:
            db: Sesión de base de datos
            empresa_id: ID de la empresa
            desde: Fecha desde
            hasta: Fecha hasta
            
        Returns:
            Diccionario con comprobantes y resumen
        """
        comprobantes = await self.obtener_comprobantes_por_periodo(
            db, empresa_id, desde, hasta
        )
        
        # Calcular totales por tipo
        total_facturas = Decimal(0)
        total_nc = Decimal(0)  # Notas de crédito
        total_nd = Decimal(0)  # Notas de débito
        
        comprobantes_list = []
        for comp in comprobantes:
            comp_dict = {
                "id": comp.id,
                "fecha_emision": comp.fecha_emision.strftime("%d/%m/%Y"),
                "tipo_comprobante": comp.tipo_comprobante,
                "tipo_nombre": self._get_nombre_tipo_comprobante(comp.tipo_comprobante),
                "letra": self._get_letra_comprobante(comp.tipo_comprobante),
                "punto_venta": comp.punto_venta.numero,
                "numero": comp.numero,
                "numero_completo": f"{comp.punto_venta.numero:04d}-{comp.numero:08d}",
                "cliente_nombre": comp.cliente.razon_social,
                "subtotal": float(comp.subtotal),
                "iva_total": float(comp.iva_21 + comp.iva_10_5 + comp.iva_27),
                "total": float(comp.total),
            }
            comprobantes_list.append(comp_dict)
            
            # Clasificar por tipo
            if comp.tipo_comprobante in [1, 6, 11]:  # Facturas
                total_facturas += comp.total
            elif comp.tipo_comprobante in [3, 8, 13]:  # Notas de crédito
                total_nc += comp.total
            elif comp.tipo_comprobante in [2, 7, 12]:  # Notas de débito
                total_nd += comp.total
        
        total_neto = total_facturas + total_nd - total_nc
        
        resumen = {
            "total_facturas": float(total_facturas),
            "total_notas_credito": float(total_nc),
            "total_notas_debito": float(total_nd),
            "total_neto": float(total_neto),
            "cantidad_comprobantes": len(comprobantes),
            "periodo": {
                "desde": desde.strftime("%d/%m/%Y"),
                "hasta": hasta.strftime("%d/%m/%Y")
            }
        }
        
        return {
            "comprobantes": comprobantes_list,
            "resumen": resumen
        }
    
    async def generar_reporte_iva(
        self,
        db: AsyncSession,
        empresa_id: int,
        periodo_mes: int,
        periodo_anio: int
    ) -> Dict[str, Any]:
        """
        Genera subdiario de IVA ventas para DDJJ.
        
        Args:
            db: Sesión de base de datos
            empresa_id: ID de la empresa
            periodo_mes: Mes del período (1-12)
            periodo_anio: Año del período
            
        Returns:
            Diccionario con detalle de IVA
        """
        # Calcular primer y último día del mes
        desde = date(periodo_anio, periodo_mes, 1)
        ultimo_dia = monthrange(periodo_anio, periodo_mes)[1]
        hasta = date(periodo_anio, periodo_mes, ultimo_dia)
        
        comprobantes = await self.obtener_comprobantes_por_periodo(
            db, empresa_id, desde, hasta
        )
        
        # Procesar IVA
        total_gravado_21 = Decimal(0)
        total_gravado_10_5 = Decimal(0)
        total_gravado_27 = Decimal(0)
        total_iva_21 = Decimal(0)
        total_iva_10_5 = Decimal(0)
        total_iva_27 = Decimal(0)
        total_no_gravado = Decimal(0)
        total_exento = Decimal(0)
        
        comprobantes_list = []
        for comp in comprobantes:
            # Calcular neto gravado por cada alícuota
            gravado_21 = comp.iva_21 / Decimal("0.21") if comp.iva_21 > 0 else Decimal(0)
            gravado_10_5 = comp.iva_10_5 / Decimal("0.105") if comp.iva_10_5 > 0 else Decimal(0)
            gravado_27 = comp.iva_27 / Decimal("0.27") if comp.iva_27 > 0 else Decimal(0)
            
            # Para comprobantes sin IVA (tipo C o exentos)
            neto_sin_iva = comp.total - comp.iva_21 - comp.iva_10_5 - comp.iva_27
            
            comp_dict = {
                "fecha_emision": comp.fecha_emision.strftime("%d/%m/%Y"),
                "tipo_letra": self._get_letra_comprobante(comp.tipo_comprobante),
                "tipo_nombre": self._get_nombre_tipo_comprobante(comp.tipo_comprobante)[:2],
                "punto_venta": comp.punto_venta.numero,
                "numero": comp.numero,
                "numero_completo": f"{comp.punto_venta.numero:04d}-{comp.numero:08d}",
                "cuit_receptor": comp.cliente.numero_documento,
                "razon_social_receptor": comp.cliente.razon_social,
                "gravado_21": float(gravado_21),
                "iva_21": float(comp.iva_21),
                "gravado_10_5": float(gravado_10_5),
                "iva_10_5": float(comp.iva_10_5),
                "gravado_27": float(gravado_27),
                "iva_27": float(comp.iva_27),
                "no_gravado": 0,  # TODO: implementar si hay items no gravados
                "exento": 0,  # TODO: implementar si hay items exentos
                "total": float(comp.total),
            }
            comprobantes_list.append(comp_dict)
            
            # Acumular totales
            total_gravado_21 += gravado_21
            total_iva_21 += comp.iva_21
            total_gravado_10_5 += gravado_10_5
            total_iva_10_5 += comp.iva_10_5
            total_gravado_27 += gravado_27
            total_iva_27 += comp.iva_27
        
        total_neto = total_gravado_21 + total_gravado_10_5 + total_gravado_27 + total_no_gravado + total_exento
        total_iva = total_iva_21 + total_iva_10_5 + total_iva_27
        
        resumen = {
            "gravado_21": float(total_gravado_21),
            "iva_21": float(total_iva_21),
            "gravado_10_5": float(total_gravado_10_5),
            "iva_10_5": float(total_iva_10_5),
            "gravado_27": float(total_gravado_27),
            "iva_27": float(total_iva_27),
            "no_gravado": float(total_no_gravado),
            "exento": float(total_exento),
            "total_neto": float(total_neto),
            "total_iva": float(total_iva),
            "periodo": {
                "mes": periodo_mes,
                "anio": periodo_anio,
                "nombre": self._get_nombre_mes(periodo_mes)
            }
        }
        
        return {
            "comprobantes": comprobantes_list,
            "resumen": resumen
        }
    
    async def obtener_ranking_clientes(
        self,
        db: AsyncSession,
        empresa_id: int,
        desde: date,
        hasta: date,
        limite: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Obtiene ranking de clientes por facturación.
        
        Args:
            db: Sesión de base de datos
            empresa_id: ID de la empresa
            desde: Fecha desde
            hasta: Fecha hasta
            limite: Cantidad de clientes a devolver
            
        Returns:
            Lista de clientes con totales
        """
        # Obtener todos los comprobantes del período
        comprobantes = await self.obtener_comprobantes_por_periodo(
            db, empresa_id, desde, hasta
        )
        
        # Agrupar por cliente
        totales_por_cliente = {}
        for comp in comprobantes:
            cliente_id = comp.cliente.id
            if cliente_id not in totales_por_cliente:
                totales_por_cliente[cliente_id] = {
                    "cliente_id": cliente_id,
                    "razon_social": comp.cliente.razon_social,
                    "numero_documento": comp.cliente.numero_documento,
                    "total_facturado": Decimal(0),
                    "cantidad_comprobantes": 0
                }
            
            # Sumar o restar según el tipo
            if comp.tipo_comprobante in [1, 6, 11]:  # Facturas
                totales_por_cliente[cliente_id]["total_facturado"] += comp.total
            elif comp.tipo_comprobante in [3, 8, 13]:  # NC
                totales_por_cliente[cliente_id]["total_facturado"] -= comp.total
            elif comp.tipo_comprobante in [2, 7, 12]:  # ND
                totales_por_cliente[cliente_id]["total_facturado"] += comp.total
            
            totales_por_cliente[cliente_id]["cantidad_comprobantes"] += 1
        
        # Ordenar por total y limitar
        ranking = sorted(
            totales_por_cliente.values(),
            key=lambda x: x["total_facturado"],
            reverse=True
        )[:limite]
        
        # Convertir Decimal a float
        for item in ranking:
            item["total_facturado"] = float(item["total_facturado"])
        
        return ranking
    
    def _get_letra_comprobante(self, tipo: int) -> str:
        """Obtiene la letra del comprobante."""
        if tipo in [1, 2, 3]:
            return "A"
        elif tipo in [6, 7, 8]:
            return "B"
        elif tipo in [11, 12, 13]:
            return "C"
        return ""
    
    def _get_nombre_tipo_comprobante(self, tipo: int) -> str:
        """Obtiene el nombre corto del tipo de comprobante."""
        nombres = {
            1: "Factura A", 2: "Nota Débito A", 3: "Nota Crédito A",
            6: "Factura B", 7: "Nota Débito B", 8: "Nota Crédito B",
            11: "Factura C", 12: "Nota Débito C", 13: "Nota Crédito C",
        }
        return nombres.get(tipo, "Comprobante")
    
    def _get_nombre_mes(self, mes: int) -> str:
        """Obtiene el nombre del mes en español."""
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        return meses.get(mes, "")


# Instancia global del servicio
reportes_service = ReportesService()
