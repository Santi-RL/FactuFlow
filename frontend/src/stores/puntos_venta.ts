import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { PuntoVenta, PuntoVentaCreate, PuntoVentaUpdate, PuntoVentaArca } from '@/types/punto_venta'
import { puntosVentaService } from '@/services/puntos_venta.service'
import { arcaService } from '@/services/arca.service'

interface SyncResult {
  total_arca: number
  nuevos: number
  existentes: number
}

export const usePuntosVentaStore = defineStore('puntosVenta', () => {
  const puntosVenta = ref<PuntoVenta[]>([])
  const loading = ref(false)
  const syncing = ref(false)
  const error = ref<string | null>(null)

  const fetchPuntosVenta = async () => {
    loading.value = true
    error.value = null
    try {
      const data = await puntosVentaService.getAll()
      puntosVenta.value = data.sort((a, b) => a.numero - b.numero)
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al cargar los puntos de venta'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createPuntoVenta = async (data: PuntoVentaCreate) => {
    loading.value = true
    error.value = null
    try {
      const nuevo = await puntosVentaService.create(data)
      puntosVenta.value = [...puntosVenta.value, nuevo].sort((a, b) => a.numero - b.numero)
      return nuevo
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al crear el punto de venta'
      throw err
    } finally {
      loading.value = false
    }
  }

  const updatePuntoVenta = async (id: number, data: PuntoVentaUpdate) => {
    loading.value = true
    error.value = null
    try {
      const actualizado = await puntosVentaService.update(id, data)
      const index = puntosVenta.value.findIndex(pv => pv.id === id)
      if (index !== -1) {
        puntosVenta.value[index] = actualizado
      }
      puntosVenta.value = [...puntosVenta.value].sort((a, b) => a.numero - b.numero)
      return actualizado
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al actualizar el punto de venta'
      throw err
    } finally {
      loading.value = false
    }
  }

  const deletePuntoVenta = async (id: number) => {
    loading.value = true
    error.value = null
    try {
      await puntosVentaService.delete(id)
      puntosVenta.value = puntosVenta.value.filter(pv => pv.id !== id)
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al eliminar el punto de venta'
      throw err
    } finally {
      loading.value = false
    }
  }

  const syncFromArca = async (): Promise<SyncResult> => {
    syncing.value = true
    error.value = null
    try {
      const [puntosArca, locales] = await Promise.all([
        arcaService.getPuntosVenta(),
        puntosVentaService.getAll()
      ])

      const habilitados = puntosArca.filter((pv: PuntoVentaArca) => pv.bloqueado !== 'S' && !pv.fecha_baja)
      const existentes = new Set(locales.map(pv => pv.numero))
      const nuevos = habilitados.filter(pv => !existentes.has(pv.numero))

      const creados: PuntoVenta[] = []
      for (const pv of nuevos) {
        const creado = await puntosVentaService.create({ numero: pv.numero })
        creados.push(creado)
      }

      const merged = [...locales, ...creados]
      puntosVenta.value = merged.sort((a, b) => a.numero - b.numero)

      return {
        total_arca: habilitados.length,
        nuevos: creados.length,
        existentes: habilitados.length - creados.length
      }
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Error al sincronizar puntos de venta'
      throw err
    } finally {
      syncing.value = false
    }
  }

  return {
    puntosVenta,
    loading,
    syncing,
    error,
    fetchPuntosVenta,
    createPuntoVenta,
    updatePuntoVenta,
    deletePuntoVenta,
    syncFromArca
  }
})
