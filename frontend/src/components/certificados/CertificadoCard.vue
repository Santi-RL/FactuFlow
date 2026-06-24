<script setup lang="ts">
import { computed } from "vue";
import {
  ExclamationTriangleIcon,
  KeyIcon,
} from "@heroicons/vue/24/outline";
import type { Certificado, VerificacionResponse } from "@/types/certificado";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import CertificadoEstado from "./CertificadoEstado.vue";

interface Props {
  certificado: Certificado;
  verificando?: boolean;
  resultadoVerificacion?: VerificacionResponse | null;
}

interface Emits {
  (e: "renovar", id: number): void;
  (e: "eliminar", id: number): void;
  (e: "verificar", id: number): void;
}

const props = withDefaults(defineProps<Props>(), {
  verificando: false,
  resultadoVerificacion: null,
});
const emit = defineEmits<Emits>();

const porcentajeVida = computed(() => {
  const fechaEmision = new Date(props.certificado.fecha_emision);
  const fechaVencimiento = new Date(props.certificado.fecha_vencimiento);
  const hoy = new Date();

  const totalDias = Math.floor(
    (fechaVencimiento.getTime() - fechaEmision.getTime()) /
      (1000 * 60 * 60 * 24),
  );
  const diasTranscurridos = Math.floor(
    (hoy.getTime() - fechaEmision.getTime()) / (1000 * 60 * 60 * 24),
  );

  const porcentaje = Math.max(
    0,
    Math.min(100, ((totalDias - diasTranscurridos) / totalDias) * 100),
  );

  return Math.round(porcentaje);
});

const barraColorClasses = computed(() => {
  if (props.certificado.estado === "vencido") {
    return "bg-status-danger";
  } else if (props.certificado.estado === "por_vencer") {
    return "bg-status-warning";
  }
  return "bg-status-success";
});

const resultadoClasses = computed(() => {
  if (!props.resultadoVerificacion) return "";

  return props.resultadoVerificacion.exito
    ? "border-status-success bg-surface-page"
    : "border-status-danger bg-surface-page";
});

const formatearFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
};

const formatearCUIT = (cuit: string) => {
  // Formato: XX-XXXXXXXX-X
  return `${cuit.slice(0, 2)}-${cuit.slice(2, 10)}-${cuit.slice(10)}`;
};

const nombreAmbiente = computed(() => {
  return props.certificado.ambiente === "produccion"
    ? "Producción"
    : "Homologación";
});
</script>

<template>
  <BaseCard class="h-full transition-shadow">
    <!-- Header -->
    <div class="mb-4 flex items-start justify-between gap-4">
      <div class="flex min-w-0 items-center gap-3">
        <div
          class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-control bg-brand-mint text-brand-teal"
        >
          <KeyIcon class="h-6 w-6" />
        </div>
        <div class="min-w-0">
          <h3 class="text-lg font-semibold text-brand-ink">
            {{ certificado.nombre }}
          </h3>
          <CertificadoEstado
            :estado="certificado.estado"
            :dias-restantes="certificado.dias_restantes"
            class="mt-1"
          />
        </div>
      </div>

      <ExclamationTriangleIcon
        v-if="
          certificado.estado === 'por_vencer' ||
            certificado.estado === 'vencido'
        "
        class="h-6 w-6 flex-shrink-0 text-status-warning"
      />
    </div>

    <!-- Info -->
    <div class="mb-4 space-y-2 text-sm">
      <div class="flex justify-between gap-4">
        <span class="text-brand-slate">CUIT:</span>
        <span class="font-medium text-brand-ink">{{
          formatearCUIT(certificado.cuit)
        }}</span>
      </div>

      <div class="flex justify-between gap-4">
        <span class="text-brand-slate">Ambiente:</span>
        <span class="font-medium text-brand-ink">{{ nombreAmbiente }}</span>
      </div>

      <div class="flex justify-between gap-4">
        <span class="text-brand-slate">Vence:</span>
        <span class="font-medium text-brand-ink">{{
          formatearFecha(certificado.fecha_vencimiento)
        }}</span>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="mb-4">
      <div class="mb-1 flex justify-between gap-4 text-xs text-brand-slate">
        <span>{{ porcentajeVida }}% válido</span>
        <span>{{ certificado.dias_restantes }} días restantes</span>
      </div>
      <div class="h-2 w-full rounded-full bg-surface-page">
        <div
          class="h-2 rounded-full transition-all duration-300"
          :class="barraColorClasses"
          :style="{ width: `${porcentajeVida}%` }"
        />
      </div>
    </div>

    <!-- Actions -->
    <div class="flex flex-wrap gap-2">
      <BaseButton
        variant="primary"
        size="sm"
        class="flex-1"
        :loading="verificando"
        :disabled="verificando"
        @click="emit('verificar', certificado.id)"
      >
        {{ verificando ? "Probando..." : "Probar conexión" }}
      </BaseButton>

      <BaseButton
        v-if="
          certificado.estado === 'por_vencer' ||
            certificado.estado === 'vencido'
        "
        variant="secondary"
        size="sm"
        @click="emit('renovar', certificado.id)"
      >
        Renovar
      </BaseButton>

      <BaseButton
        variant="danger"
        size="sm"
        @click="emit('eliminar', certificado.id)"
      >
        Eliminar
      </BaseButton>
    </div>

    <div
      v-if="resultadoVerificacion"
      class="mt-4 rounded-control border p-3 text-sm text-brand-ink"
      :class="resultadoClasses"
    >
      <p class="font-semibold">
        {{
          resultadoVerificacion.exito
            ? "Conexión exitosa"
            : "No se pudo conectar"
        }}
      </p>
      <p class="mt-1 text-brand-slate">
        {{ resultadoVerificacion.error || resultadoVerificacion.mensaje }}
      </p>
    </div>
  </BaseCard>
</template>
