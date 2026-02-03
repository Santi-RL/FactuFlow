<script setup lang="ts">
import { ref, computed } from 'vue'
import type { GenerarCSRRequest, GenerarCSRResponse } from '@/types/certificado'
import certificadosService from '@/services/certificados.service'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseAlert from '@/components/ui/BaseAlert.vue'

interface Emits {
  (e: 'next', data: { keyFilename: string; cuit: string; nombre: string; ambiente: string }): void
  (e: 'prev'): void
}

const emit = defineEmits<Emits>()

const cuit = ref('')
const nombreEmpresa = ref('')
const ambiente = ref<'homologacion' | 'produccion'>('homologacion')
const loading = ref(false)
const error = ref('')
const csrGenerado = ref(false)
const csrData = ref<GenerarCSRResponse | null>(null)

const ambienteOptions = [
  { value: 'homologacion', label: 'Homologación (Pruebas)' },
  { value: 'produccion', label: 'Producción (Real)' }
]

const formatearCUIT = (valor: string) => {
  // Remover todo excepto números
  const numeros = valor.replace(/\D/g, '')
  
  // Limitar a 11 dígitos
  const cuitLimpio = numeros.slice(0, 11)
  
  // Formatear con guiones si tiene suficientes dígitos
  if (cuitLimpio.length <= 2) {
    return cuitLimpio
  } else if (cuitLimpio.length <= 10) {
    return `${cuitLimpio.slice(0, 2)}-${cuitLimpio.slice(2)}`
  } else {
    return `${cuitLimpio.slice(0, 2)}-${cuitLimpio.slice(2, 10)}-${cuitLimpio.slice(10)}`
  }
}

const onCuitInput = (event: Event) => {
  const input = event.target as HTMLInputElement
  const formatted = formatearCUIT(input.value)
  cuit.value = formatted
}

const cuitSinFormato = computed(() => {
  return cuit.value.replace(/\D/g, '')
})

const formularioValido = computed(() => {
  return cuitSinFormato.value.length === 11 && nombreEmpresa.value.trim().length > 0
})

const generarCSR = async () => {
  if (!formularioValido.value) return
  
  loading.value = true
  error.value = ''
  
  try {
    const request: GenerarCSRRequest = {
      cuit: cuitSinFormato.value,
      nombre_empresa: nombreEmpresa.value.trim(),
      ambiente: ambiente.value
    }
    
    const response = await certificadosService.generarCSR(request)
    csrData.value = response
    
    // Descargar CSR automáticamente
    certificadosService.descargarCSR(response.csr, cuitSinFormato.value)
    
    csrGenerado.value = true
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Error al generar CSR. Por favor, intentá nuevamente.'
  } finally {
    loading.value = false
  }
}

const continuar = () => {
  if (!csrData.value) return
  
  emit('next', {
    keyFilename: csrData.value.key_filename,
    cuit: cuitSinFormato.value,
    nombre: nombreEmpresa.value.trim(),
    ambiente: ambiente.value
  })
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">
      Generación de clave privada y solicitud
    </h2>
    
    <div class="bg-blue-50 border-l-4 border-blue-500 p-6 mb-6">
      <p class="text-gray-700 mb-4">
        Primero vamos a generar dos archivos importantes:
      </p>
      
      <div class="space-y-3">
        <div class="flex gap-3">
          <span class="text-2xl">🔑</span>
          <div>
            <p class="font-semibold text-gray-900">Clave Privada (.key)</p>
            <p class="text-sm text-gray-600">
              Es tu "contraseña secreta". <strong>NUNCA</strong> la compartas con nadie.
            </p>
          </div>
        </div>
        
        <div class="flex gap-3">
          <span class="text-2xl">📄</span>
          <div>
            <p class="font-semibold text-gray-900">Solicitud de Certificado (.csr)</p>
            <p class="text-sm text-gray-600">
              Es lo que vas a subir al portal de ARCA para obtener tu certificado.
            </p>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="!csrGenerado" class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6">
      <BaseAlert v-if="error" type="error" class="mb-4">
        {{ error }}
      </BaseAlert>
      
      <form @submit.prevent="generarCSR" class="space-y-4">
        <BaseInput
          v-model="cuit"
          label="CUIT"
          placeholder="XX-XXXXXXXX-X"
          required
          :maxlength="13"
          @input="onCuitInput"
        />
        
        <BaseInput
          v-model="nombreEmpresa"
          label="Nombre de la empresa/persona"
          placeholder="Mi Empresa S.A."
          required
          :maxlength="255"
        />
        
        <BaseSelect
          v-model="ambiente"
          label="Ambiente"
          :options="ambienteOptions"
          required
        >
          <template #help>
            <p class="text-sm text-gray-600 mt-1">
              <strong>Homologación:</strong> Para pruebas (recomendado para comenzar)<br>
              <strong>Producción:</strong> Para facturación real
            </p>
          </template>
        </BaseSelect>
        
        <div class="pt-4">
          <BaseButton
            type="submit"
            variant="primary"
            :loading="loading"
            :disabled="!formularioValido"
            class="w-full"
          >
            <span v-if="!loading">🔐 Generar automáticamente</span>
            <span v-else>Generando...</span>
          </BaseButton>
        </div>
      </form>
    </div>
    
    <div v-else class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6">
      <BaseAlert type="success" class="mb-4">
        <p class="font-semibold mb-2">✅ CSR generado exitosamente</p>
        <p class="text-sm">
          El archivo de solicitud (.csr) se descargó automáticamente.
          Guardá este archivo, lo vas a necesitar en el siguiente paso.
        </p>
      </BaseAlert>
      
      <div class="bg-yellow-50 border-l-4 border-yellow-500 p-4">
        <p class="font-semibold text-gray-900 mb-2">⚠️ IMPORTANTE</p>
        <p class="text-sm text-gray-700">
          La clave privada (.key) se guardó de forma segura en el servidor.
          No la pierdas, ya que la vas a necesitar para usar el certificado.
        </p>
      </div>
    </div>
    
    <div class="flex justify-between">
      <BaseButton
        @click="emit('prev')"
        variant="secondary"
      >
        ← Anterior
      </BaseButton>
      
      <BaseButton
        v-if="csrGenerado"
        @click="continuar"
        variant="primary"
      >
        Siguiente →
      </BaseButton>
    </div>
  </div>
</template>
