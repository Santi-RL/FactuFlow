<script setup lang="ts">
import { computed } from "vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import type {
  RecoveryCheckResponse,
  RecoveryComponentName,
  RecoveryHealthResponse,
} from "@/services/sistema.service";
import { formatearFechaHoraArgentina } from "@/utils/instantes";

const props = defineProps<{ evidence: RecoveryHealthResponse | null }>();
const componentNames: Record<RecoveryComponentName, string> = {
  database: "Base de datos",
  certificates: "Certificados y claves",
  configuration: "Configuración",
  runtime: "Aplicación ejecutable",
};
const purposeNames = {
  pre_update: "Previo a una actualización",
  pre_maintenance: "Previo a mantenimiento",
  pre_resolution: "Previo a una recuperación",
  manual: "Respaldo manual",
};
const components = computed(() =>
  (Object.keys(componentNames) as RecoveryComponentName[]).map((name) => ({
    name: componentNames[name],
    state:
      props.evidence?.components.find((item) => item.name === name)?.state ??
      "unknown",
  })),
);
const dateLabel = (value: string | null) =>
  value ? formatearFechaHoraArgentina(value) : "Fecha desconocida";
const checkLabel = (check: RecoveryCheckResponse) => {
  if (check.result === "not_verified") return "No verificado";
  const result = check.result === "verified" ? "Verificado" : "Falló";
  const scope = check.components.map((name) => componentNames[name]).join(", ");
  const precision =
    check.time_precision === "unknown"
      ? " · Precisión horaria desconocida"
      : check.time_precision === "minute"
        ? " · Precisión de un minuto"
        : "";
  return `${result} el ${dateLabel(check.checked_at)}${precision} · Alcance: ${scope}`;
};
const changeLabels = {
  changed: "Cambios detectados",
  not_detected: "Sin cambios detectados en ese cotejo",
  unknown: "No verificado",
};
</script>

<template>
  <BaseCard
    title="Evidencia de recuperación"
    data-testid="recovery-evidence"
  >
    <p class="text-sm text-gray-600 dark:text-gray-400">
      Respaldo de la instalación. La cobertura del estado actual no está
      verificada. Esta información no autoriza una restauración.
    </p>
    <dl
      v-if="evidence?.status === 'recorded'"
      class="mt-4 space-y-3 text-sm"
    >
      <div>
        <dt class="font-semibold">
          Respaldo registrado
        </dt>
        <dd>{{ evidence.backup_id }}</dd>
        <dd>
          {{
            evidence.purpose
              ? purposeNames[evidence.purpose]
              : "Propósito desconocido"
          }}
        </dd>
        <dd>Creado: {{ dateLabel(evidence.created_at) }}</dd>
        <dd>Punto respaldado: {{ dateLabel(evidence.captured_at) }}</dd>
      </div>
      <div>
        <dt class="font-semibold">
          Componentes del respaldo
        </dt>
        <dd
          v-for="item in components"
          :key="item.name"
        >
          {{ item.name }}:
          {{
            item.state === "present"
              ? "Incluido"
              : item.state === "missing"
                ? "Ausente"
                : "No verificado"
          }}
        </dd>
      </div>
      <div>
        <dt class="font-semibold">
          Integridad registrada
        </dt>
        <dd>{{ checkLabel(evidence.integrity) }}</dd>
      </div>
      <div>
        <dt class="font-semibold">
          Ensayo de recuperación registrado
        </dt>
        <dd>{{ checkLabel(evidence.restore) }}</dd>
      </div>
      <div v-if="evidence.comparison">
        <dt class="font-semibold">
          Último cotejo: {{ dateLabel(evidence.comparison.observed_at) }}
        </dt>
        <dd>Base de datos: {{ changeLabels[evidence.comparison.database] }}</dd>
        <dd>
          Archivos gestionados:
          {{ changeLabels[evidence.comparison.managed_files] }}
        </dd>
        <dd>
          Configuración: {{ changeLabels[evidence.comparison.configuration] }}
        </dd>
        <dd>
          Actividad fiscal posterior:
          {{ changeLabels[evidence.comparison.fiscal_writes] }}
        </dd>
        <dd>
          Actividad administrativa posterior:
          {{ changeLabels[evidence.comparison.administrative_writes] }}
        </dd>
      </div>
      <div v-else>
        <dt class="font-semibold">
          Escrituras posteriores
        </dt>
        <dd>No verificado: no hay un cotejo registrado.</dd>
      </div>
      <div>
        <dt class="font-semibold">
          Copia fuera del servidor registrada
        </dt>
        <dd>{{ checkLabel(evidence.external_copy) }}</dd>
      </div>
    </dl>
    <p
      v-else
      class="mt-4 text-sm"
    >
      No verificado: no hay evidencia utilizable.
    </p>
    <p class="mt-4 text-sm">
      Antes de recuperar o actualizar, soporte debe verificar un respaldo
      apropiado para esa operación y revisar las escrituras posteriores. Si pudo
      haber una autorización de ARCA, conservar su evidencia y reconciliar antes
      de reintentar.
    </p>
  </BaseCard>
</template>
