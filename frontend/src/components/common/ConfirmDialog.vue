<script setup lang="ts">
import BaseModal from '../ui/BaseModal.vue'
import BaseButton from '../ui/BaseButton.vue'
import { ExclamationTriangleIcon } from '@heroicons/vue/24/outline'

interface Props {
  show: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'primary'
}

withDefaults(defineProps<Props>(), {
  title: '¿Está seguro?',
  message: 'Esta acción no se puede deshacer',
  confirmText: 'Confirmar',
  cancelText: 'Cancelar',
  variant: 'danger'
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <BaseModal :show="show" size="sm" @close="emit('cancel')">
    <div class="text-center">
      <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 mb-4">
        <ExclamationTriangleIcon class="h-6 w-6 text-red-600" />
      </div>
      
      <h3 class="text-lg font-semibold text-gray-900 mb-2">{{ title }}</h3>
      <p class="text-sm text-gray-500 mb-6">{{ message }}</p>
      
      <div class="flex gap-3 justify-center">
        <BaseButton variant="secondary" @click="emit('cancel')">
          {{ cancelText }}
        </BaseButton>
        <BaseButton :variant="variant" @click="emit('confirm')">
          {{ confirmText }}
        </BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
