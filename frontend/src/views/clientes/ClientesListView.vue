<script setup lang="ts">
import { computed, ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useClientesStore } from "@/stores/clientes";
import { useEmpresaStore } from "@/stores/empresa";
import { useNotification } from "@/composables/useNotification";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseTable from "@/components/ui/BaseTable.vue";
import BaseBadge from "@/components/ui/BaseBadge.vue";
import Pagination from "@/components/common/Pagination.vue";
import ConfirmDialog from "@/components/common/ConfirmDialog.vue";
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  EyeIcon,
  MagnifyingGlassIcon,
} from "@heroicons/vue/24/outline";

const router = useRouter();
const clientesStore = useClientesStore();
const empresaStore = useEmpresaStore();
const { showSuccess, showError } = useNotification();

const search = ref("");
const currentPage = ref(1);
const showDeleteDialog = ref(false);
const clienteToDelete = ref<number | null>(null);
const empresaId = computed(() => empresaStore.empresaActivaId || 0);

const columns = [
  { key: "razon_social", label: "Razón Social", sortable: true },
  { key: "numero_documento", label: "Documento", sortable: false },
  { key: "condicion_iva", label: "IVA", sortable: false },
  { key: "email", label: "Email", sortable: false },
  { key: "activo", label: "Estado", sortable: false },
];

onMounted(async () => {
  if (!empresaStore.empresaActivaId) {
    await empresaStore.inicializarEmpresaActiva();
  } else if (!empresaStore.empresaActiva) {
    await empresaStore.cargarEmpresa();
  }

  await loadClientes();
});

watch([search, currentPage], () => {
  loadClientes();
});

watch(
  () => empresaStore.empresaActivaId,
  async (nuevoEmpresaId, anteriorEmpresaId) => {
    if (!nuevoEmpresaId || nuevoEmpresaId === anteriorEmpresaId) return;

    if (currentPage.value !== 1) {
      currentPage.value = 1;
      return;
    }

    await loadClientes();
  },
);

const loadClientes = async () => {
  if (!empresaId.value) return;

  try {
    await clientesStore.fetchClientes({
      page: currentPage.value,
      per_page: 30,
      search: search.value || undefined,
    });
  } catch (error: any) {
    showError("Error", "No se pudieron cargar los clientes");
  }
};

const handleNew = () => {
  router.push("/clientes/nuevo");
};

const handleView = (cliente: any) => {
  router.push(`/clientes/${cliente.id}`);
};

const handleEdit = (cliente: any) => {
  router.push(`/clientes/${cliente.id}/editar`);
};

const handleDeleteClick = (cliente: any) => {
  clienteToDelete.value = cliente.id;
  showDeleteDialog.value = true;
};

const confirmDelete = async () => {
  if (!clienteToDelete.value) return;

  try {
    await clientesStore.deleteCliente(clienteToDelete.value);
    showSuccess("Cliente eliminado", "El cliente se eliminó correctamente");
    showDeleteDialog.value = false;
    clienteToDelete.value = null;
  } catch (error: any) {
    showError("Error", "No se pudo eliminar el cliente");
  }
};
</script>

<template>
  <div>
    <div class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1
          class="text-3xl font-bold text-brand-ink"
          data-testid="page-title"
        >
          Clientes
        </h1>
        <p class="mt-2 text-brand-slate">
          Gestión de clientes
        </p>
      </div>
      <BaseButton
        class="w-full sm:w-auto"
        data-testid="clientes-nuevo"
        @click="handleNew"
      >
        <PlusIcon class="h-5 w-5 mr-2" />
        Nuevo Cliente
      </BaseButton>
    </div>

    <BaseCard>
      <!-- Search -->
      <div class="mb-6">
        <div class="relative">
          <MagnifyingGlassIcon
            class="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 transform text-brand-slate"
          />
          <input
            v-model="search"
            type="text"
            placeholder="Buscar por nombre o documento..."
            class="w-full rounded-control border border-border-subtle bg-surface-card py-2 pl-10 pr-4 text-brand-ink placeholder:text-brand-slate transition-colors focus:outline-none focus:ring-2 focus:ring-brand-flow"
          >
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
            <div class="font-medium text-brand-ink">
              {{ row.razon_social }}
            </div>
            <div class="text-sm text-brand-slate">
              {{ row.tipo_documento }}: {{ row.numero_documento }}
            </div>
          </div>
        </template>

        <template #cell-condicion_iva="{ value }">
          <BaseBadge :variant="value === 'RI' ? 'primary' : 'default'">
            {{ value }}
          </BaseBadge>
        </template>

        <template #cell-email="{ value }">
          <span class="text-brand-slate">{{ value || "-" }}</span>
        </template>

        <template #cell-activo="{ value }">
          <BaseBadge :variant="value ? 'success' : 'default'">
            {{ value ? "Activo" : "Inactivo" }}
          </BaseBadge>
        </template>

        <template #actions="{ row }">
          <div class="flex gap-2">
            <button
              class="rounded-control p-1 text-brand-flow transition-colors hover:bg-brand-mint hover:text-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
              title="Ver"
              @click="handleView(row)"
            >
              <EyeIcon class="h-5 w-5" />
            </button>
            <button
              class="rounded-control p-1 text-status-success transition-colors hover:bg-brand-mint focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
              title="Editar"
              @click="handleEdit(row)"
            >
              <PencilIcon class="h-5 w-5" />
            </button>
            <button
              class="rounded-control p-1 text-status-danger transition-colors hover:bg-[rgba(180,35,24,0.10)] focus:outline-none focus:ring-2 focus:ring-status-danger focus:ring-offset-2"
              title="Eliminar"
              @click="handleDeleteClick(row)"
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
