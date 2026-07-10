<script setup lang="ts">
import { PlusIcon } from "@heroicons/vue/24/outline";
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import type { Certificado, VerificacionResponse } from "@/types/certificado";
import certificadosService from "@/services/certificados.service";
import { useEmpresaStore } from "@/stores/empresa";
import { getEmpresaActivaIdForRequest } from "@/utils/empresa-activa-storage";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import BaseEmpty from "@/components/ui/BaseEmpty.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import CertificadoCard from "@/components/certificados/CertificadoCard.vue";
import ConfirmDialog from "@/components/common/ConfirmDialog.vue";

const router = useRouter();
const empresaStore = useEmpresaStore();

const certificados = ref<Certificado[]>([]);
const loading = ref(true);
const error = ref("");
const showConfirmDelete = ref(false);
const certificadoToDelete = ref<number | null>(null);
const certificadoToDeleteEmpresaId = ref<number | null>(null);
const verificandoId = ref<number | null>(null);
const resultadosVerificacion = ref<Record<number, VerificacionResponse>>({});
let cargarCertificadosRequestId = 0;

const esContextoEmisorActual = (empresaId: number | null) =>
  empresaId !== null &&
  empresaStore.empresaActivaId === empresaId &&
  getEmpresaActivaIdForRequest() === String(empresaId);

const certificadosActivos = computed(() =>
  certificados.value.filter((c) => c.activo),
);

const certificadosPorVencer = computed(() =>
  certificadosActivos.value.filter(
    (c) => c.estado === "por_vencer" || c.estado === "vencido",
  ),
);

const cargarCertificados = async () => {
  const requestId = ++cargarCertificadosRequestId;
  const empresaIdSolicitada = empresaStore.empresaActivaId;
  loading.value = true;
  error.value = "";

  if (!esContextoEmisorActual(empresaIdSolicitada)) {
    certificados.value = [];
    loading.value = false;
    return;
  }

  try {
    const resultado = await certificadosService.listar();
    if (
      requestId === cargarCertificadosRequestId &&
      esContextoEmisorActual(empresaIdSolicitada)
    ) {
      certificados.value = resultado;
    }
  } catch (err: any) {
    if (
      requestId === cargarCertificadosRequestId &&
      esContextoEmisorActual(empresaIdSolicitada)
    ) {
      error.value = "Error al cargar certificados";
      console.error(err);
    }
  } finally {
    if (requestId === cargarCertificadosRequestId) {
      loading.value = false;
    }
  }
};

const irAWizard = () => {
  router.push({ name: "certificado-wizard" });
};

const renovarCertificado = (id: number) => {
  router.push({
    name: "certificado-renovar",
    params: { id },
  });
};

const cerrarConfirmacionEliminar = () => {
  showConfirmDelete.value = false;
  certificadoToDelete.value = null;
  certificadoToDeleteEmpresaId.value = null;
};

const confirmarEliminar = (id: number) => {
  const empresaId = empresaStore.empresaActivaId;
  if (!esContextoEmisorActual(empresaId)) return;

  certificadoToDelete.value = id;
  certificadoToDeleteEmpresaId.value = empresaId;
  showConfirmDelete.value = true;
};

const verificarCertificado = async (id: number) => {
  const empresaIdSolicitada = empresaStore.empresaActivaId;
  if (!esContextoEmisorActual(empresaIdSolicitada)) return;

  verificandoId.value = id;
  error.value = "";

  try {
    const resultado = await certificadosService.verificarConexion(id);
    if (!esContextoEmisorActual(empresaIdSolicitada)) return;
    resultadosVerificacion.value = {
      ...resultadosVerificacion.value,
      [id]: resultado,
    };
  } catch (err: any) {
    if (!esContextoEmisorActual(empresaIdSolicitada)) return;
    resultadosVerificacion.value = {
      ...resultadosVerificacion.value,
      [id]: {
        exito: false,
        mensaje: "No se pudo completar la prueba de conexión",
        error:
          err?.response?.data?.detail || err?.message || "Error desconocido",
      },
    };
    console.error(err);
  } finally {
    if (esContextoEmisorActual(empresaIdSolicitada)) {
      verificandoId.value = null;
    }
  }
};

const eliminarCertificado = async () => {
  const certificadoId = certificadoToDelete.value;
  const empresaId = certificadoToDeleteEmpresaId.value;
  if (!certificadoId || !esContextoEmisorActual(empresaId)) {
    cerrarConfirmacionEliminar();
    return;
  }

  try {
    await certificadosService.eliminar(certificadoId);
    if (!esContextoEmisorActual(empresaId)) return;
    certificados.value = certificados.value.filter((c) => c.id !== certificadoId);
    cerrarConfirmacionEliminar();
  } catch (err: any) {
    if (!esContextoEmisorActual(empresaId)) return;
    error.value = "Error al eliminar certificado";
    console.error(err);
  }
};

onMounted(async () => {
  if (!empresaStore.empresaActivaId) {
    await empresaStore.inicializarEmpresaActiva();
    if (!empresaStore.empresaActivaId) {
      loading.value = false;
    }
    return;
  }

  await cargarCertificados();
});

watch(
  () => empresaStore.empresaActivaId,
  (empresaId, previousEmpresaId) => {
    if (empresaId === previousEmpresaId) return;

    cerrarConfirmacionEliminar();
    verificandoId.value = null;
    resultadosVerificacion.value = {};
    certificados.value = [];
    if (empresaId && esContextoEmisorActual(empresaId)) {
      cargarCertificados();
    } else {
      ++cargarCertificadosRequestId;
      loading.value = false;
    }
  },
);
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <div
      class="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <h1
          class="mb-2 text-3xl font-bold text-brand-ink"
          data-testid="page-title"
        >
          Certificados ARCA
        </h1>
        <p class="text-brand-slate">
          Gestioná tus certificados digitales para facturación electrónica
        </p>
      </div>

      <BaseButton
        variant="primary"
        class="flex items-center gap-2"
        data-testid="certificados-agregar"
        @click="irAWizard"
      >
        <PlusIcon class="h-5 w-5" />
        <span>Agregar certificado</span>
      </BaseButton>
    </div>

    <!-- Alerta de certificados por vencer -->
    <BaseAlert
      v-if="certificadosPorVencer.length > 0 && !loading"
      type="warning"
      class="mb-6"
    >
      <div class="flex items-start justify-between">
        <div>
          <p class="mb-1 font-semibold">
            {{ certificadosPorVencer.length }} certificado(s) necesita(n)
            atención
          </p>
          <p class="text-sm">
            Tenés certificados próximos a vencer o ya vencidos. Te recomendamos
            renovarlos pronto.
          </p>
        </div>
      </div>
    </BaseAlert>

    <!-- Error -->
    <BaseAlert
      v-if="error && !loading"
      type="error"
      class="mb-6"
    >
      {{ error }}
    </BaseAlert>

    <!-- Loading -->
    <div
      v-if="loading"
      class="flex justify-center py-12"
    >
      <BaseSpinner size="lg" />
    </div>

    <!-- Empty State -->
    <BaseEmpty
      v-else-if="certificadosActivos.length === 0"
      title="No tenés certificados configurados"
      message="Configurá tu primer certificado ARCA para comenzar a facturar electrónicamente"
    >
      <template #action>
        <BaseButton
          variant="primary"
          @click="irAWizard"
        >
          Configurar certificado
        </BaseButton>
      </template>
    </BaseEmpty>

    <!-- Grid de certificados -->
    <div
      v-else
      class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3"
    >
      <CertificadoCard
        v-for="certificado in certificadosActivos"
        :key="certificado.id"
        :certificado="certificado"
        :verificando="verificandoId === certificado.id"
        :resultado-verificacion="resultadosVerificacion[certificado.id] || null"
        @renovar="renovarCertificado"
        @eliminar="confirmarEliminar"
        @verificar="verificarCertificado"
      />
    </div>

    <!-- Confirm Delete Dialog -->
    <ConfirmDialog
      :show="showConfirmDelete"
      title="Eliminar certificado"
      message="¿Estás seguro que querés eliminar este certificado? Esta acción no se puede deshacer."
      confirm-text="Eliminar"
      cancel-text="Cancelar"
      variant="danger"
      @confirm="eliminarCertificado"
      @cancel="showConfirmDelete = false"
    />
  </div>
</template>
