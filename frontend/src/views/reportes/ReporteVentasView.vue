<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useEmpresaStore } from "@/stores/empresa";
import { useNotification } from "@/composables/useNotification";
import { useFormatters } from "@/composables/useFormatters";
import reportesService from "@/services/reportes.service";
import type { ReporteVentas } from "@/services/reportes.service";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import BaseTable from "@/components/ui/BaseTable.vue";
import BaseEmpty from "@/components/ui/BaseEmpty.vue";
import { ArrowLeftIcon, DocumentChartBarIcon } from "@heroicons/vue/24/outline";

const router = useRouter();
const empresaStore = useEmpresaStore();
const { showError } = useNotification();
const { formatearFecha, formatearMoneda } = useFormatters();

const loading = ref(false);
const reporte = ref<ReporteVentas | null>(null);
let generarReporteRequestId = 0;

// Fechas por defecto: mes actual
const hoy = new Date();
const primerDiaMes = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
const ultimoDiaMes = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0);

const desde = ref(primerDiaMes.toISOString().split("T")[0]);
const hasta = ref(ultimoDiaMes.toISOString().split("T")[0]);

const columns = [
  { key: "fecha_emision", label: "Fecha", sortable: false },
  { key: "tipo_nombre", label: "Tipo", sortable: false },
  { key: "numero_completo", label: "Número", sortable: false },
  { key: "cliente_nombre", label: "Cliente", sortable: false },
  { key: "total", label: "Total", sortable: false },
];

const empresaActivaId = computed(() => empresaStore.empresaActivaId);

const generarReporte = async () => {
  const requestId = ++generarReporteRequestId;
  const empresaIdSolicitada = empresaActivaId.value;
  if (!empresaIdSolicitada) {
    showError(
      "Empresa activa requerida",
      "Selecciona la empresa con la que queres trabajar antes de generar el reporte.",
    );
    return;
  }

  if (!desde.value || !hasta.value) {
    showError("Error", "Debe seleccionar un rango de fechas");
    return;
  }

  if (desde.value > hasta.value) {
    showError(
      "Error",
      'La fecha "desde" no puede ser mayor que la fecha "hasta"',
    );
    return;
  }

  loading.value = true;
  try {
    const resultado = await reportesService.obtenerReporteVentas(
      desde.value,
      hasta.value,
    );
    if (
      requestId === generarReporteRequestId &&
      empresaActivaId.value === empresaIdSolicitada
    ) {
      reporte.value = resultado;
    }
  } catch (error: any) {
    if (requestId === generarReporteRequestId) {
      showError(
        "Error",
        error.response?.data?.detail || "No se pudo generar el reporte",
      );
      reporte.value = null;
    }
  } finally {
    if (requestId === generarReporteRequestId) {
      loading.value = false;
    }
  }
};

const volver = () => {
  router.push("/reportes");
};

onMounted(async () => {
  if (!empresaStore.empresaActivaId) {
    await empresaStore.inicializarEmpresaActiva();
  }
});

watch(
  () => empresaStore.empresaActivaId,
  async (empresaId, previousEmpresaId) => {
    if (!empresaId || empresaId === previousEmpresaId) return;

    const debeRegenerar = !!reporte.value;
    reporte.value = null;

    if (debeRegenerar) {
      await generarReporte();
    }
  },
);

const resumenCards = computed(() => {
  if (!reporte.value) return [];

  return [
    {
      label: "Total Facturas",
      valor: formatearMoneda(reporte.value.resumen.total_facturas),
      color: "text-status-success",
      bg: "bg-emerald-50",
    },
    {
      label: "Total Notas de Crédito",
      valor: formatearMoneda(reporte.value.resumen.total_notas_credito),
      color: "text-status-danger",
      bg: "bg-surface-page",
    },
    {
      label: "Total Notas de Débito",
      valor: formatearMoneda(reporte.value.resumen.total_notas_debito),
      color: "text-brand-flow",
      bg: "bg-brand-mint",
    },
    {
      label: "Total Neto",
      valor: formatearMoneda(reporte.value.resumen.total_neto),
      color: "text-brand-teal",
      bg: "bg-surface-page",
    },
  ];
});
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <div class="mb-4 flex items-center gap-4">
        <button
          type="button"
          class="rounded-control p-2 text-brand-slate transition-colors hover:bg-brand-mint hover:text-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
          aria-label="Volver a reportes"
          title="Volver"
          @click="volver"
        >
          <ArrowLeftIcon class="h-5 w-5" />
        </button>
        <div>
          <h1 class="text-3xl font-bold text-brand-ink">
            Reporte de Ventas
          </h1>
          <p class="mt-1 text-brand-slate">
            Resumen de comprobantes emitidos por período
          </p>
        </div>
      </div>
    </div>

    <!-- Filtros -->
    <BaseCard class="mb-6">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <BaseInput
          v-model="desde"
          type="date"
          label="Desde"
          required
        />
        <BaseInput
          v-model="hasta"
          type="date"
          label="Hasta"
          required
        />
        <div class="flex items-end">
          <BaseButton
            :disabled="loading"
            class="w-full"
            @click="generarReporte"
          >
            <DocumentChartBarIcon class="h-5 w-5 mr-2" />
            Generar Reporte
          </BaseButton>
        </div>
      </div>
    </BaseCard>

    <!-- Loading -->
    <div
      v-if="loading"
      class="flex justify-center py-12"
    >
      <BaseSpinner />
    </div>

    <!-- Reporte -->
    <template v-else-if="reporte">
      <!-- Resumen -->
      <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <BaseCard
          v-for="card in resumenCards"
          :key="card.label"
          :padding="false"
        >
          <div class="p-6">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-brand-slate">
                  {{ card.label }}
                </p>
                <p :class="['mt-2 text-2xl font-bold', card.color]">
                  {{ card.valor }}
                </p>
              </div>
              <div :class="['rounded-panel p-3', card.bg]">
                <DocumentChartBarIcon :class="['h-6 w-6', card.color]" />
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Período -->
      <div class="mb-4 text-sm text-brand-slate">
        <p>
          <span class="font-medium">Período:</span>
          {{ formatearFecha(reporte.resumen.periodo.desde) }} -
          {{ formatearFecha(reporte.resumen.periodo.hasta) }}
        </p>
        <p>
          <span class="font-medium">Total comprobantes:</span>
          {{ reporte.resumen.cantidad_comprobantes }}
        </p>
      </div>

      <!-- Tabla de Comprobantes -->
      <BaseCard>
        <div
          class="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
        >
          <h2 class="text-lg font-semibold text-brand-ink">
            Detalle de Comprobantes
          </h2>
          <p
            class="rounded-panel border border-border-subtle bg-brand-mint px-3 py-2 text-sm text-brand-slate"
          >
            Este reporte es solo de consulta. Muestra comprobantes autorizados
            de la empresa activa.
          </p>
        </div>

        <BaseTable
          v-if="reporte.comprobantes.length > 0"
          :columns="columns"
          :data="reporte.comprobantes"
          :loading="false"
        >
          <template #cell-fecha_emision="{ value }">
            <span class="text-brand-ink">{{ formatearFecha(value) }}</span>
          </template>

          <template #cell-tipo_nombre="{ row }">
            <div>
              <span class="text-sm text-brand-ink">{{ row.tipo_nombre }}</span>
            </div>
          </template>

          <template #cell-numero_completo="{ value }">
            <span class="font-mono text-sm">{{ value }}</span>
          </template>

          <template #cell-cliente_nombre="{ value }">
            <span class="text-brand-ink">{{ value }}</span>
          </template>

          <template #cell-total="{ value }">
            <span class="font-semibold text-brand-ink">{{
              formatearMoneda(value)
            }}</span>
          </template>
        </BaseTable>

        <BaseEmpty v-else>
          No hay comprobantes en el período seleccionado
        </BaseEmpty>
      </BaseCard>
    </template>

    <!-- Estado inicial -->
    <BaseEmpty v-else>
      <DocumentChartBarIcon class="mx-auto mb-4 h-12 w-12 text-brand-slate" />
      <p class="text-brand-slate">
        Seleccioná un rango de fechas y hacé clic en "Generar Reporte" para ver
        los resultados
      </p>
    </BaseEmpty>
  </div>
</template>
