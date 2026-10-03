import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useEmpresaStore } from "@/stores/empresa";
import { useClientesStore } from "@/stores/clientes";
import { useComprobantesStore } from "@/stores/comprobantes";
import { clientesService } from "@/services/clientes.service";
import comprobantesService from "@/services/comprobantes.service";
import type { Cliente } from "@/types/cliente";
import type { ComprobanteDetalle } from "@/types/comprobante";
import ClienteDetailView from "./clientes/ClienteDetailView.vue";
import ClienteFormView from "./clientes/ClienteFormView.vue";
import ComprobanteDetalleView from "./comprobantes/ComprobanteDetalleView.vue";

const contexto = vi.hoisted(() => ({
  route: null as unknown as { params: { id?: string } },
  push: vi.fn(),
  showError: vi.fn(),
  showSuccess: vi.fn(),
}));

vi.mock("vue-router", async () => {
  const { reactive } = await import("vue");
  contexto.route = reactive({ params: { id: "1" } });
  return {
    useRoute: () => contexto.route,
    useRouter: () => ({ push: contexto.push }),
  };
});
vi.mock("@/composables/useNotification", () => ({
  useNotification: () => ({
    showError: contexto.showError,
    showSuccess: contexto.showSuccess,
  }),
}));
vi.mock("@/services/clientes.service", () => ({
  clientesService: {
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));
vi.mock("@/services/comprobantes.service", () => ({
  default: { obtener: vi.fn() },
}));

const cliente = (id: number, empresaId: number, nombre: string): Cliente => ({
  id,
  empresa_id: empresaId,
  razon_social: nombre,
  tipo_documento: "DNI",
  numero_documento: "10000001",
  condicion_iva: "CF",
  domicilio: null,
  localidad: null,
  provincia: null,
  codigo_postal: null,
  email: null,
  telefono: null,
  notas: null,
  activo: true,
  created_at: "2026-10-03T12:00:00Z",
  updated_at: "2026-10-03T12:00:00Z",
});

const comprobante = (
  id: number,
  empresaId: number,
  nombre: string,
): ComprobanteDetalle => ({
  id,
  empresa_id: empresaId,
  tipo_comprobante: 6,
  concepto: 1,
  numero: id,
  punto_venta_id: empresaId,
  punto_venta_numero: 1,
  fecha_emision: "2026-10-03",
  subtotal: 100,
  descuento: 0,
  iva_21: 21,
  iva_10_5: 0,
  iva_27: 0,
  otros_impuestos: 0,
  total: 121,
  estado: "autorizado",
  moneda: "PES",
  cotizacion: 1,
  cliente_nombre: nombre,
  cliente_cuit: "10000001",
  items: [],
});

const diferido = <T>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolver, rechazador) => {
    resolve = resolver;
    reject = rechazador;
  });
  return { promise, resolve, reject };
};

describe("identidad del emisor en detalles y formulario de clientes", () => {
  let wrapper: VueWrapper | undefined;
  let pinia: ReturnType<typeof createPinia>;

  beforeEach(() => {
    vi.resetAllMocks();
    contexto.route.params.id = "1";
    pinia = createPinia();
    setActivePinia(pinia);
    useEmpresaStore().empresaActivaId = 1;
  });
  afterEach(() => wrapper?.unmount());

  it("descarta el detalle de A al seleccionar B y respeta el rechazo de acceso", async () => {
    vi.mocked(clientesService.getById)
      .mockResolvedValueOnce(cliente(1, 1, "Cliente del emisor A"))
      .mockRejectedValueOnce({ response: { data: { detail: "No encontrado" } } });
    wrapper = mount(ClienteDetailView, { global: { plugins: [pinia] } });
    await flushPromises();
    expect(wrapper.text()).toContain("Cliente del emisor A");

    useEmpresaStore().empresaActivaId = 2;
    await flushPromises();

    expect(wrapper.text()).not.toContain("Cliente del emisor A");
    expect(useClientesStore().clienteActual).toBeNull();
    expect(contexto.push).toHaveBeenCalledWith("/clientes");
  });

  it("una respuesta tardía de A no reemplaza el detalle ya cargado de B", async () => {
    const anterior = diferido<Cliente>();
    vi.mocked(clientesService.getById)
      .mockReturnValueOnce(anterior.promise)
      .mockResolvedValueOnce(cliente(2, 2, "Cliente del emisor B"));
    wrapper = mount(ClienteDetailView, { global: { plugins: [pinia] } });

    useEmpresaStore().empresaActivaId = 2;
    contexto.route.params.id = "2";
    await flushPromises();
    expect(wrapper.text()).toContain("Cliente del emisor B");

    anterior.resolve(cliente(1, 1, "Cliente del emisor A"));
    await flushPromises();
    expect(wrapper.text()).not.toContain("Cliente del emisor A");
    expect(useClientesStore().clienteActual?.empresa_id).toBe(2);
    expect(contexto.push).not.toHaveBeenCalled();
  });

  it("recarga un detalle al cambiar solamente el ID de la ruta", async () => {
    vi.mocked(clientesService.getById)
      .mockResolvedValueOnce(cliente(1, 1, "Cliente anterior"))
      .mockResolvedValueOnce(cliente(2, 1, "Cliente siguiente"));
    wrapper = mount(ClienteDetailView, { global: { plugins: [pinia] } });
    await flushPromises();

    contexto.route.params.id = "2";
    await flushPromises();

    expect(wrapper.text()).toContain("Cliente siguiente");
    expect(wrapper.text()).not.toContain("Cliente anterior");
    expect(clientesService.getById).toHaveBeenLastCalledWith(2);
  });

  it("un error tardío de A no borra ni muestra un error en el comprobante de B", async () => {
    const anterior = diferido<ComprobanteDetalle>();
    vi.mocked(comprobantesService.obtener)
      .mockReturnValueOnce(anterior.promise)
      .mockResolvedValueOnce(comprobante(2, 2, "Receptor del emisor B"));
    wrapper = mount(ComprobanteDetalleView, { global: { plugins: [pinia] } });

    useEmpresaStore().empresaActivaId = 2;
    contexto.route.params.id = "2";
    await flushPromises();
    anterior.reject({ response: { data: { detail: "Acceso revocado a A" } } });
    await flushPromises();

    expect(wrapper.text()).toContain("Receptor del emisor B");
    expect(useComprobantesStore().comprobanteActual?.empresa_id).toBe(2);
    expect(contexto.showError).not.toHaveBeenCalled();
    expect(useComprobantesStore().error).toBeNull();
  });

  it("limpia un comprobante visible mientras carga el nuevo contexto", async () => {
    const siguiente = diferido<ComprobanteDetalle>();
    vi.mocked(comprobantesService.obtener)
      .mockResolvedValueOnce(comprobante(1, 1, "Receptor del emisor A"))
      .mockReturnValueOnce(siguiente.promise);
    wrapper = mount(ComprobanteDetalleView, { global: { plugins: [pinia] } });
    await flushPromises();
    expect(wrapper.text()).toContain("Receptor del emisor A");

    useEmpresaStore().empresaActivaId = 2;
    contexto.route.params.id = "2";
    await nextTick();
    expect(wrapper.text()).not.toContain("Receptor del emisor A");
    expect(useComprobantesStore().comprobanteActual).toBeNull();

    siguiente.resolve(comprobante(2, 2, "Receptor del emisor B"));
    await flushPromises();
    expect(wrapper.text()).toContain("Receptor del emisor B");
  });

  it("el formulario no guarda en B los datos cargados o editados en A", async () => {
    contexto.route.params.id = undefined;
    vi.mocked(clientesService.create).mockResolvedValue(cliente(2, 2, "Nuevo B"));
    wrapper = mount(ClienteFormView, { global: { plugins: [pinia] } });
    await wrapper.get('input[placeholder="Nombre o razón social del cliente"]').setValue("Datos de A");
    await wrapper.get('input[placeholder="20123456789"]').setValue("10000001");

    useEmpresaStore().empresaActivaId = 2;
    await nextTick();
    const razonSocial = wrapper.get('input[placeholder="Nombre o razón social del cliente"]');
    expect((razonSocial.element as HTMLInputElement).value).toBe("");
    expect((wrapper.get('input[placeholder="20123456789"]').element as HTMLInputElement).value).toBe("");
    await razonSocial.setValue("Nuevo B");
    await wrapper.get('input[placeholder="20123456789"]').setValue("10000002");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(clientesService.create).toHaveBeenCalledWith(
      expect.objectContaining({ razon_social: "Nuevo B", numero_documento: "10000002" }),
    );
    expect(clientesService.update).not.toHaveBeenCalled();
  });

  it("el formulario descarta una carga de edición anterior que responde tarde", async () => {
    const anterior = diferido<Cliente>();
    vi.mocked(clientesService.getById)
      .mockReturnValueOnce(anterior.promise)
      .mockResolvedValueOnce(cliente(2, 2, "Cliente editable B"));
    vi.mocked(clientesService.update).mockResolvedValue(cliente(2, 2, "Cliente editable B"));
    wrapper = mount(ClienteFormView, { global: { plugins: [pinia] } });
    useEmpresaStore().empresaActivaId = 2;
    contexto.route.params.id = "2";
    await flushPromises();
    anterior.resolve(cliente(1, 1, "Cliente editable A"));
    await flushPromises();

    const input = wrapper.get('input[placeholder="Nombre o razón social del cliente"]');
    expect((input.element as HTMLInputElement).value).toBe("Cliente editable B");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(clientesService.update).toHaveBeenCalledWith(
      2,
      expect.objectContaining({ razon_social: "Cliente editable B" }),
    );
  });

  it("una escritura de A que termina tarde no repuebla B ni redirige su formulario", async () => {
    const escritura = diferido<Cliente>();
    vi.mocked(clientesService.getById)
      .mockResolvedValueOnce(cliente(1, 1, "Cliente editable A"))
      .mockResolvedValueOnce(cliente(2, 2, "Cliente editable B"));
    vi.mocked(clientesService.update).mockReturnValueOnce(escritura.promise);
    wrapper = mount(ClienteFormView, { global: { plugins: [pinia] } });
    await flushPromises();
    await wrapper.get("form").trigger("submit");
    expect(clientesService.update).toHaveBeenCalledWith(1, expect.any(Object));

    useEmpresaStore().empresaActivaId = 2;
    contexto.route.params.id = "2";
    await flushPromises();
    escritura.resolve(cliente(1, 1, "Cliente actualizado A"));
    await flushPromises();

    const input = wrapper.get('input[placeholder="Nombre o razón social del cliente"]');
    expect((input.element as HTMLInputElement).value).toBe("Cliente editable B");
    expect(useClientesStore().clienteActual?.empresa_id).toBe(2);
    expect(contexto.showSuccess).not.toHaveBeenCalled();
    expect(contexto.push).not.toHaveBeenCalled();
  });

  it("descarta datos abiertos si deja de existir un emisor activo", async () => {
    vi.mocked(clientesService.getById).mockResolvedValue(cliente(1, 1, "Cliente del emisor A"));
    wrapper = mount(ClienteDetailView, { global: { plugins: [pinia] } });
    await flushPromises();
    useEmpresaStore().empresaActivaId = null;
    await nextTick();

    expect(wrapper.text()).not.toContain("Cliente del emisor A");
    expect(useClientesStore().clienteActual).toBeNull();
    expect(clientesService.getById).toHaveBeenCalledTimes(1);
  });

  it("no envía datos del formulario si el emisor acaba de cambiar antes de refrescar la vista", async () => {
    vi.mocked(clientesService.getById)
      .mockResolvedValueOnce(cliente(1, 1, "Cliente editable A"))
      .mockRejectedValueOnce({ response: { data: { detail: "No encontrado" } } });
    wrapper = mount(ClienteFormView, { global: { plugins: [pinia] } });
    await flushPromises();

    useEmpresaStore().empresaActivaId = 2;
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(clientesService.update).not.toHaveBeenCalled();
    expect(clientesService.create).not.toHaveBeenCalled();
  });
});
