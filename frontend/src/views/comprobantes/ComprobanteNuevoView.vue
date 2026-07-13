<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import { useNotification } from "@/composables/useNotification";
import { useEmpresaStore } from "@/stores/empresa";
import { useComprobantesStore } from "@/stores/comprobantes";
import { usePuntosVentaStore } from "@/stores/puntos_venta";
import {
  ArrowPathIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  PaperAirplaneIcon,
} from "@heroicons/vue/24/outline";
import BaseCard from "@/components/ui/BaseCard.vue";
import ConfirmDialog from "@/components/common/ConfirmDialog.vue";
import ClienteSelector from "@/components/comprobantes/ClienteSelector.vue";
import ItemsTable from "@/components/comprobantes/ItemsTable.vue";
import TotalesPanel from "@/components/comprobantes/TotalesPanel.vue";
import ComprobantePreview from "@/components/comprobantes/ComprobantePreview.vue";
import type {
  ItemComprobante,
  EmitirComprobanteRequest,
  EmitirComprobanteResponse,
} from "@/types/comprobante";
import {
  TIPOS_COMPROBANTE,
  TIPOS_COMPROBANTE_NOMBRES,
  TIPOS_CONCEPTO,
  TIPOS_CONCEPTO_NOMBRES,
  TIPOS_DOCUMENTO,
} from "@/types/comprobante";

interface OperacionInciertaEmision {
  readonly idempotencyKey: string;
  readonly empresaId: number;
  readonly empresaNombre: string;
  readonly request: EmitirComprobanteRequest;
  readonly respuesta: EmitirComprobanteResponse;
  readonly puntoVentaNumero: number;
  readonly numeroPlanificado: number | null;
  readonly totalPlanificado: number;
}

const router = useRouter();
const empresaStore = useEmpresaStore();
const comprobantesStore = useComprobantesStore();
const puntosVentaStore = usePuntosVentaStore();
const { showError, showSuccess, showWarning } = useNotification();

// Estado del formulario
const formData = ref({
  tipo_comprobante: TIPOS_COMPROBANTE.FACTURA_B,
  punto_venta_id: 0,
  concepto: "" as number | "",
  fecha_emision: "",

  // Cliente
  cliente: {
    cliente_id: undefined as number | undefined,
    tipo_documento: 80,
    numero_documento: "",
    razon_social: "",
    condicion_iva: "",
    domicilio: "",
  },

  // Items
  items: [] as ItemComprobante[],

  // Servicios
  fecha_servicio_desde: "",
  fecha_servicio_hasta: "",
  fecha_vto_pago: "",

  // Observaciones
  observaciones: "",
});

// Estados
const loading = ref(false);
const mostrarPreview = ref(false);
const mostrarCancelacion = ref(false);
const mostrarConfirmacionFechaFiscal = ref(false);
const mostrarConfirmacionDuplicadoLogico = ref(false);
const mensajeConfirmacionDuplicadoLogico = ref("");
const idempotencyKeyEmision = ref<string | null>(null);
const operacionIncierta = ref<OperacionInciertaEmision | null>(null);
const confirmacionDuplicadoLogico = ref(false);
const proximoNumero = ref<number | null>(null);
const consultandoProximoNumero = ref(false);
const errorProximoNumero = ref("");
let proximoNumeroRequestId = 0;
const puntosVenta = computed(() => puntosVentaStore.puntosVenta);
const puntosVentaUsables = computed(() =>
  puntosVenta.value.filter((puntoVenta) => puntoVenta.usable_factuflow),
);
const empresaId = computed(() => empresaStore.empresaActivaId || 0);
const empresaActiva = computed(() => empresaStore.empresaActiva);
const tiposComprobanteA = new Set<number>([
  TIPOS_COMPROBANTE.FACTURA_A,
  TIPOS_COMPROBANTE.NOTA_DEBITO_A,
  TIPOS_COMPROBANTE.NOTA_CREDITO_A,
]);
const tiposComprobanteC = new Set<number>([TIPOS_COMPROBANTE.FACTURA_C]);

const requiereClienteCuit = computed(() =>
  tiposComprobanteA.has(formData.value.tipo_comprobante),
);
const esComprobanteC = computed(() =>
  tiposComprobanteC.has(formData.value.tipo_comprobante),
);

const limpiarClienteSeleccionado = () => {
  formData.value.cliente = {
    cliente_id: undefined,
    tipo_documento: 80,
    numero_documento: "",
    razon_social: "",
    condicion_iva: "",
    domicilio: "",
  };
};

const normalizarOrdenItems = (items: ItemComprobante[]): ItemComprobante[] =>
  items.map((item, index) => ({ ...item, orden: index }));

const crearIdempotencyKey = (): string => {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `ff-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const obtenerIdempotencyKeyEmision = (): string => {
  if (!idempotencyKeyEmision.value) {
    idempotencyKeyEmision.value = crearIdempotencyKey();
  }
  return idempotencyKeyEmision.value;
};

const esRegistroDesconocido = (
  value: unknown,
): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const obtenerDetalleError = (error: unknown): unknown => {
  if (!esRegistroDesconocido(error)) return null;
  const response = error.response;
  if (!esRegistroDesconocido(response)) return null;
  const data = response.data;
  if (!esRegistroDesconocido(data)) return null;
  return data.detail;
};

const obtenerStatusHttpError = (error: unknown): number | null => {
  if (!esRegistroDesconocido(error)) return null;
  const response = error.response;
  if (!esRegistroDesconocido(response)) return null;
  return typeof response.status === "number" &&
    Number.isInteger(response.status)
    ? response.status
    : null;
};

const obtenerMensajeRechazoFinal = (detail: unknown): string | null => {
  if (
    !esRegistroDesconocido(detail) ||
    typeof detail.mensaje !== "string" ||
    !Array.isArray(detail.errores)
  ) {
    return null;
  }

  const errores = detail.errores.filter(
    (item): item is string => typeof item === "string",
  );
  return [detail.mensaje, ...errores].filter(Boolean).join(" | ");
};

const crearSnapshotInmutable = (
  request: EmitirComprobanteRequest,
): EmitirComprobanteRequest => {
  const items = request.items.map((item) => Object.freeze({ ...item }));
  return Object.freeze({
    ...request,
    items: Object.freeze(items),
  }) as unknown as EmitirComprobanteRequest;
};

const resetearIdempotencyKeyEmision = (forzar = false) => {
  if (operacionIncierta.value && !forzar) return;

  idempotencyKeyEmision.value = null;
  confirmacionDuplicadoLogico.value = false;
  mostrarConfirmacionDuplicadoLogico.value = false;
  mensajeConfirmacionDuplicadoLogico.value = "";
};

const finalizarOperacionIncierta = () => {
  operacionIncierta.value = null;
  resetearIdempotencyKeyEmision(true);
};

const normalizarRespuestaReconciliacion = (
  detail: unknown,
  request: EmitirComprobanteRequest,
  puntoVentaNumero: number,
  numeroPlanificado: number | null,
  totalPlanificado: number,
): EmitirComprobanteResponse | null => {
  if (
    !esRegistroDesconocido(detail) ||
    detail.requiere_reconciliacion !== true
  ) {
    return null;
  }

  const numeroSeguro = (value: unknown, fallback: number): number =>
    typeof value === "number" && Number.isFinite(value) && value >= 0
      ? value
      : fallback;
  const cae =
    typeof detail.cae === "string" && /^\d{14}$/.test(detail.cae)
      ? detail.cae
      : undefined;
  const caeVencimiento =
    cae && typeof detail.cae_vencimiento === "string"
      ? detail.cae_vencimiento
      : undefined;
  const categoriaError =
    detail.categoria_error === "post_arca_persistencia" ||
    detail.categoria_error === "arca_respuesta_incierta"
      ? detail.categoria_error
      : "arca_respuesta_incierta";
  const comprobanteId =
    typeof detail.comprobante_id === "number" &&
    Number.isInteger(detail.comprobante_id) &&
    detail.comprobante_id > 0
      ? detail.comprobante_id
      : undefined;

  return {
    exito: false,
    comprobante_id: comprobanteId,
    tipo_comprobante: numeroSeguro(
      detail.tipo_comprobante,
      request.tipo_comprobante,
    ),
    punto_venta: numeroSeguro(detail.punto_venta, puntoVentaNumero),
    numero: numeroSeguro(detail.numero, numeroPlanificado ?? 0),
    fecha:
      typeof detail.fecha === "string" && detail.fecha.length > 0
        ? detail.fecha
        : request.fecha_emision,
    cae,
    cae_vencimiento: caeVencimiento,
    total: numeroSeguro(detail.total, totalPlanificado),
    mensaje:
      "FactuFlow no puede confirmar todavía el resultado fiscal de esta operación.",
    errores: [
      "No cambies los datos ni generes otra operación. Verificá el estado con esta misma clave.",
    ],
    requiere_reconciliacion: true,
    categoria_error: categoriaError,
  };
};

const registrarOperacionIncierta = (
  request: EmitirComprobanteRequest,
  idempotencyKey: string,
  respuesta: EmitirComprobanteResponse,
) => {
  const operacionPrevia = operacionIncierta.value;
  const puntoVentaNumero =
    operacionPrevia?.puntoVentaNumero ??
    puntoVentaSeleccionado.value?.numero ??
    respuesta.punto_venta;
  const numeroPlanificado =
    operacionPrevia?.numeroPlanificado ??
    (respuesta.numero > 0 ? respuesta.numero : proximoNumero.value);
  const totalPlanificado =
    operacionPrevia?.totalPlanificado ??
    (respuesta.total > 0 ? respuesta.total : totales.value.total);

  operacionIncierta.value = Object.freeze({
    idempotencyKey: operacionPrevia?.idempotencyKey ?? idempotencyKey,
    empresaId: operacionPrevia?.empresaId ?? request.empresa_id,
    empresaNombre:
      operacionPrevia?.empresaNombre ??
      empresaActiva.value?.razon_social ??
      `Emisor ${request.empresa_id}`,
    request: operacionPrevia?.request ?? crearSnapshotInmutable(request),
    respuesta: Object.freeze({
      ...respuesta,
      errores: Object.freeze([...respuesta.errores]),
    }) as unknown as EmitirComprobanteResponse,
    puntoVentaNumero,
    numeroPlanificado,
    totalPlanificado,
  });

  mostrarPreview.value = false;
  mostrarCancelacion.value = false;
  mostrarConfirmacionFechaFiscal.value = false;
  mostrarConfirmacionDuplicadoLogico.value = false;
};

const normalizarClienteParaTipoComprobante = () => {
  if (
    requiereClienteCuit.value &&
    formData.value.cliente.tipo_documento !== TIPOS_DOCUMENTO.CUIT
  ) {
    limpiarClienteSeleccionado();
  }
};

const cargarDatosEmisorActivo = async () => {
  try {
    await puntosVentaStore.fetchPuntosVenta();
  } catch (error) {
    console.error("Error al cargar puntos de venta:", error);
  }

  formData.value.punto_venta_id = puntosVentaUsables.value[0]?.id || 0;
  proximoNumero.value = null;
  await actualizarProximoNumero();
};

// Inicializar datos
onMounted(async () => {
  if (!empresaStore.empresaActivaId) {
    await empresaStore.inicializarEmpresaActiva();
  }

  await cargarDatosEmisorActivo();

  // Agregar primer item vacío
  if (formData.value.items.length === 0) {
    formData.value.items.push({
      codigo: "",
      descripcion: "",
      cantidad: 1,
      unidad: "unidades",
      precio_unitario: 0,
      descuento_porcentaje: 0,
      iva_porcentaje: 21,
      orden: 0,
    });
  }
});

watch(
  () => empresaStore.empresaActivaId,
  async (empresaIdActual, empresaIdAnterior) => {
    if (!empresaIdActual || empresaIdActual === empresaIdAnterior) return;

    if (operacionIncierta.value) {
      mostrarPreview.value = false;
      mostrarCancelacion.value = false;
      mostrarConfirmacionFechaFiscal.value = false;
      mostrarConfirmacionDuplicadoLogico.value = false;
      return;
    }

    resetearIdempotencyKeyEmision();
    limpiarClienteSeleccionado();
    await cargarDatosEmisorActivo();
  },
);

watch(formData, () => resetearIdempotencyKeyEmision(), { deep: true });

const manejarBeforeUnload = (event: BeforeUnloadEvent) => {
  if (!operacionIncierta.value) return;
  event.preventDefault();
  event.returnValue = "";
};

onMounted(() => {
  window.addEventListener("beforeunload", manejarBeforeUnload);
});

onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", manejarBeforeUnload);
});

onBeforeRouteLeave(() => {
  if (!operacionIncierta.value) return true;

  showWarning(
    "Verificación fiscal pendiente",
    "No salgas de esta pantalla hasta verificar el resultado con la misma operación.",
  );
  return false;
});

const tiposComprobanteDisponibles = computed(() => {
  // TODO: Filtrar según configuración de empresa
  return [
    { value: TIPOS_COMPROBANTE.FACTURA_A, label: TIPOS_COMPROBANTE_NOMBRES[1] },
    { value: TIPOS_COMPROBANTE.FACTURA_B, label: TIPOS_COMPROBANTE_NOMBRES[6] },
    {
      value: TIPOS_COMPROBANTE.FACTURA_C,
      label: TIPOS_COMPROBANTE_NOMBRES[11],
    },
  ];
});

const normalizarIvaComprobanteC = () => {
  if (!esComprobanteC.value) return;
  formData.value.items = formData.value.items.map((item) => ({
    ...item,
    iva_porcentaje: 0,
  }));
};

watch(
  () => formData.value.tipo_comprobante,
  async () => {
    normalizarClienteParaTipoComprobante();
    normalizarIvaComprobanteC();
    await actualizarProximoNumero();
  },
);

const mostrarFechasServicios = computed(() => {
  return (
    formData.value.concepto === TIPOS_CONCEPTO.SERVICIOS ||
    formData.value.concepto === TIPOS_CONCEPTO.PRODUCTOS_Y_SERVICIOS
  );
});

watch(mostrarFechasServicios, (requiereFechas) => {
  if (requiereFechas) return;

  formData.value.fecha_servicio_desde = "";
  formData.value.fecha_servicio_hasta = "";
  formData.value.fecha_vto_pago = "";
});

const totales = computed(() => {
  let subtotal = 0;
  let iva21 = 0;
  let iva105 = 0;
  let iva27 = 0;

  formData.value.items.forEach((item) => {
    const itemSubtotal =
      item.cantidad *
      item.precio_unitario *
      (1 - item.descuento_porcentaje / 100);
    subtotal += itemSubtotal;

    if (item.iva_porcentaje === 21) {
      iva21 += itemSubtotal * 0.21;
    } else if (item.iva_porcentaje === 10.5) {
      iva105 += itemSubtotal * 0.105;
    } else if (item.iva_porcentaje === 27) {
      iva27 += itemSubtotal * 0.27;
    }
  });

  const total = subtotal + iva21 + iva105 + iva27;

  return {
    subtotal,
    iva21,
    iva105,
    iva27,
    total,
  };
});

const formularioValido = computed(() => {
  return (
    proximoNumero.value !== null &&
    !consultandoProximoNumero.value &&
    formData.value.punto_venta_id > 0 &&
    formData.value.concepto !== "" &&
    formData.value.fecha_emision.length > 0 &&
    formData.value.cliente.numero_documento.length > 0 &&
    formData.value.cliente.razon_social.length > 0 &&
    formData.value.cliente.condicion_iva.length > 0 &&
    (!requiereClienteCuit.value ||
      formData.value.cliente.tipo_documento === TIPOS_DOCUMENTO.CUIT) &&
    formData.value.items.length > 0 &&
    formData.value.items.every(
      (item) =>
        item.descripcion.length > 0 &&
        item.cantidad > 0 &&
        item.precio_unitario >= 0 &&
        (!esComprobanteC.value || item.iva_porcentaje === 0),
    ) &&
    (!mostrarFechasServicios.value ||
      (formData.value.fecha_servicio_desde &&
        formData.value.fecha_servicio_hasta &&
        formData.value.fecha_vto_pago))
  );
});

const fechaEmisionLegible = computed(() => {
  if (!formData.value.fecha_emision) return "sin definir";
  const [year, month, day] = formData.value.fecha_emision.split("-");
  return `${day}/${month}/${year}`;
});

const puntoVentaSeleccionado = computed(() => {
  return puntosVenta.value.find(
    (pv) => pv.id === formData.value.punto_venta_id,
  );
});

const formularioBloqueado = computed(() => operacionIncierta.value !== null);
const emisorOperacionCoincide = computed(
  () =>
    operacionIncierta.value !== null &&
    operacionIncierta.value.empresaId === empresaId.value,
);
const respuestaOperacionIncierta = computed(
  () => operacionIncierta.value?.respuesta ?? null,
);
const fechaOperacionIncierta = computed(() => {
  const fecha =
    respuestaOperacionIncierta.value?.fecha ??
    operacionIncierta.value?.request.fecha_emision ??
    "";
  const coincidencia = /^(\d{4})-(\d{2})-(\d{2})/.exec(fecha);
  return coincidencia
    ? `${coincidencia[3]}/${coincidencia[2]}/${coincidencia[1]}`
    : fecha || "No disponible";
});
const tipoOperacionIncierta = computed(() => {
  const tipo =
    respuestaOperacionIncierta.value?.tipo_comprobante ??
    operacionIncierta.value?.request.tipo_comprobante;
  return tipo
    ? TIPOS_COMPROBANTE_NOMBRES[tipo] || `Tipo ${tipo}`
    : "No disponible";
});
const puntoVentaOperacionIncierta = computed(
  () =>
    respuestaOperacionIncierta.value?.punto_venta ||
    operacionIncierta.value?.puntoVentaNumero ||
    0,
);
const numeroOperacionIncierta = computed(
  () =>
    respuestaOperacionIncierta.value?.numero ||
    operacionIncierta.value?.numeroPlanificado ||
    0,
);
const totalOperacionIncierta = computed(
  () =>
    respuestaOperacionIncierta.value?.total ||
    operacionIncierta.value?.totalPlanificado ||
    0,
);

const mensajeConfirmacionFechaFiscal = computed(() => {
  const puntoVenta = puntoVentaSeleccionado.value?.numero
    ? ` para el punto de venta ${String(puntoVentaSeleccionado.value.numero).padStart(4, "0")}`
    : "";
  return `Está seguro que quiere emitir comprobantes con fecha ${fechaEmisionLegible.value}${puntoVenta}? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.`;
});

// Methods
const actualizarProximoNumero = async () => {
  const requestId = ++proximoNumeroRequestId;
  const puntoVentaId = formData.value.punto_venta_id;
  const tipoComprobante = formData.value.tipo_comprobante;
  proximoNumero.value = null;
  consultandoProximoNumero.value = false;
  errorProximoNumero.value = "";

  if (!puntoVentaId || !empresaId.value) return;

  consultandoProximoNumero.value = true;

  try {
    const puntoVenta = puntosVenta.value.find((pv) => pv.id === puntoVentaId);
    if (!puntoVenta?.usable_factuflow) {
      errorProximoNumero.value =
        "El punto de venta seleccionado no está disponible para emitir.";
      return;
    }

    const numero = await comprobantesStore.obtenerProximoNumero(
      puntoVenta.numero,
      tipoComprobante,
    );
    if (
      requestId === proximoNumeroRequestId &&
      formData.value.punto_venta_id === puntoVentaId &&
      formData.value.tipo_comprobante === tipoComprobante
    ) {
      proximoNumero.value = numero;
    }
  } catch (error) {
    if (requestId === proximoNumeroRequestId) {
      errorProximoNumero.value =
        "No se pudo confirmar la numeración fiscal con ARCA.";
      console.error("Error al obtener próximo número:", error);
    }
  } finally {
    if (requestId === proximoNumeroRequestId) {
      consultandoProximoNumero.value = false;
    }
  }
};

const abrirVistaPrevia = () => {
  if (consultandoProximoNumero.value) {
    showWarning(
      "Numeración en proceso",
      "Espera a que FactuFlow confirme el próximo número antes de continuar.",
    );
    return;
  }

  if (proximoNumero.value === null) {
    showWarning(
      "Numeración no disponible",
      errorProximoNumero.value ||
        "No se pudo confirmar el próximo número. Revisa el punto de venta e inténtalo nuevamente.",
    );
    return;
  }

  if (!formularioValido.value) {
    showWarning(
      "Faltan datos para continuar",
      "Revisa cliente, punto de venta, items y fechas obligatorias antes de abrir la vista previa.",
    );
    return;
  }

  mostrarPreview.value = true;
};

const solicitarConfirmacionFechaFiscal = () => {
  mostrarConfirmacionFechaFiscal.value = true;
};

const construirRequestEmision = (): EmitirComprobanteRequest => ({
  empresa_id: empresaId.value,
  punto_venta_id: formData.value.punto_venta_id,
  tipo_comprobante: formData.value.tipo_comprobante,
  concepto: Number(formData.value.concepto),
  fecha_emision: formData.value.fecha_emision,
  confirmacion_fecha_fiscal: true,
  confirmacion_duplicado_logico: confirmacionDuplicadoLogico.value,
  cliente_id: formData.value.cliente.cliente_id,
  tipo_documento: formData.value.cliente.tipo_documento,
  numero_documento: formData.value.cliente.numero_documento,
  razon_social: formData.value.cliente.razon_social,
  condicion_iva: formData.value.cliente.condicion_iva,
  domicilio: formData.value.cliente.domicilio,
  guardar_cliente: true,
  items: normalizarOrdenItems(formData.value.items),
  fecha_servicio_desde: formData.value.fecha_servicio_desde || undefined,
  fecha_servicio_hasta: formData.value.fecha_servicio_hasta || undefined,
  fecha_vto_pago: formData.value.fecha_vto_pago || undefined,
  observaciones: formData.value.observaciones || undefined,
  moneda: "PES",
  cotizacion: 1,
});

const ejecutarEmision = async (
  request: EmitirComprobanteRequest,
  idempotencyKey: string,
  esVerificacion: boolean,
) => {
  if (loading.value) return;

  loading.value = true;
  if (!esVerificacion) {
    mostrarPreview.value = false;
    mostrarConfirmacionFechaFiscal.value = false;
  }

  const puntoVentaNumero =
    operacionIncierta.value?.puntoVentaNumero ??
    puntoVentaSeleccionado.value?.numero ??
    0;
  const numeroPlanificado =
    operacionIncierta.value?.numeroPlanificado ?? proximoNumero.value;
  const totalPlanificado =
    operacionIncierta.value?.totalPlanificado ?? totales.value.total;

  try {
    const resultado = await comprobantesStore.emitirComprobante(
      request,
      idempotencyKey,
    );
    const respuestaIncierta = normalizarRespuestaReconciliacion(
      resultado,
      request,
      puntoVentaNumero,
      numeroPlanificado,
      totalPlanificado,
    );

    if (respuestaIncierta) {
      registrarOperacionIncierta(request, idempotencyKey, respuestaIncierta);
      return;
    }

    if (resultado.exito) {
      finalizarOperacionIncierta();
      showSuccess(
        "Comprobante emitido",
        `CAE ${resultado.cae || "sin informar"} | Total $${Number(resultado.total).toFixed(2)}`,
      );

      if (resultado.comprobante_id) {
        await router.push({
          name: "comprobante-detalle",
          params: { id: resultado.comprobante_id },
        });
      } else {
        await router.push({ name: "comprobantes" });
      }
      return;
    }

    finalizarOperacionIncierta();
    showError(
      esVerificacion
        ? "ARCA confirmó que el comprobante no fue autorizado"
        : "No se pudo emitir el comprobante",
      [resultado.mensaje, ...resultado.errores].filter(Boolean).join(" | "),
    );
  } catch (error: unknown) {
    console.error(
      esVerificacion
        ? "Error al verificar la operación fiscal"
        : "Error al emitir comprobante",
    );
    const detail = obtenerDetalleError(error);
    const respuestaIncierta = normalizarRespuestaReconciliacion(
      detail,
      request,
      puntoVentaNumero,
      numeroPlanificado,
      totalPlanificado,
    );

    if (respuestaIncierta) {
      registrarOperacionIncierta(request, idempotencyKey, respuestaIncierta);
      return;
    }

    if (
      !esVerificacion &&
      esRegistroDesconocido(detail) &&
      detail.categoria_error === "duplicado_logico"
    ) {
      const errores = Array.isArray(detail.errores)
        ? detail.errores.filter(
            (item): item is string => typeof item === "string",
          )
        : [];
      mensajeConfirmacionDuplicadoLogico.value =
        [
          typeof detail.mensaje === "string" ? detail.mensaje : "",
          ...errores,
        ]
          .filter(Boolean)
          .join(" ") ||
        "Existe un comprobante local muy similar ya autorizado. Confirmá si corresponde emitirlo igualmente.";
      mostrarConfirmacionDuplicadoLogico.value = true;
      return;
    }

    const mensajeRechazoFinal = obtenerMensajeRechazoFinal(detail);
    if (
      esVerificacion &&
      obtenerStatusHttpError(error) === 400 &&
      mensajeRechazoFinal
    ) {
      finalizarOperacionIncierta();
      showError(
        "ARCA confirmó que el comprobante no fue autorizado",
        mensajeRechazoFinal,
      );
      return;
    }

    if (esVerificacion) {
      showWarning(
        "No se pudo verificar el estado",
        "La operación continúa bloqueada. Conservá esta pantalla y volvé a verificar con la misma clave.",
      );
      return;
    }

    const mensaje =
      esRegistroDesconocido(detail) && typeof detail.mensaje === "string"
        ? detail.mensaje
        : "Ocurrió un error inesperado. Revisá los datos e intentá nuevamente.";
    showError("Error al emitir comprobante", mensaje);
  } finally {
    loading.value = false;
  }
};

const confirmarEmision = async () => {
  if (loading.value || formularioBloqueado.value) return;
  const request = construirRequestEmision();
  await ejecutarEmision(request, obtenerIdempotencyKeyEmision(), false);
};

const verificarEstado = async () => {
  const operacion = operacionIncierta.value;
  if (!operacion || loading.value) return;

  if (!emisorOperacionCoincide.value) {
    showWarning(
      "Emisor distinto",
      `Volvé a seleccionar ${operacion.empresaNombre} para verificar esta operación sin cambiar su alcance.`,
    );
    return;
  }

  await ejecutarEmision(
    operacion.request,
    operacion.idempotencyKey,
    true,
  );
};
const confirmarDuplicadoLogico = async () => {
  confirmacionDuplicadoLogico.value = true;
  mostrarConfirmacionDuplicadoLogico.value = false;
  await confirmarEmision();
};

const cancelar = () => {
  if (operacionIncierta.value) {
    showWarning(
      "Verificación fiscal pendiente",
      "No podés cancelar esta operación hasta obtener un resultado final.",
    );
    return;
  }
  mostrarCancelacion.value = true;
};

const confirmarCancelacion = () => {
  resetearIdempotencyKeyEmision();
  mostrarCancelacion.value = false;
  router.push({ name: "comprobantes" });
};
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <h1
        class="text-3xl font-bold text-gray-900 flex items-center gap-3"
        data-testid="page-title"
      >
        <DocumentTextIcon class="h-8 w-8" />
        Nueva Factura
      </h1>
      <p class="mt-2 text-gray-600">
        Complete los datos para emitir un nuevo comprobante electrónico
      </p>
    </div>

    <section
      v-if="operacionIncierta"
      data-testid="operacion-incierta"
      role="status"
      aria-live="polite"
      class="mb-6 rounded-xl border border-orange-300 bg-orange-50 p-5 text-orange-950"
    >
      <div
        class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"
      >
        <div>
          <div class="flex items-center gap-2">
            <ExclamationTriangleIcon class="h-6 w-6 text-orange-700" />
            <h2 class="text-lg font-semibold">
              Emisión pendiente de verificación
            </h2>
          </div>
          <p class="mt-2 max-w-3xl text-sm">
            ARCA pudo haber procesado esta solicitud. Los datos y la clave
            quedaron congelados: no generes otra factura ni cambies la operación.
          </p>
        </div>
        <button
          type="button"
          data-testid="verificar-operacion-incierta"
          :disabled="loading || !emisorOperacionCoincide"
          class="inline-flex items-center justify-center gap-2 rounded-lg bg-orange-700 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-800 disabled:cursor-not-allowed disabled:opacity-50"
          @click="verificarEstado"
        >
          <ArrowPathIcon
            class="h-5 w-5"
            :class="{ 'animate-spin': loading }"
          />
          {{ loading ? "Verificando..." : "Verificar estado" }}
        </button>
      </div>

      <div
        class="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5"
      >
        <div>
          <span
            class="block text-xs font-semibold uppercase text-orange-700"
          >
            Emisor
          </span>
          <span>{{ operacionIncierta.empresaNombre }}</span>
        </div>
        <div>
          <span
            class="block text-xs font-semibold uppercase text-orange-700"
          >
            Comprobante
          </span>
          <span>{{ tipoOperacionIncierta }}</span>
        </div>
        <div>
          <span
            class="block text-xs font-semibold uppercase text-orange-700"
          >
            Fecha fiscal
          </span>
          <span>{{ fechaOperacionIncierta }}</span>
        </div>
        <div>
          <span
            class="block text-xs font-semibold uppercase text-orange-700"
          >
            Punto y número
          </span>
          <span>
            {{ String(puntoVentaOperacionIncierta).padStart(4, "0") }}-
            {{
              numeroOperacionIncierta > 0
                ? String(numeroOperacionIncierta).padStart(8, "0")
                : "pendiente"
            }}
          </span>
        </div>
        <div>
          <span
            class="block text-xs font-semibold uppercase text-orange-700"
          >
            Total
          </span>
          <span>ARS {{ Number(totalOperacionIncierta).toFixed(2) }}</span>
        </div>
      </div>

      <p
        v-if="respuestaOperacionIncierta?.cae"
        class="mt-4 rounded-lg bg-white/70 px-3 py-2 text-sm"
      >
        FactuFlow recibió el CAE
        <span class="font-mono font-semibold">
          {{ respuestaOperacionIncierta.cae }}
        </span>
        , pero todavía no pudo confirmar el cierre local.
      </p>
      <p
        v-if="!emisorOperacionCoincide"
        data-testid="operacion-incierta-emisor-distinto"
        class="mt-4 font-medium text-red-800"
      >
        Volvé a seleccionar {{ operacionIncierta.empresaNombre }} para verificar.
        La operación permanece bloqueada.
      </p>
    </section>

    <form
      data-testid="formulario-emision"
      v-bind="formularioBloqueado ? { inert: true } : {}"
      :aria-disabled="formularioBloqueado"
      class="space-y-6"
      @submit.prevent="abrirVistaPrevia"
    >
      <!-- Sección 1: Datos del Comprobante -->
      <BaseCard title="📄 Datos del Comprobante">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Tipo de comprobante -->
          <div>
            <label
              for="tipo-comprobante"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              Tipo de Comprobante *
            </label>
            <select
              id="tipo-comprobante"
              v-model="formData.tipo_comprobante"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option
                v-for="tipo in tiposComprobanteDisponibles"
                :key="tipo.value"
                :value="tipo.value"
              >
                {{ tipo.label }}
              </option>
            </select>
          </div>

          <!-- Punto de venta -->
          <div>
            <label
              for="punto-venta"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              Punto de Venta *
            </label>
            <select
              id="punto-venta"
              v-model="formData.punto_venta_id"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              @change="actualizarProximoNumero"
            >
              <option
                v-for="pv in puntosVentaUsables"
                :key="pv.id"
                :value="pv.id"
              >
                {{ String(pv.numero).padStart(4, "0") }} -
                {{ pv.nombre || "Sin nombre" }}
              </option>
            </select>
            <p
              v-if="puntosVentaUsables.length === 0"
              class="mt-1 text-sm text-red-600"
            >
              No hay puntos de venta Web Services habilitados para emitir con FactuFlow.
            </p>
          </div>

          <!-- Concepto -->
          <div>
            <label
              for="concepto"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              Concepto *
            </label>
            <select
              id="concepto"
              v-model="formData.concepto"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option
                disabled
                value=""
              >
                Elegir productos o servicios
              </option>
              <option :value="TIPOS_CONCEPTO.PRODUCTOS">
                {{ TIPOS_CONCEPTO_NOMBRES[1] }}
              </option>
              <option :value="TIPOS_CONCEPTO.SERVICIOS">
                {{ TIPOS_CONCEPTO_NOMBRES[2] }}
              </option>
              <option :value="TIPOS_CONCEPTO.PRODUCTOS_Y_SERVICIOS">
                {{ TIPOS_CONCEPTO_NOMBRES[3] }}
              </option>
            </select>
          </div>
        </div>

        <div class="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Fecha de emisión *
            </label>
            <input
              v-model="formData.fecha_emision"
              type="date"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
          </div>
        </div>

        <!-- Próximo número -->
        <div
          v-if="consultandoProximoNumero"
          class="mt-4 text-sm text-gray-600"
        >
          Consultando próximo número...
        </div>
        <div
          v-else-if="proximoNumero !== null"
          class="mt-4 text-sm text-gray-600"
        >
          El próximo número será:
          <span class="font-mono font-semibold">{{
            String(proximoNumero).padStart(8, "0")
          }}</span>
        </div>
        <div
          v-else-if="errorProximoNumero"
          class="mt-4 text-sm text-red-700"
        >
          {{ errorProximoNumero }}
        </div>

        <!-- Fechas de servicios -->
        <div
          v-if="mostrarFechasServicios"
          class="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4"
        >
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Fecha Servicio Desde *
            </label>
            <input
              v-model="formData.fecha_servicio_desde"
              type="date"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Fecha Servicio Hasta *
            </label>
            <input
              v-model="formData.fecha_servicio_hasta"
              type="date"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Fecha Vto. Pago *
            </label>
            <input
              v-model="formData.fecha_vto_pago"
              type="date"
              required
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
          </div>
        </div>
      </BaseCard>

      <!-- Sección 2: Cliente -->
      <ClienteSelector
        v-model="formData.cliente"
        :tipo-comprobante="formData.tipo_comprobante"
      />

      <!-- Sección 3: Items -->
      <ItemsTable
        :items="formData.items"
        :solo-iva-cero="esComprobanteC"
        @update:items="formData.items = $event"
      />

      <!-- Sección 4: Totales -->
      <BaseCard title="💰 Totales">
        <TotalesPanel
          :subtotal="totales.subtotal"
          :iva21="totales.iva21"
          :iva105="totales.iva105"
          :iva27="totales.iva27"
          :total="totales.total"
        />
      </BaseCard>

      <!-- Sección 5: Observaciones -->
      <BaseCard title="📝 Observaciones">
        <textarea
          v-model="formData.observaciones"
          rows="3"
          placeholder="Observaciones adicionales (opcional)"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </BaseCard>

      <!-- Botones de acción -->
      <div class="flex items-center justify-end gap-4">
        <button
          type="button"
          data-testid="comprobante-cancelar"
          :disabled="formularioBloqueado"
          class="px-6 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="cancelar"
        >
          Cancelar
        </button>

        <button
          type="button"
          data-testid="comprobante-vista-previa"
          :disabled="!formularioValido || formularioBloqueado"
          class="inline-flex items-center gap-2 px-6 py-2 text-blue-700 bg-blue-50 border border-blue-300 rounded-lg hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="abrirVistaPrevia"
        >
          <EyeIcon class="h-5 w-5" />
          Vista Previa
        </button>

        <button
          type="submit"
          data-testid="comprobante-emitir"
          :disabled="!formularioValido || loading || formularioBloqueado"
          class="inline-flex items-center gap-2 px-6 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <PaperAirplaneIcon class="h-5 w-5" />
          {{ loading ? "Emitiendo..." : "Emitir Factura" }}
        </button>
      </div>
    </form>

    <!-- Modal de vista previa -->
    <ComprobantePreview
      v-if="mostrarPreview"
      :form-data="formData"
      :totales="totales"
      :proximo-numero="proximoNumero"
      :punto-venta-numero="puntoVentaSeleccionado?.numero || null"
      :empresa="empresaActiva"
      @close="mostrarPreview = false"
      @confirm="solicitarConfirmacionFechaFiscal"
    />

    <ConfirmDialog
      :show="mostrarConfirmacionFechaFiscal"
      title="Confirmar fecha fiscal"
      :message="mensajeConfirmacionFechaFiscal"
      confirm-text="Emitir con esta fecha"
      cancel-text="Volver a revisar"
      variant="danger"
      @confirm="confirmarEmision"
      @cancel="mostrarConfirmacionFechaFiscal = false"
    />

    <ConfirmDialog
      :show="mostrarConfirmacionDuplicadoLogico"
      title="Duplicado probable"
      :message="mensajeConfirmacionDuplicadoLogico"
      confirm-text="Emitir igualmente"
      cancel-text="Volver a revisar"
      variant="danger"
      @confirm="confirmarDuplicadoLogico"
      @cancel="mostrarConfirmacionDuplicadoLogico = false"
    />

    <ConfirmDialog
      :show="mostrarCancelacion"
      title="Cancelar comprobante"
      message="Se perderán los cambios que todavía no emitiste. Puedes volver al listado o seguir editando."
      confirm-text="Salir sin guardar"
      cancel-text="Seguir editando"
      @confirm="confirmarCancelacion"
      @cancel="mostrarCancelacion = false"
    />
  </div>
</template>
