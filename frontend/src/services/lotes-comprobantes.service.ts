import apiClient from "./api";
import type {
  LoteComprobante,
  LoteComprobanteDetalle,
  LoteOpcionesFechas,
  LoteProcesamientoResponse,
  LoteValidacionResponse,
} from "@/types/lote-comprobante";

class LotesComprobantesService {
  async listar(): Promise<LoteComprobante[]> {
    const response = await apiClient.get<LoteComprobante[]>(
      "/api/lotes-comprobantes",
    );
    return response.data;
  }

  async obtener(id: number): Promise<LoteComprobanteDetalle> {
    const response = await apiClient.get<LoteComprobanteDetalle>(
      `/api/lotes-comprobantes/${id}`,
    );
    return response.data;
  }

  async validar(
    archivo: File,
    formatoVersionId?: number | null,
    opcionesFechas?: LoteOpcionesFechas,
    perfilCargaMasivaId?: number | null,
  ): Promise<LoteValidacionResponse> {
    const formData = new FormData();
    formData.append("archivo", archivo);
    if (formatoVersionId) {
      formData.append("formato_version_id", String(formatoVersionId));
    }
    if (perfilCargaMasivaId) {
      formData.append("perfil_carga_masiva_id", String(perfilCargaMasivaId));
    }
    if (opcionesFechas) {
      Object.entries(opcionesFechas).forEach(([key, value]) => {
        if (value) {
          formData.append(key, String(value));
        }
      });
    }

    const response = await apiClient.post<LoteValidacionResponse>(
      "/api/lotes-comprobantes/validar",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );

    return response.data;
  }

  async procesar(
    id: number,
    confirmacionFechaFiscal: string,
  ): Promise<LoteProcesamientoResponse> {
    const response = await apiClient.post<LoteProcesamientoResponse>(
      `/api/lotes-comprobantes/${id}/procesar`,
      null,
      {
        params: {
          background: true,
        },
        headers: {
          "X-Confirmacion-Fecha-Fiscal": confirmacionFechaFiscal,
        },
      },
    );
    return response.data;
  }

  async descargarPlantilla(): Promise<Blob> {
    const response = await apiClient.get("/api/lotes-comprobantes/plantilla", {
      responseType: "blob",
    });
    return response.data;
  }

  async descargarArchivoObservado(id: number): Promise<Blob> {
    const response = await apiClient.get(
      `/api/lotes-comprobantes/${id}/archivo-observado`,
      {
        responseType: "blob",
      },
    );
    return response.data;
  }
}

export default new LotesComprobantesService();
