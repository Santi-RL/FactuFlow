<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useAuth } from '@/composables/useAuth'
import { UserCircleIcon, ArrowRightOnRectangleIcon } from '@heroicons/vue/24/outline'
import { ref } from 'vue'

const authStore = useAuthStore()
const { logout } = useAuth()

const showDropdown = ref(false)

const handleLogout = async () => {
  await logout()
}
</script>

<template>
  <header class="h-16 bg-white border-b border-gray-200 flex items-center justify-end px-6">
    <div class="relative">
      <button
        class="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
        @click="showDropdown = !showDropdown"
      >
        <UserCircleIcon class="h-6 w-6" />
        <span>{{ authStore.user?.nombre || 'Usuario' }}</span>
      </button>

      <!-- Dropdown -->
      <div
        v-if="showDropdown"
        v-click-outside="() => showDropdown = false"
        class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1"
      >
        <div class="px-4 py-2 border-b border-gray-200">
          <p class="text-sm font-medium text-gray-900">
            {{ authStore.user?.nombre }}
          </p>
          <p class="text-xs text-gray-500 truncate">
            {{ authStore.user?.email }}
          </p>
        </div>
        
        <button
          class="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          @click="handleLogout"
        >
          <ArrowRightOnRectangleIcon class="h-5 w-5" />
          Cerrar sesión
        </button>
      </div>
    </div>
  </header>
</template>

<script lang="ts">
// Simple click outside directive
const vClickOutside = {
  mounted(el: any, binding: any) {
    el.clickOutsideEvent = (event: Event) => {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value()
      }
    }
    document.addEventListener('click', el.clickOutsideEvent)
  },
  unmounted(el: any) {
    document.removeEventListener('click', el.clickOutsideEvent)
  }
}

export default {
  directives: {
    clickOutside: vClickOutside
  }
}
</script>
