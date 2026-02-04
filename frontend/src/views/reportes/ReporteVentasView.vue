<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotification } from '@/composables/useNotification'
import reportesService from '@/services/reportes.service'
import type { ReporteVentas } from '@/services/reportes.service'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseTable from '@/components/ui/BaseTable.vue'
import BaseEmpty from '@/components/ui/BaseEmpty.vue'
import { ArrowLeftIcon, DocumentChartBarIcon, ArrowDownTrayIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const authStore = useAuthStore()
const { showError } = useNotification()

const loading = ref(false)
const reporte = ref<ReporteVentas | null>(null)

// Fechas por defecto: mes actual
const hoy = new Date()
const primerDiaMes = new Date(hoy.getFullYear(), hoy.getMonth(), 1)
const ultimoDiaMes = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0)

const desde = ref(primerDiaMes.toISOString().split('T')[0])
const hasta = ref(ultimoDiaMes.toISOString().split('T')[0])

const columns = [
  { key: 'fecha_emision', label: 'Fecha', sortable: false },
  { key: 'tipo_nombre', label: 'Tipo', sortable: false },
  { key: 'numero_completo', label: 'Número', sortable: false },
  { key: 'cliente_nombre', label: 'Cliente', sortable: false },
  { key: 'total', label: 'Total', sortable: false }
]

const generarReporte = async () => {
  if (!authStore.user?.empresa_id) {
    showError('Error', 'No se encontró la empresa asociada')
    return
  }

  if (!desde.value || !hasta.value) {
    showError('Error', 'Debe seleccionar un rango de fechas')
    return
  }

  if (desde.value > hasta.value) {
    showError('Error', 'La fecha "desde" no puede ser mayor que la fecha "hasta"')
    return
  }

  loading.value = true
  try {
    reporte.value = await reportesService.obtenerReporteVentas(
      authStore.user.empresa_id,
      desde.value,
      hasta.value
    )
  } catch (error: any) {
    showError('Error', error.response?.data?.detail || 'No se pudo generar el reporte')
    reporte.value = null
  } finally {
    loading.value = false
  }
}

const formatearFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

const formatearMoneda = (valor: number) => {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 2
  }).format(valor)
}

const volver = () => {
  router.push('/reportes')
}

const exportarExcel = () => {
  // Placeholder para futura implementación
  showError('Próximamente', 'La exportación a Excel estará disponible en breve')
}

const resumenCards = computed(() => {
  if (!reporte.value) return []
  
  return [
    {
      label: 'Total Facturas',
      valor: formatearMoneda(reporte.value.resumen.total_facturas),
      color: 'text-green-600',
      bg: 'bg-green-50'
    },
    {
      label: 'Total Notas de Crédito',
      valor: formatearMoneda(reporte.value.resumen.total_notas_credito),
      color: 'text-red-600',
      bg: 'bg-red-50'
    },
    {
      label: 'Total Notas de Débito',
      valor: formatearMoneda(reporte.value.resumen.total_notas_debito),
      color: 'text-blue-600',
      bg: 'bg-blue-50'
    },
    {
      label: 'Total Neto',
      valor: formatearMoneda(reporte.value.resumen.total_neto),
      color: 'text-purple-600',
      bg: 'bg-purple-50'
    }
  ]
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center gap-4 mb-4">
        <button
          @click="volver"
          class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title="Volver"
        >
          <ArrowLeftIcon class="h-5 w-5 text-gray-600" />
        </button>
        <div>
          <h1 class="text-3xl font-bold text-gray-900">Reporte de Ventas</h1>
          <p class="mt-1 text-gray-600">Resumen de comprobantes emitidos por período</p>
        </div>
      </div>
    </div>

    <!-- Filtros -->
    <BaseCard class="mb-6">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <BaseInput
          v-model="desde"
          type="date"
          label="Desde"
          required
        />
        <BaseInput
          v-model="hasta"
          type="date"
          label="Hasta"
          required
        />
        <div class="flex items-end">
          <BaseButton
            @click="generarReporte"
            :disabled="loading"
            class="w-full"
          >
            <DocumentChartBarIcon class="h-5 w-5 mr-2" />
            Generar Reporte
          </BaseButton>
        </div>
      </div>
    </BaseCard>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <BaseSpinner />
    </div>

    <!-- Reporte -->
    <template v-else-if="reporte">
      <!-- Resumen -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <BaseCard
          v-for="card in resumenCards"
          :key="card.label"
          :padding="false"
        >
          <div class="p-6">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-gray-600">{{ card.label }}</p>
                <p :class="['mt-2 text-2xl font-bold', card.color]">
                  {{ card.valor }}
                </p>
              </div>
              <div :class="['p-3 rounded-lg', card.bg]">
                <DocumentChartBarIcon :class="['h-6 w-6', card.color]" />
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Período -->
      <div class="mb-4 text-sm text-gray-600">
        <p>
          <span class="font-medium">Período:</span>
          {{ formatearFecha(reporte.resumen.periodo.desde) }} - 
          {{ formatearFecha(reporte.resumen.periodo.hasta) }}
        </p>
        <p>
          <span class="font-medium">Total comprobantes:</span>
          {{ reporte.resumen.cantidad_comprobantes }}
        </p>
      </div>

      <!-- Tabla de Comprobantes -->
      <BaseCard>
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold text-gray-900">Detalle de Comprobantes</h2>
          <BaseButton
            @click="exportarExcel"
            variant="secondary"
            size="sm"
          >
            <ArrowDownTrayIcon class="h-4 w-4 mr-2" />
            Exportar Excel
          </BaseButton>
        </div>

        <BaseTable
          v-if="reporte.comprobantes.length > 0"
          :columns="columns"
          :data="reporte.comprobantes"
          :loading="false"
        >
          <template #cell-fecha_emision="{ value }">
            <span class="text-gray-900">{{ formatearFecha(value) }}</span>
          </template>

          <template #cell-tipo_nombre="{ row }">
            <div>
              <span class="font-medium">{{ row.letra }}</span>
              <span class="text-gray-600 text-sm ml-1">{{ row.tipo_nombre }}</span>
            </div>
          </template>

          <template #cell-numero_completo="{ value }">
            <span class="font-mono text-sm">{{ value }}</span>
          </template>

          <template #cell-cliente_nombre="{ value }">
            <span class="text-gray-900">{{ value }}</span>
          </template>

          <template #cell-total="{ value }">
            <span class="font-semibold text-gray-900">{{ formatearMoneda(value) }}</span>
          </template>
        </BaseTable>

        <BaseEmpty v-else>
          No hay comprobantes en el período seleccionado
        </BaseEmpty>
      </BaseCard>
    </template>

    <!-- Estado inicial -->
    <BaseEmpty v-else>
      <DocumentChartBarIcon class="h-12 w-12 mx-auto mb-4 text-gray-400" />
      <p class="text-gray-600">
        Seleccione un rango de fechas y haga clic en "Generar Reporte" para ver los resultados
      </p>
    </BaseEmpty>
  </div>
</template>
