import apiClient from "./api";
import type {
  ConstanciaArcaExtracted,
  Empresa,
  EmpresaCreate,
  EmpresaUpdate,
} from "@/types/empresa";

export const empresaService = {
  async getAll(): Promise<Empresa[]> {
    const response = await apiClient.get<Empresa[]>("/api/empresas");
    return response.data;
  },

  async getById(id: number): Promise<Empresa> {
    const response = await apiClient.get<Empresa>(`/api/empresas/${id}`);
    return response.data;
  },

  async create(data: EmpresaCreate): Promise<Empresa> {
    const response = await apiClient.post<Empresa>("/api/empresas", data);
    return response.data;
  },

  async extraerConstancia(file: File): Promise<ConstanciaArcaExtracted> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<ConstanciaArcaExtracted>(
      "/api/empresas/extraer-constancia",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
    return response.data;
  },

  async update(id: number, data: EmpresaUpdate): Promise<Empresa> {
    const response = await apiClient.put<Empresa>(`/api/empresas/${id}`, data);
    return response.data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/api/empresas/${id}`);
  },
};
