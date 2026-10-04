import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { Certificado } from "@/types/certificado";
import CertificadoCard from "./CertificadoCard.vue";

describe("CertificadoCard", () => {
  it.each([
    ["2026-01-01", "01/01/2026"],
    ["2026-12-31", "31/12/2026"],
  ])("muestra el vencimiento %s sin desplazarlo un día", (fecha, esperada) => {
    const certificado: Certificado = {
      id: 1,
      nombre: "Certificado de prueba",
      cuit: "30700000001",
      fecha_emision: "2026-01-01",
      fecha_vencimiento: fecha,
      ambiente: "homologacion",
      archivo_crt: "cert.crt",
      archivo_key: "cert.key",
      activo: true,
      empresa_id: 1,
      created_at: "2026-01-01T00:00:00",
      updated_at: "2026-01-01T00:00:00",
      dias_restantes: 89,
      estado: "valido",
    };
    const wrapper = mount(CertificadoCard, { props: { certificado } });

    expect(wrapper.text()).toContain(esperada);
  });
});
