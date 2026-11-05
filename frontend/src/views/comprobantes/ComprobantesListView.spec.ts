import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import View from "./ComprobantesListView.vue";
import comprobantesService from "@/services/comprobantes.service";
import pdfService from "@/services/pdf.service";
import {
  resolverSeleccionPDF,
  descargarZIP,
} from "@/services/descargas-pdf.service";
import { useEmpresaStore } from "@/stores/empresa";
import { useComprobantesStore } from "@/stores/comprobantes";

vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/services/comprobantes.service", () => ({
  default: { listar: vi.fn() },
}));
vi.mock("@/services/pdf.service", () => ({
  default: { descargarAutomatico: vi.fn() },
  mensajeErrorPDF: async () => "Error PDF",
}));
vi.mock("@/services/descargas-pdf.service", () => ({
  resolverSeleccionPDF: vi.fn(),
  descargarZIP: vi.fn(),
  mensajeErrorZIP: async () => "No se descargó el ZIP",
}));

const fila = (id: number) => ({
  id,
  tipo_comprobante: 11,
  numero: id,
  punto_venta_numero: 5,
  fecha_emision: "2026-11-01",
  total: 100,
  moneda: "PES",
  estado: "autorizado",
  cliente_nombre: "Cliente sintético",
});
const pagina = (page = 1) => ({
  items: [fila(page)],
  total: 25,
  page,
  per_page: 20,
  pages: 2,
});
const montar = () =>
  mount(View, {
    global: { stubs: { BaseCard: { template: "<div><slot /></div>" } } },
  });

describe("descargas desde el listado", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    const empresa = useEmpresaStore();
    empresa.empresaActivaId = 1;
    empresa.empresa = { id: 1 } as never;
    vi.mocked(comprobantesService.listar).mockImplementation(
      async (params) => pagina(params.page) as never,
    );
    vi.mocked(resolverSeleccionPDF).mockResolvedValue(
      Array.from({ length: 25 }, (_, i) => i + 1),
    );
    vi.mocked(pdfService.descargarAutomatico).mockResolvedValue();
    vi.mocked(descargarZIP).mockResolvedValue();
  });

  it("descarga junto al ojo sin navegar ni perder los filtros", async () => {
    const wrapper = montar();
    await flushPromises();
    await wrapper.get('[title="Descargar PDF"]').trigger("click");
    await flushPromises();
    expect(pdfService.descargarAutomatico).toHaveBeenCalledWith(
      1,
      "Factura C_C_0005-00000001.pdf",
      expect.any(Function),
      expect.any(AbortSignal),
    );
    expect(wrapper.findAll('[title="Ver detalle"]')).toHaveLength(1);
    wrapper.unmount();
  });

  it("selecciona todas las páginas, excluye una y conserva la selección al paginar", async () => {
    const wrapper = montar();
    await flushPromises();
    await wrapper
      .findAll("button")
      .find((b) => b.text().includes("Seleccionar los 25"))!
      .trigger("click");
    await flushPromises();
    const store = useComprobantesStore();
    expect(store.seleccionPDF).toHaveLength(25);
    await wrapper
      .get('input[aria-label="Seleccionar comprobante 0005-00000001"]')
      .setValue(false);
    await wrapper
      .findAll("button")
      .find((b) => b.text() === "Siguiente")!
      .trigger("click");
    await flushPromises();
    expect(store.seleccionPDF).toHaveLength(24);
    expect(store.seleccionPDF).not.toContain(1);
    await wrapper
      .findAll("button")
      .find((b) => b.text().includes("Descargar 24 PDF"))!
      .trigger("click");
    await flushPromises();
    expect(descargarZIP).toHaveBeenCalledWith(
      store.seleccionPDF,
      expect.any(Function),
      expect.any(AbortSignal),
    );
    wrapper.unmount();
  });

  it("aplicar filtros limpia la selección y volver a montar conserva filtros/página", async () => {
    let wrapper = montar();
    await flushPromises();
    const store = useComprobantesStore();
    store.seleccionarPDF(1, true);
    await wrapper.get('input[type="date"]').setValue("2026-11-01");
    await wrapper
      .findAll("button")
      .find((b) => b.text() === "Aplicar Filtros")!
      .trigger("click");
    await flushPromises();
    expect(store.seleccionPDF).toEqual([]);
    await store.cambiarPagina(2);
    store.seleccionarPDF(2, true);
    wrapper.unmount();
    wrapper = montar();
    await flushPromises();
    expect(
      (wrapper.get('input[type="date"]').element as HTMLInputElement).value,
    ).toBe("2026-11-01");
    expect(store.paginaActual).toBe(2);
    expect(store.seleccionPDF).toEqual([2]);
    wrapper.unmount();
  });

  it("A→B→A invalida el archivo pendiente y el estado ocupado", async () => {
    let resolver!: () => void;
    vi.mocked(pdfService.descargarAutomatico).mockReturnValue(
      new Promise<void>((r) => {
        resolver = r;
      }),
    );
    const wrapper = montar();
    await flushPromises();
    await wrapper.get('[title="Descargar PDF"]').trigger("click");
    const vigente = vi.mocked(pdfService.descargarAutomatico).mock
      .calls[0]![2]!;
    useEmpresaStore().empresaActivaId = 2;
    useEmpresaStore().empresaActivaId = 1;
    expect(vigente()).toBe(false);
    resolver();
    await flushPromises();
    expect(
      wrapper.get('[title="Descargar PDF"]').attributes("disabled"),
    ).toBeUndefined();
    wrapper.unmount();
  });

  it("navegar al detalle conserva una descarga y evita repetirla al volver", async () => {
    let resolver!: () => void;
    vi.mocked(pdfService.descargarAutomatico).mockReturnValue(
      new Promise<void>((r) => {
        resolver = r;
      }),
    );
    let wrapper = montar();
    await flushPromises();
    await wrapper.get('[title="Descargar PDF"]').trigger("click");
    const [, , vigente, signal] = vi.mocked(pdfService.descargarAutomatico).mock
      .calls[0]!;
    wrapper.unmount();
    expect(vigente!()).toBe(true);
    expect(signal!.aborted).toBe(false);
    wrapper = montar();
    await flushPromises();
    expect(
      wrapper.get('[title="Descargar PDF"]').attributes("disabled"),
    ).toBeDefined();
    resolver();
    await flushPromises();
    expect(
      wrapper.get('[title="Descargar PDF"]').attributes("disabled"),
    ).toBeUndefined();
    wrapper.unmount();
  });

  it("la casilla de cabecera afecta sólo la página y conserva selecciones de otras páginas", async () => {
    const wrapper = montar();
    await flushPromises();
    await wrapper
      .get('input[aria-label="Seleccionar esta página"]')
      .setValue(true);
    await wrapper
      .findAll("button")
      .find((b) => b.text() === "Siguiente")!
      .trigger("click");
    await flushPromises();
    await wrapper
      .get('input[aria-label="Seleccionar esta página"]')
      .setValue(true);
    expect(useComprobantesStore().seleccionPDF).toEqual([1, 2]);
    await wrapper
      .get('input[aria-label="Seleccionar esta página"]')
      .setValue(false);
    expect(useComprobantesStore().seleccionPDF).toEqual([1]);
    wrapper.unmount();
  });

  it("invalidar selección cancela el ZIP y descarta un error atrasado", async () => {
    let rechazar!: (error: Error) => void;
    vi.mocked(descargarZIP).mockReturnValue(
      new Promise<void>((_, reject) => {
        rechazar = reject;
      }),
    );
    const wrapper = montar();
    await flushPromises();
    const store = useComprobantesStore();
    store.seleccionarPDF(1, true);
    await flushPromises();
    await wrapper
      .findAll("button")
      .find((b) => b.text().includes("Descargar 1 PDF"))!
      .trigger("click");
    const [, vigente, signal] = vi.mocked(descargarZIP).mock.calls[0]!;
    store.invalidarSeleccionPDF();
    expect(signal!.aborted).toBe(true);
    expect(vigente()).toBe(false);
    rechazar(new Error("error atrasado"));
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
