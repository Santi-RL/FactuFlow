<script setup lang="ts">
import { ref, computed, watch } from 'vue'
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
const usarCSRExistente = ref(false)
const keyFilename = ref('')
const clavesDisponibles = ref<string[]>([])
const loadingClaves = ref(false)
const errorClaves = ref('')
const claveCopiada = ref(false)

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

const formularioManualValido = computed(() => {
  return formularioValido.value && keyFilename.value.trim().length > 0
})

const puedeContinuar = computed(() => {
  return usarCSRExistente.value ? formularioManualValido.value : csrGenerado.value
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

const cargarClaves = async () => {
  if (cuitSinFormato.value.length !== 11) {
    errorClaves.value = 'Ingresá un CUIT válido para buscar claves'
    return
  }
  
  loadingClaves.value = true
  errorClaves.value = ''
  
  try {
    const claves = await certificadosService.listarClaves(
      cuitSinFormato.value,
      ambiente.value
    )
    clavesDisponibles.value = claves
    
    if (claves.length === 1) {
      keyFilename.value = claves[0]
    }
    
    if (claves.length === 0) {
      errorClaves.value = 'No se encontraron claves para este CUIT y ambiente'
    }
  } catch (err: any) {
    errorClaves.value = err.response?.data?.detail || 'No se pudieron listar las claves'
  } finally {
    loadingClaves.value = false
  }
}

const continuar = () => {
  if (usarCSRExistente.value) {
    if (!formularioManualValido.value) return
    emit('next', {
      keyFilename: keyFilename.value.trim(),
      cuit: cuitSinFormato.value,
      nombre: nombreEmpresa.value.trim(),
      ambiente: ambiente.value
    })
    return
  }

  if (!csrData.value) return
  
  emit('next', {
    keyFilename: csrData.value.key_filename,
    cuit: cuitSinFormato.value,
    nombre: nombreEmpresa.value.trim(),
    ambiente: ambiente.value
  })
}

const copiarClave = async () => {
  if (!csrData.value) return
  try {
    await navigator.clipboard.writeText(csrData.value.key_filename)
    claveCopiada.value = true
    setTimeout(() => {
      claveCopiada.value = false
    }, 2000)
  } catch {
    // Silenciar error si no se puede copiar
  }
}

watch(usarCSRExistente, (value) => {
  error.value = ''
  errorClaves.value = ''
  if (!value) {
    keyFilename.value = ''
    clavesDisponibles.value = []
  }
})

watch([cuitSinFormato, ambiente], () => {
  if (usarCSRExistente.value) {
    keyFilename.value = ''
    clavesDisponibles.value = []
    errorClaves.value = ''
  }
})
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
            <p class="font-semibold text-gray-900">
              Clave Privada (.key)
            </p>
            <p class="text-sm text-gray-600">
              Es tu "contraseña secreta". <strong>NUNCA</strong> la compartas con nadie.
            </p>
          </div>
        </div>
        
        <div class="flex gap-3">
          <span class="text-2xl">📄</span>
          <div>
            <p class="font-semibold text-gray-900">
              Solicitud de Certificado (.csr)
            </p>
            <p class="text-sm text-gray-600">
              Es lo que vas a subir al portal de ARCA para obtener tu certificado.
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6">
      <label class="flex items-start gap-3 cursor-pointer">
        <input
          v-model="usarCSRExistente"
          type="checkbox"
          class="mt-1 w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
        >
        <span class="text-gray-700">
          Ya tengo el CSR generado y quiero continuar sin volver a crearlo
        </span>
      </label>
      <p class="text-sm text-gray-600 mt-2">
        Si ya generaste el CSR desde este sistema, podés usar la clave privada existente.
      </p>
    </div>
    
    <div
      v-if="!usarCSRExistente && !csrGenerado"
      class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6"
    >
      <BaseAlert
        v-if="error"
        type="error"
        class="mb-4"
      >
        {{ error }}
      </BaseAlert>
      
      <form
        class="space-y-4"
        @submit.prevent="generarCSR"
      >
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
            data-testid="cert-wizard-generar"
          >
            <span v-if="!loading">🔐 Generar automáticamente</span>
            <span v-else>Generando...</span>
          </BaseButton>
        </div>
      </form>
    </div>
    
    <div
      v-else-if="usarCSRExistente"
      class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6"
    >
      <BaseAlert
        v-if="errorClaves"
        type="warning"
        class="mb-4"
      >
        {{ errorClaves }}
      </BaseAlert>
      
      <div class="space-y-4">
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
        />
        
        <BaseInput
          v-model="keyFilename"
          label="Nombre de la clave privada (.key)"
          placeholder="23318277559_homologacion_20260204_123456.key"
          hint="Debe ser la clave generada por FactuFlow para este CSR"
          required
          :maxlength="255"
        />
        
        <div class="flex flex-wrap items-center gap-3">
          <BaseButton
            variant="secondary"
            size="sm"
            :loading="loadingClaves"
            :disabled="!formularioValido || loadingClaves"
            @click="cargarClaves"
          >
            Buscar claves en servidor
          </BaseButton>
          <span
            v-if="clavesDisponibles.length > 0"
            class="text-sm text-gray-600"
          >
            Se encontraron {{ clavesDisponibles.length }} clave(s)
          </span>
        </div>
        
        <BaseSelect
          v-if="clavesDisponibles.length > 0"
          v-model="keyFilename"
          label="Seleccionar clave encontrada"
          :options="clavesDisponibles.map(c => ({ value: c, label: c }))"
          placeholder="Seleccionar clave"
        />
      </div>
    </div>

    <div
      v-else
      class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6"
    >
      <BaseAlert
        type="success"
        class="mb-4"
      >
        <p class="font-semibold mb-2">
          ✅ CSR generado exitosamente
        </p>
        <p class="text-sm">
          El archivo de solicitud (.csr) se descargó automáticamente.
          Guardá este archivo, lo vas a necesitar en el siguiente paso.
        </p>
      </BaseAlert>
      
      <div class="bg-yellow-50 border-l-4 border-yellow-500 p-4">
        <p class="font-semibold text-gray-900 mb-2">
          ⚠️ IMPORTANTE
        </p>
        <p class="text-sm text-gray-700">
          La clave privada (.key) se guardó de forma segura en el servidor.
          No la pierdas, ya que la vas a necesitar para usar el certificado.
        </p>
      </div>

      <div class="mt-4 bg-gray-50 rounded-lg p-4">
        <p class="text-sm text-gray-700 mb-2">
          Clave privada generada:
        </p>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span class="font-mono text-sm text-gray-900 break-all">
            {{ csrData?.key_filename }}
          </span>
          <BaseButton
            variant="secondary"
            size="sm"
            @click="copiarClave"
          >
            {{ claveCopiada ? 'Copiada' : 'Copiar nombre' }}
          </BaseButton>
        </div>
        <p class="text-xs text-gray-500 mt-2">
          Se guarda en el servidor en la carpeta configurada en <code>CERTS_PATH</code>
          (por defecto <code>backend/certs/</code>).
        </p>
      </div>
    </div>
    
    <div class="flex justify-between">
      <BaseButton
        variant="secondary"
        @click="emit('prev')"
      >
        ← Anterior
      </BaseButton>
      
      <BaseButton
        variant="primary"
        :disabled="!puedeContinuar"
        data-testid="cert-wizard-step2-next"
        @click="continuar"
      >
        Siguiente →
      </BaseButton>
    </div>
  </div>
</template>
