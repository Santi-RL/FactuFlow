import apiClient from "./api";
import type {
  AccionAlmacenamiento,
  AlmacenamientoItem,
  AlmacenamientoResumen,
  CrearExportacionAlmacenamiento,
  ExportacionAlmacenamiento,
  LoteCompactable,
} from "@/types/almacenamiento";

export const almacenamientoService = {
  async resumen(): Promise<AlmacenamientoResumen> {
    const response = await apiClient.get<AlmacenamientoResumen>(
      "/api/almacenamiento/resumen",
    );
    return response.data;
  },

  async lotesCompactables(): Promise<LoteCompactable[]> {
    const response = await apiClient.get<LoteCompactable[]>(
      "/api/almacenamiento/lotes-compactables",
    );
    return response.data;
  },

  async logs(): Promise<AlmacenamientoItem[]> {
    const response = await apiClient.get<AlmacenamientoItem[]>(
      "/api/almacenamiento/logs",
    );
    return response.data;
  },

  async temporales(): Promise<AlmacenamientoItem[]> {
    const response = await apiClient.get<AlmacenamientoItem[]>(
      "/api/almacenamiento/temporales",
    );
    return response.data;
  },

  async certificadosHuerfanos(): Promise<AlmacenamientoItem[]> {
    const response = await apiClient.get<AlmacenamientoItem[]>(
      "/api/almacenamiento/certificados-huerfanos",
    );
    return response.data;
  },

  async crearExportacion(
    payload: CrearExportacionAlmacenamiento,
  ): Promise<ExportacionAlmacenamiento> {
    const response = await apiClient.post<ExportacionAlmacenamiento>(
      "/api/almacenamiento/exportaciones",
      payload,
    );
    return response.data;
  },

  async descargarExportacion(
    token: string,
  ): Promise<{ blob: Blob; downloadToken: string }> {
    const response = await apiClient.get(
      `/api/almacenamiento/exportaciones/${token}/descargar`,
      { responseType: "blob" },
    );
    return {
      blob: response.data,
      downloadToken: response.headers["x-factuflow-download-token"],
    };
  },

  async confirmarDescarga(
    token: string,
    checksumSha256: string,
    downloadToken: string,
  ): Promise<ExportacionAlmacenamiento> {
    const response = await apiClient.post<ExportacionAlmacenamiento>(
      `/api/almacenamiento/exportaciones/${token}/confirmar-descarga`,
      { checksum_sha256: checksumSha256, download_token: downloadToken },
    );
    return response.data;
  },

  async confirmarLiberacion(token: string): Promise<AccionAlmacenamiento> {
    const response = await apiClient.post<AccionAlmacenamiento>(
      `/api/almacenamiento/exportaciones/${token}/confirmar-liberacion`,
      { confirmacion: "YA_LO_DESCARGUE" },
    );
    return response.data;
  },

  async limpiarCertificadosHuerfanos(
    ids: string[],
  ): Promise<AccionAlmacenamiento> {
    const response = await apiClient.post<AccionAlmacenamiento>(
      "/api/almacenamiento/certificados-huerfanos/limpiar",
      { ids },
    );
    return response.data;
  },
};

export default almacenamientoService;
