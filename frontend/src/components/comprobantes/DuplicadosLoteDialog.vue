<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import type {
  ControlDuplicadosLote,
  DuplicadosAntecedenteResumen,
  DuplicadosCoincidenciasPage,
  DuplicadosImportes,
  DuplicadosSolicitante,
} from "@/types/lote-comprobante";

const props = withDefaults(
  defineProps<{
    show: boolean;
    control: ControlDuplicadosLote | null;
    acceptanceAvailable?: boolean;
    loading?: boolean;
    details?: DuplicadosCoincidenciasPage | null;
    detailsLoading?: boolean;
  }>(),
  {
    acceptanceAvailable: false,
    loading: false,
    details: null,
    detailsLoading: false,
  },
);

const emit = defineEmits<{
  review: [];
  accept: [];
  requestDetails: [page: number];
}>();

const dialogRef = ref<HTMLElement | null>(null);
const reviewRef = ref<HTMLButtonElement | null>(null);
const detailsTriggerRef = ref<HTMLButtonElement | null>(null);
const priorTriggerRefs = ref<Record<string, HTMLButtonElement | null>>({});
const panelHeadingRef = ref<HTMLElement | null>(null);
const checked = ref(false);
const panel = ref<"summary" | "details" | "prior">("summary");
const prior = ref<DuplicadosAntecedenteResumen | null>(null);
const returnTarget = ref<"details" | string | null>(null);
let previousFocus: HTMLElement | null = null;

const historical = computed(() => props.control?.antecedentes_resumen ?? []);
const hasInternal = computed(() =>
  props.control?.tipos_coincidencia.includes("interna_receptor"),
);
const hasComplete = computed(() =>
  props.control?.tipos_coincidencia.includes("historica_completa"),
);
const hasPartial = computed(() =>
  props.control?.tipos_coincidencia.some((item) =>
    ["historica_parcial_receptor", "historica_individual_legacy"].includes(
      item,
    ),
  ),
);
const formatCount = (count: number, singular: string, plural: string) =>
  `${count} ${count === 1 ? singular : plural}`;
const formatComprobantes = (count: number) =>
  formatCount(count, "comprobante", "comprobantes");
const formatCoincidentes = (count: number) =>
  formatCount(count, "coincidente", "coincidentes");
const blocked = computed(
  () =>
    props.control?.estado === "operacion_en_curso" ||
    Boolean(props.control?.bloqueo_operacion_ajena),
);
const canAccept = computed(() =>
  Boolean(
    props.control?.aceptacion_requerida &&
    props.control.aceptacion_habilitada &&
    props.acceptanceAvailable &&
    !blocked.value,
  ),
);
const title = computed(() => {
  if (blocked.value) return "Hay otra emisión coincidente en curso";
  if (hasComplete.value) {
    const completeHistory = historical.value.filter(
      (item) => item.tipo_coincidencia === "historica_completa",
    );
    const fullyAuthorized =
      completeHistory.length > 0 &&
      completeHistory.every(
        (item) =>
          item.cantidad_lote_anterior !== null &&
          item.cantidad_autorizada === item.cantidad_lote_anterior &&
          item.cantidad_solo_validada === 0 &&
          item.cantidad_reservada_en_curso === 0 &&
          item.cantidad_fallida === 0 &&
          item.cantidad_incierta === 0,
      );
    return fullyAuthorized
      ? "Este lote coincide por completo con otro ya emitido"
      : "Este lote coincide por completo con el contenido de otro lote";
  }
  if (hasPartial.value) {
    const affected = props.control?.cantidad_afectada ?? 0;
    const current = props.control?.cantidad_actual ?? 0;
    return `${affected} de ${formatComprobantes(current)} ${affected === 1 ? "coincide" : "coinciden"}`;
  }
  if (hasInternal.value)
    return "Hay comprobantes del mismo receptor dentro del lote";
  return "Se encontraron coincidencias para revisar";
});
const checkboxText = computed(() => {
  const hasPriorLots = historical.value.some((item) => item.origen === "lote");
  const hasPriorIndividuals = historical.value.some(
    (item) => item.origen === "comprobante_individual",
  );
  const priorLotsCount = historical.value.filter(
    (item) => item.origen === "lote",
  ).length;
  const priorIndividualsCount = historical.value.filter(
    (item) => item.origen === "comprobante_individual",
  ).length;

  if (hasInternal.value && !hasPriorLots && !hasPriorIndividuals) {
    return "Confirmo que los comprobantes señalados corresponden a operaciones distintas";
  }
  if (!hasInternal.value && !hasPriorLots && hasPriorIndividuals) {
    return priorIndividualsCount > 1
      ? "Confirmo que estos comprobantes corresponden a operaciones nuevas, distintas de las de los comprobantes anteriores"
      : "Confirmo que estos comprobantes corresponden a operaciones nuevas, distintas de la del comprobante anterior";
  }
  if (!hasInternal.value && hasPriorLots && !hasPriorIndividuals) {
    return priorLotsCount > 1
      ? "Confirmo que estos comprobantes corresponden a operaciones nuevas, distintas de las de los lotes anteriores"
      : "Confirmo que estos comprobantes corresponden a operaciones nuevas, distintas de las del lote anterior";
  }

  const clauses: string[] = [];
  if (hasInternal.value) {
    clauses.push(
      "los comprobantes señalados corresponden a operaciones distintas",
    );
  }
  if (hasPriorLots) {
    clauses.push(
      priorLotsCount > 1
        ? "estos comprobantes corresponden a operaciones nuevas, distintas de las de los lotes anteriores"
        : "estos comprobantes corresponden a operaciones nuevas, distintas de las del lote anterior",
    );
  }
  if (hasPriorIndividuals) {
    clauses.push(
      priorIndividualsCount > 1
        ? "estos comprobantes corresponden a operaciones nuevas, distintas de las de los comprobantes anteriores"
        : "estos comprobantes corresponden a operaciones nuevas, distintas de la del comprobante anterior",
    );
  }
  if (clauses.length === 0) {
    return "Confirmo que estos comprobantes corresponden a operaciones nuevas, distintas de las del lote anterior";
  }
  if (clauses.length === 1) return `Confirmo que ${clauses[0]}`;
  return `Confirmo que ${clauses.slice(0, -1).join("; que ")}; y que ${clauses[clauses.length - 1]}`;
});

const formatAmount = (value: string | null | undefined) => {
  const match = (value ?? "").match(/^(-?)(\d+)\.(\d{2})$/);
  if (!match) return "importe no disponible";
  const [, sign, integer, decimals] = match;
  return `${sign}${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".")},${decimals}`;
};

const parseIsoParts = (value: string) => {
  const match = value.match(
    /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?(Z|[+-]\d{2}:\d{2})?$/,
  );
  if (!match) return null;
  const [
    ,
    yearRaw,
    monthRaw,
    dayRaw,
    hourRaw = "00",
    minuteRaw = "00",
    secondRaw = "00",
    zone,
  ] = match;
  const hasTime = Boolean(match[4]);
  const year = Number(yearRaw);
  const month = Number(monthRaw);
  const day = Number(dayRaw);
  const hour = Number(hourRaw);
  const minute = Number(minuteRaw);
  const second = Number(secondRaw);
  const check = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
  if (
    check.getUTCFullYear() !== year ||
    check.getUTCMonth() !== month - 1 ||
    check.getUTCDate() !== day ||
    check.getUTCHours() !== hour ||
    check.getUTCMinutes() !== minute ||
    check.getUTCSeconds() !== second
  ) {
    return null;
  }
  if (zone && !hasTime) return null;
  if (zone && zone !== "Z") {
    const [offsetHour, offsetMinute] = zone.slice(1).split(":").map(Number);
    if (offsetHour > 23 || offsetMinute > 59) return null;
  }
  return {
    dayRaw,
    monthRaw,
    yearRaw,
    hourRaw,
    minuteRaw,
    zone: zone || null,
    hasTime,
  };
};

const formatDateTime = (value: string | null, reliable: boolean | null) => {
  if (!value) return "Fecha y hora no registradas";
  const parts = parseIsoParts(value);
  if (!parts) return "Fecha y hora históricas no comprobables";
  if (!parts.hasTime) {
    return `${parts.dayRaw}/${parts.monthRaw}/${parts.yearRaw} (hora no registrada)`;
  }
  if (reliable === false) {
    return `${parts.dayRaw}/${parts.monthRaw}/${parts.yearRaw} (hora histórica no comprobable)`;
  }
  if (!parts.zone) {
    return `${parts.dayRaw}/${parts.monthRaw}/${parts.yearRaw} ${parts.hourRaw}:${parts.minuteRaw} (zona horaria no registrada)`;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Fecha y hora históricas no comprobables";
  }
  const formatted = new Intl.DateTimeFormat("es-AR", {
    timeZone: "America/Argentina/Buenos_Aires",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
  return formatted;
};

const formatAmountWithCurrency = (value: string, currency: string | null) => {
  const amount = formatAmount(value);
  if (!currency) return `${amount} (moneda no registrada)`;
  if (currency === "PES") return `$ ${amount}`;
  if (currency === "DOL") return `US$ ${amount}`;
  return `${amount} ${currency}`;
};

const formatImportBreakdown = (
  value: DuplicadosImportes | null | undefined,
) => {
  if (!value) return "Importes con moneda no acreditada";
  const parts = value.por_moneda.map(
    (item) =>
      `${formatAmountWithCurrency(item.importe, item.moneda)} en ${item.cantidad} comprobante${item.cantidad === 1 ? "" : "s"}`,
  );
  if (value.cantidad_sin_moneda_acreditada > 0) {
    parts.push(
      `${value.cantidad_sin_moneda_acreditada} comprobante${value.cantidad_sin_moneda_acreditada === 1 ? "" : "s"} sin moneda acreditada`,
    );
  }
  return parts.length ? parts.join("; ") : "Sin importes afectados";
};

const resultSummary = (item: DuplicadosAntecedenteResumen) => {
  const parts = [
    formatCount(item.cantidad_autorizada, "autorizado", "autorizados"),
    formatCount(item.cantidad_solo_validada, "pendiente", "pendientes"),
    formatCount(item.cantidad_fallida, "fallido", "fallidos"),
    formatCount(item.cantidad_incierta, "incierto", "inciertos"),
  ];
  if (item.cantidad_reservada_en_curso > 0) {
    parts.splice(2, 0, `${item.cantidad_reservada_en_curso} en proceso`);
  }
  return parts.join(", ");
};

const emissionInterval = (item: DuplicadosAntecedenteResumen) => {
  const from = formatDateTime(item.emitido_desde, item.hora_confiable);
  if (!item.emitido_hasta || item.emitido_hasta === item.emitido_desde)
    return from;
  return `${from} a ${formatDateTime(item.emitido_hasta, item.hora_confiable)}`;
};

const fieldLabels: Record<string, string> = {
  nombre: "mismo nombre de receptor",
  documento: "mismo documento de receptor",
  contenido_completo: "mismo contenido contable completo",
  predicado_individual_vigente:
    "misma operación según el control individual vigente",
};

const actorNames = (actors: DuplicadosSolicitante[]) => {
  if (!actors.length) return "Usuario de emisión no registrado";
  return actors
    .map((actor) =>
      actor.estado === "registrado" && actor.nombre?.trim()
        ? actor.nombre.trim()
        : "Usuario de emisión no registrado",
    )
    .join(", ");
};

const focusReview = () => nextTick(() => reviewRef.value?.focus());

watch(
  () => props.show,
  (show) => {
    if (show) {
      previousFocus = document.activeElement as HTMLElement | null;
      checked.value = false;
      panel.value = "summary";
      prior.value = null;
      void focusReview();
    } else {
      const focusToRestore = previousFocus;
      previousFocus = null;
      void nextTick(() => {
        if (
          !props.show &&
          focusToRestore?.isConnected &&
          document.activeElement === document.body
        ) {
          focusToRestore.focus();
        }
      });
    }
  },
  { immediate: true },
);

watch(
  () => props.control?.evidencia_id,
  () => {
    checked.value = false;
    panel.value = "summary";
    prior.value = null;
    if (props.show) void focusReview();
  },
);

const review = () => emit("review");
const accept = () => {
  if (!canAccept.value || !checked.value || props.loading) return;
  emit("accept");
};

const openDetails = () => {
  returnTarget.value = "details";
  panel.value = "details";
  emit("requestDetails", 1);
  void nextTick(() => panelHeadingRef.value?.focus({ preventScroll: true }));
};

const setPriorTriggerRef = (
  key: string,
  element: Element | { $el?: Element } | null,
) => {
  priorTriggerRefs.value[key] =
    element instanceof HTMLButtonElement ? element : null;
};

const openPrior = (item: DuplicadosAntecedenteResumen) => {
  returnTarget.value = `prior-${item.lote_id}`;
  prior.value = item;
  panel.value = "prior";
  void nextTick(() => panelHeadingRef.value?.focus({ preventScroll: true }));
};

const returnToSummary = () => {
  panel.value = "summary";
  prior.value = null;
  void nextTick(() => {
    if (returnTarget.value === "details") {
      detailsTriggerRef.value?.focus();
    } else if (returnTarget.value) {
      priorTriggerRefs.value[returnTarget.value]?.focus();
    }
  });
};

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape") {
    event.preventDefault();
    review();
    return;
  }
  if (event.key === "Enter" && !(event.target instanceof HTMLButtonElement)) {
    event.preventDefault();
  }
  if (event.key !== "Tab" || !dialogRef.value) return;
  const focusable = Array.from(
    dialogRef.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  );
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement as HTMLElement | null;
  if (!active || !focusable.includes(active)) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
  } else if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
};
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show && control"
      class="fixed inset-0 z-50 overflow-y-auto bg-[rgba(16,20,24,0.72)] p-3 sm:p-6"
      @click.self="review"
    >
      <section
        ref="dialogRef"
        role="dialog"
        aria-modal="true"
        aria-labelledby="duplicados-dialog-title"
        aria-describedby="duplicados-dialog-description"
        class="mx-auto flex min-h-full max-w-3xl items-center justify-center"
        @keydown="onKeydown"
      >
        <div
          class="max-h-[calc(100vh-2rem)] w-full overflow-y-auto rounded-xl bg-white p-5 shadow-2xl sm:p-7"
        >
          <template v-if="panel === 'summary'">
            <p class="text-sm font-semibold text-amber-700">
              Revisión antes de emitir
            </p>
            <h2
              id="duplicados-dialog-title"
              class="mt-1 text-xl font-bold text-gray-900"
            >
              {{ title }}
            </h2>
            <p
              id="duplicados-dialog-description"
              class="mt-3 text-sm leading-6 text-gray-700"
            >
              <template v-if="blocked">
                Esperá el resultado de la otra operación antes de decidir. Esta
                situación no permite emitir como operaciones nuevas.
              </template>
              <template v-else-if="hasInternal && historical.length === 0">
                Revisá los comprobantes señalados: coinciden en receptor, fecha
                e importe dentro de este lote.
              </template>
              <template v-else>
                Continuar generará nuevos comprobantes; no reemplazará los
                anteriores.
              </template>
            </p>

            <div class="mt-5 grid gap-3 sm:grid-cols-2">
              <div class="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <p class="text-xs font-semibold uppercase text-gray-500">
                  Lote actual
                </p>
                <p class="mt-1 text-lg font-semibold text-gray-900">
                  {{ formatComprobantes(control.cantidad_actual) }}
                </p>
                <p class="text-sm text-gray-700">
                  {{ formatImportBreakdown(control.importes_actuales) }}
                </p>
              </div>
              <div class="rounded-lg border border-amber-200 bg-amber-50 p-4">
                <p class="text-xs font-semibold uppercase text-amber-700">
                  Coincidencias
                </p>
                <p class="mt-1 text-lg font-semibold text-gray-900">
                  {{ formatComprobantes(control.cantidad_afectada) }}
                </p>
                <p class="text-sm text-gray-700">
                  {{ formatImportBreakdown(control.importes_afectados) }}
                </p>
              </div>
            </div>

            <ul
              v-if="historical.length"
              class="mt-5 space-y-3"
            >
              <li
                v-for="item in historical"
                :key="`${item.origen}-${item.lote_id}-${item.comprobante_ref}`"
                class="rounded-lg border border-gray-200 p-4"
              >
                <p class="font-semibold text-gray-900">
                  <template v-if="item.origen === 'lote'">
                    Lote {{ item.lote_id
                    }}<span v-if="item.nombre_archivo">
                      · {{ item.nombre_archivo }}</span>
                  </template>
                  <template v-else>
                    Comprobante anterior {{ item.comprobante_ref }}
                  </template>
                </p>
                <p class="mt-1 text-sm text-gray-700">
                  {{ formatCoincidentes(item.cantidad_coincidente) }};
                  {{ formatImportBreakdown(item.importes_afectados) }}.
                  <template v-if="item.cantidad_lote_anterior !== null">
                    El lote anterior contiene
                    {{ formatComprobantes(item.cantidad_lote_anterior) }}<span
                      v-if="item.importes_lote_anterior"
                    >
                      con
                      {{
                        formatImportBreakdown(item.importes_lote_anterior)
                      }}</span>.
                  </template>
                </p>
                <p class="mt-1 text-sm text-gray-600">
                  Resultado conocido: {{ resultSummary(item) }}.
                </p>
                <p class="mt-1 text-sm text-gray-600">
                  Solicitud de emisión: {{ actorNames(item.solicitantes) }}.
                </p>
                <p class="text-sm text-gray-600">
                  Período de emisión registrado: {{ emissionInterval(item) }}.
                </p>
                <button
                  v-if="item.origen === 'lote'"
                  :ref="
                    (element) =>
                      setPriorTriggerRef(`prior-${item.lote_id}`, element)
                  "
                  type="button"
                  class="mt-3 text-sm font-semibold text-primary-700 underline-offset-2 hover:underline"
                  @click="openPrior(item)"
                >
                  Ver lote anterior
                </button>
              </li>
            </ul>

            <p
              v-if="blocked && control.bloqueo_operacion_ajena"
              class="mt-4 rounded-lg bg-gray-100 p-3 text-sm text-gray-700"
            >
              Referencia de seguimiento:
              {{ control.bloqueo_operacion_ajena.referencia }}.
            </p>

            <div class="mt-5 flex flex-wrap gap-3">
              <button
                v-if="control.detalle_url"
                ref="detailsTriggerRef"
                type="button"
                class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-800 hover:bg-gray-50"
                @click="openDetails"
              >
                Ver coincidencias
              </button>
            </div>

            <label
              v-if="canAccept"
              class="mt-6 flex cursor-pointer items-start gap-3 rounded-lg border border-gray-300 p-4 text-sm text-gray-800"
            >
              <input
                v-model="checked"
                type="checkbox"
                class="mt-0.5 h-5 w-5 rounded border-gray-400 text-primary-600"
              >
              <span>{{ checkboxText }}</span>
            </label>
            <p
              v-else-if="control.aceptacion_requerida && !blocked"
              class="mt-6 rounded-lg bg-blue-50 p-4 text-sm text-blue-900"
            >
              Volvé a revisar el lote y solicitá la emisión nuevamente para
              decidir sobre la evidencia actual.
            </p>

            <div
              class="sticky bottom-0 -mx-2 mt-7 flex flex-col-reverse gap-3 border-t border-gray-200 bg-white px-2 pt-4 sm:flex-row sm:justify-end"
            >
              <button
                ref="reviewRef"
                type="button"
                class="rounded-lg border border-primary-700 bg-primary-700 px-5 py-2.5 font-semibold text-white hover:bg-primary-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                @click="review"
              >
                Volver a revisar
              </button>
              <button
                v-if="canAccept"
                type="button"
                class="rounded-lg border border-gray-300 bg-white px-5 py-2.5 font-semibold text-gray-800 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="!checked || loading"
                @click="accept"
              >
                Emitir como operaciones nuevas
              </button>
            </div>
          </template>

          <template v-else-if="panel === 'prior' && prior">
            <h2
              id="duplicados-dialog-title"
              ref="panelHeadingRef"
              tabindex="-1"
              class="text-xl font-bold text-gray-900 outline-none"
            >
              Lote anterior {{ prior.lote_id }}
            </h2>
            <p
              id="duplicados-dialog-description"
              class="mt-2 text-sm text-gray-600"
            >
              Consulta del antecedente sin abandonar la preparación actual.
            </p>
            <dl
              class="mt-5 grid gap-4 rounded-lg border border-gray-200 p-4 sm:grid-cols-2"
            >
              <div>
                <dt class="text-xs font-semibold uppercase text-gray-500">
                  Archivo anterior
                </dt>
                <dd class="mt-1 text-sm text-gray-900">
                  {{ prior.nombre_archivo || "Archivo no registrado" }}
                </dd>
              </div>
              <div>
                <dt class="text-xs font-semibold uppercase text-gray-500">
                  Resultado conocido
                </dt>
                <dd class="mt-1 text-sm text-gray-900">
                  {{ resultSummary(prior) }}
                </dd>
              </div>
              <div>
                <dt class="text-xs font-semibold uppercase text-gray-500">
                  Solicitud de emisión
                </dt>
                <dd class="mt-1 text-sm text-gray-900">
                  {{ actorNames(prior.solicitantes) }}
                </dd>
              </div>
              <div>
                <dt class="text-xs font-semibold uppercase text-gray-500">
                  Período de emisión registrado
                </dt>
                <dd class="mt-1 text-sm text-gray-900">
                  {{ emissionInterval(prior) }}
                </dd>
              </div>
            </dl>
            <button
              data-return
              type="button"
              class="mt-6 rounded-lg border border-primary-700 bg-primary-700 px-5 py-2.5 font-semibold text-white"
              @click="returnToSummary"
            >
              Volver a la advertencia
            </button>
          </template>

          <template v-else>
            <h2
              id="duplicados-dialog-title"
              ref="panelHeadingRef"
              tabindex="-1"
              class="text-xl font-bold text-gray-900 outline-none"
            >
              Coincidencias encontradas
            </h2>
            <p
              id="duplicados-dialog-description"
              class="mt-2 text-sm text-gray-600"
            >
              Detalle de la evidencia revisada para este lote.
            </p>
            <p
              v-if="detailsLoading"
              class="mt-6 text-sm text-gray-600"
            >
              Cargando coincidencias…
            </p>
            <div
              v-else-if="details"
              class="mt-5 space-y-3"
            >
              <article
                v-for="item in details.items"
                :key="`${item.grupo_actual_id}-${item.lote_anterior_id}-${item.grupo_anterior_id}-${item.comprobante_anterior_ref}`"
                class="rounded-lg border border-gray-200 p-4"
              >
                <p class="text-sm font-semibold text-primary-800">
                  Comprobante actual {{ item.comprobante_actual_ref }}
                </p>
                <p class="font-semibold text-gray-900">
                  <template v-if="item.tipo_coincidencia === 'interna_receptor'">
                    Coincidencia dentro del lote actual
                  </template>
                  <template v-else-if="item.origen === 'comprobante_individual'">
                    Coincidencia con el comprobante
                    {{ item.comprobante_anterior_ref }}
                  </template>
                  <template v-else>
                    Coincidencia con el lote
                    {{ item.lote_anterior_id }}
                  </template>
                </p>
                <p class="mt-1 text-sm text-gray-700">
                  Coincide en:
                  {{
                    item.campos_coincidentes
                      .map((field) => fieldLabels[field] || field)
                      .join(", ")
                  }}.
                </p>
                <p class="text-sm text-gray-700">
                  Importe afectado:
                  {{ formatAmountWithCurrency(item.importe, item.moneda) }}.
                </p>
                <p class="text-sm text-gray-600">
                  Solicitud de emisión: {{ actorNames(item.solicitantes) }}.
                </p>
                <p class="text-sm text-gray-600">
                  Solicitud registrada:
                  {{ formatDateTime(item.solicitud_emision_at, null) }}.
                </p>
                <p class="text-sm text-gray-600">
                  Resultado fiscal registrado:
                  {{
                    formatDateTime(
                      item.resultado_fiscal_at,
                      item.hora_confiable,
                    )
                  }}.
                </p>
              </article>
              <div
                v-if="details.total_pages > 1"
                class="flex items-center justify-between gap-3 pt-2"
              >
                <button
                  type="button"
                  class="rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50"
                  :disabled="details.page <= 1"
                  @click="emit('requestDetails', details.page - 1)"
                >
                  Anterior
                </button>
                <span class="text-sm text-gray-600">Página {{ details.page }} de {{ details.total_pages }}</span>
                <button
                  type="button"
                  class="rounded border border-gray-300 px-3 py-2 text-sm disabled:opacity-50"
                  :disabled="details.page >= details.total_pages"
                  @click="emit('requestDetails', details.page + 1)"
                >
                  Siguiente
                </button>
              </div>
            </div>
            <button
              data-return
              type="button"
              class="mt-6 rounded-lg border border-primary-700 bg-primary-700 px-5 py-2.5 font-semibold text-white"
              @click="returnToSummary"
            >
              Volver a la advertencia
            </button>
          </template>
        </div>
      </section>
    </div>
  </Teleport>
</template>
