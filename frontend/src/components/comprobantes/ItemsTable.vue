<script setup lang="ts">
import { PlusIcon } from '@heroicons/vue/24/outline'
import ItemRow from './ItemRow.vue'
import type { ItemComprobante } from '@/types/comprobante'

interface Props {
  items: ItemComprobante[]
}

interface Emits {
  (e: 'update:items', items: ItemComprobante[]): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const agregarItem = () => {
  const nuevoItem: ItemComprobante = {
    codigo: '',
    descripcion: '',
    cantidad: 1,
    unidad: 'unidades',
    precio_unitario: 0,
    descuento_porcentaje: 0,
    iva_porcentaje: 21,
    orden: props.items.length,
  }
  
  emit('update:items', [...props.items, nuevoItem])
}

const actualizarItem = (index: number, item: ItemComprobante) => {
  const nuevosItems = [...props.items]
  nuevosItems[index] = item
  emit('update:items', nuevosItems)
}

const eliminarItem = (index: number) => {
  if (props.items.length <= 1) {
    alert('Debe haber al menos un ítem en el comprobante')
    return
  }
  
  const nuevosItems = props.items.filter((_, i) => i !== index)
  emit('update:items', nuevosItems)
}
</script>

<template>
  <div class="border border-gray-200 rounded-lg overflow-hidden">
    <!-- Header -->
    <div class="bg-gray-50 px-4 py-3 border-b border-gray-200">
      <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2">
        📦 Detalle de Items
      </h3>
    </div>

    <!-- Tabla -->
    <div class="overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-100">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
              Código
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
              Descripción
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
              Cant.
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
              Unidad
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
              Precio Unit.
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase tracking-wider">
              IVA
            </th>
            <th class="px-4 py-3 text-right text-xs font-medium text-gray-700 uppercase tracking-wider">
              Subtotal
            </th>
            <th class="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase tracking-wider">
              Acciones
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <ItemRow
            v-for="(item, index) in items"
            :key="index"
            :item="item"
            :index="index"
            @update:item="(updatedItem) => actualizarItem(index, updatedItem)"
            @remove="eliminarItem(index)"
          />
        </tbody>
      </table>
    </div>

    <!-- Botón agregar -->
    <div class="bg-gray-50 px-4 py-3 border-t border-gray-200">
      <button
        type="button"
        @click="agregarItem"
        class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-300 rounded-md hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <PlusIcon class="h-5 w-5" />
        Agregar ítem
      </button>
    </div>

    <!-- Mensaje si no hay items -->
    <div v-if="items.length === 0" class="text-center py-8 text-gray-500">
      <p>No hay ítems. Agregue al menos uno para continuar.</p>
    </div>
  </div>
</template>
