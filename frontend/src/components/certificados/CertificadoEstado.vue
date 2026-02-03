<script setup lang="ts">
import { computed } from 'vue'
import type { EstadoCertificado } from '@/types/certificado'

interface Props {
  estado: EstadoCertificado
  diasRestantes: number
}

const props = defineProps<Props>()

const badgeClasses = computed(() => {
  switch (props.estado) {
    case 'valido':
      return 'bg-green-100 text-green-800 border-green-200'
    case 'por_vencer':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    case 'vencido':
      return 'bg-red-100 text-red-800 border-red-200'
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200'
  }
})

const iconoEstado = computed(() => {
  switch (props.estado) {
    case 'valido':
      return '✅'
    case 'por_vencer':
      return '⚠️'
    case 'vencido':
      return '❌'
    default:
      return '•'
  }
})

const textoEstado = computed(() => {
  switch (props.estado) {
    case 'valido':
      return 'Válido'
    case 'por_vencer':
      return 'Por vencer'
    case 'vencido':
      return 'Vencido'
    default:
      return 'Desconocido'
  }
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border"
    :class="badgeClasses"
  >
    <span>{{ iconoEstado }}</span>
    <span>{{ textoEstado }}</span>
  </span>
</template>
