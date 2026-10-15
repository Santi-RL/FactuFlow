import { beforeEach, describe, expect, it, vi } from "vitest";

import { SERVER_UNAVAILABLE_MESSAGE } from "@/constants/auth";
import { useAuth } from "@/composables/useAuth";

const { login, push } = vi.hoisted(() => ({
  login: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({
    user: null,
    isAuthenticated: false,
    loading: false,
    login,
  }),
}));

vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));

describe("useAuth", () => {
  beforeEach(() => vi.clearAllMocks());

  it.each([
    {
      error: { code: "ERR_NETWORK" },
      message: SERVER_UNAVAILABLE_MESSAGE,
    },
    {
      error: { response: { data: { detail: "Credenciales inválidas" } } },
      message: "Credenciales inválidas",
    },
    { error: new Error("detalle interno"), message: "Error al iniciar sesión" },
  ])("conserva mensaje y causa del fallo: $message", async ({ error, message }) => {
    login.mockRejectedValue(error);

    const result = await useAuth()
      .login("operador@example.com", "clave-sintética")
      .catch((caught: unknown) => caught);

    expect(result).toBeInstanceOf(Error);
    expect((result as Error).message).toBe(message);
    expect((result as Error).cause).toBe(error);
    expect(push).not.toHaveBeenCalled();
  });

  it("navega al inicio cuando el login termina correctamente", async () => {
    login.mockResolvedValue(undefined);

    await useAuth().login("operador@example.com", "clave-sintética");

    expect(push).toHaveBeenCalledWith("/");
  });
});
