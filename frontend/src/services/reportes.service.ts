import type { FiscalDecimal } from "@/utils/fiscal-decimal";

/**
 * Servicio para generación de reportes
 */

import api from "./api";

export interface ReporteVentas {
  comprobantes: ComprobanteReporte[];
  resumen: ResumenVentas;
  por_moneda?: ResumenVentas[];
}

export interface ComprobanteReporte {
  cotizacion?: FiscalDecimal;
  moneda?: string | null;
  id: number;
  fecha_emision: string;
  tipo_comprobante: number;
  tipo_nombre: string;
  letra: string;
  punto_venta: number;
  numero: number;
  numero_completo: string;
  cliente_nombre: string;
  subtotal: FiscalDecimal;
  iva_total: FiscalDecimal;
  total: FiscalDecimal;
}

export interface ResumenVentas {
  moneda?: string | null;
  total_facturas: FiscalDecimal | null;
  total_notas_credito: FiscalDecimal | null;
  total_notas_debito: FiscalDecimal | null;
  total_neto: FiscalDecimal | null;
  cantidad_comprobantes: number;
  periodo: {
    desde: string;
    hasta: string;
  };
}

export interface ReporteIVA {
  comprobantes: ComprobanteIVA[];
  resumen: ResumenIVA;
  por_moneda?: ResumenIVA[];
}

export interface ComprobanteIVA {
  bases_acreditadas?: boolean;
  origen_bases?: string;
  sin_clasificacion?: FiscalDecimal | null;
  sin_iva_discriminado?: FiscalDecimal | null;
  cantidad_bases_no_acreditadas?: number;
  cotizacion?: FiscalDecimal;
  moneda?: string | null;
  fecha_emision: string;
  tipo_letra: string;
  tipo_nombre: string;
  punto_venta: number;
  numero: number;
  numero_completo: string;
  cuit_receptor: string;
  razon_social_receptor: string;
  gravado_21: FiscalDecimal | null;
  iva_21: FiscalDecimal | null;
  gravado_10_5: FiscalDecimal | null;
  iva_10_5: FiscalDecimal | null;
  gravado_27: FiscalDecimal | null;
  iva_27: FiscalDecimal | null;
  no_gravado: FiscalDecimal | null;
  exento: FiscalDecimal | null;
  total: FiscalDecimal;
}

export interface ResumenIVA {
  sin_clasificacion?: FiscalDecimal | null;
  sin_iva_discriminado?: FiscalDecimal | null;
  cantidad_bases_no_acreditadas?: number;
  moneda?: string | null;
  gravado_21: FiscalDecimal | null;
  iva_21: FiscalDecimal | null;
  gravado_10_5: FiscalDecimal | null;
  iva_10_5: FiscalDecimal | null;
  gravado_27: FiscalDecimal | null;
  iva_27: FiscalDecimal | null;
  no_gravado: FiscalDecimal | null;
  exento: FiscalDecimal | null;
  total_neto: FiscalDecimal | null;
  total_iva: FiscalDecimal | null;
  periodo: {
    mes: number;
    anio: number;
    nombre: string;
  };
}

export interface RankingCliente {
  moneda?: string | null;
  cliente_id: number;
  razon_social: string;
  numero_documento: string;
  total_facturado: FiscalDecimal;
  cantidad_comprobantes: number;
}

export interface ReporteClientes {
  moneda?: string | null;
  por_moneda?: {
    moneda: string;
    clientes: RankingCliente[];
    total_general: FiscalDecimal;
  }[];
  total_general: FiscalDecimal | null;
  clientes: RankingCliente[];
  periodo: {
    desde: string;
    hasta: string;
  };
}

class ReportesService {
  /**
   * Obtiene el reporte de ventas por período
   */
  async obtenerReporteVentas(
    desde: string,
    hasta: string,
  ): Promise<ReporteVentas> {
    const response = await api.get("/api/reportes/ventas", {
      params: {
        desde,
        hasta,
      },
    });
    return response.data;
  }

  /**
   * Obtiene el subdiario de IVA ventas
   */
  async obtenerReporteIVA(mes: number, anio: number): Promise<ReporteIVA> {
    const response = await api.get("/api/reportes/iva-ventas", {
      params: {
        periodo_mes: mes,
        periodo_anio: anio,
      },
    });
    return response.data;
  }

  /**
   * Obtiene el ranking de clientes por facturación
   */
  async obtenerRankingClientes(
    desde: string,
    hasta: string,
    limite: number = 10,
  ): Promise<ReporteClientes> {
    const response = await api.get("/api/reportes/clientes", {
      params: {
        desde,
        hasta,
        limite,
      },
    });
    return response.data;
  }
}

export default new ReportesService();
