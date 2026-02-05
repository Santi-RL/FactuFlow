import apiClient from './api'
import type { PuntoVenta, PuntoVentaCreate, PuntoVentaUpdate } from '@/types/punto_venta'

export const puntosVentaService = {
  async getAll(): Promise<PuntoVenta[]> {
    const response = await apiClient.get<PuntoVenta[]>('/api/puntos-venta')
    return response.data
  },

  async create(data: PuntoVentaCreate): Promise<PuntoVenta> {
    const response = await apiClient.post<PuntoVenta>('/api/puntos-venta', data)
    return response.data
  },

  async update(id: number, data: PuntoVentaUpdate): Promise<PuntoVenta> {
    const response = await apiClient.put<PuntoVenta>(`/api/puntos-venta/${id}`, data)
    return response.data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/api/puntos-venta/${id}`)
  }
}
