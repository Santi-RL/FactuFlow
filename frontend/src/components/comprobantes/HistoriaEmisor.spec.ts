import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import HistoriaEmisor from "./HistoriaEmisor.vue";
import type { LecturaHistorica } from "@/types/comprobante";

export const historiaSintetica: LecturaHistorica = {
  cobertura: "completa",
  origen: "evidencia_previa",
  punto_venta_numero: 5,
  emisor: {
    cuit: "20123456789",
    razon_social: "Emisor original sintético",
    domicilio: null,
    localidad: null,
    provincia: null,
    condicion_iva: null,
    ingresos_brutos: null,
    inicio_actividades: "2020-02-03",
  },
};

describe("HistoriaEmisor", () => {
  it("presenta originales nulos sin completarlos y usa fecha argentina", () => {
    const wrapper = mount(HistoriaEmisor, {
      props: {
        lectura: { ...historiaSintetica, cobertura: "incompleta" },
        detalle: true,
      },
    });
    expect(wrapper.text()).not.toContain("Datos originales incompletos");
    expect(wrapper.text()).toContain("Emisor original sintético");
    expect(wrapper.text()).toContain("No informado");
    expect(wrapper.text()).toContain("03/02/2020");
    expect(wrapper.text()).not.toContain("ficha actual");
  });

  it.each(["completa", "incompleta", "ausente", "no_verificable"] as const)(
    "conserva los datos con cobertura %s sin leyendas técnicas",
    (cobertura) => {
      const wrapper = mount(HistoriaEmisor, {
        props: {
          lectura: {
            ...historiaSintetica,
            cobertura,
            origen:
              cobertura === "ausente" || cobertura === "no_verificable"
                ? "ficha_actual"
                : "evidencia_previa",
          },
          detalle: true,
        },
      });
      expect(wrapper.text()).toContain("Emisor original sintético");
      expect(wrapper.text()).not.toMatch(
        /snapshot|ficha actual|datos originales|datos históricos no verificados/i,
      );
      if (cobertura === "no_verificable")
        expect(wrapper.text()).toContain("El PDF no está disponible");
      else expect(wrapper.text()).not.toContain("El PDF no está disponible");
    },
  );

  it.each(["completa", "incompleta", "ausente"] as const)(
    "no muestra avisos en filas con cobertura %s",
    (cobertura) => {
      const wrapper = mount(HistoriaEmisor, {
        props: { lectura: { ...historiaSintetica, cobertura } },
      });
      expect(wrapper.text()).toBe("");
    },
  );

  it("explica el PDF bloqueado también en filas compactas", () => {
    const wrapper = mount(HistoriaEmisor, {
      props: {
        lectura: { ...historiaSintetica, cobertura: "no_verificable" },
      },
    });
    expect(wrapper.text()).toBe(
      "El PDF no está disponible; consultá al responsable de la instalación.",
    );
  });

  it("escapa textos y oculta avisos innecesarios en filas con cobertura completa", () => {
    const lectura = {
      ...historiaSintetica,
      emisor: {
        ...historiaSintetica.emisor,
        razon_social: "<script>privado</script>",
      },
    };
    const wrapper = mount(HistoriaEmisor, {
      props: { lectura, detalle: true },
    });
    expect(wrapper.find("script").exists()).toBe(false);
    const compacta = mount(HistoriaEmisor, {
      props: { lectura: historiaSintetica },
    });
    expect(compacta.text()).toBe("");
  });
});
