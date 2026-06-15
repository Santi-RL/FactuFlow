import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import certificadosService from "@/services/certificados.service";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import type { Usuario } from "@/types/auth";
import Sidebar from "./Sidebar.vue";

let mockedRoutePath = "/";

vi.mock("vue-router", () => ({
  useRoute: () => ({
    path: mockedRoutePath,
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

const usuarioBase: Usuario = {
  id: 1,
  email: "usuario@example.com",
  nombre: "Usuario",
  empresa_id: 1,
  activo: true,
  es_admin: false,
  created_at: "2024-01-01T00:00:00",
  ultimo_login: null,
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
          template: '<a v-bind="$attrs"><slot /></a>',
        },
      },
    },
  });
};

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedRoutePath = "/";
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

  it("oculta el menú Usuarios para usuarios operativos", async () => {
    const wrapper = mountSidebar();
    const authStore = useAuthStore();
    authStore.user = usuarioBase;
    await flushPromises();

    expect(wrapper.find('[data-testid="nav-usuarios"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="nav-sistema"]').exists()).toBe(false);

    wrapper.unmount();
  });

  it("muestra los menús administrativos para administradores", async () => {
    const wrapper = mountSidebar();
    const authStore = useAuthStore();
    authStore.user = { ...usuarioBase, es_admin: true };
    await flushPromises();

    expect(wrapper.find('[data-testid="nav-usuarios"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="nav-sistema"]').exists()).toBe(true);

    wrapper.unmount();
  });

  it("activa solo emisión masiva en la ruta de lotes", async () => {
    mockedRoutePath = "/comprobantes/lotes";

    const wrapper = mountSidebar();
    await flushPromises();

    expect(
      wrapper.find('[data-testid="nav-comprobantes"]').classes(),
    ).not.toContain("bg-brand-mint");
    expect(
      wrapper.find('[data-testid="nav-lotes-comprobantes"]').classes(),
    ).toContain("bg-brand-mint");

    wrapper.unmount();
  });

  it("mantiene comprobantes activo en rutas hijas de comprobantes", async () => {
    mockedRoutePath = "/comprobantes/nuevo";

    const wrapper = mountSidebar();
    await flushPromises();

    expect(wrapper.find('[data-testid="nav-comprobantes"]').classes()).toContain(
      "bg-brand-mint",
    );
    expect(
      wrapper.find('[data-testid="nav-lotes-comprobantes"]').classes(),
    ).not.toContain("bg-brand-mint");

    wrapper.unmount();
  });
});
