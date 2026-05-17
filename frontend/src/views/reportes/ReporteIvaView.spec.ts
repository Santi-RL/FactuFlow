import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import reportesService from "@/services/reportes.service";
import { useEmpresaStore } from "@/stores/empresa";
import type { Empresa } from "@/types/empresa";
import type { ReporteIVA } from "@/services/reportes.service";
import ReporteIvaView from "./ReporteIvaView.vue";

vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("@/services/reportes.service", () => ({
  default: {
    obtenerReporteIVA: vi.fn(),
  },
}));

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => ({
    showError: vi.fn(),
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

const reporteIvaMock = (nombre: string, gravado27 = 1000): ReporteIVA => ({
  resumen: {
    gravado_21: 0,
    iva_21: 0,
    gravado_10_5: 0,
    iva_10_5: 0,
    gravado_27: gravado27,
    iva_27: gravado27 * 0.27,
    no_gravado: 0,
    exento: 0,
    total_neto: gravado27,
    total_iva: gravado27 * 0.27,
    periodo: { mes: 5, anio: 2026, nombre: "Mayo 2026" },
  },
  comprobantes: [
    {
      fecha_emision: "2026-05-15",
      tipo_letra: "A",
      tipo_nombre: "Factura A",
      punto_venta: 1,
      numero: 1,
      numero_completo: "0001-00000001",
      cuit_receptor: "30700000001",
      razon_social_receptor: nombre,
      gravado_21: 0,
      iva_21: 0,
      gravado_10_5: 0,
      iva_10_5: 0,
      gravado_27: gravado27,
      iva_27: gravado27 * 0.27,
      no_gravado: 0,
      exento: 0,
      total: gravado27 * 1.27,
    },
  ],
});

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
};

const mockedReportesService = reportesService as unknown as {
  obtenerReporteIVA: Mock;
};

const mountView = async () => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const empresaStore = useEmpresaStore();
  empresaStore.empresa = empresaMock(1);
  empresaStore.empresaActivaId = 1;
  const wrapper = mount(ReporteIvaView, { global: { plugins: [pinia] } });
  await flushPromises();
  return { wrapper, empresaStore };
};

describe("ReporteIvaView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("muestra columnas y valores de IVA 27% en el detalle", async () => {
    mockedReportesService.obtenerReporteIVA.mockResolvedValue(
      reporteIvaMock("Cliente 27", 1000),
    );
    const { wrapper } = await mountView();
    const vm = wrapper.vm as unknown as { generarReporte: () => Promise<void> };

    await vm.generarReporte();
    await flushPromises();

    expect(wrapper.text()).toContain("Gravado 27%");
    expect(wrapper.text()).toContain("IVA 27%");
    expect(wrapper.text()).toContain("Cliente 27");
    expect(wrapper.text()).toContain("1.000,00");
    expect(wrapper.text()).toContain("270,00");
  });

  it("ignora respuestas viejas despues de cambiar el emisor activo", async () => {
    const primeraCarga = deferred<ReporteIVA>();
    const segundaCarga = deferred<ReporteIVA>();
    mockedReportesService.obtenerReporteIVA
      .mockReturnValueOnce(primeraCarga.promise)
      .mockReturnValueOnce(segundaCarga.promise);
    const { wrapper, empresaStore } = await mountView();
    const vm = wrapper.vm as unknown as { generarReporte: () => Promise<void> };

    const cargaA = vm.generarReporte();
    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    const cargaB = vm.generarReporte();

    segundaCarga.resolve(reporteIvaMock("Cliente B", 2000));
    await cargaB;
    await flushPromises();
    expect(wrapper.text()).toContain("Cliente B");

    primeraCarga.resolve(reporteIvaMock("Cliente A", 1000));
    await cargaA;
    await flushPromises();
    expect(wrapper.text()).toContain("Cliente B");
    expect(wrapper.text()).not.toContain("Cliente A");
  });
});
