<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePuntosVentaStore } from '@/stores/puntos_venta'
import { useNotification } from '@/composables/useNotification'
import certificadosService from '@/services/certificados.service'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseTable from '@/components/ui/BaseTable.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseAlert from '@/components/ui/BaseAlert.vue'
import { ArrowPathIcon, ArrowDownTrayIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const puntosVentaStore = usePuntosVentaStore()
const { showSuccess, showError, showWarning } = useNotification()

const tieneCertificadoActivo = ref(false)
const cargandoCertificados = ref(false)

const columns = [
  { key: 'numero', label: 'Numero', sortable: true },
  { key: 'nombre', label: 'Nombre', sortable: false },
  { key: 'activo', label: 'Estado', sortable: false }
]

const puntosOrdenados = computed(() => {
  return [...puntosVentaStore.puntosVenta].sort((a, b) => a.numero - b.numero)
})

const cargarCertificados = async () => {
  cargandoCertificados.value = true
  try {
    const certs = await certificadosService.listar()
    tieneCertificadoActivo.value = certs.some(cert => cert.activo)
  } catch (err: any) {
    tieneCertificadoActivo.value = false
  } finally {
    cargandoCertificados.value = false
  }
}

const cargarDatos = async () => {
  try {
    await Promise.all([puntosVentaStore.fetchPuntosVenta(), cargarCertificados()])
  } catch (err: any) {
    showError('Error', 'No se pudieron cargar los puntos de venta')
  }
}

const irACertificados = () => {
  router.push('/certificados')
}

const sincronizar = async () => {
  if (!tieneCertificadoActivo.value) {
    showWarning('Certificado requerido', 'Carga un certificado activo para poder sincronizar')
    return
  }

  try {
    const resultado = await puntosVentaStore.syncFromArca()
    showSuccess(
      'Sincronizacion completa',
      `Total en ARCA: ${resultado.total_arca}. Nuevos: ${resultado.nuevos}. Existentes: ${resultado.existentes}.`
    )
  } catch (err: any) {
    const mensaje = err.response?.data?.detail || 'No se pudo sincronizar con ARCA'
    showError('Error', mensaje)
  }
}

onMounted(() => {
  cargarDatos()
})
</script>

<template>
  <div>
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">
          Puntos de venta
        </h1>
        <p class="mt-2 text-gray-600">
          Administra y sincroniza los puntos de venta de la empresa
        </p>
      </div>
      <div class="flex gap-2">
        <BaseButton
          variant="secondary"
          :loading="puntosVentaStore.loading"
          @click="cargarDatos"
        >
          <ArrowPathIcon class="h-5 w-5 mr-2" />
          Actualizar
        </BaseButton>
        <BaseButton
          :disabled="!tieneCertificadoActivo || puntosVentaStore.syncing || cargandoCertificados"
          :loading="puntosVentaStore.syncing"
          @click="sincronizar"
        >
          <ArrowDownTrayIcon class="h-5 w-5 mr-2" />
          Sincronizar con ARCA
        </BaseButton>
      </div>
    </div>

    <BaseAlert
      v-if="!tieneCertificadoActivo"
      type="warning"
      title="Certificado requerido"
      :dismissible="false"
      class="mb-6"
    >
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span>
          No se pueden sincronizar los puntos de venta si no hay un certificado activo cargado.
        </span>
        <BaseButton
          variant="secondary"
          size="sm"
          @click="irACertificados"
        >
          Ir a certificados
        </BaseButton>
      </div>
    </BaseAlert>

    <BaseCard>
      <BaseTable
        :columns="columns"
        :data="puntosOrdenados"
        :loading="puntosVentaStore.loading"
        empty-text="No hay puntos de venta registrados"
      >
        <template #cell-numero="{ value }">
          <span class="font-medium text-gray-900">
            {{ String(value).padStart(4, '0') }}
          </span>
        </template>

        <template #cell-nombre="{ value }">
          <span class="text-gray-600">{{ value || '-' }}</span>
        </template>

        <template #cell-activo="{ value }">
          <BaseBadge :variant="value ? 'success' : 'default'">
            {{ value ? 'Activo' : 'Inactivo' }}
          </BaseBadge>
        </template>
      </BaseTable>
    </BaseCard>
  </div>
</template>
