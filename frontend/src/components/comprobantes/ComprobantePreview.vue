<script setup lang="ts">
import { computed } from 'vue'
import { XMarkIcon, CheckIcon } from '@heroicons/vue/24/outline'
import { TIPOS_COMPROBANTE_NOMBRES } from '@/types/comprobante'

interface Props {
  formData: any
  totales: {
    subtotal: number
    iva21: number
    iva105: number
    iva27: number
    total: number
  }
  proximoNumero: number | null
  empresa: any
}

interface Emits {
  (e: 'close'): void
  (e: 'confirm'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const formatMonto = (monto: number) => {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
  }).format(monto)
}

const tipoComprobanteNombre = computed(() => {
  return TIPOS_COMPROBANTE_NOMBRES[props.formData.tipo_comprobante] || 'Comprobante'
})

const numeroCompleto = computed(() => {
  // TODO: Obtener punto de venta real
  const puntoVenta = '0001'
  const numero = String(props.proximoNumero || 0).padStart(8, '0')
  return `${puntoVenta}-${numero}`
})
</script>

<template>
  <div class="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-50 flex items-center justify-center p-4">
    <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
      <!-- Header del modal -->
      <div class="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h2 class="text-2xl font-bold text-gray-900">
          Vista Previa
        </h2>
        <button
          type="button"
          class="text-gray-400 hover:text-gray-600"
          @click="emit('close')"
        >
          <XMarkIcon class="h-6 w-6" />
        </button>
      </div>

      <!-- Contenido del comprobante -->
      <div class="p-8">
        <div class="border-2 border-gray-300 rounded-lg p-8 bg-white">
          <!-- Encabezado -->
          <div class="flex justify-between items-start mb-8">
            <!-- Datos de la empresa -->
            <div>
              <h3 class="text-2xl font-bold text-gray-900 mb-2">
                {{ empresa?.razon_social || 'MI EMPRESA' }}
              </h3>
              <div class="text-sm text-gray-600 space-y-1">
                <p>CUIT: {{ empresa?.cuit || '30-12345678-9' }}</p>
                <p v-if="empresa?.domicilio">
                  {{ empresa.domicilio }}
                </p>
                <p v-if="empresa?.localidad">
                  {{ empresa.localidad }}, {{ empresa.provincia }}
                </p>
              </div>
            </div>

            <!-- Tipo y número de comprobante -->
            <div class="text-right">
              <div class="text-3xl font-bold text-blue-600 mb-2">
                {{ tipoComprobanteNombre }}
              </div>
              <div class="text-sm text-gray-600">
                <p>Nro: {{ numeroCompleto }}</p>
                <p>Fecha: {{ new Date().toLocaleDateString('es-AR') }}</p>
              </div>
            </div>
          </div>

          <!-- Separador -->
          <div class="border-t-2 border-gray-300 my-6" />

          <!-- Datos del cliente -->
          <div class="mb-8">
            <h4 class="font-semibold text-gray-900 mb-3">
              Cliente:
            </h4>
            <div class="text-sm text-gray-700 space-y-1">
              <p>{{ formData.cliente.razon_social }}</p>
              <p>{{ formData.cliente.numero_documento }}</p>
              <p>IVA: {{ formData.cliente.condicion_iva }}</p>
              <p v-if="formData.cliente.domicilio">
                {{ formData.cliente.domicilio }}
              </p>
            </div>
          </div>

          <!-- Separador -->
          <div class="border-t border-gray-200 my-6" />

          <!-- Tabla de items -->
          <div class="mb-8">
            <table class="w-full">
              <thead class="border-b border-gray-300">
                <tr class="text-left text-sm font-semibold text-gray-700">
                  <th class="pb-2">
                    Descripción
                  </th>
                  <th class="pb-2 text-center">
                    Cant.
                  </th>
                  <th class="pb-2 text-right">
                    Precio
                  </th>
                  <th class="pb-2 text-right">
                    Subtotal
                  </th>
                </tr>
              </thead>
              <tbody class="text-sm text-gray-700">
                <tr
                  v-for="(item, index) in formData.items"
                  :key="index"
                  class="border-b border-gray-100"
                >
                  <td class="py-3">
                    {{ item.descripcion }}
                    <span
                      v-if="item.codigo"
                      class="text-xs text-gray-500"
                    >({{ item.codigo }})</span>
                  </td>
                  <td class="py-3 text-center">
                    {{ item.cantidad }} {{ item.unidad }}
                  </td>
                  <td class="py-3 text-right font-mono">
                    {{ formatMonto(item.precio_unitario) }}
                  </td>
                  <td class="py-3 text-right font-mono">
                    {{ formatMonto(item.cantidad * item.precio_unitario * (1 - item.descuento_porcentaje / 100)) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Separador -->
          <div class="border-t-2 border-gray-300 my-6" />

          <!-- Totales -->
          <div class="flex justify-end">
            <div class="w-64 space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-700">Subtotal:</span>
                <span class="font-mono">{{ formatMonto(totales.subtotal) }}</span>
              </div>
              <div
                v-if="totales.iva21 > 0"
                class="flex justify-between"
              >
                <span class="text-gray-700">IVA 21%:</span>
                <span class="font-mono">{{ formatMonto(totales.iva21) }}</span>
              </div>
              <div
                v-if="totales.iva105 > 0"
                class="flex justify-between"
              >
                <span class="text-gray-700">IVA 10.5%:</span>
                <span class="font-mono">{{ formatMonto(totales.iva105) }}</span>
              </div>
              <div
                v-if="totales.iva27 > 0"
                class="flex justify-between"
              >
                <span class="text-gray-700">IVA 27%:</span>
                <span class="font-mono">{{ formatMonto(totales.iva27) }}</span>
              </div>
              <div class="border-t border-gray-300 pt-2">
                <div class="flex justify-between text-xl font-bold">
                  <span>TOTAL:</span>
                  <span class="font-mono">{{ formatMonto(totales.total) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Observaciones -->
          <div
            v-if="formData.observaciones"
            class="mt-6"
          >
            <h4 class="font-semibold text-gray-900 mb-2">
              Observaciones:
            </h4>
            <p class="text-sm text-gray-700 whitespace-pre-line">
              {{ formData.observaciones }}
            </p>
          </div>

          <!-- Separador -->
          <div class="border-t border-gray-200 my-6" />

          <!-- CAE pendiente -->
          <div class="text-sm text-gray-500 space-y-1">
            <p>CAE: (pendiente de emisión)</p>
            <p>Vto. CAE: (pendiente de emisión)</p>
          </div>
        </div>

        <!-- Advertencia -->
        <div class="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4">
          <p class="text-sm text-amber-800">
            ⚠️ Esta es una vista previa. El CAE se obtendrá al confirmar la emisión.
          </p>
        </div>
      </div>

      <!-- Footer con botones -->
      <div class="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex items-center justify-end gap-4">
        <button
          type="button"
          class="px-6 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500"
          @click="emit('close')"
        >
          Volver a editar
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-2 px-6 py-2 text-white bg-green-600 rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          @click="emit('confirm')"
        >
          <CheckIcon class="h-5 w-5" />
          Confirmar y Emitir
        </button>
      </div>
    </div>
  </div>
</template>
