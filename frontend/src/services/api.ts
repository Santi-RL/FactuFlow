import axios, { AxiosError, CanceledError } from "axios";
import type { ApiError } from "@/types/api";
import {
  clearEmpresaActivaIdStorage,
  getEmpresaActivaIdForRequest,
} from "@/utils/empresa-activa-storage";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  headers: {
    "Content-Type": "application/json",
  },
});

export const EMPRESA_ACCESO_REVALIDAR_EVENT =
  "factuflow:empresa-acceso-revalidar";

const esRutaGlobalSinEmisor = (url = "") => {
  const path = url.split("?", 1)[0].replace(/\/$/, "");
  return /\/api\/(auth|usuarios)(\/|$)/.test(path) || path === "/api/empresas";
};

const getEmpresaIdDeRequest = (config?: AxiosError["config"]) => {
  const headers = config?.headers;
  if (!headers) return null;
  const value =
    typeof headers.get === "function"
      ? headers.get("X-Empresa-Id")
      : headers["X-Empresa-Id"];
  return value ? String(value) : null;
};

// Request interceptor para agregar el token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    const empresaActivaId = getEmpresaActivaIdForRequest();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (empresaActivaId && !esRutaGlobalSinEmisor(config.url)) {
      config.headers["X-Empresa-Id"] = empresaActivaId;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor para manejar errores
apiClient.interceptors.response.use(
  (response) => {
    const empresaSolicitada = getEmpresaIdDeRequest(response.config);
    const empresaActual = getEmpresaActivaIdForRequest();
    if (empresaSolicitada && empresaSolicitada !== empresaActual) {
      return Promise.reject(
        new CanceledError(
          "Se descartó una respuesta de un emisor que ya no está activo.",
        ),
      );
    }
    return response;
  },
  (error: AxiosError<ApiError>) => {
    const empresaSolicitada = getEmpresaIdDeRequest(error.config);
    const empresaActual = getEmpresaActivaIdForRequest();
    if (empresaSolicitada && empresaSolicitada !== empresaActual) {
      return Promise.reject(
        new CanceledError(
          "Se descartó un error de un emisor que ya no está activo.",
        ),
      );
    }
    // Si es 401, limpiar token y redirigir a login
    const requestUrl = error.config?.url || "";
    const isAuthLogin =
      requestUrl.includes("/api/auth/login") ||
      requestUrl.includes("auth/login");
    const isAuthSetup =
      requestUrl.includes("/api/auth/setup") ||
      requestUrl.includes("auth/setup");
    const isOnLoginPage = window.location.pathname === "/login";

    if (
      error.response?.status === 401 &&
      !isAuthLogin &&
      !isAuthSetup &&
      !isOnLoginPage
    ) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      clearEmpresaActivaIdStorage();
      window.location.href = "/login";
    }
    if (
      error.response?.status === 403 &&
      empresaSolicitada &&
      typeof window !== "undefined"
    ) {
      window.dispatchEvent(new CustomEvent(EMPRESA_ACCESO_REVALIDAR_EVENT));
    }
    return Promise.reject(error);
  },
);

export default apiClient;
