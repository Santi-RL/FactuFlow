<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Certificado } from '@/types/certificado'
import certificadosService from '@/services/certificados.service'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'

const route = useRoute()
const router = useRouter()

const certificado = ref<Certificado | null>(null)
const loading = ref(true)

const formatearCUIT = (cuit: string) => {
  return `${cuit.slice(0, 2)}-${cuit.slice(2, 10)}-${cuit.slice(10)}`
}

const formatearFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

const irADashboard = () => {
  router.push({ name: 'dashboard' })
}

const irACertificados = () => {
  router.push({ name: 'certificados' })
}

onMounted(async () => {
  const id = route.params.id
  if (id) {
    try {
      certificado.value = await certificadosService.obtener(Number(id))
    } catch (err) {
      console.error(err)
    }
  }
  loading.value = false
})
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <div v-if="loading" class="flex justify-center py-12">
      <BaseSpinner size="lg" />
    </div>
    
    <div v-else class="max-w-2xl mx-auto">
      <!-- Success Icon -->
      <div class="text-center mb-8">
        <div class="text-8xl mb-4">🎉</div>
        <h1 class="text-4xl font-bold text-gray-900 mb-2">
          ¡Felicitaciones!
        </h1>
        <p class="text-xl text-gray-600">
          Tu certificado ARCA está configurado correctamente
        </p>
      </div>
      
      <!-- Info Card -->
      <div class="bg-white rounded-lg shadow-md border border-gray-200 p-8 mb-8">
        <p class="text-gray-700 text-center mb-6">
          Ya podés empezar a emitir facturas electrónicas.
        </p>
        
        <div v-if="certificado" class="bg-gray-50 rounded-lg p-6 mb-6">
          <h3 class="font-semibold text-gray-900 mb-4">📋 Resumen:</h3>
          
          <dl class="space-y-3">
            <div class="flex justify-between">
              <dt class="text-gray-600">CUIT:</dt>
              <dd class="font-medium text-gray-900">{{ formatearCUIT(certificado.cuit) }}</dd>
            </div>
            
            <div class="flex justify-between">
              <dt class="text-gray-600">Ambiente:</dt>
              <dd class="font-medium text-gray-900">
                {{ certificado.ambiente === 'produccion' ? 'Producción' : 'Homologación' }}
              </dd>
            </div>
            
            <div class="flex justify-between">
              <dt class="text-gray-600">Válido hasta:</dt>
              <dd class="font-medium text-gray-900">
                {{ formatearFecha(certificado.fecha_vencimiento) }}
              </dd>
            </div>
          </dl>
        </div>
        
        <div class="bg-blue-50 border-l-4 border-blue-500 p-4">
          <p class="text-sm text-gray-700">
            💡 Te avisaremos cuando el certificado esté por vencer.
          </p>
        </div>
      </div>
      
      <!-- Actions -->
      <div class="flex gap-4 justify-center">
        <BaseButton
          @click="irADashboard"
          variant="primary"
          class="px-6"
        >
          Ir al Dashboard
        </BaseButton>
        
        <BaseButton
          @click="irACertificados"
          variant="secondary"
          class="px-6"
        >
          Ver certificados
        </BaseButton>
      </div>
    </div>
  </div>
</template>
