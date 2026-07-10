import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { describe, expect, it } from "vitest";

import ClienteSelector from "./ClienteSelector.vue";

describe("ClienteSelector", () => {
  it("desacopla el cliente guardado al editar sus datos fiscales", async () => {
    const wrapper = mount(ClienteSelector, {
      props: {
        modelValue: {
          cliente_id: 15,
          tipo_documento: 80,
          numero_documento: "30700000001",
          razon_social: "Cliente guardado",
          condicion_iva: "Responsable Inscripto",
          domicilio: "Calle 1",
        },
        tipoComprobante: 6,
      },
      global: {
        plugins: [createPinia()],
      },
    });
    const vm = wrapper.vm as unknown as {
      updateField: (field: string, value: string) => void;
    };

    vm.updateField("razon_social", "Receptor modificado");
    await wrapper.vm.$nextTick();

    const emisiones = wrapper.emitted("update:modelValue");
    expect(emisiones).toHaveLength(1);
    expect(emisiones?.[0]?.[0]).toEqual(
      expect.objectContaining({
        cliente_id: undefined,
        numero_documento: "30700000001",
        razon_social: "Receptor modificado",
      }),
    );
  });
});
