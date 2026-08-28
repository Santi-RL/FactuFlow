import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import { usePuntosVentaStore } from "@/stores/puntos_venta";
import type { Empresa } from "@/types/empresa";
import type {
  ImportarPuntosVentaResponse,
  PuntoVenta,
  SincronizarPuntosVentaResponse,
} from "@/types/punto_venta";
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
    sincronizarArca: vi.fn(),
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
  puede_intentar_emision: true,
  ultima_comprobacion_arca_en: "2026-08-09T15:00:00Z",
  comprobacion_arca_desactualizada: false,
  revision_fiscal: 1,
  elegibilidad_rece: {
    ambiente: "produccion",
    estado: "verificado_rece",
    estado_efectivo: "verificado_rece",
    fuente: "constancia_arca_atestada",
    revision_id: 1,
    revision: 1,
    punto_revision_fiscal: 1,
    verificado_en: "2026-08-09T12:00:00-03:00",
    vigente_hasta: null,
    motivo: null,
  },
  empresa_id: empresaId,
  created_at: "2024-01-01T00:00:00",
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
  importarConstancia: Mock;
  sincronizarArca: Mock;
};

const syncResponseMock = (): SincronizarPuntosVentaResponse => ({
  total_arca: 2,
  nuevos: 1,
  existentes: 1,
  actualizados: 1,
  desactivados_ausentes: 1,
  comprobado_en: "2026-08-28T12:00:00Z",
});

const importResponseMock = (): ImportarPuntosVentaResponse => ({
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
});

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

    expect(mockedPuntosVentaService.sincronizarArca).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.getAll).not.toHaveBeenCalled();
    expect(store.error).toBe(mensaje);
    expect(store.syncing).toBe(false);
  });

  it("sincroniza en una sola operación transaccional y refresca el listado", async () => {
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const resultadoEsperado = syncResponseMock();
    const puntosActualizados = [
      puntoVentaMock(1, 1),
      { ...puntoVentaMock(1, 2), activo: false, usable_factuflow: false },
    ];
    mockedPuntosVentaService.sincronizarArca.mockResolvedValue(
      resultadoEsperado,
    );
    mockedPuntosVentaService.getAll.mockResolvedValue(puntosActualizados);
    const store = usePuntosVentaStore();

    await expect(store.syncFromArca()).resolves.toEqual(resultadoEsperado);

    expect(mockedPuntosVentaService.sincronizarArca).toHaveBeenCalledTimes(1);
    expect(mockedPuntosVentaService.create).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.update).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.getAll).toHaveBeenCalledTimes(1);
    expect(store.puntosVenta).toEqual(puntosActualizados);
    expect(store.syncing).toBe(false);
  });

  it("ignora sincronizaciones ARCA obsoletas cuando cambia el emisor activo", async () => {
    const respuestaSync = deferred<SincronizarPuntosVentaResponse>();
    mockedPuntosVentaService.sincronizarArca.mockReturnValue(
      respuestaSync.promise,
    );
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
    respuestaSync.resolve(syncResponseMock());
    const resultado = await sincronizacion;

    expect(resultado).toEqual({
      total_arca: 0,
      nuevos: 0,
      existentes: 0,
      actualizados: 0,
      desactivados_ausentes: 0,
      comprobado_en: new Date(0).toISOString(),
    });
    expect(mockedPuntosVentaService.getAll).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.create).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.update).not.toHaveBeenCalled();
    expect(store.puntosVenta.map((punto) => punto.empresa_id)).toEqual([2]);
    expect(store.syncing).toBe(false);
    expect(store.error).toBeNull();
  });

  it("corta la sincronización si el scope de request se limpia durante cambio de emisor", async () => {
    const respuestaSync = deferred<SincronizarPuntosVentaResponse>();
    mockedPuntosVentaService.sincronizarArca.mockReturnValue(
      respuestaSync.promise,
    );
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const store = usePuntosVentaStore();

    const sincronizacion = store.syncFromArca();
    clearEmpresaActivaIdForRequest();
    respuestaSync.resolve(syncResponseMock());
    const resultado = await sincronizacion;

    expect(resultado).toEqual({
      total_arca: 0,
      nuevos: 0,
      existentes: 0,
      actualizados: 0,
      desactivados_ausentes: 0,
      comprobado_en: new Date(0).toISOString(),
    });
    expect(mockedPuntosVentaService.getAll).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.create).not.toHaveBeenCalled();
    expect(store.puntosVenta).toEqual([]);
    expect(store.syncing).toBe(false);
    expect(store.error).toBeNull();
  });

  it("ignora errores ARCA obsoletos si el scope de request se limpia durante cambio de emisor", async () => {
    const respuestaSync = deferred<SincronizarPuntosVentaResponse>();
    mockedPuntosVentaService.sincronizarArca.mockReturnValue(
      respuestaSync.promise,
    );
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const store = usePuntosVentaStore();

    const sincronizacion = store.syncFromArca();
    clearEmpresaActivaIdForRequest();
    respuestaSync.reject({
      response: { data: { detail: "ARCA no disponible" } },
    });
    const resultado = await sincronizacion;

    expect(resultado).toEqual({
      total_arca: 0,
      nuevos: 0,
      existentes: 0,
      actualizados: 0,
      desactivados_ausentes: 0,
      comprobado_en: new Date(0).toISOString(),
    });
    expect(store.error).toBeNull();
    expect(store.syncing).toBe(false);
  });

  it("importa una constancia por el camino seguro y refresca el listado", async () => {
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const file = new File(["PDF"], "constancia.pdf", {
      type: "application/pdf",
    });
    const resultadoEsperado = importResponseMock();
    const puntosActualizados = [puntoVentaMock(1, 1)];
    mockedPuntosVentaService.importarConstancia.mockResolvedValue(
      resultadoEsperado,
    );
    mockedPuntosVentaService.getAll.mockResolvedValue(puntosActualizados);
    const store = usePuntosVentaStore();

    await expect(store.importarConstancia(file)).resolves.toEqual(
      resultadoEsperado,
    );

    expect(mockedPuntosVentaService.importarConstancia).toHaveBeenCalledWith(
      file,
    );
    expect(mockedPuntosVentaService.getAll).toHaveBeenCalledTimes(1);
    expect(store.puntosVenta).toEqual(puntosActualizados);
    expect(store.importing).toBe(false);
  });

  it("no mezcla el refresh de una importación después de cambiar el emisor", async () => {
    const importacionPendiente = deferred<ImportarPuntosVentaResponse>();
    mockedPuntosVentaService.importarConstancia.mockReturnValue(
      importacionPendiente.promise,
    );
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const store = usePuntosVentaStore();
    const puntosEmisorB = [puntoVentaMock(2, 2)];
    store.puntosVenta = puntosEmisorB;

    const importacion = store.importarConstancia(
      new File(["PDF"], "constancia.pdf", { type: "application/pdf" }),
    );
    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    setEmpresaActivaIdStorage(2);
    importacionPendiente.resolve(importResponseMock());

    await expect(importacion).resolves.toEqual(importResponseMock());
    expect(mockedPuntosVentaService.getAll).not.toHaveBeenCalled();
    expect(store.puntosVenta).toEqual(puntosEmisorB);
    expect(store.error).toBeNull();
    expect(store.importing).toBe(false);
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
