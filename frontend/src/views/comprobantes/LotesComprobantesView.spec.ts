import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";

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
import type { PuntoVenta } from "@/types/punto_venta";
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
    descargar: vi.fn(),
  },
}));

vi.mock("@/services/lotes-comprobantes.service", () => ({
  default: {
    listar: vi.fn(),
    validar: vi.fn(),
    procesar: vi.fn(),
    obtener: vi.fn(),
    obtenerResumen: vi.fn(),
    obtenerSeguimiento: vi.fn(),
    obtenerGrupos: vi.fn(),
    obtenerCoincidencias: vi.fn(),
    reintentarFallidos: vi.fn(),
    descartarGrupos: vi.fn(),
    descargarPlantilla: vi.fn(),
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

const notificationMock = vi.hoisted(() => ({
  showError: vi.fn(),
  showInfo: vi.fn(),
  showSuccess: vi.fn(),
  showWarning: vi.fn(),
}));

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => notificationMock,
}));

const CUIT_EMISOR_TEST_NO_REAL = ["30", "70000000", "1"].join("");
const CUIT_RECEPTOR_TEST_NO_REAL = ["20", "40937847", "2"].join("");

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
  cuit: CUIT_EMISOR_TEST_NO_REAL,
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
    fecha_emision: { modo: "ultimo_dia_mes_anterior" as never },
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
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolver, rechazar) => {
    resolve = resolver;
    reject = rechazar;
  });
  return { promise, reject, resolve };
};

const puntoVentaMock = (numero: number, empresaId: number): PuntoVenta => ({
  id: empresaId * 100 + numero,
  numero,
  nombre: `Punto ${numero}`,
  sistema: "RECE",
  domicilio: null,
  domicilio_fuente: null,
  nombre_fantasia: null,
  nombre_fantasia_fuente: null,
  es_webservice: true,
  bloqueado: false,
  fecha_baja: null,
  fuente: "arca",
  activo: true,
  usar_en_factuflow: true,
  usable_factuflow: true,
  puede_intentar_emision: true,
  seleccionable_para_emision: true,
  ultima_comprobacion_arca_en: "2026-08-01T12:00:00Z",
  comprobacion_arca_desactualizada: false,
  revision_fiscal: 1,
  elegibilidad_rece: {
    ambiente: "produccion",
    estado: "verificado_rece",
    estado_efectivo: "verificado_rece",
    fuente: "constancia_arca",
    revision_id: 1,
    revision: 1,
    punto_revision_fiscal: 1,
    verificado_en: "2026-08-01T12:00:00Z",
    vigente_hasta: null,
    motivo: null,
  },
  empresa_id: empresaId,
  created_at: "2026-08-01T12:00:00Z",
});

const mockedFormatos = formatosImportacionService as unknown as {
  listar: Mock;
  detectar: Mock;
  descargar: Mock;
};
const mockedLotesDetalle = lotesComprobantesService as unknown as {
  listar: Mock;
  validar: Mock;
  obtener: Mock;
  obtenerResumen: Mock;
  obtenerSeguimiento: Mock;
  obtenerGrupos: Mock;
  obtenerCoincidencias: Mock;
  procesar: Mock;
  reintentarFallidos: Mock;
  descartarGrupos: Mock;
  descargarPlantilla: Mock;
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
  control_duplicados: {
    version: "duplicados_lotes/v2",
    cobertura: "completa",
    estado: "sin_coincidencias",
    evidencia_id: null,
    datos_hash: "datos-lote-12",
    seleccion_hash: "seleccion-lote-12",
    tipos_coincidencia: [],
    cantidad_actual: 1432,
    cantidad_afectada: 0,
    importe_actual: "1732720.00",
    importe_afectado: "0.00",
    importes_actuales: {
      por_moneda: [{ moneda: "PES", importe: "1732720.00", cantidad: 1432 }],
      cantidad_sin_moneda_acreditada: 0,
    },
    importes_afectados: {
      por_moneda: [],
      cantidad_sin_moneda_acreditada: 0,
    },
    antecedentes_resumen: [],
    aceptacion_requerida: false,
    aceptacion_habilitada: false,
    bloqueo_operacion_ajena: null,
    detalle_url: null,
  },
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

const loteActivoMock = (
  overrides: Partial<LoteComprobanteResumen> = {},
): LoteComprobanteResumen => ({
  ...loteResumenMock(),
  estado: "procesando",
  grupos_validos: 1431,
  grupos_emitidos: 1,
  started_at: "2026-05-01T00:00:00",
  ...overrides,
});

const grupoDetalleMock = (): LoteComprobanteGrupoDetalle => ({
  id: 21,
  comprobante_ref: "LOTE-001",
  orden: 1,
  estado: "validado",
  tipo_comprobante: 6,
  concepto: 1,
  punto_venta_numero: 1,
  cliente_documento: CUIT_RECEPTOR_TEST_NO_REAL,
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
  grupos: LoteComprobanteGruposPage = gruposPageMock(),
  puntosVentaIniciales: PuntoVenta[] | Promise<PuntoVenta[]> = [],
  attachTo?: Element,
) => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const empresaStore = useEmpresaStore();
  empresaStore.empresa = empresaMock();
  empresaStore.empresaActivaId = 1;

  mockedFormatos.listar.mockResolvedValue([formatoMock()]);
  mockedLotesDetalle.listar.mockResolvedValue(lotesIniciales);
  mockedLotesDetalle.validar.mockResolvedValue({
    lote: resumen,
    mensaje: "El lote se validó correctamente.",
    requiere_background: false,
  });
  mockedLotesDetalle.obtenerResumen.mockResolvedValue(resumen);
  mockedLotesDetalle.obtenerSeguimiento.mockResolvedValue(resumen);
  mockedLotesDetalle.obtenerGrupos.mockResolvedValue(grupos);
  mockedLotesDetalle.obtenerCoincidencias.mockResolvedValue({
    items: [],
    page: 1,
    per_page: 50,
    total: 0,
    total_pages: 0,
  });
  mockedPerfiles.listar.mockResolvedValue(perfiles);
  mockedPuntosVenta.getAll.mockReturnValue(
    Promise.resolve(puntosVentaIniciales),
  );

  const wrapper = mount(LotesComprobantesView, {
    attachTo,
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

  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it.each(["requiere_confirmacion", "operacion_en_curso"] as const)(
    "presenta totales y filas de forma neutral con duplicados en estado %s sin impedir el primer POST",
    async (estadoDuplicados) => {
      const control = {
        ...loteResumenMock().control_duplicados,
        estado: estadoDuplicados,
        evidencia_id: "v2.evidencia-mensajes",
        tipos_coincidencia: ["historica_completa" as const],
        cantidad_afectada: 1,
        aceptacion_requerida: estadoDuplicados === "requiere_confirmacion",
        aceptacion_habilitada: estadoDuplicados === "requiere_confirmacion",
        bloqueo_operacion_ajena:
          estadoDuplicados === "operacion_en_curso"
            ? {
                referencia: "seguimiento-opaco",
                estado: "intento_en_curso" as const,
                cantidad_afectada: 1,
                detectado_at: null,
              }
            : null,
        detalle_url: "/api/lotes-comprobantes/12/coincidencias",
      };
      const lote = { ...loteResumenMock(), control_duplicados: control };
      mockedLotesDetalle.procesar.mockRejectedValueOnce({
        response: {
          status: 409,
          data: {
            detail: {
              categoria_error:
                estadoDuplicados === "operacion_en_curso"
                  ? "duplicado_operacion_en_curso"
                  : "duplicado_logico_lote",
              control_duplicados: control,
              ...(estadoDuplicados === "requiere_confirmacion"
                ? { aceptacion_id: "v2.aceptacion-mensajes" }
                : {}),
            },
          },
        },
      });
      const wrapper = await mountView([], [lote], lote, {
        ...gruposPageMock(),
        items: [{ ...grupoDetalleMock(), mensajes_json: [] }],
      });

      const totals = wrapper.get('[data-testid="totales-lote"]');
      expect(totals.text()).toContain("Totales preparados para revisión");
      expect(totals.text().replace(/\u00a0/g, " ")).toContain(
        "$ 1.732.720,00",
      );
      expect(totals.classes()).not.toContain("bg-status-success-soft");
      expect(wrapper.text()).not.toContain("Totales listos para emitir");
      expect(wrapper.text()).not.toContain(
        "El lote se validó correctamente y puede emitirse.",
      );
      expect(wrapper.text()).toContain(
        "El lote se validó correctamente. La revisión de coincidencias sigue pendiente.",
      );
      expect(wrapper.text()).not.toContain("Sin observaciones");
      expect(wrapper.text()).toContain(
        "Sin errores de validación en este comprobante. La revisión general de coincidencias del lote sigue pendiente.",
      );
      expect(wrapper.get('[data-testid="lote-reciente-12"]').text()).toContain(
        "1432 comprobantes validados",
      );
      expect(wrapper.get('[data-testid="lote-reciente-12"]').text()).not.toContain(
        "1432 listos",
      );

      const emitButton = wrapper
        .findAll("button")
        .find((button) => button.text().includes("Emitir comprobantes válidos"));
      expect(emitButton?.attributes("disabled")).toBeUndefined();
      await emitButton?.trigger("click");
      await flushPromises();
      const fiscalConfirm = Array.from(
        document.body.querySelectorAll("button"),
      ).find((button) => button.textContent?.includes("Emitir con esta fecha"));
      (fiscalConfirm as HTMLButtonElement).click();
      await flushPromises();
      expect(mockedLotesDetalle.procesar).toHaveBeenCalledTimes(1);

      wrapper.unmount();
    },
  );

  it("usa singular en el aviso y neutraliza la métrica lateral del lote actual pendiente", async () => {
    const base = loteResumenMock();
    const lote = {
      ...base,
      total_grupos: 1,
      grupos_validos: 1,
      control_duplicados: {
        ...base.control_duplicados,
        estado: "requiere_confirmacion" as const,
        cantidad_actual: 1,
        cantidad_afectada: 1,
      },
    };
    const wrapper = await mountView([], [lote], lote);

    expect(wrapper.get('[data-testid="resumen-control-duplicados"]').text()).toContain(
      "1 de 1 comprobante:",
    );
    const actual = wrapper.get('[data-testid="lote-reciente-12"]');
    expect(actual.text()).toContain("1 comprobante validado");
    expect(actual.text()).not.toContain("1 listo");

    wrapper.unmount();
  });

  it.each([
    {
      estado: "requiere_reconciliacion",
      gruposConError: 1,
      gruposFallidos: 1,
      esperado: "3 pendientes",
    },
    {
      estado: "con_errores",
      gruposConError: 2,
      gruposFallidos: 0,
      esperado: "2 observados",
    },
    {
      estado: "autorizado_parcial",
      gruposConError: 1,
      gruposFallidos: 0,
      esperado: "2 pendientes",
    },
  ])(
    "preserva la métrica operativa $estado aunque el control actual esté pendiente",
    async ({ estado, gruposConError, gruposFallidos, esperado }) => {
      const base = loteResumenMock();
      const lote = {
        ...base,
        estado,
        grupos_validos: 1,
        grupos_con_error: gruposConError,
        grupos_fallidos: gruposFallidos,
        control_duplicados: {
          ...base.control_duplicados,
          estado: "requiere_confirmacion" as const,
        },
      };
      const wrapper = await mountView([], [lote], lote);
      const actual = wrapper.get('[data-testid="lote-reciente-12"]');

      expect(actual.text()).toContain(esperado);
      expect(actual.text()).not.toContain("comprobante validado");
      expect(actual.text()).not.toContain("1 listo");

      wrapper.unmount();
    },
  );

  it("preserva los mensajes de lote listo y fila sin observaciones cuando no hay coincidencias", async () => {
    const lote = loteResumenMock();
    const wrapper = await mountView([], [lote], lote, {
      ...gruposPageMock(),
      items: [{ ...grupoDetalleMock(), mensajes_json: [] }],
    });

    const totals = wrapper.get('[data-testid="totales-lote"]');
    expect(totals.text()).toContain("Totales listos para emitir");
    expect(totals.classes()).toContain("bg-status-success-soft");
    expect(wrapper.text()).toContain("Sin observaciones");
    expect(wrapper.text()).toContain(
      "El lote se validó correctamente y puede emitirse.",
    );
    expect(wrapper.text()).not.toContain(
      "La revisión general de coincidencias del lote sigue pendiente.",
    );

    wrapper.unmount();
  });

  it("conserva los puntos del emisor B si la respuesta de A llega tarde", async () => {
    const cargaA = deferred<PuntoVenta[]>();
    const cargaB = deferred<PuntoVenta[]>();
    const wrapper = await mountView(
      [],
      [],
      loteResumenMock(),
      gruposPageMock(),
      cargaA.promise,
    );
    mockedPuntosVenta.getAll.mockReturnValue(cargaB.promise);

    const empresaStore = useEmpresaStore();
    empresaStore.empresas = [
      empresaMock(),
      { ...empresaMock(), id: 2, razon_social: "Emisor B" },
    ];
    empresaStore.empresaActivaId = 2;
    await flushPromises();

    expect(mockedPuntosVenta.getAll).toHaveBeenCalledTimes(2);
    cargaB.resolve([puntoVentaMock(2, 2)]);
    await flushPromises();

    const vm = wrapper.vm as unknown as { puntosVenta: PuntoVenta[] };
    expect(vm.puntosVenta.map((punto) => punto.empresa_id)).toEqual([2]);

    cargaA.resolve([puntoVentaMock(1, 1)]);
    await flushPromises();

    expect(vm.puntosVenta.map((punto) => punto.empresa_id)).toEqual([2]);
    wrapper.unmount();
  });

  it("ignora el error tardío de A mientras carga los puntos del emisor B", async () => {
    const cargaA = deferred<PuntoVenta[]>();
    const cargaB = deferred<PuntoVenta[]>();
    const wrapper = await mountView(
      [],
      [],
      loteResumenMock(),
      gruposPageMock(),
      cargaA.promise,
    );
    mockedPuntosVenta.getAll.mockReturnValue(cargaB.promise);

    const empresaStore = useEmpresaStore();
    empresaStore.empresas = [
      empresaMock(),
      { ...empresaMock(), id: 2, razon_social: "Emisor B" },
    ];
    empresaStore.empresaActivaId = 2;
    await flushPromises();
    notificationMock.showError.mockClear();

    cargaA.reject({ response: { data: { detail: "Error del emisor A" } } });
    await flushPromises();

    expect(notificationMock.showError).not.toHaveBeenCalledWith(
      "No se pudieron cargar los puntos de venta",
      expect.any(String),
    );
    const vm = wrapper.vm as unknown as { puntosVenta: PuntoVenta[] };
    expect(vm.puntosVenta).toEqual([]);

    cargaB.resolve([puntoVentaMock(2, 2)]);
    await flushPromises();
    expect(vm.puntosVenta.map((punto) => punto.empresa_id)).toEqual([2]);
    wrapper.unmount();
  });

  it("limpia la configuración visible de A antes de esperar la primera carga de B", async () => {
    const cargaFormatoB = deferred<FormatoImportacion[]>();
    const cargaB = deferred<PuntoVenta[]>();
    const wrapper = await mountView(
      [perfilRelativoMock()],
      [],
      loteResumenMock(),
      gruposPageMock(),
      [puntoVentaMock(1, 1)],
    );
    const vm = wrapper.vm as unknown as {
      formatosImportacion: FormatoImportacion[];
      perfilesCargaMasiva: PerfilCargaMasiva[];
      puntosVenta: PuntoVenta[];
    };
    expect(vm.formatosImportacion.map((formato) => formato.empresa_id)).toEqual(
      [1],
    );
    expect(vm.perfilesCargaMasiva.map((perfil) => perfil.empresa_id)).toEqual([
      1,
    ]);
    expect(vm.puntosVenta.map((punto) => punto.empresa_id)).toEqual([1]);

    mockedFormatos.listar.mockReturnValue(cargaFormatoB.promise);
    mockedPuntosVenta.getAll.mockReturnValue(cargaB.promise);
    mockedPerfiles.listar.mockResolvedValue([
      { ...perfilRelativoMock(), id: 20, empresa_id: 2 },
    ]);
    const empresaStore = useEmpresaStore();
    empresaStore.empresas = [
      empresaMock(),
      { ...empresaMock(), id: 2, razon_social: "Emisor B" },
    ];
    empresaStore.empresaActivaId = 2;
    await flushPromises();

    expect(vm.formatosImportacion).toEqual([]);
    expect(vm.perfilesCargaMasiva).toEqual([]);
    expect(vm.puntosVenta).toEqual([]);

    cargaFormatoB.resolve([
      { ...formatoMock(), id: 20, empresa_id: 2, nombre: "Formato B" },
    ]);
    await flushPromises();
    expect(vm.formatosImportacion.map((formato) => formato.empresa_id)).toEqual(
      [2],
    );
    expect(vm.perfilesCargaMasiva).toEqual([]);
    expect(vm.puntosVenta).toEqual([]);

    notificationMock.showError.mockClear();
    cargaB.reject({ response: { data: { detail: "Error del emisor B" } } });
    await flushPromises();

    expect(vm.puntosVenta).toEqual([]);
    expect(vm.perfilesCargaMasiva.map((perfil) => perfil.empresa_id)).toEqual([
      2,
    ]);
    expect(notificationMock.showError).toHaveBeenCalledWith(
      "No se pudieron cargar los puntos de venta",
      "Error del emisor B",
    );
    wrapper.unmount();
  });

  it("descarta formatos de B si terminan después de completar la carga de C", async () => {
    const cargaFormatoB = deferred<FormatoImportacion[]>();
    const wrapper = await mountView(
      [perfilRelativoMock()],
      [],
      loteResumenMock(),
      gruposPageMock(),
      [puntoVentaMock(1, 1)],
    );
    const vm = wrapper.vm as unknown as {
      formatosImportacion: FormatoImportacion[];
      perfilesCargaMasiva: PerfilCargaMasiva[];
      puntosVenta: PuntoVenta[];
    };
    const empresaStore = useEmpresaStore();
    empresaStore.empresas = [
      empresaMock(),
      { ...empresaMock(), id: 2, razon_social: "Emisor B" },
      { ...empresaMock(), id: 3, razon_social: "Emisor C" },
    ];

    mockedFormatos.listar.mockReturnValue(cargaFormatoB.promise);
    empresaStore.empresaActivaId = 2;
    await flushPromises();
    expect(vm.formatosImportacion).toEqual([]);

    mockedFormatos.listar.mockResolvedValue([
      { ...formatoMock(), id: 30, empresa_id: 3, nombre: "Formato C" },
    ]);
    mockedPuntosVenta.getAll.mockResolvedValue([puntoVentaMock(3, 3)]);
    mockedPerfiles.listar.mockResolvedValue([
      { ...perfilRelativoMock(), id: 30, empresa_id: 3 },
    ]);
    empresaStore.empresaActivaId = 3;
    await flushPromises();

    expect(vm.formatosImportacion.map((formato) => formato.empresa_id)).toEqual(
      [3],
    );
    expect(vm.puntosVenta.map((punto) => punto.empresa_id)).toEqual([3]);
    expect(vm.perfilesCargaMasiva.map((perfil) => perfil.empresa_id)).toEqual([
      3,
    ]);

    cargaFormatoB.resolve([
      { ...formatoMock(), id: 20, empresa_id: 2, nombre: "Formato B" },
    ]);
    await flushPromises();
    expect(vm.formatosImportacion.map((formato) => formato.empresa_id)).toEqual(
      [3],
    );
    expect(vm.puntosVenta.map((punto) => punto.empresa_id)).toEqual([3]);
    expect(vm.perfilesCargaMasiva.map((perfil) => perfil.empresa_id)).toEqual([
      3,
    ]);
    wrapper.unmount();
  });

  it("descarta perfiles de B si terminan después de completar la carga de C", async () => {
    const cargaPerfilB = deferred<PerfilCargaMasiva[]>();
    const wrapper = await mountView();
    const vm = wrapper.vm as unknown as {
      formatosImportacion: FormatoImportacion[];
      perfilesCargaMasiva: PerfilCargaMasiva[];
      puntosVenta: PuntoVenta[];
    };
    const empresaStore = useEmpresaStore();
    empresaStore.empresas = [
      empresaMock(),
      { ...empresaMock(), id: 2, razon_social: "Emisor B" },
      { ...empresaMock(), id: 3, razon_social: "Emisor C" },
    ];

    mockedFormatos.listar.mockResolvedValue([
      { ...formatoMock(), id: 20, empresa_id: 2, nombre: "Formato B" },
    ]);
    mockedPuntosVenta.getAll.mockResolvedValue([puntoVentaMock(2, 2)]);
    mockedPerfiles.listar.mockReturnValue(cargaPerfilB.promise);
    empresaStore.empresaActivaId = 2;
    await flushPromises();
    expect(vm.perfilesCargaMasiva).toEqual([]);

    mockedFormatos.listar.mockResolvedValue([
      { ...formatoMock(), id: 30, empresa_id: 3, nombre: "Formato C" },
    ]);
    mockedPuntosVenta.getAll.mockResolvedValue([puntoVentaMock(3, 3)]);
    mockedPerfiles.listar.mockResolvedValue([
      { ...perfilRelativoMock(), id: 30, empresa_id: 3 },
    ]);
    empresaStore.empresaActivaId = 3;
    await flushPromises();

    cargaPerfilB.resolve([{ ...perfilRelativoMock(), id: 20, empresa_id: 2 }]);
    await flushPromises();
    expect(vm.formatosImportacion.map((formato) => formato.empresa_id)).toEqual(
      [3],
    );
    expect(vm.puntosVenta.map((punto) => punto.empresa_id)).toEqual([3]);
    expect(vm.perfilesCargaMasiva.map((perfil) => perfil.empresa_id)).toEqual([
      3,
    ]);
    wrapper.unmount();
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

  it("permite validar desde el cierre de la configuración fiscal", async () => {
    mockedFormatos.detectar.mockResolvedValue(
      deteccionMock("Formato Base", 10, ["Fecha", "Importe"]),
    );
    const wrapper = await mountView();
    const input = wrapper.find('input[type="file"]');
    const archivo = new File(["demo"], "lote.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    Object.defineProperty(input.element, "files", {
      value: [archivo],
      configurable: true,
    });
    await input.trigger("change");
    await flushPromises();

    const vm = wrapper.vm as unknown as {
      conceptoModo: string;
      descripcionItemModo: string;
      fechaEmisionModo: string;
    };
    vm.conceptoModo = "productos";
    vm.descripcionItemModo = "archivo";
    vm.fechaEmisionModo = "archivo";
    await flushPromises();

    expect(wrapper.text()).toContain("Requisitos completos para validar");
    const botonFinal = wrapper.find('[data-testid="validar-lote-final"]');
    expect(botonFinal.exists()).toBe(true);
    expect(botonFinal.attributes("disabled")).toBeUndefined();

    await botonFinal.trigger("click");

    expect(mockedLotesDetalle.validar).toHaveBeenCalledWith(
      archivo,
      10,
      expect.objectContaining({
        punto_venta_modo: "archivo",
        concepto_modo: "productos",
        descripcion_item_modo: "archivo",
        fecha_emision_modo: "archivo",
      }),
      null,
    );
  });

  it.each([
    {
      estado: "requiere_confirmacion" as const,
      esperado: "El lote se validó correctamente.",
    },
    {
      estado: "operacion_en_curso" as const,
      esperado: "El lote se validó correctamente.",
    },
    {
      estado: "sin_coincidencias" as const,
      esperado: "El lote se validó correctamente.",
    },
  ])(
    "presenta el toast de validación según el control de duplicados $estado",
    async ({ estado, esperado }) => {
      const resumen = loteResumenMock();
      resumen.control_duplicados = {
        ...resumen.control_duplicados,
        estado,
      };
      mockedLotesDetalle.validar.mockResolvedValueOnce({
        lote: resumen,
        mensaje: "El lote se validó correctamente y puede emitirse.",
        requiere_background: false,
      });
      const wrapper = await mountView();
      mockedLotesDetalle.obtenerResumen.mockResolvedValueOnce(resumen);
      const vm = wrapper.vm as unknown as {
        archivoSeleccionado: File;
        formatoSeleccionadoId: number;
        conceptoModo: string;
        descripcionItemModo: string;
        fechaEmisionModo: string;
        validarArchivo: () => Promise<void>;
      };
      vm.archivoSeleccionado = new File(["demo"], "lote.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      vm.formatoSeleccionadoId = 10;
      vm.conceptoModo = "productos";
      vm.descripcionItemModo = "archivo";
      vm.fechaEmisionModo = "archivo";
      await flushPromises();

      await vm.validarArchivo();

      expect(notificationMock.showSuccess).toHaveBeenCalledWith(
        "Archivo validado",
        esperado,
      );
      wrapper.unmount();
    },
  );
  it("omite fechas de servicio al validar un lote de productos", async () => {
    mockedFormatos.detectar.mockResolvedValue(
      deteccionMock("Formato Base", 10, ["Fecha", "Importe"]),
    );
    const wrapper = await mountView();
    const input = wrapper.find('input[type="file"]');
    const archivo = new File(["demo"], "lote.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    Object.defineProperty(input.element, "files", {
      value: [archivo],
      configurable: true,
    });
    await input.trigger("change");
    await flushPromises();

    const vm = wrapper.vm as unknown as {
      conceptoModo: string;
      descripcionItemModo: string;
      fechaEmisionModo: string;
      fechaServicioDesdeModo: string;
      fechaServicioDesdeFija: string;
      fechaServicioHastaModo: string;
      fechaServicioHastaFija: string;
      fechaVtoPagoModo: string;
      fechaVtoPagoFija: string;
    };
    vm.conceptoModo = "servicios";
    vm.fechaServicioDesdeModo = "fija";
    vm.fechaServicioDesdeFija = "2026-04-01";
    vm.fechaServicioHastaModo = "fija";
    vm.fechaServicioHastaFija = "2026-04-30";
    vm.fechaVtoPagoModo = "fija";
    vm.fechaVtoPagoFija = "2026-05-10";
    vm.conceptoModo = "productos";
    vm.descripcionItemModo = "archivo";
    vm.fechaEmisionModo = "archivo";
    await flushPromises();

    await wrapper.find('[data-testid="validar-lote-final"]').trigger("click");

    const opciones = mockedLotesDetalle.validar.mock.calls[0][2];
    expect(opciones).toMatchObject({
      concepto_modo: "productos",
      fecha_servicio_desde_modo: "",
      fecha_servicio_hasta_modo: "",
      fecha_vto_pago_modo: "",
    });
    expect(opciones.fecha_servicio_desde_fija).toBeUndefined();
    expect(opciones.fecha_servicio_hasta_fija).toBeUndefined();
    expect(opciones.fecha_vto_pago_fija).toBeUndefined();
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

  it("no descarga la plantilla oficial si el perfil apunta a una version no vigente", async () => {
    const perfil = {
      ...perfilRelativoMock(),
      configuracion_json: {
        ...perfilRelativoMock().configuracion_json,
        formato_importacion_version_id: 999,
      },
    };
    const wrapper = await mountView([perfil]);
    const vm = wrapper.vm as unknown as {
      formatoSeleccionadoId: string | number;
      descargarPlantilla: () => Promise<void>;
    };

    expect(Number(vm.formatoSeleccionadoId)).toBe(999);
    await vm.descargarPlantilla();

    expect(mockedFormatos.descargar).not.toHaveBeenCalled();
    expect(mockedLotesDetalle.descargarPlantilla).not.toHaveBeenCalled();
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
    expect(wrapper.text()).toContain(
      "El resumen fiscal considera el lote completo",
    );
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
  });

  it("muestra lotes recientes como navegación compacta", async () => {
    const lote = loteResumenMock();
    const loteObservado = {
      ...loteResumenMock(),
      id: 13,
      nombre_archivo: "lote-observado.xlsx",
      estado: "con_errores",
      total_grupos: 2,
      grupos_validos: 0,
      grupos_con_error: 2,
      totales_listos_para_emitir: {
        comprobantes: 0,
        neto: 0,
        iva21: 0,
        iva105: 0,
        total: 0,
        valores_invalidos: 0,
      },
    };
    const wrapper = await mountView([], [lote, loteObservado]);

    const lista = wrapper.get('[data-testid="lotes-recientes-lista"]');
    expect(lista.text()).toContain("1432 listos");
    expect(lista.text()).toContain("2 observados");
    expect(lista.text()).not.toContain("Válidos:");
    expect(lista.text()).not.toContain("Externos:");

    mockedLotesDetalle.obtenerResumen.mockClear();
    await wrapper.get('[data-testid="lote-reciente-13"]').trigger("click");
    await flushPromises();

    expect(mockedLotesDetalle.obtenerResumen).toHaveBeenCalledWith(13);
  });

  it("advierte que un fallo temporal de seguimiento no implica lote inexistente", async () => {
    const lote = loteResumenMock();
    const wrapper = await mountView([], [lote]);

    mockedLotesDetalle.obtenerResumen.mockClear();
    notificationMock.showError.mockClear();
    mockedLotesDetalle.obtenerResumen.mockRejectedValueOnce({
      response: { status: 500, data: {} },
    });

    await wrapper
      .get(`[data-testid="lote-reciente-${lote.id}"]`)
      .trigger("click");
    await flushPromises();

    expect(notificationMock.showError).toHaveBeenCalledWith(
      "No se pudo actualizar el seguimiento del lote",
      expect.stringContaining("El lote puede seguir existiendo o procesándose"),
    );
    const llamadas = notificationMock.showError.mock.calls;
    const ultimaLlamada = llamadas[llamadas.length - 1];
    expect(ultimaLlamada[1]).not.toContain("ya no está disponible");
  });

  it("usa un solo request liviano por ciclo activo aunque el detalle esté abierto", async () => {
    vi.useFakeTimers();
    const activo = loteActivoMock();
    const seguimiento = loteActivoMock({
      grupos_validos: 1430,
      grupos_emitidos: 2,
    });
    const wrapper = await mountView([], [activo], activo);
    const detalle = wrapper.get('[data-testid="detalle-comprobantes-lote"]');
    (detalle.element as HTMLDetailsElement).open = true;
    await detalle.trigger("toggle");

    mockedLotesDetalle.listar.mockClear();
    mockedLotesDetalle.obtenerResumen.mockClear();
    mockedLotesDetalle.obtenerGrupos.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockResolvedValue(seguimiento);

    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();

    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledWith(
      activo.id,
    );
    expect(mockedLotesDetalle.listar).not.toHaveBeenCalled();
    expect(mockedLotesDetalle.obtenerResumen).not.toHaveBeenCalled();
    expect(mockedLotesDetalle.obtenerGrupos).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("no solapa callbacks mientras el seguimiento anterior está pendiente", async () => {
    vi.useFakeTimers();
    const activo = loteActivoMock();
    const pendiente = deferred<LoteComprobante>();
    const wrapper = await mountView([], [activo], activo);
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    mockedLotesDetalle.obtenerSeguimiento
      .mockReturnValueOnce(pendiente.promise)
      .mockResolvedValue(activo);

    await vi.advanceTimersByTimeAsync(3000);
    await vi.advanceTimersByTimeAsync(6000);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);

    pendiente.resolve(activo);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(2999);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("refresca una vez el lote terminal y detiene el seguimiento", async () => {
    vi.useFakeTimers();
    const activo = loteActivoMock();
    const terminal = loteActivoMock({
      estado: "completado",
      grupos_validos: 0,
      grupos_emitidos: 1432,
      finished_at: "2026-05-01T00:10:00",
    });
    const wrapper = await mountView([], [activo], activo);
    mockedLotesDetalle.listar.mockClear();
    mockedLotesDetalle.obtenerResumen.mockClear();
    mockedLotesDetalle.obtenerGrupos.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockResolvedValue(terminal);
    mockedLotesDetalle.listar.mockResolvedValue([terminal]);
    mockedLotesDetalle.obtenerResumen.mockResolvedValue(terminal);

    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();

    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);
    expect(mockedLotesDetalle.listar).toHaveBeenCalledTimes(1);
    expect(mockedLotesDetalle.obtenerResumen).toHaveBeenCalledTimes(1);
    expect(mockedLotesDetalle.obtenerGrupos).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(30000);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("adapta el intervalo a cinco y diez segundos según la duración", async () => {
    vi.useFakeTimers();
    const activo = loteActivoMock();
    const primero = deferred<LoteComprobante>();
    const segundo = deferred<LoteComprobante>();
    const wrapper = await mountView([], [activo], activo);
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    mockedLotesDetalle.obtenerSeguimiento
      .mockReturnValueOnce(primero.promise)
      .mockReturnValueOnce(segundo.promise)
      .mockResolvedValue(activo);

    await vi.advanceTimersByTimeAsync(3000);
    await vi.advanceTimersByTimeAsync(28000);
    primero.resolve(activo);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(4999);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(85000);
    segundo.resolve(activo);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(9999);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(3);
    wrapper.unmount();
  });

  it("aplica backoff temporal y vuelve al intervalo base después de un éxito", async () => {
    vi.useFakeTimers();
    const activo = loteActivoMock();
    const wrapper = await mountView([], [activo], activo);
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    notificationMock.showError.mockClear();
    mockedLotesDetalle.obtenerSeguimiento
      .mockRejectedValueOnce({ response: { status: 500, data: {} } })
      .mockRejectedValueOnce({ response: { status: 503, data: {} } })
      .mockResolvedValue(activo);

    await vi.advanceTimersByTimeAsync(3000);
    await vi.advanceTimersByTimeAsync(5999);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(11999);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(3);
    await vi.advanceTimersByTimeAsync(2999);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(3);
    await vi.advanceTimersByTimeAsync(1);
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(4);
    expect(notificationMock.showError).toHaveBeenCalledWith(
      "No se pudo actualizar el seguimiento del lote",
      expect.stringContaining("El lote puede seguir existiendo o procesándose"),
    );
    wrapper.unmount();
  });

  it("sigue el primer lote activo si el seleccionado ya está terminal", async () => {
    vi.useFakeTimers();
    const seleccionado = loteResumenMock();
    const activo = loteActivoMock({ id: 13, nombre_archivo: "activo.xlsx" });
    const wrapper = await mountView([], [seleccionado, activo], seleccionado);
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockResolvedValue(activo);

    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();
    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledWith(
      activo.id,
    );
    wrapper.unmount();
  });

  it("ignora una respuesta tardía después de cambiar de emisor", async () => {
    vi.useFakeTimers();
    const activo = loteActivoMock();
    const tardia = deferred<LoteComprobante>();
    const wrapper = await mountView([], [activo], activo);
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    mockedLotesDetalle.obtenerResumen.mockClear();
    mockedLotesDetalle.obtenerGrupos.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockReturnValueOnce(tardia.promise);
    await vi.advanceTimersByTimeAsync(3000);

    const empresaStore = useEmpresaStore();
    mockedLotesDetalle.listar.mockResolvedValue([]);
    empresaStore.empresa = {
      ...empresaMock(),
      id: 2,
      razon_social: "Segundo emisor",
    };
    empresaStore.empresaActivaId = 2;
    await flushPromises();

    tardia.resolve(loteActivoMock({ grupos_emitidos: 99 }));
    await flushPromises();
    await vi.advanceTimersByTimeAsync(30000);

    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);
    expect(mockedLotesDetalle.obtenerResumen).not.toHaveBeenCalled();
    expect(mockedLotesDetalle.obtenerGrupos).not.toHaveBeenCalled();
    expect(
      wrapper.find(`[data-testid="lote-reciente-${activo.id}"]`).exists(),
    ).toBe(false);
    wrapper.unmount();
  });

  it("ignora el refresco terminal tardío si cambia el emisor", async () => {
    vi.useFakeTimers();
    const activo = loteActivoMock();
    const terminal = loteActivoMock({
      estado: "completado",
      grupos_validos: 0,
      grupos_emitidos: 1432,
    });
    const listadoAnterior = deferred<LoteComprobante[]>();
    const wrapper = await mountView([], [activo], activo);
    mockedLotesDetalle.listar.mockClear();
    mockedLotesDetalle.obtenerResumen.mockClear();
    mockedLotesDetalle.obtenerGrupos.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockResolvedValue(terminal);
    mockedLotesDetalle.listar
      .mockReturnValueOnce(listadoAnterior.promise)
      .mockResolvedValue([]);

    await vi.advanceTimersByTimeAsync(3000);
    expect(mockedLotesDetalle.listar).toHaveBeenCalledTimes(1);

    const empresaStore = useEmpresaStore();
    empresaStore.empresa = {
      ...empresaMock(),
      id: 2,
      razon_social: "Segundo emisor",
    };
    empresaStore.empresaActivaId = 2;
    await flushPromises();

    listadoAnterior.resolve([terminal]);
    await flushPromises();

    expect(mockedLotesDetalle.listar).toHaveBeenCalledTimes(2);
    expect(mockedLotesDetalle.obtenerResumen).not.toHaveBeenCalled();
    expect(mockedLotesDetalle.obtenerGrupos).not.toHaveBeenCalled();
    expect(
      wrapper.find(`[data-testid="lote-reciente-${activo.id}"]`).exists(),
    ).toBe(false);
    wrapper.unmount();
  });
  it("no reprograma el seguimiento después de desmontar", async () => {
    vi.useFakeTimers();
    const activo = loteActivoMock();
    const tardia = deferred<LoteComprobante>();
    const wrapper = await mountView([], [activo], activo);
    mockedLotesDetalle.obtenerSeguimiento.mockClear();
    mockedLotesDetalle.listar.mockClear();
    mockedLotesDetalle.obtenerResumen.mockClear();
    mockedLotesDetalle.obtenerGrupos.mockClear();
    mockedLotesDetalle.obtenerSeguimiento.mockReturnValueOnce(tardia.promise);

    await vi.advanceTimersByTimeAsync(3000);
    wrapper.unmount();
    tardia.resolve(activo);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(30000);

    expect(mockedLotesDetalle.obtenerSeguimiento).toHaveBeenCalledTimes(1);
    expect(mockedLotesDetalle.listar).not.toHaveBeenCalled();
    expect(mockedLotesDetalle.obtenerResumen).not.toHaveBeenCalled();
    expect(mockedLotesDetalle.obtenerGrupos).not.toHaveBeenCalled();
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

  it("cuenta pendientes de reconciliación en el avance de lote incierto", async () => {
    const lote = {
      ...loteResumenMock(),
      estado: "requiere_reconciliacion",
      grupos_validos: 0,
      mensaje_resumen:
        "El procesamiento quedó en estado incierto. No reintentes este lote.",
      totales_listos_para_emitir: {
        comprobantes: 0,
        neto: 0,
        iva21: 0,
        iva105: 0,
        total: 0,
        valores_invalidos: 0,
      },
    };
    const grupo = {
      ...grupoDetalleMock(),
      estado: "requiere_reconciliacion",
      mensajes_json: [
        "El lote quedó en estado incierto durante el procesamiento.",
      ],
    };
    const wrapper = await mountView([], [lote], lote, {
      items: [grupo],
      page: 1,
      per_page: 100,
      total: 1,
      total_pages: 1,
      estado: null,
    });

    expect(wrapper.text()).toContain("No hay comprobantes listos para emitir");
    expect(wrapper.text()).toContain("Pendientes visibles 1");
    expect(wrapper.text()).toContain(
      "El procesamiento quedó en estado incierto. No reintentes este lote.",
    );
    expect(wrapper.text()).not.toContain(
      "Validado correctamente. Listo para emitir.",
    );
  });

  it("deshabilita reintento de fallidos cuando el lote está incierto", async () => {
    const lote = {
      ...loteResumenMock(),
      estado: "requiere_reconciliacion",
      grupos_validos: 0,
      grupos_fallidos: 1,
      mensaje_resumen:
        "El procesamiento quedó en estado incierto. No reintentes este lote.",
      totales_listos_para_emitir: {
        comprobantes: 0,
        neto: 0,
        iva21: 0,
        iva105: 0,
        total: 0,
        valores_invalidos: 0,
      },
    };
    const grupo = {
      ...grupoDetalleMock(),
      estado: "fallido",
      mensajes_json: ["Fallo técnico previo."],
    };
    const wrapper = await mountView([], [lote], lote, {
      items: [grupo],
      page: 1,
      per_page: 100,
      total: 1,
      total_pages: 1,
      estado: null,
    });

    const botonReintento = wrapper
      .findAll("button")
      .find((button) => button.text().includes("Reintentar fallidos"));

    expect(botonReintento).toBeTruthy();
    expect(botonReintento?.attributes("disabled")).toBeDefined();

    await botonReintento?.trigger("click");

    expect(mockedLotesDetalle.reintentarFallidos).not.toHaveBeenCalled();
  });

  it("deshabilita descarte de visibles cuando el lote está incierto", async () => {
    const lote = {
      ...loteResumenMock(),
      estado: "requiere_reconciliacion",
      grupos_validos: 0,
      grupos_fallidos: 1,
      mensaje_resumen:
        "El procesamiento quedó en estado incierto. No descartes este lote.",
      totales_listos_para_emitir: {
        comprobantes: 0,
        neto: 0,
        iva21: 0,
        iva105: 0,
        total: 0,
        valores_invalidos: 0,
      },
    };
    const grupo = {
      ...grupoDetalleMock(),
      estado: "fallido",
      mensajes_json: ["Fallo técnico previo."],
    };
    const wrapper = await mountView([], [lote], lote, {
      items: [grupo],
      page: 1,
      per_page: 100,
      total: 1,
      total_pages: 1,
      estado: null,
    });

    await wrapper.find("textarea").setValue("Auditar antes de cerrar");

    const botonDescartar = wrapper
      .findAll("button")
      .find((button) => button.text().includes("Descartar visibles"));

    expect(botonDescartar).toBeTruthy();
    expect(botonDescartar?.attributes("disabled")).toBeDefined();

    await botonDescartar?.trigger("click");

    expect(mockedLotesDetalle.descartarGrupos).not.toHaveBeenCalled();
  });

  it("mantiene la resolución de pendientes cerrada hasta intervención explícita", async () => {
    const lote = {
      ...loteResumenMock(),
      total_grupos: 1,
      grupos_validos: 1,
      totales_listos_para_emitir: {
        comprobantes: 1,
        neto: 1000,
        iva21: 210,
        iva105: 0,
        total: 1210,
        valores_invalidos: 0,
      },
    };
    const wrapper = await mountView([], [lote], lote, {
      items: [grupoDetalleMock()],
      page: 1,
      per_page: 100,
      total: 1,
      total_pages: 1,
      estado: null,
    });

    const resolucion = wrapper.get(
      '[data-testid="resolucion-pendientes-lote"]',
    );
    expect((resolucion.element as HTMLDetailsElement).open).toBe(false);
    expect(resolucion.text()).toContain("Abrir resolución");
    expect(resolucion.text()).toContain(
      "Modo sensible para reintentar, descartar o reconciliar",
    );

    (resolucion.element as HTMLDetailsElement).open = true;
    await resolucion.trigger("toggle");
    await flushPromises();

    expect((resolucion.element as HTMLDetailsElement).open).toBe(true);
    expect(resolucion.text()).toContain("Cerrar resolución");
    expect(resolucion.text()).toContain(
      "Reintenta fallidos cuando quieras emitirlos desde FactuFlow",
    );
  });

  it("bloquea acciones sobre visibles si el detalle está cerrado", async () => {
    const lote = {
      ...loteResumenMock(),
      total_grupos: 1,
      grupos_validos: 1,
      totales_listos_para_emitir: {
        comprobantes: 1,
        neto: 1000,
        iva21: 210,
        iva105: 0,
        total: 1210,
        valores_invalidos: 0,
      },
    };
    const wrapper = await mountView([], [lote], lote, {
      items: [grupoDetalleMock()],
      page: 1,
      per_page: 100,
      total: 1,
      total_pages: 1,
      estado: null,
    });

    const detalle = wrapper.get('[data-testid="detalle-comprobantes-lote"]');
    expect((detalle.element as HTMLDetailsElement).open).toBe(false);
    expect(wrapper.text()).toContain("Abrí el detalle de comprobantes");

    const buscarBotonDescartar = () =>
      wrapper
        .findAll("button")
        .find((button) => button.text().includes("Descartar visibles"));
    const botonDescartarCerrado = buscarBotonDescartar();

    expect(botonDescartarCerrado).toBeTruthy();
    expect(botonDescartarCerrado?.attributes("disabled")).toBeDefined();

    (detalle.element as HTMLDetailsElement).open = true;
    await detalle.trigger("toggle");
    await flushPromises();
    await wrapper.findAll("textarea")[0].setValue("No corresponde emitir");

    expect(buscarBotonDescartar()?.attributes("disabled")).toBeUndefined();
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

  it("recupera el progreso del reintento sin contar los autorizados anteriores", async () => {
    const progreso = {
      operacion_id: 10,
      seleccionados: 3,
      autorizados: 0,
      fallidos: 0,
      pendientes: 3,
      inciertos: 0,
    };
    const lote = {
      ...loteResumenMock(),
      estado: "en_cola" as const,
      grupos_emitidos: 97,
      grupos_validos: 3,
      metadata_json: {
        reintento_background: true,
        operacion_progreso: progreso,
      },
    };
    const wrapper = await mountView([], [lote], lote);
    const vm = wrapper.vm as unknown as {
      cargarDetalleLote: (id: number, silent: boolean) => Promise<boolean>;
    };
    await vm.cargarDetalleLote(lote.id, true);
    await flushPromises();
    expect(wrapper.text()).toContain("En cola para procesar 3 comprobantes");
    expect(wrapper.text()).toContain("Seleccionados 3 · Autorizados 0 · Fallidos 0 · Pendientes 3 · Inciertos 0");
    expect(mockedLotesDetalle.reintentarFallidos).not.toHaveBeenCalled();
    wrapper.unmount();
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

  it("conserva clave y confirmación fiscal entre el POST 409 y la excepción explícita", async () => {
    const control = {
      ...loteResumenMock().control_duplicados,
      estado: "requiere_confirmacion" as const,
      evidencia_id: "v2.evidencia-post",
      tipos_coincidencia: ["historica_completa" as const],
      cantidad_actual: 1,
      cantidad_afectada: 1,
      importe_actual: "1210.00",
      importe_afectado: "1210.00",
      aceptacion_requerida: true,
      aceptacion_habilitada: true,
      detalle_url: "/api/lotes-comprobantes/12/coincidencias",
    };
    const lote = { ...loteResumenMock(), control_duplicados: control };
    mockedLotesDetalle.procesar.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: control,
            aceptacion_id: "v2.aceptacion-post",
            confirmacion_duplicado_logico: "v2.aceptacion-post",
          },
        },
      },
    });
    const wrapper = await mountView([], [lote], lote);

    const emitButton = wrapper
      .findAll("button")
      .find((button) => button.text().includes("Emitir comprobantes válidos"));
    await emitButton?.trigger("click");
    await flushPromises();
    const fiscalConfirm = Array.from(
      document.body.querySelectorAll("button"),
    ).find((button) =>
      button.textContent?.includes("Emitir con esta fecha"),
    ) as HTMLButtonElement;
    fiscalConfirm.click();
    await flushPromises();

    expect(document.body.textContent).toContain(
      "Este lote coincide por completo con el contenido de otro lote",
    );
    const firstKey = mockedLotesDetalle.procesar.mock.calls[0][2];
    const review = Array.from(document.body.querySelectorAll("button")).find(
      (button) => button.textContent?.trim() === "Volver a revisar",
    ) as HTMLButtonElement;
    review.click();
    await flushPromises();

    mockedLotesDetalle.procesar.mockResolvedValueOnce({
      lote,
      mensaje: "Lote en cola",
      en_progreso: true,
    });
    await emitButton?.trigger("click");
    await flushPromises();
    expect(mockedLotesDetalle.procesar).toHaveBeenCalledTimes(2);
    expect(mockedLotesDetalle.procesar.mock.calls[1][2]).toBe(firstKey);
    expect(
      Array.from(document.body.querySelectorAll("button")).some((button) =>
        button.textContent?.includes("Emitir con esta fecha"),
      ),
    ).toBe(false);

    wrapper.unmount();
  });

  it("restaura el foco al disparador tras confirmación fiscal, POST 409 y revisión por teclado", async () => {
    const control = {
      ...loteResumenMock().control_duplicados,
      estado: "requiere_confirmacion" as const,
      evidencia_id: "v2.evidencia-foco",
      tipos_coincidencia: ["interna_receptor" as const],
      cantidad_actual: 2,
      cantidad_afectada: 2,
      importe_actual: "2420.00",
      importe_afectado: "2420.00",
      aceptacion_requerida: true,
      aceptacion_habilitada: true,
      detalle_url: "/api/lotes-comprobantes/12/coincidencias",
    };
    const lote = { ...loteResumenMock(), control_duplicados: control };
    mockedLotesDetalle.procesar.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: control,
            aceptacion_id: "v2.aceptacion-foco",
          },
        },
      },
    });
    const wrapper = await mountView(
      [],
      [lote],
      lote,
      gruposPageMock(),
      [],
      document.body,
    );
    const emitButton = wrapper
      .findAll("button")
      .find((button) => button.text().includes("Emitir comprobantes válidos"));
    const emitElement = emitButton?.element as HTMLButtonElement;

    emitElement.focus();
    await emitButton?.trigger("click");
    await flushPromises();
    const fiscalConfirm = Array.from(
      document.body.querySelectorAll("button"),
    ).find((button) =>
      button.textContent?.includes("Emitir con esta fecha"),
    ) as HTMLButtonElement;
    fiscalConfirm.focus();
    fiscalConfirm.click();
    await flushPromises();

    const review = Array.from(document.body.querySelectorAll("button")).find(
      (button) => button.textContent?.trim() === "Volver a revisar",
    ) as HTMLButtonElement;
    expect(document.activeElement).toBe(review);
    review.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    review.click();
    await flushPromises();

    expect(document.body.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(emitElement);
    expect(mockedLotesDetalle.procesar).toHaveBeenCalledTimes(1);
    expect(mockedLotesDetalle.procesar.mock.calls[0][3]).toBeUndefined();

    const informationalTrigger = wrapper
      .findAll("button")
      .find((button) => button.text().includes("Revisar coincidencias"));
    await informationalTrigger?.trigger("click");
    await flushPromises();
    const informationalReview = Array.from(
      document.body.querySelectorAll("button"),
    ).find(
      (button) => button.textContent?.trim() === "Volver a revisar",
    ) as HTMLButtonElement;
    const newerFocus = document.createElement("button");
    document.body.appendChild(newerFocus);
    informationalReview.click();
    newerFocus.focus();
    await flushPromises();

    expect(document.activeElement).toBe(newerFocus);
    expect(mockedLotesDetalle.procesar).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("usa la aceptación del POST 409 sólo después del checkbox y conserva la misma clave", async () => {
    const control = {
      ...loteResumenMock().control_duplicados,
      estado: "requiere_confirmacion" as const,
      evidencia_id: "v2.evidencia-aceptada",
      tipos_coincidencia: ["interna_receptor" as const],
      cantidad_actual: 2,
      cantidad_afectada: 2,
      importe_actual: "2420.00",
      importe_afectado: "2420.00",
      aceptacion_requerida: true,
      aceptacion_habilitada: true,
      detalle_url: "/api/lotes-comprobantes/12/coincidencias",
    };
    const lote = { ...loteResumenMock(), control_duplicados: control };
    mockedLotesDetalle.procesar.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: control,
            aceptacion_id: "v2.aceptacion-interna",
          },
        },
      },
    });
    const wrapper = await mountView([], [lote], lote);
    const vm = wrapper.vm as unknown as { procesarLote: () => Promise<void> };
    await vm.procesarLote();
    const firstKey = mockedLotesDetalle.procesar.mock.calls[0][2];

    const checkbox = document.body.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    checkbox.click();
    await flushPromises();
    mockedLotesDetalle.procesar.mockResolvedValueOnce({
      lote,
      mensaje: "Lote en cola",
      en_progreso: true,
    });
    const accept = Array.from(document.body.querySelectorAll("button")).find(
      (button) =>
        button.textContent?.trim() === "Emitir como operaciones nuevas",
    ) as HTMLButtonElement;
    accept.click();
    await flushPromises();

    expect(mockedLotesDetalle.procesar.mock.calls[1]).toEqual([
      lote.id,
      lote.confirmacion_fecha_fiscal,
      firstKey,
      "v2.aceptacion-interna",
    ]);
    wrapper.unmount();
  });

  it("un GET 409 actualiza evidencia, limpia aceptación y no dispara otro POST", async () => {
    const controlInicial = {
      ...loteResumenMock().control_duplicados,
      estado: "requiere_confirmacion" as const,
      evidencia_id: "v2.evidencia-inicial",
      tipos_coincidencia: ["historica_completa" as const],
      aceptacion_requerida: true,
      aceptacion_habilitada: true,
      cantidad_afectada: 1,
      detalle_url: "/api/lotes-comprobantes/12/coincidencias",
    };
    const controlNuevo = {
      ...controlInicial,
      evidencia_id: "v2.evidencia-nueva",
      cantidad_afectada: 2,
    };
    const lote = { ...loteResumenMock(), control_duplicados: controlInicial };
    mockedLotesDetalle.procesar.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: controlInicial,
            aceptacion_id: "v2.aceptacion-inicial",
          },
        },
      },
    });
    mockedLotesDetalle.obtenerCoincidencias.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: controlNuevo,
          },
        },
      },
    });
    const wrapper = await mountView([], [lote], lote);
    const vm = wrapper.vm as unknown as {
      procesarLote: () => Promise<void>;
      idempotencyKeyProcesar: string | null;
      confirmacionFiscalProcesarVigente: boolean;
    };
    await vm.procesarLote();
    const key = vm.idempotencyKeyProcesar;
    vm.confirmacionFiscalProcesarVigente = true;

    const detailsButton = Array.from(
      document.body.querySelectorAll("button"),
    ).find(
      (button) => button.textContent?.trim() === "Ver coincidencias",
    ) as HTMLButtonElement;
    detailsButton.click();
    await flushPromises();

    expect(mockedLotesDetalle.procesar).toHaveBeenCalledTimes(1);
    expect(vm.idempotencyKeyProcesar).toBe(key);
    expect(vm.confirmacionFiscalProcesarVigente).toBe(true);
    expect(document.body.querySelector('input[type="checkbox"]')).toBeNull();
    expect(document.body.textContent).toContain(
      "solicitá la emisión nuevamente para decidir sobre la evidencia actual",
    );
    expect((document.activeElement as HTMLElement).textContent?.trim()).toBe(
      "Volver a revisar",
    );
    wrapper.unmount();
  });

  it("un GET 409 con cambio material invalida clave y confirmación fiscal", async () => {
    const controlInicial = {
      ...loteResumenMock().control_duplicados,
      estado: "requiere_confirmacion" as const,
      evidencia_id: "v2.evidencia-material-inicial",
      tipos_coincidencia: ["historica_completa" as const],
      aceptacion_requerida: true,
      aceptacion_habilitada: true,
      cantidad_afectada: 1,
      detalle_url: "/api/lotes-comprobantes/12/coincidencias",
    };
    const controlNuevo = {
      ...controlInicial,
      evidencia_id: "v2.evidencia-material-nueva",
      datos_hash: "datos-materialmente-distintos",
    };
    const lote = { ...loteResumenMock(), control_duplicados: controlInicial };
    mockedLotesDetalle.procesar.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: controlInicial,
            aceptacion_id: "v2.aceptacion-material-inicial",
          },
        },
      },
    });
    mockedLotesDetalle.obtenerCoincidencias.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: controlNuevo,
          },
        },
      },
    });
    const wrapper = await mountView([], [lote], lote);
    const vm = wrapper.vm as unknown as {
      procesarLote: () => Promise<void>;
      idempotencyKeyProcesar: string | null;
      confirmacionFiscalProcesarVigente: boolean;
    };
    await vm.procesarLote();
    expect(vm.idempotencyKeyProcesar).toEqual(expect.any(String));
    vm.confirmacionFiscalProcesarVigente = true;

    const detailsButton = Array.from(
      document.body.querySelectorAll("button"),
    ).find(
      (button) => button.textContent?.trim() === "Ver coincidencias",
    ) as HTMLButtonElement;
    detailsButton.click();
    await flushPromises();

    expect(vm.idempotencyKeyProcesar).toBeNull();
    expect(vm.confirmacionFiscalProcesarVigente).toBe(false);
    expect(document.body.querySelector('input[type="checkbox"]')).toBeNull();
    wrapper.unmount();
  });

  it("descarta un POST 409 tardío después de cambiar de emisor", async () => {
    const pending = deferred<never>();
    const control = {
      ...loteResumenMock().control_duplicados,
      estado: "requiere_confirmacion" as const,
      evidencia_id: "v2.evidencia-tardia",
      tipos_coincidencia: ["historica_completa" as const],
      aceptacion_requerida: true,
      aceptacion_habilitada: true,
      detalle_url: "/api/lotes-comprobantes/12/coincidencias",
    };
    const lote = { ...loteResumenMock(), control_duplicados: control };
    mockedLotesDetalle.procesar.mockReturnValueOnce(pending.promise);
    const wrapper = await mountView([], [lote], lote);
    const vm = wrapper.vm as unknown as { procesarLote: () => Promise<void> };
    const request = vm.procesarLote();
    const empresaStore = useEmpresaStore();
    empresaStore.empresaActivaId = 2;
    await flushPromises();
    pending.reject({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: control,
            aceptacion_id: "v2.aceptacion-tardia",
          },
        },
      },
    });
    await request;
    await flushPromises();

    expect(document.body.textContent).not.toContain(
      "Este lote coincide por completo con otro ya emitido",
    );
    wrapper.unmount();
  });

  it("descarta un POST 409 tardío si cambia la selección comprobada del mismo lote", async () => {
    const pending = deferred<never>();
    const lote = loteResumenMock();
    const changed = {
      ...lote,
      control_duplicados: {
        ...lote.control_duplicados,
        seleccion_hash: "seleccion-actualizada",
      },
    };
    mockedLotesDetalle.procesar.mockReturnValueOnce(pending.promise);
    const wrapper = await mountView([], [lote], lote);
    const vm = wrapper.vm as unknown as {
      procesarLote: () => Promise<void>;
      cargarDetalleLote: (id: number, silent: boolean) => Promise<boolean>;
    };
    const request = vm.procesarLote();
    mockedLotesDetalle.obtenerResumen.mockResolvedValueOnce(changed);
    await vm.cargarDetalleLote(lote.id, true);
    pending.reject({
      response: {
        status: 409,
        data: {
          detail: {
            categoria_error: "duplicado_logico_lote",
            control_duplicados: {
              ...changed.control_duplicados,
              estado: "requiere_confirmacion",
            },
            aceptacion_id: "v2.aceptacion-obsoleta",
          },
        },
      },
    });
    await request;
    await flushPromises();

    expect(document.body.querySelector('[role="dialog"]')).toBeNull();
    wrapper.unmount();
  });
});
