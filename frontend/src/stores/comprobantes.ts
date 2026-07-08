/**
 * Store de Comprobantes con Pinia
 */

import { defineStore } from "pinia";
import { ref, computed } from "vue";
import comprobantesService, {
  type ListarComprobantesParams,
} from "@/services/comprobantes.service";
import type {
  ComprobanteListItem,
  ComprobanteDetalle,
  EmitirComprobanteRequest,
  EmitirComprobanteResponse,
  PaginatedComprobantesResponse,
} from "@/types/comprobante";

interface ListarComprobantesOptions {
  conservarResultadosEnError?: boolean;
}

export const useComprobantesStore = defineStore("comprobantes", () => {
  const crearPaginacionVacia = (
    params: Partial<ListarComprobantesParams> = {},
  ) => ({
    total: 0,
    page: params.page ?? 1,
    per_page: params.per_page ?? 20,
    pages: 0,
  });
  // State
  const comprobantes = ref<ComprobanteListItem[]>([]);
  const comprobanteActual = ref<ComprobanteDetalle | null>(null);
  const paginacion = ref(crearPaginacionVacia());
  const loading = ref(false);
  const error = ref<string | null>(null);
  let solicitudListarComprobantesId = 0;

  const esSolicitudListarActual = (solicitudId: number) =>
    solicitudId === solicitudListarComprobantesId;

  // Filtros actuales
  const filtros = ref<Partial<ListarComprobantesParams>>({});

  // Getters
  const totalComprobantes = computed(() => paginacion.value.total);
  const hayComprobantes = computed(() => comprobantes.value.length > 0);
  const paginaActual = computed(() => paginacion.value.page);
  const totalPaginas = computed(() => paginacion.value.pages);

  // Actions
  async function listarComprobantes(
    params: ListarComprobantesParams,
    options: ListarComprobantesOptions = {},
  ) {
    const solicitudId = ++solicitudListarComprobantesId;
    const comprobantesPrevios = [...comprobantes.value];
    const paginacionPrevia = { ...paginacion.value };
    const filtrosPrevios = { ...filtros.value };
    const paginacionVacia = crearPaginacionVacia(params);
    loading.value = true;
    error.value = null;
    filtros.value = params;

    if (!options.conservarResultadosEnError) {
      comprobantes.value = [];
      paginacion.value = paginacionVacia;
    }

    try {
      const response: PaginatedComprobantesResponse =
        await comprobantesService.listar(params);

      if (!esSolicitudListarActual(solicitudId)) {
        return response;
      }

      comprobantes.value = response.items;
      paginacion.value = {
        total: response.total,
        page: response.page,
        per_page: response.per_page,
        pages: response.pages,
      };

      return response;
    } catch (e: any) {
      if (!esSolicitudListarActual(solicitudId)) {
        return undefined;
      }

      if (options.conservarResultadosEnError) {
        comprobantes.value = comprobantesPrevios;
        paginacion.value = paginacionPrevia;
        filtros.value = filtrosPrevios;
      } else {
        comprobantes.value = [];
        paginacion.value = paginacionVacia;
      }
      error.value = e.response?.data?.detail || "Error al listar comprobantes";
      throw e;
    } finally {
      if (esSolicitudListarActual(solicitudId)) {
        loading.value = false;
      }
    }
  }

  async function obtenerComprobante(id: number) {
    loading.value = true;
    error.value = null;
    comprobanteActual.value = null;

    try {
      const comprobante = await comprobantesService.obtener(id);
      comprobanteActual.value = comprobante;
      return comprobante;
    } catch (e: any) {
      error.value = e.response?.data?.detail || "Error al obtener comprobante";
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function emitirComprobante(
    request: EmitirComprobanteRequest,
    idempotencyKey: string,
  ): Promise<EmitirComprobanteResponse> {
    loading.value = true;
    error.value = null;

    try {
      const response = await comprobantesService.emitir(
        request,
        idempotencyKey,
      );

      if (!response.exito) {
        error.value = response.mensaje;
        return response;
      }

      // Recargar listado si hay filtros activos
      if (Object.keys(filtros.value).length > 0) {
        try {
          await listarComprobantes(filtros.value as ListarComprobantesParams, {
            conservarResultadosEnError: true,
          });
        } catch (refreshError) {
          console.warn(
            "No se pudo refrescar el listado despues de emitir",
            refreshError,
          );
          error.value = null;
        }
      }

      return response;
    } catch (e: any) {
      const errorMsg =
        e.response?.data?.detail?.mensaje || "Error al emitir comprobante";
      const errores = e.response?.data?.detail?.errores || [];

      error.value = `${errorMsg}: ${errores.join(", ")}`;
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function obtenerProximoNumero(
    puntoVenta: number,
    tipoComprobante: number,
  ) {
    try {
      const response = await comprobantesService.proximoNumero(
        puntoVenta,
        tipoComprobante,
      );
      return response.proximo_numero;
    } catch (e: any) {
      error.value =
        e.response?.data?.detail || "Error al obtener próximo número";
      throw e;
    }
  }

  function limpiarComprobanteActual() {
    comprobanteActual.value = null;
  }

  function limpiarError() {
    error.value = null;
  }

  async function cambiarPagina(pagina: number) {
    if (Object.keys(filtros.value).length === 0) return;

    try {
      await listarComprobantes(
        {
          ...filtros.value,
          page: pagina,
        } as ListarComprobantesParams,
        { conservarResultadosEnError: true },
      );
    } catch {
      // El error queda en el store; se conserva la página visible anterior.
    }
  }

  return {
    // State
    comprobantes,
    comprobanteActual,
    paginacion,
    loading,
    error,
    filtros,

    // Getters
    totalComprobantes,
    hayComprobantes,
    paginaActual,
    totalPaginas,

    // Actions
    listarComprobantes,
    obtenerComprobante,
    emitirComprobante,
    obtenerProximoNumero,
    limpiarComprobanteActual,
    limpiarError,
    cambiarPagina,
  };
});
