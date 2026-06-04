import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import comprobantesService from "@/services/comprobantes.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import { useEmpresaStore } from "@/stores/empresa";
import {
  TIPOS_COMPROBANTE,
  TIPOS_CONCEPTO,
  TIPOS_DOCUMENTO,
} from "@/types/comprobante";
import type { Empresa } from "@/types/empresa";
import type { PuntoVenta } from "@/types/punto_venta";
import ComprobanteNuevoView from "./ComprobanteNuevoView.vue";

vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("@/services/comprobantes.service", () => ({
  default: {
    listar: vi.fn(),
    emitir: vi.fn(),
    obtener: vi.fn(),
    proximoNumero: vi.fn(),
  },
}));

vi.mock("@/services/puntos_venta.service", () => ({
  puntosVentaService: {
    getAll: vi.fn(),
  },
}));

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
    showWarning: vi.fn(),
  }),
}));

const empresaMock = (): Empresa => ({
  id: 1,
  razon_social: "Emisor Demo",
  cuit: "30700000001",
  condicion_iva: "RI",
  ingresos_brutos: null,
  domicilio: "Av. Demo 123",
  localidad: "CABA",
  provincia: "CABA",
  codigo_postal: "1000",
  email: null,
  telefono: null,
  inicio_actividades: "2024-01-01",
  logo: null,
  created_at: "2024-01-01T00:00:00",
  updated_at: "2024-01-01T00:00:00",
});

const puntoVentaMock = (
  id: number,
  numero: number,
  overrides: Partial<PuntoVenta> = {},
): PuntoVenta => ({
  id,
  numero,
  nombre: `PV ${numero}`,
  sistema: "Factura Electronica - Web Services",
  domicilio: null,
  nombre_fantasia: null,
  es_webservice: true,
  bloqueado: false,
  fecha_baja: null,
  fuente: "arca_wsfe",
  activo: true,
  usable_factuflow: true,
  empresa_id: 1,
  created_at: "2024-01-01T00:00:00",
  ...overrides,
});

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
};

const mockedComprobantesService = comprobantesService as unknown as {
  proximoNumero: Mock;
  emitir: Mock;
};
const mockedPuntosVentaService = puntosVentaService as unknown as {
  getAll: Mock;
};

const mountView = async () => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const empresaStore = useEmpresaStore();
  empresaStore.empresa = empresaMock();
  empresaStore.empresaActivaId = 1;
  mockedPuntosVentaService.getAll.mockResolvedValue([
    puntoVentaMock(1, 1),
    puntoVentaMock(2, 2),
  ]);

  const wrapper = mount(ComprobanteNuevoView, {
    global: {
      plugins: [pinia],
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });
  await flushPromises();
  return wrapper;
};

describe("ComprobanteNuevoView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("ignora respuestas viejas al consultar el proximo numero", async () => {
    const primeraConsulta = deferred<{ proximo_numero: number }>();
    const segundaConsulta = deferred<{ proximo_numero: number }>();
    mockedComprobantesService.proximoNumero
      .mockReturnValueOnce(primeraConsulta.promise)
      .mockReturnValueOnce(segundaConsulta.promise);
    const wrapper = await mountView();
    const vm = wrapper.vm as unknown as {
      formData: { punto_venta_id: number };
      actualizarProximoNumero: () => Promise<void>;
      proximoNumero: number | null;
    };

    vm.formData.punto_venta_id = 2;
    const segundaActualizacion = vm.actualizarProximoNumero();
    segundaConsulta.resolve({ proximo_numero: 200 });
    await segundaActualizacion;
    expect(vm.proximoNumero).toBe(200);

    primeraConsulta.resolve({ proximo_numero: 100 });
    await flushPromises();
    expect(vm.proximoNumero).toBe(200);
  });

  it("selecciona por defecto el primer punto de venta usable", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const empresaStore = useEmpresaStore();
    empresaStore.empresa = empresaMock();
    empresaStore.empresaActivaId = 1;
    mockedPuntosVentaService.getAll.mockResolvedValue([
      puntoVentaMock(1, 1, {
        sistema: "Factuweb (Imprenta) - Monotributo",
        es_webservice: false,
        usable_factuflow: false,
      }),
      puntoVentaMock(2, 6),
    ]);
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 42,
    });

    const wrapper = mount(ComprobanteNuevoView, {
      global: {
        plugins: [pinia],
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    const vm = wrapper.vm as unknown as {
      formData: { punto_venta_id: number };
      proximoNumero: number | null;
    };

    expect(vm.formData.punto_venta_id).toBe(2);
    expect(mockedComprobantesService.proximoNumero).toHaveBeenCalledWith(6, 6);
    expect(vm.proximoNumero).toBe(42);
  });

  it("mantiene invalida una Factura A con receptor no CUIT", async () => {
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    const wrapper = await mountView();
    const vm = wrapper.vm as unknown as {
      formData: {
        tipo_comprobante: number;
        punto_venta_id: number;
        concepto: number | "";
        fecha_emision: string;
        cliente: {
          tipo_documento: number;
          numero_documento: string;
          razon_social: string;
          condicion_iva: string;
        };
        items: Array<{
          descripcion: string;
          cantidad: number;
          unidad: string;
          precio_unitario: number;
          descuento_porcentaje: number;
          iva_porcentaje: number;
          orden: number;
        }>;
      };
      formularioValido: boolean;
    };

    vm.formData.tipo_comprobante = TIPOS_COMPROBANTE.FACTURA_A;
    await flushPromises();
    vm.formData.punto_venta_id = 1;
    vm.formData.concepto = TIPOS_CONCEPTO.PRODUCTOS;
    vm.formData.fecha_emision = "2026-05-15";
    vm.formData.cliente = {
      tipo_documento: TIPOS_DOCUMENTO.DNI,
      numero_documento: "12345678",
      razon_social: "Cliente DNI",
      condicion_iva: "Consumidor Final",
    };
    vm.formData.items = [
      {
        descripcion: "Servicio",
        cantidad: 1,
        unidad: "unidades",
        precio_unitario: 100,
        descuento_porcentaje: 0,
        iva_porcentaje: 21,
        orden: 0,
      },
    ];
    await flushPromises();

    expect(vm.formularioValido).toBe(false);
    vm.formData.cliente.tipo_documento = TIPOS_DOCUMENTO.CUIT;
    await flushPromises();
    expect(vm.formularioValido).toBe(true);
  });

  it("envia una clave de idempotencia al confirmar la emision", async () => {
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    mockedComprobantesService.emitir.mockResolvedValue({
      exito: true,
      comprobante_id: 55,
      tipo_comprobante: 6,
      punto_venta: 1,
      numero: 100,
      fecha: "2026-05-20",
      cae: "12345678901234",
      cae_vencimiento: "2026-05-30",
      total: 121,
      mensaje: "Autorizado",
      errores: [],
    });
    const wrapper = await mountView();
    const vm = wrapper.vm as unknown as {
      formData: {
        punto_venta_id: number;
        concepto: number | "";
        fecha_emision: string;
        cliente: {
          tipo_documento: number;
          numero_documento: string;
          razon_social: string;
          condicion_iva: string;
        };
        items: Array<{
          descripcion: string;
          cantidad: number;
          unidad: string;
          precio_unitario: number;
          descuento_porcentaje: number;
          iva_porcentaje: number;
          orden: number;
        }>;
      };
      confirmarEmision: () => Promise<void>;
    };

    vm.formData.punto_venta_id = 1;
    vm.formData.concepto = TIPOS_CONCEPTO.PRODUCTOS;
    vm.formData.fecha_emision = "2026-05-20";
    vm.formData.cliente = {
      tipo_documento: TIPOS_DOCUMENTO.DNI,
      numero_documento: "12345678",
      razon_social: "Cliente Demo",
      condicion_iva: "Consumidor Final",
    };
    vm.formData.items = [
      {
        descripcion: "Servicio",
        cantidad: 1,
        unidad: "unidad",
        precio_unitario: 100,
        descuento_porcentaje: 0,
        iva_porcentaje: 21,
        orden: 0,
      },
    ];

    await vm.confirmarEmision();

    expect(mockedComprobantesService.emitir).toHaveBeenCalledWith(
      expect.objectContaining({
        confirmacion_fecha_fiscal: true,
      }),
      expect.any(String),
    );
  });
});
