import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { arcaService, type ArcaStatus } from "@/services/arca.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import type { Empresa } from "@/types/empresa";
import type { PuntoVenta, PuntoVentaArca } from "@/types/punto_venta";
import {
  clearEmpresaActivaIdForRequest,
  clearEmpresaActivaIdStorage,
  setEmpresaActivaIdStorage,
} from "@/utils/empresa-activa-storage";
import PuntosVentaView from "./PuntosVentaView.vue";

vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("@/services/arca.service", () => ({
  arcaService: {
    getStatus: vi.fn(),
    getPuntosVenta: vi.fn(),
  },
}));

vi.mock("@/services/puntos_venta.service", () => ({
  puntosVentaService: {
    getAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    importarConstancia: vi.fn(),
  },
}));

const notificationMocks = vi.hoisted(() => ({
  showSuccess: vi.fn(),
  showError: vi.fn(),
  showWarning: vi.fn(),
}));

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => notificationMocks,
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

const puntoVentaMock = (empresaId: number): PuntoVenta => ({
  id: empresaId,
  numero: empresaId,
  nombre: `Punto ${empresaId}`,
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
  created_at: "2026-01-01T00:00:00",
});

const statusMock = (
  ambiente: "homologacion" | "produccion",
  certificadoActivo: boolean,
  certificadoDisponible = certificadoActivo,
): ArcaStatus => ({
  ambiente,
  certificado_activo: certificadoActivo,
  certificado_disponible: certificadoDisponible,
  certificado_id: certificadoActivo ? 1 : null,
  certificado_nombre: certificadoActivo ? "Certificado" : null,
  certificado_vencimiento: certificadoActivo ? "2027-01-01" : null,
});

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
};

const mockedArcaService = arcaService as unknown as {
  getStatus: Mock;
  getPuntosVenta: Mock;
};
const mockedPuntosVentaService = puntosVentaService as unknown as {
  getAll: Mock;
  create: Mock;
  update: Mock;
  importarConstancia: Mock;
};

describe("PuntosVentaView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
    clearEmpresaActivaIdStorage();
  });

  it("no muestra éxito de una sincronización obsoleta si el cambio de emisor está en curso", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const puntosArca = deferred<PuntoVentaArca[]>();
    const locales = deferred<PuntoVenta[]>();
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true),
    );
    mockedArcaService.getPuntosVenta.mockReturnValue(puntosArca.promise);
    mockedPuntosVentaService.getAll
      .mockResolvedValueOnce([])
      .mockReturnValueOnce(locales.promise);
    mockedPuntosVentaService.create.mockResolvedValue({});
    mockedPuntosVentaService.update.mockResolvedValue({});
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    const vm = wrapper.vm as unknown as {
      sincronizar: () => Promise<void>;
      tieneCertificadoDisponible: boolean;
    };
    expect(vm.tieneCertificadoDisponible).toBe(true);

    const sincronizacion = vm.sincronizar();
    clearEmpresaActivaIdForRequest();
    puntosArca.resolve([
      {
        numero: 6,
        emision_tipo: "CAE - Factura Electronica",
        bloqueado: "N",
        fecha_baja: null,
      },
    ]);
    locales.resolve([]);
    await sincronizacion;

    expect(notificationMocks.showSuccess).not.toHaveBeenCalled();
    expect(notificationMocks.showError).not.toHaveBeenCalled();
  });

  it("no muestra una importación obsoleta después de cambiar el emisor", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const importacionPendiente = deferred<{
      total_constancia: number;
      creados: number;
      actualizados: number;
    }>();
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    mockedPuntosVentaService.importarConstancia.mockReturnValue(
      importacionPendiente.promise,
    );
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    const input = document.createElement("input");
    Object.defineProperty(input, "files", {
      value: [new File(["PDF"], "constancia.pdf", { type: "application/pdf" })],
    });
    const vm = wrapper.vm as unknown as {
      importarConstancia: (event: Event) => Promise<void>;
    };
    const importacion = vm.importarConstancia({ target: input } as unknown as Event);

    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    setEmpresaActivaIdStorage(2);
    importacionPendiente.resolve({
      total_constancia: 1,
      creados: 1,
      actualizados: 0,
    });
    await importacion;

    expect(notificationMocks.showSuccess).not.toHaveBeenCalled();
    expect(notificationMocks.showError).not.toHaveBeenCalled();
    expect(input.value).toBe("");
  });

  it("ignora estados ARCA viejos despues de cambiar el emisor activo", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const primeraCarga = deferred<ArcaStatus>();
    const segundaCarga = deferred<ArcaStatus>();
    mockedArcaService.getStatus
      .mockReturnValueOnce(primeraCarga.promise)
      .mockReturnValueOnce(segundaCarga.promise);
    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    setEmpresaActivaIdStorage(2);
    await flushPromises();

    segundaCarga.resolve(statusMock("produccion", true));
    await flushPromises();
    const vm = wrapper.vm as unknown as {
      tieneCertificadoDisponible: boolean;
      ambienteArcaActual: "homologacion" | "produccion" | null;
    };
    expect(vm.tieneCertificadoDisponible).toBe(true);
    expect(vm.ambienteArcaActual).toBe("produccion");

    primeraCarga.resolve(statusMock("homologacion", false));
    await flushPromises();
    expect(vm.tieneCertificadoDisponible).toBe(true);
    expect(vm.ambienteArcaActual).toBe("produccion");
  });

  it("deshabilita sincronizar si el certificado activo no tiene archivos locales", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true, false),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);

    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    const sincronizarButton = wrapper
      .findAll("button")
      .find((button) => button.text().includes("Sincronizar con ARCA"));
    expect(sincronizarButton).toBeDefined();
    expect(sincronizarButton?.attributes("disabled")).toBeDefined();
    const vm = wrapper.vm as unknown as {
      sincronizar: () => Promise<void>;
      tieneCertificadoDisponible: boolean;
    };
    expect(vm.tieneCertificadoDisponible).toBe(false);

    await vm.sincronizar();

    expect(mockedArcaService.getPuntosVenta).not.toHaveBeenCalled();
    expect(notificationMocks.showWarning).toHaveBeenCalledWith(
      "Certificado no disponible",
      expect.stringContaining("Cargá un certificado o restaurá sus archivos"),
    );
  });

  it("cierra el editor pendiente al cambiar de emisor", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const punto = puntoVentaMock(1);
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([punto]);
    mockedPuntosVentaService.update.mockResolvedValue(punto);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);

    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();
    const vm = wrapper.vm as unknown as {
      editarPunto: (punto: PuntoVenta) => void;
      guardarEdicion: () => Promise<void>;
      puntoEditando: PuntoVenta | null;
    };

    vm.editarPunto(punto);
    expect(vm.puntoEditando?.id).toBe(punto.id);

    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    setEmpresaActivaIdStorage(2);
    await flushPromises();

    expect(vm.puntoEditando).toBeNull();
    await vm.guardarEdicion();
    expect(mockedPuntosVentaService.update).not.toHaveBeenCalled();
  });

  it("no consulta puntos ni ARCA sin emisor activo", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const empresaStore = useEmpresaStore();
    empresaStore.inicializarEmpresaActiva = vi.fn().mockResolvedValue(undefined);

    mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    expect(mockedPuntosVentaService.getAll).not.toHaveBeenCalled();
    expect(mockedArcaService.getStatus).not.toHaveBeenCalled();

    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", false),
    );
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    await flushPromises();

    expect(mockedPuntosVentaService.getAll).toHaveBeenCalledTimes(1);
    expect(mockedArcaService.getStatus).toHaveBeenCalledTimes(1);
  });
});
