/**
 * Servicio para generación de reportes
 */

import api from './api'

export interface ReporteVentas {
  comprobantes: ComprobanteReporte[]
  resumen: ResumenVentas
}

export interface ComprobanteReporte {
  id: number
  fecha_emision: string
  tipo_comprobante: number
  tipo_nombre: string
  letra: string
  punto_venta: number
  numero: number
  numero_completo: string
  cliente_nombre: string
  subtotal: number
  iva_total: number
  total: number
}

export interface ResumenVentas {
  total_facturas: number
  total_notas_credito: number
  total_notas_debito: number
  total_neto: number
  cantidad_comprobantes: number
  periodo: {
    desde: string
    hasta: string
  }
}

export interface ReporteIVA {
  comprobantes: ComprobanteIVA[]
  resumen: ResumenIVA
}

export interface ComprobanteIVA {
  fecha_emision: string
  tipo_letra: string
  tipo_nombre: string
  punto_venta: number
  numero: number
  numero_completo: string
  cuit_receptor: string
  razon_social_receptor: string
  gravado_21: number
  iva_21: number
  gravado_10_5: number
  iva_10_5: number
  gravado_27: number
  iva_27: number
  no_gravado: number
  exento: number
  total: number
}

export interface ResumenIVA {
  gravado_21: number
  iva_21: number
  gravado_10_5: number
  iva_10_5: number
  gravado_27: number
  iva_27: number
  no_gravado: number
  exento: number
  total_neto: number
  total_iva: number
  periodo: {
    mes: number
    anio: number
    nombre: string
  }
}

export interface RankingCliente {
  cliente_id: number
  razon_social: string
  numero_documento: string
  total_facturado: number
  cantidad_comprobantes: number
}

export interface ReporteClientes {
  clientes: RankingCliente[]
  periodo: {
    desde: string
    hasta: string
  }
}

class ReportesService {
  /**
   * Obtiene el reporte de ventas por período
   */
  async obtenerReporteVentas(
    empresaId: number,
    desde: string,
    hasta: string
  ): Promise<ReporteVentas> {
    const response = await api.get('/reportes/ventas', {
      params: {
        empresa_id: empresaId,
        desde,
        hasta
      }
    })
    return response.data
  }

  /**
   * Obtiene el subdiario de IVA ventas
   */
  async obtenerReporteIVA(
    empresaId: number,
    mes: number,
    anio: number
  ): Promise<ReporteIVA> {
    const response = await api.get('/reportes/iva-ventas', {
      params: {
        empresa_id: empresaId,
        periodo_mes: mes,
        periodo_anio: anio
      }
    })
    return response.data
  }

  /**
   * Obtiene el ranking de clientes por facturación
   */
  async obtenerRankingClientes(
    empresaId: number,
    desde: string,
    hasta: string,
    limite: number = 10
  ): Promise<ReporteClientes> {
    const response = await api.get('/reportes/clientes', {
      params: {
        empresa_id: empresaId,
        desde,
        hasta,
        limite
      }
    })
    return response.data
  }
}

export default new ReportesService()
