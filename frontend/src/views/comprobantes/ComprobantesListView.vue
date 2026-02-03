<script setup lang="ts">
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseEmpty from '@/components/ui/BaseEmpty.vue'
import { DocumentTextIcon } from '@heroicons/vue/24/outline'
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900">Comprobantes</h1>
      <p class="mt-2 text-gray-600">Gestión de facturas y comprobantes electrónicos</p>
    </div>

    <BaseCard>
      <BaseEmpty
        title="Próximamente"
        message="La gestión de comprobantes estará disponible en una próxima versión"
        :icon="DocumentTextIcon"
      />
    </BaseCard>
  </div>
</template>
