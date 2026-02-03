<script setup lang="ts">
const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="bg-white border-t border-gray-200 py-4 px-6">
    <div class="text-center text-sm text-gray-500">
      © {{ currentYear }} FactuFlow - Sistema de Facturación Electrónica ARCA
    </div>
  </footer>
</template>
