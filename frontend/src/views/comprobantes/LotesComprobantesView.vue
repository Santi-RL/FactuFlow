<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import ConfirmDialog from "@/components/common/ConfirmDialog.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseEmpty from "@/components/ui/BaseEmpty.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import { useNotification } from "@/composables/useNotification";
import formatosImportacionService from "@/services/formatos-importacion.service";
import lotesComprobantesService from "@/services/lotes-comprobantes.service";
import { useEmpresaStore } from "@/stores/empresa";
import type {
  FormatoImportacion,
  FormatoImportacionCandidato,
  FormatoImportacionDeteccion,
} from "@/types/formato-importacion";
import {
  ESTADOS_GRUPO_COLOR,
  ESTADOS_LOTE_COLOR,
  ESTADOS_LOTE_NOMBRES,
  type LoteComprobante,
  type LoteComprobanteDetalle,
  type LoteOpcionesFechas,
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
const formatosImportacion = ref<FormatoImportacion[]>([]);
const deteccionFormato = ref<FormatoImportacionDeteccion | null>(null);
const formatoSeleccionadoId = ref<string | number>("");
const conceptoModo = ref<"productos" | "servicios" | "archivo" | "">("");
const descripcionItemModo = ref<"archivo" | "fija" | "">("");
const descripcionItemFija = ref("");
const fechaEmisionModo = ref<"archivo" | "fija" | "">("");
const fechaEmisionFija = ref("");
const fechaServicioDesdeModo = ref<"archivo" | "fija" | "">("");
const fechaServicioDesdeFija = ref("");
const fechaServicioHastaModo = ref<"archivo" | "fija" | "">("");
const fechaServicioHastaFija = ref("");
const fechaVtoPagoModo = ref<"archivo" | "fija" | "">("");
const fechaVtoPagoFija = ref("");
const lotes = ref<LoteComprobante[]>([]);
const loteActual = ref<LoteComprobanteDetalle | null>(null);
const loadingLotes = ref(false);
const validandoArchivo = ref(false);
const detectandoFormato = ref(false);
const procesandoLote = ref(false);
const descargandoPlantilla = ref(false);
const descargandoObservado = ref(false);
const mostrarConfirmacionFechaFiscal = ref(false);
const pollingHandle = ref<number | null>(null);

const empresaActiva = computed(() => empresaStore.empresaActiva);
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
const formatosOptions = computed(() => {
  return formatosImportacion.value
    .filter((formato) => !!formato.version_vigente)
    .map((formato) => ({
      value: formato.version_vigente?.id || "",
      label: `${formato.nombre} (${formato.alcance})`,
    }));
});
const candidatoPrincipal = computed<FormatoImportacionCandidato | null>(() => {
  return deteccionFormato.value?.candidatos[0] || null;
});
const candidatoSeleccionado = computed<FormatoImportacionCandidato | null>(() => {
  const selected = Number(formatoSeleccionadoId.value || 0);
  if (!selected) {
    return (
      deteccionFormato.value?.candidatos.find(
        (candidato) => candidato.formato_version_id === null,
      ) || null
    );
  }

  return (
    deteccionFormato.value?.candidatos.find(
      (candidato) => candidato.formato_version_id === selected,
    ) || null
  );
});
const requiereElegirFormato = computed(() => {
  if (!archivoSeleccionado.value || detectandoFormato.value) return false;
  if (!deteccionFormato.value) return true;
  const principal = candidatoPrincipal.value;
  if (!principal) return !formatoSeleccionadoId.value;
  if (principal.formato_version_id === null && principal.confianza === "alta") {
    return false;
  }
  return !formatoSeleccionadoId.value;
});
const opcionesFechasCompletas = computed(() => {
  const requiereFechasServicio = conceptoModo.value !== "productos";
  return (
    !!fechaEmisionModo.value &&
    (fechaEmisionModo.value !== "fija" || !!fechaEmisionFija.value) &&
    (!requiereFechasServicio ||
      (!!fechaServicioDesdeModo.value &&
        (fechaServicioDesdeModo.value !== "fija" ||
          !!fechaServicioDesdeFija.value) &&
        !!fechaServicioHastaModo.value &&
        (fechaServicioHastaModo.value !== "fija" ||
          !!fechaServicioHastaFija.value) &&
        !!fechaVtoPagoModo.value &&
        (fechaVtoPagoModo.value !== "fija" || !!fechaVtoPagoFija.value)))
  );
});
const descripcionItemCompleta = computed(() => {
  return (
    !!descripcionItemModo.value &&
    (descripcionItemModo.value !== "fija" || !!descripcionItemFija.value.trim())
  );
});
const opcionesFechas = computed<LoteOpcionesFechas>(() => ({
  concepto_modo: conceptoModo.value,
  descripcion_item_modo: descripcionItemModo.value,
  descripcion_item_fija: descripcionItemFija.value.trim() || undefined,
  fecha_emision_modo: fechaEmisionModo.value,
  fecha_emision_fija: fechaEmisionFija.value || undefined,
  fecha_servicio_desde_modo: fechaServicioDesdeModo.value,
  fecha_servicio_desde_fija: fechaServicioDesdeFija.value || undefined,
  fecha_servicio_hasta_modo: fechaServicioHastaModo.value,
  fecha_servicio_hasta_fija: fechaServicioHastaFija.value || undefined,
  fecha_vto_pago_modo: fechaVtoPagoModo.value,
  fecha_vto_pago_fija: fechaVtoPagoFija.value || undefined,
}));
const puedeValidar = computed(
  () =>
    !!archivoSeleccionado.value &&
    !!empresaActivaId.value &&
    !detectandoFormato.value &&
    !requiereElegirFormato.value &&
    !!conceptoModo.value &&
    descripcionItemCompleta.value &&
    opcionesFechasCompletas.value,
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

const fechasEmisionValidas = computed(() => {
  const fechas = new Set<string>();
  loteActual.value?.grupos
    .filter((grupo) => grupo.estado === "validado" && grupo.fecha_emision)
    .forEach((grupo) => fechas.add(formatDate(grupo.fecha_emision)));
  return Array.from(fechas);
});

const puntosVentaValidos = computed(() => {
  const puntos = new Set<number>();
  loteActual.value?.grupos
    .filter((grupo) => grupo.estado === "validado" && grupo.punto_venta_numero)
    .forEach((grupo) => puntos.add(Number(grupo.punto_venta_numero)));
  return Array.from(puntos).sort((a, b) => a - b);
});

const resumenFechasConfirmacion = computed(() => {
  if (fechasEmisionValidas.value.length === 0) return "sin fecha definida";
  return fechasEmisionValidas.value.join(", ");
});

const resumenPuntosVentaConfirmacion = computed(() => {
  if (puntosVentaValidos.value.length === 0) return "";
  return ` para los puntos de venta ${puntosVentaValidos.value
    .map((punto) => String(punto).padStart(4, "0"))
    .join(", ")}`;
});

const mensajeConfirmacionFechaFiscalLote = computed(() => {
  return `Está seguro que quiere emitir comprobantes con fecha ${resumenFechasConfirmacion.value}${resumenPuntosVentaConfirmacion.value}? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`;
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

const formatDate = (value: string | null) => {
  if (!value) return "-";
  const [year, month, day] = value.split("T")[0].split("-");
  return `${day}/${month}/${year}`;
};

const formatMoney = (value: number) => {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
  }).format(value || 0);
};

const formatConcepto = (value: number | null) => {
  if (value === 1) return "Productos";
  if (value === 2) return "Servicios";
  if (value === 3) return "Productos y servicios";
  return "-";
};

const descripcionFacturada = (comprobanteRef: string) => {
  const fila = loteActual.value?.filas.find(
    (item) => item.comprobante_ref === comprobanteRef,
  );
  const descripcion = fila?.datos_json?.item_descripcion;
  return typeof descripcion === "string" && descripcion.trim()
    ? descripcion.trim()
    : "-";
};

const triggerFileSelection = () => {
  fileInputRef.value?.click();
};

const handleArchivoSeleccionado = (event: Event) => {
  const target = event.target as HTMLInputElement;
  archivoSeleccionado.value = target.files?.[0] || null;
  deteccionFormato.value = null;
  formatoSeleccionadoId.value = "";
  conceptoModo.value = "";
  descripcionItemModo.value = "";
  descripcionItemFija.value = "";
  fechaEmisionModo.value = "";
  fechaEmisionFija.value = "";
  fechaServicioDesdeModo.value = "";
  fechaServicioDesdeFija.value = "";
  fechaServicioHastaModo.value = "";
  fechaServicioHastaFija.value = "";
  fechaVtoPagoModo.value = "";
  fechaVtoPagoFija.value = "";
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

const cargarFormatosImportacion = async () => {
  if (!empresaActivaId.value) return;

  try {
    formatosImportacion.value = await formatosImportacionService.listar();
  } catch (error: any) {
    showError(
      "No se pudieron cargar los formatos",
      error.response?.data?.detail ||
        "Revisa tu sesion antes de validar archivos externos.",
    );
  }
};

const detectarFormatoArchivo = async (archivo: File) => {
  if (!empresaActivaId.value) {
    showWarning(
      "Emisor activo requerido",
      "Selecciona un emisor antes de analizar los encabezados del Excel.",
    );
    return;
  }

  detectandoFormato.value = true;
  try {
    if (formatosImportacion.value.length === 0) {
      await cargarFormatosImportacion();
    }
    const resultado = await formatosImportacionService.detectar(archivo);
    deteccionFormato.value = resultado;
    formatoSeleccionadoId.value = resultado.formato_sugerido_version_id || "";

    if (resultado.candidatos.length === 0) {
      showWarning(
        "Formato no reconocido",
        "El sistema no encontro un formato confiable. Selecciona uno antes de validar.",
      );
    }
  } catch (error: any) {
    deteccionFormato.value = null;
    formatoSeleccionadoId.value = "";
    showError(
      "No se pudo detectar el formato",
      error.response?.data?.detail ||
        "Puedes seleccionar un formato manualmente e intentar validar.",
    );
  } finally {
    detectandoFormato.value = false;
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
      "Selecciona primero un Excel de lote o un archivo externo con formato definido.",
    );
    return;
  }

  validandoArchivo.value = true;
  try {
    const resultado = await lotesComprobantesService.validar(
      archivoSeleccionado.value,
      Number(formatoSeleccionadoId.value || 0) || null,
      opcionesFechas.value,
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
  mostrarConfirmacionFechaFiscal.value = false;
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

const solicitarConfirmacionEmisionLote = () => {
  if (!puedeProcesar.value) return;
  mostrarConfirmacionFechaFiscal.value = true;
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

watch([archivoSeleccionado, empresaActivaId], ([archivo, empresaId]) => {
  if (!archivo || !empresaId || deteccionFormato.value || detectandoFormato.value) {
    return;
  }
  detectarFormatoArchivo(archivo);
});

watch(
  empresaActivaId,
  async (empresaId) => {
    archivoSeleccionado.value = null;
    loteActual.value = null;
    deteccionFormato.value = null;
    formatoSeleccionadoId.value = "";
    conceptoModo.value = "";
    descripcionItemModo.value = "";
    descripcionItemFija.value = "";
    fechaEmisionModo.value = "";
    fechaEmisionFija.value = "";
    fechaServicioDesdeModo.value = "";
    fechaServicioDesdeFija.value = "";
    fechaServicioHastaModo.value = "";
    fechaServicioHastaFija.value = "";
    fechaVtoPagoModo.value = "";
    fechaVtoPagoFija.value = "";

    if (!empresaId) return;
    await cargarFormatosImportacion();
    await cargarLotes();
  },
  { immediate: false },
);

onMounted(async () => {
  if (!empresaActivaId.value) {
    await empresaStore.inicializarEmpresaActiva();
  }

  await cargarLotes();
  await cargarFormatosImportacion();
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
            Puedes usar el archivo oficial o subir un Excel externo con formato
            configurado.
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
              El mismo lote puede incluir varios puntos de venta del emisor.
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
            Sube la plantilla oficial o un archivo `.xlsx` externo y confirma
            el formato antes de validar.
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

          <div
            v-if="archivoSeleccionado"
            class="mt-4 rounded-xl border border-gray-200 bg-white p-4"
          >
            <div
              class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"
            >
              <div>
                <p class="text-sm font-semibold text-gray-900">
                  Formato de importacion
                </p>
                <p class="mt-1 text-sm text-gray-600">
                  {{
                    detectandoFormato
                      ? "Detectando columnas del Excel..."
                      : candidatoPrincipal
                        ? `Sugerencia: ${candidatoPrincipal.nombre} (${Math.round(candidatoPrincipal.score * 100)}%)`
                        : "Selecciona el formato que corresponde al origen del archivo."
                  }}
                </p>
              </div>
              <span
                v-if="candidatoSeleccionado"
                class="inline-flex rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700"
              >
                Confianza {{ candidatoSeleccionado.confianza }}
              </span>
            </div>

            <div class="mt-4 grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
              <BaseSelect
                v-model="formatoSeleccionadoId"
                label="Formato"
                :options="formatosOptions"
                placeholder="Selecciona un formato"
                :disabled="detectandoFormato"
              />

              <div class="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                <p class="font-medium text-gray-900">Columnas detectadas</p>
                <p class="mt-1 break-words">
                  {{
                    deteccionFormato?.headers_detectados.join(", ") ||
                    "Todavia no se analizaron encabezados."
                  }}
                </p>
              </div>
            </div>

            <BaseAlert v-if="requiereElegirFormato" type="warning" class="mt-4">
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <span>
                  {{
                    deteccionFormato
                      ? "Confirma un formato antes de validar. Si el mapeo no coincide, el sistema puede interpretar mal importes, receptor o punto de venta."
                      : "Todavia no se analizaron los encabezados del Excel. El analisis deberia iniciar automaticamente; si no avanza, reintentalo."
                  }}
                </span>
                <BaseButton
                  v-if="!deteccionFormato"
                  size="sm"
                  variant="secondary"
                  :loading="detectandoFormato"
                  @click="archivoSeleccionado && detectarFormatoArchivo(archivoSeleccionado)"
                >
                  Analizar encabezados
                </BaseButton>
              </div>
            </BaseAlert>
          </div>

          <div
            v-if="archivoSeleccionado"
            class="mt-4 rounded-xl border border-sky-200 bg-sky-50 p-4"
          >
            <div class="flex items-start gap-3">
              <InformationCircleIcon
                class="mt-0.5 h-5 w-5 flex-shrink-0 text-sky-700"
              />
              <div>
                <p class="text-sm font-semibold text-sky-950">
                  Tipo de concepto fiscal ARCA obligatorio
                </p>
                <p class="mt-1 text-sm text-sky-900">
                  Defini si el lote corresponde a productos, servicios o si el
                  Excel lo indica fila por fila. No se usa un valor por defecto.
                </p>
              </div>
            </div>

            <div class="mt-4 grid gap-3 text-sm text-gray-800 md:grid-cols-3">
              <label class="rounded-lg border border-sky-100 bg-white p-3">
                <span class="flex items-center gap-2 font-medium">
                  <input
                    v-model="conceptoModo"
                    type="radio"
                    value="productos"
                    class="h-4 w-4 text-primary-600"
                  />
                  Productos
                </span>
              </label>
              <label class="rounded-lg border border-sky-100 bg-white p-3">
                <span class="flex items-center gap-2 font-medium">
                  <input
                    v-model="conceptoModo"
                    type="radio"
                    value="servicios"
                    class="h-4 w-4 text-primary-600"
                  />
                  Servicios
                </span>
              </label>
              <label class="rounded-lg border border-sky-100 bg-white p-3">
                <span class="flex items-center gap-2 font-medium">
                  <input
                    v-model="conceptoModo"
                    type="radio"
                    value="archivo"
                    class="h-4 w-4 text-primary-600"
                  />
                  Definido por el archivo
                </span>
                <span class="mt-2 block text-xs text-gray-600">
                  El Excel debe tener una columna con Producto o Servicio en
                  todas las filas.
                </span>
              </label>
            </div>

            <BaseAlert v-if="!conceptoModo" type="warning" class="mt-4">
              Elegi el tipo de concepto fiscal ARCA antes de validar. Sin esta
              confirmacion el lote no puede quedar listo para emitir.
            </BaseAlert>
          </div>

          <div
            v-if="archivoSeleccionado"
            class="mt-4 rounded-xl border border-violet-200 bg-violet-50 p-4"
          >
            <div class="flex items-start gap-3">
              <InformationCircleIcon
                class="mt-0.5 h-5 w-5 flex-shrink-0 text-violet-700"
              />
              <div>
                <p class="text-sm font-semibold text-violet-950">
                  Descripción facturada obligatoria
                </p>
                <p class="mt-1 text-sm text-violet-900">
                  Esto es el texto del ítem que verá el receptor, por ejemplo
                  Honorarios o Zapatillas. Es distinto del tipo fiscal ARCA.
                </p>
              </div>
            </div>

            <div class="mt-4 grid gap-3 text-sm text-gray-800 lg:grid-cols-2">
              <label class="rounded-lg border border-violet-100 bg-white p-3">
                <span class="flex items-center gap-2 font-medium">
                  <input
                    v-model="descripcionItemModo"
                    type="radio"
                    value="archivo"
                    class="h-4 w-4 text-primary-600"
                  />
                  Utilizar la descripción del archivo
                </span>
                <span class="mt-2 block text-xs text-gray-600">
                  El Excel debe traer una columna de descripción del ítem con
                  valor en todas las filas.
                </span>
              </label>
              <label class="rounded-lg border border-violet-100 bg-white p-3">
                <span class="flex flex-wrap items-center gap-2 font-medium">
                  <input
                    v-model="descripcionItemModo"
                    type="radio"
                    value="fija"
                    class="h-4 w-4 text-primary-600"
                  />
                  Utilizar esta descripción para todo el lote
                </span>
                <input
                  v-model="descripcionItemFija"
                  type="text"
                  :disabled="descripcionItemModo !== 'fija'"
                  placeholder="Ej.: Honorarios profesionales"
                  class="mt-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                />
              </label>
            </div>

            <BaseAlert
              v-if="!descripcionItemCompleta"
              type="warning"
              class="mt-4"
            >
              Defini la descripción facturada antes de validar. No se usará una
              descripción oculta del formato ni del sistema.
            </BaseAlert>
          </div>

          <div
            v-if="archivoSeleccionado"
            class="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4"
          >
            <div class="flex items-start gap-3">
              <ExclamationTriangleIcon
                class="mt-0.5 h-5 w-5 flex-shrink-0 text-rose-700"
              />
              <div>
                <p class="text-sm font-semibold text-rose-950">
                  Fechas fiscales obligatorias
                </p>
                <p class="mt-1 text-sm text-rose-900">
                  La fecha de emision no se completa automaticamente con la
                  fecha de hoy. Elegi que fecha se usara antes de validar.
                </p>
              </div>
            </div>

            <div class="mt-4 grid gap-4 xl:grid-cols-2">
              <div class="rounded-lg border border-rose-100 bg-white p-4">
                <p class="text-sm font-semibold text-gray-900">
                  Fecha de emision
                </p>
                <div class="mt-3 space-y-3 text-sm text-gray-700">
                  <label class="flex items-center gap-2">
                    <input
                      v-model="fechaEmisionModo"
                      type="radio"
                      value="archivo"
                      class="h-4 w-4 text-primary-600"
                    />
                    Utilizar la fecha del archivo
                  </label>
                  <label class="flex flex-wrap items-center gap-2">
                    <input
                      v-model="fechaEmisionModo"
                      type="radio"
                      value="fija"
                      class="h-4 w-4 text-primary-600"
                    />
                    Utilizar esta fecha para todos
                    <input
                      v-model="fechaEmisionFija"
                      type="date"
                      :disabled="fechaEmisionModo !== 'fija'"
                      class="rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                    />
                  </label>
                </div>
              </div>

              <div class="rounded-lg border border-rose-100 bg-white p-4">
                <p class="text-sm font-semibold text-gray-900">
                  Periodo y vencimiento de servicios
                </p>
                <div class="mt-3 space-y-4 text-sm text-gray-700">
                  <div>
                    <p class="font-medium text-gray-800">Desde</p>
                    <label class="mt-2 flex items-center gap-2">
                      <input
                        v-model="fechaServicioDesdeModo"
                        type="radio"
                        value="archivo"
                        class="h-4 w-4 text-primary-600"
                      />
                      Utilizar la fecha del archivo
                    </label>
                    <label class="mt-2 flex flex-wrap items-center gap-2">
                      <input
                        v-model="fechaServicioDesdeModo"
                        type="radio"
                        value="fija"
                        class="h-4 w-4 text-primary-600"
                      />
                      Fijar
                      <input
                        v-model="fechaServicioDesdeFija"
                        type="date"
                        :disabled="fechaServicioDesdeModo !== 'fija'"
                        class="rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                      />
                    </label>
                  </div>

                  <div>
                    <p class="font-medium text-gray-800">Hasta</p>
                    <label class="mt-2 flex items-center gap-2">
                      <input
                        v-model="fechaServicioHastaModo"
                        type="radio"
                        value="archivo"
                        class="h-4 w-4 text-primary-600"
                      />
                      Utilizar la fecha del archivo
                    </label>
                    <label class="mt-2 flex flex-wrap items-center gap-2">
                      <input
                        v-model="fechaServicioHastaModo"
                        type="radio"
                        value="fija"
                        class="h-4 w-4 text-primary-600"
                      />
                      Fijar
                      <input
                        v-model="fechaServicioHastaFija"
                        type="date"
                        :disabled="fechaServicioHastaModo !== 'fija'"
                        class="rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                      />
                    </label>
                  </div>

                  <div>
                    <p class="font-medium text-gray-800">Vencimiento de pago</p>
                    <label class="mt-2 flex items-center gap-2">
                      <input
                        v-model="fechaVtoPagoModo"
                        type="radio"
                        value="archivo"
                        class="h-4 w-4 text-primary-600"
                      />
                      Utilizar la fecha del archivo
                    </label>
                    <label class="mt-2 flex flex-wrap items-center gap-2">
                      <input
                        v-model="fechaVtoPagoModo"
                        type="radio"
                        value="fija"
                        class="h-4 w-4 text-primary-600"
                      />
                      Fijar
                      <input
                        v-model="fechaVtoPagoFija"
                        type="date"
                        :disabled="fechaVtoPagoModo !== 'fija'"
                        class="rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                      />
                    </label>
                  </div>
                </div>
              </div>
            </div>

            <BaseAlert
              v-if="!opcionesFechasCompletas"
              type="warning"
              class="mt-4"
            >
              Completa la decision de fechas antes de validar. Si una fecha del
              archivo queda fuera de la ventana ARCA, el lote quedara observado
              y deberas elegir una fecha permitida antes de emitir.
            </BaseAlert>
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
            <li>Fecha de emision confirmada antes de validar.</li>
            <li>Tipo de concepto fiscal ARCA confirmado antes de validar.</li>
            <li>Descripción facturada confirmada antes de validar.</li>
            <li>Periodo de servicios confirmado cuando corresponda.</li>
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
                  @click="solicitarConfirmacionEmisionLote"
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
                      class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-600"
                    >
                      Fecha fiscal
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-600"
                    >
                      Descripción facturada
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
                        {{ formatConcepto(grupo.concepto) }}
                      </p>
                      <p class="text-xs text-gray-500">
                        Punto de venta {{ grupo.punto_venta_numero || "-" }}
                      </p>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-700">
                      <p>Emision {{ formatDate(grupo.fecha_emision) }}</p>
                      <p
                        v-if="grupo.fecha_servicio_desde || grupo.fecha_servicio_hasta"
                        class="text-xs text-gray-500"
                      >
                        Servicio {{ formatDate(grupo.fecha_servicio_desde) }} -
                        {{ formatDate(grupo.fecha_servicio_hasta) }}
                      </p>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-700">
                      {{ descripcionFacturada(grupo.comprobante_ref) }}
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

    <ConfirmDialog
      :show="mostrarConfirmacionFechaFiscal"
      title="Confirmar fecha fiscal"
      :message="mensajeConfirmacionFechaFiscalLote"
      confirm-text="Emitir con esta fecha"
      cancel-text="Volver a revisar"
      variant="danger"
      @confirm="procesarLote"
      @cancel="mostrarConfirmacionFechaFiscal = false"
    />
  </div>
</template>
