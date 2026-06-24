<template>
  <div>
    <div class="mb-6">
      <h1
        class="text-3xl font-bold text-brand-ink"
        data-testid="page-title"
      >
        Reportes
      </h1>
      <p class="mt-2 text-brand-slate">
        Consultá reportes de ventas, IVA y clientes
      </p>
    </div>

    <div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      <!-- Reporte de Ventas -->
      <router-link
        :to="{ name: 'reporte-ventas' }"
        class="group rounded-panel border border-border-subtle bg-surface-card p-6 text-left shadow-panel transition-all hover:-translate-y-0.5 hover:border-brand-flow hover:shadow-overlay focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
      >
        <div class="mb-4 flex items-start">
          <div class="rounded-panel bg-brand-mint p-3">
            <ChartBarIcon class="h-8 w-8 text-brand-teal" />
          </div>
        </div>

        <h2 class="mb-2 text-xl font-bold text-brand-ink">
          Ventas por Período
        </h2>
        <p class="mb-4 text-brand-slate">
          Ver ventas y totales del período elegido. Incluye facturas, notas de
          crédito y débito.
        </p>

        <div
          class="flex items-center font-medium text-brand-flow transition-colors group-hover:text-brand-teal"
        >
          Ver reporte
          <ArrowRightIcon class="ml-2 h-4 w-4" />
        </div>
      </router-link>

      <!-- Subdiario IVA Ventas -->
      <router-link
        :to="{ name: 'reporte-iva' }"
        class="group rounded-panel border border-border-subtle bg-surface-card p-6 text-left shadow-panel transition-all hover:-translate-y-0.5 hover:border-brand-flow hover:shadow-overlay focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
      >
        <div class="mb-4 flex items-start">
          <div class="rounded-panel bg-status-success-soft p-3">
            <DocumentTextIcon class="h-8 w-8 text-status-success" />
          </div>
        </div>

        <h2 class="mb-2 text-xl font-bold text-brand-ink">
          Subdiario IVA Ventas
        </h2>
        <p class="mb-4 text-brand-slate">
          Para tu declaración jurada mensual. Detalle de IVA discriminado por
          alícuota.
        </p>

        <div
          class="flex items-center font-medium text-status-success transition-opacity group-hover:opacity-80"
        >
          Ver reporte
          <ArrowRightIcon class="ml-2 h-4 w-4" />
        </div>
      </router-link>

      <!-- Ranking de Clientes -->
      <router-link
        :to="{ name: 'reporte-clientes' }"
        class="group rounded-panel border border-border-subtle bg-surface-card p-6 text-left shadow-panel transition-all hover:-translate-y-0.5 hover:border-brand-flow hover:shadow-overlay focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
      >
        <div class="mb-4 flex items-start">
          <div class="rounded-panel bg-surface-page p-3">
            <UsersIcon class="h-8 w-8 text-brand-flow" />
          </div>
        </div>

        <h2 class="mb-2 text-xl font-bold text-brand-ink">
          Ranking de Clientes
        </h2>
        <p class="mb-4 text-brand-slate">
          Clientes con mayor facturación en el período seleccionado.
        </p>

        <div
          class="flex items-center font-medium text-brand-flow transition-colors group-hover:text-brand-teal"
        >
          Ver reporte
          <ArrowRightIcon class="ml-2 h-4 w-4" />
        </div>
      </router-link>
    </div>

    <!-- Información adicional -->
    <div class="mt-8 rounded-panel border border-border-subtle bg-brand-mint p-4">
      <div class="flex items-start">
        <InformationCircleIcon
          class="mr-3 mt-0.5 h-5 w-5 flex-shrink-0 text-brand-teal"
        />
        <div>
          <h3 class="mb-1 font-semibold text-brand-ink">
            Información sobre reportes
          </h3>
          <p class="text-sm text-brand-slate">
            Los reportes solo incluyen comprobantes autorizados por ARCA. Los
            comprobantes en estado borrador o pendiente no se contabilizan.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  ArrowRightIcon,
  ChartBarIcon,
  DocumentTextIcon,
  InformationCircleIcon,
  UsersIcon,
} from "@heroicons/vue/24/outline";
</script>
