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

  const fetchEmpresa = async (id: number) => {
    loading.value = true;
    error.value = null;
    try {
      empresa.value = await empresaService.getById(id);
      empresaActivaId.value = empresa.value.id;
      setEmpresaActivaIdStorage(empresa.value.id);
    } catch (err: any) {
      if (empresaActivaId.value === id) {
        empresaActivaId.value = null;
        empresa.value = null;
        clearEmpresaActivaIdStorage();
      }
      error.value = err.response?.data?.detail || "Error al cargar la empresa";
      throw err;
    } finally {
      loading.value = false;
    }
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
    const authStore = useAuthStore();
    const empresaId = empresaActivaId.value || authStore.user?.empresa_id;
    if (!empresaId) return;
    await fetchEmpresa(empresaId);
  };

  const fetchEmpresas = async () => {
    const authStore = useAuthStore();
    if (!authStore.user?.es_admin) {
      empresas.value = empresa.value ? [empresa.value] : [];
      return empresas.value;
    }

    loading.value = true;
    error.value = null;
    try {
      empresas.value = await empresaService.getAll();
      return empresas.value;
    } catch (err: any) {
      error.value =
        err.response?.data?.detail || "Error al cargar las empresas";
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const setEmpresaActiva = async (id: number) => {
    clearEmpresaActivaIdForRequest();
    try {
      await fetchEmpresa(id);
    } catch (err) {
      empresa.value = null;
      empresaActivaId.value = null;
      clearEmpresaActivaIdStorage();
      throw err;
    }
  };

  const inicializarEmpresaActiva = async () => {
    const authStore = useAuthStore();
    if (!authStore.user) return;

    if (authStore.user.es_admin) {
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

      const empresaId = empresaPreferida?.id || empresas.value[0]?.id || null;
      if (empresaId) {
        await setEmpresaActiva(empresaId);
      } else {
        empresa.value = null;
        empresaActivaId.value = null;
        clearEmpresaActivaIdStorage();
      }
      return;
    }

    if (authStore.user.empresa_id) {
      clearEmpresaActivaIdForRequest();
      await fetchEmpresa(authStore.user.empresa_id);
      empresas.value = empresa.value ? [empresa.value] : [];
    }
  };

  return {
    empresa,
    empresas,
    empresaActiva,
    empresaActivaId,
    loading,
    error,
    fetchEmpresa,
    cargarEmpresa,
    createEmpresa,
    updateEmpresa,
    fetchEmpresas,
    setEmpresaActiva,
    inicializarEmpresaActiva,
  };
});
