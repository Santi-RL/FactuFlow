<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import ConfirmDialog from "@/components/common/ConfirmDialog.vue";
import Pagination from "@/components/common/Pagination.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseEmpty from "@/components/ui/BaseEmpty.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import { useNotification } from "@/composables/useNotification";
import formatosImportacionService from "@/services/formatos-importacion.service";
import lotesComprobantesService from "@/services/lotes-comprobantes.service";
import perfilesCargaMasivaService from "@/services/perfiles-carga-masiva.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import type {
  FormatoImportacion,
  FormatoImportacionCandidato,
  FormatoImportacionDeteccion,
} from "@/types/formato-importacion";
import type { PerfilCargaMasiva } from "@/types/perfil-carga-masiva";
import type { PuntoVenta } from "@/types/punto_venta";
import {
  ESTADOS_GRUPO_COLOR,
  ESTADOS_GRUPO_NOMBRES,
  ESTADOS_LOTE_COLOR,
  ESTADOS_LOTE_NOMBRES,
  type LoteComprobante,
  type LoteComprobanteGrupoDetalle,
  type LoteComprobanteResumen,
  type LoteOpcionesFechas,
  type ReconciliacionExternaItem,
} from "@/types/lote-comprobante";
import {
  resolverPerfilCargaMasiva,
  seleccionarPerfilInicial,
} from "@/utils/perfiles-carga-masiva";
import { calcularProgresoLote } from "@/utils/lote-progress";
import {
  ArchiveBoxIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  CloudArrowUpIcon,
  Cog6ToothIcon,
  DocumentDuplicateIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  TrashIcon,
} from "@heroicons/vue/24/outline";

const empresaStore = useEmpresaStore();
const { showError, showInfo, showSuccess, showWarning } = useNotification();
const GRUPOS_LOTE_PER_PAGE = 100;

interface ArcaBatchMetadata {
  fallback_unitario?: boolean;
  fallback_motivo?: unknown;
  reg_x_req?: unknown;
  chunk_size?: unknown;
  modo?: unknown;
}

const fileInputRef = ref<HTMLInputElement | null>(null);
const archivoSeleccionado = ref<File | null>(null);
const formatosImportacion = ref<FormatoImportacion[]>([]);
const perfilesCargaMasiva = ref<PerfilCargaMasiva[]>([]);
const puntosVenta = ref<PuntoVenta[]>([]);
const deteccionFormato = ref<FormatoImportacionDeteccion | null>(null);
const formatoSeleccionadoId = ref<string | number>("");
const perfilSeleccionadoId = ref<string | number>("");
const perfilAplicadoId = ref<number | null>(null);
const formatoAplicadoPorPerfilId = ref<number | null>(null);
const configuracionModificada = ref(false);
const aplicandoPerfil = ref(false);
const puntoVentaModo = ref<"archivo" | "fijo">("archivo");
const puntoVentaNumero = ref<number | "">("");
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
const loteActual = ref<LoteComprobanteResumen | null>(null);
const gruposLote = ref<LoteComprobanteGrupoDetalle[]>([]);
const gruposLotePage = ref(1);
const gruposLotePerPage = ref(GRUPOS_LOTE_PER_PAGE);
const gruposLoteTotal = ref(0);
const gruposLoteTotalPages = ref(0);
const grupoEstadoFiltro = ref<string | number>("");
const loadingLotes = ref(false);
const loadingGruposLote = ref(false);
const loadingPerfiles = ref(false);
const validandoArchivo = ref(false);
const detectandoFormato = ref(false);
const procesandoLote = ref(false);
const descargandoPlantilla = ref(false);
const descargandoObservado = ref(false);
const resolviendoLote = ref<
  "reintentar" | "descartar" | "reconciliar" | "compactar" | "eliminar" | null
>(null);
const mostrarConfirmacionFechaFiscal = ref(false);
const mostrarConfirmacionReintentoFallidos = ref(false);
const mostrarConfirmacionDuplicadoLogico = ref(false);
const mostrarConfirmacionCompactar = ref(false);
const idempotencyKeyProcesar = ref<string | null>(null);
const idempotencyKeyReintentar = ref<string | null>(null);
const confirmacionDuplicadoProcesar = ref<string | null>(null);
const confirmacionDuplicadoReintentar = ref<string | null>(null);
const confirmacionDuplicadoPendiente = ref<"procesar" | "reintentar" | null>(
  null,
);
const tokenDuplicadoPendiente = ref("");
const mensajeConfirmacionDuplicadoLogico = ref("");
const motivoDescartar = ref("");
const motivoEliminar = ref("");
const externoGrupoId = ref<number | "">("");
const externoNumero = ref<number | "">("");
const externoCae = ref("");
const externoMotivo = ref("");
const pollingHandle = ref<number | null>(null);
const timerHandle = ref<number | null>(null);
const timerNow = ref(new Date());
const inicioProcesamientoLocal = ref<Date | null>(null);
let deteccionFormatoRequestId = 0;

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
const arcaBatchMetadata = computed<ArcaBatchMetadata | null>(() => {
  const metadata = loteActual.value?.metadata_json;
  const arcaBatch = metadata?.arca_batch;
  if (!arcaBatch || typeof arcaBatch !== "object") return null;
  return arcaBatch as ArcaBatchMetadata;
});
const mostrarAvisoFallbackArca = computed(
  () => arcaBatchMetadata.value?.fallback_unitario === true,
);
const motivoFallbackArca = computed(() => {
  const motivo = arcaBatchMetadata.value?.fallback_motivo;
  return typeof motivo === "string" && motivo.trim() ? motivo.trim() : "";
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
      label: `${formato.nombre} (${formato.alcance === "global" ? "global" : "emisor"})`,
    }));
});
const plantillaSeleccionada = computed(() => {
  const selected = Number(formatoSeleccionadoId.value || 0);
  if (!selected) return null;
  return (
    formatosImportacion.value.find(
      (formato) => formato.version_vigente?.id === selected,
    ) || null
  );
});
const perfilesOptions = computed(() => [
  {
    value: "",
    label: "Sin perfil de carga masiva",
  },
  ...perfilesCargaMasiva.value.map((perfil) => ({
    value: perfil.id,
    label: perfil.es_predeterminado
      ? `${perfil.nombre} (predeterminado)`
      : perfil.nombre,
  })),
]);
const puntosVentaFactuflow = computed(() =>
  puntosVenta.value.filter((punto) => punto.usable_factuflow),
);
const puntoVentaOptions = computed(() => [
  { value: "", label: "Seleccioná un punto de venta" },
  ...puntosVentaFactuflow.value.map((punto) => ({
    value: punto.numero,
    label: `${String(punto.numero).padStart(4, "0")}${
      punto.nombre ? ` - ${punto.nombre}` : ""
    }`,
  })),
]);
const estadosGruposOptions = computed(() => [
  { value: "", label: "Todos los estados" },
  { value: "validado", label: "Listos para emitir" },
  { value: "con_error", label: "Con observaciones" },
  { value: "autorizado", label: "Autorizados" },
  { value: "autorizado_externo", label: "Autorizados externos" },
  { value: "fallido", label: "Fallidos" },
  { value: "requiere_reconciliacion", label: "Requiere reconciliación" },
  { value: "reintentando", label: "Reintento pendiente de verificar" },
  { value: "descartado", label: "Descartados" },
]);
const perfilAplicado = computed(() => {
  if (!perfilAplicadoId.value) return null;
  return (
    perfilesCargaMasiva.value.find(
      (perfil) => perfil.id === perfilAplicadoId.value,
    ) || null
  );
});
const candidatoPrincipal = computed<FormatoImportacionCandidato | null>(() => {
  return deteccionFormato.value?.candidatos[0] || null;
});
const candidatoSeleccionado = computed<FormatoImportacionCandidato | null>(
  () => {
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
  },
);
const requiereElegirFormato = computed(() => {
  if (!archivoSeleccionado.value || detectandoFormato.value) return false;
  if (hayConflictoFormatoPerfil.value) return true;
  if (!deteccionFormato.value) return true;
  const principal = candidatoPrincipal.value;
  if (!principal) return !formatoSeleccionadoId.value;
  if (principal.formato_version_id === null && principal.confianza === "alta") {
    return false;
  }
  return !formatoSeleccionadoId.value;
});
const hayConflictoFormatoPerfil = computed(() => {
  const perfilVersion = formatoAplicadoPorPerfilId.value;
  const principal = candidatoPrincipal.value;
  if (!perfilVersion || !principal || principal.confianza !== "alta")
    return false;
  if (principal.formato_version_id === perfilVersion) return false;
  return Number(formatoSeleccionadoId.value || 0) === perfilVersion;
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
  punto_venta_modo: puntoVentaModo.value,
  punto_venta_numero:
    puntoVentaModo.value === "fijo"
      ? Number(puntoVentaNumero.value)
      : undefined,
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
    (puntoVentaModo.value === "archivo" || !!puntoVentaNumero.value) &&
    !!conceptoModo.value &&
    descripcionItemCompleta.value &&
    opcionesFechasCompletas.value,
);
const puedeProcesar = computed(() => {
  if (!loteActual.value) return false;

  return (
    loteActual.value.grupos_validos > 0 &&
    loteActual.value.estado === "validado"
  );
});
const hayFallidosParaReintentar = computed(
  () => (loteActual.value?.grupos_fallidos || 0) > 0,
);
const gruposRequierenReconciliacionVisibles = computed(() =>
  gruposLote.value.filter((grupo) =>
    ["requiere_reconciliacion", "reintentando"].includes(grupo.estado),
  ),
);
const totalPendientesResolucion = computed(() => {
  if (!loteActual.value) return 0;
  return (
    loteActual.value.grupos_validos +
    loteActual.value.grupos_con_error +
    loteActual.value.grupos_fallidos +
    gruposRequierenReconciliacionVisibles.value.length
  );
});
const gruposDescartablesVisibles = computed(() =>
  gruposLote.value.filter((grupo) =>
    ["validado", "con_error", "fallido"].includes(grupo.estado),
  ),
);
const gruposReconciliablesVisibles = computed(() =>
  gruposLote.value.filter((grupo) =>
    [
      "validado",
      "con_error",
      "fallido",
      "requiere_reconciliacion",
      "reintentando",
    ].includes(grupo.estado),
  ),
);
const gruposDescartablesVisiblesIds = computed(() =>
  gruposDescartablesVisibles.value.map((grupo) => grupo.id),
);
const hayPendientesResolucionVisibles = computed(
  () =>
    gruposDescartablesVisibles.value.length > 0 ||
    gruposReconciliablesVisibles.value.length > 0,
);
const loteCerrado = computed(() =>
  ["completado", "cerrado_reconciliado", "cerrado_con_descartes"].includes(
    loteActual.value?.estado || "",
  ),
);
const puedeCompactarLote = computed(
  () =>
    !!loteActual.value && loteCerrado.value && !loteActual.value.compactado_at,
);
const puedeEliminarLote = computed(() => {
  if (!loteActual.value) return false;
  if (
    ["en_cola", "procesando", "requiere_reconciliacion"].includes(
      loteActual.value.estado,
    )
  ) {
    return false;
  }
  return (
    loteActual.value.grupos_emitidos === 0 &&
    loteActual.value.grupos_reconciliados_externos === 0
  );
});
const grupoExternoSeleccionado = computed(() =>
  gruposReconciliablesVisibles.value.find(
    (grupo) => grupo.id === Number(externoGrupoId.value || 0),
  ),
);
const grupoExternoOptions = computed(() => [
  { value: "", label: "Seleccioná un comprobante visible" },
  ...gruposReconciliablesVisibles.value.map((grupo) => ({
    value: grupo.id,
    label: `${grupo.comprobante_ref} · ${formatMoney(grupo.total_estimado)}`,
  })),
]);
const puedeReconciliarExterno = computed(() => {
  return (
    !!grupoExternoSeleccionado.value &&
    Number(externoNumero.value || 0) > 0 &&
    externoMotivo.value.trim().length >= 3
  );
});
const puedeDescartarVisibles = computed(
  () =>
    gruposDescartablesVisiblesIds.value.length > 0 &&
    motivoDescartar.value.trim().length >= 3,
);
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
      hint: "Necesitan corrección antes de volver a subir el archivo.",
    },
    {
      label: "Ya emitidos",
      value: loteActual.value.grupos_emitidos,
      hint: "Comprobantes autorizados con CAE.",
    },
    {
      label: "Emitidos fuera",
      value: loteActual.value.grupos_reconciliados_externos,
      hint: "Comprobantes reconciliados desde ARCA Web.",
    },
    {
      label: "Descartados",
      value: loteActual.value.grupos_descartados,
      hint: "Pendientes cerrados por decisión operativa.",
    },
  ];
});
const totalesListosParaEmitir = computed(() => {
  const totales = loteActual.value?.totales_listos_para_emitir;
  return {
    comprobantes: totales?.comprobantes || 0,
    neto: totales?.neto || 0,
    iva21: totales?.iva21 || 0,
    iva105: totales?.iva105 || 0,
    total: totales?.total || 0,
    valoresInvalidos: totales?.valores_invalidos || 0,
  };
});
const progresoLote = computed(() => {
  if (!loteActual.value) return null;
  const inicioLocal = ["en_cola", "procesando"].includes(
    loteActual.value.estado,
  )
    ? inicioProcesamientoLocal.value
    : null;
  return calcularProgresoLote(loteActual.value, timerNow.value, inicioLocal);
});
const porcentajeProcesado = computed(() => {
  return progresoLote.value?.porcentaje || 0;
});
const resumenAvanceLote = computed(() => {
  if (!progresoLote.value) return "Sin lote seleccionado";
  if (progresoLote.value.totalEmitible === 0) {
    return "No hay comprobantes listos para emitir";
  }
  if (progresoLote.value.estaEnCola) {
    return `En cola para procesar ${progresoLote.value.totalEmitible} comprobantes`;
  }
  if (progresoLote.value.estaProcesando) {
    return `Procesando ${progresoLote.value.procesados} de ${progresoLote.value.totalEmitible} comprobantes`;
  }
  return `${progresoLote.value.procesados} de ${progresoLote.value.totalEmitible} comprobantes procesados`;
});
const detalleAvanceLote = computed(() => {
  if (!progresoLote.value) return "";
  return `Emitidos ${loteActual.value?.grupos_emitidos || 0} · Fallidos ${
    loteActual.value?.grupos_fallidos || 0
  } · Pendientes ${progresoLote.value.pendientes}`;
});
const mostrarBarraIndeterminada = computed(() => {
  return (
    !!progresoLote.value &&
    progresoLote.value.estaActivo &&
    (progresoLote.value.estaEnCola || progresoLote.value.procesados === 0)
  );
});
const tiempoRestanteTexto = computed(() => {
  if (!progresoLote.value) return "-";
  if (progresoLote.value.estaActivo) return progresoLote.value.restanteTexto;
  if (progresoLote.value.restanteSegundos === 0) return "00:00";
  return "-";
});
const necesitaCorreccion = computed(() => {
  return !!loteActual.value && loteActual.value.grupos_con_error > 0;
});

const fechasEmisionValidas = computed(() => {
  return (loteActual.value?.fechas_emision_validas || []).map((fecha) =>
    formatDate(fecha),
  );
});

const puntosVentaValidos = computed(() => {
  return [...(loteActual.value?.puntos_venta_validos || [])].sort(
    (a, b) => a - b,
  );
});

const confirmacionFechaFiscalLote = computed(() => {
  return loteActual.value?.confirmacion_fecha_fiscal || "";
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
  return (
    loteActual.value?.mensaje_confirmacion_fecha_fiscal ||
    `Está seguro que quiere emitir comprobantes con fecha ${resumenFechasConfirmacion.value}${resumenPuntosVentaConfirmacion.value}? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`
  );
});

const confirmacionReintentoFallidos = computed(() => {
  return loteActual.value?.confirmacion_reintento_fallidos || "";
});

const mensajeConfirmacionReintentoFallidos = computed(() => {
  return (
    loteActual.value?.mensaje_confirmacion_reintento_fallidos ||
    "¿Está seguro que quiere reintentar los comprobantes fallidos? Recuerde que una emisión autorizada por ARCA no se puede deshacer."
  );
});

const mensajeConfirmacionCompactar = computed(() => {
  return (
    "Al compactar se eliminará el detalle original por fila del Excel para ahorrar espacio. " +
    "Se conservarán el resumen del lote, los comprobantes agrupados, los CAE, los comprobantes emitidos y la auditoría. " +
    "Después no podrás descargar el archivo observado de este lote."
  );
});

const paginaGruposInicio = computed(() => {
  if (gruposLoteTotal.value === 0) return 0;
  return (gruposLotePage.value - 1) * gruposLotePerPage.value + 1;
});

const paginaGruposFin = computed(() =>
  Math.min(gruposLotePage.value * gruposLotePerPage.value, gruposLoteTotal.value),
);

const resumenPaginacionGrupos = computed(() => {
  if (gruposLoteTotal.value === 0) {
    return "No hay comprobantes para el filtro seleccionado.";
  }
  return `Mostrando ${paginaGruposInicio.value} a ${paginaGruposFin.value} de ${gruposLoteTotal.value} comprobantes.`;
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

const descripcionFacturada = (grupo: LoteComprobanteGrupoDetalle) => {
  return grupo.descripcion_facturada?.trim() || "-";
};

const crearIdempotencyKey = (): string => {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `ff-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const obtenerIdempotencyKeyProcesar = (): string => {
  if (!idempotencyKeyProcesar.value) {
    idempotencyKeyProcesar.value = crearIdempotencyKey();
  }
  return idempotencyKeyProcesar.value;
};

const obtenerIdempotencyKeyReintentar = (): string => {
  if (!idempotencyKeyReintentar.value) {
    idempotencyKeyReintentar.value = crearIdempotencyKey();
  }
  return idempotencyKeyReintentar.value;
};

const resetearIdempotencyKeyProcesar = () => {
  idempotencyKeyProcesar.value = null;
  confirmacionDuplicadoProcesar.value = null;
};

const resetearIdempotencyKeyReintentar = () => {
  idempotencyKeyReintentar.value = null;
  confirmacionDuplicadoReintentar.value = null;
};

const resetearConfirmacionDuplicadoPendiente = () => {
  mostrarConfirmacionDuplicadoLogico.value = false;
  confirmacionDuplicadoPendiente.value = null;
  tokenDuplicadoPendiente.value = "";
  mensajeConfirmacionDuplicadoLogico.value = "";
};

const limpiarConfiguracionLote = () => {
  formatoSeleccionadoId.value = "";
  formatoAplicadoPorPerfilId.value = null;
  puntoVentaModo.value = "archivo";
  puntoVentaNumero.value = "";
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

const aplicarPerfilCargaMasiva = (
  perfil: PerfilCargaMasiva,
  mostrarAviso = true,
) => {
  aplicandoPerfil.value = true;
  const perfilAplicadoLote = resolverPerfilCargaMasiva(perfil);
  perfilSeleccionadoId.value = perfil.id;
  perfilAplicadoId.value = perfil.id;
  formatoAplicadoPorPerfilId.value =
    Number(perfilAplicadoLote.formatoVersionId || 0) || null;
  formatoSeleccionadoId.value = perfilAplicadoLote.formatoVersionId || "";
  puntoVentaModo.value = perfilAplicadoLote.opciones.punto_venta_modo;
  puntoVentaNumero.value = perfilAplicadoLote.opciones.punto_venta_numero || "";
  conceptoModo.value = perfilAplicadoLote.opciones.concepto_modo;
  descripcionItemModo.value = perfilAplicadoLote.opciones.descripcion_item_modo;
  descripcionItemFija.value =
    perfilAplicadoLote.opciones.descripcion_item_fija || "";
  fechaEmisionModo.value = perfilAplicadoLote.opciones.fecha_emision_modo;
  fechaEmisionFija.value = perfilAplicadoLote.opciones.fecha_emision_fija || "";
  fechaServicioDesdeModo.value =
    perfilAplicadoLote.opciones.fecha_servicio_desde_modo;
  fechaServicioDesdeFija.value =
    perfilAplicadoLote.opciones.fecha_servicio_desde_fija || "";
  fechaServicioHastaModo.value =
    perfilAplicadoLote.opciones.fecha_servicio_hasta_modo;
  fechaServicioHastaFija.value =
    perfilAplicadoLote.opciones.fecha_servicio_hasta_fija || "";
  fechaVtoPagoModo.value = perfilAplicadoLote.opciones.fecha_vto_pago_modo;
  fechaVtoPagoFija.value =
    perfilAplicadoLote.opciones.fecha_vto_pago_fija || "";
  configuracionModificada.value = false;
  window.setTimeout(() => {
    aplicandoPerfil.value = false;
  });

  if (mostrarAviso) {
    showInfo(
      "Perfil de carga masiva aplicado",
      "La configuración quedó completa en pantalla y puedes editarla antes de validar.",
    );
  }
};

const aplicarPerfilInicial = () => {
  if (perfilesCargaMasiva.value.length === 0 || perfilAplicadoId.value) return;
  const perfil = seleccionarPerfilInicial(perfilesCargaMasiva.value);
  if (perfil) {
    aplicarPerfilCargaMasiva(perfil, false);
  }
};

const handlePerfilSeleccionado = () => {
  const perfilId = Number(perfilSeleccionadoId.value || 0);
  if (!perfilId) {
    perfilAplicadoId.value = null;
    formatoAplicadoPorPerfilId.value = null;
    configuracionModificada.value = false;
    limpiarConfiguracionLote();
    return;
  }
  const perfil = perfilesCargaMasiva.value.find((item) => item.id === perfilId);
  if (perfil) {
    aplicarPerfilCargaMasiva(perfil);
  }
};

const usarFormatoSugerido = () => {
  formatoSeleccionadoId.value =
    candidatoPrincipal.value?.formato_version_id || "";
  formatoAplicadoPorPerfilId.value = null;
};

const usarFormatoDelPerfil = () => {
  formatoSeleccionadoId.value = formatoAplicadoPorPerfilId.value || "";
};

const triggerFileSelection = () => {
  fileInputRef.value?.click();
};

const handleArchivoSeleccionado = (event: Event) => {
  const target = event.target as HTMLInputElement;
  deteccionFormatoRequestId += 1;
  archivoSeleccionado.value = target.files?.[0] || null;
  deteccionFormato.value = null;
  resetearIdempotencyKeyProcesar();
  resetearIdempotencyKeyReintentar();
  resetearConfirmacionDuplicadoPendiente();
  if (perfilAplicado.value) {
    aplicarPerfilCargaMasiva(perfilAplicado.value, false);
  } else {
    limpiarConfiguracionLote();
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

const cargarPerfilesCargaMasiva = async () => {
  if (!empresaActivaId.value) return;

  loadingPerfiles.value = true;
  try {
    perfilesCargaMasiva.value = await perfilesCargaMasivaService.listar();
    aplicarPerfilInicial();
  } catch (error: any) {
    showError(
      "No se pudieron cargar los perfiles de carga masiva",
      error.response?.data?.detail ||
        "Revisa tu sesion antes de validar archivos.",
    );
  } finally {
    loadingPerfiles.value = false;
  }
};

const cargarPuntosVenta = async () => {
  if (!empresaActivaId.value) return;

  try {
    puntosVenta.value = await puntosVentaService.getAll();
  } catch (error: any) {
    showError(
      "No se pudieron cargar los puntos de venta",
      error.response?.data?.detail ||
        "Revisa Puntos de venta antes de validar archivos.",
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

  const requestId = ++deteccionFormatoRequestId;
  const sigueVigente = () =>
    requestId === deteccionFormatoRequestId &&
    archivoSeleccionado.value === archivo;

  detectandoFormato.value = true;
  try {
    if (formatosImportacion.value.length === 0) {
      await cargarFormatosImportacion();
      if (!sigueVigente()) return;
    }
    const resultado = await formatosImportacionService.detectar(archivo);
    if (!sigueVigente()) return;
    deteccionFormato.value = resultado;
    if (!formatoAplicadoPorPerfilId.value) {
      formatoSeleccionadoId.value = resultado.formato_sugerido_version_id || "";
    }

    if (resultado.candidatos.length === 0) {
      showWarning(
        "Formato no reconocido",
        "El sistema no encontro un formato confiable. Selecciona uno antes de validar.",
      );
    }
  } catch (error: any) {
    if (!sigueVigente()) return;
    deteccionFormato.value = null;
    formatoSeleccionadoId.value = "";
    showError(
      "No se pudo detectar el formato",
      error.response?.data?.detail ||
        "Puedes seleccionar un formato manualmente e intentar validar.",
    );
  } finally {
    if (sigueVigente()) {
      detectandoFormato.value = false;
    }
  }
};

const cargarGruposLote = async (
  loteId: number,
  page = gruposLotePage.value,
  silent = false,
) => {
  try {
    if (!silent) {
      loadingGruposLote.value = true;
    }
    const estado =
      typeof grupoEstadoFiltro.value === "string" && grupoEstadoFiltro.value
        ? grupoEstadoFiltro.value
        : null;
    const pagina = await lotesComprobantesService.obtenerGrupos(loteId, {
      page,
      perPage: gruposLotePerPage.value,
      estado,
    });
    gruposLote.value = pagina.items;
    gruposLotePage.value = pagina.page;
    gruposLotePerPage.value = pagina.per_page;
    gruposLoteTotal.value = pagina.total;
    gruposLoteTotalPages.value = pagina.total_pages;
  } catch (error: any) {
    showError(
      "No se pudo cargar el detalle",
      error.response?.data?.detail ||
        "Intenta cambiar de pagina o abrir el lote nuevamente.",
    );
  } finally {
    if (!silent) {
      loadingGruposLote.value = false;
    }
  }
};

const cargarDetalleLote = async (loteId: number, silent = false) => {
  try {
    if (!silent) {
      loadingLotes.value = true;
    }
    const esNuevoLote = loteActual.value?.id !== loteId;
    if (esNuevoLote) {
      gruposLote.value = [];
      gruposLotePage.value = 1;
      gruposLoteTotal.value = 0;
      gruposLoteTotalPages.value = 0;
      grupoEstadoFiltro.value = "";
      resetearIdempotencyKeyProcesar();
      resetearIdempotencyKeyReintentar();
      resetearConfirmacionDuplicadoPendiente();
    }
    loteActual.value = await lotesComprobantesService.obtenerResumen(loteId);
    await cargarGruposLote(loteId, esNuevoLote ? 1 : gruposLotePage.value, true);
  } catch (error: any) {
    showError(
      "No se pudo abrir el lote",
      error.response?.data?.detail ||
        "El lote ya no está disponible para esta empresa.",
    );
  } finally {
    if (!silent) {
      loadingLotes.value = false;
    }
  }
};

const cambiarPaginaGrupos = async (page: number) => {
  if (!loteActual.value || page === gruposLotePage.value) return;
  await cargarGruposLote(loteActual.value.id, page);
};

const cambiarFiltroGrupos = async (value?: string | number) => {
  if (value !== undefined) {
    grupoEstadoFiltro.value = value;
  }
  if (!loteActual.value) return;
  gruposLotePage.value = 1;
  await cargarGruposLote(loteActual.value.id, 1);
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
    const plantilla = plantillaSeleccionada.value;
    if (formatoSeleccionadoId.value && !plantilla) {
      showError(
        "Plantilla no disponible",
        "El perfil apunta a una versión de plantilla que ya no está vigente. Actualiza el perfil o elegí una plantilla vigente antes de descargar.",
      );
      return;
    }
    const archivo = plantilla
      ? await formatosImportacionService.descargar(plantilla.id)
      : await lotesComprobantesService.descargarPlantilla();
    const filename = plantilla
      ? `plantilla-${plantilla.nombre.replace(/\W+/g, "-").toLowerCase()}.xlsx`
      : `factuflow-lote-${empresaActiva.value.cuit}.xlsx`;
    downloadBlob(archivo, filename);
    showSuccess(
      "Plantilla lista",
      plantilla
        ? `Descargaste la plantilla ${plantilla.nombre}.`
        : "Completá una fila por ítem y repetí los datos del comprobante en todas las filas del mismo comprobante_ref.",
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
      perfilAplicadoId.value,
    );
    showSuccess("Archivo validado", resultado.mensaje);
    await cargarLotes(true);
    await cargarDetalleLote(resultado.lote.id, true);

    if (resultado.requiere_background) {
      showInfo(
        "Lote grande detectado",
        "Como supera el límite síncrono, la emisión se ejecutará en segundo plano cuando la confirmes.",
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

const prepararConfirmacionDuplicadoLogico = (
  error: any,
  accion: "procesar" | "reintentar",
) => {
  const detail = error.response?.data?.detail;
  if (detail?.categoria_error !== "duplicado_logico_lote") {
    return false;
  }

  const token = detail.confirmacion_duplicado_logico;
  if (!token) return false;

  confirmacionDuplicadoPendiente.value = accion;
  tokenDuplicadoPendiente.value = token;
  mensajeConfirmacionDuplicadoLogico.value =
    [detail.mensaje, ...(detail.errores || [])].filter(Boolean).join(" ") ||
    "Se detectaron comprobantes probablemente duplicados. Confirmá si corresponde solicitar CAE igualmente.";
  mostrarConfirmacionDuplicadoLogico.value = true;
  return true;
};

const detalleErrorComoTexto = (detail: unknown, fallback: string): string => {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (!detail || typeof detail !== "object") {
    return fallback;
  }

  const data = detail as { mensaje?: unknown; errores?: unknown };
  const partes: string[] = [];
  if (typeof data.mensaje === "string" && data.mensaje.trim()) {
    partes.push(data.mensaje.trim());
  }
  if (Array.isArray(data.errores)) {
    partes.push(
      ...data.errores
        .filter((item): item is string => typeof item === "string")
        .map((item) => item.trim())
        .filter(Boolean),
    );
  }
  return partes.join(" ") || fallback;
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
  inicioProcesamientoLocal.value = new Date();
  timerNow.value = new Date();
  try {
    const resultado = await lotesComprobantesService.procesar(
      loteActual.value.id,
      confirmacionFechaFiscalLote.value,
      obtenerIdempotencyKeyProcesar(),
      confirmacionDuplicadoProcesar.value || undefined,
    );
    showSuccess(
      resultado.en_progreso ? "Emisión iniciada" : "Lote procesado",
      resultado.mensaje,
    );
    await cargarLotes(true);
    await cargarDetalleLote(loteActual.value.id, true);
    if (!resultado.en_progreso) {
      inicioProcesamientoLocal.value = null;
    }
  } catch (error: any) {
    inicioProcesamientoLocal.value = null;
    if (prepararConfirmacionDuplicadoLogico(error, "procesar")) {
      return;
    }
    showError(
      "No se pudo emitir el lote",
      detalleErrorComoTexto(
        error.response?.data?.detail,
        "Revisa las observaciones y vuelve a intentarlo.",
      ),
    );
  } finally {
    procesandoLote.value = false;
  }
};

const solicitarConfirmacionEmisionLote = () => {
  if (!puedeProcesar.value) return;
  mostrarConfirmacionFechaFiscal.value = true;
};

const refrescarLoteDespuesAccion = async (loteId: number) => {
  await cargarLotes(true);
  await cargarDetalleLote(loteId, true);
};

const solicitarConfirmacionReintentoFallidos = () => {
  if (!hayFallidosParaReintentar.value) {
    showWarning(
      "Sin fallidos para reintentar",
      "El lote no tiene comprobantes fallidos pendientes.",
    );
    return;
  }
  mostrarConfirmacionReintentoFallidos.value = true;
};

const reintentarFallidos = async () => {
  if (!loteActual.value) return;
  const loteId = loteActual.value.id;
  mostrarConfirmacionReintentoFallidos.value = false;
  resolviendoLote.value = "reintentar";

  try {
    const resultado = await lotesComprobantesService.reintentarFallidos(
      loteId,
      [],
      confirmacionReintentoFallidos.value,
      obtenerIdempotencyKeyReintentar(),
      confirmacionDuplicadoReintentar.value || undefined,
    );
    showSuccess("Reintento finalizado", resultado.mensaje);
    await refrescarLoteDespuesAccion(loteId);
    resetearIdempotencyKeyReintentar();
  } catch (error: any) {
    if (prepararConfirmacionDuplicadoLogico(error, "reintentar")) {
      return;
    }
    showError(
      "No se pudieron reintentar los fallidos",
      detalleErrorComoTexto(
        error.response?.data?.detail,
        "Revisa la fecha fiscal confirmada y el estado del lote.",
      ),
    );
  } finally {
    resolviendoLote.value = null;
  }
};

const confirmarDuplicadoLogicoLote = async () => {
  const accion = confirmacionDuplicadoPendiente.value;
  const token = tokenDuplicadoPendiente.value;
  resetearConfirmacionDuplicadoPendiente();

  if (accion === "procesar") {
    confirmacionDuplicadoProcesar.value = token;
    await procesarLote();
  } else if (accion === "reintentar") {
    confirmacionDuplicadoReintentar.value = token;
    await reintentarFallidos();
  }
};

const descartarGruposVisibles = async () => {
  if (!loteActual.value) return;
  const grupoIds = gruposDescartablesVisiblesIds.value;
  if (grupoIds.length === 0) {
    showWarning(
      "Sin comprobantes descartables",
      "La página actual no tiene comprobantes pendientes que puedan descartarse.",
    );
    return;
  }
  if (motivoDescartar.value.trim().length < 3) {
    showWarning(
      "Motivo requerido",
      "Indica por qué esos comprobantes no se van a emitir desde FactuFlow.",
    );
    return;
  }

  const loteId = loteActual.value.id;
  resolviendoLote.value = "descartar";
  try {
    const resultado = await lotesComprobantesService.descartarGrupos(
      loteId,
      grupoIds,
      motivoDescartar.value.trim(),
    );
    motivoDescartar.value = "";
    showSuccess("Comprobantes descartados", resultado.mensaje);
    await refrescarLoteDespuesAccion(loteId);
  } catch (error: any) {
    showError(
      "No se pudieron descartar",
      error.response?.data?.detail ||
        "Revisa que los comprobantes sigan pendientes y no emitidos.",
    );
  } finally {
    resolviendoLote.value = null;
  }
};

const reconciliarExterno = async () => {
  if (!loteActual.value || !grupoExternoSeleccionado.value) return;
  const grupo = grupoExternoSeleccionado.value;
  if (!grupo.tipo_comprobante || !grupo.punto_venta_numero || !grupo.fecha_emision) {
    showWarning(
      "Datos incompletos",
      "El comprobante seleccionado no tiene tipo, punto de venta o fecha fiscal para reconciliar.",
    );
    return;
  }

  const numero = Number(externoNumero.value || 0);
  if (numero <= 0 || externoMotivo.value.trim().length < 3) {
    showWarning(
      "Datos requeridos",
      "Indica el número autorizado en ARCA y un motivo operativo.",
    );
    return;
  }

  const loteId = loteActual.value.id;
  const comprobante: ReconciliacionExternaItem = {
    grupo_id: grupo.id,
    tipo_comprobante: grupo.tipo_comprobante,
    punto_venta_numero: grupo.punto_venta_numero,
    numero,
    fecha_emision: grupo.fecha_emision,
    total: Number(grupo.total_estimado || 0),
    cae: externoCae.value.trim() || undefined,
    motivo: externoMotivo.value.trim(),
  };

  resolviendoLote.value = "reconciliar";
  try {
    const resultado = await lotesComprobantesService.reconciliarExternos(
      loteId,
      [comprobante],
    );
    externoGrupoId.value = "";
    externoNumero.value = "";
    externoCae.value = "";
    externoMotivo.value = "";
    showSuccess("Comprobante reconciliado", resultado.mensaje);
    await refrescarLoteDespuesAccion(loteId);
  } catch (error: any) {
    showError(
      "No se pudo reconciliar",
      error.response?.data?.detail ||
        "FactuFlow no pudo verificar ese comprobante contra ARCA.",
    );
  } finally {
    resolviendoLote.value = null;
  }
};

const compactarLote = async () => {
  if (!loteActual.value) return;
  const loteId = loteActual.value.id;
  mostrarConfirmacionCompactar.value = false;
  resolviendoLote.value = "compactar";
  try {
    const resultado = await lotesComprobantesService.compactar(loteId);
    showSuccess("Lote compactado", resultado.mensaje);
    await refrescarLoteDespuesAccion(loteId);
  } catch (error: any) {
    showError(
      "No se pudo compactar",
      error.response?.data?.detail ||
        "Solo se pueden compactar lotes cerrados.",
    );
  } finally {
    resolviendoLote.value = null;
  }
};

const eliminarLote = async () => {
  if (!loteActual.value) return;
  if (motivoEliminar.value.trim().length < 3) {
    showWarning(
      "Motivo requerido",
      "Indica por qué quieres eliminar este lote sin emisión.",
    );
    return;
  }

  const loteId = loteActual.value.id;
  resolviendoLote.value = "eliminar";
  try {
    await lotesComprobantesService.eliminar(loteId, motivoEliminar.value.trim());
    motivoEliminar.value = "";
    loteActual.value = null;
    gruposLote.value = [];
    gruposLotePage.value = 1;
    gruposLoteTotal.value = 0;
    gruposLoteTotalPages.value = 0;
    showSuccess(
      "Lote eliminado",
      "Se eliminó el lote porque no tenía comprobantes emitidos ni inciertos.",
    );
    await cargarLotes(true);
    if (lotes.value[0]) {
      await cargarDetalleLote(lotes.value[0].id, true);
    }
  } catch (error: any) {
    showError(
      "No se pudo eliminar",
      error.response?.data?.detail ||
        "No se eliminan lotes con emisión o incertidumbre fiscal.",
    );
  } finally {
    resolviendoLote.value = null;
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
  if (loteActual.value.compactado_at) {
    showWarning(
      "Lote compactado",
      "El detalle de filas ya fue eliminado para ahorrar espacio. El resumen del lote sigue disponible.",
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
  if (!inicioProcesamientoLocal.value) {
    inicioProcesamientoLocal.value = new Date();
  }

  pollingHandle.value = window.setInterval(async () => {
    await cargarLotes(true);
    if (loteActual.value) {
      await cargarDetalleLote(loteActual.value.id, true);
    }
  }, 1500);
};

const detenerPolling = () => {
  if (pollingHandle.value === null) return;

  window.clearInterval(pollingHandle.value);
  pollingHandle.value = null;
  inicioProcesamientoLocal.value = null;
};

const iniciarTimer = () => {
  if (timerHandle.value !== null) return;
  timerNow.value = new Date();
  timerHandle.value = window.setInterval(() => {
    timerNow.value = new Date();
  }, 1000);
};

const detenerTimer = () => {
  if (timerHandle.value === null) return;

  window.clearInterval(timerHandle.value);
  timerHandle.value = null;
};

watch(hayProcesamientoEnCurso, (activo) => {
  if (activo) {
    iniciarPolling();
    iniciarTimer();
  } else {
    detenerPolling();
    detenerTimer();
  }
});

watch([archivoSeleccionado, empresaActivaId], ([archivo, empresaId]) => {
  if (!archivo || !empresaId || deteccionFormato.value) {
    return;
  }
  detectarFormatoArchivo(archivo);
});

watch(
  [
    formatoSeleccionadoId,
    puntoVentaModo,
    puntoVentaNumero,
    conceptoModo,
    descripcionItemModo,
    descripcionItemFija,
    fechaEmisionModo,
    fechaEmisionFija,
    fechaServicioDesdeModo,
    fechaServicioDesdeFija,
    fechaServicioHastaModo,
    fechaServicioHastaFija,
    fechaVtoPagoModo,
    fechaVtoPagoFija,
  ],
  () => {
    if (aplicandoPerfil.value || !perfilAplicadoId.value) return;
    configuracionModificada.value = true;
    perfilAplicadoId.value = null;
    formatoAplicadoPorPerfilId.value = null;
  },
);

watch(
  empresaActivaId,
  async (empresaId) => {
    archivoSeleccionado.value = null;
    loteActual.value = null;
    gruposLote.value = [];
    gruposLotePage.value = 1;
    gruposLoteTotal.value = 0;
    gruposLoteTotalPages.value = 0;
    grupoEstadoFiltro.value = "";
    resetearIdempotencyKeyProcesar();
    resetearIdempotencyKeyReintentar();
    resetearConfirmacionDuplicadoPendiente();
    deteccionFormato.value = null;
    perfilesCargaMasiva.value = [];
    perfilSeleccionadoId.value = "";
    perfilAplicadoId.value = null;
    configuracionModificada.value = false;
    limpiarConfiguracionLote();

    if (!empresaId) return;
    await cargarFormatosImportacion();
    await cargarPuntosVenta();
    await cargarPerfilesCargaMasiva();
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
  await cargarPuntosVenta();
  await cargarPerfilesCargaMasiva();
  if (lotes.value[0]) {
    await cargarDetalleLote(lotes.value[0].id);
  }
});

onBeforeUnmount(() => {
  detenerPolling();
  detenerTimer();
});
</script>

<template>
  <div class="space-y-6">
    <div
      class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between"
    >
      <div>
        <h1 class="text-3xl font-bold text-gray-900">
          Emisión masiva
        </h1>
        <p class="mt-2 max-w-3xl text-gray-600">
          Carga un Excel, revisa errores antes de emitir y sigue el resultado
          del lote sin perder contexto técnico.
        </p>
      </div>

      <div
        class="rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-600 shadow-sm"
      >
        <p class="font-semibold text-gray-900">
          Emisor activo
        </p>
        <p>
          {{
            empresaActiva?.razon_social ||
              "Selecciona una empresa para empezar."
          }}
        </p>
      </div>
    </div>

    <BaseAlert
      v-if="!empresaActivaId"
      type="warning"
    >
      Selecciona un emisor activo antes de descargar la plantilla o subir el
      archivo.
    </BaseAlert>

    <BaseCard>
      <div class="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <div class="flex items-center gap-2">
            <Cog6ToothIcon class="h-5 w-5 text-primary-600" />
            <h2 class="text-lg font-semibold text-gray-900">
              Perfil de carga masiva
            </h2>
          </div>
          <p class="mt-2 text-sm text-gray-600">
            Usa una configuración habitual del emisor activo. Todo lo aplicado
            queda visible y editable antes de validar.
          </p>
          <div class="mt-4 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
            <BaseSelect
              v-model="perfilSeleccionadoId"
              label="Perfil de carga masiva"
              :options="perfilesOptions"
              placeholder="Sin perfil de carga masiva"
              :disabled="loadingPerfiles || perfilesCargaMasiva.length === 0"
              @update:model-value="handlePerfilSeleccionado"
            />
            <router-link
              to="/empresa"
              class="inline-flex min-h-[42px] items-center justify-center rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              Administrar perfiles de carga masiva
            </router-link>
          </div>
        </div>

        <div
          class="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700"
        >
          <p class="font-medium text-gray-900">
            {{
              perfilAplicado
                ? `Perfil de carga masiva aplicado: ${perfilAplicado.nombre}`
                : "Sin perfil de carga masiva aplicado"
            }}
          </p>
          <p
            v-if="configuracionModificada"
            class="mt-1 text-amber-700"
          >
            Configuración modificada en esta carga. Se validará sin snapshot de
            perfil de carga masiva.
          </p>
          <p
            v-else
            class="mt-1 text-gray-500"
          >
            {{
              perfilesCargaMasiva.length
                ? "Puedes cambiarlo antes de validar."
                : "Configuralos desde Emisores."
            }}
          </p>
        </div>
      </div>
    </BaseCard>

    <BaseCard>
      <div class="grid gap-4 lg:grid-cols-3">
        <div class="rounded-xl border border-blue-100 bg-blue-50 p-4">
          <p class="text-sm font-semibold text-blue-900">
            1. Descarga la plantilla
          </p>
          <p class="mt-2 text-sm text-blue-800">
            Puedes usar el archivo oficial o la plantilla configurada por el
            perfil de carga masiva.
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
            <h2 class="text-lg font-semibold text-gray-900">
              Validar archivo
            </h2>
          </div>
          <p class="mt-2 text-sm text-gray-600">
            Sube la plantilla oficial o un archivo `.xlsx` externo y confirma
            la plantilla/formato antes de validar.
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
            >

            <div
              class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
            >
              <div>
                <p class="font-medium text-gray-900">
                  {{
                    archivoSeleccionado?.name ||
                      "Todavía no seleccionaste ningún archivo."
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
                <BaseButton
                  variant="secondary"
                  @click="triggerFileSelection"
                >
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
                  Plantilla/formato de importación
                </p>
                <p class="mt-1 text-sm text-gray-600">
                  {{
                    detectandoFormato
                      ? "Detectando columnas del Excel..."
                      : candidatoPrincipal
                        ? `Sugerencia: ${candidatoPrincipal.nombre} (${Math.round(candidatoPrincipal.score * 100)}%)`
                        : "Selecciona la plantilla/formato que corresponde al origen del archivo."
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
                label="Plantilla/formato"
                :options="formatosOptions"
                placeholder="Selecciona una plantilla"
                :disabled="detectandoFormato"
              />

              <div class="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                <p class="font-medium text-gray-900">
                  Columnas detectadas
                </p>
                <p class="mt-1 break-words">
                  {{
                    deteccionFormato?.headers_detectados.join(", ") ||
                      "Todavía no se analizaron encabezados."
                  }}
                </p>
              </div>
            </div>

            <BaseAlert
              v-if="requiereElegirFormato"
              type="warning"
              class="mt-4"
            >
              <div
                class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <span>
                  {{
                    hayConflictoFormatoPerfil
                      ? "El perfil de carga masiva trae una plantilla, pero el Excel coincide con otra de alta confianza. Confirma cuál corresponde antes de validar."
                      : deteccionFormato
                        ? "Confirma una plantilla/formato antes de validar. Si el mapeo no coincide, el sistema puede interpretar mal importes, receptor o punto de venta."
                        : "Todavía no se analizaron los encabezados del Excel. El análisis debería iniciar automáticamente; si no avanza, reinténtalo."
                  }}
                </span>
                <div class="flex flex-wrap gap-2">
                  <BaseButton
                    v-if="hayConflictoFormatoPerfil"
                    size="sm"
                    variant="secondary"
                    @click="usarFormatoSugerido"
                  >
                    Usar sugerido
                  </BaseButton>
                  <BaseButton
                    v-if="hayConflictoFormatoPerfil"
                    size="sm"
                    variant="secondary"
                    @click="usarFormatoDelPerfil"
                  >
                    Usar perfil
                  </BaseButton>
                  <BaseButton
                    v-if="!deteccionFormato"
                    size="sm"
                    variant="secondary"
                    :loading="detectandoFormato"
                    @click="
                      archivoSeleccionado &&
                        detectarFormatoArchivo(archivoSeleccionado)
                    "
                  >
                    Analizar encabezados
                  </BaseButton>
                </div>
              </div>
            </BaseAlert>
          </div>

          <div
            v-if="archivoSeleccionado"
            class="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4"
          >
            <div class="flex items-start gap-3">
              <InformationCircleIcon
                class="mt-0.5 h-5 w-5 flex-shrink-0 text-indigo-700"
              />
              <div>
                <p class="text-sm font-semibold text-indigo-950">
                  Punto de venta
                </p>
                <p class="mt-1 text-sm text-indigo-900">
                  Podés usar el punto de venta definido en el archivo o fijar
                  uno habilitado para FactuFlow en este emisor.
                </p>
              </div>
            </div>

            <div class="mt-4 grid gap-3 text-sm text-gray-800 lg:grid-cols-2">
              <label class="rounded-lg border border-indigo-100 bg-white p-3">
                <span class="flex items-center gap-2 font-medium">
                  <input
                    v-model="puntoVentaModo"
                    type="radio"
                    value="archivo"
                    class="h-4 w-4 text-primary-600"
                  >
                  Utilizar punto de venta definido en el archivo
                </span>
              </label>
              <label class="rounded-lg border border-indigo-100 bg-white p-3">
                <span class="flex items-center gap-2 font-medium">
                  <input
                    v-model="puntoVentaModo"
                    type="radio"
                    value="fijo"
                    class="h-4 w-4 text-primary-600"
                    :disabled="puntosVentaFactuflow.length === 0"
                  >
                  Utilizar punto de venta del emisor
                </span>
                <BaseSelect
                  v-model="puntoVentaNumero"
                  class="mt-3"
                  label="Punto de venta"
                  :options="puntoVentaOptions"
                  :disabled="
                    puntoVentaModo !== 'fijo' ||
                      puntosVentaFactuflow.length === 0
                  "
                />
              </label>
            </div>

            <BaseAlert
              v-if="puntosVentaFactuflow.length === 0"
              type="warning"
              class="mt-4"
            >
              Para elegir un punto de venta fijo, primero completá los puntos de
              venta habilitados del emisor en la pantalla Puntos de venta.
            </BaseAlert>
            <BaseAlert
              v-else-if="puntoVentaModo === 'fijo' && !puntoVentaNumero"
              type="warning"
              class="mt-4"
            >
              Seleccioná el punto de venta del emisor antes de validar.
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
                  Definí si el lote corresponde a productos, servicios o si el
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
                  >
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
                  >
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
                  >
                  Definido por el archivo
                </span>
                <span class="mt-2 block text-xs text-gray-600">
                  El Excel debe tener una columna con Producto o Servicio en
                  todas las filas.
                </span>
              </label>
            </div>

            <BaseAlert
              v-if="!conceptoModo"
              type="warning"
              class="mt-4"
            >
              Elegí el tipo de concepto fiscal ARCA antes de validar. Sin esta
              confirmación el lote no puede quedar listo para emitir.
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
                  >
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
                  >
                  Utilizar esta descripción para todo el lote
                </span>
                <input
                  v-model="descripcionItemFija"
                  type="text"
                  :disabled="descripcionItemModo !== 'fija'"
                  placeholder="Ej.: Honorarios profesionales"
                  class="mt-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                >
              </label>
            </div>

            <BaseAlert
              v-if="!descripcionItemCompleta"
              type="warning"
              class="mt-4"
            >
              Definí la descripción facturada antes de validar. No se usará una
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
                  La fecha de emisión no se completa automáticamente con la
                  fecha de hoy. Elegí qué fecha se usará antes de validar.
                </p>
              </div>
            </div>

            <div class="mt-4 grid gap-4 xl:grid-cols-2">
              <div class="rounded-lg border border-rose-100 bg-white p-4">
                <p class="text-sm font-semibold text-gray-900">
                  Fecha de emisión
                </p>
                <div class="mt-3 space-y-3 text-sm text-gray-700">
                  <label class="flex items-center gap-2">
                    <input
                      v-model="fechaEmisionModo"
                      type="radio"
                      value="archivo"
                      class="h-4 w-4 text-primary-600"
                    >
                    Utilizar la fecha del archivo
                  </label>
                  <label class="flex flex-wrap items-center gap-2">
                    <input
                      v-model="fechaEmisionModo"
                      type="radio"
                      value="fija"
                      class="h-4 w-4 text-primary-600"
                    >
                    Utilizar esta fecha para todos
                    <input
                      v-model="fechaEmisionFija"
                      type="date"
                      :disabled="fechaEmisionModo !== 'fija'"
                      class="rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                    >
                  </label>
                </div>
              </div>

              <div class="rounded-lg border border-rose-100 bg-white p-4">
                <p class="text-sm font-semibold text-gray-900">
                  Periodo y vencimiento de servicios
                </p>
                <div class="mt-3 space-y-4 text-sm text-gray-700">
                  <div>
                    <p class="font-medium text-gray-800">
                      Desde
                    </p>
                    <label class="mt-2 flex items-center gap-2">
                      <input
                        v-model="fechaServicioDesdeModo"
                        type="radio"
                        value="archivo"
                        class="h-4 w-4 text-primary-600"
                      >
                      Utilizar la fecha del archivo
                    </label>
                    <label class="mt-2 flex flex-wrap items-center gap-2">
                      <input
                        v-model="fechaServicioDesdeModo"
                        type="radio"
                        value="fija"
                        class="h-4 w-4 text-primary-600"
                      >
                      Fijar
                      <input
                        v-model="fechaServicioDesdeFija"
                        type="date"
                        :disabled="fechaServicioDesdeModo !== 'fija'"
                        class="rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                      >
                    </label>
                  </div>

                  <div>
                    <p class="font-medium text-gray-800">
                      Hasta
                    </p>
                    <label class="mt-2 flex items-center gap-2">
                      <input
                        v-model="fechaServicioHastaModo"
                        type="radio"
                        value="archivo"
                        class="h-4 w-4 text-primary-600"
                      >
                      Utilizar la fecha del archivo
                    </label>
                    <label class="mt-2 flex flex-wrap items-center gap-2">
                      <input
                        v-model="fechaServicioHastaModo"
                        type="radio"
                        value="fija"
                        class="h-4 w-4 text-primary-600"
                      >
                      Fijar
                      <input
                        v-model="fechaServicioHastaFija"
                        type="date"
                        :disabled="fechaServicioHastaModo !== 'fija'"
                        class="rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                      >
                    </label>
                  </div>

                  <div>
                    <p class="font-medium text-gray-800">
                      Vencimiento de pago
                    </p>
                    <label class="mt-2 flex items-center gap-2">
                      <input
                        v-model="fechaVtoPagoModo"
                        type="radio"
                        value="archivo"
                        class="h-4 w-4 text-primary-600"
                      >
                      Utilizar la fecha del archivo
                    </label>
                    <label class="mt-2 flex flex-wrap items-center gap-2">
                      <input
                        v-model="fechaVtoPagoModo"
                        type="radio"
                        value="fija"
                        class="h-4 w-4 text-primary-600"
                      >
                      Fijar
                      <input
                        v-model="fechaVtoPagoFija"
                        type="date"
                        :disabled="fechaVtoPagoModo !== 'fija'"
                        class="rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100"
                      >
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
              Completa la decisión de fechas antes de validar. Si una fecha del
              archivo queda fuera de la ventana ARCA, el lote quedara observado
              y deberas elegir una fecha permitida antes de emitir.
            </BaseAlert>
          </div>
        </div>

        <div class="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <div class="flex items-center gap-2">
            <ExclamationTriangleIcon class="h-5 w-5 text-amber-600" />
            <h3 class="font-semibold text-gray-900">
              Controles previos
            </h3>
          </div>
          <ul class="mt-3 space-y-2 text-sm text-gray-700">
            <li>Emisor activo correcto.</li>
            <li>Certificado vigente para el ambiente actual.</li>
            <li>Punto de venta habilitado FactuFlow.</li>
            <li>Fecha de emisión confirmada antes de validar.</li>
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
                  :disabled="!!loteActual.compactado_at"
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
                  Emitir comprobantes válidos
                </BaseButton>
              </div>
            </div>

            <BaseAlert
              v-if="mostrarAvisoFallbackArca"
              type="warning"
              class="mt-6"
            >
              ARCA no informó la capacidad máxima por request. FactuFlow emitió
              este lote en modo unitario para no bloquear la operación, por lo
              que el procesamiento pudo demorar más.
              <span v-if="motivoFallbackArca">
                Motivo técnico: {{ motivoFallbackArca }}
              </span>
            </BaseAlert>

            <BaseAlert
              v-if="loteActual.compactado_at"
              type="info"
              class="mt-6"
            >
              Este lote fue compactado el
              {{ formatDateTime(loteActual.compactado_at) }}. Se conserva el
              resumen fiscal y los comprobantes agrupados, pero ya no está
              disponible el detalle original por fila.
            </BaseAlert>

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

            <div
              v-if="
                totalPendientesResolucion > 0 ||
                  hayPendientesResolucionVisibles
              "
              class="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4"
            >
              <div
                class="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between"
              >
                <div>
                  <p class="text-sm font-semibold text-amber-950">
                    Resolver pendientes del lote
                  </p>
                  <p class="mt-1 text-sm text-amber-900">
                    Reintenta fallidos cuando quieras emitirlos desde
                    FactuFlow. Reconcilia solo comprobantes que ya verificaste
                    como autorizados en ARCA Web. Descarta únicamente los que no
                    deben emitirse desde este lote.
                  </p>
                </div>
                <p class="text-sm font-medium text-amber-900">
                  {{ totalPendientesResolucion }} pendientes contabilizados
                </p>
              </div>

              <div class="mt-4 grid gap-4 xl:grid-cols-3">
                <div class="rounded-lg border border-amber-100 bg-white p-4">
                  <p class="text-sm font-semibold text-gray-900">
                    Reintentar fallidos
                  </p>
                  <p class="mt-1 text-sm text-gray-600">
                    Solicita CAE nuevamente para los comprobantes fallidos del
                    lote, con la misma confirmación de fecha fiscal.
                  </p>
                  <BaseButton
                    class="mt-4 w-full"
                    size="sm"
                    :loading="resolviendoLote === 'reintentar'"
                    :disabled="
                      !hayFallidosParaReintentar || resolviendoLote !== null
                    "
                    @click="solicitarConfirmacionReintentoFallidos"
                  >
                    <ArrowPathIcon class="mr-2 h-4 w-4" />
                    Reintentar fallidos
                  </BaseButton>
                </div>

                <div class="rounded-lg border border-amber-100 bg-white p-4">
                  <p class="text-sm font-semibold text-gray-900">
                    Descartar visibles
                  </p>
                  <p class="mt-1 text-sm text-gray-600">
                    Cierra los comprobantes pendientes visibles sin emitirlos.
                    No se usa para comprobantes inciertos.
                  </p>
                  <textarea
                    v-model="motivoDescartar"
                    rows="3"
                    class="mt-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder="Motivo operativo"
                  />
                  <BaseButton
                    class="mt-3 w-full"
                    size="sm"
                    variant="secondary"
                    :loading="resolviendoLote === 'descartar'"
                    :disabled="
                      !puedeDescartarVisibles || resolviendoLote !== null
                    "
                    @click="descartarGruposVisibles"
                  >
                    <ExclamationTriangleIcon class="mr-2 h-4 w-4" />
                    Descartar visibles
                  </BaseButton>
                </div>

                <div class="rounded-lg border border-amber-100 bg-white p-4">
                  <p class="text-sm font-semibold text-gray-900">
                    Reconciliar ARCA Web
                  </p>
                  <p class="mt-1 text-sm text-gray-600">
                    Vincula un comprobante emitido manualmente si ARCA confirma
                    tipo, punto de venta, número, fecha, total y CAE.
                  </p>
                  <div class="mt-3 space-y-3">
                    <BaseSelect
                      v-model="externoGrupoId"
                      label="Comprobante visible"
                      :options="grupoExternoOptions"
                      :disabled="resolviendoLote !== null"
                    />
                    <BaseInput
                      v-model="externoNumero"
                      type="number"
                      min="1"
                      label="Número autorizado"
                      placeholder="Ej. 1234"
                      :disabled="resolviendoLote !== null"
                    />
                    <BaseInput
                      v-model="externoCae"
                      label="CAE informado"
                      placeholder="Opcional"
                      :disabled="resolviendoLote !== null"
                    />
                    <textarea
                      v-model="externoMotivo"
                      rows="3"
                      class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
                      placeholder="Motivo operativo"
                      :disabled="resolviendoLote !== null"
                    />
                  </div>
                  <BaseButton
                    class="mt-3 w-full"
                    size="sm"
                    :loading="resolviendoLote === 'reconciliar'"
                    :disabled="
                      !puedeReconciliarExterno || resolviendoLote !== null
                    "
                    @click="reconciliarExterno"
                  >
                    <CheckCircleIcon class="mr-2 h-4 w-4" />
                    Reconciliar comprobante
                  </BaseButton>
                </div>
              </div>
            </div>

            <div
              v-if="puedeCompactarLote || puedeEliminarLote"
              class="mt-6 rounded-xl border border-gray-200 bg-gray-50 p-4"
            >
              <p class="text-sm font-semibold text-gray-900">
                Limpieza de almacenamiento
              </p>
              <p class="mt-1 text-sm text-gray-600">
                Estas acciones reducen espacio local sin emitir comprobantes.
                Compactar conserva el lote cerrado; eliminar solo aplica cuando
                no existe emisión ni incertidumbre fiscal.
              </p>
              <div class="mt-4 grid gap-4 lg:grid-cols-2">
                <div
                  v-if="puedeCompactarLote"
                  class="rounded-lg border border-gray-200 bg-white p-4"
                >
                  <p class="text-sm font-medium text-gray-900">
                    Compactar lote cerrado
                  </p>
                  <p class="mt-2 text-sm text-gray-600">
                    Elimina el detalle por fila del Excel para ahorrar espacio.
                    El popup siguiente muestra las consecuencias antes de
                    confirmar.
                  </p>
                  <BaseButton
                    class="mt-3 w-full"
                    size="sm"
                    variant="secondary"
                    :loading="resolviendoLote === 'compactar'"
                    :disabled="resolviendoLote !== null"
                    @click="mostrarConfirmacionCompactar = true"
                  >
                    <ArchiveBoxIcon class="mr-2 h-4 w-4" />
                    Compactar detalle
                  </BaseButton>
                </div>

                <div
                  v-if="puedeEliminarLote"
                  class="rounded-lg border border-red-100 bg-white p-4"
                >
                  <p class="text-sm font-medium text-gray-900">
                    Eliminar lote sin emisión
                  </p>
                  <textarea
                    v-model="motivoEliminar"
                    rows="3"
                    class="mt-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder="Motivo de eliminación"
                  />
                  <BaseButton
                    class="mt-3 w-full"
                    size="sm"
                    variant="danger"
                    :loading="resolviendoLote === 'eliminar'"
                    :disabled="
                      motivoEliminar.trim().length < 3 ||
                        resolviendoLote !== null
                    "
                    @click="eliminarLote"
                  >
                    <TrashIcon class="mr-2 h-4 w-4" />
                    Eliminar lote
                  </BaseButton>
                </div>
              </div>
            </div>

            <div
              class="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4"
            >
              <div
                class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <p class="text-sm font-semibold text-emerald-950">
                    Totales listos para emitir
                  </p>
                  <p class="mt-1 text-sm text-emerald-900">
                    Revisá estos importes contra el Excel antes de solicitar
                    CAE.
                  </p>
                </div>
                <p class="text-sm font-medium text-emerald-900">
                  {{ totalesListosParaEmitir.comprobantes }} comprobantes
                </p>
              </div>

              <div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div class="rounded-lg border border-emerald-100 bg-white p-3">
                  <p class="text-xs font-medium uppercase text-gray-500">
                    Neto
                  </p>
                  <p class="mt-1 text-lg font-semibold text-gray-900">
                    {{ formatMoney(totalesListosParaEmitir.neto) }}
                  </p>
                </div>
                <div class="rounded-lg border border-emerald-100 bg-white p-3">
                  <p class="text-xs font-medium uppercase text-gray-500">
                    IVA 21%
                  </p>
                  <p class="mt-1 text-lg font-semibold text-gray-900">
                    {{ formatMoney(totalesListosParaEmitir.iva21) }}
                  </p>
                </div>
                <div class="rounded-lg border border-emerald-100 bg-white p-3">
                  <p class="text-xs font-medium uppercase text-gray-500">
                    IVA 10,5%
                  </p>
                  <p class="mt-1 text-lg font-semibold text-gray-900">
                    {{ formatMoney(totalesListosParaEmitir.iva105) }}
                  </p>
                </div>
                <div class="rounded-lg border border-emerald-100 bg-white p-3">
                  <p class="text-xs font-medium uppercase text-gray-500">
                    Total
                  </p>
                  <p class="mt-1 text-lg font-semibold text-gray-900">
                    {{ formatMoney(totalesListosParaEmitir.total) }}
                  </p>
                </div>
              </div>
              <BaseAlert
                v-if="totalesListosParaEmitir.valoresInvalidos > 0"
                type="warning"
                class="mt-4"
              >
                Hay importes con un formato ambiguo en
                {{ totalesListosParaEmitir.valoresInvalidos }} fila(s)
                validada(s). Revisa el Excel y vuelve a validar antes de emitir.
              </BaseAlert>
            </div>

            <div class="mt-6 rounded-xl border border-gray-200 bg-gray-50 p-4">
              <div
                class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <p class="text-sm font-medium text-gray-900">
                    Avance del lote
                  </p>
                  <p class="mt-1 text-sm text-gray-600">
                    {{ resumenAvanceLote }}
                  </p>
                </div>
                <p class="text-sm font-semibold text-primary-700">
                  {{ porcentajeProcesado }}% procesado
                </p>
              </div>
              <div
                class="mt-3 h-3 overflow-hidden rounded-full bg-gray-200"
                :class="{ relative: mostrarBarraIndeterminada }"
              >
                <div
                  v-if="mostrarBarraIndeterminada"
                  class="progress-indeterminate h-full rounded-full bg-primary-500/80"
                />
                <div
                  v-else
                  class="h-full rounded-full bg-primary-600 transition-all duration-500 ease-out"
                  :style="{ width: `${porcentajeProcesado}%` }"
                />
              </div>
              <div
                class="mt-3 grid gap-2 text-sm text-gray-600 md:grid-cols-[1fr_auto_auto]"
              >
                <p>{{ detalleAvanceLote }}</p>
                <p>
                  <span class="font-medium text-gray-700">Transcurrido:</span>
                  {{ progresoLote?.transcurridoTexto || "00:00" }}
                </p>
                <p>
                  <span class="font-medium text-gray-700">
                    Estimado restante:
                  </span>
                  {{ tiempoRestanteTexto }}
                </p>
              </div>
              <p
                v-if="loteActual.mensaje_resumen"
                class="mt-2 text-xs text-gray-500"
              >
                {{ loteActual.mensaje_resumen }}
              </p>
            </div>

            <BaseAlert
              v-if="necesitaCorreccion"
              type="warning"
              class="mt-6"
            >
              Hay comprobantes observados. Descarga el archivo observado para
              ver fila por fila que debes corregir antes de volver a subir el
              Excel.
            </BaseAlert>

            <div
              class="mt-6 flex flex-col gap-3 border-t border-gray-200 pt-6 lg:flex-row lg:items-end lg:justify-between"
            >
              <div>
                <p class="text-sm font-semibold text-gray-900">
                  Detalle de comprobantes
                </p>
                <p class="mt-1 text-sm text-gray-600">
                  {{ resumenPaginacionGrupos }} El resumen fiscal considera el
                  lote completo.
                </p>
              </div>
              <BaseSelect
                v-model="grupoEstadoFiltro"
                class="w-full lg:max-w-xs"
                label="Filtrar por estado"
                :options="estadosGruposOptions"
                @update:model-value="cambiarFiltroGrupos"
              />
            </div>

            <div
              v-if="loadingGruposLote"
              class="mt-6 flex justify-center py-10"
            >
              <BaseSpinner />
            </div>

            <div
              v-else-if="gruposLote.length > 0"
              class="mt-6 overflow-x-auto"
            >
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
                    v-for="grupo in gruposLote"
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
                      <p>Emisión {{ formatDate(grupo.fecha_emision) }}</p>
                      <p
                        v-if="
                          grupo.fecha_servicio_desde ||
                            grupo.fecha_servicio_hasta
                        "
                        class="text-xs text-gray-500"
                      >
                        Servicio {{ formatDate(grupo.fecha_servicio_desde) }} -
                        {{ formatDate(grupo.fecha_servicio_hasta) }}
                      </p>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-700">
                      {{ descripcionFacturada(grupo) }}
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
                        {{ ESTADOS_GRUPO_NOMBRES[grupo.estado] || grupo.estado }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-600">
                      {{ grupo.mensajes_json[0] || "Sin observaciones" }}
                    </td>
                  </tr>
                </tbody>
              </table>
              <Pagination
                v-if="gruposLoteTotalPages > 1"
                :current-page="gruposLotePage"
                :total-pages="gruposLoteTotalPages"
                :per-page="gruposLotePerPage"
                :total="gruposLoteTotal"
                @update:current-page="cambiarPaginaGrupos"
              />
            </div>

            <div
              v-else
              class="mt-6"
            >
              <BaseEmpty
                title="Sin comprobantes para mostrar"
                message="Cambia el filtro de estado para revisar otros comprobantes del lote."
                :icon="DocumentDuplicateIcon"
              />
            </div>
          </BaseCard>
        </template>

        <BaseCard v-else>
          <BaseEmpty
            title="Todavía no hay un lote seleccionado"
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

        <div
          v-else-if="lotes.length > 0"
          class="space-y-3"
        >
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
              <p>Válidos: {{ lote.grupos_validos }}</p>
              <p>Errores: {{ lote.grupos_con_error }}</p>
              <p>Emitidos: {{ lote.grupos_emitidos }}</p>
              <p>Fallidos: {{ lote.grupos_fallidos }}</p>
              <p>Externos: {{ lote.grupos_reconciliados_externos }}</p>
              <p>Descartados: {{ lote.grupos_descartados }}</p>
            </div>
          </button>
        </div>

        <BaseEmpty v-else>
          <DocumentDuplicateIcon class="mx-auto mb-4 h-12 w-12 text-gray-400" />
          <p class="text-gray-600">
            Todavía no se cargaron lotes para esta empresa.
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
    <ConfirmDialog
      :show="mostrarConfirmacionReintentoFallidos"
      title="Confirmar reintento"
      :message="mensajeConfirmacionReintentoFallidos"
      confirm-text="Reintentar fallidos"
      cancel-text="Volver a revisar"
      variant="danger"
      @confirm="reintentarFallidos"
      @cancel="mostrarConfirmacionReintentoFallidos = false"
    />
    <ConfirmDialog
      :show="mostrarConfirmacionDuplicadoLogico"
      title="Duplicados probables"
      :message="mensajeConfirmacionDuplicadoLogico"
      confirm-text="Emitir igualmente"
      cancel-text="Volver a revisar"
      variant="danger"
      @confirm="confirmarDuplicadoLogicoLote"
      @cancel="resetearConfirmacionDuplicadoPendiente"
    />
    <ConfirmDialog
      :show="mostrarConfirmacionCompactar"
      title="Compactar lote"
      :message="mensajeConfirmacionCompactar"
      confirm-text="Compactar"
      cancel-text="Cancelar"
      variant="danger"
      @confirm="compactarLote"
      @cancel="mostrarConfirmacionCompactar = false"
    />
  </div>
</template>

<style scoped>
.progress-indeterminate {
  animation: lote-progress-indeterminate 1.2s ease-in-out infinite;
  transform: translateX(-100%);
  width: 40%;
}

@keyframes lote-progress-indeterminate {
  0% {
    transform: translateX(-100%);
  }

  100% {
    transform: translateX(250%);
  }
}
</style>
