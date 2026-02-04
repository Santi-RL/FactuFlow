<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotification } from '@/composables/useNotification'
import { useFormatters } from '@/composables/useFormatters'
import reportesService from '@/services/reportes.service'
import type { ReporteClientes } from '@/services/reportes.service'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseEmpty from '@/components/ui/BaseEmpty.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import { 
  ArrowLeftIcon, 
  DocumentChartBarIcon, 
  TrophyIcon,
  UserIcon,
  DocumentTextIcon
} from '@heroicons/vue/24/outline'

const router = useRouter()
const authStore = useAuthStore()
const { showError } = useNotification()
const { formatearFecha, formatearMoneda, formatearCUIT } = useFormatters()

const loading = ref(false)
const reporte = ref<ReporteClientes | null>(null)

// Fechas por defecto: mes actual
const hoy = new Date()
const primerDiaMes = new Date(hoy.getFullYear(), hoy.getMonth(), 1)
const ultimoDiaMes = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0)

const desde = ref(primerDiaMes.toISOString().split('T')[0])
const hasta = ref(ultimoDiaMes.toISOString().split('T')[0])
const limite = ref('10')

const limitesDisponibles = [
  { value: '5', label: 'Top 5' },
  { value: '10', label: 'Top 10' },
  { value: '20', label: 'Top 20' },
  { value: '50', label: 'Top 50' }
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
    reporte.value = await reportesService.obtenerRankingClientes(
      authStore.user.empresa_id,
      desde.value,
      hasta.value,
      parseInt(limite.value)
    )
  } catch (error: any) {
    showError('Error', error.response?.data?.detail || 'No se pudo generar el reporte')
    reporte.value = null
  } finally {
    loading.value = false
  }
}

const volver = () => {
  router.push('/reportes')
}

const obtenerMedalla = (posicion: number) => {
  if (posicion === 1) return { emoji: '🥇', color: 'text-yellow-500', label: '1° Puesto' }
  if (posicion === 2) return { emoji: '🥈', color: 'text-gray-400', label: '2° Puesto' }
  if (posicion === 3) return { emoji: '🥉', color: 'text-amber-600', label: '3° Puesto' }
  return { emoji: '', color: 'text-gray-600', label: `${posicion}° Puesto` }
}

const obtenerColorCard = (posicion: number) => {
  if (posicion === 1) return 'border-yellow-400 bg-yellow-50'
  if (posicion === 2) return 'border-gray-300 bg-gray-50'
  if (posicion === 3) return 'border-amber-400 bg-amber-50'
  return 'border-gray-200 bg-white'
}

const clientesConPosicion = computed(() => {
  if (!reporte.value) return []
  return reporte.value.clientes.map((cliente, index) => ({
    ...cliente,
    posicion: index + 1
  }))
})

const totalGeneral = computed(() => {
  if (!reporte.value) return 0
  return reporte.value.clientes.reduce((sum, cliente) => sum + cliente.total_facturado, 0)
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
          <h1 class="text-3xl font-bold text-gray-900">Ranking de Clientes</h1>
          <p class="mt-1 text-gray-600">Clientes con mayor facturación en el período</p>
        </div>
      </div>
    </div>

    <!-- Filtros -->
    <BaseCard class="mb-6">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
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
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Límite
          </label>
          <select
            v-model="limite"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option
              v-for="opt in limitesDisponibles"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>
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
    <template v-else-if="reporte && reporte.clientes.length > 0">
      <!-- Período -->
      <div class="mb-6">
        <BaseCard :padding="false">
          <div class="p-4 bg-gray-50">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <p class="text-sm text-gray-600">
                <span class="font-medium">Período:</span>
                {{ formatearFecha(reporte.periodo.desde) }} - 
                {{ formatearFecha(reporte.periodo.hasta) }}
              </p>
              <p class="text-sm text-gray-600">
                <span class="font-medium">Total facturado:</span>
                <span class="text-lg font-bold text-primary-600 ml-2">
                  {{ formatearMoneda(totalGeneral) }}
                </span>
              </p>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Top 3 destacado (móvil y desktop) -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <BaseCard
          v-for="cliente in clientesConPosicion.slice(0, 3)"
          :key="cliente.cliente_id"
          :padding="false"
          :class="['border-2', obtenerColorCard(cliente.posicion)]"
        >
          <div class="p-6">
            <!-- Medalla y posición -->
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-3xl">{{ obtenerMedalla(cliente.posicion).emoji }}</span>
                <TrophyIcon :class="['h-6 w-6', obtenerMedalla(cliente.posicion).color]" />
              </div>
              <BaseBadge
                :variant="cliente.posicion === 1 ? 'warning' : cliente.posicion === 2 ? 'default' : 'secondary'"
              >
                {{ obtenerMedalla(cliente.posicion).label }}
              </BaseBadge>
            </div>

            <!-- Info del cliente -->
            <div class="mb-4">
              <h3 class="text-lg font-bold text-gray-900 mb-1 truncate">
                {{ cliente.razon_social }}
              </h3>
              <p class="text-sm text-gray-600 font-mono">
                {{ formatearCUIT(cliente.numero_documento) }}
              </p>
            </div>

            <!-- Estadísticas -->
            <div class="space-y-2">
              <div class="flex items-center justify-between p-2 bg-white rounded">
                <span class="text-sm text-gray-600">Total facturado</span>
                <span :class="['font-bold text-lg', obtenerMedalla(cliente.posicion).color]">
                  {{ formatearMoneda(cliente.total_facturado) }}
                </span>
              </div>
              <div class="flex items-center justify-between p-2 bg-white rounded">
                <span class="text-sm text-gray-600">Comprobantes</span>
                <span class="font-semibold text-gray-900">
                  {{ cliente.cantidad_comprobantes }}
                </span>
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Resto del ranking (si hay más de 3) -->
      <BaseCard v-if="clientesConPosicion.length > 3">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Resto del Ranking</h2>
        
        <div class="space-y-3">
          <div
            v-for="cliente in clientesConPosicion.slice(3)"
            :key="cliente.cliente_id"
            class="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <div class="flex items-center gap-4 flex-1 min-w-0">
              <!-- Posición -->
              <div class="flex-shrink-0 w-12 h-12 flex items-center justify-center bg-gray-100 rounded-full">
                <span class="text-lg font-bold text-gray-600">{{ cliente.posicion }}</span>
              </div>

              <!-- Info cliente -->
              <div class="flex-1 min-w-0">
                <h4 class="font-semibold text-gray-900 truncate">
                  {{ cliente.razon_social }}
                </h4>
                <p class="text-sm text-gray-600 font-mono">
                  {{ formatearCUIT(cliente.numero_documento) }}
                </p>
              </div>

              <!-- Estadísticas (visible en desktop) -->
              <div class="hidden md:flex items-center gap-6">
                <div class="text-right">
                  <p class="text-sm text-gray-600">Comprobantes</p>
                  <p class="font-semibold text-gray-900">
                    {{ cliente.cantidad_comprobantes }}
                  </p>
                </div>
                <div class="text-right">
                  <p class="text-sm text-gray-600">Total</p>
                  <p class="font-bold text-primary-600 text-lg">
                    {{ formatearMoneda(cliente.total_facturado) }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Estadísticas (visible en móvil) -->
            <div class="md:hidden flex flex-col items-end gap-1">
              <p class="font-bold text-primary-600">
                {{ formatearMoneda(cliente.total_facturado) }}
              </p>
              <p class="text-sm text-gray-600">
                {{ cliente.cantidad_comprobantes }} docs
              </p>
            </div>
          </div>
        </div>
      </BaseCard>
    </template>

    <!-- Sin resultados -->
    <BaseEmpty v-else-if="reporte && reporte.clientes.length === 0">
      <UserIcon class="h-12 w-12 mx-auto mb-4 text-gray-400" />
      <p class="text-gray-600">
        No hay clientes con facturación en el período seleccionado
      </p>
    </BaseEmpty>

    <!-- Estado inicial -->
    <BaseEmpty v-else>
      <DocumentChartBarIcon class="h-12 w-12 mx-auto mb-4 text-gray-400" />
      <p class="text-gray-600">
        Seleccione un rango de fechas y haga clic en "Generar Reporte" para ver los resultados
      </p>
    </BaseEmpty>
  </div>
</template>
