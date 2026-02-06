<script setup lang="ts">
import { computed, useAttrs, useId } from 'vue'

interface Option {
  value: string | number
  label: string
}

interface Props {
  label?: string
  options: Option[]
  placeholder?: string
  error?: string
  required?: boolean
  disabled?: boolean
  modelValue?: string | number
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
  placeholder: '',
  error: '',
  required: false,
  disabled: false,
  modelValue: '',
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
}>()

const attrs = useAttrs()
const generatedId = useId()
const selectId = computed(() => (attrs.id as string) || generatedId)

const selectClasses = computed(() => {
  const baseClasses = 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 transition-colors duration-200'
  const normalClasses = 'border-gray-300 focus:ring-primary-500 focus:border-transparent'
  const errorClasses = 'border-red-500 focus:ring-red-500'
  
  return `${baseClasses} ${props.error ? errorClasses : normalClasses}`
})

const handleChange = (event: Event) => {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="w-full">
    <label
      v-if="label"
      :for="selectId"
      class="block text-sm font-medium text-gray-700 mb-1"
    >
      {{ label }}
      <span
        v-if="required"
        class="text-red-500"
      >*</span>
    </label>
    
    <select
      :id="selectId"
      :required="required"
      :disabled="disabled"
      :value="modelValue"
      :class="selectClasses"
      v-bind="attrs"
      @change="handleChange"
    >
      <option
        value=""
        disabled
      >
        {{ placeholder || 'Seleccionar...' }}
      </option>
      <option
        v-for="option in options"
        :key="option.value"
        :value="option.value"
      >
        {{ option.label }}
      </option>
    </select>
    
    <p
      v-if="error"
      class="mt-1 text-sm text-red-600"
    >
      {{ error }}
    </p>
  </div>
</template>
