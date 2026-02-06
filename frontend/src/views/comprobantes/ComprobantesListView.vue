<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useComprobantesStore } from '@/stores/comprobantes'
import { useEmpresaStore } from '@/stores/empresa'
import {
  DocumentTextIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  EyeIcon,
  FunnelIcon,
} from '@heroicons/vue/24/outline'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseEmpty from '@/components/ui/BaseEmpty.vue'
import { TIPOS_COMPROBANTE_NOMBRES, ESTADOS_COMPROBANTE_NOMBRES } from '@/types/comprobante'

const router = useRouter()
const comprobantesStore = useComprobantesStore()
const empresaStore = useEmpresaStore()

// Filtros
const filtros = ref({
  buscar: '',
  desde: '',
  hasta: '',
  tipo: null as number | null,
})

const loading = ref(false)

onMounted(async () => {
  // Cargar empresa si no está cargada
  if (!empresaStore.empresa) {
    await empresaStore.cargarEmpresa()
  }
  
  // Cargar comprobantes
  await cargarComprobantes()
})

const empresaId = computed(() => empresaStore.empresa?.id || 0)

const cargarComprobantes = async (page = 1) => {
  if (!empresaId.value) return
  
  loading.value = true
  
  try {
    await comprobantesStore.listarComprobantes({
      empresa_id: empresaId.value,
      page,
      per_page: 20,
      desde: filtros.value.desde || undefined,
      hasta: filtros.value.hasta || undefined,
      tipo: filtros.value.tipo || undefined,
      buscar: filtros.value.buscar || undefined,
    })
  } catch (error) {
    console.error('Error al cargar comprobantes:', error)
  } finally {
    loading.value = false
  }
}

const aplicarFiltros = () => {
  cargarComprobantes(1)
}

const limpiarFiltros = () => {
  filtros.value = {
    buscar: '',
    desde: '',
    hasta: '',
    tipo: null,
  }
  cargarComprobantes(1)
}

const nuevaFactura = () => {
  router.push({ name: 'comprobante-nuevo' })
}

const verDetalle = (id: number) => {
  router.push({ name: 'comprobante-detalle', params: { id } })
}

const formatMonto = (monto: number) => {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
  }).format(monto)
}

const formatFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString('es-AR')
}

const getTipoNombre = (tipo: number) => {
  return TIPOS_COMPROBANTE_NOMBRES[tipo] || `Tipo ${tipo}`
}

const getEstadoColor = (estado: string) => {
  switch (estado) {
    case 'autorizado':
      return 'bg-green-100 text-green-800'
    case 'rechazado':
      return 'bg-red-100 text-red-800'
    case 'pendiente':
      return 'bg-yellow-100 text-yellow-800'
    case 'anulado':
      return 'bg-gray-100 text-gray-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

const tiposDisponibles = [
  { value: 1, label: 'Factura A' },
  { value: 6, label: 'Factura B' },
  { value: 11, label: 'Factura C' },
  { value: 3, label: 'Nota Crédito A' },
  { value: 8, label: 'Nota Crédito B' },
  { value: 13, label: 'Nota Crédito C' },
]
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1
          class="text-3xl font-bold text-gray-900"
          data-testid="page-title"
        >
          Comprobantes
        </h1>
        <p class="mt-2 text-gray-600">
          Gestión de facturas y comprobantes electrónicos
        </p>
      </div>

      <button
        data-testid="comprobantes-nueva-factura"
        class="inline-flex items-center gap-2 px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        @click="nuevaFactura"
      >
        <PlusIcon class="h-5 w-5" />
        Nueva Factura
      </button>
    </div>

    <!-- Filtros -->
    <BaseCard class="mb-6">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <!-- Búsqueda -->
        <div class="md:col-span-2">
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Buscar
          </label>
          <div class="relative">
            <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              v-model="filtros.buscar"
              type="text"
              placeholder="Buscar por número o cliente..."
              class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              @keyup.enter="aplicarFiltros"
            >
          </div>
        </div>

        <!-- Desde -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Desde
          </label>
          <input
            v-model="filtros.desde"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
        </div>

        <!-- Hasta -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Hasta
          </label>
          <input
            v-model="filtros.hasta"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
        </div>

        <!-- Tipo -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Tipo
          </label>
          <select
            v-model="filtros.tipo"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option :value="null">
              Todos
            </option>
            <option
              v-for="tipo in tiposDisponibles"
              :key="tipo.value"
              :value="tipo.value"
            >
              {{ tipo.label }}
            </option>
          </select>
        </div>

        <!-- Botones -->
        <div class="md:col-span-3 flex items-end gap-2">
          <button
            class="inline-flex items-center gap-2 px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            @click="aplicarFiltros"
          >
            <FunnelIcon class="h-5 w-5" />
            Aplicar Filtros
          </button>

          <button
            class="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            @click="limpiarFiltros"
          >
            Limpiar
          </button>
        </div>
      </div>
    </BaseCard>

    <!-- Loading -->
    <div
      v-if="loading"
      class="text-center py-12"
    >
      <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      <p class="mt-4 text-gray-600">
        Cargando comprobantes...
      </p>
    </div>

    <!-- Lista de comprobantes -->
    <BaseCard v-else-if="comprobantesStore.hayComprobantes">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                Tipo
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                Número
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                Fecha
              </th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                Cliente
              </th>
              <th class="px-4 py-3 text-right text-xs font-medium text-gray-700 uppercase">
                Total
              </th>
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase">
                Estado
              </th>
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase">
                Acciones
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr
              v-for="comprobante in comprobantesStore.comprobantes"
              :key="comprobante.id"
              class="hover:bg-gray-50"
            >
              <td class="px-4 py-3 text-sm text-gray-900">
                {{ getTipoNombre(comprobante.tipo_comprobante) }}
              </td>
              <td class="px-4 py-3 text-sm font-mono text-gray-900">
                {{ String(comprobante.punto_venta_numero).padStart(4, '0') }}-{{ String(comprobante.numero).padStart(8, '0') }}
              </td>
              <td class="px-4 py-3 text-sm text-gray-600">
                {{ formatFecha(comprobante.fecha_emision) }}
              </td>
              <td class="px-4 py-3 text-sm text-gray-900">
                <div>{{ comprobante.cliente_nombre }}</div>
                <div class="text-xs text-gray-500">
                  {{ comprobante.cliente_documento }}
                </div>
              </td>
              <td class="px-4 py-3 text-sm text-right font-mono text-gray-900">
                {{ formatMonto(comprobante.total) }}
              </td>
              <td class="px-4 py-3 text-center">
                <span :class="['inline-flex items-center px-2 py-1 rounded-full text-xs font-medium', getEstadoColor(comprobante.estado)]">
                  {{ ESTADOS_COMPROBANTE_NOMBRES[comprobante.estado] || comprobante.estado }}
                </span>
              </td>
              <td class="px-4 py-3 text-center">
                <button
                  class="text-blue-600 hover:text-blue-700 p-1 rounded hover:bg-blue-50"
                  title="Ver detalle"
                  @click="verDetalle(comprobante.id)"
                >
                  <EyeIcon class="h-5 w-5" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Paginación -->
      <div
        v-if="comprobantesStore.totalPaginas > 1"
        class="mt-6 flex items-center justify-between"
      >
        <div class="text-sm text-gray-700">
          Mostrando {{ ((comprobantesStore.paginaActual - 1) * comprobantesStore.paginacion.per_page) + 1 }} 
          - 
          {{ Math.min(comprobantesStore.paginaActual * comprobantesStore.paginacion.per_page, comprobantesStore.totalComprobantes) }}
          de {{ comprobantesStore.totalComprobantes }} comprobantes
        </div>

        <div class="flex gap-2">
          <button
            :disabled="comprobantesStore.paginaActual === 1"
            class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            @click="comprobantesStore.cambiarPagina(comprobantesStore.paginaActual - 1)"
          >
            Anterior
          </button>

          <span class="px-3 py-1 text-gray-700">
            Página {{ comprobantesStore.paginaActual }} de {{ comprobantesStore.totalPaginas }}
          </span>

          <button
            :disabled="comprobantesStore.paginaActual === comprobantesStore.totalPaginas"
            class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            @click="comprobantesStore.cambiarPagina(comprobantesStore.paginaActual + 1)"
          >
            Siguiente
          </button>
        </div>
      </div>
    </BaseCard>

    <!-- Sin comprobantes -->
    <BaseCard v-else>
      <BaseEmpty
        title="No hay comprobantes"
        message="Comience emitiendo su primera factura electrónica"
        :icon="DocumentTextIcon"
      >
        <template #actions>
          <button
            data-testid="comprobantes-empty-nueva-factura"
            class="inline-flex items-center gap-2 px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700"
            @click="nuevaFactura"
          >
            <PlusIcon class="h-5 w-5" />
            Nueva Factura
          </button>
        </template>
      </BaseEmpty>
    </BaseCard>
  </div>
</template>
