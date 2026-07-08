import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import comprobantesService from "@/services/comprobantes.service";
import { useComprobantesStore } from "@/stores/comprobantes";
import type {
  ComprobanteDetalle,
  ComprobanteListItem,
  EmitirComprobanteRequest,
  EmitirComprobanteResponse,
  PaginatedComprobantesResponse,
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
  obtener: Mock;
};

const crearDiferido = <T>() => {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolver, rechazador) => {
    resolve = resolver;
    reject = rechazador;
  });

  return { promise, resolve, reject };
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

const comprobanteDetalleMock = (id: number): ComprobanteDetalle => ({
  id,
  tipo_comprobante: 6,
  concepto: 1,
  numero: 123,
  fecha_emision: "2026-05-15",
  subtotal: 100,
  descuento: 0,
  iva_21: 21,
  iva_10_5: 0,
  iva_27: 0,
  otros_impuestos: 0,
  total: 121,
  cae: "12345678901234",
  cae_vencimiento: "2026-05-25",
  estado: "autorizado",
  moneda: "PES",
  cotizacion: 1,
  empresa_id: 1,
  punto_venta_id: 2,
  cliente_id: 3,
  items: [],
  cliente_nombre: "Cliente Demo",
  cliente_cuit: "30700000001",
  punto_venta_numero: 1,
});

const comprobanteListItemMock = (id: number): ComprobanteListItem => ({
  id,
  tipo_comprobante: 6,
  numero: 123,
  fecha_emision: "2026-05-15",
  total: 121,
  estado: "autorizado",
  cae: "12345678901234",
  cliente_nombre: "Cliente Demo",
  cliente_documento: "30700000001",
  punto_venta_numero: 1,
});

const paginaComprobantesMock = (
  items: ComprobanteListItem[],
): PaginatedComprobantesResponse => ({
  items,
  total: items.length,
  page: 1,
  per_page: 20,
  pages: items.length ? 1 : 0,
});

describe("comprobantes store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("limpia el comprobante actual si falla una carga de detalle", async () => {
    const store = useComprobantesStore();
    const error = { response: { data: { detail: "No encontrado" } } };
    store.comprobanteActual = comprobanteDetalleMock(10);
    mockedComprobantesService.obtener.mockRejectedValue(error);

    await expect(store.obtenerComprobante(999)).rejects.toEqual(error);

    expect(mockedComprobantesService.obtener).toHaveBeenCalledWith(999);
    expect(store.comprobanteActual).toBeNull();
    expect(store.error).toBe("No encontrado");
  });

  it("limpia el listado si falla una carga nueva", async () => {
    const store = useComprobantesStore();
    const error = { response: { data: { detail: "Empresa no autorizada" } } };
    store.comprobantes = [comprobanteListItemMock(10)];
    store.paginacion = paginaComprobantesMock(store.comprobantes);
    mockedComprobantesService.listar.mockRejectedValue(error);

    await expect(
      store.listarComprobantes({ page: 2, per_page: 20 }),
    ).rejects.toEqual(error);

    expect(mockedComprobantesService.listar).toHaveBeenCalledWith({
      page: 2,
      per_page: 20,
    });
    expect(store.comprobantes).toEqual([]);
    expect(store.hayComprobantes).toBe(false);
    expect(store.paginacion).toEqual({
      total: 0,
      page: 2,
      per_page: 20,
      pages: 0,
    });
    expect(store.error).toBe("Empresa no autorizada");
  });
  it("conserva el listado visible si falla un cambio de pagina", async () => {
    const store = useComprobantesStore();
    const error = { response: { data: { detail: "Fallo transitorio" } } };
    const comprobantesPrevios = [comprobanteListItemMock(10)];
    const paginacionPrevia = paginaComprobantesMock(comprobantesPrevios);
    store.filtros = { page: 1, per_page: 20 };
    store.comprobantes = comprobantesPrevios;
    store.paginacion = paginacionPrevia;
    mockedComprobantesService.listar.mockRejectedValue(error);

    await store.cambiarPagina(2);

    expect(mockedComprobantesService.listar).toHaveBeenCalledWith({
      page: 2,
      per_page: 20,
    });
    expect(store.comprobantes).toEqual(comprobantesPrevios);
    expect(store.hayComprobantes).toBe(true);
    expect(store.paginacion).toEqual(paginacionPrevia);
    expect(store.filtros).toEqual({ page: 1, per_page: 20 });
    expect(store.error).toBe("Fallo transitorio");
  });
  it("ignora fallas obsoletas de listados solapados", async () => {
    const store = useComprobantesStore();
    const primeraCarga = crearDiferido<PaginatedComprobantesResponse>();
    const segundaCarga = crearDiferido<PaginatedComprobantesResponse>();
    const comprobanteVigente = comprobanteListItemMock(20);
    const paginaVigente = paginaComprobantesMock([comprobanteVigente]);
    mockedComprobantesService.listar
      .mockReturnValueOnce(primeraCarga.promise)
      .mockReturnValueOnce(segundaCarga.promise);

    const requestAnterior = store.listarComprobantes({ page: 1, per_page: 20 });
    const requestVigente = store.listarComprobantes({ page: 2, per_page: 20 });

    segundaCarga.resolve({ ...paginaVigente, page: 2 });
    await requestVigente;

    primeraCarga.reject({ response: { data: { detail: "Fallo obsoleto" } } });
    await expect(requestAnterior).resolves.toBeUndefined();

    expect(store.comprobantes).toEqual([comprobanteVigente]);
    expect(store.paginacion).toEqual({
      total: paginaVigente.total,
      page: 2,
      per_page: paginaVigente.per_page,
      pages: paginaVigente.pages,
    });
    expect(store.filtros).toEqual({ page: 2, per_page: 20 });
    expect(store.error).toBeNull();
  });
  it("mantiene exitosa la emision aunque falle el refresco posterior", async () => {
    const store = useComprobantesStore();
    const warnSpy = vi
      .spyOn(console, "warn")
      .mockImplementation(() => undefined);
    store.filtros = { page: 1, per_page: 20 };
    const comprobantesPrevios = [comprobanteListItemMock(10)];
    const paginacionPrevia = paginaComprobantesMock(comprobantesPrevios);
    store.comprobantes = comprobantesPrevios;
    store.paginacion = paginacionPrevia;
    mockedComprobantesService.emitir.mockResolvedValue(responseMock());
    mockedComprobantesService.listar.mockRejectedValue(
      new Error("Fallo transitorio"),
    );

    await expect(
      store.emitirComprobante(requestMock(), "idem-store-test"),
    ).resolves.toMatchObject({
      exito: true,
      comprobante_id: 99,
      cae: "12345678901234",
    });
    expect(mockedComprobantesService.emitir).toHaveBeenCalledWith(
      expect.any(Object),
      "idem-store-test",
    );
    expect(mockedComprobantesService.listar).toHaveBeenCalledWith({
      page: 1,
      per_page: 20,
    });
    expect(store.error).toBeNull();
    expect(store.comprobantes).toEqual(comprobantesPrevios);
    expect(store.paginacion).toEqual(paginacionPrevia);
    expect(warnSpy).toHaveBeenCalled();
  });
});
