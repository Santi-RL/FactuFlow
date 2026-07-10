import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { arcaService } from "@/services/arca.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import { usePuntosVentaStore } from "@/stores/puntos_venta";
import type { Empresa } from "@/types/empresa";
import type { PuntoVenta, PuntoVentaArca } from "@/types/punto_venta";
import {
  clearEmpresaActivaIdForRequest,
  clearEmpresaActivaIdStorage,
  setEmpresaActivaIdStorage,
} from "@/utils/empresa-activa-storage";

vi.mock("@/services/puntos_venta.service", () => ({
  puntosVentaService: {
    getAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    importarConstancia: vi.fn(),
  },
}));

vi.mock("@/services/arca.service", () => ({
  arcaService: {
    getPuntosVenta: vi.fn(),
  },
}));

const empresaMock = (id: number): Empresa => ({
  id,
  razon_social: `Emisor ${id}`,
  cuit: `3070000000${id}`,
  condicion_iva: "RI",
  ingresos_brutos: null,
  domicilio: "Av. Demo 123",
  localidad: "CABA",
  provincia: "CABA",
  codigo_postal: "1000",
  email: null,
  telefono: null,
  inicio_actividades: "2024-01-01",
  logo: null,
  created_at: "2024-01-01T00:00:00",
  updated_at: "2024-01-01T00:00:00",
});

const puntoVentaMock = (empresaId: number, numero: number): PuntoVenta => ({
  id: empresaId * 10 + numero,
  numero,
  nombre: `PV ${numero}`,
  sistema: "Factura Electronica - Web Services",
  domicilio: null,
  nombre_fantasia: null,
  es_webservice: true,
  bloqueado: false,
  fecha_baja: null,
  fuente: "arca_wsfe",
  activo: true,
  usable_factuflow: true,
  empresa_id: empresaId,
  created_at: "2024-01-01T00:00:00",
});
const puntoVentaArcaMock = (numero: number): PuntoVentaArca => ({
  numero,
  emision_tipo: "CAE - Factura Electronica",
  bloqueado: "N",
  fecha_baja: null,
});

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolver, rejecter) => {
    resolve = resolver;
    reject = rejecter;
  });
  return { promise, resolve, reject };
};

const mockedPuntosVentaService = puntosVentaService as unknown as {
  getAll: Mock;
  create: Mock;
  update: Mock;
};

const mockedArcaService = arcaService as unknown as {
  getPuntosVenta: Mock;
};

describe("puntos venta store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
    clearEmpresaActivaIdStorage();
  });

  it("rechaza sincronizar ARCA sin emisor activo confirmado", async () => {
    const store = usePuntosVentaStore();
    const mensaje =
      "Seleccioná un emisor activo antes de sincronizar puntos de venta con ARCA";

    await expect(store.syncFromArca()).rejects.toThrow(mensaje);

    expect(mockedArcaService.getPuntosVenta).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.getAll).not.toHaveBeenCalled();
    expect(store.error).toBe(mensaje);
    expect(store.syncing).toBe(false);
  });
  it("ignora sincronizaciones ARCA obsoletas cuando cambia el emisor activo", async () => {
    const puntosArca = deferred<PuntoVentaArca[]>();
    const locales = deferred<PuntoVenta[]>();
    mockedArcaService.getPuntosVenta.mockReturnValue(puntosArca.promise);
    mockedPuntosVentaService.getAll.mockReturnValue(locales.promise);
    mockedPuntosVentaService.create.mockResolvedValue(puntoVentaMock(1, 6));
    mockedPuntosVentaService.update.mockResolvedValue(puntoVentaMock(1, 6));
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const store = usePuntosVentaStore();
    store.puntosVenta = [puntoVentaMock(2, 2)];

    const sincronizacion = store.syncFromArca();
    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    setEmpresaActivaIdStorage(2);
    puntosArca.resolve([puntoVentaArcaMock(6)]);
    locales.resolve([]);
    const resultado = await sincronizacion;

    expect(resultado).toEqual({ total_arca: 0, nuevos: 0, existentes: 0 });
    expect(mockedPuntosVentaService.create).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.update).not.toHaveBeenCalled();
    expect(store.puntosVenta.map((punto) => punto.empresa_id)).toEqual([2]);
    expect(store.syncing).toBe(false);
    expect(store.error).toBeNull();
  });

  it("corta la sincronización si el scope de request se limpia durante cambio de emisor", async () => {
    const puntosArca = deferred<PuntoVentaArca[]>();
    const locales = deferred<PuntoVenta[]>();
    mockedArcaService.getPuntosVenta.mockReturnValue(puntosArca.promise);
    mockedPuntosVentaService.getAll.mockReturnValue(locales.promise);
    mockedPuntosVentaService.create.mockResolvedValue(puntoVentaMock(1, 6));
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const store = usePuntosVentaStore();

    const sincronizacion = store.syncFromArca();
    clearEmpresaActivaIdForRequest();
    puntosArca.resolve([puntoVentaArcaMock(6)]);
    locales.resolve([]);
    const resultado = await sincronizacion;

    expect(resultado).toEqual({ total_arca: 0, nuevos: 0, existentes: 0 });
    expect(mockedPuntosVentaService.create).not.toHaveBeenCalled();
    expect(store.puntosVenta).toEqual([]);
    expect(store.syncing).toBe(false);
    expect(store.error).toBeNull();
  });

  it("ignora errores ARCA obsoletos si el scope de request se limpia durante cambio de emisor", async () => {
    const puntosArca = deferred<PuntoVentaArca[]>();
    mockedArcaService.getPuntosVenta.mockReturnValue(puntosArca.promise);
    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const store = usePuntosVentaStore();

    const sincronizacion = store.syncFromArca();
    clearEmpresaActivaIdForRequest();
    puntosArca.reject({
      response: { data: { detail: "ARCA no disponible" } },
    });
    const resultado = await sincronizacion;

    expect(resultado).toEqual({ total_arca: 0, nuevos: 0, existentes: 0 });
    expect(store.error).toBeNull();
    expect(store.syncing).toBe(false);
  });

  it("ignora una actualización obsoleta con ids superpuestos", async () => {
    const actualizacionPendiente = deferred<PuntoVenta>();
    mockedPuntosVentaService.update.mockReturnValue(
      actualizacionPendiente.promise,
    );
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const store = usePuntosVentaStore();
    const puntoEmisorA = { ...puntoVentaMock(1, 6), id: 42 };
    const puntoEmisorB = { ...puntoVentaMock(2, 8), id: 42 };
    store.puntosVenta = [puntoEmisorA];

    const actualizacion = store.updatePuntoVenta(puntoEmisorA.id, {
      nombre: "PV actualizado emisor A",
    });
    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    setEmpresaActivaIdStorage(2);
    store.puntosVenta = [puntoEmisorB];
    actualizacionPendiente.resolve({
      ...puntoEmisorA,
      nombre: "PV actualizado emisor A",
    });
    await actualizacion;

    expect(store.puntosVenta).toEqual([puntoEmisorB]);
    expect(store.error).toBeNull();
  });
  it("ignora respuestas viejas cuando cambia el emisor activo", async () => {
    const primeraCarga = deferred<PuntoVenta[]>();
    const segundaCarga = deferred<PuntoVenta[]>();
    mockedPuntosVentaService.getAll
      .mockReturnValueOnce(primeraCarga.promise)
      .mockReturnValueOnce(segundaCarga.promise);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    const store = usePuntosVentaStore();

    const cargaA = store.fetchPuntosVenta();
    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    const cargaB = store.fetchPuntosVenta();

    segundaCarga.resolve([puntoVentaMock(2, 2)]);
    await cargaB;
    expect(store.puntosVenta.map((punto) => punto.empresa_id)).toEqual([2]);

    primeraCarga.resolve([puntoVentaMock(1, 1)]);
    await cargaA;
    expect(store.puntosVenta.map((punto) => punto.empresa_id)).toEqual([2]);
  });
});
