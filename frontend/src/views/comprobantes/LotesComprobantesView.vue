<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseEmpty from "@/components/ui/BaseEmpty.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import { useNotification } from "@/composables/useNotification";
import lotesComprobantesService from "@/services/lotes-comprobantes.service";
import { useEmpresaStore } from "@/stores/empresa";
import {
  ESTADOS_GRUPO_COLOR,
  ESTADOS_LOTE_COLOR,
  ESTADOS_LOTE_NOMBRES,
  type LoteComprobante,
  type LoteComprobanteDetalle,
} from "@/types/lote-comprobante";
import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  CloudArrowUpIcon,
  DocumentDuplicateIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from "@heroicons/vue/24/outline";

const empresaStore = useEmpresaStore();
const { showError, showInfo, showSuccess, showWarning } = useNotification();

const fileInputRef = ref<HTMLInputElement | null>(null);
const archivoSeleccionado = ref<File | null>(null);
const lotes = ref<LoteComprobante[]>([]);
const loteActual = ref<LoteComprobanteDetalle | null>(null);
const loadingLotes = ref(false);
const validandoArchivo = ref(false);
const procesandoLote = ref(false);
const descargandoPlantilla = ref(false);
const descargandoObservado = ref(false);
const pollingHandle = ref<number | null>(null);

const empresaActiva = computed(
  () => empresaStore.empresaActiva || empresaStore.empresa,
);
const empresaActivaId = computed(() => empresaActiva.value?.id || null);
const loteEstadoNombre = computed(() => {
  if (!loteActual.value) return "";
  return (
    ESTADOS_LOTE_NOMBRES[loteActual.value.estado] || loteActual.value.estado
  );
});
const loteEstadoColor = computed(() => {
  if (!loteActual.value) return "bg-gray-100 text-gray-800";
  return (
    ESTADOS_LOTE_COLOR[loteActual.value.estado] || "bg-gray-100 text-gray-800"
  );
});
const hayProcesamientoEnCurso = computed(() => {
  return (
    loteActual.value?.estado === "procesando" ||
    loteActual.value?.estado === "en_cola" ||
    lotes.value.some((lote) => ["en_cola", "procesando"].includes(lote.estado))
  );
});
const puedeValidar = computed(
  () => !!archivoSeleccionado.value && !!empresaActivaId.value,
);
const puedeProcesar = computed(() => {
  if (!loteActual.value) return false;

  return (
    loteActual.value.grupos_validos > 0 &&
    !["en_cola", "procesando", "completado"].includes(loteActual.value.estado)
  );
});
const resumenOperativo = computed(() => {
  if (!loteActual.value) return [];

  return [
    {
      label: "Comprobantes detectados",
      value: loteActual.value.total_grupos,
      hint: "Cada comprobante_ref forma un comprobante real para ARCA.",
    },
    {
      label: "Listos para emitir",
      value: loteActual.value.grupos_validos,
      hint: "Son los comprobantes que pasaron todas las validaciones previas.",
    },
    {
      label: "Con observaciones",
      value: loteActual.value.grupos_con_error,
      hint: "Necesitan correccion antes de volver a subir el archivo.",
    },
    {
      label: "Ya emitidos",
      value: loteActual.value.grupos_emitidos,
      hint: "Comprobantes autorizados con CAE.",
    },
  ];
});
const porcentajeProcesado = computed(() => {
  if (!loteActual.value || loteActual.value.total_grupos === 0) return 0;

  const terminados =
    loteActual.value.grupos_emitidos + loteActual.value.grupos_fallidos;
  return Math.round((terminados / loteActual.value.total_grupos) * 100);
});
const necesitaCorreccion = computed(() => {
  return !!loteActual.value && loteActual.value.grupos_con_error > 0;
});

const formatDateTime = (value: string | null) => {
  if (!value) return "Sin iniciar";

  return new Date(value).toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const formatMoney = (value: number) => {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
  }).format(value || 0);
};

const triggerFileSelection = () => {
  fileInputRef.value?.click();
};

const handleArchivoSeleccionado = (event: Event) => {
  const target = event.target as HTMLInputElement;
  archivoSeleccionado.value = target.files?.[0] || null;
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

const cargarLotes = async (silent = false) => {
  if (!empresaActivaId.value) return;

  if (!silent) {
    loadingLotes.value = true;
  }

  try {
    lotes.value = await lotesComprobantesService.listar();
  } catch (error: any) {
    showError(
      "No se pudieron cargar los lotes",
      error.response?.data?.detail || "Revisa tu sesion o intenta nuevamente.",
    );
  } finally {
    if (!silent) {
      loadingLotes.value = false;
    }
  }
};

const cargarDetalleLote = async (loteId: number, silent = false) => {
  try {
    if (!silent) {
      loadingLotes.value = true;
    }
    loteActual.value = await lotesComprobantesService.obtener(loteId);
  } catch (error: any) {
    showError(
      "No se pudo abrir el lote",
      error.response?.data?.detail ||
        "El lote ya no esta disponible para esta empresa.",
    );
  } finally {
    if (!silent) {
      loadingLotes.value = false;
    }
  }
};

const descargarPlantilla = async () => {
  if (!empresaActiva.value) {
    showWarning(
      "Emisor activo requerido",
      "Selecciona una empresa antes de descargar la plantilla.",
    );
    return;
  }

  descargandoPlantilla.value = true;
  try {
    const archivo = await lotesComprobantesService.descargarPlantilla();
    downloadBlob(archivo, `factuflow-lote-${empresaActiva.value.cuit}.xlsx`);
    showSuccess(
      "Plantilla lista",
      "Completa una fila por item y repeti los datos del comprobante en todas las filas del mismo comprobante_ref.",
    );
  } catch (error: any) {
    showError(
      "No se pudo descargar la plantilla",
      error.response?.data?.detail || "Intenta nuevamente en unos segundos.",
    );
  } finally {
    descargandoPlantilla.value = false;
  }
};

const validarArchivo = async () => {
  if (!puedeValidar.value || !archivoSeleccionado.value) {
    showWarning(
      "Archivo requerido",
      "Selecciona primero el Excel generado desde la plantilla oficial.",
    );
    return;
  }

  validandoArchivo.value = true;
  try {
    const resultado = await lotesComprobantesService.validar(
      archivoSeleccionado.value,
    );
    showSuccess("Archivo validado", resultado.mensaje);
    await cargarLotes(true);
    await cargarDetalleLote(resultado.lote.id, true);

    if (resultado.requiere_background) {
      showInfo(
        "Lote grande detectado",
        "Como supera el limite sincrono, la emision se ejecutara en segundo plano cuando la confirmes.",
      );
    }
  } catch (error: any) {
    showError(
      "El archivo tiene problemas",
      error.response?.data?.detail ||
        "Revisa la plantilla y vuelve a intentarlo.",
    );
  } finally {
    validandoArchivo.value = false;
  }
};

const procesarLote = async () => {
  if (!loteActual.value) {
    showWarning(
      "Selecciona un lote",
      "Primero valida un archivo o abre un lote ya cargado.",
    );
    return;
  }

  procesandoLote.value = true;
  try {
    const resultado = await lotesComprobantesService.procesar(
      loteActual.value.id,
    );
    showSuccess(
      resultado.en_progreso ? "Emision iniciada" : "Lote procesado",
      resultado.mensaje,
    );
    await cargarLotes(true);
    await cargarDetalleLote(loteActual.value.id, true);
  } catch (error: any) {
    showError(
      "No se pudo emitir el lote",
      error.response?.data?.detail ||
        "Revisa las observaciones y vuelve a intentarlo.",
    );
  } finally {
    procesandoLote.value = false;
  }
};

const descargarObservado = async () => {
  if (!loteActual.value) {
    showWarning(
      "Selecciona un lote",
      "Abre un lote para descargar el archivo observado con el detalle por fila.",
    );
    return;
  }

  descargandoObservado.value = true;
  try {
    const archivo = await lotesComprobantesService.descargarArchivoObservado(
      loteActual.value.id,
    );
    downloadBlob(
      archivo,
      `${loteActual.value.nombre_archivo.replace(".xlsx", "")}-observado.xlsx`,
    );
  } catch (error: any) {
    showError(
      "No se pudo descargar el archivo observado",
      error.response?.data?.detail || "Vuelve a intentarlo.",
    );
  } finally {
    descargandoObservado.value = false;
  }
};

const iniciarPolling = () => {
  if (pollingHandle.value !== null) return;

  pollingHandle.value = window.setInterval(async () => {
    await cargarLotes(true);
    if (loteActual.value) {
      await cargarDetalleLote(loteActual.value.id, true);
    }
  }, 5000);
};

const detenerPolling = () => {
  if (pollingHandle.value === null) return;

  window.clearInterval(pollingHandle.value);
  pollingHandle.value = null;
};

watch(hayProcesamientoEnCurso, (activo) => {
  if (activo) {
    iniciarPolling();
  } else {
    detenerPolling();
  }
});

watch(
  empresaActivaId,
  async (empresaId) => {
    archivoSeleccionado.value = null;
    loteActual.value = null;

    if (!empresaId) return;
    await cargarLotes();
  },
  { immediate: false },
);

onMounted(async () => {
  if (!empresaActivaId.value) {
    await empresaStore.inicializarEmpresaActiva();
  }

  await cargarLotes();
  if (lotes.value[0]) {
    await cargarDetalleLote(lotes.value[0].id);
  }
});

onBeforeUnmount(() => {
  detenerPolling();
});
</script>

<template>
  <div class="space-y-6">
    <div
      class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between"
    >
      <div>
        <h1 class="text-3xl font-bold text-gray-900">Emision masiva</h1>
        <p class="mt-2 max-w-3xl text-gray-600">
          Carga un Excel, revisa errores antes de emitir y sigue el resultado
          del lote sin perder contexto tecnico.
        </p>
      </div>

      <div
        class="rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-600 shadow-sm"
      >
        <p class="font-semibold text-gray-900">Emisor activo</p>
        <p>
          {{
            empresaActiva?.razon_social ||
            "Selecciona una empresa para empezar."
          }}
        </p>
      </div>
    </div>

    <BaseAlert v-if="!empresaActivaId" type="warning">
      Selecciona un emisor activo antes de descargar la plantilla o subir el
      archivo.
    </BaseAlert>

    <BaseCard>
      <div class="grid gap-4 lg:grid-cols-3">
        <div class="rounded-xl border border-blue-100 bg-blue-50 p-4">
          <p class="text-sm font-semibold text-blue-900">
            1. Descarga la plantilla
          </p>
          <p class="mt-2 text-sm text-blue-800">
            Usa siempre el archivo oficial para evitar columnas mal escritas o
            faltantes.
          </p>
          <BaseButton
            class="mt-4 w-full"
            :loading="descargandoPlantilla"
            :disabled="!empresaActivaId"
            @click="descargarPlantilla"
          >
            <ArrowDownTrayIcon class="mr-2 h-5 w-5" />
            Descargar plantilla
          </BaseButton>
        </div>

        <div class="rounded-xl border border-amber-100 bg-amber-50 p-4">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-amber-900">
                2. Completa el archivo
              </p>
              <p class="mt-2 text-sm text-amber-800">
                Una fila por item. Repite los datos del comprobante en cada fila
                del mismo comprobante_ref.
              </p>
            </div>
            <InformationCircleIcon
              class="h-5 w-5 flex-shrink-0 text-amber-700"
              title="La plantilla admite varios tipos de comprobante y varios puntos de venta dentro del mismo lote."
            />
          </div>
          <ul class="mt-4 space-y-2 text-sm text-amber-900">
            <li>1 empresa por lote.</li>
            <li>
              Cliente precargado opcional: el Excel alcanza para consumidor
              final y operaciones masivas.
            </li>
            <li>Si una fila falla, el sistema te indica como corregirla.</li>
          </ul>
        </div>

        <div class="rounded-xl border border-emerald-100 bg-emerald-50 p-4">
          <p class="text-sm font-semibold text-emerald-900">
            3. Valida y confirma
          </p>
          <p class="mt-2 text-sm text-emerald-800">
            Primero se revisa todo el archivo. Despues puedes emitir solo los
            comprobantes que quedaron listos.
          </p>
          <p class="mt-4 text-sm font-medium text-emerald-900">
            Hasta 100 comprobantes: procesamiento inmediato.
          </p>
          <p class="text-sm text-emerald-900">
            Mas de 100 comprobantes: seguimiento en segundo plano.
          </p>
        </div>
      </div>
    </BaseCard>

    <BaseCard>
      <div class="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div>
          <div class="flex items-center gap-2">
            <CloudArrowUpIcon class="h-5 w-5 text-primary-600" />
            <h2 class="text-lg font-semibold text-gray-900">Validar archivo</h2>
          </div>
          <p class="mt-2 text-sm text-gray-600">
            Que espera esta pantalla: un archivo `.xlsx` generado desde la
            plantilla oficial para el emisor activo.
          </p>

          <div
            class="mt-4 rounded-2xl border-2 border-dashed border-gray-300 bg-gray-50 p-6"
          >
            <input
              ref="fileInputRef"
              type="file"
              accept=".xlsx"
              class="hidden"
              @change="handleArchivoSeleccionado"
            />

            <div
              class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
            >
              <div>
                <p class="font-medium text-gray-900">
                  {{
                    archivoSeleccionado?.name ||
                    "Todavia no seleccionaste ningun archivo."
                  }}
                </p>
                <p class="mt-1 text-sm text-gray-500">
                  {{
                    archivoSeleccionado
                      ? "Cuando confirmes, el sistema validara fila por fila antes de emitir."
                      : "Sube el Excel y revisa el resumen antes de emitir."
                  }}
                </p>
              </div>

              <div class="flex flex-wrap gap-3">
                <BaseButton variant="secondary" @click="triggerFileSelection">
                  <DocumentDuplicateIcon class="mr-2 h-5 w-5" />
                  Elegir archivo
                </BaseButton>
                <BaseButton
                  :loading="validandoArchivo"
                  :disabled="!puedeValidar"
                  @click="validarArchivo"
                >
                  <CheckCircleIcon class="mr-2 h-5 w-5" />
                  Validar lote
                </BaseButton>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <div class="flex items-center gap-2">
            <ExclamationTriangleIcon class="h-5 w-5 text-amber-600" />
            <h3 class="font-semibold text-gray-900">Controles previos</h3>
          </div>
          <ul class="mt-3 space-y-2 text-sm text-gray-700">
            <li>Emisor activo correcto.</li>
            <li>Certificado vigente para el ambiente actual.</li>
            <li>Punto de venta habilitado FactuFlow.</li>
            <li>
              Documento del receptor solo cuando corresponde por tipo o importe.
            </li>
            <li>
              comprobante_ref repetido solo para las filas del mismo
              comprobante.
            </li>
          </ul>
        </div>
      </div>
    </BaseCard>

    <div class="grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
      <div class="space-y-6">
        <BaseCard v-if="loadingLotes && !loteActual">
          <div class="flex justify-center py-10">
            <BaseSpinner />
          </div>
        </BaseCard>

        <template v-else-if="loteActual">
          <BaseCard>
            <div
              class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between"
            >
              <div>
                <div class="flex flex-wrap items-center gap-3">
                  <h2 class="text-xl font-semibold text-gray-900">
                    {{ loteActual.nombre_archivo }}
                  </h2>
                  <span
                    :class="[
                      'inline-flex rounded-full px-3 py-1 text-xs font-semibold',
                      loteEstadoColor,
                    ]"
                  >
                    {{ loteEstadoNombre }}
                  </span>
                </div>
                <p class="mt-2 text-sm text-gray-600">
                  {{ loteActual.mensaje_resumen || "Sin novedades por ahora." }}
                </p>
                <p class="mt-2 text-xs text-gray-500">
                  Cargado {{ formatDateTime(loteActual.created_at) }} | Inicio
                  {{ formatDateTime(loteActual.started_at) }} | Fin
                  {{ formatDateTime(loteActual.finished_at) }}
                </p>
              </div>

              <div class="flex flex-wrap gap-3">
                <BaseButton
                  variant="secondary"
                  :loading="descargandoObservado"
                  @click="descargarObservado"
                >
                  <ArrowDownTrayIcon class="mr-2 h-5 w-5" />
                  Descargar observado
                </BaseButton>
                <BaseButton
                  :loading="procesandoLote"
                  :disabled="!puedeProcesar"
                  @click="procesarLote"
                >
                  <ArrowPathIcon class="mr-2 h-5 w-5" />
                  Emitir comprobantes validos
                </BaseButton>
              </div>
            </div>

            <div class="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div
                v-for="item in resumenOperativo"
                :key="item.label"
                class="rounded-xl border border-gray-200 bg-gray-50 p-4"
              >
                <div class="flex items-start justify-between gap-2">
                  <p class="text-sm font-medium text-gray-600">
                    {{ item.label }}
                  </p>
                  <InformationCircleIcon
                    class="h-4 w-4 flex-shrink-0 text-gray-400"
                    :title="item.hint"
                  />
                </div>
                <p class="mt-3 text-3xl font-bold text-gray-900">
                  {{ item.value }}
                </p>
              </div>
            </div>

            <div class="mt-6 rounded-xl border border-gray-200 bg-gray-50 p-4">
              <div
                class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between"
              >
                <p class="text-sm font-medium text-gray-900">Avance del lote</p>
                <p class="text-sm text-gray-600">
                  {{ porcentajeProcesado }}% procesado
                </p>
              </div>
              <div class="mt-3 h-3 overflow-hidden rounded-full bg-gray-200">
                <div
                  class="h-full rounded-full bg-primary-600 transition-all"
                  :style="{ width: `${porcentajeProcesado}%` }"
                />
              </div>
            </div>

            <BaseAlert v-if="necesitaCorreccion" type="warning" class="mt-6">
              Hay comprobantes observados. Descarga el archivo observado para
              ver fila por fila que debes corregir antes de volver a subir el
              Excel.
            </BaseAlert>

            <div class="mt-6 overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th
                      class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-600"
                    >
                      Ref
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-600"
                    >
                      Receptor
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-600"
                    >
                      Tipo / PV
                    </th>
                    <th
                      class="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide text-gray-600"
                    >
                      Total estimado
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-600"
                    >
                      Estado
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-600"
                    >
                      Observacion principal
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr
                    v-for="grupo in loteActual.grupos"
                    :key="grupo.id"
                    class="hover:bg-gray-50"
                  >
                    <td class="px-4 py-3 text-sm font-medium text-gray-900">
                      {{ grupo.comprobante_ref }}
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-700">
                      <p>
                        {{ grupo.cliente_razon_social || "A consumidor final" }}
                      </p>
                      <p class="text-xs text-gray-500">
                        {{ grupo.cliente_documento || "Sin documento" }}
                      </p>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-700">
                      <p>Tipo {{ grupo.tipo_comprobante || "-" }}</p>
                      <p class="text-xs text-gray-500">
                        Punto de venta {{ grupo.punto_venta_numero || "-" }}
                      </p>
                    </td>
                    <td
                      class="px-4 py-3 text-right text-sm font-medium text-gray-900"
                    >
                      {{ formatMoney(grupo.total_estimado) }}
                    </td>
                    <td class="px-4 py-3 text-sm">
                      <span
                        :class="[
                          'inline-flex rounded-full px-3 py-1 text-xs font-semibold',
                          ESTADOS_GRUPO_COLOR[grupo.estado] ||
                            'bg-gray-50 text-gray-700',
                        ]"
                      >
                        {{ grupo.estado }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-600">
                      {{ grupo.mensajes_json[0] || "Sin observaciones" }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </BaseCard>
        </template>

        <BaseCard v-else>
          <BaseEmpty
            title="Todavia no hay un lote seleccionado"
            message="Descarga la plantilla, sube el Excel y valida el archivo para ver el resumen completo aca."
            :icon="DocumentDuplicateIcon"
          />
        </BaseCard>
      </div>

      <BaseCard>
        <template #header>
          <div class="flex items-center justify-between">
            <span>Lotes recientes</span>
            <button
              class="text-sm font-medium text-primary-700 hover:text-primary-800"
              @click="cargarLotes()"
            >
              Actualizar
            </button>
          </div>
        </template>

        <div
          v-if="loadingLotes && lotes.length === 0"
          class="flex justify-center py-10"
        >
          <BaseSpinner />
        </div>

        <div v-else-if="lotes.length > 0" class="space-y-3">
          <button
            v-for="lote in lotes"
            :key="lote.id"
            class="w-full rounded-xl border border-gray-200 p-4 text-left transition-colors hover:border-primary-200 hover:bg-primary-50"
            @click="cargarDetalleLote(lote.id)"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="font-medium text-gray-900">
                  {{ lote.nombre_archivo }}
                </p>
                <p class="mt-1 text-xs text-gray-500">
                  {{ formatDateTime(lote.created_at) }}
                </p>
              </div>
              <span
                :class="[
                  'inline-flex rounded-full px-3 py-1 text-xs font-semibold',
                  ESTADOS_LOTE_COLOR[lote.estado] ||
                    'bg-gray-100 text-gray-800',
                ]"
              >
                {{ ESTADOS_LOTE_NOMBRES[lote.estado] || lote.estado }}
              </span>
            </div>

            <div class="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-600">
              <p>Validos: {{ lote.grupos_validos }}</p>
              <p>Errores: {{ lote.grupos_con_error }}</p>
              <p>Emitidos: {{ lote.grupos_emitidos }}</p>
              <p>Fallidos: {{ lote.grupos_fallidos }}</p>
            </div>
          </button>
        </div>

        <BaseEmpty v-else>
          <DocumentDuplicateIcon class="mx-auto mb-4 h-12 w-12 text-gray-400" />
          <p class="text-gray-600">
            Todavia no se cargaron lotes para esta empresa.
          </p>
        </BaseEmpty>
      </BaseCard>
    </div>
  </div>
</template>
