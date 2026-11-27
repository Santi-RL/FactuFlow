import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { EditableItemComprobante as ItemComprobante } from "@/types/comprobante";
import ItemRow from "./ItemRow.vue";

describe("ItemRow PF-03B", () => {
  it("distingue precio borrado de cero escrito y no emite subtotal derivado", async () => {
    const item: ItemComprobante = {
      descripcion: "Prueba",
      cantidad: 1,
      unidad: "unidad",
      precio_unitario: 100,
      descuento_porcentaje: 0,
      iva_porcentaje: 21,
      orden: 0,
    };
    const wrapper = mount(ItemRow, { props: { item, index: 0 } });
    const precio = wrapper.get('input[aria-label="Precio Unitario"]');
    await precio.setValue("");
    const vacio = wrapper
      .emitted("update:item")!
      .slice(-1)[0][0] as ItemComprobante;
    expect(Number.isNaN(vacio.precio_unitario)).toBe(true);
    expect(vacio).not.toHaveProperty("subtotal");
    await wrapper.setProps({ item: vacio });
    expect(wrapper.text()).toContain("Revisá los importes");
    expect(wrapper.text()).not.toMatch(/NaN|∞/);
    await precio.setValue("0");
    const cero = wrapper
      .emitted("update:item")!
      .slice(-1)[0][0] as ItemComprobante;
    expect(cero.precio_unitario).toBe(0);
    await wrapper.setProps({ item: cero });
    expect(wrapper.text()).not.toContain("Revisá los importes");
    await precio.setValue("27.272,727272727272123456");
    const editado = wrapper.emitted("update:item")!.slice(-1)[0][0] as ItemComprobante;
    expect(editado.precio_unitario).toBe("27272.727272727272123456");
    await wrapper.setProps({ item: editado });
    await precio.trigger("blur");
    expect((precio.element as HTMLInputElement).value).toBe("27.272,727272727272123456");
    await precio.setValue("1.234");
    const ambiguo = wrapper.emitted("update:item")!.slice(-1)[0][0] as ItemComprobante;
    expect(Number.isNaN(ambiguo.precio_unitario)).toBe(true);
    await wrapper.setProps({ item: ambiguo });
    await precio.trigger("blur");
    expect((precio.element as HTMLInputElement).value).toBe("1.234");
    expect(wrapper.text()).toContain("Usá coma decimal");
  });
});
