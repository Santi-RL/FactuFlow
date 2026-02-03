<script setup lang="ts">
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseEmpty from '@/components/ui/BaseEmpty.vue'
import { DocumentTextIcon } from '@heroicons/vue/24/outline'
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900">Empresa</h1>
      <p class="mt-2 text-gray-600">Configuración de la empresa</p>
    </div>

    <BaseCard>
      <BaseEmpty
        title="Próximamente"
        message="La configuración de empresa estará disponible en una próxima versión"
        :icon="DocumentTextIcon"
      />
    </BaseCard>
  </div>
</template>
