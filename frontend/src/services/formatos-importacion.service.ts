import apiClient from "./api";
import type {
  FormatoImportacion,
  FormatoImportacionCampoCatalogo,
  FormatoImportacionCompatibilidad,
  FormatoImportacionDeteccion,
  FormatoImportacionExcelAnalisis,
  FormatoImportacionPayload,
} from "@/types/formato-importacion";

class FormatosImportacionService {
  async listar(): Promise<FormatoImportacion[]> {
    const response = await apiClient.get<FormatoImportacion[]>(
      "/api/formatos-importacion",
    );
    return response.data;
  }

  async crear(payload: FormatoImportacionPayload): Promise<FormatoImportacion> {
    const response = await apiClient.post<FormatoImportacion>(
      "/api/formatos-importacion",
      payload,
    );
    return response.data;
  }

  async actualizar(
    id: number,
    payload: FormatoImportacionPayload,
  ): Promise<FormatoImportacion> {
    const response = await apiClient.put<FormatoImportacion>(
      `/api/formatos-importacion/${id}`,
      payload,
    );
    return response.data;
  }

  async eliminar(id: number): Promise<void> {
    await apiClient.delete(`/api/formatos-importacion/${id}`);
  }

  async clonar(
    id: number,
    payload: { nombre?: string | null; alcance: "global" | "emisor" },
  ): Promise<FormatoImportacion> {
    const response = await apiClient.post<FormatoImportacion>(
      `/api/formatos-importacion/${id}/clonar`,
      payload,
    );
    return response.data;
  }

  async descargar(id: number): Promise<Blob> {
    const response = await apiClient.get(`/api/formatos-importacion/${id}/descargar`, {
      responseType: "blob",
    });
    return response.data;
  }

  async catalogoCampos(): Promise<FormatoImportacionCampoCatalogo[]> {
    const response = await apiClient.get<FormatoImportacionCampoCatalogo[]>(
      "/api/formatos-importacion/catalogo-campos",
    );
    return response.data;
  }

  async analizarExcel(archivo: File): Promise<FormatoImportacionExcelAnalisis> {
    const formData = new FormData();
    formData.append("archivo", archivo);
    const response = await apiClient.post<FormatoImportacionExcelAnalisis>(
      "/api/formatos-importacion/analizar-excel",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  }

  async evaluarCompatibilidad(
    configuracionJson: Record<string, unknown>,
    perfilConfiguracionJson?: Record<string, unknown> | null,
  ): Promise<FormatoImportacionCompatibilidad> {
    const response = await apiClient.post<FormatoImportacionCompatibilidad>(
      "/api/formatos-importacion/compatibilidad",
      {
        configuracion_json: configuracionJson,
        perfil_configuracion_json: perfilConfiguracionJson || null,
      },
    );
    return response.data;
  }

  async detectar(archivo: File): Promise<FormatoImportacionDeteccion> {
    const formData = new FormData();
    formData.append("archivo", archivo);
    const response = await apiClient.post<FormatoImportacionDeteccion>(
      "/api/formatos-importacion/detectar",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  }
}

export default new FormatosImportacionService();
