import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import almacenamientoService from "@/services/almacenamiento.service";
import { arcaService } from "@/services/arca.service";
import sistemaService, {
  type LoteWorkerHealthResponse,
} from "@/services/sistema.service";
import type {
  AlmacenamientoResumen,
  ExportacionAlmacenamiento,
  LoteCompactable,
} from "@/types/almacenamiento";
import SistemaView from "./SistemaView.vue";

vi.mock("@/services/almacenamiento.service", () => ({
  default: {
    resumen: vi.fn(),
    lotesCompactables: vi.fn(),
    logs: vi.fn(),
    temporales: vi.fn(),
    certificadosHuerfanos: vi.fn(),
    crearExportacion: vi.fn(),
    descargarExportacion: vi.fn(),
    confirmarDescarga: vi.fn(),
    confirmarLiberacion: vi.fn(),
    limpiarCertificadosHuerfanos: vi.fn(),
  },
}));

vi.mock("@/services/arca.service", () => ({
  arcaService: {
    getStatus: vi.fn(),
    testConnection: vi.fn(),
  },
}));

vi.mock("@/services/sistema.service", () => ({
  default: {
    health: vi.fn(),
    databaseHealth: vi.fn(),
    workerHealth: vi.fn(),
  },
}));

vi.mock("@/composables/useNotification", () => ({
  useNotification: () => ({
    showSuccess: vi.fn(),
    showError: vi.fn(),
  }),
}));

const resumenMock: AlmacenamientoResumen = {
  generated_at: "2026-06-03T10:00:00",
  estado: "necesita_atencion",
  total_bytes_usados: 10_240,
  total_bytes_recuperables: 2_048,
  storage_limit_bytes: 20_480,
  disk_total_bytes: 100_000,
  disk_used_bytes: 70_000,
  disk_free_bytes: 30_000,
  categorias: [
    {
      clave: "lotes",
      nombre: "Lotes",
      bytes_usados: 4_096,
      bytes_recuperables: 2_048,
      items: 1,
      estado: "necesita_atencion",
      descripcion: "Detalle original de lotes masivos.",
    },
  ],
  emisores: [
    {
      empresa_id: 1,
      etiqueta: "Emisor demo · CUIT terminado en 0001",
      lotes: 1,
      filas_persistidas: 10,
      filas_compactables: 10,
      comprobantes: 1,
      bytes_estimados: 4_096,
      bytes_recuperables: 2_048,
    },
  ],
};

const loteMock: LoteCompactable = {
  id: 7,
  empresa_id: 1,
  etiqueta_emisor: "Emisor demo · CUIT terminado en 0001",
  estado: "completado",
  total_filas: 10,
  total_grupos: 1,
  filas_persistidas: 10,
  bytes_recuperables: 2_048,
  created_at: "2026-06-02T10:00:00",
  finished_at: "2026-06-02T11:00:00",
};

const exportacionMock: ExportacionAlmacenamiento = {
  token: "token-seguro",
  estado: "preparada",
  archivo_nombre: "factuflow-almacenamiento.zip",
  checksum_sha256: "abc123",
  size_bytes: 1_024,
  created_at: "2026-06-03T10:05:00",
  downloaded_at: null,
  released_at: null,
  manifest: {},
};

const mockedService = almacenamientoService as unknown as {
  resumen: Mock;
  lotesCompactables: Mock;
  logs: Mock;
  temporales: Mock;
  certificadosHuerfanos: Mock;
  crearExportacion: Mock;
  descargarExportacion: Mock;
  confirmarDescarga: Mock;
  confirmarLiberacion: Mock;
};

const mockedArcaService = arcaService as unknown as {
  getStatus: Mock;
  testConnection: Mock;
};

const mockedSistemaService = sistemaService as unknown as {
  health: Mock;
  databaseHealth: Mock;
  workerHealth: Mock;
};

const apiPoolHealthMock = {
  pool_size: 4,
  max_overflow: 0,
  capacity: 4,
  checked_out: 1,
  checked_in: 3,
  overflow: 0,
  high_water_mark: 2,
  acquisition_count: 10,
  timeout_count: 0,
  last_wait_ms: 0,
  max_wait_ms: 2,
};

const workerPoolHealthMock = {
  ...apiPoolHealthMock,
  pool_size: 1,
  capacity: 1,
  checked_in: 0,
  high_water_mark: 1,
};

const workerHealthMock: LoteWorkerHealthResponse = {
  status: "healthy",
  worker: {
    estado: "esperando",
    habilitado: true,
    ejecutando: true,
    ocupado: false,
    ciclo_iniciado_at: null,
    ciclo_finalizado_at: "2026-07-10T12:00:00Z",
    ultima_duracion_ms: 125,
    ultimo_resultado: "exitoso",
    ultimo_exito_at: "2026-07-10T12:00:00Z",
    ultimo_error_at: null,
    stale_detectados_ultimo_ciclo: 0,
    lotes_en_cola_ultimo_ciclo: 0,
    lotes_procesados_ultimo_ciclo: 1,
  },
  pools: {
    separation_required: true,
    separated: true,
    api: apiPoolHealthMock,
    worker: workerPoolHealthMock,
  },
};

const mountView = () => {
  const pinia = createPinia();
  setActivePinia(pinia);

  return mount(SistemaView, {
    global: {
      plugins: [pinia],
      stubs: {
        ConfirmDialog: {
          props: [
            "show",
            "title",
            "message",
            "confirmText",
            "cancelText",
            "variant",
          ],
          emits: ["confirm", "cancel"],
          template: `
            <div v-if="show" data-testid="confirm-dialog">
              <p>{{ message }}</p>
              <button data-testid="confirm-action" @click="$emit('confirm')">
                {{ confirmText }}
              </button>
              <button data-testid="cancel-action" @click="$emit('cancel')">
                {{ cancelText }}
              </button>
            </div>
          `,
        },
      },
    },
  });
};

const buttonByText = (wrapper: ReturnType<typeof mount>, text: string) => {
  const button = wrapper.findAll("button").find((item) => item.text().includes(text));
  if (!button) {
    throw new Error(`No se encontró el botón ${text}`);
  }
  return button;
};

describe("SistemaView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedService.resumen.mockResolvedValue(resumenMock);
    mockedService.lotesCompactables.mockResolvedValue([loteMock]);
    mockedService.logs.mockResolvedValue([]);
    mockedService.temporales.mockResolvedValue([]);
    mockedService.certificadosHuerfanos.mockResolvedValue([]);
    mockedService.crearExportacion.mockResolvedValue(exportacionMock);
    mockedService.descargarExportacion.mockResolvedValue({
      blob: new Blob(["zip"]),
      downloadToken: "download-token",
    });
    mockedService.confirmarDescarga.mockResolvedValue({
      ...exportacionMock,
      estado: "descargada",
      downloaded_at: "2026-06-03T10:06:00",
    });
    mockedService.confirmarLiberacion.mockResolvedValue({
      mensaje: "Espacio liberado",
      bytes_afectados: 2_048,
      items_afectados: 1,
    });
    mockedSistemaService.health.mockResolvedValue({
      status: "healthy",
      message: "FactuFlow API funcionando correctamente",
    });
    mockedSistemaService.databaseHealth.mockResolvedValue({
      status: "healthy",
      message: "Conexión a la base de datos OK",
    });
    mockedSistemaService.workerHealth.mockResolvedValue(workerHealthMock);
    mockedArcaService.getStatus.mockResolvedValue({
      ambiente: "produccion",
      certificado_activo: true,
      certificado_disponible: true,
      certificado_id: 3,
      certificado_nombre: "Certificado productivo",
      certificado_vencimiento: "2028-05-04T00:00:00",
    });
    mockedArcaService.testConnection.mockResolvedValue({
      status: "ok",
      message: "Conexión exitosa con ARCA",
    });
    Object.defineProperty(window.URL, "createObjectURL", {
      value: vi.fn(() => "blob:factuflow"),
      configurable: true,
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
      value: vi.fn(),
      configurable: true,
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  it("muestra estado operativo sin probar ARCA automáticamente", async () => {
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("Estado operativo");
    expect(wrapper.text()).toContain("API de FactuFlow");
    expect(wrapper.text()).toContain("Conexión ARCA");
    expect(wrapper.text()).toContain("Worker de lotes");
    expect(wrapper.text()).toContain("Guía rápida de soporte");
    expect(wrapper.text()).toContain("Ficha para soporte");
    expect(wrapper.text()).toContain("Emisor activo");
    expect(wrapper.text()).toContain(
      "No copiar CUIT completo en documentación pública.",
    );
    expect(wrapper.text()).toContain("Lote detenido, parcial o incierto");
    expect(wrapper.text()).toContain(
      "No reintentar automáticamente si pudo existir una respuesta de ARCA.",
    );
    expect(mockedSistemaService.health).toHaveBeenCalled();
    expect(mockedSistemaService.databaseHealth).toHaveBeenCalled();
    expect(mockedSistemaService.workerHealth).toHaveBeenCalled();
    expect(mockedArcaService.getStatus).toHaveBeenCalled();
    expect(mockedService.resumen).toHaveBeenCalledTimes(1);
    expect(mockedService.lotesCompactables).not.toHaveBeenCalled();
    expect(mockedService.logs).not.toHaveBeenCalled();
    expect(mockedService.temporales).not.toHaveBeenCalled();
    expect(mockedService.certificadosHuerfanos).not.toHaveBeenCalled();
    expect(mockedArcaService.testConnection).not.toHaveBeenCalled();

    const worker = wrapper.get('[data-testid="estado-sistema-worker-lotes"]');
    expect(worker.text()).toContain("Correcto");
    expect(worker.text()).toContain("El worker está disponible.");
    expect(worker.text()).toContain(
      "Los pools de API y worker están separados.",
    );
  });

  it("muestra el worker como no disponible si falla el healthcheck", async () => {
    mockedSistemaService.workerHealth.mockRejectedValueOnce({});
    const wrapper = mountView();
    await flushPromises();

    const worker = wrapper.get('[data-testid="estado-sistema-worker-lotes"]');
    expect(worker.text()).toContain("No disponible");
    expect(worker.text()).toContain(
      "No se pudo consultar el worker de lotes.",
    );
  });

  it("marca el certificado como no disponible si faltan sus archivos locales", async () => {
    mockedArcaService.getStatus.mockResolvedValueOnce({
      ambiente: "produccion",
      certificado_activo: true,
      certificado_disponible: false,
      certificado_id: 3,
      certificado_nombre: "Certificado productivo",
      certificado_vencimiento: "2028-05-04T00:00:00",
    });

    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain(
      "El certificado activo no tiene disponibles sus archivos locales.",
    );
  });

  it("prepara, descarga y libera un resguardo seleccionado", async () => {
    const wrapper = mountView();
    await flushPromises();

    await buttonByText(wrapper, "Almacenamiento").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Lotes");
    expect(wrapper.text()).toContain("Emisor demo");

    await wrapper.find('input[type="checkbox"]').setValue(true);
    await buttonByText(wrapper, "Preparar ZIP").trigger("click");
    await flushPromises();

    expect(mockedService.crearExportacion).toHaveBeenCalledWith({
      lote_ids: [7],
      log_ids: [],
      temporal_ids: [],
    });
    expect(wrapper.text()).toContain("factuflow-almacenamiento.zip");

    await buttonByText(wrapper, "Descargar resguardo").trigger("click");
    await flushPromises();

    expect(mockedService.descargarExportacion).toHaveBeenCalledWith("token-seguro");
    expect(mockedService.confirmarDescarga).toHaveBeenCalledWith(
      "token-seguro",
      "abc123",
      "download-token",
    );

    await buttonByText(wrapper, "Liberar espacio").trigger("click");
    await wrapper.find('[data-testid="confirm-action"]').trigger("click");
    await flushPromises();

    expect(mockedService.confirmarLiberacion).toHaveBeenCalledWith("token-seguro");
  });
});
