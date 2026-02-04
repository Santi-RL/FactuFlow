<script setup lang="ts">
import { ref } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'

interface Emits {
  (e: 'next'): void
  (e: 'prev'): void
}

const emit = defineEmits<Emits>()

const tengoElCertificado = ref(false)

const abrirPortalArca = () => {
  window.open('https://auth.afip.gob.ar/contribuyente_/login.xhtml', '_blank')
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">
      Obtené tu certificado en el portal de ARCA
    </h2>
    
    <div class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6">
      <p class="text-gray-700 mb-6">
        Ahora tenés que ir al portal de ARCA para obtener tu certificado.
        Seguí estos pasos:
      </p>
      
      <div class="space-y-6">
        <!-- Paso 1 -->
        <div class="flex gap-4">
          <div class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
            1
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Ingresá al portal de ARCA
            </h3>
            <button
              class="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
              @click="abrirPortalArca"
            >
              <span>🔗</span>
              <span>Ir al portal de ARCA</span>
              <span>↗</span>
            </button>
          </div>
        </div>
        
        <!-- Paso 2 -->
        <div class="flex gap-4">
          <div class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
            2
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Iniciá sesión con tu CUIT y clave fiscal
            </h3>
            <p class="text-sm text-gray-600">
              Necesitás nivel 3 o superior en tu clave fiscal.
            </p>
          </div>
        </div>
        
        <!-- Paso 3 -->
        <div class="flex gap-4">
          <div class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
            3
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Buscá el servicio "Administración de Certificados Digitales"
            </h3>
            <p class="text-sm text-gray-600">
              También puede aparecer como "WSASS" o en "Administrador de Relaciones"
            </p>
          </div>
        </div>
        
        <!-- Paso 4 -->
        <div class="flex gap-4">
          <div class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
            4
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Seleccioná "Agregar Alias" o "Nuevo Certificado"
            </h3>
          </div>
        </div>
        
        <!-- Paso 5 -->
        <div class="flex gap-4">
          <div class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
            5
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Completá un nombre para identificar el certificado
            </h3>
            <p class="text-sm text-gray-600">
              Ejemplo: "FactuFlow Producción"
            </p>
          </div>
        </div>
        
        <!-- Paso 6 -->
        <div class="flex gap-4">
          <div class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
            6
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Subí el archivo .csr que descargaste en el paso anterior
            </h3>
          </div>
        </div>
        
        <!-- Paso 7 -->
        <div class="flex gap-4">
          <div class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
            7
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Descargá el certificado (.crt) que te genera ARCA
            </h3>
            <p class="text-sm text-gray-600">
              💡 El archivo descargado suele llamarse algo como "certificado_XXXXXXXX.crt" o similar.
            </p>
          </div>
        </div>
      </div>
      
      <div class="mt-6 pt-6 border-t border-gray-200">
        <button
          class="text-blue-600 hover:text-blue-700 font-medium text-sm"
        >
          ¿Tenés problemas? Ver guía detallada →
        </button>
      </div>
    </div>
    
    <div class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6">
      <label class="flex items-start gap-3 cursor-pointer">
        <input
          v-model="tengoElCertificado"
          type="checkbox"
          class="mt-1 w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
        >
        <span class="text-gray-700">
          Ya tengo el certificado .crt descargado
        </span>
      </label>
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
        :disabled="!tengoElCertificado"
        @click="emit('next')"
      >
        Siguiente →
      </BaseButton>
    </div>
  </div>
</template>
