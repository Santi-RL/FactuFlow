/**
 * Servicio de API para Comprobantes
 */

import api from "./api";
import type {
  EmitirComprobanteRequest,
  EmitirComprobanteResponse,
  ComprobanteDetalle,
  PaginatedComprobantesResponse,
  ProximoNumeroResponse,
} from "@/types/comprobante";

export interface ListarComprobantesParams {
  desde?: string;
  hasta?: string;
  tipo?: number;
  cliente_id?: number;
  buscar?: string;
  page?: number;
  per_page?: number;
}

export const comprobantesService = {
  /**
   * Lista comprobantes con filtros
   */
  async listar(
    params: ListarComprobantesParams,
  ): Promise<PaginatedComprobantesResponse> {
    const { data } = await api.get("/api/comprobantes/", { params });
    return data;
  },

  /**
   * Obtiene detalle de un comprobante
   */
  async obtener(id: number): Promise<ComprobanteDetalle> {
    const { data } = await api.get(`/api/comprobantes/${id}`);
    return data;
  },

  /**
   * Emite un nuevo comprobante
   */
  async emitir(
    request: EmitirComprobanteRequest,
  ): Promise<EmitirComprobanteResponse> {
    const { data } = await api.post("/api/comprobantes/emitir", request);
    return data;
  },

  /**
   * Obtiene el próximo número de comprobante
   */
  async proximoNumero(
    puntoVenta: number,
    tipoComprobante: number,
  ): Promise<ProximoNumeroResponse> {
    const { data } = await api.get(
      `/api/comprobantes/proximo-numero/${puntoVenta}/${tipoComprobante}`,
    );
    return data;
  },
};

export default comprobantesService;
