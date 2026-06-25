import apiClient from "./api";

export interface SistemaHealthResponse {
  status: string;
  message: string;
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
};

export default sistemaService;
