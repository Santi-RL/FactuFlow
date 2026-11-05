import { isAxiosError } from "axios";
import api from "./api";
import type { ListarComprobantesParams } from "./comprobantes.service";

export async function resolverSeleccionPDF(filtros: ListarComprobantesParams) {
  const { page: _page, per_page: _perPage, ...params } = filtros;
  const { data } = await api.get<{ ids: number[]; total: number }>(
    "/api/pdf/seleccion",
    { params },
  );
  if (
    !Array.isArray(data.ids) ||
    data.ids.some((id) => !Number.isSafeInteger(id) || id <= 0)
  ) {
    throw new Error("Selección no disponible");
  }
  return [...new Set(data.ids)];
}

export async function descargarZIP(
  ids: number[],
  vigente: () => boolean,
  signal?: AbortSignal,
) {
  const { data } = await api.post<Blob>(
    "/api/pdf/zip",
    { ids },
    { responseType: "blob", ...(signal ? { signal } : {}) },
  );
  if (!vigente()) return;
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  try {
    link.href = url;
    link.download = `Comprobantes_${ids.length}.zip`;
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    URL.revokeObjectURL(url);
  }
}

export async function mensajeErrorZIP(error: unknown): Promise<string> {
  if (isAxiosError(error) && error.response?.status === 404) {
    return "La selección contiene comprobantes no disponibles. Volvé a aplicar los filtros y seleccioná nuevamente.";
  }
  if (isAxiosError(error) && error.response?.status === 409) {
    let data = error.response.data;
    if (data instanceof Blob) {
      try {
        data = JSON.parse(await data.text());
      } catch {
        data = null;
      }
    }
    const fallidos = data?.detail?.fallidos;
    if (
      Array.isArray(fallidos) &&
      fallidos.every(
        (f) =>
          f &&
          typeof f.comprobante === "string" &&
          typeof f.mensaje === "string",
      )
    ) {
      return (
        "No se descargó el ZIP porque faltan PDF de la selección. Podés quitar estos comprobantes o descargar los demás individualmente:\n" +
        fallidos.map((f) => `${f.comprobante}: ${f.mensaje}`).join("\n")
      );
    }
  }
  return "No se pudo descargar el ZIP. Intentá nuevamente y, si el problema continúa, consultá al responsable de la instalación.";
}
