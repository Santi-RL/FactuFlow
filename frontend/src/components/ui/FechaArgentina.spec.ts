import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import FechaArgentina from "./FechaArgentina.vue";

describe("fecha argentina", () => {
  it("invalida el valor anterior al borrar o ingresar una fecha imposible", async () => {
    const wrapper = mount(FechaArgentina, { props: { modelValue: "2028-02-29" } });
    const entrada = wrapper.get<HTMLInputElement>('input[type="text"]');
    expect(entrada.element.value).toBe("29/02/2028");
    await entrada.setValue("29/02/2026");
    expect(wrapper.emitted("update:modelValue")?.slice(-1)[0]).toEqual([""]);
    await wrapper.setProps({ modelValue: "" });
    expect(entrada.element.value).toBe("29/02/2026");
    expect(entrada.element.checkValidity()).toBe(false);
    await entrada.setValue("");
    expect(entrada.element.checkValidity()).toBe(true);
    await entrada.setValue("03/09/2026");
    expect(wrapper.emitted("update:modelValue")?.slice(-1)[0]).toEqual(["2026-09-03"]);
  });

  it("el calendario, el mínimo y los cambios externos comparten la fecha civil", async () => {
    const wrapper = mount(FechaArgentina, { props: { min: "2026-11-09" } });
    const entrada = wrapper.get<HTMLInputElement>('input[type="text"]');
    const calendario = wrapper.get<HTMLInputElement>('input[type="date"]');
    await entrada.setValue("05/11/2026");
    expect(entrada.element.validationMessage).toContain("09/11/2026");
    await calendario.setValue("2026-11-10");
    expect(entrada.element.value).toBe("10/11/2026");
    expect(wrapper.emitted("update:modelValue")?.slice(-1)[0]).toEqual(["2026-11-10"]);
    await wrapper.setProps({ modelValue: "2027-01-04" });
    expect(entrada.element.value).toBe("04/01/2027");
    expect(entrada.element.checkValidity()).toBe(true);
  });
});
