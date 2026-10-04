import { defineStore } from "pinia";
import { ref } from "vue";
import type {
  Cliente,
  ClienteCreate,
  ClienteUpdate,
  ClienteListParams,
} from "@/types/cliente";
import type { PaginatedResponse } from "@/types/api";
import { clientesService } from "@/services/clientes.service";
import { useEmpresaStore } from "@/stores/empresa";

export const useClientesStore = defineStore("clientes", () => {
  const clientes = ref<Cliente[]>([]);
  const clienteActual = ref<Cliente | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const pagination = ref({
    total: 0,
    page: 1,
    per_page: 30,
    pages: 0,
  });
  let fetchClientesRequestId = 0;
  let fetchClienteRequestId = 0;

  const fetchClientes = async (params?: ClienteListParams) => {
    const requestId = ++fetchClientesRequestId;
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    loading.value = true;
    error.value = null;
    try {
      const response: PaginatedResponse<Cliente> =
        await clientesService.getAll(params);
      if (
        requestId === fetchClientesRequestId &&
        empresaStore.empresaActivaId === empresaIdSolicitada
      ) {
        clientes.value = response.items;
        pagination.value = {
          total: response.total,
          page: response.page,
          per_page: response.per_page,
          pages: response.pages,
        };
      }
      return response;
    } catch (err: any) {
      if (requestId === fetchClientesRequestId) {
        error.value =
          err.response?.data?.detail || "Error al cargar los clientes";
      }
      throw err;
    } finally {
      if (requestId === fetchClientesRequestId) {
        loading.value = false;
      }
    }
  };

  const fetchCliente = async (id: number) => {
    const requestId = ++fetchClienteRequestId;
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    const sigueVigente = () =>
      requestId === fetchClienteRequestId &&
      empresaStore.empresaActivaId === empresaIdSolicitada;
    loading.value = true;
    error.value = null;
    clienteActual.value = null;
    try {
      const cliente = await clientesService.getById(id);
      if (!sigueVigente()) return undefined;
      clienteActual.value = cliente;
      return cliente;
    } catch (err: any) {
      if (!sigueVigente()) return undefined;
      error.value = err.response?.data?.detail || "Error al cargar el cliente";
      throw err;
    } finally {
      if (sigueVigente()) loading.value = false;
    }
  };

  const limpiarClienteActual = () => {
    fetchClienteRequestId += 1;
    clienteActual.value = null;
    error.value = null;
    loading.value = false;
  };

  const createCliente = async (data: ClienteCreate) => {
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    const sigueVigente = () =>
      empresaStore.empresaActivaId === empresaIdSolicitada;
    loading.value = true;
    error.value = null;
    try {
      const newCliente = await clientesService.create(data);
      if (sigueVigente()) clientes.value.unshift(newCliente);
      return newCliente;
    } catch (err: any) {
      if (!sigueVigente()) throw err;
      error.value = err.response?.data?.detail || "Error al crear el cliente";
      throw err;
    } finally {
      if (sigueVigente()) loading.value = false;
    }
  };

  const updateCliente = async (id: number, data: ClienteUpdate) => {
    const empresaStore = useEmpresaStore();
    const empresaIdSolicitada = empresaStore.empresaActivaId;
    const solicitudDetalleId = fetchClienteRequestId;
    const sigueVigente = () =>
      empresaStore.empresaActivaId === empresaIdSolicitada &&
      solicitudDetalleId === fetchClienteRequestId;
    loading.value = true;
    error.value = null;
    try {
      const updatedCliente = await clientesService.update(id, data);
      if (!sigueVigente()) return updatedCliente;
      const index = clientes.value.findIndex((c) => c.id === id);
      if (index !== -1) {
        clientes.value[index] = updatedCliente;
      }
      clienteActual.value = updatedCliente;
      return updatedCliente;
    } catch (err: any) {
      if (!sigueVigente()) throw err;
      error.value =
        err.response?.data?.detail || "Error al actualizar el cliente";
      throw err;
    } finally {
      if (sigueVigente()) loading.value = false;
    }
  };

  const deleteCliente = async (id: number) => {
    loading.value = true;
    error.value = null;
    try {
      await clientesService.delete(id);
      clientes.value = clientes.value.filter((c) => c.id !== id);
    } catch (err: any) {
      error.value =
        err.response?.data?.detail || "Error al eliminar el cliente";
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return {
    clientes,
    clienteActual,
    loading,
    error,
    pagination,
    fetchClientes,
    fetchCliente,
    limpiarClienteActual,
    createCliente,
    updateCliente,
    deleteCliente,
  };
});
