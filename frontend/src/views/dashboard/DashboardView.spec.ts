import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import certificadosService from "@/services/certificados.service";
import { clientesService } from "@/services/clientes.service";
import comprobantesService from "@/services/comprobantes.service";
import reportesService from "@/services/reportes.service";
import { useEmpresaStore } from "@/stores/empresa";
import type { Certificado } from "@/types/certificado";
import type { Empresa } from "@/types/empresa";
import type { ReporteVentas } from "@/services/reportes.service";
import DashboardView from "./DashboardView.vue";

vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("@/services/clientes.service", () => ({
  clientesService: {
    getAll: vi.fn(),
  },
}));

vi.mock("@/services/certificados.service", () => ({
  default: {
    obtenerAlertasVencimiento: vi.fn(),
    listar: vi.fn(),
  },
}));

vi.mock("@/services/comprobantes.service", () => ({
  default: {
    listar: vi.fn(),
  },
}));

vi.mock("@/services/reportes.service", () => ({
  default: {
    obtenerReporteVentas: vi.fn(),
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

const certificadoMock = (): Certificado => ({
  id: 1,
  nombre: "Certificado",
  cuit: "30700000001",
  fecha_emision: "2026-01-01",
  fecha_vencimiento: "2027-01-01",
  ambiente: "homologacion",
  archivo_crt: "cert.crt",
  archivo_key: "cert.key",
  activo: true,
  empresa_id: 1,
  created_at: "2026-01-01T00:00:00",
  updated_at: "2026-01-01T00:00:00",
  dias_restantes: 200,
  estado: "valido",
});

const reporteVentasMock = (cantidad: number): ReporteVentas => ({
  resumen: {
    total_facturas: 0,
    total_notas_credito: 0,
    total_notas_debito: 0,
    total_neto: 0,
    cantidad_comprobantes: cantidad,
    periodo: { desde: "2026-05-01", hasta: "2026-05-31" },
  },
  comprobantes: [],
});

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
};

const mockedClientesService = clientesService as unknown as { getAll: Mock };
const mockedCertificadosService = certificadosService as unknown as {
  obtenerAlertasVencimiento: Mock;
  listar: Mock;
};
const mockedComprobantesService = comprobantesService as unknown as {
  listar: Mock;
};
const mockedReportesService = reportesService as unknown as {
  obtenerReporteVentas: Mock;
};

describe("DashboardView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ignora cargas viejas despues de cambiar el emisor activo", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    mockedClientesService.getAll.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      per_page: 100,
      pages: 0,
    });
    mockedCertificadosService.obtenerAlertasVencimiento.mockResolvedValue([]);
    mockedCertificadosService.listar.mockResolvedValue([certificadoMock()]);
    mockedComprobantesService.listar.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      per_page: 1,
      pages: 0,
    });
    const primeraCarga = deferred<ReporteVentas>();
    const segundaCarga = deferred<ReporteVentas>();
    mockedReportesService.obtenerReporteVentas
      .mockReturnValueOnce(primeraCarga.promise)
      .mockReturnValueOnce(segundaCarga.promise);
    const wrapper = mount(DashboardView, {
      global: {
        plugins: [pinia],
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();
    const vm = wrapper.vm as unknown as { totalComprobantesMes: number };

    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    await flushPromises();

    segundaCarga.resolve(reporteVentasMock(22));
    await flushPromises();
    expect(vm.totalComprobantesMes).toBe(22);

    primeraCarga.resolve(reporteVentasMock(11));
    await flushPromises();
    expect(vm.totalComprobantesMes).toBe(22);
  });
});
