<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { TrashIcon } from "@heroicons/vue/24/outline";
import type { EditableItemComprobante as ItemComprobante } from "@/types/comprobante";
import { ALICUOTAS_IVA } from "@/types/comprobante";
import { subtotalItem } from "@/utils/comprobante-items";
import { formatearDecimalFiscal } from "@/utils/fiscal-decimal";

interface Props {
  item: ItemComprobante;
  index: number;
  soloIvaCero?: boolean;
}

interface Emits {
  (e: "update:item", item: ItemComprobante): void;
  (e: "remove"): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const alicuotasDisponibles = computed(() => {
  if (props.soloIvaCero) {
    return ALICUOTAS_IVA.filter((alicuota) => alicuota.value === 0);
  }
  return ALICUOTAS_IVA;
});

// Calcular subtotal automáticamente
const subtotal = computed(() => subtotalItem(props.item));

// Handlers
const updateField = (field: keyof ItemComprobante, value: any) => {
  emit("update:item", {
    ...props.item,
    [field]: value,
  });
};

const textoPrecioEnEdicion = ref<string | null>(null);
const errorSeparador = computed(() =>
  Number.isNaN(props.item.precio_unitario) && !!textoPrecioEnEdicion.value,
);
const precioCompleto = computed(() =>
  Number.isNaN(props.item.precio_unitario)
    ? ""
    : formatearDecimalFiscal(props.item.precio_unitario, 2),
);

const interpretarPrecio = (texto: string) => {
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

const editarPrecio = (texto: string) => {
  textoPrecioEnEdicion.value = texto;
  updateField("precio_unitario", interpretarPrecio(texto));
};

watch(() => props.item.precio_unitario, (nuevo) => {
  const texto = textoPrecioEnEdicion.value;
  if (texto !== null && !Object.is(interpretarPrecio(texto), nuevo))
    textoPrecioEnEdicion.value = null;
});

const formatMonto = (monto: number | null) => {
  if (monto === null) return "Revisá los importes";
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
  }).format(monto);
};
</script>

<template>
  <tr class="border-b hover:bg-gray-50">
    <!-- Código -->
    <td class="px-4 py-3">
      <input
        type="text"
        aria-label="Código"
        :value="item.codigo"
        placeholder="Código"
        class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        @input="
          updateField('codigo', ($event.target as HTMLInputElement).value)
        "
      >
    </td>

    <!-- Descripción -->
    <td class="px-4 py-3">
      <input
        type="text"
        aria-label="Descripción"
        :value="item.descripcion"
        placeholder="Descripción *"
        required
        class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        @input="
          updateField('descripcion', ($event.target as HTMLInputElement).value)
        "
      >
    </td>

    <!-- Cantidad -->
    <td class="px-4 py-3">
      <input
        type="number"
        aria-label="Cantidad"
        :value="Number.isFinite(Number(item.cantidad)) ? item.cantidad : ''"
        placeholder="0"
        step="0.01"
        min="0"
        required
        class="w-20 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        @input="
          updateField(
            'cantidad',
            ($event.target as HTMLInputElement).valueAsNumber,
          )
        "
      >
    </td>

    <!-- Unidad -->
    <td class="px-4 py-3">
      <input
        type="text"
        aria-label="Unidad"
        :value="item.unidad"
        placeholder="unidades"
        class="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        @input="
          updateField('unidad', ($event.target as HTMLInputElement).value)
        "
      >
    </td>

    <!-- Precio Unitario -->
    <td class="px-4 py-3">
      <input
        type="text"
        inputmode="decimal"
        aria-label="Precio Unitario"
        :value="textoPrecioEnEdicion ?? precioCompleto"
        :aria-invalid="errorSeparador"
        :aria-describedby="errorSeparador ? 'ayuda-precio-' + index : undefined"
        placeholder="0,00"
        required
        class="w-28 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        @input="editarPrecio(($event.target as HTMLInputElement).value)"
        @blur="!errorSeparador && (textoPrecioEnEdicion = null)"
      >
      <small
        v-if="errorSeparador"
        :id="'ayuda-precio-' + index"
        class="block text-red-700"
      >
        Usá coma decimal, por ejemplo 1,234 o 1.234,00.
      </small>
    </td>

    <!-- IVA -->
    <td class="px-4 py-3">
      <select
        aria-label="IVA"
        :value="item.iva_porcentaje"
        class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        @change="
          updateField(
            'iva_porcentaje',
            parseFloat(($event.target as HTMLSelectElement).value),
          )
        "
      >
        <option
          v-for="alicuota in alicuotasDisponibles"
          :key="alicuota.value"
          :value="alicuota.value"
        >
          {{ alicuota.label }}
        </option>
      </select>
    </td>

    <!-- Subtotal -->
    <td class="px-4 py-3 text-right font-mono text-sm">
      {{ formatMonto(subtotal) }}
    </td>

    <!-- Acciones -->
    <td class="px-4 py-3 text-center">
      <button
        type="button"
        class="text-red-600 hover:text-red-700 p-1 rounded hover:bg-red-50"
        title="Eliminar ítem"
        @click="emit('remove')"
      >
        <TrashIcon class="h-5 w-5" />
      </button>
    </td>
  </tr>
</template>
