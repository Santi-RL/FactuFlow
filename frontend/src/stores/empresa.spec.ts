import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { empresaService } from "@/services/empresa.service";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import type { Usuario } from "@/types/auth";
import type { Empresa } from "@/types/empresa";
import {
  clearEmpresaActivaIdStorage,
  getEmpresaActivaIdForRequest,
} from "@/utils/empresa-activa-storage";

vi.mock("@/services/empresa.service", () => ({
  empresaService: {
    getAll: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

const empresaMock = (id: number, razonSocial: string): Empresa => ({
  id,
  razon_social: razonSocial,
  cuit: `30${String(id).padStart(9, "0")}`,
  condicion_iva: "RI",
  ingresos_brutos: null,
  domicilio: "Av. Siempre Viva 123",
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

const usuarioAdmin: Usuario = {
  id: 1,
  email: "admin@example.com",
  nombre: "Admin",
  empresa_id: null,
  activo: true,
  es_admin: true,
  created_at: "2024-01-01T00:00:00",
  ultimo_login: null,
};

const usuarioOperativo: Usuario = {
  id: 2,
  email: "operativo@example.com",
  nombre: "Operativo",
  empresa_id: 1,
  activo: true,
  es_admin: false,
  created_at: "2024-01-01T00:00:00",
  ultimo_login: null,
};

const mockedEmpresaService = empresaService as unknown as {
  getAll: Mock;
  getById: Mock;
};

describe("empresa store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    window.localStorage.clear();
    window.sessionStorage.clear();
    clearEmpresaActivaIdStorage();
    vi.clearAllMocks();
  });

  it("valida la preferencia guardada antes de confirmarla para requests", async () => {
    const empresaUno = empresaMock(1, "Emisor Uno");
    const empresaDos = empresaMock(2, "Emisor Dos");
    window.localStorage.setItem("empresa_activa_id", "999");

    mockedEmpresaService.getAll.mockResolvedValue([empresaUno, empresaDos]);
    mockedEmpresaService.getById.mockResolvedValue(empresaUno);

    const authStore = useAuthStore();
    authStore.user = usuarioAdmin;
    const empresaStore = useEmpresaStore();

    expect(getEmpresaActivaIdForRequest()).toBeNull();

    await empresaStore.inicializarEmpresaActiva();

    expect(mockedEmpresaService.getById).toHaveBeenCalledWith(1);
    expect(empresaStore.empresaActivaId).toBe(1);
    expect(window.localStorage.getItem("empresa_activa_id")).toBe("1");
    expect(window.sessionStorage.getItem("empresa_activa_id")).toBe("1");
    expect(getEmpresaActivaIdForRequest()).toBe("1");
  });

  it("limpia el emisor guardado cuando no hay emisores validos", async () => {
    window.localStorage.setItem("empresa_activa_id", "999");
    window.sessionStorage.setItem("empresa_activa_id", "999");
    mockedEmpresaService.getAll.mockResolvedValue([]);

    const authStore = useAuthStore();
    authStore.user = usuarioAdmin;
    const empresaStore = useEmpresaStore();

    await empresaStore.inicializarEmpresaActiva();

    expect(mockedEmpresaService.getById).not.toHaveBeenCalled();
    expect(empresaStore.empresaActivaId).toBeNull();
    expect(window.localStorage.getItem("empresa_activa_id")).toBeNull();
    expect(window.sessionStorage.getItem("empresa_activa_id")).toBeNull();
    expect(getEmpresaActivaIdForRequest()).toBeNull();
  });

  it("permite a un usuario operativo inicializar otro emisor guardado", async () => {
    const empresaUno = empresaMock(1, "Emisor Uno");
    const empresaDos = empresaMock(2, "Emisor Dos");
    window.localStorage.setItem("empresa_activa_id", "2");

    mockedEmpresaService.getAll.mockResolvedValue([empresaUno, empresaDos]);
    mockedEmpresaService.getById.mockResolvedValue(empresaDos);

    const authStore = useAuthStore();
    authStore.user = usuarioOperativo;
    const empresaStore = useEmpresaStore();

    await empresaStore.inicializarEmpresaActiva();

    expect(mockedEmpresaService.getAll).toHaveBeenCalled();
    expect(mockedEmpresaService.getById).toHaveBeenCalledWith(2);
    expect(empresaStore.empresaActivaId).toBe(2);
    expect(empresaStore.empresas).toHaveLength(2);
    expect(getEmpresaActivaIdForRequest()).toBe("2");
  });

  it("no persiste un emisor que falla la validacion", async () => {
    mockedEmpresaService.getById.mockRejectedValue({
      response: { data: { detail: "Empresa no encontrada" } },
    });

    const empresaStore = useEmpresaStore();

    await expect(empresaStore.setEmpresaActiva(999)).rejects.toEqual({
      response: { data: { detail: "Empresa no encontrada" } },
    });

    expect(empresaStore.empresaActivaId).toBeNull();
    expect(window.localStorage.getItem("empresa_activa_id")).toBeNull();
    expect(window.sessionStorage.getItem("empresa_activa_id")).toBeNull();
    expect(getEmpresaActivaIdForRequest()).toBeNull();
  });
});
