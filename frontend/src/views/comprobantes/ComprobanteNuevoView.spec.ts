import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
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
import type {
  EmitirComprobanteRequest,
  EmitirComprobanteResponse,
} from "@/types/comprobante";
import type { Empresa } from "@/types/empresa";
import type { PuntoVenta } from "@/types/punto_venta";
import ComprobanteNuevoView from "./ComprobanteNuevoView.vue";

vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  onBeforeRouteLeave: vi.fn(),
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

interface ComprobanteNuevoViewModel {
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
    items: EmitirComprobanteRequest["items"];
  };
  confirmarEmision: () => Promise<void>;
  verificarEstado: () => Promise<void>;
  loading: boolean;
  idempotencyKeyEmision: string | null;
  operacionIncierta: {
    idempotencyKey: string;
    empresaId: number;
    request: EmitirComprobanteRequest;
    respuesta: EmitirComprobanteResponse;
  } | null;
}

const errorReconciliacion = (
  overrides: Partial<EmitirComprobanteResponse> = {},
) => ({
  response: {
    data: {
      detail: {
        exito: false,
        tipo_comprobante: 6,
        punto_venta: 1,
        numero: 100,
        fecha: "2026-05-20",
        total: 121,
        mensaje: "<img src=x onerror=alert(1)>",
        errores: ["backend no confiable"],
        requiere_reconciliacion: true,
        categoria_error: "arca_respuesta_incierta",
        ...overrides,
      },
    },
  },
});

const completarFormulario = async (
  wrapper: VueWrapper,
): Promise<ComprobanteNuevoViewModel> => {
  const vm = wrapper.vm as unknown as ComprobanteNuevoViewModel;
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
  await flushPromises();
  return vm;
};

const respuestaFinal = (
  overrides: Partial<EmitirComprobanteResponse> = {},
): EmitirComprobanteResponse => ({
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
  ...overrides,
});

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

  it("limpia fechas de servicio al volver a productos", async () => {
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    const wrapper = await mountView();
    const vm = wrapper.vm as unknown as {
      formData: {
        concepto: number | "";
        fecha_servicio_desde: string;
        fecha_servicio_hasta: string;
        fecha_vto_pago: string;
      };
    };

    vm.formData.concepto = TIPOS_CONCEPTO.SERVICIOS;
    vm.formData.fecha_servicio_desde = "2026-05-01";
    vm.formData.fecha_servicio_hasta = "2026-05-31";
    vm.formData.fecha_vto_pago = "2026-06-10";
    await flushPromises();

    vm.formData.concepto = TIPOS_CONCEPTO.PRODUCTOS;
    await flushPromises();

    expect(vm.formData.fecha_servicio_desde).toBe("");
    expect(vm.formData.fecha_servicio_hasta).toBe("");
    expect(vm.formData.fecha_vto_pago).toBe("");
  });

  it("bloquea la vista previa si no puede confirmar la numeracion", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    mockedComprobantesService.proximoNumero.mockRejectedValue(
      new Error("ARCA no disponible"),
    );

    try {
      const wrapper = await mountView();
      const vm = wrapper.vm as unknown as {
        abrirVistaPrevia: () => void;
        errorProximoNumero: string;
        mostrarPreview: boolean;
        proximoNumero: number | null;
      };

      vm.abrirVistaPrevia();

      expect(vm.proximoNumero).toBeNull();
      expect(vm.errorProximoNumero).toBe(
        "No se pudo confirmar la numeración fiscal con ARCA.",
      );
      expect(vm.mostrarPreview).toBe(false);
    } finally {
      consoleError.mockRestore();
    }
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
  it("muestra un estado dedicado y congela la operación ante un 409 incierto", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    mockedComprobantesService.emitir.mockRejectedValue(errorReconciliacion());

    try {
      const wrapper = await mountView();
      const vm = await completarFormulario(wrapper);

      await vm.confirmarEmision();
      await flushPromises();

      expect(
        wrapper.get('[data-testid="operacion-incierta"]').text(),
      ).toContain("Emisión pendiente de verificación");
      expect(
        wrapper.get('[data-testid="formulario-emision"]').attributes(),
      ).toHaveProperty("inert");
      expect(wrapper.text()).not.toContain("<img src=x");
      expect(vm.operacionIncierta).not.toBeNull();
      expect(Object.isFrozen(vm.operacionIncierta?.request)).toBe(true);
      expect(Object.isFrozen(vm.operacionIncierta?.request.items)).toBe(true);
      expect(vm.operacionIncierta?.respuesta.mensaje).toContain(
        "no puede confirmar todavía",
      );
    } finally {
      consoleError.mockRestore();
    }
  });

  it("verifica con la misma clave y el mismo payload hasta obtener autorización", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    mockedComprobantesService.emitir
      .mockRejectedValueOnce(errorReconciliacion())
      .mockResolvedValueOnce(respuestaFinal());

    try {
      const wrapper = await mountView();
      const vm = await completarFormulario(wrapper);

      await vm.confirmarEmision();
      const [requestInicial, claveInicial] =
        mockedComprobantesService.emitir.mock.calls[0];

      await vm.verificarEstado();

      const [requestReplay, claveReplay] =
        mockedComprobantesService.emitir.mock.calls[1];
      expect(claveReplay).toBe(claveInicial);
      expect(requestReplay).toEqual(requestInicial);
      expect(vm.operacionIncierta).toBeNull();
      expect(vm.idempotencyKeyEmision).toBeNull();
      expect(wrapper.find('[data-testid="operacion-incierta"]').exists()).toBe(
        false,
      );
    } finally {
      consoleError.mockRestore();
    }
  });

  it("conserva el snapshot y bloquea la verificación si cambia el emisor", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    mockedComprobantesService.emitir.mockRejectedValue(errorReconciliacion());

    try {
      const wrapper = await mountView();
      const vm = await completarFormulario(wrapper);
      await vm.confirmarEmision();

      const claveOriginal = vm.operacionIncierta?.idempotencyKey;
      const fechaOriginal = vm.operacionIncierta?.request.fecha_emision;
      const empresaStore = useEmpresaStore();
      empresaStore.empresaActivaId = 2;
      vm.formData.fecha_emision = "2026-05-21";
      await flushPromises();

      expect(vm.operacionIncierta?.idempotencyKey).toBe(claveOriginal);
      expect(vm.operacionIncierta?.request.fecha_emision).toBe(fechaOriginal);
      expect(
        wrapper
          .get('[data-testid="verificar-operacion-incierta"]')
          .attributes(),
      ).toHaveProperty("disabled");
      expect(
        wrapper
          .get('[data-testid="operacion-incierta-emisor-distinto"]')
          .text(),
      ).toContain("operación permanece bloqueada");
    } finally {
      consoleError.mockRestore();
    }
  });

  it("evita dos solicitudes efectivas ante una interacción duplicada", async () => {
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    const emisionDiferida = deferred<EmitirComprobanteResponse>();
    mockedComprobantesService.emitir.mockReturnValue(emisionDiferida.promise);
    const wrapper = await mountView();
    const vm = await completarFormulario(wrapper);

    const primera = vm.confirmarEmision();
    const segunda = vm.confirmarEmision();

    expect(mockedComprobantesService.emitir).toHaveBeenCalledTimes(1);
    emisionDiferida.resolve(respuestaFinal());
    await Promise.all([primera, segunda]);
  });

  it("desbloquea el formulario cuando la verificación devuelve un rechazo final", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    mockedComprobantesService.emitir
      .mockRejectedValueOnce(errorReconciliacion())
      .mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            detail: {
              mensaje: "Rechazado por ARCA",
              errores: ["Dato fiscal inválido"],
            },
          },
        },
      });

    try {
      const wrapper = await mountView();
      const vm = await completarFormulario(wrapper);
      await vm.confirmarEmision();
      await vm.verificarEstado();
      await flushPromises();

      expect(vm.operacionIncierta).toBeNull();
      expect(vm.idempotencyKeyEmision).toBeNull();
      expect(
        wrapper.get('[data-testid="formulario-emision"]').attributes(),
      ).not.toHaveProperty("inert");
    } finally {
      consoleError.mockRestore();
    }
  });

  it("no presenta un error genérico pre-ARCA como reconciliación", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    mockedComprobantesService.proximoNumero.mockResolvedValue({
      proximo_numero: 100,
    });
    mockedComprobantesService.emitir.mockRejectedValue({
      response: {
        data: {
          detail: {
            mensaje: "No se pudo iniciar la solicitud fiscal",
          },
        },
      },
    });

    try {
      const wrapper = await mountView();
      const vm = await completarFormulario(wrapper);
      await vm.confirmarEmision();
      await flushPromises();

      expect(vm.operacionIncierta).toBeNull();
      expect(wrapper.find('[data-testid="operacion-incierta"]').exists()).toBe(
        false,
      );
      expect(
        wrapper.get('[data-testid="formulario-emision"]').attributes(),
      ).not.toHaveProperty("inert");
    } finally {
      consoleError.mockRestore();
    }
  });
});
