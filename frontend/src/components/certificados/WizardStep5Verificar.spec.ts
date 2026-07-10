import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import certificadosService from "@/services/certificados.service";
import WizardStep5Verificar from "./WizardStep5Verificar.vue";

vi.mock("@/services/certificados.service", () => ({
  default: {
    verificarConexion: vi.fn(),
  },
}));

describe("WizardStep5Verificar", () => {
  it("ignora reintentos mientras la verificación está en curso", async () => {
    let resolve!: (value: { exito: boolean; mensaje: string }) => void;
    const pendiente = new Promise<{ exito: boolean; mensaje: string }>(
      (resolver) => {
        resolve = resolver;
      },
    );
    const verificar = vi.mocked(certificadosService.verificarConexion);
    verificar.mockReturnValue(pendiente);
    const wrapper = mount(WizardStep5Verificar, {
      props: {
        certificado: {
          id: 7,
          nombre: "Certificado de prueba",
          cuit: "30700000001",
          fecha_emision: "2026-01-01",
          fecha_vencimiento: "2027-01-01",
          ambiente: "homologacion",
          archivo_crt: "prueba.crt",
          archivo_key: "prueba.key",
          activo: true,
          empresa_id: 1,
          created_at: "2026-01-01T00:00:00",
          updated_at: "2026-01-01T00:00:00",
          dias_restantes: 365,
          estado: "valido",
        },
      },
    });
    const vm = wrapper.vm as unknown as {
      verificarConexion: () => Promise<void>;
    };

    const primera = vm.verificarConexion();
    const segunda = vm.verificarConexion();

    expect(verificar).toHaveBeenCalledTimes(1);
    resolve({ exito: true, mensaje: "Conexión correcta" });
    await Promise.all([primera, segunda]);
  });
});
