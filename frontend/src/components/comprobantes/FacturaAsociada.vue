<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import BaseCard from "@/components/ui/BaseCard.vue";
import comprobantesService from "@/services/comprobantes.service";
import { formatearDecimalFiscal } from "@/utils/fiscal-decimal";
import type { PreparacionNota } from "@/types/comprobante";

const props = defineProps<{ tipoNota: number; empresaId: number }>();
const emit = defineEmits<{ preparada: [original: PreparacionNota | null] }>();
const route = useRoute();
const tipos: Record<number, number> = {
  2: 1,
  3: 1,
  7: 6,
  8: 6,
  12: 11,
  13: 11,
};
const tipoOriginal = computed(() => tipos[props.tipoNota]);
const letra = computed(
  () => ({ 1: "A", 6: "B", 11: "C" })[tipoOriginal.value as 1],
);
const punto = ref("");
const numero = ref("");
const loading = ref(false);
const error = ref("");
const original = ref<PreparacionNota | null>(null);
let solicitud = 0;
const invalidar = () => {
  solicitud++;
  loading.value = false;
  error.value = "";
  original.value = null;
  emit("preparada", null);
};
watch([punto, numero], invalidar, { flush: "sync" });
async function consultar() {
  invalidar();
  const pv = Number(punto.value);
  const nro = Number(numero.value);
  if (
    !Number.isInteger(pv) ||
    pv < 1 ||
    pv > 99999 ||
    !Number.isInteger(nro) ||
    nro < 1 ||
    nro > 99999999
  ) {
    error.value =
      "Indicá el punto de venta y el número de la factura original.";
    return;
  }
  const id = ++solicitud;
  loading.value = true;
  try {
    const resultado = await comprobantesService.originalNota(
      tipoOriginal.value,
      pv,
      nro,
    );
    if (id !== solicitud) return;
    original.value = resultado;
    emit("preparada", resultado);
  } catch (e: unknown) {
    if (id !== solicitud) return;
    const detalle = (e as { response?: { data?: { detail?: unknown } } })
      .response?.data?.detail;
    error.value =
      typeof detalle === "string"
        ? detalle
        : "No se pudo consultar la factura. Revisá sus datos y volvé a intentar.";
  } finally {
    if (id === solicitud) loading.value = false;
  }
}
watch(
  [() => tipoOriginal.value, () => props.empresaId],
  () => {
    invalidar();
    punto.value = "";
    numero.value = "";
    if (
      Number(route.query.emisor) === props.empresaId &&
      Number(route.query.originalTipo) === tipoOriginal.value
    ) {
      punto.value = String(route.query.originalPunto || "");
      numero.value = String(route.query.originalNumero || "");
      if (punto.value && numero.value) void consultar();
    }
  },
  { immediate: true },
);
watch(() => props.tipoNota, (tipo, anterior) => {
  if (tipos[tipo] === tipos[anterior] && original.value) {
    emit("preparada", original.value);
  }
});
onBeforeUnmount(invalidar);
</script>

<template>
  <BaseCard title="Factura que se ajusta">
    <p class="mb-4 text-sm text-gray-600">
      Indicá la factura {{ letra }} del emisor activo. Puede haberse emitido en
      FactuFlow o en otro sistema.
    </p>
    <div class="grid grid-cols-1 items-end gap-4 sm:grid-cols-3">
      <div>
        <label
          for="original-punto"
          class="mb-1 block text-sm font-medium text-gray-700"
        >Punto de venta del original</label>
        <input
          id="original-punto"
          v-model="punto"
          inputmode="numeric"
          maxlength="5"
          class="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-blue-500 focus:ring-2 focus:ring-blue-500"
        >
      </div>
      <div>
        <label
          for="original-numero"
          class="mb-1 block text-sm font-medium text-gray-700"
        >Número de factura</label>
        <input
          id="original-numero"
          v-model="numero"
          inputmode="numeric"
          maxlength="8"
          class="w-full rounded-lg border border-gray-300 px-3 py-2 focus:border-blue-500 focus:ring-2 focus:ring-blue-500"
        >
      </div>
      <button
        type="button"
        :disabled="loading"
        class="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-blue-700 focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        @click="consultar"
      >
        {{ loading ? "Consultando factura…" : "Consultar factura" }}
      </button>
    </div>
    <p
      v-if="error"
      role="alert"
      class="mt-4 text-sm text-red-700"
    >
      {{ error }}
    </p>
    <div
      v-if="original"
      class="mt-4 space-y-1 text-sm text-gray-700"
      role="status"
    >
      <p class="font-medium">
        Factura {{ letra }}
        {{ String(original.asociado.punto_venta).padStart(5, "0") }}-{{
          String(original.asociado.numero).padStart(8, "0")
        }}
        · $ {{ formatearDecimalFiscal(original.total, 2) }}
      </p>
      <p v-if="original.origen === 'arca'">
        Factura consultada en ARCA. Completá el nombre del receptor, su
        condición IVA y la descripción del ajuste según el original.
      </p>
      <p>El punto de venta de la nota se elige en «Datos del comprobante».</p>
    </div>
    <slot />
  </BaseCard>
</template>
