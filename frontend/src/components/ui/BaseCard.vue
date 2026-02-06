<script setup lang="ts">
interface Props {
  title?: string
  padding?: boolean
}

withDefaults(defineProps<Props>(), {
  title: '',
  padding: true
})
</script>

<template>
  <div class="bg-white rounded-lg shadow-sm border border-gray-200">
    <div
      v-if="title || $slots.header"
      class="px-6 py-4 border-b border-gray-200"
    >
      <h3 class="text-lg font-semibold text-gray-900">
        <slot name="header">
          {{ title }}
        </slot>
      </h3>
    </div>
    
    <div :class="padding ? 'p-6' : ''">
      <slot />
    </div>
    
    <div
      v-if="$slots.footer"
      class="px-6 py-4 border-t border-gray-200 bg-gray-50"
    >
      <slot name="footer" />
    </div>
  </div>
</template>
