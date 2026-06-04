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
import type {
  LoteComprobante,
  LoteComprobanteGrupoDetalle,
  LoteComprobanteGruposPage,
  LoteComprobanteResumen,
} from "@/types/lote-comprobante";
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
    obtenerResumen: vi.fn(),
    obtenerGrupos: vi.fn(),
    reintentarFallidos: vi.fn(),
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
const mockedLotesDetalle = lotesComprobantesService as unknown as {
  listar: Mock;
  obtener: Mock;
  obtenerResumen: Mock;
  obtenerGrupos: Mock;
  procesar: Mock;
  reintentarFallidos: Mock;
};
const mockedPerfiles = perfilesCargaMasivaService as unknown as {
  listar: Mock;
};
const mockedPuntosVenta = puntosVentaService as unknown as { getAll: Mock };

const loteResumenMock = (): LoteComprobanteResumen => ({
  id: 12,
  nombre_archivo: "lote-grande.xlsx",
  archivo_hash: "hash-lote-grande",
  estado: "validado",
  modo_procesamiento: "background",
  procesamiento_async: true,
  total_filas: 1432,
  total_grupos: 1432,
  grupos_validos: 1432,
  grupos_con_error: 0,
  grupos_emitidos: 0,
  grupos_fallidos: 0,
  grupos_reconciliados_externos: 0,
  grupos_descartados: 0,
  mensaje_resumen: "El lote se validó correctamente y puede emitirse.",
  metadata_json: null,
  mapeo_usado_json: null,
  headers_detectados_json: null,
  started_at: null,
  finished_at: null,
  compactado_at: null,
  created_at: "2026-05-01T00:00:00",
  updated_at: "2026-05-01T00:00:00",
  empresa_id: 1,
  usuario_id: 1,
  formato_importacion_id: null,
  formato_importacion_version_id: null,
  confirmacion_fecha_fiscal: "fechas=2026-05-20;puntos_venta=1",
  mensaje_confirmacion_fecha_fiscal:
    "Está seguro que quiere emitir comprobantes con fecha 20/05/26 para el punto de venta 0001? Recuerde que luego no podrá emitir comprobantes con fecha anterior para ese mismo punto de venta.",
  confirmacion_reintento_fallidos: "",
  mensaje_confirmacion_reintento_fallidos:
    "No hay comprobantes pendientes con fecha fiscal para confirmar.",
  confirmacion_duplicado_logico: "",
  mensaje_confirmacion_duplicado_logico: "",
  cantidad_duplicados_logicos: 0,
  fechas_emision_validas: ["2026-05-20"],
  puntos_venta_validos: [1],
  totales_listos_para_emitir: {
    comprobantes: 1432,
    neto: 1432000,
    iva21: 300720,
    iva105: 0,
    total: 1732720,
    valores_invalidos: 0,
  },
});

const grupoDetalleMock = (): LoteComprobanteGrupoDetalle => ({
  id: 21,
  comprobante_ref: "LOTE-001",
  orden: 1,
  estado: "validado",
  tipo_comprobante: 6,
  concepto: 1,
  punto_venta_numero: 1,
  cliente_documento: "20409378472",
  cliente_razon_social: "Cliente Lote SA",
  fecha_emision: "2026-05-20",
  fecha_servicio_desde: null,
  fecha_servicio_hasta: null,
  fecha_vto_pago: null,
  total_estimado: 1210,
  mensajes_json: ["Validado correctamente. Listo para emitir."],
  cae: null,
  numero_asignado: null,
  comprobante_id: null,
  descripcion_facturada: "Servicio mensual",
});

const gruposPageMock = (): LoteComprobanteGruposPage => ({
  items: [grupoDetalleMock()],
  page: 1,
  per_page: 100,
  total: 1432,
  total_pages: 15,
  estado: null,
});

const mountView = async (
  perfiles: PerfilCargaMasiva[] = [],
  lotesIniciales: LoteComprobante[] = [],
  resumen: LoteComprobanteResumen = loteResumenMock(),
) => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const empresaStore = useEmpresaStore();
  empresaStore.empresa = empresaMock();
  empresaStore.empresaActivaId = 1;

  mockedFormatos.listar.mockResolvedValue([formatoMock()]);
  mockedLotesDetalle.listar.mockResolvedValue(lotesIniciales);
  mockedLotesDetalle.obtenerResumen.mockResolvedValue(resumen);
  mockedLotesDetalle.obtenerGrupos.mockResolvedValue(gruposPageMock());
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

  it("abre lotes grandes con resumen y pagina de grupos", async () => {
    const lote = loteResumenMock();
    const wrapper = await mountView([], [lote]);

    expect(mockedLotesDetalle.obtener).not.toHaveBeenCalled();
    expect(mockedLotesDetalle.obtenerResumen).toHaveBeenCalledWith(lote.id);
    expect(mockedLotesDetalle.obtenerGrupos).toHaveBeenCalledWith(lote.id, {
      page: 1,
      perPage: 100,
      estado: null,
    });
    expect(wrapper.text()).toContain("Mostrando 1 a 100 de 1432 comprobantes");
    expect(wrapper.text()).toContain("El resumen fiscal considera el lote completo");
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
  });

  it("muestra aviso cuando ARCA degrada el lote a emisión unitaria", async () => {
    const lote = loteResumenMock();
    const resumen = {
      ...lote,
      metadata_json: {
        arca_batch: {
          modo: "unitario_fallback",
          reg_x_req: null,
          chunk_size: 1,
          fallback_unitario: true,
          fallback_motivo: "ARCA no devolvió RegXReq",
        },
      },
    };

    const wrapper = await mountView([], [lote], resumen);

    expect(wrapper.text()).toContain(
      "ARCA no informó la capacidad máxima por request",
    );
    expect(wrapper.text()).toContain("ARCA no devolvió RegXReq");
  });

  it("envia una clave de idempotencia al procesar un lote", async () => {
    const lote = loteResumenMock();
    mockedLotesDetalle.procesar.mockResolvedValue({
      lote,
      mensaje: "El lote quedó en cola.",
      en_progreso: true,
    });
    const wrapper = await mountView([], [lote]);
    const vm = wrapper.vm as unknown as {
      procesarLote: () => Promise<void>;
    };

    await vm.procesarLote();

    expect(mockedLotesDetalle.procesar).toHaveBeenCalledWith(
      lote.id,
      lote.confirmacion_fecha_fiscal,
      expect.any(String),
      undefined,
    );
  });

  it("renueva la clave de idempotencia despues de reintentar fallidos", async () => {
    const lote = {
      ...loteResumenMock(),
      grupos_validos: 0,
      grupos_fallidos: 1,
      confirmacion_reintento_fallidos: "fechas=2026-05-20;puntos_venta=1",
      mensaje_confirmacion_reintento_fallidos:
        "Está seguro que quiere emitir comprobantes con fecha 20/05/26 para el punto de venta 0001?",
    };
    mockedLotesDetalle.reintentarFallidos.mockResolvedValue({
      lote,
      mensaje: "Reintento finalizado",
    });
    const wrapper = await mountView([], [lote], lote);
    const vm = wrapper.vm as unknown as {
      reintentarFallidos: () => Promise<void>;
    };

    await vm.reintentarFallidos();
    await vm.reintentarFallidos();

    const primeraClave = mockedLotesDetalle.reintentarFallidos.mock.calls[0][3];
    const segundaClave = mockedLotesDetalle.reintentarFallidos.mock.calls[1][3];
    expect(primeraClave).toEqual(expect.any(String));
    expect(segundaClave).toEqual(expect.any(String));
    expect(segundaClave).not.toBe(primeraClave);
  });
});
