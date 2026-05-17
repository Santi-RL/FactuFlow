import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import type { ItemComprobante } from "@/types/comprobante";
import ItemsTable from "./ItemsTable.vue";

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => ({
    showWarning: vi.fn(),
  }),
}));

const item = (orden: number, descripcion: string): ItemComprobante => ({
  codigo: "",
  descripcion,
  cantidad: 1,
  unidad: "unidades",
  precio_unitario: 100,
  descuento_porcentaje: 0,
  iva_porcentaje: 21,
  orden,
});

const ultimaEmisionItems = (wrapper: ReturnType<typeof mount>) => {
  const emisiones = wrapper.emitted("update:items") || [];
  return emisiones[emisiones.length - 1]?.[0] as ItemComprobante[];
};

describe("ItemsTable", () => {
  it("reindexa el orden despues de eliminar y agregar items", async () => {
    const wrapper = mount(ItemsTable, {
      props: { items: [item(0, "Primero"), item(1, "Segundo")] },
    });

    await wrapper.findAll('button[title="Eliminar ítem"]')[0].trigger("click");
    const despuesDeEliminar = ultimaEmisionItems(wrapper);
    expect(despuesDeEliminar.map((row) => row.orden)).toEqual([0]);

    await wrapper.setProps({ items: despuesDeEliminar });
    await wrapper.find("button.bg-blue-50").trigger("click");
    const despuesDeAgregar = ultimaEmisionItems(wrapper);

    expect(despuesDeAgregar.map((row) => row.orden)).toEqual([0, 1]);
  });
});
