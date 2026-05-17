import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import certificadosService from "@/services/certificados.service";
import { useEmpresaStore } from "@/stores/empresa";
import Sidebar from "./Sidebar.vue";

vi.mock("vue-router", () => ({
  useRoute: () => ({
    path: "/",
  }),
}));

vi.mock("@/services/certificados.service", () => ({
  default: {
    obtenerAlertasVencimiento: vi.fn(),
  },
}));

const mockedCertificadosService = certificadosService as unknown as {
  obtenerAlertasVencimiento: Mock;
};

const mountSidebar = () => {
  const pinia = createPinia();
  setActivePinia(pinia);

  return mount(Sidebar, {
    global: {
      plugins: [pinia],
      stubs: {
        RouterLink: {
          props: ["to"],
          template: "<a><slot /></a>",
        },
      },
    },
  });
};

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCertificadosService.obtenerAlertasVencimiento.mockResolvedValue([]);
  });

  it("no consulta alertas de certificados hasta tener emisor activo", async () => {
    const wrapper = mountSidebar();
    await flushPromises();

    expect(
      mockedCertificadosService.obtenerAlertasVencimiento,
    ).not.toHaveBeenCalled();

    const empresaStore = useEmpresaStore();
    empresaStore.empresaActivaId = 3;
    await flushPromises();

    expect(
      mockedCertificadosService.obtenerAlertasVencimiento,
    ).toHaveBeenCalledTimes(1);

    wrapper.unmount();
  });

  it("recarga alertas cuando cambia el emisor activo", async () => {
    const wrapper = mountSidebar();
    const empresaStore = useEmpresaStore();

    empresaStore.empresaActivaId = 3;
    await flushPromises();
    empresaStore.empresaActivaId = 8;
    await flushPromises();

    expect(
      mockedCertificadosService.obtenerAlertasVencimiento,
    ).toHaveBeenCalledTimes(2);

    wrapper.unmount();
  });
});
