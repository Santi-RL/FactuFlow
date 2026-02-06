<script setup lang="ts">
import { ref, computed } from 'vue'
import { MagnifyingGlassIcon, UserPlusIcon } from '@heroicons/vue/24/outline'
import { useClientesStore } from '@/stores/clientes'
import { TIPOS_DOCUMENTO_NOMBRES, CONDICIONES_IVA } from '@/types/comprobante'

interface ClienteData {
  cliente_id?: number
  tipo_documento: number
  numero_documento: string
  razon_social: string
  condicion_iva: string
  domicilio?: string
}

interface Props {
  modelValue: ClienteData
  empresaId: number
  tipoComprobante: number
}

interface Emits {
  (e: 'update:modelValue', value: ClienteData): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const clientesStore = useClientesStore()

const busqueda = ref('')
const mostrarResultados = ref(false)
const modoManual = ref(false)

const tipoDocumentoToCodigo: Record<string, number> = {
  CUIT: 80,
  CUIL: 86,
  DNI: 96,
  Pasaporte: 94,
  LE: 89,
  LC: 90,
  CI: 99,
}

const mapTipoDocumento = (tipo?: string) => {
  if (!tipo) return 99
  return tipoDocumentoToCodigo[tipo] ?? 99
}

// Buscar clientes
const buscarClientes = async () => {
  if (busqueda.value.length < 2) return
  
  await clientesStore.fetchClientes({
    empresa_id: props.empresaId,
    search: busqueda.value,
    page: 1,
    per_page: 10,
  })
  
  mostrarResultados.value = true
}

// Seleccionar cliente
const seleccionarCliente = (cliente: any) => {
  emit('update:modelValue', {
    cliente_id: cliente.id,
    tipo_documento: mapTipoDocumento(cliente.tipo_documento),
    numero_documento: cliente.numero_documento || '',
    razon_social: cliente.razon_social,
    condicion_iva: cliente.condicion_iva,
    domicilio: cliente.domicilio ?? undefined,
  })
  
  mostrarResultados.value = false
  busqueda.value = cliente.razon_social
}

// Activar modo manual
const activarModoManual = () => {
  modoManual.value = true
  mostrarResultados.value = false
}

// Actualizar campo
const updateField = (field: keyof ClienteData, value: any) => {
  emit('update:modelValue', {
    ...props.modelValue,
    [field]: value,
  })
}

// Validar según tipo de comprobante
const requiereCUIT = computed(() => {
  // Facturas A requieren CUIT
  return [1, 2, 3].includes(props.tipoComprobante)
})

// Watch para cerrar resultados al hacer clic fuera
const cerrarResultados = () => {
  setTimeout(() => {
    mostrarResultados.value = false
  }, 200)
}
</script>

<template>
  <div class="border border-gray-200 rounded-lg p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2">
        👤 Cliente / Receptor
      </h3>
      <button
        v-if="!modoManual"
        type="button"
        data-testid="cliente-nuevo-manual"
        class="inline-flex items-center gap-2 px-3 py-1 text-sm font-medium text-green-700 bg-green-50 border border-green-300 rounded-md hover:bg-green-100"
        @click="activarModoManual"
      >
        <UserPlusIcon class="h-4 w-4" />
        Nuevo cliente
      </button>
    </div>

    <!-- Búsqueda de cliente -->
    <div
      v-if="!modoManual && !modelValue.cliente_id"
      class="mb-6"
    >
      <label
        for="cliente-busqueda"
        class="block text-sm font-medium text-gray-700 mb-2"
      >
        Buscar cliente por nombre o CUIT
      </label>
      <div class="relative">
        <div class="relative">
          <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            id="cliente-busqueda"
            v-model="busqueda"
            type="text"
            placeholder="Buscar cliente..."
            class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            @input="buscarClientes"
            @blur="cerrarResultados"
          >
        </div>

        <!-- Resultados de búsqueda -->
        <div
          v-if="mostrarResultados && clientesStore.clientes.length > 0"
          class="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto"
        >
          <button
            v-for="cliente in clientesStore.clientes"
            :key="cliente.id"
            type="button"
            class="w-full px-4 py-3 text-left hover:bg-gray-50 border-b last:border-b-0"
            @click="seleccionarCliente(cliente)"
          >
            <div class="font-medium text-gray-900">
              {{ cliente.razon_social }}
            </div>
            <div class="text-sm text-gray-500">
              {{ cliente.numero_documento }} - {{ cliente.condicion_iva }}
            </div>
          </button>
        </div>

        <!-- Sin resultados -->
        <div
          v-if="mostrarResultados && clientesStore.clientes.length === 0"
          class="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg p-4 text-center text-gray-500"
        >
          No se encontraron clientes
        </div>
      </div>
    </div>

    <!-- Separador -->
    <div
      v-if="!modoManual && !modelValue.cliente_id"
      class="relative mb-6"
    >
      <div class="absolute inset-0 flex items-center">
        <div class="w-full border-t border-gray-300" />
      </div>
      <div class="relative flex justify-center text-sm">
        <span class="px-2 bg-white text-gray-500">O completar datos manualmente</span>
      </div>
    </div>

    <!-- Cliente seleccionado -->
    <div
      v-if="modelValue.cliente_id && !modoManual"
      class="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg"
    >
      <div class="flex items-center justify-between">
        <div>
          <div class="font-medium text-gray-900">
            {{ modelValue.razon_social }}
          </div>
          <div class="text-sm text-gray-600">
            {{ modelValue.numero_documento }} - {{ modelValue.condicion_iva }}
          </div>
        </div>
        <button
          type="button"
          class="text-sm text-blue-600 hover:text-blue-700"
          @click="emit('update:modelValue', { tipo_documento: 80, numero_documento: '', razon_social: '', condicion_iva: '' }); modoManual = true"
        >
          Cambiar
        </button>
      </div>
    </div>

    <!-- Formulario manual -->
    <div
      v-if="modoManual || modelValue.cliente_id"
      class="space-y-4"
    >
      <!-- Tipo de documento y número -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label
            for="cliente-tipo-documento"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            Tipo Documento *
          </label>
          <select
            id="cliente-tipo-documento"
            :value="modelValue.tipo_documento"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            @change="updateField('tipo_documento', parseInt(($event.target as HTMLSelectElement).value))"
          >
            <option :value="80">
              {{ TIPOS_DOCUMENTO_NOMBRES[80] }}
            </option>
            <option :value="96">
              {{ TIPOS_DOCUMENTO_NOMBRES[96] }}
            </option>
            <option :value="94">
              {{ TIPOS_DOCUMENTO_NOMBRES[94] }}
            </option>
            <option
              v-if="!requiereCUIT"
              :value="99"
            >
              {{ TIPOS_DOCUMENTO_NOMBRES[99] }}
            </option>
          </select>
        </div>

        <div class="md:col-span-2">
          <label
            for="cliente-numero-documento"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            Número *
          </label>
          <input
            id="cliente-numero-documento"
            type="text"
            :value="modelValue.numero_documento"
            placeholder="20-12345678-9"
            required
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            @input="updateField('numero_documento', ($event.target as HTMLInputElement).value)"
          >
          <p
            v-if="requiereCUIT"
            class="mt-1 text-xs text-amber-600"
          >
            * Para comprobantes tipo A, el receptor debe tener CUIT
          </p>
        </div>
      </div>

      <!-- Condición IVA -->
      <div>
        <label
          for="cliente-condicion-iva"
          class="block text-sm font-medium text-gray-700 mb-1"
        >
          Condición IVA *
        </label>
        <select
          id="cliente-condicion-iva"
          :value="modelValue.condicion_iva"
          required
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          @change="updateField('condicion_iva', ($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            Seleccione...
          </option>
          <option
            v-for="condicion in CONDICIONES_IVA"
            :key="condicion"
            :value="condicion"
          >
            {{ condicion }}
          </option>
        </select>
      </div>

      <!-- Razón Social -->
      <div>
        <label
          for="cliente-razon-social"
          class="block text-sm font-medium text-gray-700 mb-1"
        >
          Razón Social / Nombre *
        </label>
        <input
          id="cliente-razon-social"
          type="text"
          :value="modelValue.razon_social"
          placeholder="Empresa Ejemplo S.A."
          required
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          @input="updateField('razon_social', ($event.target as HTMLInputElement).value)"
        >
      </div>

      <!-- Domicilio -->
      <div>
        <label
          for="cliente-domicilio"
          class="block text-sm font-medium text-gray-700 mb-1"
        >
          Domicilio (opcional)
        </label>
        <input
          id="cliente-domicilio"
          type="text"
          :value="modelValue.domicilio"
          placeholder="Av. Corrientes 1234, CABA"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          @input="updateField('domicilio', ($event.target as HTMLInputElement).value)"
        >
      </div>
    </div>
  </div>
</template>
