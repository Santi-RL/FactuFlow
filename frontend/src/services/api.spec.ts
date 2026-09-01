import axios, { AxiosError, type AxiosResponse } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import apiClient, { EMPRESA_ACCESO_REVALIDAR_EVENT } from "@/services/api";
import {
  clearEmpresaActivaIdStorage,
  setEmpresaActivaIdStorage,
} from "@/utils/empresa-activa-storage";

const respuestaOk = (config: AxiosResponse["config"]): AxiosResponse => ({
  data: { ok: true },
  status: 200,
  statusText: "OK",
  headers: {},
  config,
});

describe("apiClient y contexto de emisor", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    clearEmpresaActivaIdStorage();
  });

  it("descarta una respuesta tardía del emisor anterior", async () => {
    setEmpresaActivaIdStorage(1);

    await expect(
      apiClient.get("/api/clientes", {
        adapter: async (config) => {
          expect(config.headers.get("X-Empresa-Id")).toBe("1");
          setEmpresaActivaIdStorage(2);
          return respuestaOk(config);
        },
      }),
    ).rejects.toMatchObject({ code: "ERR_CANCELED" });
  });

  it("descarta también un error tardío del emisor anterior", async () => {
    setEmpresaActivaIdStorage(1);

    await expect(
      apiClient.get("/api/clientes", {
        adapter: async (config) => {
          setEmpresaActivaIdStorage(2);
          throw new AxiosError("Fallo tardío", undefined, config);
        },
      }),
    ).rejects.toMatchObject({ code: "ERR_CANCELED" });
  });

  it("no envía el emisor activo a contratos globales", async () => {
    setEmpresaActivaIdStorage(1);

    await apiClient.get("/api/empresas", {
      adapter: async (config) => {
        expect(config.headers.get("X-Empresa-Id")).toBeUndefined();
        return respuestaOk(config);
      },
    });
  });

  it("solicita revalidar accesos después de un 403 contextual", async () => {
    setEmpresaActivaIdStorage(1);
    const listener = vi.fn();
    window.addEventListener(EMPRESA_ACCESO_REVALIDAR_EVENT, listener);

    await expect(
      apiClient.get("/api/clientes", {
        adapter: async (config) => {
          throw new AxiosError("Prohibido", undefined, config, undefined, {
            data: { detail: "Sin acceso" },
            status: 403,
            statusText: "Forbidden",
            headers: {},
            config,
          });
        },
      }),
    ).rejects.toBeInstanceOf(axios.AxiosError);

    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(EMPRESA_ACCESO_REVALIDAR_EVENT, listener);
  });
});
