<script setup lang="ts">
import { computed, useAttrs, useId } from "vue";

interface Props {
  label?: string;
  type?: "text" | "email" | "password" | "number" | "tel" | "date";
  placeholder?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  disabled?: boolean;
  modelValue?: string | number | null;
}

const props = withDefaults(defineProps<Props>(), {
  label: "",
  type: "text",
  placeholder: "",
  error: "",
  hint: "",
  required: false,
  disabled: false,
  modelValue: "",
});

const emit = defineEmits<{
  "update:modelValue": [value: string | number];
}>();

const attrs = useAttrs();
const generatedId = useId();
const inputId = computed(() => (attrs.id as string) || generatedId);

const inputClasses = computed(() => {
  const baseClasses =
    "w-full rounded-control border bg-surface-card px-3 py-2 text-brand-ink placeholder:text-brand-slate focus:outline-none focus:ring-2 transition-colors duration-200 disabled:cursor-not-allowed disabled:bg-surface-page disabled:text-brand-slate";
  const normalClasses =
    "border-border-subtle focus:border-brand-flow focus:ring-brand-flow";
  const errorClasses = "border-status-danger focus:border-status-danger focus:ring-status-danger";

  return `${baseClasses} ${props.error ? errorClasses : normalClasses}`;
});

const handleInput = (event: Event) => {
  const target = event.target as HTMLInputElement;
  emit("update:modelValue", target.value);
};
</script>

<template>
  <div class="w-full">
    <label
      v-if="label"
      :for="inputId"
      class="mb-1 block text-sm font-medium text-brand-ink"
    >
      {{ label }}
      <span
        v-if="required"
        class="text-status-danger"
      >*</span>
    </label>

    <input
      :id="inputId"
      :type="type"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :value="modelValue"
      :class="inputClasses"
      v-bind="attrs"
      @input="handleInput"
    >

    <p
      v-if="hint && !error"
      class="mt-1 text-sm text-brand-slate"
    >
      {{ hint }}
    </p>

    <p
      v-if="error"
      class="mt-1 text-sm text-status-danger"
    >
      {{ error }}
    </p>
  </div>
</template>
