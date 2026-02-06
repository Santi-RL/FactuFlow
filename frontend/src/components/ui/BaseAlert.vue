<script setup lang="ts">
import { computed } from 'vue'
import { CheckCircleIcon, XCircleIcon, ExclamationTriangleIcon, InformationCircleIcon, XMarkIcon } from '@heroicons/vue/24/outline'

interface Props {
  type: 'success' | 'error' | 'warning' | 'info'
  title?: string
  message?: string
  dismissible?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  message: '',
  dismissible: true
})

const emit = defineEmits<{
  dismiss: []
}>()

const iconComponent = computed(() => {
  const icons = {
    success: CheckCircleIcon,
    error: XCircleIcon,
    warning: ExclamationTriangleIcon,
    info: InformationCircleIcon
  }
  return icons[props.type]
})

const colorClasses = computed(() => {
  const colors = {
    success: 'bg-green-50 border-green-200 text-green-800',
    error: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800'
  }
  return colors[props.type]
})

const iconColorClasses = computed(() => {
  const colors = {
    success: 'text-green-600',
    error: 'text-red-600',
    warning: 'text-yellow-600',
    info: 'text-blue-600'
  }
  return colors[props.type]
})
</script>

<template>
  <div :class="['p-4 rounded-lg border flex items-start gap-3', colorClasses]">
    <component
      :is="iconComponent"
      :class="['h-5 w-5 flex-shrink-0 mt-0.5', iconColorClasses]"
    />
    
    <div class="flex-1">
      <h3
        v-if="title"
        class="text-sm font-medium"
      >
        {{ title }}
      </h3>
      <div
        v-if="$slots.default"
        :class="[title ? 'mt-1 text-sm opacity-90' : 'text-sm opacity-90']"
      >
        <slot />
      </div>
      <p
        v-else-if="message"
        :class="[title ? 'mt-1 text-sm opacity-90' : 'text-sm opacity-90']"
      >
        {{ message }}
      </p>
    </div>
    
    <button
      v-if="dismissible"
      type="button"
      class="flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity"
      @click="emit('dismiss')"
    >
      <XMarkIcon class="h-5 w-5" />
    </button>
  </div>
</template>
