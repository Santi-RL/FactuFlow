<script setup lang="ts">
import { computed } from 'vue'
import type { Certificado } from '@/types/certificado'
import CertificadoEstado from './CertificadoEstado.vue'

interface Props {
  certificado: Certificado
}

interface Emits {
  (e: 'renovar', id: number): void
  (e: 'eliminar', id: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const porcentajeVida = computed(() => {
  const fechaEmision = new Date(props.certificado.fecha_emision)
  const fechaVencimiento = new Date(props.certificado.fecha_vencimiento)
  const hoy = new Date()
  
  const totalDias = Math.floor((fechaVencimiento.getTime() - fechaEmision.getTime()) / (1000 * 60 * 60 * 24))
  const diasTranscurridos = Math.floor((hoy.getTime() - fechaEmision.getTime()) / (1000 * 60 * 60 * 24))
  
  const porcentaje = Math.max(0, Math.min(100, ((totalDias - diasTranscurridos) / totalDias) * 100))
  
  return Math.round(porcentaje)
})

const barraColorClasses = computed(() => {
  if (props.certificado.estado === 'vencido') {
    return 'bg-red-500'
  } else if (props.certificado.estado === 'por_vencer') {
    return 'bg-yellow-500'
  }
  return 'bg-green-500'
})

const formatearFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

const formatearCUIT = (cuit: string) => {
  // Formato: XX-XXXXXXXX-X
  return `${cuit.slice(0, 2)}-${cuit.slice(2, 10)}-${cuit.slice(10)}`
}

const nombreAmbiente = computed(() => {
  return props.certificado.ambiente === 'produccion' ? 'Producción' : 'Homologación'
})
</script>

<template>
  <div class="bg-white rounded-lg shadow-md border border-gray-200 p-6 hover:shadow-lg transition-shadow">
    <!-- Header -->
    <div class="flex items-start justify-between mb-4">
      <div class="flex items-center gap-3">
        <div class="text-3xl">
          🔐
        </div>
        <div>
          <h3 class="text-lg font-semibold text-gray-900">
            {{ certificado.nombre }}
          </h3>
          <CertificadoEstado
            :estado="certificado.estado"
            :dias-restantes="certificado.dias_restantes"
            class="mt-1"
          />
        </div>
      </div>
      
      <div
        v-if="certificado.estado === 'por_vencer' || certificado.estado === 'vencido'"
        class="text-2xl"
      >
        ⚠️
      </div>
    </div>
    
    <!-- Info -->
    <div class="space-y-2 mb-4 text-sm">
      <div class="flex justify-between">
        <span class="text-gray-600">CUIT:</span>
        <span class="font-medium">{{ formatearCUIT(certificado.cuit) }}</span>
      </div>
      
      <div class="flex justify-between">
        <span class="text-gray-600">Ambiente:</span>
        <span class="font-medium">{{ nombreAmbiente }}</span>
      </div>
      
      <div class="flex justify-between">
        <span class="text-gray-600">Vence:</span>
        <span class="font-medium">{{ formatearFecha(certificado.fecha_vencimiento) }}</span>
      </div>
    </div>
    
    <!-- Progress Bar -->
    <div class="mb-4">
      <div class="flex justify-between text-xs text-gray-600 mb-1">
        <span>{{ porcentajeVida }}% válido</span>
        <span>{{ certificado.dias_restantes }} días restantes</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div
          class="h-2 rounded-full transition-all duration-300"
          :class="barraColorClasses"
          :style="{ width: `${porcentajeVida}%` }"
        />
      </div>
    </div>
    
    <!-- Actions -->
    <div class="flex gap-2">
      <button
        v-if="certificado.estado === 'por_vencer' || certificado.estado === 'vencido'"
        class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors font-medium text-sm"
        @click="emit('renovar', certificado.id)"
      >
        Renovar
      </button>
      
      <button
        class="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors font-medium text-sm"
        @click="emit('eliminar', certificado.id)"
      >
        Eliminar
      </button>
    </div>
  </div>
</template>
