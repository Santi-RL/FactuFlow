import apiClient from "./api";
import type {
  FormatoImportacion,
  FormatoImportacionDeteccion,
} from "@/types/formato-importacion";

class FormatosImportacionService {
  async listar(): Promise<FormatoImportacion[]> {
    const response = await apiClient.get<FormatoImportacion[]>(
      "/api/formatos-importacion",
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
