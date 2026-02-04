<script setup lang="ts">
import { XMarkIcon } from '@heroicons/vue/24/outline'

interface Props {
  show: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
}

withDefaults(defineProps<Props>(), {
  size: 'md'
})

const emit = defineEmits<{
  close: []
}>()

const sizeClasses = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl'
}

const handleClose = () => {
  emit('close')
}

const handleOverlayClick = (event: MouseEvent) => {
  if (event.target === event.currentTarget) {
    handleClose()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="show"
        class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity z-40"
        @click="handleOverlayClick"
      />
    </Transition>

    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
      enter-to-class="opacity-100 translate-y-0 sm:scale-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100 translate-y-0 sm:scale-100"
      leave-to-class="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
    >
      <div
        v-if="show"
        class="fixed inset-0 z-50 overflow-y-auto"
        @click="handleOverlayClick"
      >
        <div class="flex min-h-full items-center justify-center p-4">
          <div
            :class="['relative w-full bg-white rounded-lg shadow-xl', sizeClasses[size]]"
            @click.stop
          >
            <!-- Header -->
            <div v-if="title || $slots.header" class="flex items-center justify-between p-6 border-b border-gray-200">
              <h3 class="text-lg font-semibold text-gray-900">
                <slot name="header">{{ title }}</slot>
              </h3>
              <button
                type="button"
                class="text-gray-400 hover:text-gray-500 transition-colors"
                @click="handleClose"
              >
                <XMarkIcon class="h-6 w-6" />
              </button>
            </div>

            <!-- Content -->
            <div class="p-6">
              <slot />
            </div>

            <!-- Footer -->
            <div v-if="$slots.footer" class="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50 rounded-b-lg">
              <slot name="footer" />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
