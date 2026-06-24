<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useClientesStore } from "@/stores/clientes";
import { useEmpresaStore } from "@/stores/empresa";
import certificadosService from "@/services/certificados.service";
import comprobantesService from "@/services/comprobantes.service";
import reportesService from "@/services/reportes.service";
import type { CertificadoAlerta } from "@/types/certificado";
import type { Certificado } from "@/types/certificado";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import {
  UsersIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  DocumentDuplicateIcon,
} from "@heroicons/vue/24/outline";

const authStore = useAuthStore();
const clientesStore = useClientesStore();
const empresaStore = useEmpresaStore();
const router = useRouter();
const loading = ref(true);
const alertasCertificados = ref<CertificadoAlerta[]>([]);
const totalComprobantesMes = ref(0);
const ultimoComprobante = ref("-");
const estadoCertificado = ref("Sin certificado");
let cargarDashboardRequestId = 0;

onMounted(async () => {
  if (!empresaStore.empresaActivaId) {
    await empresaStore.inicializarEmpresaActiva();
  }

  await cargarDashboard();
});

watch(
  () => empresaStore.empresaActivaId,
  async (empresaId, anteriorId) => {
    if (!empresaId || empresaId === anteriorId) return;
    await cargarDashboard();
  },
);

const formatearFecha = (fecha: string) => {
  return new Date(fecha).toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
};

const irACertificados = () => {
  router.push({ name: "certificados" });
};

const obtenerRangoMesActual = () => {
  const hoy = new Date();
  const desde = new Date(hoy.getFullYear(), hoy.getMonth(), 1)
    .toISOString()
    .split("T")[0];
  const hasta = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0)
    .toISOString()
    .split("T")[0];

  return { desde, hasta };
};

const obtenerEstadoCertificado = (certificados: Certificado[]) => {
  const certificadoActivo = certificados.find(
    (certificado) => certificado.activo,
  );

  if (!certificadoActivo) {
    return "Sin certificado";
  }

  if (certificadoActivo.estado === "valido") {
    return "Válido";
  }

  if (certificadoActivo.estado === "por_vencer") {
    return "Por vencer";
  }

  return "Vencido";
};

const formatearNumeroComprobante = (puntoVenta: number, numero: number) => {
  return `${String(puntoVenta).padStart(4, "0")}-${String(numero).padStart(
    8,
    "0",
  )}`;
};

const cargarDashboard = async () => {
  const requestId = ++cargarDashboardRequestId;
  const empresaIdSolicitada = empresaStore.empresaActivaId;
  if (!empresaIdSolicitada) {
    loading.value = false;
    return;
  }

  loading.value = true;
  const sigueVigente = () =>
    requestId === cargarDashboardRequestId &&
    empresaStore.empresaActivaId === empresaIdSolicitada;

  const { desde, hasta } = obtenerRangoMesActual();
  try {
    const [
      clientesResult,
      alertasResult,
      certificadosResult,
      reporteVentasResult,
      ultimoComprobanteResult,
    ] = await Promise.allSettled([
      clientesStore.fetchClientes({ per_page: 100 }),
      certificadosService.obtenerAlertasVencimiento(),
      certificadosService.listar(),
      reportesService.obtenerReporteVentas(desde, hasta),
      comprobantesService.listar({
        page: 1,
        per_page: 1,
      }),
    ]);

    if (!sigueVigente()) return;

    if (clientesResult.status === "rejected") {
      console.error("Error loading clientes:", clientesResult.reason);
    }

    if (alertasResult.status === "fulfilled") {
      alertasCertificados.value = alertasResult.value;
    } else {
      alertasCertificados.value = [];
      console.error("Error loading certificate alerts:", alertasResult.reason);
    }

    if (certificadosResult.status === "fulfilled") {
      estadoCertificado.value = obtenerEstadoCertificado(
        certificadosResult.value,
      );
    } else {
      estadoCertificado.value = "Sin certificado";
      console.error("Error loading certificados:", certificadosResult.reason);
    }

    if (reporteVentasResult.status === "fulfilled") {
      totalComprobantesMes.value =
        reporteVentasResult.value.resumen.cantidad_comprobantes;
    } else {
      totalComprobantesMes.value = 0;
      console.error("Error loading ventas report:", reporteVentasResult.reason);
    }

    if (
      ultimoComprobanteResult.status === "fulfilled" &&
      ultimoComprobanteResult.value.items.length > 0
    ) {
      const comprobante = ultimoComprobanteResult.value.items[0];
      ultimoComprobante.value = formatearNumeroComprobante(
        comprobante.punto_venta_numero,
        comprobante.numero,
      );
    } else {
      ultimoComprobante.value = "-";
      if (ultimoComprobanteResult.status === "rejected") {
        console.error(
          "Error loading ultimo comprobante:",
          ultimoComprobanteResult.reason,
        );
      }
    }
  } finally {
    if (requestId === cargarDashboardRequestId) {
      loading.value = false;
    }
  }
};

const stats = computed(() => [
  {
    name: "Total Clientes",
    value: clientesStore.pagination.total || 0,
    icon: UsersIcon,
    color: "text-brand-teal",
    bg: "bg-brand-mint",
  },
  {
    name: "Comprobantes del Mes",
    value: totalComprobantesMes.value,
    icon: DocumentTextIcon,
    color: "text-status-success",
    bg: "bg-status-success-soft",
  },
  {
    name: "Último Comprobante",
    value: ultimoComprobante.value,
    icon: CheckCircleIcon,
    color: "text-brand-flow",
    bg: "bg-surface-page",
  },
  {
    name: "Estado Certificado",
    value: estadoCertificado.value,
    icon: ExclamationTriangleIcon,
    color: "text-status-warning",
    bg: "bg-status-warning-soft",
  },
]);
</script>

<template>
  <div>
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-brand-ink">
        ¡Bienvenido, {{ authStore.user?.nombre }}!
      </h1>
      <p class="mt-2 text-brand-slate">
        Panel de control de FactuFlow
      </p>
    </div>

    <BaseSpinner v-if="loading" />

    <div v-else>
      <!-- Alertas de certificados -->
      <BaseAlert
        v-if="alertasCertificados.length > 0"
        type="warning"
        class="mb-6"
      >
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div class="flex-1">
            <p class="mb-2 flex items-center gap-2 font-semibold">
              <ExclamationTriangleIcon class="h-5 w-5 flex-shrink-0 text-status-warning" />
              <span>Certificado(s) próximo(s) a vencer</span>
            </p>
            <div
              v-for="alerta in alertasCertificados.slice(0, 2)"
              :key="alerta.id"
              class="text-sm mb-1"
            >
              <span class="font-medium">{{ alerta.nombre }}</span>
              <span v-if="alerta.dias_restantes > 0">
                vence en {{ alerta.dias_restantes }} día(s) ({{
                  formatearFecha(alerta.fecha_vencimiento)
                }})
              </span>
              <span
                v-else
                class="font-semibold text-status-danger"
              >
                ¡YA VENCIÓ! ({{ formatearFecha(alerta.fecha_vencimiento) }})
              </span>
            </div>
            <p
              v-if="alertasCertificados.length > 2"
              class="text-sm mt-1"
            >
              y {{ alertasCertificados.length - 2 }} más...
            </p>
            <p class="text-sm mt-2">
              Te recomendamos renovarlos pronto para evitar interrupciones en la
              facturación.
            </p>
          </div>
          <BaseButton
            variant="secondary"
            size="sm"
            class="w-full sm:ml-4 sm:w-auto sm:flex-shrink-0"
            @click="irACertificados"
          >
            Ver certificados
          </BaseButton>
        </div>
      </BaseAlert>

      <!-- Stats Grid -->
      <div class="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <BaseCard
          v-for="stat in stats"
          :key="stat.name"
          :padding="false"
        >
          <div class="p-6">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-brand-slate">
                  {{ stat.name }}
                </p>
                <p class="mt-2 text-3xl font-bold text-brand-ink">
                  {{ stat.value }}
                </p>
              </div>
              <div :class="['rounded-panel p-3', stat.bg]">
                <component
                  :is="stat.icon"
                  :class="['h-6 w-6', stat.color]"
                />
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Quick Actions -->
      <BaseCard title="Accesos Rápidos">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <router-link
            to="/clientes/nuevo"
            class="group rounded-panel border-2 border-dashed border-border-subtle p-6 text-center transition-colors hover:border-brand-flow hover:bg-brand-mint focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
          >
            <UsersIcon class="mx-auto mb-2 h-8 w-8 text-brand-slate transition-colors group-hover:text-brand-flow" />
            <h3 class="font-medium text-brand-ink">
              Nuevo Cliente
            </h3>
            <p class="mt-1 text-sm text-brand-slate">
              Agregar un cliente
            </p>
          </router-link>

          <router-link
            to="/comprobantes"
            class="group rounded-panel border-2 border-dashed border-border-subtle p-6 text-center transition-colors hover:border-brand-flow hover:bg-brand-mint focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
          >
            <DocumentTextIcon class="mx-auto mb-2 h-8 w-8 text-brand-slate transition-colors group-hover:text-brand-flow" />
            <h3 class="font-medium text-brand-ink">
              Emitir Factura
            </h3>
            <p class="mt-1 text-sm text-brand-slate">
              Crear comprobante
            </p>
          </router-link>

          <router-link
            to="/comprobantes/lotes"
            class="group rounded-panel border-2 border-dashed border-border-subtle p-6 text-center transition-colors hover:border-brand-flow hover:bg-brand-mint focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
          >
            <DocumentDuplicateIcon class="mx-auto mb-2 h-8 w-8 text-brand-slate transition-colors group-hover:text-brand-flow" />
            <h3 class="font-medium text-brand-ink">
              Emisión masiva
            </h3>
            <p class="mt-1 text-sm text-brand-slate">
              Validar y emitir lotes
            </p>
          </router-link>

          <router-link
            to="/empresa"
            class="group rounded-panel border-2 border-dashed border-border-subtle p-6 text-center transition-colors hover:border-brand-flow hover:bg-brand-mint focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
          >
            <CheckCircleIcon class="mx-auto mb-2 h-8 w-8 text-brand-slate transition-colors group-hover:text-brand-flow" />
            <h3 class="font-medium text-brand-ink">
              Configurar
            </h3>
            <p class="mt-1 text-sm text-brand-slate">
              Mi empresa
            </p>
          </router-link>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
