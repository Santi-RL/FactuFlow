<script setup lang="ts">
interface Emits {
  (e: 'next'): void
}

const emit = defineEmits<Emits>()
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <div class="text-center mb-8">
      <div class="text-6xl mb-4">
        🔐
      </div>
      <h2 class="text-3xl font-bold text-gray-900 mb-2">
        ¡Configuremos tu certificado ARCA!
      </h2>
    </div>
    
    <div class="bg-white rounded-lg shadow-md border border-gray-200 p-8 mb-8">
      <div class="prose prose-lg max-w-none">
        <p class="text-gray-700 mb-6">
          Para poder emitir facturas electrónicas, necesitás un certificado digital 
          que te identifica ante ARCA (ex-AFIP).
        </p>
        
        <p class="text-gray-700 mb-6">
          Este asistente te guiará paso a paso por todo el proceso. 
          <strong>¡No te preocupes, es más fácil de lo que parece!</strong>
        </p>
        
        <div class="bg-blue-50 border-l-4 border-blue-500 p-6 mb-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span>📋</span>
            <span>Vas a necesitar:</span>
          </h3>
          
          <ul class="space-y-2">
            <li class="flex items-start gap-2">
              <span class="text-green-600 mt-1">✓</span>
              <span>Tu CUIT</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-green-600 mt-1">✓</span>
              <span>Tu clave fiscal (nivel 3 o superior)</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-green-600 mt-1">✓</span>
              <span>Acceso al portal de ARCA</span>
            </li>
          </ul>
        </div>
        
        <div class="bg-gray-50 border border-gray-200 rounded-lg p-6">
          <div class="flex items-center gap-3 mb-2">
            <span class="text-2xl">⏱️</span>
            <span class="text-lg font-semibold text-gray-900">Tiempo estimado:</span>
          </div>
          <p class="text-gray-700 text-lg">
            10-15 minutos
          </p>
        </div>
      </div>
    </div>
    
    <div class="flex justify-center">
      <button
        class="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold text-lg shadow-md hover:shadow-lg"
        @click="emit('next')"
      >
        Comenzar →
      </button>
    </div>
  </div>
</template>
