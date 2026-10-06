import type { FiscalDecimal } from "@/utils/fiscal-decimal";

/**
 * Servicio para generación de reportes
 */

import api from "./api";

export interface ReporteVentas {
  comprobantes: ComprobanteReporte[];
  resumen: ResumenVentas;
}

export interface ComprobanteReporte {
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
  total_facturas: FiscalDecimal;
  total_notas_credito: FiscalDecimal;
  total_notas_debito: FiscalDecimal;
  total_neto: FiscalDecimal;
  cantidad_comprobantes: number;
  periodo: {
    desde: string;
    hasta: string;
  };
}

export interface ReporteIVA {
  comprobantes: ComprobanteIVA[];
  resumen: ResumenIVA;
}

export interface ComprobanteIVA {
  fecha_emision: string;
  tipo_letra: string;
  tipo_nombre: string;
  punto_venta: number;
  numero: number;
  numero_completo: string;
  cuit_receptor: string;
  razon_social_receptor: string;
  gravado_21: FiscalDecimal;
  iva_21: FiscalDecimal;
  gravado_10_5: FiscalDecimal;
  iva_10_5: FiscalDecimal;
  gravado_27: FiscalDecimal;
  iva_27: FiscalDecimal;
  no_gravado: FiscalDecimal;
  exento: FiscalDecimal;
  total: FiscalDecimal;
}

export interface ResumenIVA {
  gravado_21: FiscalDecimal;
  iva_21: FiscalDecimal;
  gravado_10_5: FiscalDecimal;
  iva_10_5: FiscalDecimal;
  gravado_27: FiscalDecimal;
  iva_27: FiscalDecimal;
  no_gravado: FiscalDecimal;
  exento: FiscalDecimal;
  total_neto: FiscalDecimal;
  total_iva: FiscalDecimal;
  periodo: {
    mes: number;
    anio: number;
    nombre: string;
  };
}

export interface RankingCliente {
  cliente_id: number;
  razon_social: string;
  numero_documento: string;
  total_facturado: FiscalDecimal;
  cantidad_comprobantes: number;
}

export interface ReporteClientes {
  total_general: FiscalDecimal;
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
