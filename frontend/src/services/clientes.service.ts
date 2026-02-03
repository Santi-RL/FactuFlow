import apiClient from './api'
import type { Cliente, ClienteCreate, ClienteUpdate, ClienteListParams } from '@/types/cliente'
import type { PaginatedResponse } from '@/types/api'

export const clientesService = {
  async getAll(params?: ClienteListParams): Promise<PaginatedResponse<Cliente>> {
    const response = await apiClient.get<PaginatedResponse<Cliente>>('/api/clientes', { params })
    return response.data
  },

  async getById(id: number): Promise<Cliente> {
    const response = await apiClient.get<Cliente>(`/api/clientes/${id}`)
    return response.data
  },

  async create(data: ClienteCreate): Promise<Cliente> {
    const response = await apiClient.post<Cliente>('/api/clientes', data)
    return response.data
  },

  async update(id: number, data: ClienteUpdate): Promise<Cliente> {
    const response = await apiClient.put<Cliente>(`/api/clientes/${id}`, data)
    return response.data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/api/clientes/${id}`)
  }
}
