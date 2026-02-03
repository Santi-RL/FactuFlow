<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useClientesStore } from '@/stores/clientes'
import { useNotification } from '@/composables/useNotification'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseTable from '@/components/ui/BaseTable.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseEmpty from '@/components/ui/BaseEmpty.vue'
import Pagination from '@/components/common/Pagination.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { PlusIcon, PencilIcon, TrashIcon, EyeIcon, MagnifyingGlassIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const clientesStore = useClientesStore()
const { showSuccess, showError } = useNotification()

const search = ref('')
const currentPage = ref(1)
const showDeleteDialog = ref(false)
const clienteToDelete = ref<number | null>(null)

const columns = [
  { key: 'razon_social', label: 'Razón Social', sortable: true },
  { key: 'numero_documento', label: 'Documento', sortable: false },
  { key: 'condicion_iva', label: 'IVA', sortable: false },
  { key: 'email', label: 'Email', sortable: false },
  { key: 'activo', label: 'Estado', sortable: false }
]

onMounted(() => {
  loadClientes()
})

watch([search, currentPage], () => {
  loadClientes()
})

const loadClientes = async () => {
  try {
    await clientesStore.fetchClientes({
      page: currentPage.value,
      per_page: 30,
      search: search.value || undefined
    })
  } catch (error: any) {
    showError('Error', 'No se pudieron cargar los clientes')
  }
}

const handleNew = () => {
  router.push('/clientes/nuevo')
}

const handleView = (cliente: any) => {
  router.push(`/clientes/${cliente.id}`)
}

const handleEdit = (cliente: any) => {
  router.push(`/clientes/${cliente.id}/editar`)
}

const handleDeleteClick = (cliente: any) => {
  clienteToDelete.value = cliente.id
  showDeleteDialog.value = true
}

const confirmDelete = async () => {
  if (!clienteToDelete.value) return

  try {
    await clientesStore.deleteCliente(clienteToDelete.value)
    showSuccess('Cliente eliminado', 'El cliente se eliminó correctamente')
    showDeleteDialog.value = false
    clienteToDelete.value = null
  } catch (error: any) {
    showError('Error', 'No se pudo eliminar el cliente')
  }
}
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-3xl font-bold text-gray-900">Clientes</h1>
        <p class="mt-2 text-gray-600">Gestión de clientes</p>
      </div>
      <BaseButton @click="handleNew">
        <PlusIcon class="h-5 w-5 mr-2" />
        Nuevo Cliente
      </BaseButton>
    </div>

    <BaseCard>
      <!-- Search -->
      <div class="mb-6">
        <div class="relative">
          <MagnifyingGlassIcon class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            v-model="search"
            type="text"
            placeholder="Buscar por nombre o documento..."
            class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
      </div>

      <!-- Table -->
      <BaseTable
        :columns="columns"
        :data="clientesStore.clientes"
        :loading="clientesStore.loading"
        empty-text="No hay clientes registrados"
      >
        <template #cell-razon_social="{ row }">
          <div>
            <div class="font-medium text-gray-900">{{ row.razon_social }}</div>
            <div class="text-sm text-gray-500">{{ row.tipo_documento }}: {{ row.numero_documento }}</div>
          </div>
        </template>

        <template #cell-condicion_iva="{ value }">
          <BaseBadge :variant="value === 'RI' ? 'primary' : 'default'">
            {{ value }}
          </BaseBadge>
        </template>

        <template #cell-email="{ value }">
          <span class="text-gray-600">{{ value || '-' }}</span>
        </template>

        <template #cell-activo="{ value }">
          <BaseBadge :variant="value ? 'success' : 'default'">
            {{ value ? 'Activo' : 'Inactivo' }}
          </BaseBadge>
        </template>

        <template #actions="{ row }">
          <div class="flex gap-2">
            <button
              @click="handleView(row)"
              class="text-blue-600 hover:text-blue-800"
              title="Ver"
            >
              <EyeIcon class="h-5 w-5" />
            </button>
            <button
              @click="handleEdit(row)"
              class="text-green-600 hover:text-green-800"
              title="Editar"
            >
              <PencilIcon class="h-5 w-5" />
            </button>
            <button
              @click="handleDeleteClick(row)"
              class="text-red-600 hover:text-red-800"
              title="Eliminar"
            >
              <TrashIcon class="h-5 w-5" />
            </button>
          </div>
        </template>
      </BaseTable>

      <!-- Pagination -->
      <Pagination
        v-if="clientesStore.pagination.pages > 1"
        v-model:current-page="currentPage"
        :total-pages="clientesStore.pagination.pages"
        :per-page="clientesStore.pagination.per_page"
        :total="clientesStore.pagination.total"
      />
    </BaseCard>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :show="showDeleteDialog"
      title="¿Eliminar cliente?"
      message="Esta acción no se puede deshacer. ¿Está seguro que desea eliminar este cliente?"
      confirm-text="Eliminar"
      cancel-text="Cancelar"
      variant="danger"
      @confirm="confirmDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
