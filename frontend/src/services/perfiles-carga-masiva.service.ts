import apiClient from "./api";
import type {
  PerfilCargaMasiva,
  PerfilCargaMasivaPayload,
} from "@/types/perfil-carga-masiva";

class PerfilesCargaMasivaService {
  async listar(): Promise<PerfilCargaMasiva[]> {
    const response = await apiClient.get<PerfilCargaMasiva[]>(
      "/api/perfiles-carga-masiva",
    );
    return response.data;
  }

  async crear(payload: PerfilCargaMasivaPayload): Promise<PerfilCargaMasiva> {
    const response = await apiClient.post<PerfilCargaMasiva>(
      "/api/perfiles-carga-masiva",
      payload,
    );
    return response.data;
  }

  async actualizar(
    id: number,
    payload: Partial<PerfilCargaMasivaPayload>,
  ): Promise<PerfilCargaMasiva> {
    const response = await apiClient.put<PerfilCargaMasiva>(
      `/api/perfiles-carga-masiva/${id}`,
      payload,
    );
    return response.data;
  }

  async eliminar(id: number): Promise<void> {
    await apiClient.delete(`/api/perfiles-carga-masiva/${id}`);
  }

  async marcarPredeterminado(id: number): Promise<PerfilCargaMasiva> {
    const response = await apiClient.post<PerfilCargaMasiva>(
      `/api/perfiles-carga-masiva/${id}/predeterminado`,
    );
    return response.data;
  }
}

export default new PerfilesCargaMasivaService();
