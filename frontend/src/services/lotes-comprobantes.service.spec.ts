import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import api from "@/services/api";
import lotesComprobantesService from "@/services/lotes-comprobantes.service";

vi.mock("@/services/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApi = api as unknown as { get: Mock; post: Mock };

describe("lotesComprobantesService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.get.mockResolvedValue({
      data: { items: [], page: 1, per_page: 50, total: 0, total_pages: 0 },
    });
    mockedApi.post.mockResolvedValue({
      data: { lote: {}, mensaje: "ok", en_progreso: false },
    });
  });

  it("consulta coincidencias con evidencia opaca y paginación acotada", async () => {
    await lotesComprobantesService.obtenerCoincidencias(42, {
      evidenciaId: "v2.evidencia-opaca",
      page: 3,
      perPage: 50,
    });

    expect(mockedApi.get).toHaveBeenCalledWith(
      "/api/lotes-comprobantes/42/coincidencias",
      {
        params: {
          evidencia_id: "v2.evidencia-opaca",
          page: 3,
          per_page: 50,
        },
      },
    );
  });

  it("reenvía la misma clave idempotente y la aceptación opaca del POST 409", async () => {
    const key = "operacion-idempotente-uno";
    const acceptanceId = "v2.aceptacion-opaca";

    await lotesComprobantesService.procesar(42, "confirmacion-fecha", key);
    await lotesComprobantesService.procesar(
      42,
      "confirmacion-fecha",
      key,
      acceptanceId,
    );

    expect(mockedApi.post).toHaveBeenNthCalledWith(
      1,
      "/api/lotes-comprobantes/42/procesar",
      null,
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Idempotency-Key": key,
          "X-Confirmacion-Fecha-Fiscal": "confirmacion-fecha",
        }),
      }),
    );
    expect(mockedApi.post.mock.calls[0][2].headers).not.toHaveProperty(
      "X-Confirmacion-Duplicado-Logico",
    );
    expect(mockedApi.post).toHaveBeenNthCalledWith(
      2,
      "/api/lotes-comprobantes/42/procesar",
      null,
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Idempotency-Key": key,
          "X-Confirmacion-Duplicado-Logico": acceptanceId,
        }),
      }),
    );
  });

  it("conserva selección, clave y aceptación al reintentar fallidos", async () => {
    await lotesComprobantesService.reintentarFallidos(
      42,
      [8, 9],
      "confirmacion-reintento",
      "operacion-reintento",
      "v2.aceptacion-reintento",
    );

    expect(mockedApi.post).toHaveBeenCalledWith(
      "/api/lotes-comprobantes/42/reintentar-fallidos",
      { grupo_ids: [8, 9] },
      {
        params: { background: true },
        headers: {
          "X-Confirmacion-Fecha-Fiscal": "confirmacion-reintento",
          "X-Idempotency-Key": "operacion-reintento",
          "X-Confirmacion-Duplicado-Logico": "v2.aceptacion-reintento",
        },
      },
    );
  });
});
