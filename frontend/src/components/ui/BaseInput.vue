<script setup lang="ts">
import { computed, useAttrs } from 'vue'

interface Props {
  label?: string
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'date'
  placeholder?: string
  error?: string
  hint?: string
  required?: boolean
  disabled?: boolean
  modelValue?: string | number
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  required: false,
  disabled: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()

const attrs = useAttrs()

const inputClasses = computed(() => {
  const baseClasses = 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-colors duration-200'
  const normalClasses = 'border-gray-300 focus:ring-primary-500 focus:border-transparent'
  const errorClasses = 'border-red-500 focus:ring-red-500'
  
  return `${baseClasses} ${props.error ? errorClasses : normalClasses}`
})

const handleInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="w-full">
    <label v-if="label" class="block text-sm font-medium text-gray-700 mb-1">
      {{ label }}
      <span v-if="required" class="text-red-500">*</span>
    </label>
    
    <input
      :type="type"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :value="modelValue"
      :class="inputClasses"
      v-bind="attrs"
      @input="handleInput"
    />
    
    <p v-if="hint && !error" class="mt-1 text-sm text-gray-500">
      {{ hint }}
    </p>
    
    <p v-if="error" class="mt-1 text-sm text-red-600">
      {{ error }}
    </p>
  </div>
</template>
