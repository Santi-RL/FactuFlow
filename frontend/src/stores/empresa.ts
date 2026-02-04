import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Empresa, EmpresaCreate, EmpresaUpdate } from '@/types/empresa'
import { empresaService } from '@/services/empresa.service'
import { useAuthStore } from '@/stores/auth'

export const useEmpresaStore = defineStore('empresa', () => {
  const empresa = ref<Empresa | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchEmpresa = async (id: number) => {
    loading.value = true
    error.value = null
    try {
      empresa.value = await empresaService.getById(id)
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al cargar la empresa'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createEmpresa = async (data: EmpresaCreate) => {
    loading.value = true
    error.value = null
    try {
      empresa.value = await empresaService.create(data)
      return empresa.value
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al crear la empresa'
      throw err
    } finally {
      loading.value = false
    }
  }

  const updateEmpresa = async (id: number, data: EmpresaUpdate) => {
    loading.value = true
    error.value = null
    try {
      empresa.value = await empresaService.update(id, data)
      return empresa.value
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al actualizar la empresa'
      throw err
    } finally {
      loading.value = false
    }
  }

  const cargarEmpresa = async () => {
    const authStore = useAuthStore()
    const empresaId = authStore.user?.empresa_id
    if (!empresaId) return
    await fetchEmpresa(empresaId)
  }

  return {
    empresa,
    loading,
    error,
    fetchEmpresa,
    cargarEmpresa,
    createEmpresa,
    updateEmpresa
  }
})
