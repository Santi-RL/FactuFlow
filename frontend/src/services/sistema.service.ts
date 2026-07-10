import apiClient from "./api";

export interface SistemaHealthResponse {
  status: string;
  message: string;
}

export type LoteWorkerHealthStatus = "healthy" | "degraded" | "disabled";
export type LoteWorkerEstado =
  | "deshabilitado"
  | "detenido"
  | "esperando"
  | "ocupado";

export interface DatabasePoolRoleHealthResponse {
  pool_size: number | null;
  max_overflow: number | null;
  capacity: number | null;
  checked_out: number | null;
  checked_in: number | null;
  overflow: number | null;
  high_water_mark: number | null;
  acquisition_count: number | null;
  timeout_count: number | null;
  last_wait_ms: number | null;
  max_wait_ms: number | null;
}

export interface LoteWorkerHealthResponse {
  status: LoteWorkerHealthStatus;
  worker: {
    estado: LoteWorkerEstado;
    habilitado: boolean;
    ejecutando: boolean;
    ocupado: boolean;
    ciclo_iniciado_at: string | null;
    ciclo_finalizado_at: string | null;
    ultima_duracion_ms: number | null;
    ultimo_resultado: "exitoso" | "error" | null;
    ultimo_exito_at: string | null;
    ultimo_error_at: string | null;
    stale_detectados_ultimo_ciclo: number;
    lotes_en_cola_ultimo_ciclo: number;
    lotes_procesados_ultimo_ciclo: number;
  };
  pools: {
    separation_required: boolean;
    separated: boolean;
    api: DatabasePoolRoleHealthResponse;
    worker: DatabasePoolRoleHealthResponse;
  };
}

const sistemaService = {
  async health(): Promise<SistemaHealthResponse> {
    const response = await apiClient.get<SistemaHealthResponse>("/api/health");
    return response.data;
  },

  async databaseHealth(): Promise<SistemaHealthResponse> {
    const response =
      await apiClient.get<SistemaHealthResponse>("/api/health/db");
    return response.data;
  },

  async workerHealth(): Promise<LoteWorkerHealthResponse> {
    const response = await apiClient.get<LoteWorkerHealthResponse>(
      "/api/health/worker",
    );
    return response.data;
  },
};

export default sistemaService;
