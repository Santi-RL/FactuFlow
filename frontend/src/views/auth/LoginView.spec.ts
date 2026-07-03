import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { authService } from "@/services/auth.service";
import LoginView from "./LoginView.vue";

const loginMock = vi.fn();

vi.mock("@/composables/useAuth", () => ({
  useAuth: () => ({
    login: loginMock,
    loading: ref(false),
  }),
}));

vi.mock("@/services/auth.service", () => ({
  authService: {
    checkBackendAvailable: vi.fn(),
    checkSetupRequired: vi.fn(),
  },
}));

const mockedAuthService = authService as unknown as {
  checkBackendAvailable: Mock;
  checkSetupRequired: Mock;
};

const mountView = () =>
  mount(LoginView, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });

const completarLogin = async (wrapper: ReturnType<typeof mount>) => {
  await wrapper.find('input[type="email"]').setValue("usuario@demo.com");
  await wrapper.find('input[type="password"]').setValue("secreto");
  await wrapper.find("form").trigger("submit.prevent");
  await flushPromises();
};

describe("LoginView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedAuthService.checkSetupRequired.mockResolvedValue(false);
  });

  it("muestra un mensaje claro si el backend no responde", async () => {
    mockedAuthService.checkBackendAvailable.mockResolvedValue(false);
    const wrapper = mountView();

    await completarLogin(wrapper);

    expect(loginMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain(
      "FactuFlow no está listo para iniciar sesión",
    );
    expect(wrapper.text()).toContain(
      "No se pudo conectar con el servidor local",
    );
    expect(wrapper.text()).toContain("acceso directo del escritorio");
    expect(wrapper.text()).toContain("Backend OK");
    expect(wrapper.text()).toContain("Reiniciar servicios");
    expect(wrapper.text()).not.toContain("Error al iniciar sesión");
  });

  it("mantiene separado el error de credenciales cuando el backend responde", async () => {
    mockedAuthService.checkBackendAvailable.mockResolvedValue(true);
    loginMock.mockRejectedValue(new Error("Correo o contraseña incorrectos"));
    const wrapper = mountView();

    await completarLogin(wrapper);

    expect(loginMock).toHaveBeenCalledWith("usuario@demo.com", "secreto");
    expect(wrapper.text()).toContain("Correo o contraseña incorrectos");
    expect(wrapper.text()).not.toContain(
      "FactuFlow no está listo para iniciar sesión",
    );
  });

  it("permite reintentar la conexion con el servidor local", async () => {
    mockedAuthService.checkBackendAvailable
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true);
    const wrapper = mountView();

    await completarLogin(wrapper);
    expect(wrapper.text()).toContain(
      "FactuFlow no está listo para iniciar sesión",
    );

    await wrapper.get("button").trigger("click");
    await flushPromises();

    expect(mockedAuthService.checkBackendAvailable).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).not.toContain(
      "FactuFlow no está listo para iniciar sesión",
    );
  });

  it("muestra el enlace de configuración solo si falta el setup inicial", async () => {
    mockedAuthService.checkSetupRequired.mockResolvedValueOnce(true);
    const wrapper = mountView();

    await flushPromises();

    expect(wrapper.text()).toContain("¿Primera instalación?");
    expect(wrapper.text()).toContain("Configurar sistema");
  });
});
