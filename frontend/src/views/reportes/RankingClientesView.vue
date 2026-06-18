<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useEmpresaStore } from "@/stores/empresa";
import { useNotification } from "@/composables/useNotification";
import { useFormatters } from "@/composables/useFormatters";
import reportesService from "@/services/reportes.service";
import type { ReporteClientes } from "@/services/reportes.service";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import BaseSpinner from "@/components/ui/BaseSpinner.vue";
import BaseEmpty from "@/components/ui/BaseEmpty.vue";
import BaseBadge from "@/components/ui/BaseBadge.vue";
import {
  ArrowLeftIcon,
  DocumentChartBarIcon,
  TrophyIcon,
  UserIcon,
} from "@heroicons/vue/24/outline";

const router = useRouter();
const empresaStore = useEmpresaStore();
const { showError } = useNotification();
const { formatearFecha, formatearMoneda, formatearCUIT } = useFormatters();

const loading = ref(false);
const reporte = ref<ReporteClientes | null>(null);
let generarReporteRequestId = 0;

// Fechas por defecto: mes actual
const hoy = new Date();
const primerDiaMes = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
const ultimoDiaMes = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0);

const desde = ref(primerDiaMes.toISOString().split("T")[0]);
const hasta = ref(ultimoDiaMes.toISOString().split("T")[0]);
const limite = ref("10");

const limitesDisponibles = [
  { value: "5", label: "Top 5" },
  { value: "10", label: "Top 10" },
  { value: "20", label: "Top 20" },
  { value: "50", label: "Top 50" },
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
    const resultado = await reportesService.obtenerRankingClientes(
      desde.value,
      hasta.value,
      parseInt(limite.value),
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

const obtenerMedalla = (posicion: number) => {
  if (posicion === 1)
    return { color: "text-status-warning", label: "1° Puesto" };
  if (posicion === 2)
    return { color: "text-brand-flow", label: "2° Puesto" };
  if (posicion === 3)
    return { color: "text-brand-teal", label: "3° Puesto" };
  return { color: "text-brand-slate", label: `${posicion}° Puesto` };
};

const obtenerColorCard = (posicion: number) => {
  if (posicion === 1) return "border-status-warning bg-amber-50";
  if (posicion === 2) return "border-brand-flow bg-brand-mint";
  if (posicion === 3) return "border-brand-teal bg-surface-page";
  return "border-border-subtle bg-surface-card";
};

const clientesConPosicion = computed(() => {
  if (!reporte.value) return [];
  return reporte.value.clientes.map((cliente, index) => ({
    ...cliente,
    posicion: index + 1,
  }));
});

const totalGeneral = computed(() => {
  if (!reporte.value) return 0;
  return reporte.value.clientes.reduce(
    (sum, cliente) => sum + cliente.total_facturado,
    0,
  );
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
            Ranking de Clientes
          </h1>
          <p class="mt-1 text-brand-slate">
            Clientes con mayor facturación en el período
          </p>
        </div>
      </div>
    </div>

    <!-- Filtros -->
    <BaseCard class="mb-6">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-4">
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
        <BaseSelect
          v-model="limite"
          :options="limitesDisponibles"
          label="Límite"
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
    <template v-else-if="reporte && reporte.clientes.length > 0">
      <!-- Período -->
      <div class="mb-6">
        <BaseCard :padding="false">
          <div class="bg-surface-page p-4">
            <div
              class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
            >
              <p class="text-sm text-brand-slate">
                <span class="font-medium">Período:</span>
                {{ formatearFecha(reporte.periodo.desde) }} -
                {{ formatearFecha(reporte.periodo.hasta) }}
              </p>
              <p class="text-sm text-brand-slate">
                <span class="font-medium">Total facturado:</span>
                <span class="ml-2 text-lg font-bold text-brand-flow">
                  {{ formatearMoneda(totalGeneral) }}
                </span>
              </p>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Top 3 destacado (móvil y desktop) -->
      <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <BaseCard
          v-for="cliente in clientesConPosicion.slice(0, 3)"
          :key="cliente.cliente_id"
          :padding="false"
          :class="['border-2', obtenerColorCard(cliente.posicion)]"
        >
          <div class="p-6">
            <!-- Medalla y posición -->
            <div class="mb-4 flex items-center justify-between">
              <div class="flex items-center gap-2">
                <TrophyIcon
                  :class="['h-6 w-6', obtenerMedalla(cliente.posicion).color]"
                />
              </div>
              <BaseBadge
                :variant="
                  cliente.posicion === 1
                    ? 'warning'
                    : cliente.posicion === 2
                      ? 'default'
                      : 'info'
                "
              >
                {{ obtenerMedalla(cliente.posicion).label }}
              </BaseBadge>
            </div>

            <!-- Info del cliente -->
            <div class="mb-4">
              <h3 class="mb-1 truncate text-lg font-bold text-brand-ink">
                {{ cliente.razon_social }}
              </h3>
              <p class="font-mono text-sm text-brand-slate">
                {{ formatearCUIT(cliente.numero_documento) }}
              </p>
            </div>

            <!-- Estadísticas -->
            <div class="space-y-2">
              <div
                class="flex items-center justify-between rounded-control bg-surface-card p-2"
              >
                <span class="text-sm text-brand-slate">Total facturado</span>
                <span
                  :class="[
                    'font-bold text-lg',
                    obtenerMedalla(cliente.posicion).color,
                  ]"
                >
                  {{ formatearMoneda(cliente.total_facturado) }}
                </span>
              </div>
              <div
                class="flex items-center justify-between rounded-control bg-surface-card p-2"
              >
                <span class="text-sm text-brand-slate">Comprobantes</span>
                <span class="font-semibold text-brand-ink">
                  {{ cliente.cantidad_comprobantes }}
                </span>
              </div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Resto del ranking (si hay más de 3) -->
      <BaseCard v-if="clientesConPosicion.length > 3">
        <h2 class="mb-4 text-lg font-semibold text-brand-ink">
          Resto del Ranking
        </h2>

        <div class="space-y-3">
          <div
            v-for="cliente in clientesConPosicion.slice(3)"
            :key="cliente.cliente_id"
            class="flex items-center justify-between rounded-panel border border-border-subtle p-4 transition-colors hover:bg-brand-mint"
          >
            <div class="flex min-w-0 flex-1 items-center gap-4">
              <!-- Posición -->
              <div
                class="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-control bg-surface-page"
              >
                <span class="text-lg font-bold text-brand-slate">{{
                  cliente.posicion
                }}</span>
              </div>

              <!-- Info cliente -->
              <div class="min-w-0 flex-1">
                <h4 class="truncate font-semibold text-brand-ink">
                  {{ cliente.razon_social }}
                </h4>
                <p class="font-mono text-sm text-brand-slate">
                  {{ formatearCUIT(cliente.numero_documento) }}
                </p>
              </div>

              <!-- Estadísticas (visible en desktop) -->
              <div class="hidden items-center gap-6 md:flex">
                <div class="text-right">
                  <p class="text-sm text-brand-slate">
                    Comprobantes
                  </p>
                  <p class="font-semibold text-brand-ink">
                    {{ cliente.cantidad_comprobantes }}
                  </p>
                </div>
                <div class="text-right">
                  <p class="text-sm text-brand-slate">
                    Total
                  </p>
                  <p class="text-lg font-bold text-brand-flow">
                    {{ formatearMoneda(cliente.total_facturado) }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Estadísticas (visible en móvil) -->
            <div class="flex flex-col items-end gap-1 md:hidden">
              <p class="font-bold text-brand-flow">
                {{ formatearMoneda(cliente.total_facturado) }}
              </p>
              <p class="text-sm text-brand-slate">
                {{ cliente.cantidad_comprobantes }} docs
              </p>
            </div>
          </div>
        </div>
      </BaseCard>
    </template>

    <!-- Sin resultados -->
    <BaseEmpty
      v-else-if="reporte && reporte.clientes.length === 0"
      :icon="UserIcon"
      title="Sin clientes facturados"
      message="No hay clientes con facturación en el período seleccionado"
    />

    <!-- Estado inicial -->
    <BaseEmpty
      v-else
      :icon="DocumentChartBarIcon"
      title="No hay datos"
      message="Seleccioná un rango de fechas y hacé clic en &quot;Generar Reporte&quot; para ver los resultados"
    />
  </div>
</template>
