<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useEmpresaStore } from '@/stores/empresa'
import { useComprobantesStore } from '@/stores/comprobantes'
import { DocumentTextIcon, EyeIcon, PaperAirplaneIcon } from '@heroicons/vue/24/outline'
import BaseCard from '@/components/ui/BaseCard.vue'
import ClienteSelector from '@/components/comprobantes/ClienteSelector.vue'
import ItemsTable from '@/components/comprobantes/ItemsTable.vue'
import TotalesPanel from '@/components/comprobantes/TotalesPanel.vue'
import ComprobantePreview from '@/components/comprobantes/ComprobantePreview.vue'
import type { ItemComprobante, EmitirComprobanteRequest } from '@/types/comprobante'
import {
  TIPOS_COMPROBANTE,
  TIPOS_COMPROBANTE_NOMBRES,
  TIPOS_CONCEPTO,
  TIPOS_CONCEPTO_NOMBRES,
} from '@/types/comprobante'

const router = useRouter()
const empresaStore = useEmpresaStore()
const comprobantesStore = useComprobantesStore()

// Estado del formulario
const formData = ref({
  tipo_comprobante: TIPOS_COMPROBANTE.FACTURA_B,
  punto_venta_id: 0,
  concepto: TIPOS_CONCEPTO.PRODUCTOS,
  
  // Cliente
  cliente: {
    cliente_id: undefined as number | undefined,
    tipo_documento: 80,
    numero_documento: '',
    razon_social: '',
    condicion_iva: '',
    domicilio: '',
  },
  
  // Items
  items: [] as ItemComprobante[],
  
  // Servicios
  fecha_servicio_desde: '',
  fecha_servicio_hasta: '',
  fecha_vto_pago: '',
  
  // Observaciones
  observaciones: '',
})

// Estados
const loading = ref(false)
const mostrarPreview = ref(false)
const proximoNumero = ref<number | null>(null)
const puntosVenta = ref<any[]>([])

// Inicializar datos
onMounted(async () => {
  // Cargar empresa si no está cargada
  if (!empresaStore.empresa) {
    await empresaStore.cargarEmpresa()
  }
  
  // Cargar puntos de venta
  // TODO: Implementar endpoint de puntos de venta
  puntosVenta.value = [
    { id: 1, numero: 1, descripcion: 'Punto de Venta 1' }
  ]
  
  if (puntosVenta.value.length > 0) {
    formData.value.punto_venta_id = puntosVenta.value[0].id
  }
  
  // Agregar primer item vacío
  if (formData.value.items.length === 0) {
    formData.value.items.push({
      codigo: '',
      descripcion: '',
      cantidad: 1,
      unidad: 'unidades',
      precio_unitario: 0,
      descuento_porcentaje: 0,
      iva_porcentaje: 21,
      orden: 0,
    })
  }
  
  // Obtener próximo número
  await actualizarProximoNumero()
})

// Computed
const empresaId = computed(() => empresaStore.empresa?.id || 0)

const tiposComprobanteDisponibles = computed(() => {
  // TODO: Filtrar según configuración de empresa
  return [
    { value: TIPOS_COMPROBANTE.FACTURA_A, label: TIPOS_COMPROBANTE_NOMBRES[1] },
    { value: TIPOS_COMPROBANTE.FACTURA_B, label: TIPOS_COMPROBANTE_NOMBRES[6] },
    { value: TIPOS_COMPROBANTE.FACTURA_C, label: TIPOS_COMPROBANTE_NOMBRES[11] },
  ]
})

const mostrarFechasServicios = computed(() => {
  return formData.value.concepto !== TIPOS_CONCEPTO.PRODUCTOS
})

const totales = computed(() => {
  let subtotal = 0
  let iva21 = 0
  let iva105 = 0
  let iva27 = 0
  
  formData.value.items.forEach(item => {
    const itemSubtotal = item.cantidad * item.precio_unitario * (1 - item.descuento_porcentaje / 100)
    subtotal += itemSubtotal
    
    if (item.iva_porcentaje === 21) {
      iva21 += itemSubtotal * 0.21
    } else if (item.iva_porcentaje === 10.5) {
      iva105 += itemSubtotal * 0.105
    } else if (item.iva_porcentaje === 27) {
      iva27 += itemSubtotal * 0.27
    }
  })
  
  const total = subtotal + iva21 + iva105 + iva27
  
  return {
    subtotal,
    iva21,
    iva105,
    iva27,
    total,
  }
})

const formularioValido = computed(() => {
  return (
    formData.value.punto_venta_id > 0 &&
    formData.value.cliente.numero_documento.length > 0 &&
    formData.value.cliente.razon_social.length > 0 &&
    formData.value.cliente.condicion_iva.length > 0 &&
    formData.value.items.length > 0 &&
    formData.value.items.every(item => 
      item.descripcion.length > 0 && 
      item.cantidad > 0 && 
      item.precio_unitario >= 0
    ) &&
    (!mostrarFechasServicios.value || (
      formData.value.fecha_servicio_desde &&
      formData.value.fecha_servicio_hasta &&
      formData.value.fecha_vto_pago
    ))
  )
})

// Methods
const actualizarProximoNumero = async () => {
  if (!formData.value.punto_venta_id || !empresaId.value) return
  
  try {
    const puntoVenta = puntosVenta.value.find(pv => pv.id === formData.value.punto_venta_id)
    if (!puntoVenta) return
    
    proximoNumero.value = await comprobantesStore.obtenerProximoNumero(
      puntoVenta.numero,
      formData.value.tipo_comprobante,
      empresaId.value
    )
  } catch (error) {
    console.error('Error al obtener próximo número:', error)
  }
}

const abrirVistaPrevia = () => {
  if (!formularioValido.value) {
    alert('Por favor, complete todos los campos requeridos')
    return
  }
  
  mostrarPreview.value = true
}

const confirmarEmision = async () => {
  loading.value = true
  mostrarPreview.value = false
  
  try {
    const request: EmitirComprobanteRequest = {
      empresa_id: empresaId.value,
      punto_venta_id: formData.value.punto_venta_id,
      tipo_comprobante: formData.value.tipo_comprobante,
      concepto: formData.value.concepto,
      
      // Cliente
      cliente_id: formData.value.cliente.cliente_id,
      tipo_documento: formData.value.cliente.tipo_documento,
      numero_documento: formData.value.cliente.numero_documento,
      razon_social: formData.value.cliente.razon_social,
      condicion_iva: formData.value.cliente.condicion_iva,
      domicilio: formData.value.cliente.domicilio,
      
      // Items
      items: formData.value.items,
      
      // Servicios
      fecha_servicio_desde: formData.value.fecha_servicio_desde || undefined,
      fecha_servicio_hasta: formData.value.fecha_servicio_hasta || undefined,
      fecha_vto_pago: formData.value.fecha_vto_pago || undefined,
      
      // Observaciones
      observaciones: formData.value.observaciones || undefined,
      
      // Moneda
      moneda: 'PES',
      cotizacion: 1,
    }
    
    const resultado = await comprobantesStore.emitirComprobante(request)
    
    if (resultado.exito) {
      // Mostrar éxito y redirigir
      alert(`✅ Comprobante emitido exitosamente!\n\nCAE: ${resultado.cae}\nTotal: $${resultado.total.toFixed(2)}`)
      
      // Redirigir al detalle
      if (resultado.comprobante_id) {
        router.push({ name: 'comprobante-detalle', params: { id: resultado.comprobante_id } })
      } else {
        router.push({ name: 'comprobantes' })
      }
    } else {
      // Mostrar error
      alert(`❌ Error al emitir comprobante:\n\n${resultado.mensaje}\n\n${resultado.errores.join('\n')}`)
    }
  } catch (error: any) {
    console.error('Error al emitir:', error)
    alert(`❌ Error al emitir comprobante:\n\n${error.message || 'Error desconocido'}`)
  } finally {
    loading.value = false
  }
}

const cancelar = () => {
  if (confirm('¿Está seguro que desea cancelar? Se perderán todos los cambios.')) {
    router.push({ name: 'comprobantes' })
  }
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900 flex items-center gap-3">
        <DocumentTextIcon class="h-8 w-8" />
        Nueva Factura
      </h1>
      <p class="mt-2 text-gray-600">Complete los datos para emitir un nuevo comprobante electrónico</p>
    </div>

    <form @submit.prevent="abrirVistaPrevia" class="space-y-6">
      <!-- Sección 1: Datos del Comprobante -->
      <BaseCard title="📄 Datos del Comprobante">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Tipo de comprobante -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Tipo de Comprobante *
            </label>
            <select
              v-model="formData.tipo_comprobante"
              @change="actualizarProximoNumero"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option v-for="tipo in tiposComprobanteDisponibles" :key="tipo.value" :value="tipo.value">
                {{ tipo.label }}
              </option>
            </select>
          </div>

          <!-- Punto de venta -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Punto de Venta *
            </label>
            <select
              v-model="formData.punto_venta_id"
              @change="actualizarProximoNumero"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option v-for="pv in puntosVenta" :key="pv.id" :value="pv.id">
                {{ String(pv.numero).padStart(4, '0') }} - {{ pv.descripcion }}
              </option>
            </select>
          </div>

          <!-- Concepto -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Concepto *
            </label>
            <select
              v-model="formData.concepto"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option :value="TIPOS_CONCEPTO.PRODUCTOS">{{ TIPOS_CONCEPTO_NOMBRES[1] }}</option>
              <option :value="TIPOS_CONCEPTO.SERVICIOS">{{ TIPOS_CONCEPTO_NOMBRES[2] }}</option>
              <option :value="TIPOS_CONCEPTO.PRODUCTOS_Y_SERVICIOS">{{ TIPOS_CONCEPTO_NOMBRES[3] }}</option>
            </select>
          </div>
        </div>

        <!-- Próximo número -->
        <div v-if="proximoNumero !== null" class="mt-4 text-sm text-gray-600">
          El próximo número será: <span class="font-mono font-semibold">{{ String(proximoNumero).padStart(8, '0') }}</span>
        </div>

        <!-- Fechas de servicios -->
        <div v-if="mostrarFechasServicios" class="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Fecha Servicio Desde *
            </label>
            <input
              v-model="formData.fecha_servicio_desde"
              type="date"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Fecha Servicio Hasta *
            </label>
            <input
              v-model="formData.fecha_servicio_hasta"
              type="date"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Fecha Vto. Pago *
            </label>
            <input
              v-model="formData.fecha_vto_pago"
              type="date"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
      </BaseCard>

      <!-- Sección 2: Cliente -->
      <ClienteSelector
        v-model="formData.cliente"
        :empresa-id="empresaId"
        :tipo-comprobante="formData.tipo_comprobante"
      />

      <!-- Sección 3: Items -->
      <ItemsTable
        :items="formData.items"
        @update:items="formData.items = $event"
      />

      <!-- Sección 4: Totales -->
      <BaseCard title="💰 Totales">
        <TotalesPanel
          :subtotal="totales.subtotal"
          :iva21="totales.iva21"
          :iva105="totales.iva105"
          :iva27="totales.iva27"
          :total="totales.total"
        />
      </BaseCard>

      <!-- Sección 5: Observaciones -->
      <BaseCard title="📝 Observaciones">
        <textarea
          v-model="formData.observaciones"
          rows="3"
          placeholder="Observaciones adicionales (opcional)"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        ></textarea>
      </BaseCard>

      <!-- Botones de acción -->
      <div class="flex items-center justify-end gap-4">
        <button
          type="button"
          @click="cancelar"
          class="px-6 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500"
        >
          Cancelar
        </button>

        <button
          type="button"
          @click="abrirVistaPrevia"
          :disabled="!formularioValido"
          class="inline-flex items-center gap-2 px-6 py-2 text-blue-700 bg-blue-50 border border-blue-300 rounded-lg hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <EyeIcon class="h-5 w-5" />
          Vista Previa
        </button>

        <button
          type="submit"
          :disabled="!formularioValido || loading"
          class="inline-flex items-center gap-2 px-6 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <PaperAirplaneIcon class="h-5 w-5" />
          {{ loading ? 'Emitiendo...' : 'Emitir Factura' }}
        </button>
      </div>
    </form>

    <!-- Modal de vista previa -->
    <ComprobantePreview
      v-if="mostrarPreview"
      :form-data="formData"
      :totales="totales"
      :proximo-numero="proximoNumero"
      :empresa="empresaStore.empresa"
      @close="mostrarPreview = false"
      @confirm="confirmarEmision"
    />
  </div>
</template>
