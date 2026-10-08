"""Servicio para generación de reportes."""

from datetime import date
from typing import List
from decimal import Decimal
from calendar import monthrange

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comprobante import Comprobante
from app.core.fiscal_storage import sum_decimals
from app.core.lecturas_fiscales import leer_bases_iva


class ReportesService:
    """Servicio para generación de reportes de ventas e IVA."""

    async def obtener_comprobantes_por_periodo(
        self, db: AsyncSession, empresa_id: int, desde: date, hasta: date
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
                selectinload(Comprobante.items),
            )
            .where(
                and_(
                    Comprobante.empresa_id == empresa_id,
                    Comprobante.fecha_emision >= desde,
                    Comprobante.fecha_emision <= hasta,
                    Comprobante.estado == "autorizado",
                )
            )
            .order_by(Comprobante.fecha_emision, Comprobante.numero)
        )

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    def _resumir_por_moneda(filas, campos):
        resumenes = []
        for moneda in sorted({fila["moneda"] for fila in filas}):
            grupo = [fila for fila in filas if fila["moneda"] == moneda]
            resumen = {"moneda": moneda, "cantidad_comprobantes": len(grupo)}
            for campo in campos:
                resumen[campo] = (
                    None
                    if any(fila[campo] is None for fila in grupo)
                    else str(sum_decimals(Decimal(fila[campo]) for fila in grupo))
                )
            resumen["cantidad_bases_no_acreditadas"] = sum(
                fila.get("bases_acreditadas") is False for fila in grupo
            )
            resumenes.append(resumen)
        return resumenes

    @staticmethod
    def _resumen_compatible(resumenes, campos):
        if len(resumenes) == 1:
            return dict(resumenes[0])
        return {
            "moneda": None,
            **{campo: None if resumenes else "0" for campo in campos},
        }

    async def generar_reporte_ventas(self, db, empresa_id, desde, hasta):
        comprobantes = await self.obtener_comprobantes_por_periodo(
            db, empresa_id, desde, hasta
        )
        filas = []
        campos = (
            "total_facturas",
            "total_notas_credito",
            "total_notas_debito",
            "total_neto",
        )
        for comp in comprobantes:
            fila = {
                "id": comp.id,
                "fecha_emision": comp.fecha_emision.isoformat(),
                "tipo_comprobante": comp.tipo_comprobante,
                "tipo_nombre": self._get_nombre_tipo_comprobante(comp.tipo_comprobante),
                "letra": self._get_letra_comprobante(comp.tipo_comprobante),
                "punto_venta": comp.punto_venta.numero,
                "numero": comp.numero,
                "numero_completo": f"{comp.punto_venta.numero:04d}-{comp.numero:08d}",
                "cliente_nombre": self._get_receptor_nombre(comp),
                "moneda": comp.moneda,
                "cotizacion": str(comp.cotizacion),
                "subtotal": str(comp.subtotal),
                "iva_total": str(
                    sum_decimals([comp.iva_21, comp.iva_10_5, comp.iva_27])
                ),
                "total": str(comp.total),
                "total_facturas": str(
                    comp.total if comp.tipo_comprobante in {1, 6, 11} else Decimal(0)
                ),
                "total_notas_credito": str(
                    comp.total if comp.tipo_comprobante in {3, 8, 13} else Decimal(0)
                ),
                "total_notas_debito": str(
                    comp.total if comp.tipo_comprobante in {2, 7, 12} else Decimal(0)
                ),
                "total_neto": str(
                    comp.total.copy_negate()
                    if comp.tipo_comprobante in {3, 8, 13}
                    else comp.total
                ),
            }
            filas.append(fila)
        por_moneda = self._resumir_por_moneda(filas, campos)
        resumen = self._resumen_compatible(por_moneda, campos)
        resumen.update(
            cantidad_comprobantes=len(filas),
            periodo={"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        )
        return {"comprobantes": filas, "resumen": resumen, "por_moneda": por_moneda}

    async def generar_reporte_iva(self, db, empresa_id, periodo_mes, periodo_anio):
        desde = date(periodo_anio, periodo_mes, 1)
        hasta = date(
            periodo_anio, periodo_mes, monthrange(periodo_anio, periodo_mes)[1]
        )
        comprobantes = await self.obtener_comprobantes_por_periodo(
            db, empresa_id, desde, hasta
        )
        filas = []
        campos = (
            "gravado_21",
            "iva_21",
            "gravado_10_5",
            "iva_10_5",
            "gravado_27",
            "iva_27",
            "no_gravado",
            "exento",
            "sin_clasificacion",
            "sin_iva_discriminado",
            "total_neto",
            "total_iva",
            "total",
        )
        for comp in comprobantes:
            bases = leer_bases_iva(comp)
            importes = {
                key: value
                for key, value in bases.items()
                if key not in {"bases_acreditadas", "origen_bases"}
            }
            importes.update(
                iva_21=comp.iva_21,
                iva_10_5=comp.iva_10_5,
                iva_27=comp.iva_27,
                total_neto=comp.subtotal,
                total_iva=sum_decimals([comp.iva_21, comp.iva_10_5, comp.iva_27]),
                total=comp.total,
            )
            negativo = self._get_signo_comprobante(comp.tipo_comprobante) < 0
            fila = {
                "fecha_emision": comp.fecha_emision.isoformat(),
                "tipo_letra": self._get_letra_comprobante(comp.tipo_comprobante),
                "tipo_nombre": self._get_abreviatura_tipo_comprobante(
                    comp.tipo_comprobante
                ),
                "punto_venta": comp.punto_venta.numero,
                "numero": comp.numero,
                "numero_completo": f"{comp.punto_venta.numero:04d}-{comp.numero:08d}",
                "cuit_receptor": self._get_receptor_documento(comp),
                "razon_social_receptor": self._get_receptor_nombre(comp),
                "moneda": comp.moneda,
                "cotizacion": str(comp.cotizacion),
                "bases_acreditadas": bases["bases_acreditadas"],
                "origen_bases": bases["origen_bases"],
                **{
                    key: (
                        None
                        if value is None
                        else str(value.copy_negate() if negativo else value)
                    )
                    for key, value in importes.items()
                },
            }
            filas.append(fila)
        por_moneda = self._resumir_por_moneda(filas, campos)
        resumen = self._resumen_compatible(por_moneda, campos)
        resumen.update(
            cantidad_comprobantes=len(filas),
            cantidad_bases_no_acreditadas=sum(
                not fila["bases_acreditadas"] for fila in filas
            ),
            periodo={
                "mes": periodo_mes,
                "anio": periodo_anio,
                "nombre": self._get_nombre_mes(periodo_mes),
            },
        )
        return {"comprobantes": filas, "resumen": resumen, "por_moneda": por_moneda}

    async def obtener_ranking_clientes(self, db, empresa_id, desde, hasta, limite=10):
        comprobantes = await self.obtener_comprobantes_por_periodo(
            db, empresa_id, desde, hasta
        )
        grupos = {}
        for comp in comprobantes:
            receptor = (
                f"cliente:{comp.cliente.id}"
                if comp.cliente
                else f"receptor:{self._get_receptor_documento(comp)}"
            )
            key = (comp.moneda, receptor)
            if key not in grupos:
                grupos[key] = {
                    "cliente_id": comp.cliente.id if comp.cliente else 0,
                    "razon_social": self._get_receptor_nombre(comp),
                    "numero_documento": self._get_receptor_documento(comp),
                    "moneda": comp.moneda,
                    "total_facturado": Decimal(0),
                    "cantidad_comprobantes": 0,
                }
            grupo = grupos[key]
            importe = (
                comp.total.copy_negate()
                if self._get_signo_comprobante(comp.tipo_comprobante) < 0
                else comp.total
            )
            grupo["total_facturado"] = sum_decimals([grupo["total_facturado"], importe])
            grupo["cantidad_comprobantes"] += 1
        ranking = []
        for moneda in sorted({key[0] for key in grupos}):
            clientes = sorted(
                (grupo for grupo in grupos.values() if grupo["moneda"] == moneda),
                key=lambda x: x["total_facturado"],
                reverse=True,
            )[:limite]
            ranking.extend(
                {**item, "total_facturado": str(item["total_facturado"])}
                for item in clientes
            )
        return ranking

    def _get_receptor_nombre(self, comprobante: Comprobante) -> str:
        """Nombre fiscal del receptor guardado en el comprobante."""
        if comprobante.receptor_razon_social:
            return comprobante.receptor_razon_social
        if comprobante.cliente:
            return comprobante.cliente.razon_social
        return "A CONSUMIDOR FINAL"

    def _get_receptor_documento(self, comprobante: Comprobante) -> str:
        """Documento del receptor guardado en el comprobante."""
        if comprobante.receptor_numero_documento:
            return comprobante.receptor_numero_documento
        if comprobante.cliente:
            return comprobante.cliente.numero_documento
        return "0"

    def _get_signo_comprobante(self, tipo: int) -> Decimal:
        """Devuelve el signo contable del tipo de comprobante."""
        if tipo in [3, 8, 13]:
            return Decimal("-1")
        return Decimal("1")

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
            1: "Factura A",
            2: "Nota Débito A",
            3: "Nota Crédito A",
            6: "Factura B",
            7: "Nota Débito B",
            8: "Nota Crédito B",
            11: "Factura C",
            12: "Nota Débito C",
            13: "Nota Crédito C",
        }
        return nombres.get(tipo, "Comprobante")

    def _get_abreviatura_tipo_comprobante(self, tipo: int) -> str:
        """Obtiene la abreviatura del tipo de comprobante para reportes."""
        abreviaturas = {
            1: "FA",
            2: "ND",
            3: "NC",  # Tipo A
            6: "FB",
            7: "ND",
            8: "NC",  # Tipo B
            11: "FC",
            12: "ND",
            13: "NC",  # Tipo C
        }
        return abreviaturas.get(tipo, "CO")

    def _get_nombre_mes(self, mes: int) -> str:
        """Obtiene el nombre del mes en español."""
        meses = {
            1: "Enero",
            2: "Febrero",
            3: "Marzo",
            4: "Abril",
            5: "Mayo",
            6: "Junio",
            7: "Julio",
            8: "Agosto",
            9: "Septiembre",
            10: "Octubre",
            11: "Noviembre",
            12: "Diciembre",
        }
        return meses.get(mes, "")


# Instancia global del servicio
reportes_service = ReportesService()
