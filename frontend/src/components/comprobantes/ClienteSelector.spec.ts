import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { describe, expect, it } from "vitest";

import ClienteSelector from "./ClienteSelector.vue";

describe("ClienteSelector", () => {
  it("mantiene visible el dato legacy y exige corregirlo sin sustituirlo", async () => {
    const wrapper = mount(ClienteSelector, {
      props: {
        modelValue: {
          cliente_id: 15,
          tipo_documento: 80,
          numero_documento: "20409378472",
          razon_social: "Receptor sintético",
          condicion_iva: "Responsable No Inscripto",
        },
        tipoComprobante: 1,
      },
      global: { plugins: [createPinia()] },
    });
    const select = wrapper.get("#cliente-condicion-iva");
    expect(wrapper.get('[role="alert"]').text()).toContain(
      "Revisá la condición IVA",
    );
    expect(select.text()).toContain("Responsable No Inscripto (revisar)");
    expect(
      select
        .findAll("option")
        .filter((opcion) => !(opcion.element as HTMLOptionElement).disabled)
        .map((opcion) => opcion.text()),
    ).toEqual(["Seleccione...", "Responsable Inscripto", "Monotributo"]);
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    await select.setValue("Monotributo");
    expect(wrapper.emitted("update:modelValue")?.[0]?.[0]).toEqual(
      expect.objectContaining({
        cliente_id: undefined,
        condicion_iva: "Monotributo",
      }),
    );
  });

  it("oculta resultados si la búsqueda baja de dos caracteres", async () => {
    const wrapper = mount(ClienteSelector, {
      props: {
        modelValue: {
          tipo_documento: 99,
          numero_documento: "",
          razon_social: "",
          condicion_iva: "Consumidor Final",
        },
        tipoComprobante: 6,
      },
      global: {
        plugins: [createPinia()],
      },
    });
    const vm = wrapper.vm as unknown as {
      busqueda: string;
      mostrarResultados: boolean;
      buscarClientes: () => Promise<void>;
    };

    vm.mostrarResultados = true;
    vm.busqueda = "a";
    await vm.buscarClientes();

    expect(vm.mostrarResultados).toBe(false);
  });

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
