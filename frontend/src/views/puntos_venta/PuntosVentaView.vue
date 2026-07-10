<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { usePuntosVentaStore } from "@/stores/puntos_venta";
import { useEmpresaStore } from "@/stores/empresa";
import { useNotification } from "@/composables/useNotification";
import { arcaService } from "@/services/arca.service";
import type { PuntoVenta, PuntoVentaUpdate } from "@/types/punto_venta";
import { getEmpresaActivaIdForRequest } from "@/utils/empresa-activa-storage";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseModal from "@/components/ui/BaseModal.vue";
import BaseTable from "@/components/ui/BaseTable.vue";
import BaseBadge from "@/components/ui/BaseBadge.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import {
  ArrowPathIcon,
  ArrowDownTrayIcon,
  PencilSquareIcon,
} from "@heroicons/vue/24/outline";

const router = useRouter();
const puntosVentaStore = usePuntosVentaStore();
const empresaStore = useEmpresaStore();
const { showSuccess, showError, showWarning } = useNotification();

const tieneCertificadoDisponible = ref(false);
const ambienteArcaActual = ref<"homologacion" | "produccion" | null>(null);
const cargandoCertificados = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);
const puntoEditando = ref<PuntoVenta | null>(null);
const puntoEditandoEmpresaId = ref<number | null>(null);
const guardandoEdicion = ref(false);
const editForm = ref<PuntoVentaUpdate>({});
const mostrarSoloHabilitados = ref(false);
let cargarDatosRequestId = 0;
let cargarCertificadosRequestId = 0;

const esSolicitudDelEmisorActual = (empresaIdSolicitada: number | null) =>
  empresaIdSolicitada !== null &&
  empresaStore.empresaActivaId === empresaIdSolicitada &&
  getEmpresaActivaIdForRequest() === String(empresaIdSolicitada);

const columns = [
  { key: "numero", label: "Numero", sortable: true },
  { key: "sistema", label: "Sistema", sortable: false },
  { key: "domicilio", label: "Domicilio", sortable: false },
  { key: "nombre_fantasia", label: "Nombre fantasia", sortable: false },
  { key: "activo", label: "Estado", sortable: false },
];

const puntosOrdenados = computed(() => {
  const puntos = mostrarSoloHabilitados.value
    ? puntosVentaStore.puntosVenta.filter((punto) => punto.usable_factuflow)
    : puntosVentaStore.puntosVenta;
  return [...puntos].sort((a, b) => a.numero - b.numero);
});

const estadoPunto = (row: PuntoVenta) => {
  if (row.usable_factuflow) {
    return {
      label: "Habilitado FactuFlow",
      detail: "Web Services activo",
      variant: "success" as const,
    };
  }

  if (row.bloqueado) {
    return {
      label: "Bloqueado en ARCA",
      detail: "No disponible para emitir",
      variant: "danger" as const,
    };
  }

  if (row.fecha_baja) {
    return {
      label: "Dado de baja",
      detail: row.fecha_baja,
      variant: "danger" as const,
    };
  }

  if (!row.es_webservice) {
    return {
      label: "Otro sistema",
      detail: row.sistema || "No usable por FactuFlow",
      variant: "default" as const,
    };
  }

  return {
    label: row.activo ? "Web Services activo" : "Inactivo",
    detail: row.activo
      ? "Revisar habilitacion ARCA"
      : "No disponible para emitir",
    variant: row.activo ? ("warning" as const) : ("default" as const),
  };
};

const cargarCertificados = async (
  empresaIdSolicitada = empresaStore.empresaActivaId,
) => {
  const requestId = ++cargarCertificadosRequestId;
  cargandoCertificados.value = true;
  if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) {
    tieneCertificadoDisponible.value = false;
    ambienteArcaActual.value = null;
    cargandoCertificados.value = false;
    return;
  }

  try {
    const status = await arcaService.getStatus();
    if (
      requestId === cargarCertificadosRequestId &&
      empresaStore.empresaActivaId === empresaIdSolicitada
    ) {
      ambienteArcaActual.value = status.ambiente;
      tieneCertificadoDisponible.value = status.certificado_disponible;
    }
  } catch (err: any) {
    if (
      requestId === cargarCertificadosRequestId &&
      empresaStore.empresaActivaId === empresaIdSolicitada
    ) {
      tieneCertificadoDisponible.value = false;
    }
  } finally {
    if (requestId === cargarCertificadosRequestId) {
      cargandoCertificados.value = false;
    }
  }
};

const limpiarDatosContexto = () => {
  puntosVentaStore.puntosVenta = [];
  tieneCertificadoDisponible.value = false;
  ambienteArcaActual.value = null;
};

const cargarDatos = async () => {
  const requestId = ++cargarDatosRequestId;
  const empresaIdSolicitada = empresaStore.empresaActivaId;
  if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) {
    limpiarDatosContexto();
    return;
  }

  try {
    await Promise.all([
      puntosVentaStore.fetchPuntosVenta(),
      cargarCertificados(empresaIdSolicitada),
    ]);
  } catch (err: any) {
    if (
      requestId === cargarDatosRequestId &&
      esSolicitudDelEmisorActual(empresaIdSolicitada)
    ) {
      showError("Error", "No se pudieron cargar los puntos de venta");
    }
  }
};

const irACertificados = () => {
  router.push("/certificados");
};

const sincronizar = async () => {
  if (!tieneCertificadoDisponible.value) {
    showWarning(
      "Certificado no disponible",
      `Cargá un certificado o restaurá sus archivos para el ambiente ${ambienteArcaActual.value || "actual"} antes de sincronizar`,
    );
    return;
  }

  const empresaIdSolicitada = empresaStore.empresaActivaId;

  try {
    const resultado = await puntosVentaStore.syncFromArca();
    if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) return;

    showSuccess(
      "Sincronizacion completa",
      `Total en ARCA: ${resultado.total_arca}. Nuevos: ${resultado.nuevos}. Existentes: ${resultado.existentes}.`,
    );
  } catch (err: any) {
    if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) return;

    const mensaje =
      err.response?.data?.detail || "No se pudo sincronizar con ARCA";
    showError("Error", mensaje);
  }
};

const seleccionarConstancia = () => {
  fileInputRef.value?.click();
};

const importarConstancia = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  try {
    const resultado = await puntosVentaStore.importarConstancia(file);
    showSuccess(
      "Constancia importada",
      `Detectados: ${resultado.total_constancia}. Creados: ${resultado.creados}. Actualizados: ${resultado.actualizados}.`,
    );
  } catch (err: any) {
    const mensaje =
      err.response?.data?.detail || "No se pudo importar la constancia";
    showError("Error", mensaje);
  } finally {
    input.value = "";
  }
};

const editarPunto = (punto: PuntoVenta) => {
  const empresaId = empresaStore.empresaActivaId;
  if (
    !esSolicitudDelEmisorActual(empresaId) ||
    punto.empresa_id !== empresaId
  ) {
    showWarning(
      "Emisor desactualizado",
      "Volvé a abrir el punto de venta desde el emisor activo.",
    );
    return;
  }

  puntoEditando.value = punto;
  puntoEditandoEmpresaId.value = empresaId;
  editForm.value = {
    numero: punto.numero,
    nombre: punto.nombre,
    sistema: punto.sistema,
    domicilio: punto.domicilio,
    nombre_fantasia: punto.nombre_fantasia,
    es_webservice: punto.es_webservice,
    bloqueado: punto.bloqueado,
    fecha_baja: punto.fecha_baja,
    fuente: punto.fuente,
    activo: punto.activo,
  };
};

const cerrarEditor = () => {
  puntoEditando.value = null;
  puntoEditandoEmpresaId.value = null;
  editForm.value = {};
};

const guardarEdicion = async () => {
  const punto = puntoEditando.value;
  const empresaId = puntoEditandoEmpresaId.value;
  if (
    !punto ||
    !esSolicitudDelEmisorActual(empresaId) ||
    punto.empresa_id !== empresaId
  ) {
    cerrarEditor();
    return;
  }

  guardandoEdicion.value = true;
  try {
    const payload = {
      ...editForm.value,
      numero: editForm.value.numero ? Number(editForm.value.numero) : undefined,
    };
    await puntosVentaStore.updatePuntoVenta(punto.id, payload);
    if (!esSolicitudDelEmisorActual(empresaId)) return;
    showSuccess(
      "Punto actualizado",
      "Los datos del punto de venta fueron guardados",
    );
    cerrarEditor();
  } catch (err: any) {
    if (!esSolicitudDelEmisorActual(empresaId)) return;
    const mensaje =
      err.response?.data?.detail || "No se pudo guardar el punto de venta";
    showError("Error", mensaje);
  } finally {
    if (esSolicitudDelEmisorActual(empresaId)) {
      guardandoEdicion.value = false;
    }
  }
};

onMounted(async () => {
  if (!empresaStore.empresaActivaId) {
    await empresaStore.inicializarEmpresaActiva();
    return;
  }

  await cargarDatos();
});

watch(
  () => empresaStore.empresaActivaId,
  (empresaId, previousEmpresaId) => {
    if (empresaId === previousEmpresaId) return;

    cerrarEditor();
    guardandoEdicion.value = false;
    limpiarDatosContexto();
    if (empresaId && esSolicitudDelEmisorActual(empresaId)) {
      cargarDatos();
    } else {
      ++cargarDatosRequestId;
      ++cargarCertificadosRequestId;
      cargandoCertificados.value = false;
    }
  },
);
</script>

<template>
  <div>
    <div
      class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6"
    >
      <div>
        <h1 class="text-3xl font-bold text-gray-900">
          Puntos de venta
        </h1>
        <p class="mt-2 text-gray-600">
          Administra y sincroniza los puntos de venta del emisor activo
        </p>
      </div>
      <div class="flex gap-2">
        <BaseButton
          variant="secondary"
          :loading="puntosVentaStore.loading"
          @click="cargarDatos"
        >
          <ArrowPathIcon class="h-5 w-5 mr-2" />
          Actualizar
        </BaseButton>
        <BaseButton
          :disabled="
            !tieneCertificadoDisponible ||
              puntosVentaStore.syncing ||
              cargandoCertificados
          "
          :loading="puntosVentaStore.syncing"
          @click="sincronizar"
        >
          <ArrowDownTrayIcon class="h-5 w-5 mr-2" />
          Sincronizar con ARCA
        </BaseButton>
        <input
          ref="fileInputRef"
          type="file"
          class="hidden"
          accept=".pdf"
          @change="importarConstancia"
        >
        <BaseButton
          variant="secondary"
          :loading="puntosVentaStore.syncing"
          @click="seleccionarConstancia"
        >
          Importar constancia
        </BaseButton>
      </div>
    </div>

    <BaseAlert
      v-if="!cargandoCertificados && !tieneCertificadoDisponible"
      type="warning"
      title="Certificado no disponible"
      :dismissible="false"
      class="mb-6"
    >
      <div
        class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <span>
          Para sincronizar, el certificado activo del ambiente
          {{ ambienteArcaActual || "actual" }} debe conservar sus archivos
          locales.
        </span>
        <BaseButton
          variant="secondary"
          size="sm"
          @click="irACertificados"
        >
          Ir a certificados
        </BaseButton>
      </div>
    </BaseAlert>

    <BaseCard>
      <div
        class="px-6 py-4 border-b border-gray-200 bg-gray-50 text-sm text-gray-700"
      >
        <div
          class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
        >
          <p class="max-w-4xl">
            `Sincronizar con ARCA` valida el estado tecnico de webservices.
            `Importar constancia` completa sistema, domicilio y nombre de
            fantasia desde el PDF de ARCA.
          </p>
          <label
            class="inline-flex items-center gap-2 whitespace-nowrap text-sm font-medium text-gray-700"
          >
            <input
              v-model="mostrarSoloHabilitados"
              type="checkbox"
              class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            >
            Solo habilitados FactuFlow
          </label>
        </div>
      </div>
      <BaseTable
        :columns="columns"
        :data="puntosOrdenados"
        :loading="puntosVentaStore.loading"
        empty-text="No hay puntos de venta registrados"
      >
        <template #cell-numero="{ value }">
          <span class="font-medium text-gray-900">
            {{ String(value).padStart(4, "0") }}
          </span>
        </template>

        <template #cell-nombre="{ value }">
          <span class="text-gray-600">{{ value || "-" }}</span>
        </template>

        <template #cell-sistema="{ value }">
          <span class="text-gray-700">{{ value || "-" }}</span>
        </template>

        <template #cell-domicilio="{ value }">
          <span class="text-gray-700 whitespace-normal">{{
            value || "-"
          }}</span>
        </template>

        <template #cell-nombre_fantasia="{ value }">
          <span class="text-gray-700">{{ value || "-" }}</span>
        </template>

        <template #cell-activo="{ row }">
          <BaseBadge :variant="estadoPunto(row).variant">
            {{ estadoPunto(row).label }}
          </BaseBadge>
          <p class="mt-1 text-xs text-gray-500 max-w-48 whitespace-normal">
            {{ estadoPunto(row).detail }}
          </p>
        </template>

        <template #actions="{ row }">
          <button
            class="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800"
            @click="editarPunto(row)"
          >
            <PencilSquareIcon class="h-4 w-4" />
            Editar
          </button>
        </template>
      </BaseTable>
    </BaseCard>

    <BaseModal
      :show="!!puntoEditando"
      title="Editar punto de venta"
      size="xl"
      @close="cerrarEditor"
    >
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <BaseInput
          v-model="editForm.numero"
          type="number"
          label="Numero"
        />
        <BaseInput
          v-model="editForm.nombre_fantasia"
          label="Nombre fantasia"
        />
        <BaseInput
          v-model="editForm.sistema"
          label="Sistema"
        />
        <BaseInput
          v-model="editForm.fecha_baja"
          label="Fecha de baja"
        />
        <div class="md:col-span-2">
          <BaseInput
            v-model="editForm.domicilio"
            label="Domicilio"
          />
        </div>
        <label class="flex items-center gap-2 text-sm text-gray-700">
          <input
            v-model="editForm.es_webservice"
            type="checkbox"
            class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          >
          Es punto Web Services
        </label>
        <label class="flex items-center gap-2 text-sm text-gray-700">
          <input
            v-model="editForm.bloqueado"
            type="checkbox"
            class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          >
          Bloqueado
        </label>
        <label class="flex items-center gap-2 text-sm text-gray-700">
          <input
            v-model="editForm.activo"
            type="checkbox"
            class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          >
          Activo
        </label>
      </div>

      <template #footer>
        <BaseButton
          variant="secondary"
          @click="cerrarEditor"
        >
          Cancelar
        </BaseButton>
        <BaseButton
          :loading="guardandoEdicion"
          @click="guardarEdicion"
        >
          Guardar cambios
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
