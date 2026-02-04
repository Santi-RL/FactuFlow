/**
 * Store de Comprobantes con Pinia
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import comprobantesService, { type ListarComprobantesParams } from '@/services/comprobantes.service'
import type {
  ComprobanteListItem,
  ComprobanteDetalle,
  EmitirComprobanteRequest,
  EmitirComprobanteResponse,
  PaginatedComprobantesResponse,
} from '@/types/comprobante'

export const useComprobantesStore = defineStore('comprobantes', () => {
  // State
  const comprobantes = ref<ComprobanteListItem[]>([])
  const comprobanteActual = ref<ComprobanteDetalle | null>(null)
  const paginacion = ref({
    total: 0,
    page: 1,
    per_page: 20,
    pages: 0,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Filtros actuales
  const filtros = ref<Partial<ListarComprobantesParams>>({})

  // Getters
  const totalComprobantes = computed(() => paginacion.value.total)
  const hayComprobantes = computed(() => comprobantes.value.length > 0)
  const paginaActual = computed(() => paginacion.value.page)
  const totalPaginas = computed(() => paginacion.value.pages)

  // Actions
  async function listarComprobantes(params: ListarComprobantesParams) {
    loading.value = true
    error.value = null
    filtros.value = params

    try {
      const response: PaginatedComprobantesResponse = await comprobantesService.listar(params)
      
      comprobantes.value = response.items
      paginacion.value = {
        total: response.total,
        page: response.page,
        per_page: response.per_page,
        pages: response.pages,
      }

      return response
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Error al listar comprobantes'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function obtenerComprobante(id: number) {
    loading.value = true
    error.value = null

    try {
      const comprobante = await comprobantesService.obtener(id)
      comprobanteActual.value = comprobante
      return comprobante
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Error al obtener comprobante'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function emitirComprobante(
    request: EmitirComprobanteRequest
  ): Promise<EmitirComprobanteResponse> {
    loading.value = true
    error.value = null

    try {
      const response = await comprobantesService.emitir(request)
      
      if (!response.exito) {
        error.value = response.mensaje
        return response
      }

      // Recargar listado si hay filtros activos
      if (filtros.value.empresa_id) {
        await listarComprobantes(filtros.value as ListarComprobantesParams)
      }

      return response
    } catch (e: any) {
      const errorMsg = e.response?.data?.detail?.mensaje || 'Error al emitir comprobante'
      const errores = e.response?.data?.detail?.errores || []
      
      error.value = `${errorMsg}: ${errores.join(', ')}`
      throw e
    } finally {
      loading.value = false
    }
  }

  async function obtenerProximoNumero(
    puntoVenta: number,
    tipoComprobante: number,
    empresaId: number
  ) {
    try {
      const response = await comprobantesService.proximoNumero(
        puntoVenta,
        tipoComprobante,
        empresaId
      )
      return response.proximo_numero
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Error al obtener próximo número'
      throw e
    }
  }

  function limpiarComprobanteActual() {
    comprobanteActual.value = null
  }

  function limpiarError() {
    error.value = null
  }

  function cambiarPagina(pagina: number) {
    if (filtros.value.empresa_id) {
      listarComprobantes({
        ...filtros.value,
        page: pagina,
      } as ListarComprobantesParams)
    }
  }

  return {
    // State
    comprobantes,
    comprobanteActual,
    paginacion,
    loading,
    error,
    filtros,
    
    // Getters
    totalComprobantes,
    hayComprobantes,
    paginaActual,
    totalPaginas,
    
    // Actions
    listarComprobantes,
    obtenerComprobante,
    emitirComprobante,
    obtenerProximoNumero,
    limpiarComprobanteActual,
    limpiarError,
    cambiarPagina,
  }
})
