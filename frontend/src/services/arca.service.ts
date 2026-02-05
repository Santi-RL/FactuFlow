import apiClient from './api'
import type { PuntoVentaArca } from '@/types/punto_venta'

export const arcaService = {
  async getStatus(): Promise<any> {
    const response = await apiClient.get('/api/arca/status')
    return response.data
  },

  async testConnection(): Promise<any> {
    const response = await apiClient.post('/api/arca/test')
    return response.data
  },

  async getPuntosVenta(): Promise<PuntoVentaArca[]> {
    const response = await apiClient.get<PuntoVentaArca[]>('/api/arca/puntos-venta')
    return response.data
  }
}
