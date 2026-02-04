<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  subtotal: number
  iva21: number
  iva105: number
  iva27: number
  total: number
}

const props = defineProps<Props>()

const formatMonto = (monto: number) => {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
  }).format(monto)
}

const tieneIva = computed(() => {
  return props.iva21 > 0 || props.iva105 > 0 || props.iva27 > 0
})
</script>

<template>
  <div class="bg-gray-50 rounded-lg p-6 border border-gray-200">
    <div class="space-y-3">
      <!-- Subtotal -->
      <div class="flex justify-between text-gray-700">
        <span class="font-medium">Subtotal:</span>
        <span class="font-mono">{{ formatMonto(subtotal) }}</span>
      </div>

      <!-- IVA 21% -->
      <div
        v-if="iva21 > 0"
        class="flex justify-between text-gray-700"
      >
        <span class="font-medium">IVA 21%:</span>
        <span class="font-mono">{{ formatMonto(iva21) }}</span>
      </div>

      <!-- IVA 10.5% -->
      <div
        v-if="iva105 > 0"
        class="flex justify-between text-gray-700"
      >
        <span class="font-medium">IVA 10.5%:</span>
        <span class="font-mono">{{ formatMonto(iva105) }}</span>
      </div>

      <!-- IVA 27% -->
      <div
        v-if="iva27 > 0"
        class="flex justify-between text-gray-700"
      >
        <span class="font-medium">IVA 27%:</span>
        <span class="font-mono">{{ formatMonto(iva27) }}</span>
      </div>

      <!-- Separador -->
      <div class="border-t border-gray-300 pt-3">
        <div class="flex justify-between text-xl font-bold text-gray-900">
          <span>TOTAL:</span>
          <span class="font-mono">{{ formatMonto(total) }}</span>
        </div>
      </div>

      <!-- Mensaje si no hay IVA -->
      <div
        v-if="!tieneIva"
        class="text-sm text-gray-500 text-center pt-2"
      >
        * Los items no tienen IVA
      </div>
    </div>
  </div>
</template>
