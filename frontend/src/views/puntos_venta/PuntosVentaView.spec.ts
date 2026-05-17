import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { arcaService, type ArcaStatus } from "@/services/arca.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import type { Empresa } from "@/types/empresa";
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

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => ({
    showSuccess: vi.fn(),
    showError: vi.fn(),
    showWarning: vi.fn(),
  }),
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

const statusMock = (
  ambiente: "homologacion" | "produccion",
  certificadoActivo: boolean,
): ArcaStatus => ({
  ambiente,
  certificado_activo: certificadoActivo,
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
};
const mockedPuntosVentaService = puntosVentaService as unknown as {
  getAll: Mock;
};

describe("PuntosVentaView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
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
    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    await flushPromises();

    segundaCarga.resolve(statusMock("produccion", true));
    await flushPromises();
    const vm = wrapper.vm as unknown as {
      tieneCertificadoActivo: boolean;
      ambienteArcaActual: "homologacion" | "produccion" | null;
    };
    expect(vm.tieneCertificadoActivo).toBe(true);
    expect(vm.ambienteArcaActual).toBe("produccion");

    primeraCarga.resolve(statusMock("homologacion", false));
    await flushPromises();
    expect(vm.tieneCertificadoActivo).toBe(true);
    expect(vm.ambienteArcaActual).toBe("produccion");
  });
});
