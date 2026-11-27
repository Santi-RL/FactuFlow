<script setup lang="ts">
import { computed, ref, watch, watchEffect } from "vue";
import { formatearDecimalFiscal, type FiscalDecimal } from "@/utils/fiscal-decimal";

defineOptions({ inheritAttrs: false });
const props = defineProps<{
  modelValue: FiscalDecimal;
  decimalesMinimos?: number;
  ayudaId: string;
  paso?: string;
}>();
const emit = defineEmits<{ "update:modelValue": [valor: FiscalDecimal] }>();
const entrada = ref<HTMLInputElement>();
const texto = ref<string | null>(null);
const invalido = computed(() => Number.isNaN(props.modelValue) && !!texto.value);
const valorVisible = computed(() => Number.isNaN(props.modelValue) ? "" :
  formatearDecimalFiscal(props.modelValue, props.decimalesMinimos));
const interpretarDecimal = (texto: string) => {
  // Un punto aislado puede ser decimal o de miles. Sólo se admite la
  // agrupación pegada si la coma hace inequívoca la lectura argentina.
  const valido = /^(?:\d+(?:,\d*)?|\d{1,3}(?:\.\d{3})+,\d*|,\d+)(?:e[+-]?\d+)?$/i.test(texto);
  const decimal = texto.replace(/\./g, "").replace(",", ".");
  // Los enteros seguros conservan el contrato numérico anterior.
  if (!valido) return NaN;
  return /^\d+$/.test(decimal) && Number.isSafeInteger(Number(decimal))
    ? Number(decimal)
    : decimal.replace(/^\./, "0.");
};

// El mismo control numérico que antes validaba el paso en la entrega del formulario.
watchEffect(() => {
  if (!props.paso || !entrada.value) return;
  const numero = document.createElement("input");
  numero.type = "number";
  numero.min = "0";
  numero.step = props.paso;
  numero.value = String(props.modelValue);
  entrada.value.setCustomValidity(numero.validity.stepMismatch
    ? "La cantidad debe ser un múltiplo de " + formatearDecimalFiscal(props.paso) + "."
    : "");
});

function editar(valor: string) {
  texto.value = valor;
  emit("update:modelValue", interpretarDecimal(valor));
}
watch(() => props.modelValue, (valor) => {
  if (texto.value !== null && !Object.is(interpretarDecimal(texto.value), valor))
    texto.value = null;
});
</script>

<template>
  <input
    ref="entrada"
    v-bind="$attrs"
    type="text"
    inputmode="decimal"
    :value="texto ?? valorVisible"
    :aria-invalid="invalido"
    :aria-describedby="invalido ? ayudaId : undefined"
    @input="editar(($event.target as HTMLInputElement).value)"
    @blur="!invalido && (texto = null)"
  >
  <small
    v-if="invalido"
    :id="ayudaId"
    class="block text-red-700"
  >
    Usá coma decimal, por ejemplo 1,234 o 1.234,00.
  </small>
</template>
