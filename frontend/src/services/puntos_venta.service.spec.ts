import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import apiClient from "@/services/api";
import { puntosVentaService } from "@/services/puntos_venta.service";
import type {
  ImportarPuntosVentaResponse,
  SincronizarPuntosVentaResponse,
} from "@/types/punto_venta";

vi.mock("@/services/api", () => ({
  default: {
    post: vi.fn(),
  },
}));

const mockedApi = apiClient as unknown as { post: Mock };

const importResponseMock: ImportarPuntosVentaResponse = {
  total_constancia: 2,
  creados: 1,
  actualizados: 1,
  omitidos: 0,
  desactivados_ausentes: 1,
  verificados_rece: 1,
  pendientes_comprobacion: 0,
  no_verificados_rece: 1,
  documento_emitido_en: "2026-08-09",
  vigente_hasta: null,
  warnings: [],
};

describe("puntosVentaService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("usa siempre el camino seguro de acreditación productiva", async () => {
    mockedApi.post.mockResolvedValue({ data: importResponseMock });
    const file = new File(["PDF"], "constancia.pdf", {
      type: "application/pdf",
    });

    await expect(puntosVentaService.importarConstancia(file)).resolves.toEqual(
      importResponseMock,
    );

    const [url, body, config] = mockedApi.post.mock.calls[0] as [
      string,
      FormData,
      { headers: Record<string, string> },
    ];
    expect(url).toBe("/api/puntos-venta/importar-constancia");
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("file")).toBe(file);
    expect(body.get("confirmar_procedencia_produccion")).toBe("true");
    expect(config).toEqual({
      headers: { "Content-Type": "multipart/form-data" },
    });
  });

  it("delega la sincronización completa al endpoint transaccional", async () => {
    const response: SincronizarPuntosVentaResponse = {
      total_arca: 3,
      nuevos: 1,
      existentes: 2,
      actualizados: 1,
      desactivados_ausentes: 4,
      comprobado_en: "2026-08-28T12:00:00Z",
    };
    mockedApi.post.mockResolvedValue({ data: response });

    await expect(puntosVentaService.sincronizarArca()).resolves.toEqual(
      response,
    );
    expect(mockedApi.post).toHaveBeenCalledWith(
      "/api/puntos-venta/sincronizar-arca",
    );
  });
});
