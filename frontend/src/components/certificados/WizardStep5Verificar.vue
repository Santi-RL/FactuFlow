<script setup lang="ts">
import { ref } from 'vue'
import type { Certificado, VerificacionResponse } from '@/types/certificado'
import certificadosService from '@/services/certificados.service'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseAlert from '@/components/ui/BaseAlert.vue'

interface Props {
  certificado: Certificado
}

interface Emits {
  (e: 'finish'): void
  (e: 'prev'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const loading = ref(false)
const verificado = ref(false)
const resultado = ref<VerificacionResponse | null>(null)

const verificarConexion = async () => {
  loading.value = true
  verificado.value = false
  
  try {
    const response = await certificadosService.verificarConexion(props.certificado.id)
    resultado.value = response
    verificado.value = true
  } catch (err: any) {
    resultado.value = {
      exito: false,
      mensaje: 'Error al conectar',
      error: err.response?.data?.detail || 'Ocurrió un error inesperado'
    }
    verificado.value = true
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">
      ¡Último paso! Verifiquemos que todo funciona
    </h2>
    
    <div class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6">
      <p class="text-gray-700 mb-6">
        Vamos a hacer una prueba de conexión con ARCA para asegurarnos 
        de que el certificado está bien configurado.
      </p>
      
      <div
        v-if="!verificado"
        class="text-center"
      >
        <BaseButton
          variant="primary"
          :loading="loading"
          class="px-8 py-3 text-lg"
          @click="verificarConexion"
        >
          <span v-if="!loading">🔌 Probar conexión</span>
          <span v-else>Verificando...</span>
        </BaseButton>
      </div>
      
      <div v-else>
        <!-- Éxito -->
        <div
          v-if="resultado?.exito"
          class="space-y-6"
        >
          <BaseAlert type="success">
            <div class="flex items-start gap-3">
              <span class="text-3xl">✅</span>
              <div>
                <h3 class="font-bold text-lg mb-2">
                  ¡Conexión exitosa!
                </h3>
                <p class="text-sm">
                  Tu certificado está correctamente configurado y listo para usar.
                </p>
              </div>
            </div>
          </BaseAlert>
          
          <div class="bg-gray-50 rounded-lg p-6">
            <h4 class="font-semibold text-gray-900 mb-4">
              Estado de servidores ARCA:
            </h4>
            
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-gray-700">• Aplicación:</span>
                <span class="text-green-600 font-medium flex items-center gap-1">
                  <span>✅</span>
                  <span>{{ resultado.estado_servidores?.aplicacion || 'OK' }}</span>
                </span>
              </div>
              
              <div class="flex items-center justify-between">
                <span class="text-gray-700">• Base de datos:</span>
                <span class="text-green-600 font-medium flex items-center gap-1">
                  <span>✅</span>
                  <span>{{ resultado.estado_servidores?.base_datos || 'OK' }}</span>
                </span>
              </div>
              
              <div class="flex items-center justify-between">
                <span class="text-gray-700">• Autenticación:</span>
                <span class="text-green-600 font-medium flex items-center gap-1">
                  <span>✅</span>
                  <span>{{ resultado.estado_servidores?.autenticacion || 'OK' }}</span>
                </span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Error -->
        <div
          v-else
          class="space-y-6"
        >
          <BaseAlert type="error">
            <div class="flex items-start gap-3">
              <span class="text-3xl">❌</span>
              <div>
                <h3 class="font-bold text-lg mb-2">
                  No se pudo conectar
                </h3>
                <p class="text-sm mb-3">
                  {{ resultado?.error || resultado?.mensaje }}
                </p>
              </div>
            </div>
          </BaseAlert>
          
          <div class="bg-yellow-50 border-l-4 border-yellow-500 p-6">
            <h4 class="font-semibold text-gray-900 mb-3">
              Posibles soluciones:
            </h4>
            
            <ul class="space-y-2 text-sm text-gray-700">
              <li class="flex gap-2">
                <span>•</span>
                <span>Verificá que el certificado sea correcto</span>
              </li>
              <li class="flex gap-2">
                <span>•</span>
                <span>Asegurate de haber autorizado el servicio en el portal de ARCA</span>
              </li>
              <li class="flex gap-2">
                <span>•</span>
                <span>Intentá de nuevo en unos minutos</span>
              </li>
            </ul>
          </div>
          
          <div class="flex gap-3 justify-center">
            <BaseButton
              variant="secondary"
              @click="verificarConexion"
            >
              Reintentar
            </BaseButton>
            
            <BaseButton
              variant="secondary"
            >
              Ver ayuda
            </BaseButton>
          </div>
        </div>
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
        v-if="resultado?.exito"
        variant="primary"
        @click="emit('finish')"
      >
        Finalizar ✓
      </BaseButton>
    </div>
  </div>
</template>
