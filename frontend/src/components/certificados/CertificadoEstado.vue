<script setup lang="ts">
import { computed } from "vue";
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  QuestionMarkCircleIcon,
  XCircleIcon,
} from "@heroicons/vue/24/outline";
import type { EstadoCertificado } from "@/types/certificado";
import BaseBadge from "@/components/ui/BaseBadge.vue";

interface Props {
  estado: EstadoCertificado;
  diasRestantes: number;
}

const props = defineProps<Props>();

const badgeVariant = computed(() => {
  switch (props.estado) {
    case "valido":
      return "success";
    case "por_vencer":
      return "warning";
    case "vencido":
      return "danger";
    default:
      return "default";
  }
});

const iconoEstado = computed(() => {
  switch (props.estado) {
    case "valido":
      return CheckCircleIcon;
    case "por_vencer":
      return ExclamationTriangleIcon;
    case "vencido":
      return XCircleIcon;
    default:
      return QuestionMarkCircleIcon;
  }
});

const textoEstado = computed(() => {
  switch (props.estado) {
    case "valido":
      return "Válido";
    case "por_vencer":
      return "Por vencer";
    case "vencido":
      return "Vencido";
    default:
      return "Desconocido";
  }
});
</script>

<template>
  <BaseBadge
    :variant="badgeVariant"
    size="sm"
    class="gap-1"
  >
    <component
      :is="iconoEstado"
      class="h-3.5 w-3.5"
    />
    <span>{{ textoEstado }}</span>
  </BaseBadge>
</template>
