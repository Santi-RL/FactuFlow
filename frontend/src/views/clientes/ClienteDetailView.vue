<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useClientesStore } from '@/stores/clientes'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { PencilIcon, ArrowLeftIcon } from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const clientesStore = useClientesStore()

const loading = ref(true)

onMounted(async () => {
  const id = parseInt(route.params.id as string)
  try {
    await clientesStore.fetchCliente(id)
  } catch (error) {
    router.push('/clientes')
  } finally {
    loading.value = false
  }
})

const handleEdit = () => {
  router.push(`/clientes/${route.params.id}/editar`)
}

const handleBack = () => {
  router.push('/clientes')
}
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">
          Detalle del Cliente
        </h1>
      </div>
      <div class="flex gap-3">
        <BaseButton
          variant="secondary"
          @click="handleBack"
        >
          <ArrowLeftIcon class="h-5 w-5 mr-2" />
          Volver
        </BaseButton>
        <BaseButton @click="handleEdit">
          <PencilIcon class="h-5 w-5 mr-2" />
          Editar
        </BaseButton>
      </div>
    </div>

    <BaseSpinner v-if="loading" />

    <BaseCard v-else-if="clientesStore.clienteActual">
      <div class="space-y-6">
        <div>
          <h3 class="text-lg font-semibold text-gray-900 mb-4">
            Información Básica
          </h3>
          <dl class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Razón Social
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.razon_social }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Documento
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.tipo_documento }}: {{ clientesStore.clienteActual.numero_documento }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Condición IVA
              </dt>
              <dd class="mt-1">
                <BaseBadge>{{ clientesStore.clienteActual.condicion_iva }}</BaseBadge>
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Estado
              </dt>
              <dd class="mt-1">
                <BaseBadge :variant="clientesStore.clienteActual.activo ? 'success' : 'default'">
                  {{ clientesStore.clienteActual.activo ? 'Activo' : 'Inactivo' }}
                </BaseBadge>
              </dd>
            </div>
          </dl>
        </div>

        <div
          v-if="clientesStore.clienteActual.domicilio"
          class="border-t pt-6"
        >
          <h3 class="text-lg font-semibold text-gray-900 mb-4">
            Domicilio
          </h3>
          <dl class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Dirección
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.domicilio || '-' }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Localidad
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.localidad || '-' }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Provincia
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.provincia || '-' }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Código Postal
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.codigo_postal || '-' }}
              </dd>
            </div>
          </dl>
        </div>

        <div class="border-t pt-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-4">
            Contacto
          </h3>
          <dl class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Email
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.email || '-' }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-gray-500">
                Teléfono
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.telefono || '-' }}
              </dd>
            </div>
            <div
              v-if="clientesStore.clienteActual.notas"
              class="md:col-span-2"
            >
              <dt class="text-sm font-medium text-gray-500">
                Notas
              </dt>
              <dd class="mt-1 text-sm text-gray-900">
                {{ clientesStore.clienteActual.notas }}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </BaseCard>
  </div>
</template>
