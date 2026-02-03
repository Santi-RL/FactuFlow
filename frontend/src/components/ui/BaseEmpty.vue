<script setup lang="ts">
import { FolderOpenIcon } from '@heroicons/vue/24/outline'

interface Props {
  title?: string
  message?: string
  icon?: any
}

const props = withDefaults(defineProps<Props>(), {
  title: 'No hay datos',
  message: 'No se encontraron resultados',
  icon: FolderOpenIcon
})
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 text-center">
    <component
      :is="icon"
      class="h-16 w-16 text-gray-400 mb-4"
    />
    <h3 class="text-lg font-medium text-gray-900 mb-1">{{ title }}</h3>
    <p class="text-gray-500">{{ message }}</p>
    <div v-if="$slots.default" class="mt-6">
      <slot />
    </div>
  </div>
</template>
