import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ComprobantePreview from "./ComprobantePreview.vue";

describe("ComprobantePreview", () => {
  it("no representa numeracion ausente como un comprobante cero", () => {
    const wrapper = mount(ComprobantePreview, {
      props: {
        formData: {
          tipo_comprobante: 6,
          fecha_emision: "2026-05-20",
          cliente: {
            razon_social: "Cliente Demo",
            numero_documento: "12345678",
            condicion_iva: "Consumidor Final",
          },
          items: [],
          observaciones: "",
        },
        totales: {
          subtotal: 0,
          iva21: 0,
          iva105: 0,
          iva27: 0,
          total: 0,
        },
        proximoNumero: null,
        puntoVentaNumero: 1,
        empresa: null,
      },
    });

    expect(wrapper.text()).toContain("Nro: No disponible");
    expect(wrapper.text()).not.toContain("0000-00000000");
    expect(
      wrapper.get('[data-testid="comprobante-confirmar-emitir"]').attributes(),
    ).toHaveProperty("disabled");
  });
});
