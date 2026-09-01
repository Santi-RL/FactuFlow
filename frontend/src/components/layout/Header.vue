<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import BaseSelect from "@/components/ui/BaseSelect.vue";
import { useAuth } from "@/composables/useAuth";
import { useNotification } from "@/composables/useNotification";
import { EMPRESA_ACCESO_REVALIDAR_EVENT } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import {
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
} from "@heroicons/vue/24/outline";

const authStore = useAuthStore();
const empresaStore = useEmpresaStore();
const { logout } = useAuth();
const { showWarning } = useNotification();

const showDropdown = ref(false);
const loadingEmpresas = ref(false);
const dropdownRef = ref<HTMLElement | null>(null);
let revalidandoAccesos = false;

const empresasOptions = computed(() =>
  empresaStore.empresas.map((empresa) => ({
    value: empresa.id,
    label: `${empresa.razon_social} (${empresa.cuit})`,
  })),
);

const handleDocumentClick = (event: MouseEvent) => {
  if (!dropdownRef.value) return;

  const target = event.target as Node | null;
  if (target && !dropdownRef.value.contains(target)) {
    showDropdown.value = false;
  }
};

const handleRevalidarAccesos = async () => {
  if (revalidandoAccesos || !authStore.isAuthenticated) return;
  revalidandoAccesos = true;
  try {
    const sesionVigente = await authStore.checkAuth();
    if (!sesionVigente) return;
    const accesoRevocado = await empresaStore.revalidarAccesos();
    if (accesoRevocado) {
      showWarning(
        "Acceso al emisor revocado",
        "La selección y los datos abiertos de ese emisor se descartaron. Elegí otro emisor habilitado para continuar.",
      );
    }
  } finally {
    revalidandoAccesos = false;
  }
};

onMounted(async () => {
  document.addEventListener("click", handleDocumentClick);
  window.addEventListener(
    EMPRESA_ACCESO_REVALIDAR_EVENT,
    handleRevalidarAccesos,
  );

  if (!authStore.isAuthenticated) return;

  loadingEmpresas.value = true;
  try {
    await empresaStore.inicializarEmpresaActiva();
  } finally {
    loadingEmpresas.value = false;
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
  window.removeEventListener(
    EMPRESA_ACCESO_REVALIDAR_EVENT,
    handleRevalidarAccesos,
  );
});

const handleLogout = async () => {
  await logout();
};

const handleEmpresaChange = async (value: string | number) => {
  const empresaId = Number(value);
  if (!empresaId || empresaStore.empresaActivaId === empresaId) return;

  loadingEmpresas.value = true;
  try {
    await empresaStore.setEmpresaActiva(empresaId);
  } finally {
    loadingEmpresas.value = false;
  }
};
</script>

<template>
  <header
    class="flex min-h-24 flex-col items-stretch gap-3 border-b border-border-subtle bg-surface-card px-6 pb-3 pt-16 shadow-panel lg:flex-row lg:items-center lg:justify-between lg:gap-4 lg:py-3"
  >
    <div class="w-full flex-1 lg:max-w-2xl">
      <div class="max-w-xl">
        <BaseSelect
          :model-value="empresaStore.empresaActivaId || ''"
          :options="empresasOptions"
          label="Emisor activo"
          placeholder="Selecciona el emisor con el que vas a trabajar"
          :disabled="loadingEmpresas || empresasOptions.length === 0"
          @update:model-value="handleEmpresaChange"
        />
        <p
          v-if="empresaStore.avisoAcceso"
          class="mt-1 text-xs font-medium text-status-danger"
        >
          {{ empresaStore.avisoAcceso }}
        </p>
        <p
          v-else-if="empresasOptions.length > 0 && empresaStore.empresaActivaId"
          class="mt-1 text-xs text-brand-slate"
        >
          Todo lo que hagas en comprobantes, emisión masiva, certificados y
          reportes se aplicará a este emisor.
        </p>
        <p
          v-else-if="empresasOptions.length > 1"
          class="mt-1 text-xs font-medium text-status-warning"
        >
          Elegí explícitamente un emisor para comenzar. No se cambiará la
          selección de forma automática.
        </p>
        <p
          v-else-if="authStore.user?.puede_crear_editar_emisores"
          class="mt-1 text-xs text-brand-slate"
        >
          No tenés emisores habilitados. Podés crear uno desde Emisor.
        </p>
        <p v-else class="mt-1 text-xs text-brand-slate">
          No tenés emisores habilitados. Pedile a un administrador que te asigne
          acceso.
        </p>
      </div>
    </div>

    <div ref="dropdownRef" class="relative flex-shrink-0 self-end lg:self-auto">
      <button
        class="flex items-center gap-2 rounded-control px-3 py-2 text-sm font-medium text-brand-slate transition-colors hover:bg-brand-mint hover:text-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
        @click="showDropdown = !showDropdown"
      >
        <UserCircleIcon class="h-6 w-6" />
        <span>{{ authStore.user?.nombre || "Usuario" }}</span>
      </button>

      <div
        v-if="showDropdown"
        class="absolute right-0 mt-2 w-56 rounded-panel border border-border-subtle bg-surface-card py-1 shadow-overlay"
      >
        <div class="border-b border-border-subtle px-4 py-2">
          <p class="text-sm font-medium text-brand-ink">
            {{ authStore.user?.nombre }}
          </p>
          <p class="truncate text-xs text-brand-slate">
            {{ authStore.user?.email }}
          </p>
        </div>

        <button
          class="flex w-full items-center gap-2 px-4 py-2 text-sm text-brand-slate transition-colors hover:bg-brand-mint hover:text-brand-teal"
          @click="handleLogout"
        >
          <ArrowRightOnRectangleIcon class="h-5 w-5" />
          Cerrar sesión
        </button>
      </div>
    </div>
  </header>
</template>
