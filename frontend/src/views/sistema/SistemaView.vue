<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  ArchiveBoxIcon,
  ArrowDownTrayIcon,
  CircleStackIcon,
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
import type {
  AlmacenamientoItem,
  AlmacenamientoResumen,
  ExportacionAlmacenamiento,
  LoteCompactable,
} from "@/types/almacenamiento";

const { showError, showSuccess } = useNotification();

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

const cargarDatos = async () => {
  loading.value = true;
  error.value = "";
  try {
    const [
      resumenResponse,
      lotesResponse,
      logsResponse,
      temporalesResponse,
      certificadosResponse,
    ] = await Promise.all([
      almacenamientoService.resumen(),
      almacenamientoService.lotesCompactables(),
      almacenamientoService.logs(),
      almacenamientoService.temporales(),
      almacenamientoService.certificadosHuerfanos(),
    ]);
    resumen.value = resumenResponse;
    lotes.value = lotesResponse;
    logs.value = logsResponse;
    temporales.value = temporalesResponse;
    certificadosHuerfanos.value = certificadosResponse;
    limpiarSeleccionesAusentes();
  } catch (err: any) {
    error.value =
      err.response?.data?.detail || "No se pudo cargar el almacenamiento.";
  } finally {
    loading.value = false;
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
  };
  return labels[value] || value;
};

const estadoVariant = (value: string) => {
  if (value === "critico") return "danger";
  if (value === "necesita_atencion") return "warning";
  return "success";
};

onMounted(() => {
  cargarDatos();
});
</script>

<template>
  <div>
    <div
      class="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"
    >
      <div>
        <h1 class="text-3xl font-bold text-gray-900">
          Sistema
        </h1>
        <div class="mt-3 inline-flex rounded-lg border border-gray-200 bg-white p-1">
          <button
            type="button"
            class="rounded-md bg-primary-50 px-3 py-1.5 text-sm font-medium text-primary-700"
          >
            Almacenamiento
          </button>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <BaseBadge
          v-if="resumen"
          :variant="estadoVariant(resumen.estado)"
        >
          {{ estadoLabel(resumen.estado) }}
        </BaseBadge>
        <BaseButton
          variant="secondary"
          :loading="loading"
          @click="cargarDatos"
        >
          Actualizar
        </BaseButton>
      </div>
    </div>

    <BaseAlert
      v-if="error"
      type="error"
      title="Error"
      :message="error"
      class="mb-6"
      @dismiss="error = ''"
    />

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
