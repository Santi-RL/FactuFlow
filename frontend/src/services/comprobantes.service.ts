/**
 * Servicio de API para Comprobantes
 */

import api from './api'
import type {
  EmitirComprobanteRequest,
  EmitirComprobanteResponse,
  ComprobanteDetalle,
  PaginatedComprobantesResponse,
  ProximoNumeroResponse,
} from '@/types/comprobante'

export interface ListarComprobantesParams {
  empresa_id: number
  desde?: string
  hasta?: string
  tipo?: number
  cliente_id?: number
  buscar?: string
  page?: number
  per_page?: number
}

export const comprobantesService = {
  /**
   * Lista comprobantes con filtros
   */
  async listar(params: ListarComprobantesParams): Promise<PaginatedComprobantesResponse> {
    const { data } = await api.get('/comprobantes', { params })
    return data
  },

  /**
   * Obtiene detalle de un comprobante
   */
  async obtener(id: number): Promise<ComprobanteDetalle> {
    const { data } = await api.get(`/comprobantes/${id}`)
    return data
  },

  /**
   * Emite un nuevo comprobante
   */
  async emitir(request: EmitirComprobanteRequest): Promise<EmitirComprobanteResponse> {
    const { data } = await api.post('/comprobantes/emitir', request)
    return data
  },

  /**
   * Obtiene el próximo número de comprobante
   */
  async proximoNumero(
    puntoVenta: number,
    tipoComprobante: number,
    empresaId: number
  ): Promise<ProximoNumeroResponse> {
    const { data } = await api.get(
      `/comprobantes/proximo-numero/${puntoVenta}/${tipoComprobante}`,
      { params: { empresa_id: empresaId } }
    )
    return data
  },
}

export default comprobantesService
