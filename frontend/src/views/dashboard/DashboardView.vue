<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useClientesStore } from '@/stores/clientes'
import certificadosService from '@/services/certificados.service'
import type { CertificadoAlerta } from '@/types/certificado'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseAlert from '@/components/ui/BaseAlert.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { UsersIcon, DocumentTextIcon, CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/vue/24/outline'

const authStore = useAuthStore()
const clientesStore = useClientesStore()
const router = useRouter()
const loading = ref(true)
const alertasCertificados = ref<CertificadoAlerta[]>([])

onMounted(async () => {
  try {
    await Promise.all([
      clientesStore.fetchClientes({ per_page: 100 }),
      cargarAlertasCertificados()
    ])
  } catch (error) {
    console.error('Error loading data:', error)
  } finally {
    loading.value = false
  }
})

const cargarAlertasCertificados = async () => {
  try {
    alertasCertificados.value = await certificadosService.obtenerAlertasVencimiento()
  } catch (err) {
    console.error('Error loading certificate alerts:', err)
  }
}

const formatearFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

const irACertificados = () => {
  router.push({ name: 'certificados' })
}

const stats = computed(() => [
  {
    name: 'Total Clientes',
    value: clientesStore.pagination.total || 0,
    icon: UsersIcon,
    color: 'text-blue-600',
    bg: 'bg-blue-100'
  },
  {
    name: 'Comprobantes del Mes',
    value: '0',
    icon: DocumentTextIcon,
    color: 'text-green-600',
    bg: 'bg-green-100'
  },
  {
    name: 'Último Comprobante',
    value: '-',
    icon: CheckCircleIcon,
    color: 'text-purple-600',
    bg: 'bg-purple-100'
  },
  {
    name: 'Estado Certificado',
    value: 'Pendiente',
    icon: ExclamationTriangleIcon,
    color: 'text-yellow-600',
    bg: 'bg-yellow-100'
  }
])
</script>

<template>
  <div>
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900">
        ¡Bienvenido, {{ authStore.user?.nombre }}!
      </h1>
      <p class="mt-2 text-gray-600">
        Panel de control de FactuFlow
      </p>
    </div>

    <BaseSpinner v-if="loading" />

    <div v-else>
      <!-- Alertas de certificados -->
      <BaseAlert
        v-if="alertasCertificados.length > 0"
        type="warning"
        class="mb-6"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <p class="font-semibold mb-2">
              ⚠️ Certificado(s) próximo(s) a vencer
            </p>
            <div
              v-for="alerta in alertasCertificados.slice(0, 2)"
              :key="alerta.id"
              class="text-sm mb-1"
            >
              <span class="font-medium">{{ alerta.nombre }}</span>
              <span v-if="alerta.dias_restantes > 0">
                vence en {{ alerta.dias_restantes }} día(s) ({{ formatearFecha(alerta.fecha_vencimiento) }})
              </span>
              <span v-else class="text-red-700 font-semibold">
                ¡YA VENCIÓ! ({{ formatearFecha(alerta.fecha_vencimiento) }})
              </span>
            </div>
            <p v-if="alertasCertificados.length > 2" class="text-sm mt-1">
              y {{ alertasCertificados.length - 2 }} más...
            </p>
            <p class="text-sm mt-2">
              Te recomendamos renovarlos pronto para evitar interrupciones en la facturación.
            </p>
          </div>
          <BaseButton
            @click="irACertificados"
            variant="secondary"
            size="sm"
            class="ml-4 flex-shrink-0"
          >
            Ver certificados
          </BaseButton>
        </div>
      </BaseAlert>

      <!-- Stats Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <BaseCard v-for="stat in stats" :key="stat.name" :padding="false">
          <div class="p-6">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-gray-600">{{ stat.name }}</p>
                <p class="mt-2 text-3xl font-bold text-gray-900">{{ stat.value }}</p>
              </div>
              <div :class="['p-3 rounded-lg', stat.bg]">
                <component :is="stat.icon" :class="['h-6 w-6', stat.color]" />
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Quick Actions -->
      <BaseCard title="Accesos Rápidos">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <router-link
            to="/clientes/nuevo"
            class="p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors text-center"
          >
            <UsersIcon class="h-8 w-8 mx-auto mb-2 text-gray-400" />
            <h3 class="font-medium text-gray-900">Nuevo Cliente</h3>
            <p class="text-sm text-gray-500 mt-1">Agregar un cliente</p>
          </router-link>

          <router-link
            to="/comprobantes"
            class="p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors text-center"
          >
            <DocumentTextIcon class="h-8 w-8 mx-auto mb-2 text-gray-400" />
            <h3 class="font-medium text-gray-900">Emitir Factura</h3>
            <p class="text-sm text-gray-500 mt-1">Crear comprobante</p>
          </router-link>

          <router-link
            to="/empresa"
            class="p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors text-center"
          >
            <CheckCircleIcon class="h-8 w-8 mx-auto mb-2 text-gray-400" />
            <h3 class="font-medium text-gray-900">Configurar</h3>
            <p class="text-sm text-gray-500 mt-1">Mi empresa</p>
          </router-link>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
