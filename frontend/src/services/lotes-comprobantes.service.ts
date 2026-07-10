import apiClient from "./api";
import type {
  LoteComprobante,
  LoteComprobanteDetalle,
  LoteComprobanteSeguimiento,
  LoteComprobanteGruposPage,
  LoteComprobanteResumen,
  LoteAccionResponse,
  LoteOpcionesFechas,
  LoteProcesamientoResponse,
  ReconciliacionExternaItem,
  LoteValidacionResponse,
} from "@/types/lote-comprobante";

interface ObtenerGruposParams {
  page?: number;
  perPage?: number;
  estado?: string | null;
}

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

  async obtenerResumen(id: number): Promise<LoteComprobanteResumen> {
    const response = await apiClient.get<LoteComprobanteResumen>(
      `/api/lotes-comprobantes/${id}/resumen`,
    );
    return response.data;
  }

  async obtenerSeguimiento(id: number): Promise<LoteComprobanteSeguimiento> {
    const response = await apiClient.get<LoteComprobanteSeguimiento>(
      `/api/lotes-comprobantes/${id}/seguimiento`,
    );
    return response.data;
  }

  async obtenerGrupos(
    id: number,
    params: ObtenerGruposParams = {},
  ): Promise<LoteComprobanteGruposPage> {
    const response = await apiClient.get<LoteComprobanteGruposPage>(
      `/api/lotes-comprobantes/${id}/grupos`,
      {
        params: {
          page: params.page,
          per_page: params.perPage,
          estado: params.estado || undefined,
        },
      },
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
    idempotencyKey: string,
    confirmacionDuplicadoLogico?: string,
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
          "X-Idempotency-Key": idempotencyKey,
          ...(confirmacionDuplicadoLogico
            ? {
                "X-Confirmacion-Duplicado-Logico": confirmacionDuplicadoLogico,
              }
            : {}),
        },
      },
    );
    return response.data;
  }

  async reintentarFallidos(
    id: number,
    grupoIds: number[],
    confirmacionFechaFiscal: string,
    idempotencyKey: string,
    confirmacionDuplicadoLogico?: string,
  ): Promise<LoteAccionResponse> {
    const response = await apiClient.post<LoteAccionResponse>(
      `/api/lotes-comprobantes/${id}/reintentar-fallidos`,
      { grupo_ids: grupoIds },
      {
        headers: {
          "X-Confirmacion-Fecha-Fiscal": confirmacionFechaFiscal,
          "X-Idempotency-Key": idempotencyKey,
          ...(confirmacionDuplicadoLogico
            ? {
                "X-Confirmacion-Duplicado-Logico": confirmacionDuplicadoLogico,
              }
            : {}),
        },
      },
    );
    return response.data;
  }

  async reconciliarExternos(
    id: number,
    comprobantes: ReconciliacionExternaItem[],
  ): Promise<LoteAccionResponse> {
    const response = await apiClient.post<LoteAccionResponse>(
      `/api/lotes-comprobantes/${id}/reconciliar-externos`,
      { comprobantes },
    );
    return response.data;
  }

  async descartarGrupos(
    id: number,
    grupoIds: number[],
    motivo: string,
  ): Promise<LoteAccionResponse> {
    const response = await apiClient.post<LoteAccionResponse>(
      `/api/lotes-comprobantes/${id}/descartar-grupos`,
      { grupo_ids: grupoIds, motivo },
    );
    return response.data;
  }

  async compactar(id: number): Promise<LoteAccionResponse> {
    const response = await apiClient.post<LoteAccionResponse>(
      `/api/lotes-comprobantes/${id}/compactar`,
    );
    return response.data;
  }

  async eliminar(id: number, motivo: string): Promise<void> {
    await apiClient.delete(`/api/lotes-comprobantes/${id}`, {
      data: { motivo },
    });
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
