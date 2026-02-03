<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

onMounted(() => {
  // Inicializar auth desde localStorage
  authStore.init()
})
</script>

<template>
  <router-view />
</template>
