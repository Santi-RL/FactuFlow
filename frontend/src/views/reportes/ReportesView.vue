<template>
  <div class="reportes-view">
    <div class="mb-6">
      <h1
        class="text-3xl font-bold text-gray-800"
        data-testid="page-title"
      >
        📊 Reportes
      </h1>
      <p class="text-gray-600 mt-2">
        Consulta reportes de ventas, IVA y clientes
      </p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <!-- Reporte de Ventas -->
      <div 
        class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer"
        @click="irAReporteVentas"
      >
        <div class="flex items-start mb-4">
          <div class="bg-blue-100 rounded-lg p-3">
            <svg
              class="w-8 h-8 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          </div>
        </div>
        
        <h2 class="text-xl font-bold text-gray-800 mb-2">
          Ventas por Período
        </h2>
        <p class="text-gray-600 mb-4">
          Ver ventas y totales del período elegido. Incluye facturas, notas de crédito y débito.
        </p>
        
        <div class="flex items-center text-blue-600 font-medium">
          Ver reporte
          <svg
            class="w-4 h-4 ml-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5l7 7-7 7"
            />
          </svg>
        </div>
      </div>

      <!-- Subdiario IVA Ventas -->
      <div 
        class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer"
        @click="irAReporteIVA"
      >
        <div class="flex items-start mb-4">
          <div class="bg-green-100 rounded-lg p-3">
            <svg
              class="w-8 h-8 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
        </div>
        
        <h2 class="text-xl font-bold text-gray-800 mb-2">
          Subdiario IVA Ventas
        </h2>
        <p class="text-gray-600 mb-4">
          Para tu declaración jurada mensual. Detalle de IVA discriminado por alícuota.
        </p>
        
        <div class="flex items-center text-green-600 font-medium">
          Ver reporte
          <svg
            class="w-4 h-4 ml-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5l7 7-7 7"
            />
          </svg>
        </div>
      </div>

      <!-- Ranking de Clientes -->
      <div 
        class="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer"
        @click="irARankingClientes"
      >
        <div class="flex items-start mb-4">
          <div class="bg-purple-100 rounded-lg p-3">
            <svg
              class="w-8 h-8 text-purple-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
          </div>
        </div>
        
        <h2 class="text-xl font-bold text-gray-800 mb-2">
          Ranking de Clientes
        </h2>
        <p class="text-gray-600 mb-4">
          Clientes con mayor facturación en el período seleccionado.
        </p>
        
        <div class="flex items-center text-purple-600 font-medium">
          Ver reporte
          <svg
            class="w-4 h-4 ml-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5l7 7-7 7"
            />
          </svg>
        </div>
      </div>
    </div>

    <!-- Información adicional -->
    <div class="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div class="flex items-start">
        <svg
          class="w-5 h-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div>
          <h3 class="font-semibold text-blue-900 mb-1">
            Información sobre reportes
          </h3>
          <p class="text-blue-800 text-sm">
            Los reportes solo incluyen comprobantes autorizados por ARCA. Los comprobantes en estado borrador o pendiente no se contabilizan.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const irAReporteVentas = () => {
  router.push({ name: 'reporte-ventas' })
}

const irAReporteIVA = () => {
  router.push({ name: 'reporte-iva' })
}

const irARankingClientes = () => {
  router.push({ name: 'reporte-clientes' })
}
</script>

<style scoped>
/* Estilos adicionales si son necesarios */
</style>
