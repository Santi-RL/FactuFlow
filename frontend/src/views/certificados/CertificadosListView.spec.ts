import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import certificadosService from "@/services/certificados.service";
import { useEmpresaStore } from "@/stores/empresa";
import type { Certificado } from "@/types/certificado";
import type { Empresa } from "@/types/empresa";
import CertificadosListView from "./CertificadosListView.vue";

vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("@/services/certificados.service", () => ({
  default: {
    listar: vi.fn(),
    verificarConexion: vi.fn(),
    eliminar: vi.fn(),
  },
}));

const empresaMock = (id: number): Empresa => ({
  id,
  razon_social: `Emisor ${id}`,
  cuit: `3070000000${id}`,
  condicion_iva: "RI",
  ingresos_brutos: null,
  domicilio: "Av. Demo 123",
  localidad: "CABA",
  provincia: "CABA",
  codigo_postal: "1000",
  email: null,
  telefono: null,
  inicio_actividades: "2024-01-01",
  logo: null,
  created_at: "2024-01-01T00:00:00",
  updated_at: "2024-01-01T00:00:00",
});

const certificadoMock = (empresaId: number, nombre: string): Certificado => ({
  id: empresaId,
  nombre,
  cuit: `3070000000${empresaId}`,
  fecha_emision: "2026-01-01",
  fecha_vencimiento: "2027-01-01",
  ambiente: "homologacion",
  archivo_crt: `${nombre}.crt`,
  archivo_key: `${nombre}.key`,
  activo: true,
  empresa_id: empresaId,
  created_at: "2026-01-01T00:00:00",
  updated_at: "2026-01-01T00:00:00",
  dias_restantes: 200,
  estado: "valido",
});

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
};

const mockedCertificadosService = certificadosService as unknown as {
  listar: Mock;
};

describe("CertificadosListView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("ignora listados viejos despues de cambiar el emisor activo", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const primeraCarga = deferred<Certificado[]>();
    const segundaCarga = deferred<Certificado[]>();
    mockedCertificadosService.listar
      .mockReturnValueOnce(primeraCarga.promise)
      .mockReturnValueOnce(segundaCarga.promise);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock(1);
    empresaStore.empresaActivaId = 1;

    const wrapper = mount(CertificadosListView, {
      global: {
        plugins: [pinia],
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    empresaStore.empresa = empresaMock(2);
    empresaStore.empresaActivaId = 2;
    await flushPromises();

    segundaCarga.resolve([certificadoMock(2, "Certificado B")]);
    await flushPromises();
    expect(wrapper.text()).toContain("Certificado B");

    primeraCarga.resolve([certificadoMock(1, "Certificado A")]);
    await flushPromises();
    expect(wrapper.text()).toContain("Certificado B");
    expect(wrapper.text()).not.toContain("Certificado A");
  });
});
