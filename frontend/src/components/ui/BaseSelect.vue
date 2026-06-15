<script setup lang="ts">
import { computed, useAttrs, useId } from "vue";

interface Option {
  value: string | number;
  label: string;
}

interface Props {
  label?: string;
  options: Option[];
  placeholder?: string;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  modelValue?: string | number;
}

const props = withDefaults(defineProps<Props>(), {
  label: "",
  placeholder: "",
  error: "",
  required: false,
  disabled: false,
  modelValue: "",
});

const emit = defineEmits<{
  "update:modelValue": [value: string | number];
}>();

const attrs = useAttrs();
const generatedId = useId();
const selectId = computed(() => (attrs.id as string) || generatedId);
const tieneOpcionVacia = computed(() =>
  props.options.some((option) => option.value === ""),
);

const selectClasses = computed(() => {
  const baseClasses =
    "w-full rounded-control border bg-surface-card px-3 py-2 text-brand-ink focus:outline-none focus:ring-2 transition-colors duration-200 disabled:cursor-not-allowed disabled:bg-surface-page disabled:text-brand-slate";
  const normalClasses =
    "border-border-subtle focus:border-brand-flow focus:ring-brand-flow";
  const errorClasses = "border-status-danger focus:border-status-danger focus:ring-status-danger";

  return `${baseClasses} ${props.error ? errorClasses : normalClasses}`;
});

const handleChange = (event: Event) => {
  const target = event.target as HTMLSelectElement;
  emit("update:modelValue", target.value);
};
</script>

<template>
  <div class="w-full">
    <label
      v-if="label"
      :for="selectId"
      class="mb-1 block text-sm font-medium text-brand-ink"
    >
      {{ label }}
      <span
        v-if="required"
        class="text-status-danger"
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
        v-if="!tieneOpcionVacia"
        value=""
        disabled
      >
        {{ placeholder || "Seleccionar..." }}
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
      class="mt-1 text-sm text-status-danger"
    >
      {{ error }}
    </p>
  </div>
</template>
