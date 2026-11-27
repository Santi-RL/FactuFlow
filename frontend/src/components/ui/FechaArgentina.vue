<script setup lang="ts">
import { computed, ref, watch, watchEffect } from "vue";
import { CalendarDaysIcon } from "@heroicons/vue/24/outline";
import { fechaArgentinaAIso, formatearFecha } from "@/composables/useFormatters";

defineOptions({ inheritAttrs: false });
const props = defineProps<{
  modelValue?: string | null;
  disabled?: boolean;
  min?: string;
  max?: string;
}>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
const texto = ref(formatearFecha(props.modelValue || ""));
const entrada = ref<HTMLInputElement>();
const calendario = ref<HTMLInputElement>();
const iso = computed(() => fechaArgentinaAIso(texto.value));
const error = computed(() => {
  if (texto.value && !iso.value) return "Ingresá una fecha válida en formato DD/MM/AAAA.";
  if (iso.value && props.min && iso.value < props.min)
    return "La primera fecha permitida es " + formatearFecha(props.min) + ".";
  if (iso.value && props.max && iso.value > props.max)
    return "La última fecha permitida es " + formatearFecha(props.max) + ".";
  return "";
});
watchEffect(() => entrada.value?.setCustomValidity(error.value));
watch(() => props.modelValue, (valor) => {
  if ((valor || "") !== iso.value) texto.value = formatearFecha(valor || "");
});
function editar(valor: string) {
  texto.value = valor;
  emit("update:modelValue", iso.value);
}
function elegir(event: Event) {
  editar(formatearFecha((event.target as HTMLInputElement).value));
  entrada.value?.focus();
}
</script>

<template>
  <span class="relative inline-flex w-full max-w-full items-center">
    <input
      ref="entrada"
      v-bind="$attrs"
      type="text"
      placeholder="DD/MM/AAAA"
      :disabled="disabled"
      :value="texto"
      :aria-invalid="($attrs['aria-invalid'] as boolean | 'true' | 'false' | undefined) || (!!texto && !!error)"
      class="min-w-0 pr-10"
      @input="editar(($event.target as HTMLInputElement).value)"
    >
    <span class="absolute inset-y-0 right-1 flex w-8 items-center justify-center rounded focus-within:ring-2">
      <CalendarDaysIcon
        class="pointer-events-none h-5 w-5 text-brand-slate"
        aria-hidden="true"
      />
      <input
        ref="calendario"
        type="date"
        aria-label="Elegir fecha en el calendario"
        :value="iso"
        :disabled="disabled"
        :min="min"
        :max="max"
        class="calendario absolute inset-0 h-full w-full cursor-pointer opacity-0"
        @click="calendario?.showPicker?.()"
        @change="elegir"
      >
    </span>
  </span>
</template>

<style scoped>
.calendario::-webkit-calendar-picker-indicator {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
}
</style>
