import { defineStore } from "pinia";
import { ref } from "vue";
import type {
  PuntoVenta,
  PuntoVentaCreate,
  PuntoVentaUpdate,
  PuntoVentaArca,
} from "@/types/punto_venta";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { arcaService } from "@/services/arca.service";
import { useEmpresaStore } from "@/stores/empresa";
import { getEmpresaActivaIdForRequest } from "@/utils/empresa-activa-storage";

interface SyncResult {
  total_arca: number;
  nuevos: number;
  existentes: number;
}

const sistemaWebservice = (punto: PuntoVentaArca): string => {
  const emisionTipo = punto.emision_tipo?.trim();
  if (!emisionTipo) {
    return "Factura Electronica - Web Services";
  }

  const detalle = emisionTipo.replace(/^CAE\s*-\s*/i, "").trim();
  return detalle
    ? `Factura Electronica - ${detalle} - Web Services`
    : "Factura Electronica - Web Services";
};

const textoIndicaWebservice = (value: string | null): boolean =>
  /web\s*services?/i.test(value || "");

const EMISOR_ACTIVO_REQUERIDO =
  "Seleccioná un emisor activo antes de sincronizar puntos de venta con ARCA";

export const usePuntosVentaStore = defineStore("puntosVenta", () => {
  const puntosVenta = ref<PuntoVenta[]>([]);
  const loading = ref(false);
  const syncing = ref(false);
  const error = ref<string | null>(null);
  let fetchPuntosVentaRequestId = 0;
  let syncFromArcaRequestId = 0;

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
    syncing.value = true;
    error.value = null;
    try {
      const resultado = await puntosVentaService.importarConstancia(file);
      await fetchPuntosVenta();
      return resultado;
    } catch (err: any) {
      error.value =
        err.response?.data?.detail || "Error al importar constancia";
      throw err;
    } finally {
      syncing.value = false;
    }
  };

  const syncFromArca = async (): Promise<SyncResult> => {
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
    const emptyResult = { total_arca: 0, nuevos: 0, existentes: 0 };

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
      const [puntosArca, locales] = await Promise.all([
        arcaService.getPuntosVenta(),
        puntosVentaService.getAll(),
      ]);

      if (!isCurrentRequest()) {
        return emptyResult;
      }

      const habilitados = puntosArca.filter((pv: PuntoVentaArca) => {
        const fechaBaja = pv.fecha_baja?.trim().toUpperCase();
        return pv.bloqueado !== "S" && (!fechaBaja || fechaBaja === "NULL");
      });
      const existentes = new Map(locales.map((pv) => [pv.numero, pv]));
      const nuevos = habilitados.filter((pv) => !existentes.has(pv.numero));

      const creados: PuntoVenta[] = [];
      for (const pv of nuevos) {
        if (!isCurrentRequest()) {
          return emptyResult;
        }

        const creado = await puntosVentaService.create({
          numero: pv.numero,
          nombre: sistemaWebservice(pv),
          sistema: sistemaWebservice(pv),
          es_webservice: true,
          bloqueado: false,
          fecha_baja: null,
          fuente: "arca_wsfe",
        });

        if (!isCurrentRequest()) {
          return emptyResult;
        }
        creados.push(creado);
      }

      const actualizados: PuntoVenta[] = [];
      for (const pv of habilitados) {
        if (!isCurrentRequest()) {
          return emptyResult;
        }

        const local = existentes.get(pv.numero);
        if (!local) continue;

        const sistema = textoIndicaWebservice(local.sistema)
          ? local.sistema
          : sistemaWebservice(pv);
        const needsUpdate =
          !local.activo ||
          !local.es_webservice ||
          local.bloqueado ||
          !!local.fecha_baja ||
          !local.sistema ||
          !textoIndicaWebservice(local.sistema) ||
          !local.fuente;

        if (!needsUpdate) continue;

        const actualizado = await puntosVentaService.update(local.id, {
          nombre: local.nombre || sistema,
          sistema,
          es_webservice: true,
          bloqueado: false,
          fecha_baja: null,
          fuente: local.fuente || "arca_wsfe",
          activo: true,
        });

        if (!isCurrentRequest()) {
          return emptyResult;
        }
        actualizados.push(actualizado);
      }

      if (!isCurrentRequest()) {
        return emptyResult;
      }

      const actualizadosPorNumero = new Map(
        actualizados.map((pv) => [pv.numero, pv]),
      );
      const merged = [
        ...locales.map((pv) => actualizadosPorNumero.get(pv.numero) || pv),
        ...creados,
      ];
      puntosVenta.value = merged.sort((a, b) => a.numero - b.numero);

      return {
        total_arca: habilitados.length,
        nuevos: creados.length,
        existentes: habilitados.length - creados.length,
      };
    } catch (err: any) {
      if (!isCurrentRequest()) {
        return emptyResult;
      }

      error.value =
        err.response?.data?.detail || "Error al sincronizar puntos de venta";
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
    error,
    fetchPuntosVenta,
    createPuntoVenta,
    updatePuntoVenta,
    deletePuntoVenta,
    importarConstancia,
    syncFromArca,
  };
});
