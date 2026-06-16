<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useEmpresaStore } from "@/stores/empresa";
import { useNotification } from "@/composables/useNotification";
import { useFormatters } from "@/composables/useFormatters";
import reportesService from "@/services/reportes.service";
import type { ReporteIVA } from "@/services/reportes.service";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import BaseTable from "@/components/ui/BaseTable.vue";
import BaseEmpty from "@/components/ui/BaseEmpty.vue";
import { ArrowLeftIcon, DocumentChartBarIcon } from "@heroicons/vue/24/outline";

const router = useRouter();
const empresaStore = useEmpresaStore();
const { showError } = useNotification();
const { formatearFecha, formatearMoneda, formatearCUIT } = useFormatters();

const loading = ref(false);
const reporte = ref<ReporteIVA | null>(null);
let generarReporteRequestId = 0;

// Período por defecto: mes actual
const hoy = new Date();
const mesActual = ref((hoy.getMonth() + 1).toString());
const anioActual = ref(hoy.getFullYear().toString());

const meses = [
  { value: "1", label: "Enero" },
  { value: "2", label: "Febrero" },
  { value: "3", label: "Marzo" },
  { value: "4", label: "Abril" },
  { value: "5", label: "Mayo" },
  { value: "6", label: "Junio" },
  { value: "7", label: "Julio" },
  { value: "8", label: "Agosto" },
  { value: "9", label: "Septiembre" },
  { value: "10", label: "Octubre" },
  { value: "11", label: "Noviembre" },
  { value: "12", label: "Diciembre" },
];

const anios = computed(() => {
  const anioInicio = 2020;
  const anioFin = hoy.getFullYear() + 1;
  const lista = [];
  for (let i = anioFin; i >= anioInicio; i--) {
    lista.push({ value: i.toString(), label: i.toString() });
  }
  return lista;
});

const columns = [
  { key: "fecha_emision", label: "Fecha", sortable: false },
  { key: "tipo", label: "Tipo", sortable: false },
  { key: "numero", label: "Número", sortable: false },
  { key: "cuit_receptor", label: "CUIT", sortable: false },
  { key: "razon_social_receptor", label: "Razón Social", sortable: false },
  { key: "gravado_21", label: "Gravado 21%", sortable: false },
  { key: "iva_21", label: "IVA 21%", sortable: false },
  { key: "gravado_10_5", label: "Gravado 10.5%", sortable: false },
  { key: "iva_10_5", label: "IVA 10.5%", sortable: false },
  { key: "gravado_27", label: "Gravado 27%", sortable: false },
  { key: "iva_27", label: "IVA 27%", sortable: false },
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

  if (!mesActual.value || !anioActual.value) {
    showError("Error", "Debe seleccionar mes y año");
    return;
  }

  loading.value = true;
  try {
    const resultado = await reportesService.obtenerReporteIVA(
      parseInt(mesActual.value),
      parseInt(anioActual.value),
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

const resumenIVA = computed(() => {
  if (!reporte.value) return [];

  const items = [];

  if (
    reporte.value.resumen.gravado_21 > 0 ||
    reporte.value.resumen.iva_21 > 0
  ) {
    items.push({
      label: "IVA 21%",
      gravado: formatearMoneda(reporte.value.resumen.gravado_21),
      iva: formatearMoneda(reporte.value.resumen.iva_21),
      color: "text-brand-flow",
      bg: "bg-brand-mint",
    });
  }

  if (
    reporte.value.resumen.gravado_10_5 > 0 ||
    reporte.value.resumen.iva_10_5 > 0
  ) {
    items.push({
      label: "IVA 10.5%",
      gravado: formatearMoneda(reporte.value.resumen.gravado_10_5),
      iva: formatearMoneda(reporte.value.resumen.iva_10_5),
      color: "text-status-success",
      bg: "bg-emerald-50",
    });
  }

  if (
    reporte.value.resumen.gravado_27 > 0 ||
    reporte.value.resumen.iva_27 > 0
  ) {
    items.push({
      label: "IVA 27%",
      gravado: formatearMoneda(reporte.value.resumen.gravado_27),
      iva: formatearMoneda(reporte.value.resumen.iva_27),
      color: "text-brand-teal",
      bg: "bg-surface-page",
    });
  }

  return items;
});

const resumenTotales = computed(() => {
  if (!reporte.value) return [];

  return [
    {
      label: "Total IVA",
      valor: formatearMoneda(reporte.value.resumen.total_iva),
      color: "text-status-warning",
      bg: "bg-amber-50",
    },
    {
      label: "Total Neto",
      valor: formatearMoneda(reporte.value.resumen.total_neto),
      color: "text-brand-flow",
      bg: "bg-brand-mint",
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
            Subdiario de IVA Ventas
          </h1>
          <p class="mt-1 text-brand-slate">
            Detalle de comprobantes por alícuotas de IVA
          </p>
        </div>
      </div>
    </div>

    <!-- Filtros -->
    <BaseCard class="mb-6">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-4">
        <BaseSelect
          v-model="mesActual"
          :options="meses"
          label="Mes"
          required
        />
        <BaseSelect
          v-model="anioActual"
          :options="anios"
          label="Año"
          required
        />
        <div class="md:col-span-2 flex items-end">
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
      <!-- Período -->
      <div class="mb-4">
        <BaseCard :padding="false">
          <div class="border-b border-border-subtle bg-surface-page p-4">
            <p class="text-lg font-semibold text-brand-ink">
              {{ reporte.resumen.periodo.nombre }}
            </p>
          </div>
        </BaseCard>
      </div>

      <!-- Resumen por Alícuota -->
      <div class="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <BaseCard
          v-for="item in resumenIVA"
          :key="item.label"
          :padding="false"
        >
          <div class="p-6">
            <p class="mb-4 text-sm font-medium text-brand-slate">
              {{ item.label }}
            </p>
            <div class="space-y-2">
              <div class="flex justify-between">
                <span class="text-sm text-brand-slate">Gravado:</span>
                <span :class="['font-semibold', item.color]">{{
                  item.gravado
                }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-sm text-brand-slate">IVA:</span>
                <span :class="['font-semibold', item.color]">{{
                  item.iva
                }}</span>
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Totales -->
      <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <BaseCard
          v-for="total in resumenTotales"
          :key="total.label"
          :padding="false"
        >
          <div class="p-6">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-medium text-brand-slate">
                  {{ total.label }}
                </p>
                <p :class="['mt-2 text-3xl font-bold', total.color]">
                  {{ total.valor }}
                </p>
              </div>
              <div :class="['rounded-panel p-3', total.bg]">
                <DocumentChartBarIcon :class="['h-6 w-6', total.color]" />
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Tabla de Comprobantes -->
      <BaseCard>
        <h2 class="mb-4 text-lg font-semibold text-brand-ink">
          Detalle de Comprobantes
        </h2>

        <div class="overflow-x-auto">
          <BaseTable
            v-if="reporte.comprobantes.length > 0"
            :columns="columns"
            :data="reporte.comprobantes"
            :loading="false"
          >
            <template #cell-fecha_emision="{ value }">
              <span class="text-sm text-brand-ink">{{
                formatearFecha(value)
              }}</span>
            </template>

            <template #cell-tipo="{ row }">
              <div class="text-sm">
                <span class="text-brand-ink">{{ row.tipo_nombre }}</span>
              </div>
            </template>

            <template #cell-numero="{ row }">
              <span class="font-mono text-xs">{{ row.numero_completo }}</span>
            </template>

            <template #cell-cuit_receptor="{ value }">
              <span class="font-mono text-xs text-brand-slate">{{
                formatearCUIT(value)
              }}</span>
            </template>

            <template #cell-razon_social_receptor="{ value }">
              <span class="text-sm text-brand-ink">{{ value }}</span>
            </template>

            <template #cell-gravado_21="{ value }">
              <span class="text-sm text-brand-ink">{{
                value > 0 ? formatearMoneda(value) : "-"
              }}</span>
            </template>

            <template #cell-iva_21="{ value }">
              <span class="text-sm font-medium text-brand-ink">
                {{ value > 0 ? formatearMoneda(value) : "-" }}
              </span>
            </template>

            <template #cell-gravado_10_5="{ value }">
              <span class="text-sm text-brand-ink">{{
                value > 0 ? formatearMoneda(value) : "-"
              }}</span>
            </template>

            <template #cell-iva_10_5="{ value }">
              <span class="text-sm font-medium text-brand-ink">
                {{ value > 0 ? formatearMoneda(value) : "-" }}
              </span>
            </template>

            <template #cell-gravado_27="{ value }">
              <span class="text-sm text-brand-ink">{{
                value > 0 ? formatearMoneda(value) : "-"
              }}</span>
            </template>

            <template #cell-iva_27="{ value }">
              <span class="text-sm font-medium text-brand-ink">
                {{ value > 0 ? formatearMoneda(value) : "-" }}
              </span>
            </template>

            <template #cell-total="{ value }">
              <span class="font-semibold text-brand-ink">{{
                formatearMoneda(value)
              }}</span>
            </template>
          </BaseTable>

          <BaseEmpty
            v-else
            title="Sin comprobantes"
            message="No hay comprobantes en el período seleccionado"
          />
        </div>
      </BaseCard>
    </template>

    <!-- Estado inicial -->
    <BaseEmpty
      v-else
      :icon="DocumentChartBarIcon"
      title="No hay datos"
      message="Seleccioná mes y año y hacé clic en &quot;Generar Reporte&quot; para ver los resultados"
    />
  </div>
</template>
