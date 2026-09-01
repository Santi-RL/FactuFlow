import { defineStore } from "pinia";
import { ref } from "vue";
import type { Usuario, LoginCredentials, SetupData } from "@/types/auth";
import { authService } from "@/services/auth.service";
import { clearEmpresaActivaIdStorage } from "@/utils/empresa-activa-storage";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<Usuario | null>(null);
  const token = ref<string | null>(null);
  const isAuthenticated = ref(false);
  const loading = ref(false);

  const normalizarUsuario = (usuario: Usuario): Usuario => ({
    ...usuario,
    empresa_ids: Array.isArray(usuario.empresa_ids)
      ? usuario.empresa_ids
      : usuario.empresa_id
        ? [usuario.empresa_id]
        : [],
    puede_crear_editar_emisores: Boolean(usuario.puede_crear_editar_emisores),
  });

  // Inicializar desde localStorage
  const init = () => {
    const storedToken = localStorage.getItem("token");
    const storedUser = localStorage.getItem("user");

    if (storedToken && storedUser) {
      token.value = storedToken;
      user.value = normalizarUsuario(JSON.parse(storedUser) as Usuario);
      isAuthenticated.value = true;
    }
  };

  const login = async (credentials: LoginCredentials) => {
    loading.value = true;
    try {
      const response = await authService.login(credentials);

      token.value = response.access_token;
      user.value = normalizarUsuario(response.user);
      isAuthenticated.value = true;

      // Guardar en localStorage
      localStorage.setItem("token", response.access_token);
      localStorage.setItem("user", JSON.stringify(user.value));

      return response;
    } finally {
      loading.value = false;
    }
  };

  const limpiarSesionLocal = () => {
    token.value = null;
    user.value = null;
    isAuthenticated.value = false;
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    clearEmpresaActivaIdStorage();
  };

  const logout = async () => {
    try {
      await authService.logout();
    } catch {
      // El cierre local debe completarse aunque falle una limpieza remota futura.
    } finally {
      limpiarSesionLocal();
    }
  };

  const checkAuth = async () => {
    if (!token.value) return false;

    try {
      const userData = await authService.me();
      user.value = normalizarUsuario(userData);
      isAuthenticated.value = true;

      // Actualizar en localStorage
      localStorage.setItem("user", JSON.stringify(user.value));

      return true;
    } catch (error) {
      await logout();
      return false;
    }
  };

  const setup = async (data: SetupData) => {
    loading.value = true;
    try {
      const newUser = await authService.setup(data);
      return newUser;
    } finally {
      loading.value = false;
    }
  };

  return {
    user,
    token,
    isAuthenticated,
    loading,
    init,
    login,
    logout,
    checkAuth,
    setup,
  };
});
