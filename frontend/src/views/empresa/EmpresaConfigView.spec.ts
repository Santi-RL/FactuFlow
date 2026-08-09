import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { useEmpresaStore } from "@/stores/empresa";
import type { Empresa } from "@/types/empresa";
import type { PerfilCargaMasiva } from "@/types/perfil-carga-masiva";
import formatosImportacionService from "@/services/formatos-importacion.service";
import perfilesCargaMasivaService from "@/services/perfiles-carga-masiva.service";
import { puntosVentaService } from "@/services/puntos_venta.service";
import EmpresaConfigView from "./EmpresaConfigView.vue";

vi.mock("@/services/formatos-importacion.service", () => ({
  default: {
    listar: vi.fn(),
    catalogoCampos: vi.fn(),
  },
}));

vi.mock("@/services/perfiles-carga-masiva.service", () => ({
  default: {
    listar: vi.fn(),
  },
}));

vi.mock("@/services/puntos_venta.service", () => ({
  puntosVentaService: {
    getAll: vi.fn(),
  },
}));

const notificationMock = vi.hoisted(() => ({
  showError: vi.fn(),
  showSuccess: vi.fn(),
}));

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => notificationMock,
}));

const mockedFormatos = formatosImportacionService as unknown as {
  listar: Mock;
  catalogoCampos: Mock;
};
const mockedPerfiles = perfilesCargaMasivaService as unknown as {
  listar: Mock;
};
const mockedPuntosVenta = puntosVentaService as unknown as { getAll: Mock };

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolver, rechazar) => {
    resolve = resolver;
    reject = rechazar;
  });
  return { promise, reject, resolve };
};

const empresaMock = (id: number): Empresa => ({
  id,
  razon_social: `Emisor ${id}`,
  cuit: ["30", "7000000", String(id).padStart(2, "0")].join(""),
  condicion_iva: "RI",
  ingresos_brutos: null,
  domicilio: `Av. Prueba ${id}`,
  localidad: "CABA",
  provincia: "CABA",
  codigo_postal: "1000",
  email: null,
  telefono: null,
  inicio_actividades: "2024-01-01",
  logo: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
});

const perfilMock = (empresaId: number): PerfilCargaMasiva => ({
  id: empresaId * 10,
  empresa_id: empresaId,
  nombre: `Perfil emisor ${empresaId}`,
  descripcion: null,
  configuracion_json: {
    version: 1,
    formato_importacion_version_id: null,
    punto_venta: { modo: "archivo", numero: null },
    concepto_modo: "archivo",
    descripcion_item_modo: "archivo",
    fecha_emision: { modo: "manual" },
    periodo_servicio: { modo: "manual" },
    fecha_vto_pago: { modo: "manual" },
  },
  es_predeterminado: false,
  activo: true,
  created_at: "2026-08-01T12:00:00Z",
  updated_at: "2026-08-01T12:00:00Z",
});

type ConfiguracionCargaInicial = {
  catalogo?: unknown[];
  formatos?: unknown[];
  puntos?: unknown[];
};

const mountView = async (
  perfilesIniciales: Promise<PerfilCargaMasiva[]>,
  configuracionInicial: ConfiguracionCargaInicial = {},
) => {
  const pinia = createPinia();
  setActivePinia(pinia);
  const empresaStore = useEmpresaStore();
  const empresaA = empresaMock(1);
  const empresaB = empresaMock(2);
  empresaStore.empresa = empresaA;
  empresaStore.empresas = [empresaA, empresaB];
  empresaStore.empresaActivaId = empresaA.id;

  mockedPerfiles.listar.mockReturnValue(perfilesIniciales);
  mockedFormatos.listar.mockResolvedValue(configuracionInicial.formatos ?? []);
  mockedFormatos.catalogoCampos.mockResolvedValue(
    configuracionInicial.catalogo ?? [],
  );
  mockedPuntosVenta.getAll.mockResolvedValue(configuracionInicial.puntos ?? []);

  const wrapper = mount(EmpresaConfigView, {
    global: { plugins: [pinia] },
  });
  await flushPromises();
  return { empresaStore, wrapper };
};

describe("EmpresaConfigView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("conserva la configuración de B si la respuesta de A llega tarde", async () => {
    const cargaA = deferred<PerfilCargaMasiva[]>();
    const cargaB = deferred<PerfilCargaMasiva[]>();
    const { empresaStore, wrapper } = await mountView(cargaA.promise);
    mockedPerfiles.listar.mockReturnValue(cargaB.promise);

    empresaStore.empresaActivaId = 2;
    await flushPromises();
    expect(mockedPerfiles.listar).toHaveBeenCalledTimes(2);

    cargaB.resolve([perfilMock(2)]);
    await flushPromises();

    const vm = wrapper.vm as unknown as {
      loadingPerfiles: boolean;
      perfilesCargaMasiva: PerfilCargaMasiva[];
    };
    expect(vm.loadingPerfiles).toBe(false);
    expect(vm.perfilesCargaMasiva.map((perfil) => perfil.empresa_id)).toEqual([
      2,
    ]);

    cargaA.resolve([perfilMock(1)]);
    await flushPromises();

    expect(vm.loadingPerfiles).toBe(false);
    expect(vm.perfilesCargaMasiva.map((perfil) => perfil.empresa_id)).toEqual([
      2,
    ]);
    wrapper.unmount();
  });

  it("ignora el error de A y mantiene el loading de la solicitud B", async () => {
    const cargaA = deferred<PerfilCargaMasiva[]>();
    const cargaB = deferred<PerfilCargaMasiva[]>();
    const { empresaStore, wrapper } = await mountView(cargaA.promise);
    mockedPerfiles.listar.mockReturnValue(cargaB.promise);

    empresaStore.empresaActivaId = 2;
    await flushPromises();
    notificationMock.showError.mockClear();

    cargaA.reject({ response: { data: { detail: "Error del emisor A" } } });
    await flushPromises();

    const vm = wrapper.vm as unknown as {
      loadingPerfiles: boolean;
      perfilesCargaMasiva: PerfilCargaMasiva[];
    };
    expect(notificationMock.showError).not.toHaveBeenCalledWith(
      "No se pudo cargar la configuración de carga masiva",
      expect.any(String),
    );
    expect(vm.loadingPerfiles).toBe(true);
    expect(vm.perfilesCargaMasiva).toEqual([]);

    cargaB.resolve([perfilMock(2)]);
    await flushPromises();

    expect(vm.loadingPerfiles).toBe(false);
    expect(vm.perfilesCargaMasiva.map((perfil) => perfil.empresa_id)).toEqual([
      2,
    ]);
    wrapper.unmount();
  });

  it("limpia toda la configuración visible de A mientras B carga y falla", async () => {
    const cargaB = deferred<PerfilCargaMasiva[]>();
    const { empresaStore, wrapper } = await mountView(
      Promise.resolve([perfilMock(1)]),
      {
        catalogo: [{ campo: "fecha_emision" }],
        formatos: [{ id: 101, nombre: "Formato A" }],
        puntos: [{ empresa_id: 1, id: 101, numero: 1 }],
      },
    );
    const vm = wrapper.vm as unknown as {
      catalogoCampos: unknown[];
      formatosImportacion: unknown[];
      loadingPerfiles: boolean;
      perfilesCargaMasiva: PerfilCargaMasiva[];
      puntosVenta: unknown[];
    };
    expect([
      vm.perfilesCargaMasiva.length,
      vm.formatosImportacion.length,
      vm.puntosVenta.length,
      vm.catalogoCampos.length,
    ]).toEqual([1, 1, 1, 1]);

    mockedPerfiles.listar.mockReturnValue(cargaB.promise);
    mockedFormatos.listar.mockResolvedValue([{ id: 202, nombre: "Formato B" }]);
    mockedFormatos.catalogoCampos.mockResolvedValue([
      { campo: "tipo_comprobante" },
    ]);
    mockedPuntosVenta.getAll.mockResolvedValue([
      { empresa_id: 2, id: 202, numero: 2 },
    ]);
    empresaStore.empresaActivaId = 2;
    await flushPromises();

    expect(vm.loadingPerfiles).toBe(true);
    expect([
      vm.perfilesCargaMasiva,
      vm.formatosImportacion,
      vm.puntosVenta,
      vm.catalogoCampos,
    ]).toEqual([[], [], [], []]);
    notificationMock.showError.mockClear();

    cargaB.reject({ response: { data: { detail: "Error del emisor B" } } });
    await flushPromises();

    expect(vm.loadingPerfiles).toBe(false);
    expect([
      vm.perfilesCargaMasiva,
      vm.formatosImportacion,
      vm.puntosVenta,
      vm.catalogoCampos,
    ]).toEqual([[], [], [], []]);
    expect(notificationMock.showError).toHaveBeenCalledWith(
      "No se pudo cargar la configuración de carga masiva",
      "Error del emisor B",
    );
    wrapper.unmount();
  });
});
