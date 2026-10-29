<script setup lang="ts">
import type { LecturaHistorica } from "@/types/comprobante";
import { formatearFecha } from "@/composables/useFormatters";

defineProps<{ lectura?: LecturaHistorica; detalle?: boolean }>();
const avisos = {
  completa: "Datos originales conservados",
  incompleta: "Datos originales incompletos",
  ausente: "Sin snapshot histórico",
  no_verificable: "Datos históricos no verificados",
};
</script>

<template>
  <div
    v-if="lectura"
    class="text-xs font-sans font-normal whitespace-normal"
  >
    <p
      v-if="detalle || lectura.cobertura !== 'completa'"
      :class="
        lectura.cobertura === 'no_verificable'
          ? 'text-amber-800'
          : 'text-gray-600'
      "
    >
      {{ avisos[lectura.cobertura]
      }}<span v-if="lectura.origen === 'ficha_actual'">
        · Datos de ficha actual</span>
    </p>
    <template v-if="detalle">
      <p
        v-if="lectura.cobertura === 'no_verificable'"
        class="text-amber-800 mt-1"
      >
        El PDF no está disponible; consultá al responsable de la instalación.
      </p>
      <dl class="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
        <div>
          <dt class="inline font-medium">
            Emisor:
          </dt>
          <dd class="inline">
            {{ lectura.emisor.razon_social || "No informado" }}
          </dd>
        </div>
        <div>
          <dt class="inline font-medium">
            CUIT:
          </dt>
          <dd class="inline">
            {{ lectura.emisor.cuit || "No informado" }}
          </dd>
        </div>
        <div>
          <dt class="inline font-medium">
            Domicilio:
          </dt>
          <dd class="inline">
            {{ lectura.emisor.domicilio || "No informado" }}
          </dd>
        </div>
        <div>
          <dt class="inline font-medium">
            Localidad:
          </dt>
          <dd class="inline">
            {{ lectura.emisor.localidad || "No informada" }} ·
            {{ lectura.emisor.provincia || "Provincia no informada" }}
          </dd>
        </div>
        <div>
          <dt class="inline font-medium">
            Condición IVA:
          </dt>
          <dd class="inline">
            {{ lectura.emisor.condicion_iva || "No informada" }}
          </dd>
        </div>
        <div>
          <dt class="inline font-medium">
            Ingresos brutos:
          </dt>
          <dd class="inline">
            {{ lectura.emisor.ingresos_brutos || "No informados" }}
          </dd>
        </div>
        <div>
          <dt class="inline font-medium">
            Inicio de actividades:
          </dt>
          <dd class="inline">
            {{
              lectura.emisor.inicio_actividades
                ? formatearFecha(lectura.emisor.inicio_actividades)
                : "No informado"
            }}
          </dd>
        </div>
      </dl>
    </template>
  </div>
</template>
