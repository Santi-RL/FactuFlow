<script setup lang="ts">
import { ref, computed } from "vue";
import {
  ArrowLeftIcon,
  DocumentArrowUpIcon,
} from "@heroicons/vue/24/outline";
import type { Certificado } from "@/types/certificado";
import certificadosService from "@/services/certificados.service";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";

interface Props {
  cuit: string;
  nombre: string;
  ambiente: string;
  keyFilename: string;
}

interface Emits {
  (e: "next", certificado: Certificado): void;
  (e: "prev"): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const file = ref<File | null>(null);
const dragActive = ref(false);
const loading = ref(false);
const error = ref("");
const certificadoSubido = ref<Certificado | null>(null);

const fileInputRef = ref<HTMLInputElement>();

const certificadoInfo = computed(() => {
  if (!certificadoSubido.value) return null;

  const cert = certificadoSubido.value;
  const fechaEmision = new Date(cert.fecha_emision).toLocaleDateString("es-AR");
  const fechaVencimiento = new Date(cert.fecha_vencimiento).toLocaleDateString(
    "es-AR",
  );

  return {
    cuit: `${cert.cuit.slice(0, 2)}-${cert.cuit.slice(2, 10)}-${cert.cuit.slice(10)}`,
    fechaEmision,
    fechaVencimiento,
    diasRestantes: cert.dias_restantes,
  };
});

const onFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    file.value = input.files[0];
    subirCertificado();
  }
};

const onDrop = (event: DragEvent) => {
  dragActive.value = false;

  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    file.value = event.dataTransfer.files[0];
    subirCertificado();
  }
};

const onDragOver = (event: DragEvent) => {
  event.preventDefault();
  dragActive.value = true;
};

const onDragLeave = () => {
  dragActive.value = false;
};

const selectFile = () => {
  fileInputRef.value?.click();
};

const subirCertificado = async () => {
  if (!file.value) return;

  // Validar extensión
  const extension = file.value.name.split(".").pop()?.toLowerCase();
  if (!extension || !["crt", "cer", "pem"].includes(extension)) {
    error.value = "Formato de archivo inválido. Se acepta .crt, .cer o .pem";
    file.value = null;
    return;
  }

  loading.value = true;
  error.value = "";

  try {
    const certificado = await certificadosService.subirCertificado(
      file.value,
      props.cuit,
      props.nombre,
      props.ambiente,
      props.keyFilename,
    );

    certificadoSubido.value = certificado;
  } catch (err: any) {
    const detail = err.response?.data?.detail;

    if (typeof detail === "string") {
      error.value = detail;
    } else {
      error.value =
        "Error al subir el certificado. Por favor, verificá que sea el archivo correcto.";
    }

    file.value = null;
  } finally {
    loading.value = false;
  }
};

const continuar = () => {
  if (certificadoSubido.value) {
    emit("next", certificadoSubido.value);
  }
};
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h2 class="mb-6 text-2xl font-bold text-brand-ink">
      Subí tu certificado
    </h2>

    <BaseAlert
      type="info"
      class="mb-6"
    >
      Usando clave privada:
      <span class="font-mono text-brand-ink">{{ props.keyFilename }}</span>
    </BaseAlert>

    <div
      v-if="!certificadoSubido"
      class="mb-6"
    >
      <BaseAlert
        v-if="error"
        type="error"
        class="mb-4"
      >
        {{ error }}
      </BaseAlert>

      <div
        class="cursor-pointer rounded-panel border-2 border-dashed p-12 text-center shadow-panel transition-all"
        :class="{
          'border-brand-flow bg-brand-mint': dragActive && !loading,
          'border-border-subtle bg-surface-card hover:border-brand-flow hover:bg-brand-mint':
            !dragActive && !loading,
          'cursor-not-allowed border-border-subtle bg-surface-page': loading,
        }"
        @drop.prevent="onDrop"
        @dragover.prevent="onDragOver"
        @dragleave="onDragLeave"
        @click="selectFile"
      >
        <input
          ref="fileInputRef"
          type="file"
          data-testid="cert-wizard-file"
          accept=".crt,.cer,.pem"
          class="hidden"
          :disabled="loading"
          @change="onFileSelect"
        >

        <div
          v-if="!loading"
          class="space-y-4"
        >
          <div
            class="mx-auto flex h-16 w-16 items-center justify-center rounded-panel bg-brand-mint text-brand-teal"
          >
            <DocumentArrowUpIcon class="h-9 w-9" />
          </div>
          <div>
            <p class="mb-2 text-lg font-semibold text-brand-ink">
              Arrastrá el archivo .crt aquí
            </p>
            <p class="text-brand-slate">
              o hacé clic para seleccionar
            </p>
          </div>
          <p class="text-sm text-brand-slate">
            Formatos aceptados: .crt, .cer, .pem
          </p>
        </div>

        <div
          v-else
          class="space-y-4"
        >
          <div
            class="inline-block h-12 w-12 animate-spin rounded-full border-b-2 border-brand-teal"
          />
          <p class="text-lg font-semibold text-brand-ink">
            Validando certificado...
          </p>
        </div>
      </div>
    </div>

    <div
      v-else
      class="bg-white rounded-lg shadow-md border border-gray-200 p-6 mb-6"
    >
      <BaseAlert
        type="success"
        class="mb-6"
      >
        <p class="font-semibold mb-1">
          ✅ Certificado cargado correctamente
        </p>
      </BaseAlert>

      <div class="bg-gray-50 rounded-lg p-6">
        <h3 class="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <span>📋</span>
          <span>Información del certificado:</span>
        </h3>

        <dl class="space-y-3">
          <div class="flex justify-between">
            <dt class="text-gray-600">
              CUIT:
            </dt>
            <dd class="font-medium text-gray-900">
              {{ certificadoInfo?.cuit }}
            </dd>
          </div>

          <div class="flex justify-between">
            <dt class="text-gray-600">
              Emitido:
            </dt>
            <dd class="font-medium text-gray-900">
              {{ certificadoInfo?.fechaEmision }}
            </dd>
          </div>

          <div class="flex justify-between">
            <dt class="text-gray-600">
              Vence:
            </dt>
            <dd class="font-medium text-gray-900">
              {{ certificadoInfo?.fechaVencimiento }}
            </dd>
          </div>

          <div class="flex justify-between">
            <dt class="text-gray-600">
              Días restantes:
            </dt>
            <dd class="font-medium text-green-600">
              {{ certificadoInfo?.diasRestantes }} días
            </dd>
          </div>
        </dl>
      </div>
    </div>

    <div class="flex justify-between">
      <BaseButton
        variant="secondary"
        :disabled="loading"
        @click="emit('prev')"
      >
        <ArrowLeftIcon class="mr-2 h-4 w-4" />
        <span>Anterior</span>
      </BaseButton>

      <BaseButton
        v-if="certificadoSubido"
        variant="primary"
        data-testid="cert-wizard-step4-next"
        @click="continuar"
      >
        Siguiente →
      </BaseButton>
    </div>
  </div>
</template>
