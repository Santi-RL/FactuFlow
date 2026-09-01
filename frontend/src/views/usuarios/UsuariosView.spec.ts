import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { empresaService } from "@/services/empresa.service";
import { usuariosService } from "@/services/usuarios.service";
import { useAuthStore } from "@/stores/auth";
import type { Usuario } from "@/types/auth";
import type { Empresa } from "@/types/empresa";
import UsuariosView from "@/views/usuarios/UsuariosView.vue";

vi.mock("@/services/usuarios.service", () => ({
  usuariosService: {
    getAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    desactivar: vi.fn(),
    reactivar: vi.fn(),
    resetPassword: vi.fn(),
  },
}));

vi.mock("@/services/empresa.service", () => ({
  empresaService: {
    getAll: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

const empresa = (id: number, nombre: string): Empresa => ({
  id,
  razon_social: nombre,
  cuit: `30${String(id).padStart(9, "0")}`,
  condicion_iva: "RI",
  ingresos_brutos: null,
  domicilio: "Domicilio sintético",
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

const administrador: Usuario = {
  id: 2,
  email: "administrador@example.test",
  nombre: "Administradora sintética",
  empresa_id: null,
  empresa_ids: [1, 2],
  puede_crear_editar_emisores: true,
  activo: true,
  es_admin: true,
  created_at: "2024-01-01T00:00:00",
  ultimo_login: null,
};

describe("UsuariosView multiemisor", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    (usuariosService.getAll as Mock).mockResolvedValue([administrador]);
    (empresaService.getAll as Mock).mockResolvedValue([
      empresa(1, "Emisor Uno"),
      empresa(2, "Emisor Dos"),
    ]);
    const authStore = useAuthStore();
    authStore.user = { ...administrador, id: 1 };
  });

  it("confirma el alcance y envía asignaciones explícitas al degradar", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const authStore = useAuthStore();
    authStore.user = { ...administrador, id: 1 };
    (usuariosService.update as Mock).mockImplementation(
      async (_id: number, payload: Partial<Usuario>) => ({
        ...administrador,
        ...payload,
      }),
    );

    const wrapper = mount(UsuariosView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    const vm = wrapper.vm as unknown as {
      abrirEditar: (usuario: Usuario) => void;
      solicitarGuardar: () => void;
      guardarUsuario: () => Promise<void>;
      form: {
        es_admin: boolean;
        empresa_ids: number[];
        puede_crear_editar_emisores: boolean;
      };
      confirmacionGuardado: string | null;
    };

    vm.abrirEditar(administrador);
    vm.form.es_admin = false;
    vm.form.empresa_ids = [1];
    vm.form.puede_crear_editar_emisores = false;
    vm.solicitarGuardar();

    expect(vm.confirmacionGuardado).toContain("pasará a ser operador");
    expect(vm.confirmacionGuardado).toContain("Emisor Uno");

    await vm.guardarUsuario();

    expect(usuariosService.update).toHaveBeenCalledWith(
      administrador.id,
      expect.objectContaining({
        es_admin: false,
        empresa_ids: [1],
        puede_crear_editar_emisores: false,
      }),
    );
  });
});
