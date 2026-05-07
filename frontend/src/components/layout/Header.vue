<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import BaseSelect from "@/components/ui/BaseSelect.vue";
import { useAuth } from "@/composables/useAuth";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import {
  ArrowRightOnRectangleIcon,
  BuildingOffice2Icon,
  UserCircleIcon,
} from "@heroicons/vue/24/outline";

const authStore = useAuthStore();
const empresaStore = useEmpresaStore();
const { logout } = useAuth();

const showDropdown = ref(false);
const loadingEmpresas = ref(false);
const dropdownRef = ref<HTMLElement | null>(null);

const empresasOptions = computed(() =>
  empresaStore.empresas.map((empresa) => ({
    value: empresa.id,
    label: `${empresa.razon_social} (${empresa.cuit})`,
  })),
);

const empresaActivaLabel = computed(() => {
  if (!empresaStore.empresaActiva) {
    return "Selecciona un emisor para empezar a trabajar.";
  }

  return `${empresaStore.empresaActiva.razon_social} | CUIT ${empresaStore.empresaActiva.cuit}`;
});

const handleDocumentClick = (event: MouseEvent) => {
  if (!dropdownRef.value) return;

  const target = event.target as Node | null;
  if (target && !dropdownRef.value.contains(target)) {
    showDropdown.value = false;
  }
};

onMounted(async () => {
  document.addEventListener("click", handleDocumentClick);

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
    class="flex min-h-24 items-center justify-between gap-4 border-b border-gray-200 bg-white px-6 py-3"
  >
    <div class="flex-1 max-w-2xl">
      <div v-if="authStore.user?.es_admin" class="max-w-xl">
        <BaseSelect
          :model-value="empresaStore.empresaActivaId || ''"
          :options="empresasOptions"
          label="Emisor activo"
          placeholder="Selecciona el emisor con el que vas a trabajar"
          :disabled="loadingEmpresas || empresasOptions.length === 0"
          @update:model-value="handleEmpresaChange"
        />
        <p class="mt-1 text-xs text-gray-500">
          Todo lo que hagas en comprobantes, emision masiva, certificados y
          reportes se aplicara a este emisor.
        </p>
      </div>

      <div
        v-else
        class="flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600"
      >
        <BuildingOffice2Icon
          class="mt-0.5 h-5 w-5 flex-shrink-0 text-gray-400"
        />
        <div>
          <p class="font-medium text-gray-900">Emisor activo</p>
          <p>{{ empresaActivaLabel }}</p>
        </div>
      </div>
    </div>

    <div ref="dropdownRef" class="relative flex-shrink-0">
      <button
        class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
        @click="showDropdown = !showDropdown"
      >
        <UserCircleIcon class="h-6 w-6" />
        <span>{{ authStore.user?.nombre || "Usuario" }}</span>
      </button>

      <div
        v-if="showDropdown"
        class="absolute right-0 mt-2 w-56 rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
      >
        <div class="border-b border-gray-200 px-4 py-2">
          <p class="text-sm font-medium text-gray-900">
            {{ authStore.user?.nombre }}
          </p>
          <p class="truncate text-xs text-gray-500">
            {{ authStore.user?.email }}
          </p>
        </div>

        <button
          class="flex w-full items-center gap-2 px-4 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
          @click="handleLogout"
        >
          <ArrowRightOnRectangleIcon class="h-5 w-5" />
          Cerrar sesion
        </button>
      </div>
    </div>
  </header>
</template>
