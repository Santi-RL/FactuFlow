import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import { usePuntosVentaStore } from "@/stores/puntos_venta";
import type { Empresa } from "@/types/empresa";
import type { PuntoVenta } from "@/types/punto_venta";

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

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
};

const mockedPuntosVentaService = puntosVentaService as unknown as {
  getAll: Mock;
};

describe("puntos venta store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
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
