<script setup lang="ts">
import { computed, onMounted, ref, type Component } from "vue";
import {
  ArchiveBoxIcon,
  ArrowDownTrayIcon,
  CheckCircleIcon,
  CircleStackIcon,
  CloudIcon,
  ClockIcon,
  CpuChipIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  KeyIcon,
  ServerStackIcon,
  ShieldCheckIcon,
  TrashIcon,
} from "@heroicons/vue/24/outline";

import ConfirmDialog from "@/components/common/ConfirmDialog.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseBadge from "@/components/ui/BaseBadge.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import { useNotification } from "@/composables/useNotification";
import almacenamientoService from "@/services/almacenamiento.service";
import { arcaService, type ArcaStatus } from "@/services/arca.service";
import sistemaService, {
  type SistemaHealthResponse,
} from "@/services/sistema.service";
import type {
  AlmacenamientoItem,
  AlmacenamientoResumen,
  ExportacionAlmacenamiento,
  LoteCompactable,
} from "@/types/almacenamiento";

const { showError, showSuccess } = useNotification();

type SistemaTab = "estado" | "almacenamiento";
type EstadoOperativo =
  | "correcto"
  | "necesita_atencion"
  | "critico"
  | "no_disponible";

interface EstadoSistemaItem {
  id: string;
  titulo: string;
  descripcion: string;
  detalle: string;
  estado: EstadoOperativo;
  icon: Component;
  accion?: "probar-arca";
}

interface SoporteOperativoItem {
  id: string;
  caso: string;
  revisar: string;
  accion: string;
  detenerse: string;
}

interface DatoSoporteItem {
  id: string;
  etiqueta: string;
  detalle: string;
}

const activeTab = ref<SistemaTab>("estado");
const resumen = ref<AlmacenamientoResumen | null>(null);
const lotes = ref<LoteCompactable[]>([]);
const logs = ref<AlmacenamientoItem[]>([]);
const temporales = ref<AlmacenamientoItem[]>([]);
const certificadosHuerfanos = ref<AlmacenamientoItem[]>([]);
const exportacion = ref<ExportacionAlmacenamiento | null>(null);
const loading = ref(false);
const creandoExportacion = ref(false);
const descargando = ref(false);
const liberando = ref(false);
const limpiandoCertificados = ref(false);
const error = ref("");
const mostrarConfirmacionLiberacion = ref(false);
const mostrarConfirmacionCertificados = ref(false);
const estadoLoading = ref(false);
const almacenamientoInicializado = ref(false);
const almacenamientoResumenError = ref("");
const backendHealth = ref<SistemaHealthResponse | null>(null);
const backendHealthError = ref("");
const databaseHealth = ref<SistemaHealthResponse | null>(null);
const databaseHealthError = ref("");
const arcaStatus = ref<ArcaStatus | null>(null);
const arcaStatusError = ref("");
const arcaProbe = ref<any | null>(null);
const arcaProbeError = ref("");
const arcaProbeLoading = ref(false);
const ultimaActualizacionEstado = ref<string | null>(null);

const selectedLotes = ref<number[]>([]);
const selectedLogs = ref<string[]>([]);
const selectedTemporales = ref<string[]>([]);
const selectedCertificados = ref<string[]>([]);

const totalSeleccionado = computed(
  () =>
    selectedLotes.value.length +
    selectedLogs.value.length +
    selectedTemporales.value.length,
);

const hayExportacionDescargada = computed(
  () => exportacion.value?.estado === "descargada" || !!exportacion.value?.downloaded_at,
);

const categoriasOrdenadas = computed(() => resumen.value?.categorias || []);
const emisoresOrdenados = computed(() => resumen.value?.emisores || []);
const actualizando = computed(() => loading.value || estadoLoading.value);

const metricas = computed(() => [
  {
    label: "Uso medido",
    value: formatBytes(resumen.value?.total_bytes_usados || 0),
    icon: CircleStackIcon,
  },
  {
    label: "Recuperable",
    value: formatBytes(resumen.value?.total_bytes_recuperables || 0),
    icon: ArchiveBoxIcon,
  },
  {
    label: "Límite configurado",
    value: resumen.value?.storage_limit_bytes
      ? formatBytes(resumen.value.storage_limit_bytes)
      : "Sin límite",
    icon: ServerStackIcon,
  },
  {
    label: "Libre en disco",
    value: resumen.value?.disk_free_bytes
      ? formatBytes(resumen.value.disk_free_bytes)
      : "No disponible",
    icon: ShieldCheckIcon,
  },
]);

const certificadoDiasRestantes = computed(() => {
  const vencimiento = arcaStatus.value?.certificado_vencimiento;
  if (!vencimiento) return null;
  const diffMs = new Date(vencimiento).getTime() - Date.now();
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
});

const certificadoEstado = computed<EstadoOperativo>(() => {
  if (!arcaStatus.value) return "no_disponible";
  if (!arcaStatus.value.certificado_activo) return "no_disponible";
  if (!arcaStatus.value.certificado_disponible) return "no_disponible";
  const dias = certificadoDiasRestantes.value;
  if (dias !== null && dias <= 0) return "no_disponible";
  if (dias !== null && dias <= 30) return "necesita_atencion";
  return "correcto";
});

const certificadoDescripcion = computed(() => {
  if (!arcaStatus.value) return "No se pudo leer el emisor activo";
  return `Ambiente ${arcaStatus.value.ambiente}`;
});

const certificadoDetalle = computed(() => {
  if (arcaStatusError.value) return arcaStatusError.value;
  if (!arcaStatus.value) return "Sin datos de certificado.";
  if (!arcaStatus.value.certificado_activo) {
    return "No hay certificado activo para el ambiente configurado.";
  }
  if (!arcaStatus.value.certificado_disponible) {
    return "El certificado activo no tiene disponibles sus archivos locales.";
  }
  const vencimiento = formatDateTime(arcaStatus.value.certificado_vencimiento);
  const dias = certificadoDiasRestantes.value;
  const diasTexto = dias === null ? "" : `, ${dias} días restantes`;
  return `${arcaStatus.value.certificado_nombre || "Certificado activo"} · vence ${vencimiento}${diasTexto}`;
});

const arcaConexionEstado = computed<EstadoOperativo>(() => {
  if (arcaProbe.value?.status === "ok") return "correcto";
  if (arcaProbeError.value) return "no_disponible";
  return "necesita_atencion";
});

const arcaConexionDetalle = computed(() => {
  if (arcaProbe.value?.message) return arcaProbe.value.message;
  if (arcaProbeError.value) return arcaProbeError.value;
  return "No se prueba automáticamente para evitar llamadas externas sin acción del usuario.";
});

const almacenamientoEstado = computed<EstadoOperativo>(() => {
  if (resumen.value) return resumen.value.estado;
  if (loading.value) return "necesita_atencion";
  return "no_disponible";
});

const almacenamientoDetalle = computed(() => {
  if (resumen.value) {
    return `${formatBytes(resumen.value.total_bytes_usados)} usados · ${formatBytes(
      resumen.value.total_bytes_recuperables,
    )} recuperables`;
  }
  if (almacenamientoResumenError.value) {
    return almacenamientoResumenError.value;
  }
  return "Sin resumen de almacenamiento disponible.";
});

const estadoSistemaItems = computed<EstadoSistemaItem[]>(() => [
  {
    id: "backend",
    titulo: "Aplicación",
    descripcion: "API de FactuFlow",
    detalle: backendHealth.value?.message || backendHealthError.value,
    estado: backendHealth.value ? "correcto" : "no_disponible",
    icon: ServerStackIcon,
  },
  {
    id: "base-datos",
    titulo: "Base de datos",
    descripcion: "Consulta mínima de disponibilidad",
    detalle: databaseHealth.value?.message || databaseHealthError.value,
    estado: databaseHealth.value ? "correcto" : "no_disponible",
    icon: CircleStackIcon,
  },
  {
    id: "certificado",
    titulo: "Certificado del emisor",
    descripcion: certificadoDescripcion.value,
    detalle: certificadoDetalle.value,
    estado: certificadoEstado.value,
    icon: KeyIcon,
  },
  {
    id: "arca-conexion",
    titulo: "Conexión ARCA",
    descripcion: "Prueba manual contra el ambiente configurado",
    detalle: arcaConexionDetalle.value,
    estado: arcaConexionEstado.value,
    icon: CloudIcon,
    accion: "probar-arca",
  },
  {
    id: "almacenamiento",
    titulo: "Almacenamiento",
    descripcion: "Uso medido y espacio recuperable",
    detalle: almacenamientoDetalle.value,
    estado: almacenamientoEstado.value,
    icon: ArchiveBoxIcon,
  },
  {
    id: "worker-lotes",
    titulo: "Worker de lotes",
    descripcion: "Procesamiento en segundo plano",
    detalle:
      "Falta un healthcheck dedicado. Si un lote no avanza, revisar el detalle del lote y los logs de soporte.",
    estado: "necesita_atencion",
    icon: CpuChipIcon,
  },
  {
    id: "logs",
    titulo: "Logs de soporte",
    descripcion: "Acceso operativo seguro",
    detalle:
      "En local se accede desde el icono del tray. En VPS, usar la documentación privada del servidor.",
    estado: "necesita_atencion",
    icon: DocumentTextIcon,
  },
  {
    id: "backup",
    titulo: "Último backup",
    descripcion: "Evidencia de recuperación",
    detalle:
      "No hay señal automática en la aplicación. La clave real del backup cifrado y la política de retención siguen pendientes.",
    estado: "necesita_atencion",
    icon: ClockIcon,
  },
]);

const soporteOperativoItems: SoporteOperativoItem[] = [
  {
    id: "app-caida",
    caso: "La aplicación no responde",
    revisar: "Estado general, Aplicación y Base de datos.",
    accion:
      "En local, reiniciar servicios desde el icono del tray. En VPS, usar el runbook privado del servidor.",
    detenerse:
      "No repetir una emisión si la pantalla quedó esperando una respuesta fiscal.",
  },
  {
    id: "arca-certificado",
    caso: "ARCA o certificado con error",
    revisar: "Certificado del emisor, ambiente ARCA y prueba manual de conexión.",
    accion:
      "Verificar certificado activo, vencimiento y autorización WSFE antes de emitir.",
    detenerse: "No solicitar CAE mientras ARCA o el certificado figuren no disponibles.",
  },
  {
    id: "lote-detenido",
    caso: "Lote detenido, parcial o incierto",
    revisar: "Detalle del lote, estado visible y logs de soporte del entorno.",
    accion:
      "Si el lote requiere reconciliación, consultar evidencia segura antes de reintentar.",
    detenerse: "No reintentar automáticamente si pudo existir una respuesta de ARCA.",
  },
  {
    id: "almacenamiento-backup",
    caso: "Almacenamiento o backup pendiente",
    revisar: "Uso recuperable, resguardo ZIP y última evidencia privada de backup.",
    accion:
      "Descargar y verificar el resguardo antes de liberar espacio no vital.",
    detenerse: "No limpiar temporales, logs o lotes sin resguardo descargado.",
  },
];

const datosSoporteItems: DatoSoporteItem[] = [
  {
    id: "entorno",
    etiqueta: "Entorno y versión",
    detalle:
      "Local, VPS o copia de prueba; commit, tag o fecha de instalación si se conoce.",
  },
  {
    id: "emisor",
    etiqueta: "Emisor activo",
    detalle:
      "Razón social o referencia interna. No copiar CUIT completo en documentación pública.",
  },
  {
    id: "recurso",
    etiqueta: "Recurso afectado",
    detalle: "Pantalla, lote, comprobante, certificado, backup o acción iniciada.",
  },
  {
    id: "estado",
    etiqueta: "Estado visible",
    detalle:
      "Etiqueta actual en pantalla: Correcto, Necesita atención, No disponible o estado del lote.",
  },
  {
    id: "arca",
    etiqueta: "ARCA",
    detalle:
      "Indicar si se presionó Emitir, Reintentar, Reconciliar, Sincronizar o Probar conexión.",
  },
  {
    id: "evidencia",
    etiqueta: "Evidencia privada",
    detalle:
      "Logs, captura o consulta segura guardada fuera de Git y fuera de documentación pública.",
  },
];

const estadoGeneral = computed<EstadoOperativo>(() => {
  if (estadoSistemaItems.value.some((item) => item.estado === "no_disponible")) {
    return "no_disponible";
  }
  if (estadoSistemaItems.value.some((item) => item.estado === "critico")) {
    return "critico";
  }
  if (
    estadoSistemaItems.value.some((item) => item.estado === "necesita_atencion")
  ) {
    return "necesita_atencion";
  }
  return "correcto";
});

const estadoPrincipal = computed<EstadoOperativo>(() =>
  activeTab.value === "estado"
    ? estadoGeneral.value
    : resumen.value?.estado || "no_disponible",
);
const cargarDatos = async () => {
  loading.value = true;
  error.value = "";
  try {
    const resumenResponse = await almacenamientoService.resumen();
    resumen.value = resumenResponse;
    almacenamientoResumenError.value = "";

    const [lotesResponse, logsResponse, temporalesResponse, certificadosResponse] =
      await Promise.all([
        almacenamientoService.lotesCompactables(),
        almacenamientoService.logs(),
        almacenamientoService.temporales(),
        almacenamientoService.certificadosHuerfanos(),
      ]);
    lotes.value = lotesResponse;
    logs.value = logsResponse;
    temporales.value = temporalesResponse;
    certificadosHuerfanos.value = certificadosResponse;
    almacenamientoInicializado.value = true;
    limpiarSeleccionesAusentes();
  } catch (err: any) {
    error.value =
      err.response?.data?.detail || "No se pudo cargar el almacenamiento.";
  } finally {
    loading.value = false;
  }
};

const cargarEstadoSistema = async () => {
  estadoLoading.value = true;
  backendHealthError.value = "";
  databaseHealthError.value = "";
  arcaStatusError.value = "";
  almacenamientoResumenError.value = "";

  const [backendResult, databaseResult, arcaResult, resumenResult] =
    await Promise.allSettled([
      sistemaService.health(),
      sistemaService.databaseHealth(),
      arcaService.getStatus(),
      almacenamientoService.resumen(),
    ]);

  if (backendResult.status === "fulfilled") {
    backendHealth.value = backendResult.value;
  } else {
    backendHealth.value = null;
    backendHealthError.value = getErrorMessage(
      backendResult.reason,
      "No se pudo consultar la API.",
    );
  }

  if (databaseResult.status === "fulfilled") {
    databaseHealth.value = databaseResult.value;
  } else {
    databaseHealth.value = null;
    databaseHealthError.value = getErrorMessage(
      databaseResult.reason,
      "No se pudo consultar la base de datos.",
    );
  }

  if (arcaResult.status === "fulfilled") {
    arcaStatus.value = arcaResult.value;
  } else {
    arcaStatus.value = null;
    arcaStatusError.value = getErrorMessage(
      arcaResult.reason,
      "No se pudo leer el estado ARCA local.",
    );
  }

  if (resumenResult.status === "fulfilled") {
    resumen.value = resumenResult.value;
  } else {
    resumen.value = null;
    almacenamientoResumenError.value = getErrorMessage(
      resumenResult.reason,
      "No se pudo consultar el resumen de almacenamiento.",
    );
  }

  ultimaActualizacionEstado.value = new Date().toISOString();
  estadoLoading.value = false;
};

const actualizarTodo = async () => {
  if (activeTab.value === "almacenamiento") {
    await Promise.all([cargarEstadoSistema(), cargarDatos()]);
    return;
  }
  await cargarEstadoSistema();
};

const activarTab = (tab: SistemaTab) => {
  activeTab.value = tab;
  if (
    tab === "almacenamiento" &&
    !almacenamientoInicializado.value &&
    !loading.value
  ) {
    void cargarDatos();
  }
};

const probarConexionArca = async () => {
  arcaProbeLoading.value = true;
  arcaProbeError.value = "";
  arcaProbe.value = null;
  try {
    arcaProbe.value = await arcaService.testConnection();
    showSuccess("Conexión ARCA verificada", arcaProbe.value?.message);
  } catch (err: any) {
    arcaProbeError.value = getErrorMessage(
      err,
      "No se pudo probar la conexión con ARCA.",
    );
    showError("No se pudo conectar con ARCA", arcaProbeError.value);
  } finally {
    arcaProbeLoading.value = false;
  }
};
const limpiarSeleccionesAusentes = () => {
  const loteIds = new Set(lotes.value.map((item) => item.id));
  const logIds = new Set(logs.value.map((item) => item.id));
  const temporalIds = new Set(temporales.value.map((item) => item.id));
  const certIds = new Set(certificadosHuerfanos.value.map((item) => item.id));
  selectedLotes.value = selectedLotes.value.filter((id) => loteIds.has(id));
  selectedLogs.value = selectedLogs.value.filter((id) => logIds.has(id));
  selectedTemporales.value = selectedTemporales.value.filter((id) =>
    temporalIds.has(id),
  );
  selectedCertificados.value = selectedCertificados.value.filter((id) =>
    certIds.has(id),
  );
};

const toggleLote = (id: number) => {
  selectedLotes.value = selectedLotes.value.includes(id)
    ? selectedLotes.value.filter((item) => item !== id)
    : [...selectedLotes.value, id];
};

const toggleLog = (id: string) => {
  selectedLogs.value = selectedLogs.value.includes(id)
    ? selectedLogs.value.filter((item) => item !== id)
    : [...selectedLogs.value, id];
};

const toggleTemporal = (id: string) => {
  selectedTemporales.value = selectedTemporales.value.includes(id)
    ? selectedTemporales.value.filter((item) => item !== id)
    : [...selectedTemporales.value, id];
};

const toggleCertificado = (id: string) => {
  selectedCertificados.value = selectedCertificados.value.includes(id)
    ? selectedCertificados.value.filter((item) => item !== id)
    : [...selectedCertificados.value, id];
};

const crearExportacion = async () => {
  if (totalSeleccionado.value === 0) {
    showError("Sin selección", "Seleccioná lotes, logs o temporales.");
    return;
  }
  creandoExportacion.value = true;
  try {
    exportacion.value = await almacenamientoService.crearExportacion({
      lote_ids: selectedLotes.value,
      log_ids: selectedLogs.value,
      temporal_ids: selectedTemporales.value,
    });
    showSuccess("Resguardo preparado");
  } catch (err: any) {
    showError(
      "No se pudo preparar el resguardo",
      err.response?.data?.detail || "Revisá la selección e intentá nuevamente.",
    );
  } finally {
    creandoExportacion.value = false;
  }
};

const descargarExportacion = async () => {
  if (!exportacion.value) return;
  descargando.value = true;
  try {
    const descarga = await almacenamientoService.descargarExportacion(
      exportacion.value.token,
    );
    if (!descarga.downloadToken) {
      throw new Error("No se recibió la confirmación de descarga del servidor.");
    }
    downloadBlob(descarga.blob, exportacion.value.archivo_nombre);
    exportacion.value = await almacenamientoService.confirmarDescarga(
      exportacion.value.token,
      exportacion.value.checksum_sha256,
      descarga.downloadToken,
    );
    showSuccess("Resguardo descargado");
  } catch (err: any) {
    showError(
      "No se pudo descargar",
      err.response?.data?.detail || "El archivo de resguardo no está disponible.",
    );
  } finally {
    descargando.value = false;
  }
};

const confirmarLiberacion = async () => {
  if (!exportacion.value) return;
  liberando.value = true;
  try {
    const result = await almacenamientoService.confirmarLiberacion(
      exportacion.value.token,
    );
    showSuccess("Espacio liberado", result.mensaje);
    exportacion.value = null;
    selectedLotes.value = [];
    selectedLogs.value = [];
    selectedTemporales.value = [];
    await cargarDatos();
  } catch (err: any) {
    showError(
      "No se pudo liberar espacio",
      err.response?.data?.detail || "Volvé a revisar el resguardo.",
    );
  } finally {
    liberando.value = false;
    mostrarConfirmacionLiberacion.value = false;
  }
};

const limpiarCertificados = async () => {
  if (selectedCertificados.value.length === 0) return;
  limpiandoCertificados.value = true;
  try {
    const result = await almacenamientoService.limpiarCertificadosHuerfanos(
      selectedCertificados.value,
    );
    showSuccess("Certificados limpiados", result.mensaje);
    selectedCertificados.value = [];
    await cargarDatos();
  } catch (err: any) {
    showError(
      "No se pudo limpiar certificados",
      err.response?.data?.detail || "Revisá los certificados seleccionados.",
    );
  } finally {
    limpiandoCertificados.value = false;
    mostrarConfirmacionCertificados.value = false;
  }
};

const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

const formatBytes = (bytes: number | null | undefined) => {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[unitIndex]}`;
};

const formatDateTime = (value: string | null) => {
  if (!value) return "-";
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
};

const estadoLabel = (value: string) => {
  const labels: Record<string, string> = {
    correcto: "Correcto",
    necesita_atencion: "Necesita atención",
    critico: "Crítico",
    no_disponible: "No disponible",
  };
  return labels[value] || value;
};

const estadoVariant = (value: string) => {
  if (value === "critico" || value === "no_disponible") return "danger";
  if (value === "necesita_atencion") return "warning";
  return "success";
};

const estadoIconClass = (value: EstadoOperativo) => {
  if (value === "correcto") return "bg-status-success-soft text-status-success";
  if (value === "necesita_atencion") {
    return "bg-status-warning-soft text-status-warning";
  }
  return "bg-status-danger-soft text-status-danger";
};

const getErrorMessage = (err: any, fallback: string) => {
  return err?.response?.data?.detail || err?.message || fallback;
};

onMounted(() => {
  actualizarTodo();
});
</script>

<template>
  <div>
    <div
      class="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"
    >
      <div>
        <h1 class="text-3xl font-bold text-brand-ink">
          Sistema
        </h1>
        <div class="mt-3 inline-flex rounded-control border border-border-subtle bg-surface-card p-1">
          <button
            type="button"
            class="rounded-control px-3 py-1.5 text-sm font-medium transition-colors"
            :class="activeTab === 'estado'
              ? 'bg-brand-mint text-brand-teal'
              : 'text-brand-slate hover:bg-brand-mint hover:text-brand-ink'"
            @click="activarTab('estado')"
          >
            Estado
          </button>
          <button
            type="button"
            class="rounded-control px-3 py-1.5 text-sm font-medium transition-colors"
            :class="activeTab === 'almacenamiento'
              ? 'bg-brand-mint text-brand-teal'
              : 'text-brand-slate hover:bg-brand-mint hover:text-brand-ink'"
            @click="activarTab('almacenamiento')"
          >
            Almacenamiento
          </button>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <BaseBadge
          v-if="estadoPrincipal"
          :variant="estadoVariant(estadoPrincipal)"
        >
          {{ estadoLabel(estadoPrincipal) }}
        </BaseBadge>
        <BaseButton
          variant="secondary"
          :loading="actualizando"
          @click="actualizarTodo"
        >
          Actualizar
        </BaseButton>
      </div>
    </div>

    <BaseAlert
      v-if="error && activeTab === 'almacenamiento'"
      type="error"
      title="Error"
      :message="error"
      class="mb-6"
      @dismiss="error = ''"
    />

    <section
      v-if="activeTab === 'estado'"
      class="space-y-6"
    >
      <div class="grid gap-4 md:grid-cols-3">
        <BaseCard>
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-sm font-medium text-brand-slate">
                Estado general
              </p>
              <p class="mt-2 text-2xl font-semibold text-brand-ink">
                {{ estadoLabel(estadoGeneral) }}
              </p>
            </div>
            <component
              :is="estadoGeneral === 'correcto' ? CheckCircleIcon : ExclamationTriangleIcon"
              class="h-8 w-8"
              :class="estadoGeneral === 'correcto' ? 'text-status-success' : 'text-status-warning'"
            />
          </div>
        </BaseCard>
        <BaseCard>
          <p class="text-sm font-medium text-brand-slate">
            Última actualización
          </p>
          <p class="mt-2 text-2xl font-semibold text-brand-ink">
            {{ formatDateTime(ultimaActualizacionEstado) }}
          </p>
        </BaseCard>
        <BaseCard>
          <p class="text-sm font-medium text-brand-slate">
            Ambiente ARCA
          </p>
          <p class="mt-2 text-2xl font-semibold text-brand-ink capitalize">
            {{ arcaStatus?.ambiente || "Sin datos" }}
          </p>
        </BaseCard>
      </div>

      <BaseCard title="Estado operativo">
        <div class="divide-y divide-border-subtle">
          <div
            v-for="item in estadoSistemaItems"
            :key="item.id"
            class="flex flex-col gap-4 py-4 first:pt-0 last:pb-0 lg:flex-row lg:items-start lg:justify-between"
          >
            <div class="flex gap-3">
              <div
                class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-panel"
                :class="estadoIconClass(item.estado)"
              >
                <component
                  :is="item.icon"
                  class="h-5 w-5"
                />
              </div>
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="font-semibold text-brand-ink">
                    {{ item.titulo }}
                  </h3>
                  <BaseBadge :variant="estadoVariant(item.estado)">
                    {{ estadoLabel(item.estado) }}
                  </BaseBadge>
                </div>
                <p class="mt-1 text-sm text-brand-slate">
                  {{ item.descripcion }}
                </p>
                <p class="mt-2 text-sm text-brand-ink">
                  {{ item.detalle || "Sin detalle disponible." }}
                </p>
              </div>
            </div>
            <BaseButton
              v-if="item.accion === 'probar-arca'"
              variant="secondary"
              size="sm"
              :loading="arcaProbeLoading"
              @click="probarConexionArca"
            >
              Probar conexión
            </BaseButton>
          </div>
        </div>
      </BaseCard>

      <BaseCard title="Guía rápida de soporte">
        <div class="grid gap-4 lg:grid-cols-2">
          <div
            v-for="item in soporteOperativoItems"
            :key="item.id"
            class="rounded-panel border border-border-subtle bg-surface-subtle p-4"
          >
            <div class="flex items-start gap-3">
              <div class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-panel bg-brand-mint text-brand-teal">
                <DocumentTextIcon class="h-5 w-5" />
              </div>
              <div class="min-w-0">
                <h3 class="text-sm font-semibold text-brand-ink">
                  {{ item.caso }}
                </h3>
                <dl class="mt-3 space-y-2 text-sm">
                  <div>
                    <dt class="font-medium text-brand-ink">
                      Revisar
                    </dt>
                    <dd class="mt-0.5 text-brand-slate">
                      {{ item.revisar }}
                    </dd>
                  </div>
                  <div>
                    <dt class="font-medium text-brand-ink">
                      Próximo paso seguro
                    </dt>
                    <dd class="mt-0.5 text-brand-slate">
                      {{ item.accion }}
                    </dd>
                  </div>
                  <div class="rounded-md bg-status-warning-soft px-3 py-2">
                    <dt class="font-medium text-status-warning">
                      Detenerse si
                    </dt>
                    <dd class="mt-0.5 text-brand-ink">
                      {{ item.detenerse }}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </BaseCard>

      <BaseCard title="Ficha para soporte">
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <div
            v-for="item in datosSoporteItems"
            :key="item.id"
            class="border-b border-border-subtle pb-3 last:border-b-0 md:border-b-0"
          >
            <p class="text-sm font-semibold text-brand-ink">
              {{ item.etiqueta }}
            </p>
            <p class="mt-1 text-sm text-brand-slate">
              {{ item.detalle }}
            </p>
          </div>
        </div>
      </BaseCard>
    </section>

    <template v-if="activeTab === 'almacenamiento'">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <BaseCard
          v-for="metrica in metricas"
          :key="metrica.label"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-sm font-medium text-gray-500">
                {{ metrica.label }}
              </p>
              <p class="mt-2 text-2xl font-semibold text-gray-900">
                {{ metrica.value }}
              </p>
            </div>
            <component
              :is="metrica.icon"
              class="h-8 w-8 text-primary-600"
            />
          </div>
        </BaseCard>
      </div>

      <div class="mt-6 grid gap-6 xl:grid-cols-[1fr_360px]">
        <div class="space-y-6">
          <BaseCard title="Categorías">
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                      Categoría
                    </th>
                    <th class="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                      Usado
                    </th>
                    <th class="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                      Recuperable
                    </th>
                    <th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                      Estado
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr
                    v-for="categoria in categoriasOrdenadas"
                    :key="categoria.clave"
                  >
                    <td class="px-4 py-3 text-sm text-gray-900">
                      <p class="font-medium">
                        {{ categoria.nombre }}
                      </p>
                      <p class="text-xs text-gray-500">
                        {{ categoria.descripcion }}
                      </p>
                    </td>
                    <td class="px-4 py-3 text-right text-sm text-gray-700">
                      {{ formatBytes(categoria.bytes_usados) }}
                    </td>
                    <td class="px-4 py-3 text-right text-sm text-gray-700">
                      {{ formatBytes(categoria.bytes_recuperables) }}
                    </td>
                    <td class="px-4 py-3 text-sm">
                      <BaseBadge :variant="estadoVariant(categoria.estado)">
                        {{ estadoLabel(categoria.estado) }}
                      </BaseBadge>
                    </td>
                  </tr>
                  <tr v-if="!loading && categoriasOrdenadas.length === 0">
                    <td
                      colspan="4"
                      class="px-4 py-10 text-center text-sm text-gray-500"
                    >
                      Sin datos de almacenamiento.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </BaseCard>

          <BaseCard title="Lotes compactables">
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-4 py-3" />
                    <th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                      Lote
                    </th>
                    <th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                      Emisor
                    </th>
                    <th class="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                      Filas
                    </th>
                    <th class="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                      Recuperable
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr
                    v-for="lote in lotes"
                    :key="lote.id"
                  >
                    <td class="px-4 py-3">
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        :checked="selectedLotes.includes(lote.id)"
                        @change="toggleLote(lote.id)"
                      >
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-900">
                      <p class="font-medium">
                        Lote #{{ lote.id }}
                      </p>
                      <p class="text-xs text-gray-500">
                        {{ formatDateTime(lote.finished_at || lote.created_at) }}
                      </p>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-700">
                      {{ lote.etiqueta_emisor }}
                    </td>
                    <td class="px-4 py-3 text-right text-sm text-gray-700">
                      {{ lote.filas_persistidas }}
                    </td>
                    <td class="px-4 py-3 text-right text-sm text-gray-700">
                      {{ formatBytes(lote.bytes_recuperables) }}
                    </td>
                  </tr>
                  <tr v-if="!loading && lotes.length === 0">
                    <td
                      colspan="5"
                      class="px-4 py-10 text-center text-sm text-gray-500"
                    >
                      No hay lotes cerrados con detalle compactable.
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </BaseCard>

          <BaseCard title="Archivos administrados">
            <div class="grid gap-6 lg:grid-cols-2">
              <div>
                <h3 class="text-sm font-semibold text-gray-900">
                  Logs antiguos
                </h3>
                <div class="mt-3 space-y-2">
                  <label
                    v-for="item in logs"
                    :key="item.id"
                    class="flex items-center justify-between gap-3 rounded-md border border-gray-200 px-3 py-2 text-sm"
                  >
                    <span class="flex min-w-0 items-center gap-2">
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        :checked="selectedLogs.includes(item.id)"
                        @change="toggleLog(item.id)"
                      >
                      <span class="truncate text-gray-700">{{ item.nombre }}</span>
                    </span>
                    <span class="text-gray-500">{{ formatBytes(item.bytes_usados) }}</span>
                  </label>
                  <p
                    v-if="!loading && logs.length === 0"
                    class="text-sm text-gray-500"
                  >
                    Sin logs antiguos.
                  </p>
                </div>
              </div>
              <div>
                <h3 class="text-sm font-semibold text-gray-900">
                  Temporales
                </h3>
                <div class="mt-3 space-y-2">
                  <label
                    v-for="item in temporales"
                    :key="item.id"
                    class="flex items-center justify-between gap-3 rounded-md border border-gray-200 px-3 py-2 text-sm"
                  >
                    <span class="flex min-w-0 items-center gap-2">
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        :checked="selectedTemporales.includes(item.id)"
                        @change="toggleTemporal(item.id)"
                      >
                      <span class="truncate text-gray-700">{{ item.nombre }}</span>
                    </span>
                    <span class="text-gray-500">{{ formatBytes(item.bytes_usados) }}</span>
                  </label>
                  <p
                    v-if="!loading && temporales.length === 0"
                    class="text-sm text-gray-500"
                  >
                    Sin temporales administrados.
                  </p>
                </div>
              </div>
            </div>
          </BaseCard>

          <BaseCard title="Uso por emisor">
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                      Emisor
                    </th>
                    <th class="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                      Lotes
                    </th>
                    <th class="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                      Comprobantes
                    </th>
                    <th class="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                      Recuperable
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr
                    v-for="emisor in emisoresOrdenados"
                    :key="emisor.empresa_id"
                  >
                    <td class="px-4 py-3 text-sm text-gray-900">
                      {{ emisor.etiqueta }}
                    </td>
                    <td class="px-4 py-3 text-right text-sm text-gray-700">
                      {{ emisor.lotes }}
                    </td>
                    <td class="px-4 py-3 text-right text-sm text-gray-700">
                      {{ emisor.comprobantes }}
                    </td>
                    <td class="px-4 py-3 text-right text-sm text-gray-700">
                      {{ formatBytes(emisor.bytes_recuperables) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </BaseCard>
        </div>

        <div class="space-y-6">
          <BaseCard title="Resguardo">
            <div class="space-y-4">
              <div class="rounded-md border border-gray-200 bg-gray-50 p-4">
                <p class="text-sm font-medium text-gray-900">
                  Seleccionados: {{ totalSeleccionado }}
                </p>
                <p class="mt-1 text-sm text-gray-600">
                  Lotes {{ selectedLotes.length }} · Logs {{ selectedLogs.length }} ·
                  Temporales {{ selectedTemporales.length }}
                </p>
              </div>
              <BaseButton
                class="w-full"
                :disabled="totalSeleccionado === 0"
                :loading="creandoExportacion"
                @click="crearExportacion"
              >
                <ArchiveBoxIcon class="mr-2 h-5 w-5" />
                Preparar ZIP
              </BaseButton>
              <BaseAlert
                v-if="exportacion"
                type="info"
                title="ZIP preparado"
                :dismissible="false"
              >
                {{ exportacion.archivo_nombre }} ·
                {{ formatBytes(exportacion.size_bytes) }}
              </BaseAlert>
              <BaseButton
                v-if="exportacion"
                class="w-full"
                variant="secondary"
                :loading="descargando"
                @click="descargarExportacion"
              >
                <ArrowDownTrayIcon class="mr-2 h-5 w-5" />
                Descargar resguardo
              </BaseButton>
              <BaseButton
                v-if="exportacion"
                class="w-full"
                variant="danger"
                :disabled="!hayExportacionDescargada"
                :loading="liberando"
                @click="mostrarConfirmacionLiberacion = true"
              >
                <TrashIcon class="mr-2 h-5 w-5" />
                Liberar espacio
              </BaseButton>
            </div>
          </BaseCard>

          <BaseCard title="Certificados huérfanos">
            <div class="space-y-3">
              <label
                v-for="item in certificadosHuerfanos"
                :key="item.id"
                class="flex items-center justify-between gap-3 rounded-md border border-gray-200 px-3 py-2 text-sm"
              >
                <span class="flex min-w-0 items-center gap-2">
                  <input
                    type="checkbox"
                    class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    :checked="selectedCertificados.includes(item.id)"
                    @change="toggleCertificado(item.id)"
                  >
                  <span class="truncate text-gray-700">{{ item.nombre }}</span>
                </span>
                <span class="text-gray-500">{{ formatBytes(item.bytes_usados) }}</span>
              </label>
              <p
                v-if="!loading && certificadosHuerfanos.length === 0"
                class="text-sm text-gray-500"
              >
                Sin certificados huérfanos gestionados.
              </p>
              <BaseButton
                class="w-full"
                variant="danger"
                :disabled="selectedCertificados.length === 0"
                :loading="limpiandoCertificados"
                @click="mostrarConfirmacionCertificados = true"
              >
                Limpiar seleccionados
              </BaseButton>
            </div>
          </BaseCard>
        </div>
      </div>
    </template>

    <ConfirmDialog
      :show="mostrarConfirmacionLiberacion"
      title="Liberar espacio"
      message="Se compactarán o eliminarán solo los elementos incluidos en el ZIP descargado."
      confirm-text="Ya lo descargué"
      cancel-text="Cancelar"
      variant="danger"
      @confirm="confirmarLiberacion"
      @cancel="mostrarConfirmacionLiberacion = false"
    />

    <ConfirmDialog
      :show="mostrarConfirmacionCertificados"
      title="Limpiar certificados"
      message="Se eliminarán solo archivos gestionados por FactuFlow que no están referenciados."
      confirm-text="Limpiar"
      cancel-text="Cancelar"
      variant="danger"
      @confirm="limpiarCertificados"
      @cancel="mostrarConfirmacionCertificados = false"
    />
  </div>
</template>
