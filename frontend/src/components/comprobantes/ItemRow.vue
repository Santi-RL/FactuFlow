<script setup lang="ts">
import { computed, watch } from 'vue'
import { TrashIcon } from '@heroicons/vue/24/outline'
import type { ItemComprobante } from '@/types/comprobante'
import { ALICUOTAS_IVA } from '@/types/comprobante'

interface Props {
  item: ItemComprobante
  index: number
}

interface Emits {
  (e: 'update:item', item: ItemComprobante): void
  (e: 'remove'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Calcular subtotal automáticamente
const subtotal = computed(() => {
  const base = props.item.cantidad * props.item.precio_unitario
  const descuento = base * (props.item.descuento_porcentaje / 100)
  return base - descuento
})

// Actualizar item cuando cambia el subtotal
watch(subtotal, (newSubtotal) => {
  emit('update:item', {
    ...props.item,
    subtotal: newSubtotal,
  })
})

// Handlers
const updateField = (field: keyof ItemComprobante, value: any) => {
  emit('update:item', {
    ...props.item,
    [field]: value,
  })
}

const formatMonto = (monto: number) => {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 2,
  }).format(monto)
}
</script>

<template>
  <tr class="border-b hover:bg-gray-50">
    <!-- Código -->
    <td class="px-4 py-3">
      <input
        type="text"
        aria-label="Código"
        :value="item.codigo"
        @input="updateField('codigo', ($event.target as HTMLInputElement).value)"
        placeholder="Código"
        class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </td>

    <!-- Descripción -->
    <td class="px-4 py-3">
      <input
        type="text"
        aria-label="Descripción"
        :value="item.descripcion"
        @input="updateField('descripcion', ($event.target as HTMLInputElement).value)"
        placeholder="Descripción *"
        required
        class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </td>

    <!-- Cantidad -->
    <td class="px-4 py-3">
      <input
        type="number"
        aria-label="Cantidad"
        :value="item.cantidad"
        @input="updateField('cantidad', parseFloat(($event.target as HTMLInputElement).value) || 0)"
        placeholder="0"
        step="0.01"
        min="0"
        required
        class="w-20 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </td>

    <!-- Unidad -->
    <td class="px-4 py-3">
      <input
        type="text"
        aria-label="Unidad"
        :value="item.unidad"
        @input="updateField('unidad', ($event.target as HTMLInputElement).value)"
        placeholder="unidades"
        class="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </td>

    <!-- Precio Unitario -->
    <td class="px-4 py-3">
      <input
        type="number"
        aria-label="Precio Unitario"
        :value="item.precio_unitario"
        @input="updateField('precio_unitario', parseFloat(($event.target as HTMLInputElement).value) || 0)"
        placeholder="0.00"
        step="0.01"
        min="0"
        required
        class="w-28 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </td>

    <!-- IVA -->
    <td class="px-4 py-3">
      <select
        aria-label="IVA"
        :value="item.iva_porcentaje"
        @change="updateField('iva_porcentaje', parseFloat(($event.target as HTMLSelectElement).value))"
        class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        <option v-for="alicuota in ALICUOTAS_IVA" :key="alicuota.value" :value="alicuota.value">
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
        @click="emit('remove')"
        class="text-red-600 hover:text-red-700 p-1 rounded hover:bg-red-50"
        title="Eliminar ítem"
      >
        <TrashIcon class="h-5 w-5" />
      </button>
    </td>
  </tr>
</template>
