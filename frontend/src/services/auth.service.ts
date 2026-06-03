import apiClient from "./api";
import type {
  LoginCredentials,
  LoginResponse,
  SetupStatus,
  Usuario,
  SetupData,
} from "@/types/auth";

export const authService = {
  async checkBackendAvailable(): Promise<boolean> {
    try {
      await apiClient.get("/api/health");
      return true;
    } catch {
      return false;
    }
  },

  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>(
      "/api/auth/login",
      credentials,
    );
    return response.data;
  },

  async logout(): Promise<void> {
    // Limpiar el storage local
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  },

  async me(): Promise<Usuario> {
    const response = await apiClient.get<Usuario>("/api/auth/me");
    return response.data;
  },

  async setup(data: SetupData): Promise<Usuario> {
    const response = await apiClient.post<Usuario>("/api/auth/setup", data);
    return response.data;
  },

  async checkSetupRequired(): Promise<boolean> {
    const response = await apiClient.get<SetupStatus>("/api/auth/setup-status");
    return response.data.setup_required;
  },
};
