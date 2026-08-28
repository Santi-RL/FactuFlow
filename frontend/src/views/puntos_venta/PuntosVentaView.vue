<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { usePuntosVentaStore } from "@/stores/puntos_venta";
import { useEmpresaStore } from "@/stores/empresa";
import { useAuthStore } from "@/stores/auth";
import { useNotification } from "@/composables/useNotification";
import { arcaService } from "@/services/arca.service";
import type { PuntoVenta, PuntoVentaUpdate } from "@/types/punto_venta";
import { formatearFecha } from "@/composables/useFormatters";
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
  () => puntosVentaStore.syncing || puntosVentaStore.importing,
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
        (punto) => punto.puede_intentar_emision,
      )
    : puntosVentaStore.puntosVenta;
  return [...puntos].sort((a, b) => a.numero - b.numero);
});

const estadoTecnicoPunto = (row: PuntoVenta) => {
  if (row.bloqueado) {
    return {
      label: "Bloqueado en ARCA",
      detail: "El estado técnico impide emitir",
      variant: "danger" as const,
    };
  }

  if (row.fecha_baja) {
    return {
      label: "Dado de baja",
      detail: `Baja informada: ${formatearFechaVisible(row.fecha_baja)}`,
      variant: "danger" as const,
    };
  }

  if (!row.es_webservice) {
    return {
      label: "Otro sistema",
      detail: row.sistema || "No disponible mediante Web Services",
      variant: "default" as const,
    };
  }

  if (
    !row.ultima_comprobacion_arca_en &&
    row.elegibilidad_rece.estado_efectivo === "verificado_rece"
  ) {
    return {
      label: "Pendiente de ARCA",
      detail: "Se comprobará automáticamente antes de emitir",
      variant: "warning" as const,
    };
  }

  if (
    !row.activo &&
    row.elegibilidad_rece.estado_efectivo === "verificado_rece"
  ) {
    return {
      label: "Ausente en ARCA",
      detail: "La última comprobación no encontró este punto de venta",
      variant: "danger" as const,
    };
  }

  if (!row.activo) {
    return {
      label: "Inactivo",
      detail: "El estado técnico impide emitir",
      variant: "default" as const,
    };
  }

  return {
    label: "Web Services activo",
    detail: "Estado técnico disponible; RECE se valida por separado",
    variant: "success" as const,
  };
};

const MOTIVOS_RECE: Record<string, string> = {
  contexto_rece_ausente:
    "No existe evidencia RECE para el ambiente configurado.",
  revision_fiscal_obsoleta:
    "Los datos fiscales cambiaron después de la verificación.",
  punto_no_rece: "La evidencia vigente indica que el punto no es RECE.",
  elegibilidad_rece_no_verificada:
    "Todavía no se importó una constancia válida para este punto.",
};

const FUENTES_RECE: Record<string, string> = {
  migracion_legacy: "Migración de datos anteriores",
  alta_manual: "Alta manual",
  sincronizacion_wsfe: "Sincronización técnica con ARCA",
  constancia_arca_atestada: "Constancia productiva atestada",
  edicion: "Edición del punto de venta",
};

const formatearFechaVisible = (value: string): string => {
  const fechaArca = /^(\d{4})(\d{2})(\d{2})$/.exec(value.trim());
  if (fechaArca) {
    return formatearFecha(`${fechaArca[1]}-${fechaArca[2]}-${fechaArca[3]}`);
  }
  return formatearFecha(value);
};

const estadoUsoPunto = (row: PuntoVenta) => {
  if (row.usable_factuflow && row.comprobacion_arca_desactualizada) {
    return {
      label: "Comprobación recomendada",
      variant: "warning" as const,
    };
  }
  if (row.usable_factuflow) {
    return { label: "Listo para emitir", variant: "success" as const };
  }
  if (
    row.elegibilidad_rece.estado_efectivo === "verificado_rece" &&
    row.ultima_comprobacion_arca_en === null
  ) {
    return {
      label: "Pendiente de comprobar con ARCA",
      variant: "warning" as const,
    };
  }
  return { label: "Requiere atención", variant: "danger" as const };
};

const causaRecePunto = (row: PuntoVenta): string => {
  const elegibilidad = row.elegibilidad_rece;
  if (elegibilidad.motivo) {
    return (
      MOTIVOS_RECE[elegibilidad.motivo] ||
      "La acreditación RECE requiere revisión administrativa."
    );
  }
  return elegibilidad.estado_efectivo === "verificado_rece"
    ? "La constancia acredita este punto de venta sin vencimiento temporal."
    : "Importá una constancia válida para habilitar este punto de venta.";
};

const comprobacionArcaPunto = (row: PuntoVenta): string => {
  if (!row.ultima_comprobacion_arca_en) {
    return "Todavía no se comprobó el estado técnico con ARCA.";
  }
  const instanteUtc = /(?:Z|[+-]\d{2}:\d{2})$/i.test(
    row.ultima_comprobacion_arca_en,
  )
    ? row.ultima_comprobacion_arca_en
    : `${row.ultima_comprobacion_arca_en}Z`;
  const comprobadoEn = new Date(instanteUtc);
  const dias = Math.max(
    0,
    Math.floor((Date.now() - comprobadoEn.getTime()) / 86_400_000),
  );
  const antiguedad =
    dias === 0 ? "hoy" : `hace ${dias} día${dias === 1 ? "" : "s"}`;
  return `Comprobado con ARCA ${antiguedad} · ${formatearFechaVisible(row.ultima_comprobacion_arca_en)}`;
};

const procedenciaRecePunto = (row: PuntoVenta): string => {
  const { fuente, ambiente } = row.elegibilidad_rece;
  const fuenteVisible = fuente
    ? FUENTES_RECE[fuente] || "Procedencia administrativa"
    : "Sin procedencia registrada";
  const ambienteVisible =
    ambiente === "produccion" ? "Producción" : "Homologación";
  return `${fuenteVisible} · ${ambienteVisible}`;
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
  if (!esAdmin.value) {
    showWarning(
      "Acción reservada",
      "Solo un administrador puede comprobar puntos de venta con ARCA.",
    );
    return;
  }

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

    const fechaDocumento = resultado.documento_emitido_en
      ? ` Documento: ${formatearFechaVisible(resultado.documento_emitido_en)}.`
      : "";
    const detalleBase = `Detectados: ${resultado.total_constancia}. Creados: ${resultado.creados}. Actualizados: ${resultado.actualizados}. Omitidos: ${resultado.omitidos}. Desactivados por ausencia: ${resultado.desactivados_ausentes}.${fechaDocumento}`;
    const resumen = `${detalleBase} Acreditados por constancia: ${resultado.verificados_rece}. Pendientes de comprobar con ARCA: ${resultado.pendientes_comprobacion}. No compatibles: ${resultado.no_verificados_rece}.`;
    if (resultado.warnings.length > 0) {
      showWarning(
        "Constancia importada con observaciones",
        `${resumen} ${resultado.warnings.join(" ")}`,
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
          Importá una constancia una sola vez y dejá que FactuFlow compruebe el
          estado técnico con ARCA
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <BaseButton
          variant="secondary"
          :loading="puntosVentaStore.loading"
          :disabled="operacionAdministrativaEnCurso"
          @click="cargarDatos"
        >
          <ArrowPathIcon class="h-5 w-5 mr-2" />
          Actualizar
        </BaseButton>
        <BaseButton
          v-if="esAdmin"
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
      </div>
    </div>

    <BaseAlert
      v-if="esAdmin && !cargandoCertificados && !tieneCertificadoDisponible"
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
        <BaseButton variant="secondary" size="sm" @click="irACertificados">
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
      Podés consultar los puntos de venta y actualizar su nombre, domicilio y
      nombre fantasía. Solo un administrador puede comprobar con ARCA, importar
      constancias o modificar datos fiscales y técnicos.
    </BaseAlert>

    <BaseCard>
      <div
        class="px-6 py-4 border-b border-gray-200 bg-gray-50 text-sm text-gray-700"
      >
        <div
          class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
        >
          <p class="max-w-4xl">
            Importá el PDF de puntos de venta descargado de ARCA para acreditar
            el emisor activo. La constancia no vence; FactuFlow recomendará una
            nueva comprobación técnica después de 90 días y la hará
            automáticamente antes de emitir cuando sea necesario.
          </p>
          <label
            class="inline-flex items-center gap-2 whitespace-nowrap text-sm font-medium text-gray-700"
          >
            <input
              v-model="mostrarSoloElegibles"
              type="checkbox"
              class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Solo elegibles para emitir
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

        <template #cell-elegibilidad_rece="{ row }">
          <div class="flex flex-wrap items-center gap-2">
            <BaseBadge :variant="estadoUsoPunto(row).variant">
              {{ estadoUsoPunto(row).label }}
            </BaseBadge>
          </div>
          <p class="mt-1 max-w-72 whitespace-normal text-xs text-gray-700">
            {{ causaRecePunto(row) }}
          </p>
          <p class="mt-1 whitespace-normal text-xs text-gray-500">
            {{ comprobacionArcaPunto(row) }}
          </p>
          <p class="mt-1 whitespace-normal text-xs text-gray-500">
            {{ procedenciaRecePunto(row) }} · Revisión fiscal
            {{ row.revision_fiscal }}
          </p>
        </template>

        <template #cell-activo="{ row }">
          <BaseBadge :variant="estadoTecnicoPunto(row).variant">
            {{ estadoTecnicoPunto(row).label }}
          </BaseBadge>
          <p class="mt-1 text-xs text-gray-500 max-w-48 whitespace-normal">
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
