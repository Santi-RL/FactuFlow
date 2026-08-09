import apiClient from "./api";
import type {
  ImportarConstanciaPuntosVentaOptions,
  ImportarPuntosVentaResponse,
  PuntoVenta,
  PuntoVentaCreate,
  PuntoVentaUpdate,
  SincronizarPuntosVentaResponse,
} from "@/types/punto_venta";

export const puntosVentaService = {
  async getAll(): Promise<PuntoVenta[]> {
    const response = await apiClient.get<PuntoVenta[]>("/api/puntos-venta");
    return response.data;
  },

  async create(data: PuntoVentaCreate): Promise<PuntoVenta> {
    const response = await apiClient.post<PuntoVenta>(
      "/api/puntos-venta",
      data,
    );
    return response.data;
  },

  async update(id: number, data: PuntoVentaUpdate): Promise<PuntoVenta> {
    const response = await apiClient.put<PuntoVenta>(
      `/api/puntos-venta/${id}`,
      data,
    );
    return response.data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/api/puntos-venta/${id}`);
  },

  async importarConstancia(
    file: File,
    options: ImportarConstanciaPuntosVentaOptions,
  ): Promise<ImportarPuntosVentaResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append(
      "confirmar_procedencia_produccion",
      String(options.confirmar_procedencia_produccion),
    );
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
