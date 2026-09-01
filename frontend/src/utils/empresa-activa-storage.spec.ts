import {
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";

import {
  clearEmpresaActivaIdForRequest as clearRequest,
  clearEmpresaActivaIdStorage as clearStorage,
  getEmpresaActivaIdForRequest as getRequest,
  getEmpresaActivaIdStorage as getStorage,
  setEmpresaActivaIdStorage as setStorage,
} from "./empresa-activa-storage";

describe("empresa-activa-storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("usa únicamente el emisor activo de la pestaña", () => {
    window.localStorage.setItem("empresa_activa_id", "10");
    window.sessionStorage.setItem("empresa_activa_id", "20");

    expect(getStorage()).toBe("20");
  });

  it("no hereda el emisor guardado por otra pestaña en localStorage", () => {
    window.localStorage.setItem("empresa_activa_id", "10");

    expect(getStorage()).toBeNull();
    expect(getRequest()).toBeNull();
  });

  it("guarda y limpia el emisor activo confirmado", () => {
    setStorage(30);

    expect(window.sessionStorage.getItem("empresa_activa_id")).toBe("30");
    expect(window.localStorage.getItem("empresa_activa_id")).toBeNull();
    expect(getRequest()).toBe("30");

    clearRequest();

    expect(getStorage()).toBe("30");
    expect(getRequest()).toBeNull();

    clearStorage();

    expect(getStorage()).toBeNull();
    expect(getRequest()).toBeNull();
  });
});
