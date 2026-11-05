import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { AxiosError } from "axios";
import api from "./api";
import {
  descargarZIP,
  mensajeErrorZIP,
  resolverSeleccionPDF,
} from "./descargas-pdf.service";

vi.mock("./api", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

describe("descarga ZIP", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("resuelve IDs de todas las páginas sin enviar paginación ni cargar documentos", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { ids: [1, 2, 3], total: 3 },
    });
    expect(
      await resolverSeleccionPDF({
        desde: "2026-11-01",
        page: 2,
        per_page: 20,
      }),
    ).toEqual([1, 2, 3]);
    expect(api.get).toHaveBeenCalledWith("/api/pdf/seleccion", {
      params: { desde: "2026-11-01" },
    });
  });

  it("no crea un archivo de un contexto invalidado durante la espera", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: new Blob(["zip"]) });
    const create = vi.spyOn(URL, "createObjectURL");
    await descargarZIP([1, 2], () => false);
    expect(create).not.toHaveBeenCalled();
    expect(api.post).toHaveBeenCalledWith(
      "/api/pdf/zip",
      { ids: [1, 2] },
      { responseType: "blob" },
    );
  });

  it("libera URL y enlace incluso si el navegador rechaza la descarga", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: new Blob(["zip"]) });
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:sintetico");
    const revoke = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      throw new Error("fallo");
    });
    await expect(descargarZIP([1], () => true)).rejects.toThrow("fallo");
    expect(revoke).toHaveBeenCalledWith("blob:sintetico");
    expect(document.querySelector("a[download]")).toBeNull();
  });

  it("explica el ZIP no entregado y sus fallidos; sanitiza otros errores", async () => {
    const error = new AxiosError();
    error.response = {
      status: 409,
      data: {
        detail: {
          fallidos: [
            {
              comprobante: "Factura_C_0001-00000001.pdf",
              mensaje: "El PDF no está disponible.",
            },
          ],
        },
      },
    } as never;
    expect(await mensajeErrorZIP(error)).toContain(
      "Factura_C_0001-00000001.pdf",
    );
    error.response = {
      status: 500,
      data: { detail: "secreto interno" },
    } as never;
    expect(await mensajeErrorZIP(error)).not.toContain("secreto");
    error.response = {
      status: 404,
      data: { detail: "contenido interno" },
    } as never;
    expect(await mensajeErrorZIP(error)).toContain(
      "Volvé a aplicar los filtros",
    );
    expect(await mensajeErrorZIP(error)).not.toContain("interno");
  });
});
