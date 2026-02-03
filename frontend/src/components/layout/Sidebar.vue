<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUIStore } from '@/stores/ui'
import {
  HomeIcon,
  UsersIcon,
  DocumentTextIcon,
  BuildingOfficeIcon,
  KeyIcon,
  Bars3Icon,
  XMarkIcon
} from '@heroicons/vue/24/outline'
import certificadosService from '@/services/certificados.service'

const route = useRoute()
const uiStore = useUIStore()

const certificadosPorVencer = ref(0)

const menuItems = computed(() => [
  { name: 'Dashboard', icon: HomeIcon, path: '/' },
  { name: 'Clientes', icon: UsersIcon, path: '/clientes' },
  { name: 'Comprobantes', icon: DocumentTextIcon, path: '/comprobantes' },
  { 
    name: 'Certificados', 
    icon: KeyIcon, 
    path: '/certificados',
    badge: certificadosPorVencer.value > 0 ? certificadosPorVencer.value : null
  },
  { name: 'Mi Empresa', icon: BuildingOfficeIcon, path: '/empresa' }
])

const isActive = (path: string) => {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}

const cargarAlertasVencimiento = async () => {
  try {
    const alertas = await certificadosService.obtenerAlertasVencimiento()
    certificadosPorVencer.value = alertas.length
  } catch (err) {
    // Silently fail, it's not critical
    console.error('Error loading certificate alerts:', err)
  }
}

onMounted(() => {
  cargarAlertasVencimiento()
  // Reload alerts every 5 minutes
  setInterval(cargarAlertasVencimiento, 5 * 60 * 1000)
})
</script>

<template>
  <div>
    <!-- Mobile menu button -->
    <div class="lg:hidden fixed top-4 left-4 z-50">
      <button
        @click="uiStore.toggleSidebar"
        class="p-2 rounded-md text-gray-700 bg-white shadow-md"
      >
        <Bars3Icon v-if="!uiStore.sidebarOpen" class="h-6 w-6" />
        <XMarkIcon v-else class="h-6 w-6" />
      </button>
    </div>

    <!-- Overlay for mobile -->
    <div
      v-if="uiStore.sidebarOpen"
      class="lg:hidden fixed inset-0 bg-gray-600 bg-opacity-75 z-40"
      @click="uiStore.toggleSidebar"
    />

    <!-- Sidebar -->
    <aside
      :class="[
        'fixed lg:static inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 ease-in-out',
        uiStore.sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      ]"
    >
      <div class="flex flex-col h-full">
        <!-- Logo -->
        <div class="flex items-center h-16 px-6 border-b border-gray-200">
          <h1 class="text-xl font-bold text-primary-600">FactuFlow</h1>
        </div>

        <!-- Navigation -->
        <nav class="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          <router-link
            v-for="item in menuItems"
            :key="item.path"
            :to="item.path"
            :class="[
              'flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors',
              isActive(item.path)
                ? 'bg-primary-50 text-primary-700'
                : 'text-gray-700 hover:bg-gray-50'
            ]"
            @click="uiStore.sidebarOpen = false"
          >
            <component :is="item.icon" class="mr-3 h-5 w-5 flex-shrink-0" />
            <span class="flex-1">{{ item.name }}</span>
            <span
              v-if="item.badge"
              class="ml-2 px-2 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-800"
            >
              {{ item.badge }}
            </span>
          </router-link>
        </nav>

        <!-- Version info -->
        <div class="p-4 border-t border-gray-200 text-xs text-gray-500">
          FactuFlow v0.1.0
        </div>
      </div>
    </aside>
  </div>
</template>
