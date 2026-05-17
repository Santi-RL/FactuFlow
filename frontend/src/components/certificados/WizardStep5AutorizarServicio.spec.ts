import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { Certificado } from "@/types/certificado";
import WizardStep5AutorizarServicio from "./WizardStep5AutorizarServicio.vue";

const certificadoMock = (): Certificado => ({
  id: 1,
  nombre: "Certificado Demo",
  cuit: "30700000001",
  fecha_emision: "2026-01-01",
  fecha_vencimiento: "2027-01-01",
  ambiente: "homologacion",
  archivo_crt: "cert.crt",
  archivo_key: "cert.key",
  activo: true,
  empresa_id: 1,
  created_at: "2026-01-01T00:00:00",
  updated_at: "2026-01-01T00:00:00",
  dias_restantes: 200,
  estado: "valido",
});

describe("WizardStep5AutorizarServicio", () => {
  it("expone el portal externo con noopener y noreferrer", () => {
    const wrapper = mount(WizardStep5AutorizarServicio, {
      props: { certificado: certificadoMock() },
    });
    const link = wrapper.get(
      'a[href="https://auth.afip.gob.ar/contribuyente_/login.xhtml"]',
    );

    expect(link.attributes("target")).toBe("_blank");
    expect(link.attributes("rel")).toBe("noopener noreferrer");
  });
});
