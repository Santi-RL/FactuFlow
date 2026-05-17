import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import comprobantesService from "@/services/comprobantes.service";
import { useComprobantesStore } from "@/stores/comprobantes";
import type {
  EmitirComprobanteRequest,
  EmitirComprobanteResponse,
} from "@/types/comprobante";

vi.mock("@/services/comprobantes.service", () => ({
  default: {
    listar: vi.fn(),
    emitir: vi.fn(),
    obtener: vi.fn(),
    proximoNumero: vi.fn(),
  },
}));

const mockedComprobantesService = comprobantesService as unknown as {
  listar: Mock;
  emitir: Mock;
};

const requestMock = (): EmitirComprobanteRequest => ({
  empresa_id: 1,
  punto_venta_id: 2,
  tipo_comprobante: 6,
  concepto: 1,
  fecha_emision: "2026-05-15",
  confirmacion_fecha_fiscal: true,
  tipo_documento: 80,
  numero_documento: "30700000001",
  razon_social: "Cliente Demo",
  condicion_iva: "Responsable Inscripto",
  items: [
    {
      descripcion: "Servicio",
      cantidad: 1,
      unidad: "unidades",
      precio_unitario: 100,
      descuento_porcentaje: 0,
      iva_porcentaje: 21,
      orden: 0,
    },
  ],
  moneda: "PES",
  cotizacion: 1,
});

const responseMock = (): EmitirComprobanteResponse => ({
  exito: true,
  comprobante_id: 99,
  tipo_comprobante: 6,
  punto_venta: 1,
  numero: 123,
  fecha: "2026-05-15",
  cae: "12345678901234",
  cae_vencimiento: "2026-05-25",
  total: 121,
  mensaje: "Autorizado",
  errores: [],
});

describe("comprobantes store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("mantiene exitosa la emision aunque falle el refresco posterior", async () => {
    const store = useComprobantesStore();
    const warnSpy = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    store.filtros = { page: 1, per_page: 20 };
    mockedComprobantesService.emitir.mockResolvedValue(responseMock());
    mockedComprobantesService.listar.mockRejectedValue(
      new Error("Fallo transitorio"),
    );

    await expect(store.emitirComprobante(requestMock())).resolves.toMatchObject(
      {
        exito: true,
        comprobante_id: 99,
        cae: "12345678901234",
      },
    );
    expect(mockedComprobantesService.listar).toHaveBeenCalledWith({
      page: 1,
      per_page: 20,
    });
    expect(store.error).toBeNull();
    expect(warnSpy).toHaveBeenCalled();
  });
});
