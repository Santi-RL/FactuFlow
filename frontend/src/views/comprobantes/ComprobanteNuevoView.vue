<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useNotification } from "@/composables/useNotification";
import { useEmpresaStore } from "@/stores/empresa";
import { useComprobantesStore } from "@/stores/comprobantes";
import { usePuntosVentaStore } from "@/stores/puntos_venta";
import {
  DocumentTextIcon,
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
} from "@/types/comprobante";
import {
  TIPOS_COMPROBANTE,
  TIPOS_COMPROBANTE_NOMBRES,
  TIPOS_CONCEPTO,
  TIPOS_CONCEPTO_NOMBRES,
  TIPOS_DOCUMENTO,
} from "@/types/comprobante";

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
const confirmacionDuplicadoLogico = ref(false);
const proximoNumero = ref<number | null>(null);
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

const resetearIdempotencyKeyEmision = () => {
  idempotencyKeyEmision.value = null;
  confirmacionDuplicadoLogico.value = false;
  mostrarConfirmacionDuplicadoLogico.value = false;
  mensajeConfirmacionDuplicadoLogico.value = "";
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

    resetearIdempotencyKeyEmision();
    limpiarClienteSeleccionado();
    await cargarDatosEmisorActivo();
  },
);

watch(formData, resetearIdempotencyKeyEmision, { deep: true });

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

  if (!puntoVentaId || !empresaId.value) return;

  try {
    const puntoVenta = puntosVenta.value.find((pv) => pv.id === puntoVentaId);
    if (!puntoVenta?.usable_factuflow) return;

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
      console.error("Error al obtener próximo número:", error);
    }
  }
};

const abrirVistaPrevia = () => {
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

const confirmarEmision = async () => {
  loading.value = true;
  mostrarPreview.value = false;
  mostrarConfirmacionFechaFiscal.value = false;

  try {
    const request: EmitirComprobanteRequest = {
      empresa_id: empresaId.value,
      punto_venta_id: formData.value.punto_venta_id,
      tipo_comprobante: formData.value.tipo_comprobante,
      concepto: Number(formData.value.concepto),
      fecha_emision: formData.value.fecha_emision,
      confirmacion_fecha_fiscal: true,
      confirmacion_duplicado_logico: confirmacionDuplicadoLogico.value,

      // Cliente
      cliente_id: formData.value.cliente.cliente_id,
      tipo_documento: formData.value.cliente.tipo_documento,
      numero_documento: formData.value.cliente.numero_documento,
      razon_social: formData.value.cliente.razon_social,
      condicion_iva: formData.value.cliente.condicion_iva,
      domicilio: formData.value.cliente.domicilio,
      guardar_cliente: true,

      // Items
      items: normalizarOrdenItems(formData.value.items),

      // Servicios
      fecha_servicio_desde: formData.value.fecha_servicio_desde || undefined,
      fecha_servicio_hasta: formData.value.fecha_servicio_hasta || undefined,
      fecha_vto_pago: formData.value.fecha_vto_pago || undefined,

      // Observaciones
      observaciones: formData.value.observaciones || undefined,

      // Moneda
      moneda: "PES",
      cotizacion: 1,
    };

    const resultado = await comprobantesStore.emitirComprobante(
      request,
      obtenerIdempotencyKeyEmision(),
    );

    if (resultado.exito) {
      showSuccess(
        "Comprobante emitido",
        `CAE ${resultado.cae || "sin informar"} | Total $${Number(resultado.total).toFixed(2)}`,
      );

      // Redirigir al detalle
      if (resultado.comprobante_id) {
        resetearIdempotencyKeyEmision();
        router.push({
          name: "comprobante-detalle",
          params: { id: resultado.comprobante_id },
        });
      } else {
        resetearIdempotencyKeyEmision();
        router.push({ name: "comprobantes" });
      }
    } else {
      showError(
        "No se pudo emitir el comprobante",
        [resultado.mensaje, ...resultado.errores].filter(Boolean).join(" | "),
      );
    }
  } catch (error: any) {
    console.error("Error al emitir:", error);
    const detail = error.response?.data?.detail;
    if (detail?.categoria_error === "duplicado_logico") {
      mensajeConfirmacionDuplicadoLogico.value =
        [detail.mensaje, ...(detail.errores || [])]
          .filter(Boolean)
          .join(" ") ||
        "Existe un comprobante local muy similar ya autorizado. Confirmá si corresponde emitirlo igualmente.";
      mostrarConfirmacionDuplicadoLogico.value = true;
      return;
    }
    showError(
      "Error al emitir comprobante",
      detail?.mensaje ||
        error.message ||
        "Ocurrió un error inesperado. Revisa los datos e intenta nuevamente.",
    );
  } finally {
    loading.value = false;
  }
};

const confirmarDuplicadoLogico = async () => {
  confirmacionDuplicadoLogico.value = true;
  mostrarConfirmacionDuplicadoLogico.value = false;
  await confirmarEmision();
};

const cancelar = () => {
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

    <form
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
          v-if="proximoNumero !== null"
          class="mt-4 text-sm text-gray-600"
        >
          El próximo número será:
          <span class="font-mono font-semibold">{{
            String(proximoNumero).padStart(8, "0")
          }}</span>
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
          class="px-6 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500"
          @click="cancelar"
        >
          Cancelar
        </button>

        <button
          type="button"
          data-testid="comprobante-vista-previa"
          :disabled="!formularioValido"
          class="inline-flex items-center gap-2 px-6 py-2 text-blue-700 bg-blue-50 border border-blue-300 rounded-lg hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="abrirVistaPrevia"
        >
          <EyeIcon class="h-5 w-5" />
          Vista Previa
        </button>

        <button
          type="submit"
          data-testid="comprobante-emitir"
          :disabled="!formularioValido || loading"
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
