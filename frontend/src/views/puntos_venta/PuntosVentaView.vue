<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { usePuntosVentaStore } from "@/stores/puntos_venta";
import { useEmpresaStore } from "@/stores/empresa";
import { useAuthStore } from "@/stores/auth";
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
import { ArrowDownTrayIcon, PencilSquareIcon } from "@heroicons/vue/24/outline";

const router = useRouter();
const puntosVentaStore = usePuntosVentaStore();
const empresaStore = useEmpresaStore();
const authStore = useAuthStore();
const { showSuccess, showError, showWarning } = useNotification();

const tieneCertificadoDisponible = ref(false);
const ambienteArcaActual = ref<"homologacion" | "produccion" | null>(null);
const cargandoCertificados = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);
const puntoEditando = ref<PuntoVenta | null>(null);
const puntoEditandoEmpresaId = ref<number | null>(null);
const guardandoEdicion = ref(false);
const editForm = ref<PuntoVentaUpdate>({});
const mostrarSoloElegibles = ref(false);
let cargarDatosRequestId = 0;
let cargarCertificadosRequestId = 0;

const esAdmin = computed(() => Boolean(authStore.user?.es_admin));
const operacionAdministrativaEnCurso = computed(
  () =>
    puntosVentaStore.syncing ||
    puntosVentaStore.importing ||
    puntosVentaStore.preparingForSelection,
);
const esSolicitudDelEmisorActual = (empresaIdSolicitada: number | null) =>
  empresaIdSolicitada !== null &&
  empresaStore.empresaActivaId === empresaIdSolicitada &&
  getEmpresaActivaIdForRequest() === String(empresaIdSolicitada);

const columns = [
  { key: "numero", label: "Número", sortable: true },
  { key: "sistema", label: "Sistema", sortable: false },
  { key: "domicilio", label: "Domicilio", sortable: false },
  { key: "nombre_fantasia", label: "Nombre fantasía", sortable: false },
  {
    key: "elegibilidad_rece",
    label: "Estado para emitir",
    sortable: false,
  },
  { key: "activo", label: "Estado técnico", sortable: false },
];

const puntosOrdenados = computed(() => {
  const puntos = mostrarSoloElegibles.value
    ? puntosVentaStore.puntosVenta.filter(
        (punto) => punto.seleccionable_para_emision,
      )
    : puntosVentaStore.puntosVenta;
  return [...puntos].sort((a, b) => a.numero - b.numero);
});

const estadoTecnicoPunto = (row: PuntoVenta) => {
  if (!row.es_webservice) {
    return {
      label: "Otro sistema",
      detail: "",
      variant: "default" as const,
    };
  }

  if (row.bloqueado) {
    return {
      label: "Bloqueado en ARCA",
      detail: "Regularizá el punto en ARCA y seleccioná Comprobar con ARCA.",
      variant: "danger" as const,
    };
  }

  if (row.fecha_baja) {
    return {
      label: "Dado de baja",
      detail: "Reactivá el punto en ARCA o elegí otro y volvé a comprobar.",
      variant: "danger" as const,
    };
  }

  if (
    row.elegibilidad_rece.estado_efectivo === "verificado_rece" &&
    row.comprobacion_arca_desactualizada
  ) {
    return {
      label: "Pendiente de comprobar",
      detail: "Seleccioná Comprobar con ARCA para volver a intentar.",
      variant: "warning" as const,
    };
  }

  if (
    !row.activo &&
    row.elegibilidad_rece.estado_efectivo === "verificado_rece"
  ) {
    return {
      label: "Ausente en ARCA",
      detail: "Verificá el punto en ARCA y seleccioná Comprobar con ARCA.",
      variant: "danger" as const,
    };
  }

  if (!row.activo) {
    return {
      label: "Inactivo",
      detail: "Habilitá el punto en ARCA y volvé a comprobar.",
      variant: "default" as const,
    };
  }

  return {
    label: "Web Services activo",
    detail: "",
    variant: "success" as const,
  };
};

const estadoUsoPunto = (row: PuntoVenta) => {
  if (!row.es_webservice) {
    return {
      label: "No disponible en FactuFlow",
      variant: "default" as const,
    };
  }
  if (row.seleccionable_para_emision) {
    return { label: "Listo para emitir", variant: "success" as const };
  }
  if (row.elegibilidad_rece.estado_efectivo === "no_rece") {
    return { label: "No disponible para emitir", variant: "danger" as const };
  }
  if (row.elegibilidad_rece.estado_efectivo !== "verificado_rece") {
    return {
      label: "Falta validar",
      variant: "warning" as const,
    };
  }
  if (row.bloqueado || row.fecha_baja) {
    return { label: "No disponible para emitir", variant: "danger" as const };
  }
  if (row.comprobacion_arca_desactualizada) {
    return { label: "Comprobación necesaria", variant: "warning" as const };
  }
  if (!row.activo) {
    return { label: "No disponible para emitir", variant: "danger" as const };
  }
  return { label: "Comprobación necesaria", variant: "warning" as const };
};

const causaRecePunto = (row: PuntoVenta): string => {
  if (
    row.es_webservice &&
    row.elegibilidad_rece.estado_efectivo === "no_rece"
  ) {
    return "Regularizá el punto en ARCA e importá una nueva constancia.";
  }
  if (
    row.es_webservice &&
    row.elegibilidad_rece.estado_efectivo !== "verificado_rece"
  ) {
    return "Importá una constancia de puntos de venta de ARCA.";
  }
  return "";
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
      puntosVentaStore.prepareForSelection(),
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
      `Cargá un certificado o restaurá sus archivos para el ambiente ${ambienteArcaActual.value || "actual"} antes de comprobar`,
    );
    return;
  }

  const empresaIdSolicitada = empresaStore.empresaActivaId;

  try {
    const resultado = await puntosVentaStore.syncFromArca();
    if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) return;

    showSuccess(
      "Comprobación completa",
      `Total en ARCA: ${resultado.total_arca}. Nuevos: ${resultado.nuevos}. Existentes: ${resultado.existentes}. Actualizados: ${resultado.actualizados}. Desactivados por ausencia: ${resultado.desactivados_ausentes}.`,
    );
  } catch (err: any) {
    if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) return;

    const mensaje =
      err.response?.data?.detail || "No se pudo comprobar con ARCA";
    showError("Error", mensaje);
  }
};

const seleccionarConstancia = () => {
  if (!esAdmin.value) {
    showWarning(
      "Acción reservada",
      "Solo un administrador puede importar constancias de puntos de venta.",
    );
    return;
  }
  fileInputRef.value?.click();
};

const prepararImportacionConstancia = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !esAdmin.value) return;

  const empresaIdSolicitada = empresaStore.empresaActivaId;
  if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) {
    return;
  }

  if (ambienteArcaActual.value !== "produccion") {
    showWarning(
      "Acreditación no disponible",
      "La acreditación RECE mediante constancia solo está disponible en el ambiente de producción.",
    );
    return;
  }

  try {
    const resultado = await puntosVentaStore.importarConstancia(file);
    if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) return;

    const resumen = `Listos para emitir: ${resultado.listos_para_emitir}. No disponibles en FactuFlow: ${resultado.no_disponibles_factuflow}. Requieren revisión: ${resultado.requieren_revision}.`;
    if (resultado.warnings.length > 0) {
      showWarning(
        "Constancia importada con observaciones",
        `${resumen} Revisá los puntos que requieren una acción.`,
      );
    } else {
      showSuccess("Constancia importada", resumen);
    }
  } catch (err: any) {
    if (!esSolicitudDelEmisorActual(empresaIdSolicitada)) return;

    const mensaje =
      err.response?.data?.detail || "No se pudo importar la constancia";
    showError("Error", mensaje);
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
    const payload: PuntoVentaUpdate = {
      nombre: editForm.value.nombre,
      domicilio: editForm.value.domicilio,
      nombre_fantasia: editForm.value.nombre_fantasia,
    };
    if (esAdmin.value) {
      Object.assign(payload, {
        numero: editForm.value.numero
          ? Number(editForm.value.numero)
          : undefined,
        sistema: editForm.value.sistema,
        es_webservice: editForm.value.es_webservice,
        bloqueado: editForm.value.bloqueado,
        fecha_baja: editForm.value.fecha_baja,
        activo: editForm.value.activo,
      });
    }
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
        <h1 class="text-3xl font-bold text-gray-900">Puntos de venta</h1>
        <p class="mt-2 text-gray-600">
          Elegí un punto que figure como listo para emitir.
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <input
          v-if="esAdmin"
          ref="fileInputRef"
          type="file"
          class="hidden"
          accept=".pdf"
          @change="prepararImportacionConstancia"
        />
        <BaseButton
          v-if="esAdmin"
          variant="secondary"
          :disabled="operacionAdministrativaEnCurso"
          :loading="puntosVentaStore.importing"
          @click="seleccionarConstancia"
        >
          Importar constancia
        </BaseButton>
        <BaseButton
          :disabled="
            !tieneCertificadoDisponible ||
            operacionAdministrativaEnCurso ||
            cargandoCertificados
          "
          :loading="puntosVentaStore.syncing"
          @click="sincronizar"
        >
          <ArrowDownTrayIcon class="h-5 w-5 mr-2" />
          Comprobar con ARCA
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
          Para comprobar con ARCA, el certificado activo del ambiente
          {{ ambienteArcaActual || "actual" }} debe conservar sus archivos
          locales.
        </span>
        <BaseButton
          v-if="esAdmin"
          variant="secondary"
          size="sm"
          @click="irACertificados"
        >
          Ir a certificados
        </BaseButton>
      </div>
    </BaseAlert>

    <BaseAlert
      v-if="!esAdmin"
      type="info"
      title="Permisos de usuario"
      :dismissible="false"
      class="mb-6"
    >
      Podés consultar y comprobar puntos de venta con ARCA. Solo un
      administrador puede importar constancias o modificar datos fiscales.
    </BaseAlert>

    <BaseAlert
      v-if="puntosVentaStore.preparationError"
      type="warning"
      :dismissible="false"
      class="mb-6"
    >
      {{ puntosVentaStore.preparationError }}
    </BaseAlert>

    <BaseCard>
      <div
        class="px-6 py-4 border-b border-gray-200 bg-gray-50 text-sm text-gray-700"
      >
        <div
          class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
        >
          <p class="font-semibold text-gray-900">
            {{ puntosVentaStore.puntosVenta.length }}
            {{
              puntosVentaStore.puntosVenta.length === 1
                ? "punto de venta"
                : "puntos de venta"
            }}
          </p>
          <label
            class="inline-flex items-center gap-2 whitespace-nowrap text-sm font-medium text-gray-700"
          >
            <input
              v-model="mostrarSoloElegibles"
              type="checkbox"
              class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Mostrar sólo los disponibles
          </label>
        </div>
      </div>
      <BaseTable
        :columns="columns"
        :data="puntosOrdenados"
        :loading="
          puntosVentaStore.loading || puntosVentaStore.preparingForSelection
        "
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

        <template #cell-elegibilidad_rece="{ row }">
          <div class="flex flex-wrap items-center gap-2">
            <BaseBadge :variant="estadoUsoPunto(row).variant">
              {{ estadoUsoPunto(row).label }}
            </BaseBadge>
          </div>
          <p
            v-if="causaRecePunto(row)"
            class="mt-1 max-w-72 whitespace-normal text-xs text-gray-700"
          >
            {{ causaRecePunto(row) }}
          </p>
        </template>

        <template #cell-activo="{ row }">
          <BaseBadge :variant="estadoTecnicoPunto(row).variant">
            {{ estadoTecnicoPunto(row).label }}
          </BaseBadge>
          <p
            v-if="estadoTecnicoPunto(row).detail"
            class="mt-1 text-xs text-gray-500 max-w-48 whitespace-normal"
          >
            {{ estadoTecnicoPunto(row).detail }}
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
      :title="
        esAdmin
          ? 'Editar punto de venta'
          : 'Editar datos descriptivos del punto'
      "
      size="xl"
      @close="cerrarEditor"
    >
      <BaseAlert
        v-if="esAdmin"
        type="warning"
        title="Cambio fiscal"
        :dismissible="false"
        class="mb-5"
      >
        Los cambios fiscales o técnicos invalidan la acreditación RECE vigente
        hasta una nueva verificación.
      </BaseAlert>
      <BaseAlert
        v-else
        type="info"
        title="Edición descriptiva"
        :dismissible="false"
        class="mb-5"
      >
        Tu permiso permite modificar solo nombre, domicilio y nombre fantasía.
      </BaseAlert>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <BaseInput v-model="editForm.nombre" label="Nombre" />
        <BaseInput v-model="editForm.nombre_fantasia" label="Nombre fantasía" />
        <div class="md:col-span-2">
          <BaseInput v-model="editForm.domicilio" label="Domicilio" />
        </div>
        <template v-if="esAdmin">
          <BaseInput v-model="editForm.numero" type="number" label="Número" />
          <BaseInput v-model="editForm.sistema" label="Sistema" />
          <BaseInput
            v-model="editForm.fecha_baja"
            label="Fecha de baja (DD/MM/AAAA o AAAA-MM-DD)"
          />
          <div class="hidden md:block" />
          <label class="flex items-center gap-2 text-sm text-gray-700">
            <input
              v-model="editForm.es_webservice"
              type="checkbox"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Es punto Web Services
          </label>
          <label class="flex items-center gap-2 text-sm text-gray-700">
            <input
              v-model="editForm.bloqueado"
              type="checkbox"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Bloqueado
          </label>
          <label class="flex items-center gap-2 text-sm text-gray-700">
            <input
              v-model="editForm.activo"
              type="checkbox"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Activo
          </label>
        </template>
      </div>

      <template #footer>
        <BaseButton variant="secondary" @click="cerrarEditor">
          Cancelar
        </BaseButton>
        <BaseButton :loading="guardandoEdicion" @click="guardarEdicion">
          Guardar cambios
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
