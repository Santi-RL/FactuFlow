import { defineStore } from "pinia";
import { ref } from "vue";
import type {
  PuntoVenta,
  PuntoVentaCreate,
  PuntoVentaUpdate,
  SincronizarPuntosVentaResponse,
} from "@/types/punto_venta";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import { getEmpresaActivaIdForRequest } from "@/utils/empresa-activa-storage";

const EMISOR_ACTIVO_REQUERIDO =
  "Seleccioná un emisor activo antes de sincronizar puntos de venta con ARCA";
const EMISOR_ACTIVO_IMPORTACION_REQUERIDO =
  "Seleccioná un emisor activo antes de importar una constancia de ARCA";
const ERROR_PREPARACION_PUNTOS =
  "No pudimos comprobar algunos puntos. Seleccioná Comprobar con ARCA para volver a intentar.";

export const usePuntosVentaStore = defineStore("puntosVenta", () => {
  const puntosVenta = ref<PuntoVenta[]>([]);
  const loading = ref(false);
  const syncing = ref(false);
  const importing = ref(false);
  const preparingForSelection = ref(false);
  const preparationError = ref<string | null>(null);
  const error = ref<string | null>(null);
  let fetchPuntosVentaRequestId = 0;
  let syncFromArcaRequestId = 0;
  let importarConstanciaRequestId = 0;
  let prepareForSelectionRequestId = 0;
  let preparationPromise: Promise<boolean> | null = null;
  let preparationEmpresaId: number | null = null;

  const fetchPuntosVenta = async () => {
    const requestId = ++fetchPuntosVentaRequestId;
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    loading.value = true;
    error.value = null;
    try {
      const data = await puntosVentaService.getAll();
      if (
        requestId === fetchPuntosVentaRequestId &&
        empresaStore.empresaActivaId === empresaIdSolicitada
      ) {
        puntosVenta.value = data.sort((a, b) => a.numero - b.numero);
      }
    } catch (err: any) {
      if (requestId === fetchPuntosVentaRequestId) {
        error.value =
          err.response?.data?.detail || "Error al cargar los puntos de venta";
      }
      throw err;
    } finally {
      if (requestId === fetchPuntosVentaRequestId) {
        loading.value = false;
      }
    }
  };

  const createPuntoVenta = async (data: PuntoVentaCreate) => {
    loading.value = true;
    error.value = null;
    try {
      const nuevo = await puntosVentaService.create(data);
      puntosVenta.value = [...puntosVenta.value, nuevo].sort(
        (a, b) => a.numero - b.numero,
      );
      return nuevo;
    } catch (err: any) {
      error.value =
        err.response?.data?.detail || "Error al crear el punto de venta";
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const updatePuntoVenta = async (id: number, data: PuntoVentaUpdate) => {
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    const empresaIdConfirmadaSolicitada = empresaIdSolicitada
      ? String(empresaIdSolicitada)
      : null;
    const isCurrentRequest = () =>
      empresaIdConfirmadaSolicitada !== null &&
      empresaStore.empresaActivaId === empresaIdSolicitada &&
      getEmpresaActivaIdForRequest() === empresaIdConfirmadaSolicitada;

    loading.value = true;
    error.value = null;
    try {
      const actualizado = await puntosVentaService.update(id, data);
      if (isCurrentRequest()) {
        const index = puntosVenta.value.findIndex((pv) => pv.id === id);
        if (index !== -1) {
          puntosVenta.value[index] = actualizado;
        }
        puntosVenta.value = [...puntosVenta.value].sort(
          (a, b) => a.numero - b.numero,
        );
      }
      return actualizado;
    } catch (err: any) {
      if (isCurrentRequest()) {
        error.value =
          err.response?.data?.detail || "Error al actualizar el punto de venta";
      }
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const deletePuntoVenta = async (id: number) => {
    loading.value = true;
    error.value = null;
    try {
      await puntosVentaService.delete(id);
      puntosVenta.value = puntosVenta.value.filter((pv) => pv.id !== id);
    } catch (err: any) {
      error.value =
        err.response?.data?.detail || "Error al eliminar el punto de venta";
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const importarConstancia = async (file: File) => {
    const requestId = ++importarConstanciaRequestId;
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    const empresaIdConfirmadaSolicitada = empresaIdSolicitada
      ? String(empresaIdSolicitada)
      : null;
    const isCurrentRequest = () =>
      requestId === importarConstanciaRequestId &&
      empresaStore.empresaActivaId === empresaIdSolicitada &&
      empresaIdConfirmadaSolicitada !== null &&
      getEmpresaActivaIdForRequest() === empresaIdConfirmadaSolicitada;

    importing.value = true;
    error.value = null;
    if (
      !empresaIdConfirmadaSolicitada ||
      getEmpresaActivaIdForRequest() !== empresaIdConfirmadaSolicitada
    ) {
      error.value = EMISOR_ACTIVO_IMPORTACION_REQUERIDO;
      importing.value = false;
      throw new Error(EMISOR_ACTIVO_IMPORTACION_REQUERIDO);
    }

    try {
      const resultado = await puntosVentaService.importarConstancia(file);
      if (!isCurrentRequest()) return resultado;

      await fetchPuntosVenta();
      preparationError.value = null;
      return resultado;
    } catch (err: any) {
      if (isCurrentRequest()) {
        error.value =
          err.response?.data?.detail || "Error al importar constancia";
      }
      throw err;
    } finally {
      if (requestId === importarConstanciaRequestId) {
        importing.value = false;
      }
    }
  };

  const prepareForSelection = async (): Promise<boolean> => {
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    if (preparationPromise && preparationEmpresaId === empresaIdSolicitada) {
      return preparationPromise;
    }

    const requestId = ++prepareForSelectionRequestId;
    const empresaIdConfirmadaSolicitada = empresaIdSolicitada
      ? String(empresaIdSolicitada)
      : null;
    const isCurrentRequest = () =>
      requestId === prepareForSelectionRequestId &&
      empresaStore.empresaActivaId === empresaIdSolicitada &&
      empresaIdConfirmadaSolicitada !== null &&
      getEmpresaActivaIdForRequest() === empresaIdConfirmadaSolicitada;

    const runPreparation = async (): Promise<boolean> => {
      preparingForSelection.value = true;
      preparationError.value = null;
      try {
        await fetchPuntosVenta();
        if (!isCurrentRequest()) return false;

        const requiereComprobacion = puntosVenta.value.some(
          (punto) =>
            punto.elegibilidad_rece.estado_efectivo === "verificado_rece" &&
            punto.comprobacion_arca_desactualizada,
        );
        if (!requiereComprobacion) return true;

        try {
          await syncFromArca();
        } catch {
          if (isCurrentRequest()) {
            preparationError.value = ERROR_PREPARACION_PUNTOS;
          }
          return false;
        }
        return isCurrentRequest();
      } finally {
        if (requestId === prepareForSelectionRequestId) {
          preparingForSelection.value = false;
        }
      }
    };

    preparationEmpresaId = empresaIdSolicitada;
    const promise = runPreparation();
    preparationPromise = promise;
    try {
      return await promise;
    } finally {
      if (preparationPromise === promise) {
        preparationPromise = null;
        preparationEmpresaId = null;
      }
    }
  };

  const syncFromArca = async (): Promise<SincronizarPuntosVentaResponse> => {
    const requestId = ++syncFromArcaRequestId;
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    const empresaIdConfirmadaSolicitada = empresaIdSolicitada
      ? String(empresaIdSolicitada)
      : null;
    const isCurrentRequest = () =>
      requestId === syncFromArcaRequestId &&
      empresaStore.empresaActivaId === empresaIdSolicitada &&
      empresaIdConfirmadaSolicitada !== null &&
      getEmpresaActivaIdForRequest() === empresaIdConfirmadaSolicitada;
    const emptyResult: SincronizarPuntosVentaResponse = {
      total_arca: 0,
      nuevos: 0,
      existentes: 0,
      actualizados: 0,
      desactivados_ausentes: 0,
      comprobado_en: new Date(0).toISOString(),
    };

    syncing.value = true;
    error.value = null;
    if (
      !empresaIdConfirmadaSolicitada ||
      getEmpresaActivaIdForRequest() !== empresaIdConfirmadaSolicitada
    ) {
      error.value = EMISOR_ACTIVO_REQUERIDO;
      syncing.value = false;
      throw new Error(EMISOR_ACTIVO_REQUERIDO);
    }
    try {
      const resultado = await puntosVentaService.sincronizarArca();
      if (!isCurrentRequest()) return emptyResult;

      await fetchPuntosVenta();
      preparationError.value = null;
      return resultado;
    } catch (err: any) {
      if (!isCurrentRequest()) {
        return emptyResult;
      }

      error.value =
        err.response?.data?.detail || "Error al comprobar puntos de venta";
      throw err;
    } finally {
      if (requestId === syncFromArcaRequestId) {
        syncing.value = false;
      }
    }
  };

  return {
    puntosVenta,
    loading,
    syncing,
    importing,
    preparingForSelection,
    preparationError,
    error,
    fetchPuntosVenta,
    createPuntoVenta,
    updatePuntoVenta,
    deletePuntoVenta,
    importarConstancia,
    syncFromArca,
    prepareForSelection,
  };
});
