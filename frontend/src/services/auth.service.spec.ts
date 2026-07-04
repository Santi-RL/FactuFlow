import { beforeEach, describe, expect, it } from "vitest";

import { authService } from "@/services/auth.service";
import {
  getEmpresaActivaIdForRequest,
  setEmpresaActivaIdStorage,
} from "@/utils/empresa-activa-storage";

describe("authService", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("limpia credenciales y emisor activo persistidos al cerrar sesión", async () => {
    window.localStorage.setItem("token", "token-activo");
    window.localStorage.setItem("user", JSON.stringify({ id: 1 }));
    setEmpresaActivaIdStorage(25);

    await authService.logout();

    expect(window.localStorage.getItem("token")).toBeNull();
    expect(window.localStorage.getItem("user")).toBeNull();
    expect(window.localStorage.getItem("empresa_activa_id")).toBeNull();
    expect(window.sessionStorage.getItem("empresa_activa_id")).toBeNull();
    expect(getEmpresaActivaIdForRequest()).toBeNull();
  });
});