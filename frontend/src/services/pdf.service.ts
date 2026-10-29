/**
 * Servicio para gestión de PDFs
 */

import api from "./api";
import { useEmpresaStore } from "@/stores/empresa";
import { isAxiosError } from "axios";

export async function mensajeErrorPDF(error: unknown): Promise<string> {
  if (isAxiosError(error) && error.response?.status === 409) {
    let data = error.response.data;
    if (data instanceof Blob) {
      try {
        data = JSON.parse(await data.text());
      } catch {
        data = null;
      }
    }
    if (
      typeof data?.detail === "string" &&
      data.detail.startsWith("Datos históricos no verificados.")
    ) {
      return "Datos históricos no verificados. El PDF no está disponible; consultá al responsable de la instalación.";
    }
  }
  return "No se pudo obtener el PDF. Intentá nuevamente y, si el problema continúa, consultá al responsable de la instalación.";
}

const PDF_PREVIEW_URL_FALLBACK_REVOKE_MS = 5 * 60 * 1000;

export interface PDFDownloadOptions {
  comprobanteId: number;
  preview?: boolean;
}

class PDFService {
  /**
   * Descarga el PDF de un comprobante
   */
  async descargarPDF(comprobanteId: number): Promise<Blob> {
    const empresaId = useEmpresaStore().empresaActivaId;
    const response = await api.get(`/api/pdf/comprobante/${comprobanteId}`, {
      responseType: "blob",
    });
    if (useEmpresaStore().empresaActivaId !== empresaId)
      throw new Error("La empresa activa cambió");
    return response.data;
  }

  /**
   * Abre el PDF de un comprobante en una nueva ventana
   */
  async previsualizarPDF(comprobanteId: number): Promise<void> {
    const empresaId = useEmpresaStore().empresaActivaId;
    const response = await api.get(
      `/api/pdf/comprobante/${comprobanteId}/preview`,
      {
        responseType: "blob",
      },
    );
    if (useEmpresaStore().empresaActivaId !== empresaId)
      throw new Error("La empresa activa cambió");

    const blob = new Blob([response.data], { type: "application/pdf" });
    const url = window.URL.createObjectURL(blob);
    const previewWindow = window.open(url, "_blank");

    this.programarRevocacionPreview(url, previewWindow);
  }

  private programarRevocacionPreview(
    url: string,
    previewWindow: Window | null,
  ): void {
    let revocado = false;
    const fallback: {
      id?: ReturnType<typeof window.setTimeout>;
    } = {};

    const revocar = () => {
      if (revocado) {
        return;
      }

      revocado = true;
      if (fallback.id !== undefined) {
        window.clearTimeout(fallback.id);
      }
      window.URL.revokeObjectURL(url);
    };

    fallback.id = window.setTimeout(
      revocar,
      PDF_PREVIEW_URL_FALLBACK_REVOKE_MS,
    );

    if (!previewWindow) {
      return;
    }

    try {
      // Evitar pagehide/unload: pueden dispararse durante la navegación inicial
      // de about:blank al blob y revocar el URL antes de que el visor lo lea.
      previewWindow.addEventListener("load", revocar, { once: true });
    } catch {
      // Si el navegador no permite observar la ventana, queda el fallback.
    }
  }

  /**
   * Descarga automáticamente el PDF
   */
  async descargarAutomatico(
    comprobanteId: number,
    filename?: string,
  ): Promise<void> {
    const empresaId = useEmpresaStore().empresaActivaId;
    const blob = await this.descargarPDF(comprobanteId);
    if (useEmpresaStore().empresaActivaId !== empresaId) {
      throw new Error("La empresa activa cambió");
    }

    // Crear un enlace temporal y hacer click
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || `Comprobante_${comprobanteId}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Liberar el objeto URL
    window.URL.revokeObjectURL(url);
  }
}

export default new PDFService();
