import apiClient from "./api";

export interface ArcaStatus {
  ambiente: "homologacion" | "produccion";
  certificado_activo: boolean;
  certificado_disponible: boolean;
  certificado_id: number | null;
  certificado_nombre: string | null;
  certificado_vencimiento: string | null;
}

export const arcaService = {
  async getStatus(): Promise<ArcaStatus> {
    const response = await apiClient.get<ArcaStatus>("/api/arca/status");
    return response.data;
  },

  async testConnection(): Promise<any> {
    const response = await apiClient.get("/api/arca/test-conexion");
    return response.data;
  },

};
