<script setup lang="ts">
import { ref } from "vue";
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  CloudArrowUpIcon,
  QuestionMarkCircleIcon,
  ServerStackIcon,
  ShieldCheckIcon,
} from "@heroicons/vue/24/outline";
import type { Certificado, VerificacionResponse } from "@/types/certificado";
import certificadosService from "@/services/certificados.service";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseCard from "@/components/ui/BaseCard.vue";

interface Props {
  certificado: Certificado;
}

interface Emits {
  (e: "finish"): void;
  (e: "prev"): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const loading = ref(false);
const verificado = ref(false);
const resultado = ref<VerificacionResponse | null>(null);

const verificarConexion = async () => {
  loading.value = true;
  verificado.value = false;

  try {
    const response = await certificadosService.verificarConexion(
      props.certificado.id,
    );
    resultado.value = response;
    verificado.value = true;
  } catch (err: any) {
    resultado.value = {
      exito: false,
      mensaje: "Error al conectar",
      error: err.response?.data?.detail || "Ocurrió un error inesperado",
    };
    verificado.value = true;
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h2 class="mb-6 text-2xl font-bold text-brand-ink">
      Último paso: verifiquemos que todo funciona
    </h2>

    <BaseCard class="mb-6 p-6">
      <p class="mb-6 text-brand-slate">
        Vamos a hacer una prueba de conexión con ARCA para asegurarnos de que el
        certificado está bien configurado.
      </p>

      <div
        v-if="!verificado"
        class="rounded-panel border border-border-subtle bg-surface-page p-8 text-center"
      >
        <div
          class="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-panel bg-brand-mint text-brand-teal"
        >
          <CloudArrowUpIcon class="h-9 w-9" />
        </div>

        <h3 class="mb-2 text-lg font-semibold text-brand-ink">
          Probá la conexión antes de terminar
        </h3>
        <p class="mx-auto mb-6 max-w-xl text-sm text-brand-slate">
          FactuFlow va a consultar ARCA con este certificado para confirmar que
          la autenticación y los servidores responden correctamente.
        </p>

        <BaseButton
          variant="primary"
          :loading="loading"
          size="lg"
          data-testid="cert-wizard-verificar"
          @click="verificarConexion"
        >
          <span>{{ loading ? "Verificando..." : "Probar conexión" }}</span>
        </BaseButton>
      </div>

      <div v-else>
        <div
          v-if="resultado?.exito"
          class="space-y-6"
        >
          <BaseAlert
            type="success"
            title="Conexión exitosa"
            :dismissible="false"
          >
            Tu certificado está correctamente configurado y listo para usar.
          </BaseAlert>

          <div
            class="rounded-panel border border-border-subtle bg-surface-page p-6"
          >
            <h4 class="mb-4 flex items-center gap-2 font-semibold text-brand-ink">
              <ServerStackIcon class="h-5 w-5 text-brand-teal" />
              <span>Estado de servidores ARCA:</span>
            </h4>

            <div class="space-y-3">
              <div class="flex items-center justify-between gap-4">
                <span class="text-brand-slate">Aplicación:</span>
                <span
                  class="flex items-center gap-2 font-medium text-status-success"
                >
                  <CheckCircleIcon class="h-5 w-5" />
                  <span>{{ resultado.estado_servidores?.aplicacion || "OK" }}</span>
                </span>
              </div>

              <div class="flex items-center justify-between gap-4">
                <span class="text-brand-slate">Base de datos:</span>
                <span
                  class="flex items-center gap-2 font-medium text-status-success"
                >
                  <CheckCircleIcon class="h-5 w-5" />
                  <span>{{ resultado.estado_servidores?.base_datos || "OK" }}</span>
                </span>
              </div>

              <div class="flex items-center justify-between gap-4">
                <span class="text-brand-slate">Autenticación:</span>
                <span
                  class="flex items-center gap-2 font-medium text-status-success"
                >
                  <CheckCircleIcon class="h-5 w-5" />
                  <span>{{ resultado.estado_servidores?.autenticacion || "OK" }}</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <div
          v-else
          class="space-y-6"
        >
          <BaseAlert
            type="error"
            title="No se pudo conectar"
            :dismissible="false"
          >
            {{ resultado?.error || resultado?.mensaje }}
          </BaseAlert>

          <div class="rounded-panel border border-border-subtle border-l-4 border-l-status-warning bg-surface-page p-6">
            <h4 class="mb-3 flex items-center gap-2 font-semibold text-brand-ink">
              <ShieldCheckIcon class="h-5 w-5 text-status-warning" />
              <span>Posibles soluciones:</span>
            </h4>

            <ul class="space-y-2 text-sm text-brand-slate">
              <li class="flex gap-2">
                <CheckCircleIcon class="mt-0.5 h-4 w-4 flex-shrink-0 text-status-warning" />
                <span>Verificá que el certificado sea correcto</span>
              </li>
              <li class="flex gap-2">
                <CheckCircleIcon class="mt-0.5 h-4 w-4 flex-shrink-0 text-status-warning" />
                <span>
                  Asegurate de haber autorizado el servicio en el portal de ARCA
                </span>
              </li>
              <li class="flex gap-2">
                <CheckCircleIcon class="mt-0.5 h-4 w-4 flex-shrink-0 text-status-warning" />
                <span>Intentá de nuevo en unos minutos</span>
              </li>
            </ul>
          </div>

          <div class="flex flex-wrap justify-center gap-3">
            <BaseButton
              variant="secondary"
              @click="verificarConexion"
            >
              <ArrowPathIcon class="mr-2 h-4 w-4" />
              <span>Reintentar</span>
            </BaseButton>

            <BaseButton variant="secondary">
              <QuestionMarkCircleIcon class="mr-2 h-4 w-4" />
              <span>Ver ayuda</span>
            </BaseButton>
          </div>
        </div>
      </div>
    </BaseCard>

    <div class="flex justify-between gap-3">
      <BaseButton
        variant="secondary"
        :disabled="loading"
        @click="emit('prev')"
      >
        <ArrowLeftIcon class="mr-2 h-4 w-4" />
        <span>Anterior</span>
      </BaseButton>

      <BaseButton
        v-if="resultado?.exito"
        variant="primary"
        data-testid="cert-wizard-finish"
        @click="emit('finish')"
      >
        <span>Finalizar</span>
        <CheckCircleIcon class="ml-2 h-4 w-4" />
      </BaseButton>
    </div>
  </div>
</template>
