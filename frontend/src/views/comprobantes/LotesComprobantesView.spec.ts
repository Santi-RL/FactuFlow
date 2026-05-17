import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import formatosImportacionService from "@/services/formatos-importacion.service";
import lotesComprobantesService from "@/services/lotes-comprobantes.service";
import perfilesCargaMasivaService from "@/services/perfiles-carga-masiva.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import type {
  FormatoImportacion,
  FormatoImportacionDeteccion,
} from "@/types/formato-importacion";
import type { PerfilCargaMasiva } from "@/types/perfil-carga-masiva";
import type { Empresa } from "@/types/empresa";
import LotesComprobantesView from "./LotesComprobantesView.vue";

vi.mock("@/services/formatos-importacion.service", () => ({
  default: {
    listar: vi.fn(),
    detectar: vi.fn(),
  },
}));

vi.mock("@/services/lotes-comprobantes.service", () => ({
  default: {
    listar: vi.fn(),
    validar: vi.fn(),
    procesar: vi.fn(),
    obtener: vi.fn(),
  },
}));

vi.mock("@/services/perfiles-carga-masiva.service", () => ({
  default: {
    listar: vi.fn(),
  },
}));

vi.mock("@/services/puntos_venta.service", () => ({
  puntosVentaService: {
    getAll: vi.fn(),
  },
}));

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => ({
    showError: vi.fn(),
    showInfo: vi.fn(),
    showSuccess: vi.fn(),
    showWarning: vi.fn(),
  }),
}));

const formatoMock = (): FormatoImportacion => ({
  id: 1,
  nombre: "Formato Base",
  descripcion: null,
  alcance: "empresa",
  activo: true,
  empresa_id: 1,
  created_at: "2026-05-01T00:00:00",
  updated_at: "2026-05-01T00:00:00",
  version_vigente: {
    id: 10,
    version: 1,
    estado: "vigente",
    configuracion_json: {},
    headers_firma_json: null,
    created_at: "2026-05-01T00:00:00",
  },
});

const empresaMock = (): Empresa => ({
  id: 1,
  razon_social: "Emisor Demo",
  cuit: "30700000001",
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

const perfilRelativoMock = (): PerfilCargaMasiva => ({
  id: 7,
  empresa_id: 1,
  nombre: "Servicios mensuales",
  descripcion: null,
  es_predeterminado: true,
  activo: true,
  created_at: "2026-05-01T00:00:00",
  updated_at: "2026-05-01T00:00:00",
  configuracion_json: {
    version: 1,
    formato_importacion_version_id: 10,
    punto_venta: { modo: "archivo", numero: null },
    concepto_modo: "servicios",
    descripcion_item_modo: "fija",
    descripcion_item_fija: "Abono",
    fecha_emision: { modo: "ultimo_dia_mes_anterior" },
    periodo_servicio: { modo: "mes_anterior_completo" },
    fecha_vto_pago: { modo: "emision_mas_dias", dias: 10 },
  },
});

const deteccionMock = (
  nombre: string,
  versionId: number,
  headers: string[],
): FormatoImportacionDeteccion => ({
  headers_detectados: headers,
  formato_sugerido_version_id: versionId,
  requiere_confirmacion: false,
  candidatos: [
    {
      formato_id: versionId,
      formato_version_id: versionId,
      nombre,
      alcance: "empresa",
      version: 1,
      score: 0.97,
      confianza: "alta",
      columnas_detectadas: headers,
      columnas_faltantes: [],
      mensajes: [],
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

const mockedFormatos = formatosImportacionService as unknown as {
  listar: Mock;
  detectar: Mock;
};
const mockedLotes = lotesComprobantesService as unknown as { listar: Mock };
const mockedPerfiles = perfilesCargaMasivaService as unknown as {
  listar: Mock;
};
const mockedPuntosVenta = puntosVentaService as unknown as { getAll: Mock };

const mountView = async (perfiles: PerfilCargaMasiva[] = []) => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const empresaStore = useEmpresaStore();
  empresaStore.empresa = empresaMock();
  empresaStore.empresaActivaId = 1;

  mockedFormatos.listar.mockResolvedValue([formatoMock()]);
  mockedLotes.listar.mockResolvedValue([]);
  mockedPerfiles.listar.mockResolvedValue(perfiles);
  mockedPuntosVenta.getAll.mockResolvedValue([]);

  const wrapper = mount(LotesComprobantesView, {
    global: {
      plugins: [pinia],
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });
  await flushPromises();
  return wrapper;
};

describe("LotesComprobantesView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ignora detecciones de formato resueltas fuera de orden", async () => {
    const archivoA = new File(["a"], "a.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const archivoB = new File(["b"], "b.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const deteccionA = deferred<FormatoImportacionDeteccion>();
    const deteccionB = deferred<FormatoImportacionDeteccion>();
    mockedFormatos.detectar.mockImplementation((archivo: File) =>
      archivo.name === "a.xlsx" ? deteccionA.promise : deteccionB.promise,
    );
    const wrapper = await mountView();
    const input = wrapper.find('input[type="file"]');

    Object.defineProperty(input.element, "files", {
      value: [archivoA],
      configurable: true,
    });
    await input.trigger("change");
    await flushPromises();
    Object.defineProperty(input.element, "files", {
      value: [archivoB],
      configurable: true,
    });
    await input.trigger("change");
    await flushPromises();

    deteccionB.resolve(deteccionMock("Formato B", 22, ["columna_b"]));
    await flushPromises();
    expect(wrapper.text()).toContain("Sugerencia: Formato B");
    expect(wrapper.text()).toContain("columna_b");

    deteccionA.resolve(deteccionMock("Formato A", 11, ["columna_a"]));
    await flushPromises();
    expect(wrapper.text()).toContain("Sugerencia: Formato B");
    expect(wrapper.text()).toContain("columna_b");
    expect(wrapper.text()).not.toContain("Sugerencia: Formato A");
    expect(wrapper.text()).not.toContain("columna_a");
  });

  it("autoaplica perfiles relativos sin materializar fecha fiscal implicita", async () => {
    const wrapper = await mountView([perfilRelativoMock()]);
    const vm = wrapper.vm as unknown as {
      fechaEmisionModo: string;
      fechaEmisionFija: string;
      fechaServicioDesdeModo: string;
      fechaServicioHastaModo: string;
      fechaVtoPagoModo: string;
    };

    expect(vm.fechaEmisionModo).toBe("");
    expect(vm.fechaEmisionFija).toBe("");
    expect(vm.fechaServicioDesdeModo).toBe("");
    expect(vm.fechaServicioHastaModo).toBe("");
    expect(vm.fechaVtoPagoModo).toBe("");
  });
});
