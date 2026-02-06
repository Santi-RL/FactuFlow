<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Certificado } from '@/types/certificado'
import certificadosService from '@/services/certificados.service'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseAlert from '@/components/ui/BaseAlert.vue'

interface Props {
  cuit: string
  nombre: string
  ambiente: string
  keyFilename: string
}

interface Emits {
  (e: 'next', certificado: Certificado): void
  (e: 'prev'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const file = ref<File | null>(null)
const dragActive = ref(false)
const loading = ref(false)
const error = ref('')
const certificadoSubido = ref<Certificado | null>(null)

const fileInputRef = ref<HTMLInputElement>()

const certificadoInfo = computed(() => {
  if (!certificadoSubido.value) return null
  
  const cert = certificadoSubido.value
  const fechaEmision = new Date(cert.fecha_emision).toLocaleDateString('es-AR')
  const fechaVencimiento = new Date(cert.fecha_vencimiento).toLocaleDateString('es-AR')
  
  return {
    cuit: `${cert.cuit.slice(0, 2)}-${cert.cuit.slice(2, 10)}-${cert.cuit.slice(10)}`,
    fechaEmision,
    fechaVencimiento,
    diasRestantes: cert.dias_restantes
  }
})

const onFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    file.value = input.files[0]
    subirCertificado()
  }
}

const onDrop = (event: DragEvent) => {
  dragActive.value = false
  
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    file.value = event.dataTransfer.files[0]
    subirCertificado()
  }
}

const onDragOver = (event: DragEvent) => {
  event.preventDefault()
  dragActive.value = true
}

const onDragLeave = () => {
  dragActive.value = false
}

const selectFile = () => {
  fileInputRef.value?.click()
}

const subirCertificado = async () => {
  if (!file.value) return
  
  // Validar extensión
  const extension = file.value.name.split('.').pop()?.toLowerCase()
  if (!extension || !['crt', 'cer', 'pem'].includes(extension)) {
    error.value = 'Formato de archivo inválido. Se acepta .crt, .cer o .pem'
    file.value = null
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    const certificado = await certificadosService.subirCertificado(
      file.value,
      props.cuit,
      props.nombre,
      props.ambiente,
      props.keyFilename
    )
    
    certificadoSubido.value = certificado
  } catch (err: any) {
    const detail = err.response?.data?.detail
    
    if (typeof detail === 'string') {
      error.value = detail
    } else {
      error.value = 'Error al subir el certificado. Por favor, verificá que sea el archivo correcto.'
    }
    
    file.value = null
  } finally {
    loading.value = false
  }
}

const continuar = () => {
  if (certificadoSubido.value) {
    emit('next', certificadoSubido.value)
  }
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">
      Subí tu certificado
    </h2>

    <BaseAlert
      type="info"
      class="mb-6"
    >
      Usando clave privada: <span class="font-mono">{{ props.keyFilename }}</span>
    </BaseAlert>
    
    <div
      v-if="!certificadoSubido"
      class="mb-6"
    >
      <BaseAlert
        v-if="error"
        type="error"
        class="mb-4"
      >
        {{ error }}
      </BaseAlert>
      
      <div
        class="bg-white rounded-lg shadow-md border-2 border-dashed p-12 text-center cursor-pointer transition-all"
        :class="{
          'border-blue-400 bg-blue-50': dragActive && !loading,
          'border-gray-300 hover:border-gray-400 hover:bg-gray-50': !dragActive && !loading,
          'border-gray-200 bg-gray-50 cursor-not-allowed': loading
        }"
        @drop.prevent="onDrop"
        @dragover.prevent="onDragOver"
        @dragleave="onDragLeave"
        @click="selectFile"
      >
        <input
          ref="fileInputRef"
          type="file"
          data-testid="cert-wizard-file"
          accept=".crt,.cer,.pem"
          class="hidden"
          :disabled="loading"
          @change="onFileSelect"
        >
        
        <div
          v-if="!loading"
          class="space-y-4"
        >
          <div class="text-6xl">
            📄
          </div>
          <div>
            <p class="text-lg font-semibold text-gray-900 mb-2">
              Arrastrá el archivo .crt aquí
            </p>
            <p class="text-gray-600">
              o hacé clic para seleccionar
            </p>
          </div>
          <p class="text-sm text-gray-500">
            Formatos aceptados: .crt, .cer, .pem
          </p>
        </div>
        
        <div
          v-else
          class="space-y-4"
        >
          <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
          <p class="text-lg font-semibold text-gray-900">
            Validando certificado...
          </p>
        </div>
      </div>
    </div>
    
    <div
      v-else
      class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6"
    >
      <BaseAlert
        type="success"
        class="mb-6"
      >
        <p class="font-semibold mb-1">
          ✅ Certificado cargado correctamente
        </p>
      </BaseAlert>
      
      <div class="bg-gray-50 rounded-lg p-6">
        <h3 class="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <span>📋</span>
          <span>Información del certificado:</span>
        </h3>
        
        <dl class="space-y-3">
          <div class="flex justify-between">
            <dt class="text-gray-600">
              CUIT:
            </dt>
            <dd class="font-medium text-gray-900">
              {{ certificadoInfo?.cuit }}
            </dd>
          </div>
          
          <div class="flex justify-between">
            <dt class="text-gray-600">
              Emitido:
            </dt>
            <dd class="font-medium text-gray-900">
              {{ certificadoInfo?.fechaEmision }}
            </dd>
          </div>
          
          <div class="flex justify-between">
            <dt class="text-gray-600">
              Vence:
            </dt>
            <dd class="font-medium text-gray-900">
              {{ certificadoInfo?.fechaVencimiento }}
            </dd>
          </div>
          
          <div class="flex justify-between">
            <dt class="text-gray-600">
              Días restantes:
            </dt>
            <dd class="font-medium text-green-600">
              {{ certificadoInfo?.diasRestantes }} días
            </dd>
          </div>
        </dl>
      </div>
    </div>
    
    <div class="flex justify-between">
      <BaseButton
        variant="secondary"
        :disabled="loading"
        @click="emit('prev')"
      >
        ← Anterior
      </BaseButton>
      
      <BaseButton
        v-if="certificadoSubido"
        variant="primary"
        data-testid="cert-wizard-step4-next"
        @click="continuar"
      >
        Siguiente →
      </BaseButton>
    </div>
  </div>
</template>
