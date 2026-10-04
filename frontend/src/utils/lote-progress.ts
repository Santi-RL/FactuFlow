import type {
  LoteComprobante,
  LoteOperacionProgreso,
} from "@/types/lote-comprobante";
import { parsearInstante } from "@/utils/instantes";

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
  autorizados: number;
  fallidos: number;
  inciertos: number;
}

const ESTADOS_ACTIVOS = new Set(["en_cola", "procesando"]);

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
  const operacion =
    lote.operacion_progreso ||
    (lote.metadata_json?.operacion_progreso as
      LoteOperacionProgreso | undefined);
  const autorizados = operacion?.autorizados ?? lote.grupos_emitidos;
  const fallidos = operacion?.fallidos ?? lote.grupos_fallidos;
  const inciertos = operacion?.inciertos ?? 0;
  const procesados = autorizados + fallidos + inciertos;
  const pendientes = operacion?.pendientes ?? lote.grupos_validos;
  const totalEmitible = operacion?.seleccionados ?? procesados + pendientes;
  const porcentaje =
    totalEmitible > 0 ? Math.round((procesados / totalEmitible) * 100) : 0;
  const estaEnCola = lote.estado === "en_cola";
  const estaProcesando = lote.estado === "procesando";
  const estaActivo = ESTADOS_ACTIVOS.has(lote.estado);
  const startedAt =
    parsearInstante(lote.started_at, { interpretarSinZonaComoUtc: true }) ||
    fallbackStartedAt;
  const finishedAt = parsearInstante(lote.finished_at, {
    interpretarSinZonaComoUtc: true,
  });
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
    autorizados,
    fallidos,
    inciertos,
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
      restanteSegundos === null
        ? "Estimando..."
        : formatDuration(restanteSegundos),
  };
};
