<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useComprobantesStore } from '@/stores/comprobantes'
import { DocumentTextIcon, ArrowLeftIcon, ArrowDownTrayIcon } from '@heroicons/vue/24/outline'
import BaseCard from '@/components/ui/BaseCard.vue'
import { TIPOS_COMPROBANTE_NOMBRES, ESTADOS_COMPROBANTE_NOMBRES } from '@/types/comprobante'
import pdfService from '@/services/pdf.service'

const route = useRoute()
const router = useRouter()
const comprobantesStore = useComprobantesStore()

const loading = ref(true)

onMounted(async () => {
  const id = parseInt(route.params.id as string)
  
  try {
    await comprobantesStore.obtenerComprobante(id)
  } catch (error) {
    console.error('Error al cargar comprobante:', error)
    alert('Error al cargar el comprobante')
  } finally {
    loading.value = false
  }
})

const comprobante = computed(() => comprobantesStore.comprobanteActual)

const tipoComprobanteNombre = computed(() => {
  if (!comprobante.value) return ''
  return TIPOS_COMPROBANTE_NOMBRES[comprobante.value.tipo_comprobante] || 'Comprobante'
})

const estadoNombre = computed(() => {
  if (!comprobante.value) return ''
  return ESTADOS_COMPROBANTE_NOMBRES[comprobante.value.estado] || comprobante.value.estado
})

const estadoColor = computed(() => {
  if (!comprobante.value) return 'gray'
  
  switch (comprobante.value.estado) {
    case 'autorizado':
      return 'green'
    case 'rechazado':
      return 'red'
    case 'pendiente':
      return 'yellow'
    case 'anulado':
      return 'gray'
    default:
      return 'gray'
  }
})

const numeroCompleto = computed(() => {
  if (!comprobante.value) return ''
  const puntoVenta = String(comprobante.value.punto_venta_numero || 0).padStart(4, '0')
  const numero = String(comprobante.value.numero).padStart(8, '0')
  return `${puntoVenta}-${numero}`
})

const formatMonto = (monto: number) => {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
  }).format(monto)
}

const formatFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString('es-AR')
}

const volver = () => {
  router.push({ name: 'comprobantes' })
}

const descargandoPDF = ref(false)

const descargarPDF = async () => {
  if (!comprobante.value) return
  
  descargandoPDF.value = true
  try {
    const letra = obtenerLetraComprobante(comprobante.value.tipo_comprobante)
    const filename = `${tipoComprobanteNombre.value}_${letra}_${numeroCompleto.value}.pdf`
    await pdfService.descargarAutomatico(comprobante.value.id, filename)
  } catch (error) {
    console.error('Error al descargar PDF:', error)
    alert('Error al descargar el PDF. Por favor, inténtalo de nuevo.')
  } finally {
    descargandoPDF.value = false
  }
}

const previsualizarPDF = async () => {
  if (!comprobante.value) return
  
  try {
    await pdfService.previsualizarPDF(comprobante.value.id)
  } catch (error) {
    console.error('Error al previsualizar PDF:', error)
    alert('Error al previsualizar el PDF. Por favor, inténtalo de nuevo.')
  }
}

const obtenerLetraComprobante = (tipo: number): string => {
  if ([1, 2, 3].includes(tipo)) return 'A'
  if ([6, 7, 8].includes(tipo)) return 'B'
  if ([11, 12, 13].includes(tipo)) return 'C'
  return ''
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <button
          class="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-2"
          @click="volver"
        >
          <ArrowLeftIcon class="h-4 w-4" />
          Volver al listado
        </button>
        <h1 class="text-3xl font-bold text-gray-900 flex items-center gap-3">
          <DocumentTextIcon class="h-8 w-8" />
          {{ tipoComprobanteNombre }} {{ numeroCompleto }}
        </h1>
      </div>

      <div
        v-if="comprobante && comprobante.estado === 'autorizado'"
        class="flex gap-2"
      >
        <button
          class="inline-flex items-center gap-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          @click="previsualizarPDF"
        >
          <svg
            class="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
            />
          </svg>
          Ver PDF
        </button>
        <button
          :disabled="descargandoPDF"
          class="inline-flex items-center gap-2 px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="descargarPDF"
        >
          <ArrowDownTrayIcon class="h-5 w-5" />
          <span v-if="!descargandoPDF">Descargar PDF</span>
          <span v-else>Descargando...</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div
      v-if="loading"
      class="text-center py-12"
    >
      <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      <p class="mt-4 text-gray-600">
        Cargando comprobante...
      </p>
    </div>

    <!-- Contenido -->
    <div
      v-else-if="comprobante"
      class="space-y-6"
    >
      <!-- Información general -->
      <BaseCard>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-500 mb-1">Tipo</label>
            <p class="text-lg font-semibold text-gray-900">
              {{ tipoComprobanteNombre }}
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-500 mb-1">Número</label>
            <p class="text-lg font-mono font-semibold text-gray-900">
              {{ numeroCompleto }}
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-500 mb-1">Estado</label>
            <span
              :class="[
                'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium',
                estadoColor === 'green' && 'bg-green-100 text-green-800',
                estadoColor === 'red' && 'bg-red-100 text-red-800',
                estadoColor === 'yellow' && 'bg-yellow-100 text-yellow-800',
                estadoColor === 'gray' && 'bg-gray-100 text-gray-800',
              ]"
            >
              {{ estadoNombre }}
            </span>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-500 mb-1">Fecha Emisión</label>
            <p class="text-gray-900">
              {{ formatFecha(comprobante.fecha_emision) }}
            </p>
          </div>

          <div v-if="comprobante.cae">
            <label class="block text-sm font-medium text-gray-500 mb-1">CAE</label>
            <p class="text-gray-900 font-mono">
              {{ comprobante.cae }}
            </p>
          </div>

          <div v-if="comprobante.cae_vencimiento">
            <label class="block text-sm font-medium text-gray-500 mb-1">Vencimiento CAE</label>
            <p class="text-gray-900">
              {{ formatFecha(comprobante.cae_vencimiento) }}
            </p>
          </div>
        </div>
      </BaseCard>

      <!-- Cliente -->
      <BaseCard title="👤 Cliente">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-500 mb-1">Razón Social</label>
            <p class="text-gray-900">
              {{ comprobante.cliente_nombre }}
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-500 mb-1">CUIT / Documento</label>
            <p class="text-gray-900">
              {{ comprobante.cliente_cuit }}
            </p>
          </div>
        </div>
      </BaseCard>

      <!-- Items -->
      <BaseCard title="📦 Detalle">
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                  Código
                </th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">
                  Descripción
                </th>
                <th class="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase">
                  Cantidad
                </th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-700 uppercase">
                  Precio Unit.
                </th>
                <th class="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase">
                  IVA
                </th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-700 uppercase">
                  Subtotal
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr
                v-for="item in comprobante.items"
                :key="item.id"
              >
                <td class="px-4 py-3 text-sm text-gray-600">
                  {{ item.codigo || '-' }}
                </td>
                <td class="px-4 py-3 text-sm text-gray-900">
                  {{ item.descripcion }}
                </td>
                <td class="px-4 py-3 text-sm text-center text-gray-900">
                  {{ item.cantidad }} {{ item.unidad }}
                </td>
                <td class="px-4 py-3 text-sm text-right font-mono text-gray-900">
                  {{ formatMonto(item.precio_unitario) }}
                </td>
                <td class="px-4 py-3 text-sm text-center text-gray-600">
                  {{ item.iva_porcentaje }}%
                </td>
                <td class="px-4 py-3 text-sm text-right font-mono text-gray-900">
                  {{ formatMonto(item.subtotal ?? 0) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </BaseCard>

      <!-- Totales -->
      <BaseCard title="💰 Totales">
        <div class="flex justify-end">
          <div class="w-80 space-y-3">
            <div class="flex justify-between text-gray-700">
              <span class="font-medium">Subtotal:</span>
              <span class="font-mono">{{ formatMonto(comprobante.subtotal) }}</span>
            </div>

            <div
              v-if="comprobante.iva_21 > 0"
              class="flex justify-between text-gray-700"
            >
              <span class="font-medium">IVA 21%:</span>
              <span class="font-mono">{{ formatMonto(comprobante.iva_21) }}</span>
            </div>

            <div
              v-if="comprobante.iva_10_5 > 0"
              class="flex justify-between text-gray-700"
            >
              <span class="font-medium">IVA 10.5%:</span>
              <span class="font-mono">{{ formatMonto(comprobante.iva_10_5) }}</span>
            </div>

            <div
              v-if="comprobante.iva_27 > 0"
              class="flex justify-between text-gray-700"
            >
              <span class="font-medium">IVA 27%:</span>
              <span class="font-mono">{{ formatMonto(comprobante.iva_27) }}</span>
            </div>

            <div class="border-t border-gray-300 pt-3">
              <div class="flex justify-between text-xl font-bold text-gray-900">
                <span>TOTAL:</span>
                <span class="font-mono">{{ formatMonto(comprobante.total) }}</span>
              </div>
            </div>
          </div>
        </div>
      </BaseCard>

      <!-- Observaciones -->
      <BaseCard
        v-if="comprobante.observaciones"
        title="📝 Observaciones"
      >
        <p class="text-gray-700 whitespace-pre-line">
          {{ comprobante.observaciones }}
        </p>
      </BaseCard>
    </div>

    <!-- Error -->
    <div
      v-else
      class="text-center py-12"
    >
      <p class="text-red-600">
        Error al cargar el comprobante
      </p>
    </div>
  </div>
</template>
