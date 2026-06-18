<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { Certificado } from "@/types/certificado";
import certificadosService from "@/services/certificados.service";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import {
  CheckCircleIcon,
  ClipboardDocumentCheckIcon,
  LightBulbIcon,
} from "@heroicons/vue/24/outline";

const route = useRoute();
const router = useRouter();

const certificado = ref<Certificado | null>(null);
const loading = ref(true);

const formatearCUIT = (cuit: string) => {
  return `${cuit.slice(0, 2)}-${cuit.slice(2, 10)}-${cuit.slice(10)}`;
};

const formatearFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
};

const irADashboard = () => {
  router.push({ name: "dashboard" });
};

const irACertificados = () => {
  router.push({ name: "certificados" });
};

onMounted(async () => {
  const id = route.params.id;
  if (id) {
    try {
      certificado.value = await certificadosService.obtener(Number(id));
    } catch (err) {
      console.error(err);
    }
  }
  loading.value = false;
});
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <div
      v-if="loading"
      class="flex justify-center py-12"
    >
      <BaseSpinner size="lg" />
    </div>

    <div
      v-else
      class="mx-auto max-w-2xl"
    >
      <!-- Success Icon -->
      <div class="mb-8 text-center">
        <div
          class="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-panel bg-brand-mint"
        >
          <CheckCircleIcon class="h-12 w-12 text-status-success" />
        </div>
        <h1 class="mb-2 text-4xl font-bold text-brand-ink">
          ¡Felicitaciones!
        </h1>
        <p class="text-xl text-brand-slate">
          Tu certificado ARCA está configurado correctamente
        </p>
      </div>

      <!-- Info Card -->
      <BaseCard class="mb-8">
        <p class="mb-6 text-center text-brand-slate">
          Ya podés empezar a emitir facturas electrónicas.
        </p>

        <div
          v-if="certificado"
          class="mb-6 rounded-panel bg-surface-page p-6"
        >
          <h3 class="mb-4 flex items-center gap-2 font-semibold text-brand-ink">
            <ClipboardDocumentCheckIcon class="h-5 w-5 text-brand-flow" />
            Resumen
          </h3>

          <dl class="space-y-3">
            <div class="flex justify-between">
              <dt class="text-brand-slate">
                CUIT:
              </dt>
              <dd class="font-medium text-brand-ink">
                {{ formatearCUIT(certificado.cuit) }}
              </dd>
            </div>

            <div class="flex justify-between">
              <dt class="text-brand-slate">
                Ambiente:
              </dt>
              <dd class="font-medium text-brand-ink">
                {{
                  certificado.ambiente === "produccion"
                    ? "Producción"
                    : "Homologación"
                }}
              </dd>
            </div>

            <div class="flex justify-between">
              <dt class="text-brand-slate">
                Válido hasta:
              </dt>
              <dd class="font-medium text-brand-ink">
                {{ formatearFecha(certificado.fecha_vencimiento) }}
              </dd>
            </div>
          </dl>
        </div>

        <div class="border-l-4 border-brand-flow bg-brand-mint p-4">
          <p class="flex gap-2 text-sm text-brand-slate">
            <LightBulbIcon class="h-5 w-5 flex-shrink-0 text-brand-flow" />
            <span>Te avisaremos cuando el certificado esté por vencer.</span>
          </p>
        </div>
      </BaseCard>

      <!-- Actions -->
      <div class="flex flex-col justify-center gap-4 sm:flex-row">
        <BaseButton
          variant="primary"
          class="px-6"
          @click="irADashboard"
        >
          Ir al Dashboard
        </BaseButton>

        <BaseButton
          variant="secondary"
          class="px-6"
          @click="irACertificados"
        >
          Ver certificados
        </BaseButton>
      </div>
    </div>
  </div>
</template>
