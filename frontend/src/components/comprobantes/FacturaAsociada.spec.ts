import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FacturaAsociada from "./FacturaAsociada.vue";
import comprobantesService from "@/services/comprobantes.service";
import type { PreparacionNota } from "@/types/comprobante";

vi.mock("vue-router", () => ({ useRoute: () => ({ query: {} }) }));
vi.mock("@/services/comprobantes.service", () => ({ default: { originalNota: vi.fn() } }));
const original = {
  origen: "arca", total: "121.00",
  asociado: { tipo_comprobante: 6, punto_venta: 4, numero: 12, fecha: "2026-08-09", cuit: "20123456789" },
} as PreparacionNota;
const consultar = async (wrapper: ReturnType<typeof mount>) => {
  await wrapper.get("#original-punto").setValue("00004");
  await wrapper.get("#original-numero").setValue("00000012");
  await wrapper.get("button").trigger("click");
};

describe("FacturaAsociada", () => {
  beforeEach(() => vi.clearAllMocks());
  it("consulta externos con la clase correcta y expone su procedencia", async () => {
    vi.mocked(comprobantesService.originalNota).mockResolvedValue(original);
    const wrapper = mount(FacturaAsociada, { props: { tipoNota: 8, empresaId: 1 } });
    await consultar(wrapper);
    await flushPromises();
    expect(comprobantesService.originalNota).toHaveBeenCalledWith(6, 4, 12);
    expect(wrapper.text()).toContain("consultada en ARCA");
    expect(wrapper.text()).toContain("121,00");
    expect(wrapper.emitted("preparada")?.slice(-1)[0]).toEqual([original]);
    await wrapper.get("#original-numero").setValue("13");
    expect(wrapper.emitted("preparada")?.slice(-1)[0]).toEqual([null]);
  });
  it.each(["emisor", "referencia"])("descarta una consulta tardía tras cambiar %s", async (cambio) => {
    let resolver!: (value: PreparacionNota) => void;
    vi.mocked(comprobantesService.originalNota).mockReturnValue(new Promise((resolve) => { resolver = resolve; }));
    const wrapper = mount(FacturaAsociada, { props: { tipoNota: 8, empresaId: 1 } });
    await consultar(wrapper);
    if (cambio === "emisor") await wrapper.setProps({ empresaId: 2 });
    else await wrapper.get("#original-numero").setValue("13");
    resolver(original);
    await flushPromises();
    expect(wrapper.emitted("preparada")?.slice(-1)[0]).toEqual([null]);
    expect(wrapper.text()).not.toContain("consultada en ARCA");
  });
  it("muestra el problema de consulta sin dar por inexistente la factura", async () => {
    vi.mocked(comprobantesService.originalNota).mockRejectedValue(new Error("timeout"));
    const wrapper = mount(FacturaAsociada, { props: { tipoNota: 8, empresaId: 1 } });
    await consultar(wrapper);
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("No se pudo consultar");
    expect(wrapper.emitted("preparada")?.slice(-1)[0]).toEqual([null]);
  });
  it("conserva la factura al cambiar entre crédito y débito de la misma clase", async () => {
    vi.mocked(comprobantesService.originalNota).mockResolvedValue(original);
    const wrapper = mount(FacturaAsociada, { props: { tipoNota: 8, empresaId: 1 } });
    await consultar(wrapper);
    await flushPromises();
    await wrapper.setProps({ tipoNota: 7 });
    expect(comprobantesService.originalNota).toHaveBeenCalledTimes(1);
    expect(wrapper.get<HTMLInputElement>("#original-numero").element.value).toBe("00000012");
    expect(wrapper.emitted("preparada")?.slice(-1)[0]).toEqual([original]);
  });
});
