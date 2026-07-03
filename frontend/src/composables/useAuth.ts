import { computed } from "vue";
import { useAuthStore } from "@/stores/auth";
import { SERVER_UNAVAILABLE_MESSAGE } from "@/constants/auth";
import { useRouter } from "vue-router";

const isNetworkError = (error: any): boolean =>
  !error.response &&
  (error.code === "ERR_NETWORK" ||
    error.code === "ECONNABORTED" ||
    Boolean(error.request));

export function useAuth() {
  const authStore = useAuthStore();
  const router = useRouter();

  const user = computed(() => authStore.user);
  const isAuthenticated = computed(() => authStore.isAuthenticated);
  const loading = computed(() => authStore.loading);

  const login = async (email: string, password: string) => {
    try {
      await authStore.login({ email, password });
      router.push("/");
    } catch (error: any) {
      if (isNetworkError(error)) {
        throw new Error(SERVER_UNAVAILABLE_MESSAGE);
      }
      throw new Error(
        error.response?.data?.detail || "Error al iniciar sesión",
      );
    }
  };

  const logout = async () => {
    await authStore.logout();
    router.push("/login");
  };

  return {
    user,
    isAuthenticated,
    loading,
    login,
    logout,
  };
}
