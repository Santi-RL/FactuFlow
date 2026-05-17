<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import type { Certificado, VerificacionResponse } from "@/types/certificado";
import certificadosService from "@/services/certificados.service";
import { useEmpresaStore } from "@/stores/empresa";
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
const verificandoId = ref<number | null>(null);
const resultadosVerificacion = ref<Record<number, VerificacionResponse>>({});
let cargarCertificadosRequestId = 0;

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
  loading.value = true;
  error.value = "";

  try {
    if (!empresaStore.empresaActivaId) {
      await empresaStore.inicializarEmpresaActiva();
    }
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    const resultado = await certificadosService.listar();
    if (
      requestId === cargarCertificadosRequestId &&
      empresaStore.empresaActivaId === empresaIdSolicitada
    ) {
      certificados.value = resultado;
    }
  } catch (err: any) {
    if (requestId === cargarCertificadosRequestId) {
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

const confirmarEliminar = (id: number) => {
  certificadoToDelete.value = id;
  showConfirmDelete.value = true;
};

const verificarCertificado = async (id: number) => {
  verificandoId.value = id;
  error.value = "";

  try {
    const resultado = await certificadosService.verificarConexion(id);
    resultadosVerificacion.value = {
      ...resultadosVerificacion.value,
      [id]: resultado,
    };
  } catch (err: any) {
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
    verificandoId.value = null;
  }
};

const eliminarCertificado = async () => {
  if (!certificadoToDelete.value) return;

  try {
    await certificadosService.eliminar(certificadoToDelete.value);
    certificados.value = certificados.value.filter(
      (c) => c.id !== certificadoToDelete.value,
    );
    showConfirmDelete.value = false;
    certificadoToDelete.value = null;
  } catch (err: any) {
    error.value = "Error al eliminar certificado";
    console.error(err);
  }
};

onMounted(() => {
  cargarCertificados();
});

watch(
  () => empresaStore.empresaActivaId,
  (empresaId, previousEmpresaId) => {
    if (empresaId && previousEmpresaId && empresaId !== previousEmpresaId) {
      cargarCertificados();
    }
  },
);
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <div class="flex justify-between items-center mb-8">
      <div>
        <h1
          class="text-3xl font-bold text-gray-900 mb-2"
          data-testid="page-title"
        >
          Certificados ARCA
        </h1>
        <p class="text-gray-600">
          Gestioná tus certificados digitales para facturación electrónica
        </p>
      </div>

      <BaseButton
        variant="primary"
        class="flex items-center gap-2"
        data-testid="certificados-agregar"
        @click="irAWizard"
      >
        <span>+</span>
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
          <p class="font-semibold mb-1">
            ⚠️ {{ certificadosPorVencer.length }} certificado(s) necesita(n)
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
    <BaseAlert v-if="error && !loading" type="error" class="mb-6">
      {{ error }}
    </BaseAlert>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-12">
      <BaseSpinner size="lg" />
    </div>

    <!-- Empty State -->
    <BaseEmpty
      v-else-if="certificadosActivos.length === 0"
      title="No tenés certificados configurados"
      message="Configurá tu primer certificado ARCA para comenzar a facturar electrónicamente"
    >
      <template #action>
        <BaseButton variant="primary" @click="irAWizard">
          Configurar certificado
        </BaseButton>
      </template>
    </BaseEmpty>

    <!-- Grid de certificados -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
