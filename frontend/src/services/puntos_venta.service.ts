import apiClient from "./api";
import type {
  ImportarPuntosVentaResponse,
  PuntoVenta,
  PuntoVentaUpdate,
  SincronizarPuntosVentaResponse,
} from "@/types/punto_venta";

export const puntosVentaService = {
  async getAll(): Promise<PuntoVenta[]> {
    const response = await apiClient.get<PuntoVenta[]>("/api/puntos-venta");
    return response.data;
  },

  async update(id: number, data: PuntoVentaUpdate): Promise<PuntoVenta> {
    const response = await apiClient.put<PuntoVenta>(
      `/api/puntos-venta/${id}`,
      data,
    );
    return response.data;
  },

  async importarConstancia(file: File): Promise<ImportarPuntosVentaResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<ImportarPuntosVentaResponse>(
      "/api/puntos-venta/importar-constancia",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  },

  async sincronizarArca(): Promise<SincronizarPuntosVentaResponse> {
    const response = await apiClient.post<SincronizarPuntosVentaResponse>(
      "/api/puntos-venta/sincronizar-arca",
    );
    return response.data;
  },
};
