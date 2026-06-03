import apiClient from "./api";
import type {
  Usuario,
  UsuarioAdminCreate,
  UsuarioAdminUpdate,
  UsuarioPasswordReset,
} from "@/types/auth";

export const usuariosService = {
  async getAll(): Promise<Usuario[]> {
    const response = await apiClient.get<Usuario[]>("/api/usuarios");
    return response.data;
  },

  async create(data: UsuarioAdminCreate): Promise<Usuario> {
    const response = await apiClient.post<Usuario>("/api/usuarios", data);
    return response.data;
  },

  async update(id: number, data: UsuarioAdminUpdate): Promise<Usuario> {
    const response = await apiClient.put<Usuario>(`/api/usuarios/${id}`, data);
    return response.data;
  },

  async desactivar(id: number): Promise<Usuario> {
    const response = await apiClient.post<Usuario>(
      `/api/usuarios/${id}/desactivar`,
    );
    return response.data;
  },

  async reactivar(id: number): Promise<Usuario> {
    const response = await apiClient.post<Usuario>(
      `/api/usuarios/${id}/reactivar`,
    );
    return response.data;
  },

  async resetPassword(
    id: number,
    data: UsuarioPasswordReset,
  ): Promise<Usuario> {
    const response = await apiClient.post<Usuario>(
      `/api/usuarios/${id}/reset-password`,
      data,
    );
    return response.data;
  },
};
