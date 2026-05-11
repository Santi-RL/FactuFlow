import type { LoteComprobante } from "@/types/lote-comprobante";

export interface LoteProgressInfo {
  procesados: number;
  pendientes: number;
  totalEmitible: number;
  porcentaje: number;
  estaEnCola: boolean;
  estaProcesando: boolean;
  estaActivo: boolean;
  transcurridoSegundos: number;
  restanteSegundos: number | null;
  transcurridoTexto: string;
  restanteTexto: string;
}

const ESTADOS_ACTIVOS = new Set(["en_cola", "procesando"]);

const parseDate = (value?: string | null) => {
  if (!value) return null;
  const trimmed = value.trim();
  const hasTimeZone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
  const normalized = trimmed.includes("T") && !hasTimeZone ? `${trimmed}Z` : trimmed;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

export const formatDuration = (seconds: number) => {
  const total = Math.max(Math.floor(seconds), 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainingSeconds = total % 60;
  const parts = [minutes, remainingSeconds].map((part) =>
    String(part).padStart(2, "0"),
  );

  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${parts.join(":")}`;
  }
  return parts.join(":");
};

export const calcularProgresoLote = (
  lote: LoteComprobante,
  now: Date = new Date(),
  fallbackStartedAt: Date | null = null,
): LoteProgressInfo => {
  const procesados = lote.grupos_emitidos + lote.grupos_fallidos;
  const pendientes = lote.grupos_validos;
  const totalEmitible = procesados + pendientes;
  const porcentaje =
    totalEmitible > 0 ? Math.round((procesados / totalEmitible) * 100) : 0;
  const estaEnCola = lote.estado === "en_cola";
  const estaProcesando = lote.estado === "procesando";
  const estaActivo = ESTADOS_ACTIVOS.has(lote.estado);
  const startedAt = parseDate(lote.started_at) || fallbackStartedAt;
  const finishedAt = parseDate(lote.finished_at);
  const end = !estaActivo && finishedAt ? finishedAt : now;
  const transcurridoSegundos = startedAt
    ? Math.max((end.getTime() - startedAt.getTime()) / 1000, 0)
    : 0;
  const restanteSegundos =
    estaActivo && procesados > 0 && pendientes > 0
      ? (transcurridoSegundos / procesados) * pendientes
      : estaActivo && procesados > 0
        ? 0
        : null;

  return {
    procesados,
    pendientes,
    totalEmitible,
    porcentaje,
    estaEnCola,
    estaProcesando,
    estaActivo,
    transcurridoSegundos,
    restanteSegundos,
    transcurridoTexto: formatDuration(transcurridoSegundos),
    restanteTexto:
      restanteSegundos === null ? "Estimando..." : formatDuration(restanteSegundos),
  };
};
