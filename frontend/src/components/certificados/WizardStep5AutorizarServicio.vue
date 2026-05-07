<script setup lang="ts">
import { computed, ref } from "vue";
import type { Certificado } from "@/types/certificado";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";

interface Props {
  certificado: Certificado;
}

interface Emits {
  (e: "next"): void;
  (e: "prev"): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const servicioAutorizado = ref(false);

const esProduccion = computed(
  () => props.certificado.ambiente === "produccion",
);

const abrirPortalArca = () => {
  window.open("https://auth.afip.gob.ar/contribuyente_/login.xhtml", "_blank");
};
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">
      Autorizá el servicio de facturación
    </h2>

    <BaseAlert type="warning" class="mb-6">
      El certificado ya está cargado, pero ARCA no permite usarlo hasta que lo
      asocies al servicio de negocio `wsfe`. Si salteás este paso, la prueba de
      conexión puede fallar con "Computador no autorizado a acceder al
      servicio".
    </BaseAlert>

    <div class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6">
      <p class="text-gray-700 mb-6">
        Hacé esta autorización en ARCA para el mismo CUIT y certificado que
        acabás de cargar.
      </p>

      <div class="space-y-6">
        <div class="flex gap-4">
          <div
            class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold"
          >
            1
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Entrá al portal de ARCA
            </h3>
            <button
              class="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
              @click="abrirPortalArca"
            >
              <span>Ir al portal de ARCA</span>
              <span>↗</span>
            </button>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold"
          >
            2
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              {{
                esProduccion
                  ? "Abrí Administrador de Relaciones de Clave Fiscal"
                  : "Abrí WSASS"
              }}
            </h3>
            <p class="text-sm text-gray-600">
              {{
                esProduccion
                  ? "En producción, la relación del certificado con el webservice se hace desde Administrador de Relaciones."
                  : "En homologación, la relación se gestiona desde WSASS."
              }}
            </p>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold"
          >
            3
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Asociá el certificado al servicio `wsfe`
            </h3>
            <p class="text-sm text-gray-600">
              Seleccioná el alias del computador/certificado que creaste para
              FactuFlow y autorizalo para Web Service de Factura Electrónica
              (`wsfe`).
            </p>
          </div>
        </div>

        <div class="flex gap-4">
          <div
            class="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold"
          >
            4
          </div>
          <div>
            <h3 class="font-semibold text-gray-900 mb-2">
              Confirmá la relación
            </h3>
            <p class="text-sm text-gray-600">
              Al finalizar, volvé a FactuFlow para ejecutar la prueba de
              conexión contra ARCA.
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6">
      <label class="flex items-start gap-3 cursor-pointer">
        <input
          v-model="servicioAutorizado"
          type="checkbox"
          class="mt-1 w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          data-testid="cert-wizard-wsfe-authorized"
        />
        <span class="text-gray-700">
          Ya autoricé el servicio `wsfe` para este certificado en ARCA
        </span>
      </label>
    </div>

    <div class="flex justify-between">
      <BaseButton variant="secondary" @click="emit('prev')">
        ← Anterior
      </BaseButton>

      <BaseButton
        variant="primary"
        :disabled="!servicioAutorizado"
        data-testid="cert-wizard-step5-next"
        @click="emit('next')"
      >
        Siguiente →
      </BaseButton>
    </div>
  </div>
</template>
