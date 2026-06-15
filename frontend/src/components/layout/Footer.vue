<script setup lang="ts">
const currentYear = new Date().getFullYear();
</script>

<template>
  <footer class="border-t border-border-subtle bg-surface-card px-6 py-4">
    <div class="text-center text-sm text-brand-slate">
      © {{ currentYear }} FactuFlow - Sistema de Facturación Electrónica ARCA
    </div>
  </footer>
</template>
