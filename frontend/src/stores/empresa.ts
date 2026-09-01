import { defineStore } from "pinia";
import { computed, ref } from "vue";
import type { Empresa, EmpresaCreate, EmpresaUpdate } from "@/types/empresa";
import { empresaService } from "@/services/empresa.service";
import { useAuthStore } from "@/stores/auth";
import {
  clearEmpresaActivaIdForRequest,
  clearEmpresaActivaIdStorage,
  getEmpresaActivaIdStorage,
  setEmpresaActivaIdStorage,
} from "@/utils/empresa-activa-storage";

export const useEmpresaStore = defineStore("empresa", () => {
  const empresa = ref<Empresa | null>(null);
  const empresas = ref<Empresa[]>([]);
  const empresaActivaId = ref<number | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const avisoAcceso = ref<string | null>(null);
  let solicitudEmpresaActivaId = 0;
  let solicitudListadoId = 0;
  let inicializacionEnCurso: Promise<void> | null = null;

  const empresaActiva = computed(() => {
    if (!empresaActivaId.value) {
      return empresa.value;
    }

    if (empresa.value && empresaActivaId.value === empresa.value.id) {
      return empresa.value;
    }

    return (
      empresas.value.find((item) => item.id === empresaActivaId.value) || null
    );
  });

  const esSolicitudEmpresaActivaActual = (solicitudId: number) =>
    solicitudId === solicitudEmpresaActivaId;

  const limpiarEmpresaActiva = (aviso: string | null = null) => {
    solicitudEmpresaActivaId += 1;
    empresa.value = null;
    empresaActivaId.value = null;
    avisoAcceso.value = aviso;
    clearEmpresaActivaIdStorage();
  };

  const cargarEmpresaPorId = async (id: number, solicitudId: number) => {
    loading.value = true;
    error.value = null;
    try {
      const empresaCargada = await empresaService.getById(id);
      if (!esSolicitudEmpresaActivaActual(solicitudId)) {
        return;
      }
      empresa.value = empresaCargada;
      empresaActivaId.value = empresaCargada.id;
      avisoAcceso.value = null;
      setEmpresaActivaIdStorage(empresaCargada.id);
    } catch (err: any) {
      if (!esSolicitudEmpresaActivaActual(solicitudId)) {
        return;
      }
      if (empresaActivaId.value === id) {
        empresaActivaId.value = null;
        empresa.value = null;
        clearEmpresaActivaIdStorage();
      }
      error.value = err.response?.data?.detail || "Error al cargar la empresa";
      throw err;
    } finally {
      if (esSolicitudEmpresaActivaActual(solicitudId)) {
        loading.value = false;
      }
    }
  };

  const fetchEmpresa = async (id: number) => {
    const solicitudId = ++solicitudEmpresaActivaId;
    await cargarEmpresaPorId(id, solicitudId);
  };

  const createEmpresa = async (data: EmpresaCreate) => {
    loading.value = true;
    error.value = null;
    try {
      empresa.value = await empresaService.create(data);
      empresas.value = [
        ...empresas.value.filter((item) => item.id !== empresa.value?.id),
        empresa.value,
      ];
      empresaActivaId.value = empresa.value.id;
      setEmpresaActivaIdStorage(empresa.value.id);
      return empresa.value;
    } catch (err: any) {
      error.value = err.response?.data?.detail || "Error al crear la empresa";
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const updateEmpresa = async (id: number, data: EmpresaUpdate) => {
    loading.value = true;
    error.value = null;
    try {
      empresa.value = await empresaService.update(id, data);
      empresas.value = empresas.value.map((item) =>
        item.id === empresa.value?.id ? empresa.value : item,
      );
      return empresa.value;
    } catch (err: any) {
      error.value =
        err.response?.data?.detail || "Error al actualizar la empresa";
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const cargarEmpresa = async () => {
    const empresaId =
      empresaActivaId.value ||
      (empresas.value.length === 1 ? empresas.value[0].id : null);
    if (!empresaId) return;
    await fetchEmpresa(empresaId);
  };

  const fetchEmpresas = async () => {
    const solicitudId = ++solicitudListadoId;
    loading.value = true;
    error.value = null;
    try {
      const empresasAutorizadas = await empresaService.getAll();
      if (solicitudId !== solicitudListadoId) {
        return empresas.value;
      }
      empresas.value = empresasAutorizadas;
      return empresas.value;
    } catch (err: any) {
      error.value =
        err.response?.data?.detail || "Error al cargar las empresas";
      throw err;
    } finally {
      if (solicitudId === solicitudListadoId) {
        loading.value = false;
      }
    }
  };

  const setEmpresaActiva = async (id: number) => {
    const solicitudId = ++solicitudEmpresaActivaId;
    clearEmpresaActivaIdForRequest();
    try {
      await cargarEmpresaPorId(id, solicitudId);
    } catch (err) {
      if (!esSolicitudEmpresaActivaActual(solicitudId)) {
        return;
      }
      empresa.value = null;
      empresaActivaId.value = null;
      clearEmpresaActivaIdStorage();
      throw err;
    }
  };

  const ejecutarInicializacionEmpresaActiva = async () => {
    const authStore = useAuthStore();
    if (!authStore.user) return;

    clearEmpresaActivaIdForRequest();
    await fetchEmpresas();

    const storedId = getEmpresaActivaIdStorage();
    const preferredId = storedId ? Number(storedId) : null;
    const empresaPreferida =
      Number.isFinite(preferredId) && preferredId
        ? empresas.value.find((item) => item.id === preferredId)
        : null;
    if (storedId && !empresaPreferida) {
      clearEmpresaActivaIdStorage();
    }

    const empresaId =
      empresaPreferida?.id ||
      (empresas.value.length === 1 ? empresas.value[0].id : null);

    if (empresaId) {
      await setEmpresaActiva(empresaId);
    } else {
      limpiarEmpresaActiva();
    }
  };

  const inicializarEmpresaActiva = async () => {
    if (inicializacionEnCurso) {
      await inicializacionEnCurso;
      return;
    }

    inicializacionEnCurso = ejecutarInicializacionEmpresaActiva();
    try {
      await inicializacionEnCurso;
    } finally {
      inicializacionEnCurso = null;
    }
  };

  const revalidarAccesos = async () => {
    const empresaAnteriorId = empresaActivaId.value;
    await fetchEmpresas();

    if (
      empresaAnteriorId &&
      !empresas.value.some((item) => item.id === empresaAnteriorId)
    ) {
      limpiarEmpresaActiva(
        "Tu acceso al emisor activo fue revocado. Elegí otro emisor habilitado para continuar.",
      );
      return true;
    }

    return false;
  };

  return {
    empresa,
    empresas,
    empresaActiva,
    empresaActivaId,
    loading,
    error,
    avisoAcceso,
    fetchEmpresa,
    cargarEmpresa,
    createEmpresa,
    updateEmpresa,
    fetchEmpresas,
    setEmpresaActiva,
    inicializarEmpresaActiva,
    limpiarEmpresaActiva,
    revalidarAccesos,
  };
});
