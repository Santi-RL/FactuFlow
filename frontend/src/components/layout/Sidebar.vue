<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, watch } from "vue";
import { useRoute } from "vue-router";
import { useUIStore } from "@/stores/ui";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import {
  HomeIcon,
  UsersIcon,
  DocumentTextIcon,
  DocumentDuplicateIcon,
  BuildingOfficeIcon,
  KeyIcon,
  Bars3Icon,
  XMarkIcon,
  ChartBarIcon,
  MapPinIcon,
  UserGroupIcon,
  ServerStackIcon,
} from "@heroicons/vue/24/outline";
import wordmarkUrl from "@/assets/brand/factuflow-wordmark.svg";
import certificadosService from "@/services/certificados.service";

const route = useRoute();
const uiStore = useUIStore();
const authStore = useAuthStore();
const empresaStore = useEmpresaStore();

const certificadosPorVencer = ref(0);
let intervalId: number | null = null;
let cargarAlertasRequestId = 0;

const menuItems = computed(() =>
  [
    { name: "Dashboard", icon: HomeIcon, path: "/", testId: "nav-dashboard" },
    {
      name: "Clientes",
      icon: UsersIcon,
      path: "/clientes",
      testId: "nav-clientes",
    },
    {
      name: "Comprobantes",
      icon: DocumentTextIcon,
      path: "/comprobantes",
      testId: "nav-comprobantes",
    },
    {
      name: "Emisión masiva",
      icon: DocumentDuplicateIcon,
      path: "/comprobantes/lotes",
      testId: "nav-lotes-comprobantes",
    },
    {
      name: "Reportes",
      icon: ChartBarIcon,
      path: "/reportes",
      testId: "nav-reportes",
    },
    {
      name: "Certificados",
      icon: KeyIcon,
      path: "/certificados",
      testId: "nav-certificados",
      badge:
        certificadosPorVencer.value > 0 ? certificadosPorVencer.value : null,
    },
    {
      name: "Puntos de venta",
      icon: MapPinIcon,
      path: "/puntos-venta",
      testId: "nav-puntos-venta",
    },
    {
      name: "Emisores",
      icon: BuildingOfficeIcon,
      path: "/empresa",
      testId: "nav-empresa",
    },
    {
      name: "Usuarios",
      icon: UserGroupIcon,
      path: "/usuarios",
      testId: "nav-usuarios",
      requiresAdmin: true,
    },
    {
      name: "Sistema",
      icon: ServerStackIcon,
      path: "/sistema",
      testId: "nav-sistema",
      requiresAdmin: true,
    },
  ].filter((item) => !item.requiresAdmin || authStore.user?.es_admin),
);

const isActive = (path: string) => {
  if (path === "/") {
    return route.path === "/";
  }
  return route.path.startsWith(path);
};

const cargarAlertasVencimiento = async () => {
  const empresaIdSolicitada = empresaStore.empresaActivaId;
  if (!empresaIdSolicitada) {
    certificadosPorVencer.value = 0;
    return;
  }

  const requestId = ++cargarAlertasRequestId;
  try {
    const alertas = await certificadosService.obtenerAlertasVencimiento();
    if (
      requestId !== cargarAlertasRequestId ||
      empresaStore.empresaActivaId !== empresaIdSolicitada
    ) {
      return;
    }

    certificadosPorVencer.value = alertas.length;
  } catch (err) {
    if (
      requestId !== cargarAlertasRequestId ||
      empresaStore.empresaActivaId !== empresaIdSolicitada
    ) {
      return;
    }

    certificadosPorVencer.value = 0;
    // Silently fail, it's not critical
    console.error("Error loading certificate alerts:", err);
  }
};

watch(
  () => empresaStore.empresaActivaId,
  async (empresaId, anteriorId) => {
    if (!empresaId) {
      certificadosPorVencer.value = 0;
      return;
    }

    if (empresaId === anteriorId) return;
    await cargarAlertasVencimiento();
  },
  { immediate: true },
);

onMounted(() => {
  // Reload alerts every 5 minutes
  intervalId = window.setInterval(cargarAlertasVencimiento, 5 * 60 * 1000);
});

onBeforeUnmount(() => {
  if (intervalId !== null) {
    clearInterval(intervalId);
  }
});
</script>

<template>
  <div>
    <!-- Mobile menu button -->
    <div class="lg:hidden fixed top-4 left-4 z-50">
      <button
        data-testid="sidebar-toggle"
        class="rounded-control border border-border-subtle bg-surface-card p-2 text-brand-ink shadow-panel"
        @click="uiStore.toggleSidebar"
      >
        <Bars3Icon
          v-if="!uiStore.sidebarOpen"
          class="h-6 w-6"
        />
        <XMarkIcon
          v-else
          class="h-6 w-6"
        />
      </button>
    </div>

    <!-- Overlay for mobile -->
    <div
      v-if="uiStore.sidebarOpen"
      class="lg:hidden fixed inset-0 z-40 bg-gray-900 bg-opacity-50"
      @click="uiStore.toggleSidebar"
    />

    <!-- Sidebar -->
    <aside
      :class="[
        'fixed lg:static inset-y-0 left-0 z-40 w-64 transform border-r border-border-subtle bg-surface-card shadow-panel transition-transform duration-200 ease-in-out',
        uiStore.sidebarOpen
          ? 'translate-x-0'
          : '-translate-x-full lg:translate-x-0',
      ]"
    >
      <div class="flex flex-col h-full">
        <!-- Logo -->
        <div
          class="flex h-16 items-center border-b border-border-subtle pl-16 pr-5 lg:px-5"
        >
          <router-link
            to="/"
            class="flex items-center"
            data-testid="sidebar-logo"
            @click="uiStore.sidebarOpen = false"
          >
            <img
              :src="wordmarkUrl"
              alt="FactuFlow"
              class="h-8 w-auto"
            >
          </router-link>
        </div>

        <!-- Navigation -->
        <nav class="flex-1 space-y-1.5 overflow-y-auto px-3 py-5">
          <router-link
            v-for="item in menuItems"
            :key="item.path"
            :to="item.path"
            :data-testid="item.testId"
            :class="[
              'flex items-center rounded-control px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2',
              isActive(item.path)
                ? 'bg-brand-mint text-brand-teal'
                : 'text-brand-slate hover:bg-gray-50 hover:text-brand-ink',
            ]"
            @click="uiStore.sidebarOpen = false"
          >
            <component
              :is="item.icon"
              class="mr-3 h-5 w-5 flex-shrink-0"
            />
            <span class="flex-1">{{ item.name }}</span>
            <span
              v-if="item.badge"
              class="ml-2 rounded-full bg-status-danger px-2 py-0.5 text-xs font-semibold text-white"
            >
              {{ item.badge }}
            </span>
          </router-link>
        </nav>

        <!-- Version info -->
        <div class="border-t border-border-subtle p-4 text-xs text-brand-slate">
          FactuFlow v0.2.0-mvp
        </div>
      </div>
    </aside>
  </div>
</template>
