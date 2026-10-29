import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComprobanteDetalleView from "./ComprobanteDetalleView.vue";
import comprobantesService from "@/services/comprobantes.service";
import pdfService from "@/services/pdf.service";
import { useEmpresaStore } from "@/stores/empresa";
import type { ComprobanteDetalle, LecturaHistorica } from "@/types/comprobante";

const { showError } = vi.hoisted(() => ({ showError: vi.fn() }));
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { id: "1" } }),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/services/comprobantes.service", () => ({
  default: { obtener: vi.fn() },
}));
vi.mock("@/services/pdf.service", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/pdf.service")>()),
  default: { descargarAutomatico: vi.fn(), previsualizarPDF: vi.fn() },
}));
vi.mock("@/composables/useNotification", () => ({
  useNotification: () => ({ showError }),
}));

const emisor: LecturaHistorica["emisor"] = {
  cuit: "20123456789",
  razon_social: "Emisor original sintético",
  domicilio: null,
  localidad: null,
  provincia: null,
  condicion_iva: null,
  ingresos_brutos: null,
  inicio_actividades: "2020-01-01",
};
const crearComprobante = (
  cobertura: LecturaHistorica["cobertura"],
): ComprobanteDetalle => ({
  id: 1,
  empresa_id: 1,
  punto_venta_id: 1,
  tipo_comprobante: 6,
  concepto: 1,
  numero: 7,
  punto_venta_numero: 5,
  fecha_emision: "2026-08-09",
  total: "121",
  subtotal: "100",
  descuento: "0",
  iva_21: "21",
  iva_10_5: "0",
  iva_27: "0",
  otros_impuestos: "0",
  moneda: "PES",
  cotizacion: "1",
  estado: "autorizado",
  cae: "12345678901234",
  cae_vencimiento: "2026-08-18",
  items: [],
  datos_historicos: {
    cobertura,
    origen:
      cobertura === "ausente" || cobertura === "no_verificable"
        ? "ficha_actual"
        : "evidencia_previa",
    punto_venta_numero: 5,
    emisor,
  },
});

describe("ComprobanteDetalleView, historia fiscal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setActivePinia(createPinia());
    useEmpresaStore().empresaActivaId = 1;
  });
  const cargar = async (cobertura: LecturaHistorica["cobertura"]) => {
    vi.mocked(comprobantesService.obtener).mockResolvedValue(
      crearComprobante(cobertura),
    );
    const wrapper = mount(ComprobanteDetalleView);
    await flushPromises();
    return wrapper;
  };

  it("usa el punto histórico también en el nombre del archivo", async () => {
    const wrapper = await cargar("incompleta");
    expect(wrapper.text()).toContain("0005-00000007");
    expect(wrapper.text()).toContain("Emisor original sintético");
    await wrapper
      .findAll("button")
      .find((b) => b.text().includes("Descargar PDF"))!
      .trigger("click");
    await flushPromises();
    expect(pdfService.descargarAutomatico).toHaveBeenCalledWith(
      1,
      expect.stringContaining("0005-00000007.pdf"),
    );
    wrapper.unmount();
  });

  it("mantiene la consulta y bloquea sólo los botones PDF ante evidencia inválida", async () => {
    const wrapper = await cargar("no_verificable");
    expect(wrapper.text()).toContain("Datos históricos no verificados");
    expect(wrapper.text()).toContain("consultá al responsable");
    const botones = wrapper
      .findAll("button")
      .filter((b) => b.text().includes("PDF"));
    expect(botones).toHaveLength(2);
    expect(botones.every((b) => b.attributes("disabled") !== undefined)).toBe(
      true,
    );
    expect(pdfService.descargarAutomatico).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("conserva PDF disponible para antecedentes sin snapshot", async () => {
    const wrapper = await cargar("ausente");
    expect(wrapper.text()).toContain("Sin snapshot histórico");
    const boton = wrapper
      .findAll("button")
      .find((b) => b.text().includes("Descargar PDF"))!;
    expect(boton.attributes("disabled")).toBeUndefined();
    wrapper.unmount();
  });

  it("descarta una consulta tardía al revocar el emisor", async () => {
    let resolver!: (comp: ComprobanteDetalle) => void;
    vi.mocked(comprobantesService.obtener).mockReturnValue(
      new Promise((resolve) => {
        resolver = resolve;
      }),
    );
    const wrapper = mount(ComprobanteDetalleView);
    useEmpresaStore().empresaActivaId = null;
    await flushPromises();
    resolver(crearComprobante("completa"));
    await flushPromises();
    expect(wrapper.text()).not.toContain("Emisor original sintético");
    expect(wrapper.text()).not.toContain("0005-00000007");
    expect(showError).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
