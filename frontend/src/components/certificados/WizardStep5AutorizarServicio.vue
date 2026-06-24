<script setup lang="ts">
import { ref } from "vue";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
} from "@heroicons/vue/24/outline";
import type { Certificado } from "@/types/certificado";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";

interface Props {
  certificado: Certificado;
}

interface Emits {
  (e: "next"): void;
  (e: "prev"): void;
}

defineProps<Props>();
const emit = defineEmits<Emits>();

const servicioAutorizado = ref(false);
const portalArcaUrl = "https://auth.afip.gob.ar/contribuyente_/login.xhtml";
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h2 class="mb-6 text-2xl font-bold text-brand-ink">
      Autorizá el servicio de facturación
    </h2>

    <BaseCard class="mb-6 p-6">
      <p class="mb-6 text-brand-slate">
        Hacé esta autorización en ARCA para el mismo CUIT y certificado que
        acabás de cargar.
      </p>

      <div class="space-y-6">
        <div class="flex gap-4">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control bg-brand-teal font-bold text-white"
          >
            1
          </div>
          <div>
            <h3 class="mb-2 font-semibold text-brand-ink">
              Entrá al portal de ARCA
            </h3>
            <a
              :href="portalArcaUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center rounded-control px-3 py-1.5 text-sm font-medium text-brand-flow transition-colors hover:bg-brand-mint hover:text-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
            >
              <ArrowTopRightOnSquareIcon class="mr-2 h-4 w-4" />
              <span>Ir al portal de ARCA</span>
            </a>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control bg-brand-teal font-bold text-white"
          >
            2
          </div>
          <div>
            <h3 class="mb-2 font-semibold text-brand-ink">
              Abrí Administrador de Relaciones de Clave Fiscal
            </h3>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control bg-brand-teal font-bold text-white"
          >
            3
          </div>
          <div>
            <h3 class="mb-2 font-semibold text-brand-ink">
              Seleccioná "Adherir servicio"
            </h3>
            <p class="text-sm text-brand-slate">
              En la siguiente pantalla elegí "ARCA" y luego "Web Services".
            </p>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control bg-brand-teal font-bold text-white"
          >
            4
          </div>
          <div>
            <h3 class="mb-2 font-semibold text-brand-ink">
              Buscá el servicio "Factura Electrónica"
            </h3>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control bg-brand-teal font-bold text-white"
          >
            5
          </div>
          <div>
            <h3 class="mb-2 font-semibold text-brand-ink">
              En la fila "Representante", hacé click en "Buscar"
            </h3>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control bg-brand-teal font-bold text-white"
          >
            6
          </div>
          <div>
            <h3 class="mb-2 font-semibold text-brand-ink">
              Elegí el computador fiscal
            </h3>
            <p class="text-sm text-brand-slate">
              En "Computador Fiscal", elegí "FactuFlow" o el alias que le hayas
              puesto al certificado y luego confirmá.
            </p>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control bg-brand-teal font-bold text-white"
          >
            7
          </div>
          <div>
            <h3 class="mb-2 font-semibold text-brand-ink">
              Verificá los datos en pantalla
            </h3>
            <p class="text-sm text-brand-slate">
              Luego confirmá la nueva relación.
            </p>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-control bg-brand-teal font-bold text-white"
          >
            8
          </div>
          <div>
            <h3 class="mb-2 font-semibold text-brand-ink">
              Volvé a FactuFlow para continuar
            </h3>
            <p class="text-sm text-brand-slate">
              Si todo sale bien, deberías ver una pantalla de confirmación de
              ARCA.
            </p>
          </div>
        </div>
      </div>
    </BaseCard>

    <BaseCard class="mb-6 p-6">
      <label class="flex cursor-pointer items-start gap-3">
        <input
          v-model="servicioAutorizado"
          type="checkbox"
          class="mt-1 h-5 w-5 rounded border-border-subtle text-brand-teal focus:ring-brand-flow"
          data-testid="cert-wizard-wsfe-authorized"
        >
        <span class="flex items-start gap-2 text-brand-slate">
          <CheckCircleIcon class="mt-0.5 h-5 w-5 flex-shrink-0 text-brand-teal" />
          <span>
            Ya autoricé el servicio "Factura Electrónica" para este certificado
            en ARCA
          </span>
        </span>
      </label>
    </BaseCard>

    <div class="flex justify-between gap-3">
      <BaseButton
        variant="secondary"
        @click="emit('prev')"
      >
        <ArrowLeftIcon class="mr-2 h-4 w-4" />
        <span>Anterior</span>
      </BaseButton>

      <BaseButton
        variant="primary"
        :disabled="!servicioAutorizado"
        data-testid="cert-wizard-step5-next"
        @click="emit('next')"
      >
        <span>Siguiente</span>
        <ArrowRightIcon class="ml-2 h-4 w-4" />
      </BaseButton>
    </div>
  </div>
</template>
