import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Cliente, ClienteCreate, ClienteUpdate, ClienteListParams } from '@/types/cliente'
import type { PaginatedResponse } from '@/types/api'
import { clientesService } from '@/services/clientes.service'

export const useClientesStore = defineStore('clientes', () => {
  const clientes = ref<Cliente[]>([])
  const clienteActual = ref<Cliente | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pagination = ref({
    total: 0,
    page: 1,
    per_page: 30,
    pages: 0
  })

  const fetchClientes = async (params?: ClienteListParams) => {
    loading.value = true
    error.value = null
    try {
      const response: PaginatedResponse<Cliente> = await clientesService.getAll(params)
      clientes.value = response.items
      pagination.value = {
        total: response.total,
        page: response.page,
        per_page: response.per_page,
        pages: response.pages
      }
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al cargar los clientes'
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchCliente = async (id: number) => {
    loading.value = true
    error.value = null
    try {
      clienteActual.value = await clientesService.getById(id)
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al cargar el cliente'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createCliente = async (data: ClienteCreate) => {
    loading.value = true
    error.value = null
    try {
      const newCliente = await clientesService.create(data)
      clientes.value.unshift(newCliente)
      return newCliente
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al crear el cliente'
      throw err
    } finally {
      loading.value = false
    }
  }

  const updateCliente = async (id: number, data: ClienteUpdate) => {
    loading.value = true
    error.value = null
    try {
      const updatedCliente = await clientesService.update(id, data)
      const index = clientes.value.findIndex(c => c.id === id)
      if (index !== -1) {
        clientes.value[index] = updatedCliente
      }
      clienteActual.value = updatedCliente
      return updatedCliente
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al actualizar el cliente'
      throw err
    } finally {
      loading.value = false
    }
  }

  const deleteCliente = async (id: number) => {
    loading.value = true
    error.value = null
    try {
      await clientesService.delete(id)
      clientes.value = clientes.value.filter(c => c.id !== id)
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al eliminar el cliente'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    clientes,
    clienteActual,
    loading,
    error,
    pagination,
    fetchClientes,
    fetchCliente,
    createCliente,
    updateCliente,
    deleteCliente
  }
})
