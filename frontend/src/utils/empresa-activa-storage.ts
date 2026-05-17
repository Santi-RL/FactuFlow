const EMPRESA_ACTIVA_STORAGE_KEY = "empresa_activa_id";

let empresaActivaIdConfirmada: string | null = null;

const getSessionStorage = (): Storage | null => {
  return typeof window !== "undefined" ? window.sessionStorage : null;
};

const getLocalStorage = (): Storage | null => {
  return typeof window !== "undefined" ? window.localStorage : null;
};

export const getEmpresaActivaIdStorage = (): string | null => {
  const sessionValue =
    getSessionStorage()?.getItem(EMPRESA_ACTIVA_STORAGE_KEY) ?? null;
  if (sessionValue) return sessionValue;

  return getLocalStorage()?.getItem(EMPRESA_ACTIVA_STORAGE_KEY) ?? null;
};

export const getEmpresaActivaIdForRequest = (): string | null => {
  return empresaActivaIdConfirmada;
};

export const setEmpresaActivaIdStorage = (id: number): void => {
  const value = String(id);
  empresaActivaIdConfirmada = value;
  getSessionStorage()?.setItem(EMPRESA_ACTIVA_STORAGE_KEY, value);
  getLocalStorage()?.setItem(EMPRESA_ACTIVA_STORAGE_KEY, value);
};

export const clearEmpresaActivaIdForRequest = (): void => {
  empresaActivaIdConfirmada = null;
};

export const clearEmpresaActivaIdStorage = (): void => {
  clearEmpresaActivaIdForRequest();
  getSessionStorage()?.removeItem(EMPRESA_ACTIVA_STORAGE_KEY);
  getLocalStorage()?.removeItem(EMPRESA_ACTIVA_STORAGE_KEY);
};
