<script setup lang="ts">
import { ref } from "vue";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/vue/24/outline";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";

interface Emits {
  (e: "next"): void;
  (e: "prev"): void;
}

const emit = defineEmits<Emits>();

const tengoElCertificado = ref(false);

const abrirPortalArca = () => {
  window.open("https://auth.afip.gob.ar/contribuyente_/login.xhtml", "_blank");
};
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h2 class="mb-6 text-2xl font-bold text-brand-ink">
      Obtené tu certificado en el portal de ARCA
    </h2>

    <BaseCard class="mb-6 p-6">
      <p class="mb-6 text-brand-slate">
        Ahora tenés que ir al portal de ARCA para obtener tu certificado. Seguí
        estos pasos:
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
              Ingresá al portal de ARCA
            </h3>
            <BaseButton
              variant="ghost"
              size="sm"
              @click="abrirPortalArca"
            >
              <ArrowTopRightOnSquareIcon class="mr-2 h-4 w-4" />
              <span>Ir al portal de ARCA</span>
            </BaseButton>
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
              Iniciá sesión con tu CUIT y clave fiscal
            </h3>
            <p class="text-sm text-brand-slate">
              Necesitás nivel 3 o superior en tu clave fiscal.
            </p>
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
              Buscá el servicio "Administración de Certificados Digitales"
            </h3>
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
              Seleccioná "Agregar Alias"
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
              Completá un nombre para identificar el certificado
            </h3>
            <p class="text-sm text-brand-slate">
              Ejemplo: "FactuFlow Producción"
            </p>
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
              Luego seleccioná "Agregar Alias" y subí el archivo .csr que
              descargaste en el paso anterior
            </h3>
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
              Hacé click en "Ver" y descargá el certificado (.crt) que te genera
              ARCA
            </h3>
            <p class="text-sm text-brand-slate">
              El archivo descargado suele llamarse algo como
              "certificado_XXXXXXXX.crt" o similar.
            </p>
          </div>
        </div>
      </div>

      <div class="mt-6 border-t border-border-subtle pt-6">
        <button
          class="inline-flex items-center text-sm font-medium text-brand-flow transition-colors hover:text-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
          type="button"
        >
          <QuestionMarkCircleIcon class="mr-2 h-4 w-4" />
          <span>¿Tenés problemas? Ver guía detallada</span>
          <ArrowRightIcon class="ml-2 h-4 w-4" />
        </button>
      </div>
    </BaseCard>

    <BaseCard class="mb-6 p-6">
      <label class="flex cursor-pointer items-start gap-3">
        <input
          v-model="tengoElCertificado"
          type="checkbox"
          class="mt-1 h-5 w-5 rounded border-border-subtle text-brand-teal focus:ring-brand-flow"
        >
        <span class="flex items-center gap-2 text-brand-slate">
          <CheckCircleIcon class="h-5 w-5 text-brand-teal" />
          <span>Ya tengo el certificado .crt descargado</span>
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
        :disabled="!tengoElCertificado"
        data-testid="cert-wizard-step3-next"
        @click="emit('next')"
      >
        <span>Siguiente</span>
        <ArrowRightIcon class="ml-2 h-4 w-4" />
      </BaseButton>
    </div>
  </div>
</template>
