import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import reportesService from "@/services/reportes.service";
import { useEmpresaStore } from "@/stores/empresa";
import type { Empresa } from "@/types/empresa";
import type { ReporteVentas } from "@/services/reportes.service";
import ReporteVentasView from "./ReporteVentasView.vue";

vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("@/services/reportes.service", () => ({
  default: {
    obtenerReporteVentas: vi.fn(),
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

const reporteVentasMock = (clienteNombre: string): ReporteVentas => ({
  resumen: {
    total_facturas: 1210,
    total_notas_credito: 0,
    total_notas_debito: 0,
    total_neto: 1210,
    cantidad_comprobantes: 1,
    periodo: { desde: "2026-05-01", hasta: "2026-05-31" },
  },
  comprobantes: [
    {
      id: 1,
      fecha_emision: "2026-05-15",
      tipo_comprobante: 6,
      tipo_nombre: "Factura B",
      letra: "B",
      punto_venta: 1,
      numero: 1,
      numero_completo: "0001-00000001",
      cliente_nombre: clienteNombre,
      subtotal: 1000,
      iva_total: 210,
      total: 1210,
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
  obtenerReporteVentas: Mock;
};

describe("ReporteVentasView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ignora respuestas viejas despues de cambiar el emisor activo", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    const primeraCarga = deferred<ReporteVentas>();
    const segundaCarga = deferred<ReporteVentas>();
    mockedReportesService.obtenerReporteVentas
      .mockReturnValueOnce(primeraCarga.promise)
      .mockReturnValueOnce(segundaCarga.promise);
    const wrapper = mount(ReporteVentasView, { global: { plugins: [pinia] } });
    await flushPromises();
    const vm = wrapper.vm as unknown as { generarReporte: () => Promise<void> };

    const cargaA = vm.generarReporte();
    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    const cargaB = vm.generarReporte();

    segundaCarga.resolve(reporteVentasMock("Cliente B"));
    await cargaB;
    await flushPromises();
    expect(wrapper.text()).toContain("Cliente B");

    primeraCarga.resolve(reporteVentasMock("Cliente A"));
    await cargaA;
    await flushPromises();
    expect(wrapper.text()).toContain("Cliente B");
    expect(wrapper.text()).not.toContain("Cliente A");
  });
});
