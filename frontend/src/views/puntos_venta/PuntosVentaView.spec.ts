import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { arcaService, type ArcaStatus } from "@/services/arca.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import type { Usuario } from "@/types/auth";
import type { Empresa } from "@/types/empresa";
import type {
  ElegibilidadRece,
  ImportarPuntosVentaResponse,
  PuntoVenta,
  SincronizarPuntosVentaResponse,
} from "@/types/punto_venta";
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
  },
}));

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

const usuarioMock = (esAdmin: boolean): Usuario => ({
  id: 1,
  email: "usuario@example.com",
  nombre: esAdmin ? "Administrador" : "Operador",
  empresa_id: 1,
  empresa_ids: [1],
  puede_crear_editar_emisores: false,
  activo: true,
  es_admin: esAdmin,
  created_at: "2024-01-01T00:00:00",
  ultimo_login: null,
});

const elegibilidadReceMock = (
  overrides: Partial<ElegibilidadRece> = {},
): ElegibilidadRece => ({
  ambiente: "produccion",
  estado: "verificado_rece",
  estado_efectivo: "verificado_rece",
  fuente: "constancia_arca_atestada",
  revision_id: 1,
  revision: 1,
  punto_revision_fiscal: 1,
  verificado_en: "2026-08-09T12:00:00-03:00",
  vigente_hasta: "2026-08-15",
  motivo: null,
  ...overrides,
});

const puntoVentaMock = (
  empresaId: number,
  overrides: Partial<PuntoVenta> = {},
): PuntoVenta => ({
  id: empresaId,
  numero: empresaId,
  nombre: `Punto ${empresaId}`,
  sistema: "Factura Electronica - Web Services",
  domicilio: null,
  domicilio_fuente: null,
  nombre_fantasia: null,
  nombre_fantasia_fuente: null,
  es_webservice: true,
  bloqueado: false,
  fecha_baja: null,
  fuente: "arca_wsfe",
  activo: true,
  usar_en_factuflow: true,
  usable_factuflow: true,
  puede_intentar_emision: true,
  seleccionable_para_emision: true,
  ultima_comprobacion_arca_en: "2026-08-09T15:00:00Z",
  comprobacion_arca_desactualizada: false,
  revision_fiscal: 1,
  elegibilidad_rece: elegibilidadReceMock(),
  empresa_id: empresaId,
  created_at: "2026-01-01T00:00:00",
  ...overrides,
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
  listos_para_emitir: 1,
  no_disponibles_factuflow: 1,
  requieren_revision: 0,
  documento_emitido_en: "2026-08-09",
  vigente_hasta: null,
  warnings: [],
});

describe("PuntosVentaView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
    document.body.innerHTML = "";
    clearEmpresaActivaIdStorage();
  });

  it("no muestra éxito de una sincronización obsoleta si el cambio de emisor está en curso", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    useAuthStore().user = usuarioMock(true);
    const respuestaSync = deferred<SincronizarPuntosVentaResponse>();
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    mockedPuntosVentaService.sincronizarArca.mockReturnValue(
      respuestaSync.promise,
    );
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
    respuestaSync.resolve(syncResponseMock());
    await sincronizacion;

    expect(notificationMocks.showSuccess).not.toHaveBeenCalled();
    expect(notificationMocks.showError).not.toHaveBeenCalled();
  });

  it("no muestra una importación obsoleta después de cambiar el emisor", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    useAuthStore().user = usuarioMock(true);
    const importacionPendiente = deferred<ImportarPuntosVentaResponse>();
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
      prepararImportacionConstancia: (event: Event) => Promise<void>;
    };
    const importacion = vm.prepararImportacionConstancia({
      target: input,
    } as unknown as Event);

    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    setEmpresaActivaIdStorage(2);
    importacionPendiente.resolve(importResponseMock());
    await importacion;

    expect(notificationMocks.showSuccess).not.toHaveBeenCalled();
    expect(notificationMocks.showError).not.toHaveBeenCalled();
    expect(input.value).toBe("");
  });

  it("muestra autoridad WSFE y filtra por uso compartido", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    useAuthStore().user = usuarioMock(true);
    const verificado = puntoVentaMock(1, {
      id: 11,
      numero: 1,
      nombre: "Punto verificado",
    });
    const noRece = puntoVentaMock(1, {
      id: 12,
      numero: 2,
      nombre: "Punto no RECE",
      usable_factuflow: false,
      puede_intentar_emision: false,
      seleccionable_para_emision: false,
      es_webservice: false,
      usar_en_factuflow: false,
      elegibilidad_rece: elegibilidadReceMock({
        estado: "no_rece",
        estado_efectivo: "no_rece",
        fuente: "constancia_arca_atestada",
        verificado_en: null,
        vigente_hasta: null,
        motivo: "punto_no_rece",
      }),
    });
    const desactualizado = puntoVentaMock(1, {
      id: 13,
      numero: 3,
      nombre: "Punto desactualizado",
      comprobacion_arca_desactualizada: true,
      seleccionable_para_emision: false,
      ultima_comprobacion_arca_en: "2026-05-01T12:00:00Z",
    });
    const pendiente = puntoVentaMock(1, {
      id: 14,
      numero: 4,
      nombre: "Punto pendiente",
      activo: false,
      usable_factuflow: false,
      puede_intentar_emision: true,
      seleccionable_para_emision: false,
      ultima_comprobacion_arca_en: null,
      comprobacion_arca_desactualizada: true,
    });
    const ausente = puntoVentaMock(1, {
      id: 15,
      numero: 5,
      nombre: "Punto ausente",
      activo: false,
      usable_factuflow: false,
      puede_intentar_emision: false,
      seleccionable_para_emision: false,
    });
    const otroSistema = puntoVentaMock(1, {
      id: 16,
      numero: 6,
      nombre: "Punto de imprenta",
      sistema: "Factuweb (Imprenta) - Exento en IVA",
      es_webservice: false,
      activo: false,
      usable_factuflow: false,
      puede_intentar_emision: false,
      seleccionable_para_emision: false,
      usar_en_factuflow: false,
      elegibilidad_rece: elegibilidadReceMock({
        estado: "no_rece",
        estado_efectivo: "no_rece",
        motivo: "punto_no_rece",
      }),
    });
    const noVerificado = puntoVentaMock(1, {
      id: 17,
      numero: 7,
      nombre: "Punto sin constancia",
      usable_factuflow: false,
      puede_intentar_emision: false,
      seleccionable_para_emision: false,
      elegibilidad_rece: elegibilidadReceMock({
        estado: "no_verificado",
        estado_efectivo: "no_verificado",
        fuente: null,
        verificado_en: null,
        vigente_hasta: null,
        motivo: "sin_constancia",
      }),
    });
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([
      verificado,
      noRece,
      desactualizado,
      pendiente,
      ausente,
      otroSistema,
      noVerificado,
    ]);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);

    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Listo para emitir");
    expect(wrapper.text()).toContain("Comprobación necesaria");
    expect(wrapper.text()).toContain("Pendiente de comprobar");
    expect(wrapper.text()).toContain("Ausente en ARCA");
    expect(wrapper.text()).not.toContain("Requiere atención");
    expect(wrapper.text()).not.toContain("Revisión fiscal");
    expect(wrapper.text()).not.toContain("Vigente hasta");
    expect(wrapper.findAll("tbody tr")).toHaveLength(5);
    expect(wrapper.text()).not.toContain("Importá una constancia");

    const filtro = wrapper
      .findAll("label")
      .find((label) => label.text().includes("Mostrar todos"));
    expect(filtro).toBeDefined();
    await filtro!.get('input[type="checkbox"]').setValue(true);

    expect(wrapper.findAll("tbody tr")).toHaveLength(7);
    expect(wrapper.text()).toContain("0001");
    expect(wrapper.text()).toContain("0002");
    expect(wrapper.text()).toContain("0006");
    expect(wrapper.text()).toContain("No disponible en FactuFlow");
    expect(wrapper.text()).toContain("Otro sistema");
  });

  it("procesa una sola carga segura sin modal intermedio", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    useAuthStore().user = usuarioMock(true);
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    const warningTecnico =
      "No se desactivaron puntos ausentes porque la constancia no pudo validarse como completa.";
    mockedPuntosVentaService.importarConstancia.mockResolvedValueOnce({
      ...importResponseMock(),
      desactivados_ausentes: 0,
      pendientes_comprobacion: 1,
      warnings: [warningTecnico],
    });
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    const vm = wrapper.vm as unknown as {
      prepararImportacionConstancia: (event: Event) => Promise<void>;
    };
    const input = document.createElement("input");
    input.type = "file";
    const file = new File(["PDF"], "constancia.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(input, "files", { value: [file] });

    await vm.prepararImportacionConstancia({
      target: input,
    } as unknown as Event);

    expect(mockedPuntosVentaService.importarConstancia).toHaveBeenCalledOnce();
    expect(mockedPuntosVentaService.importarConstancia).toHaveBeenCalledWith(
      file,
    );
    expect(document.body.textContent).not.toContain(
      "Importar sin acreditar RECE",
    );
    expect(document.body.textContent).not.toContain(
      "Importar y acreditar RECE",
    );
    expect(notificationMocks.showWarning).toHaveBeenCalledWith(
      "Constancia importada con observaciones",
      "Listos para emitir: 1. No disponibles en FactuFlow: 1. Requieren revisión: 0. Revisá los puntos que requieren una acción.",
    );
    expect(notificationMocks.showSuccess).not.toHaveBeenCalled();
  });

  it("permite la constancia descriptiva también fuera de producción", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    useAuthStore().user = usuarioMock(true);
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("homologacion", true),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([]);
    mockedPuntosVentaService.importarConstancia.mockResolvedValue(
      importResponseMock(),
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
    input.type = "file";
    Object.defineProperty(input, "files", {
      value: [new File(["PDF"], "constancia.pdf", { type: "application/pdf" })],
    });
    const vm = wrapper.vm as unknown as {
      prepararImportacionConstancia: (event: Event) => Promise<void>;
    };
    await vm.prepararImportacionConstancia({
      target: input,
    } as unknown as Event);

    expect(mockedPuntosVentaService.importarConstancia).toHaveBeenCalledOnce();
    expect(notificationMocks.showSuccess).toHaveBeenCalledWith(
      "Constancia importada",
      expect.stringContaining("Listos para emitir"),
    );
  });

  it("oculta acciones administrativas y limita la edición operativa a datos descriptivos", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    useAuthStore().user = usuarioMock(false);
    const punto = puntoVentaMock(1);
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([punto]);
    mockedPuntosVentaService.update.mockResolvedValue({
      ...punto,
      nombre: "Nombre operativo",
      domicilio: "Domicilio operativo",
      nombre_fantasia: "Fantasía operativa",
    });
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;
    setEmpresaActivaIdStorage(1);
    const wrapper = mount(PuntosVentaView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    const botonesVisibles = wrapper
      .findAll("button")
      .map((button) => button.text().trim());
    expect(botonesVisibles).not.toContain("Sincronizar con ARCA");
    expect(botonesVisibles).not.toContain("Importar constancia");
    expect(wrapper.text()).toContain("Podés comprobar puntos con ARCA");
    expect(botonesVisibles).toContain("Comprobar con ARCA");

    const vm = wrapper.vm as unknown as {
      editarPunto: (punto: PuntoVenta) => void;
      guardarEdicion: () => Promise<void>;
      editForm: Record<string, unknown>;
    };
    vm.editarPunto(punto);
    await flushPromises();
    expect(document.body.textContent).toContain("Editar punto de venta");
    expect(document.body.textContent).not.toContain(
      "Fecha de baja (DD/MM/AAAA o AAAA-MM-DD)",
    );
    vm.editForm.nombre = "Nombre operativo";
    vm.editForm.domicilio = "Domicilio operativo";
    vm.editForm.nombre_fantasia = "Fantasía operativa";
    vm.editForm.numero = 999;
    vm.editForm.sistema = "Cambio fiscal no autorizado";
    vm.editForm.activo = false;

    await vm.guardarEdicion();

    expect(mockedPuntosVentaService.update).toHaveBeenCalledWith(punto.id, {
      nombre: "Nombre operativo",
      domicilio: "Domicilio operativo",
      nombre_fantasia: "Fantasía operativa",
      usar_en_factuflow: true,
    });
    expect(mockedPuntosVentaService.sincronizarArca).not.toHaveBeenCalled();
    expect(mockedPuntosVentaService.importarConstancia).not.toHaveBeenCalled();
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
    useAuthStore().user = usuarioMock(true);
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
      .find((button) => button.text().includes("Comprobar con ARCA"));
    expect(sincronizarButton).toBeDefined();
    expect(sincronizarButton?.attributes("disabled")).toBeDefined();
    const vm = wrapper.vm as unknown as {
      sincronizar: () => Promise<void>;
      tieneCertificadoDisponible: boolean;
    };
    expect(vm.tieneCertificadoDisponible).toBe(false);

    await vm.sincronizar();

    expect(mockedPuntosVentaService.sincronizarArca).not.toHaveBeenCalled();
    expect(notificationMocks.showWarning).toHaveBeenCalledWith(
      "Certificado no disponible",
      expect.stringContaining("Cargá un certificado o restaurá sus archivos"),
    );
  });

  it("confirma antes de cambiar el uso compartido del punto", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    useAuthStore().user = usuarioMock(false);
    const punto = puntoVentaMock(1);
    mockedArcaService.getStatus.mockResolvedValue(
      statusMock("produccion", true),
    );
    mockedPuntosVentaService.getAll.mockResolvedValue([punto]);
    mockedPuntosVentaService.update.mockResolvedValue({
      ...punto,
      usar_en_factuflow: false,
      seleccionable_para_emision: false,
    });
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
      confirmarCambioUso: () => Promise<void>;
      editForm: Record<string, unknown>;
    };

    vm.editarPunto(punto);
    vm.editForm.usar_en_factuflow = false;
    await vm.guardarEdicion();
    await flushPromises();

    expect(mockedPuntosVentaService.update).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain("Dejar de usar este punto");
    expect(document.body.textContent).toContain(
      "Los borradores y perfiles se conservarán",
    );

    await vm.confirmarCambioUso();
    expect(mockedPuntosVentaService.update).toHaveBeenCalledWith(
      punto.id,
      expect.objectContaining({ usar_en_factuflow: false }),
    );
  });

  it("cierra el editor pendiente al cambiar de emisor", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    useAuthStore().user = usuarioMock(true);
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
    await flushPromises();
    expect(vm.puntoEditando?.id).toBe(punto.id);
    expect(document.body.textContent).toContain(
      "Datos administrados por FactuFlow",
    );
    expect(document.body.textContent).not.toContain("Fecha de baja");

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
    empresaStore.inicializarEmpresaActiva = vi
      .fn()
      .mockResolvedValue(undefined);

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
