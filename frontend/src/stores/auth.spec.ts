import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { authService } from "@/services/auth.service";
import { useAuthStore } from "@/stores/auth";
import type { Usuario } from "@/types/auth";
import {
  getEmpresaActivaIdForRequest,
  setEmpresaActivaIdStorage,
} from "@/utils/empresa-activa-storage";

vi.mock("@/services/auth.service", () => ({
  authService: {
    login: vi.fn(),
    logout: vi.fn(),
    me: vi.fn(),
    setup: vi.fn(),
  },
}));

const usuarioMock: Usuario = {
  id: 1,
  email: "admin@example.com",
  nombre: "Admin",
  empresa_id: 1,
  activo: true,
  es_admin: true,
  created_at: "2024-01-01T00:00:00",
  ultimo_login: null,
};

const mockedAuthService = authService as unknown as {
  logout: Mock;
};

const prepararSesionPersistida = () => {
  window.localStorage.setItem("token", "token-activo");
  window.localStorage.setItem("user", JSON.stringify(usuarioMock));
  setEmpresaActivaIdStorage(25);
};

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("limpia estado y storage local al cerrar sesión", async () => {
    prepararSesionPersistida();
    mockedAuthService.logout.mockResolvedValue(undefined);
    const authStore = useAuthStore();
    authStore.init();

    await authStore.logout();

    expect(authStore.token).toBeNull();
    expect(authStore.user).toBeNull();
    expect(authStore.isAuthenticated).toBe(false);
    expect(window.localStorage.getItem("token")).toBeNull();
    expect(window.localStorage.getItem("user")).toBeNull();
    expect(window.localStorage.getItem("empresa_activa_id")).toBeNull();
    expect(window.sessionStorage.getItem("empresa_activa_id")).toBeNull();
    expect(getEmpresaActivaIdForRequest()).toBeNull();
  });

  it("limpia la sesión local aunque falle el servicio de logout", async () => {
    prepararSesionPersistida();
    mockedAuthService.logout.mockRejectedValue(new Error("backend no disponible"));
    const authStore = useAuthStore();
    authStore.init();

    await expect(authStore.logout()).resolves.toBeUndefined();

    expect(authStore.token).toBeNull();
    expect(authStore.user).toBeNull();
    expect(authStore.isAuthenticated).toBe(false);
    expect(window.localStorage.getItem("token")).toBeNull();
    expect(window.localStorage.getItem("user")).toBeNull();
    expect(window.localStorage.getItem("empresa_activa_id")).toBeNull();
    expect(window.sessionStorage.getItem("empresa_activa_id")).toBeNull();
    expect(getEmpresaActivaIdForRequest()).toBeNull();
  });
});