<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  CheckCircleIcon,
  KeyIcon,
  NoSymbolIcon,
  PencilSquareIcon,
  PlusIcon,
} from "@heroicons/vue/24/outline";

import ConfirmDialog from "@/components/common/ConfirmDialog.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import BaseBadge from "@/components/ui/BaseBadge.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseModal from "@/components/ui/BaseModal.vue";
import BaseTable from "@/components/ui/BaseTable.vue";
import { useNotification } from "@/composables/useNotification";
import { usuariosService } from "@/services/usuarios.service";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import type { Usuario } from "@/types/auth";

const authStore = useAuthStore();
const empresaStore = useEmpresaStore();
const { showSuccess, showError } = useNotification();

const usuarios = ref<Usuario[]>([]);
const loading = ref(false);
const saving = ref(false);
const resetting = ref(false);
const error = ref("");
const formError = ref("");
const resetError = ref("");

const usuarioEditando = ref<Usuario | null>(null);
const showFormModal = ref(false);
const usuarioReset = ref<Usuario | null>(null);
const accionPendiente = ref<{
  usuario: Usuario;
  tipo: "desactivar" | "reactivar";
} | null>(null);
const confirmacionGuardado = ref<string | null>(null);

const form = ref({
  nombre: "",
  email: "",
  password: "",
  es_admin: false,
  activo: true,
  empresa_ids: [] as number[],
  puede_crear_editar_emisores: false,
});

const resetForm = ref({
  password: "",
  passwordConfirm: "",
});

const columns = [
  { key: "nombre", label: "Usuario" },
  { key: "rol", label: "Rol" },
  { key: "estado", label: "Estado" },
  { key: "empresa", label: "Emisores habilitados" },
  { key: "capacidad_emisores", label: "Gestión de emisores" },
  { key: "ultimo_login", label: "Último ingreso" },
];

const usuariosOrdenados = computed(() =>
  [...usuarios.value].sort((a, b) => {
    if (a.activo !== b.activo) {
      return a.activo ? -1 : 1;
    }
    return a.nombre.localeCompare(b.nombre);
  }),
);

const formTitle = computed(() =>
  usuarioEditando.value ? "Editar usuario" : "Crear usuario",
);

const accionTitle = computed(() => {
  if (!accionPendiente.value) return "";
  return accionPendiente.value.tipo === "desactivar"
    ? "Desactivar usuario"
    : "Reactivar usuario";
});

const accionMessage = computed(() => {
  if (!accionPendiente.value) return "";
  const nombre = accionPendiente.value.usuario.nombre;
  return accionPendiente.value.tipo === "desactivar"
    ? `${nombre} no podrá iniciar sesión hasta que lo reactives.`
    : `${nombre} volverá a poder iniciar sesión.`;
});

const accionConfirmText = computed(() =>
  accionPendiente.value?.tipo === "desactivar" ? "Desactivar" : "Reactivar",
);

const accionVariant = computed(() =>
  accionPendiente.value?.tipo === "desactivar" ? "danger" : "primary",
);

const nombreEmpresa = (empresaId: number) => {
  const empresa = empresaStore.empresas.find((item) => item.id === empresaId);
  return empresa ? empresa.razon_social : `Emisor #${empresaId}`;
};

const nombresEmisores = (empresaIds: number[]) => {
  if (empresaIds.length === 0) return "Sin emisores habilitados";
  return empresaIds.map(nombreEmpresa).join(", ");
};

const seleccionarTodosLosEmisoresActuales = () => {
  form.value.empresa_ids = empresaStore.empresas.map((empresa) => empresa.id);
};

const alternarEmisor = (empresaId: number) => {
  form.value.empresa_ids = form.value.empresa_ids.includes(empresaId)
    ? form.value.empresa_ids.filter((id) => id !== empresaId)
    : [...form.value.empresa_ids, empresaId];
};

const formatDateTime = (value: string | null) => {
  if (!value) return "Sin ingresos";
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
};

const actualizarUsuarioLocal = (usuario: Usuario) => {
  usuarios.value = usuarios.value.map((item) =>
    item.id === usuario.id ? usuario : item,
  );

  if (authStore.user?.id === usuario.id) {
    authStore.user = usuario;
    localStorage.setItem("user", JSON.stringify(usuario));
  }
};

const cargarDatos = async () => {
  loading.value = true;
  error.value = "";
  try {
    const [usuariosResponse] = await Promise.all([
      usuariosService.getAll(),
      empresaStore.fetchEmpresas(),
    ]);
    usuarios.value = usuariosResponse;
  } catch (err: any) {
    error.value =
      err.response?.data?.detail || "No se pudieron cargar usuarios";
  } finally {
    loading.value = false;
  }
};

const abrirCrear = () => {
  usuarioEditando.value = null;
  formError.value = "";
  form.value = {
    nombre: "",
    email: "",
    password: "",
    es_admin: false,
    activo: true,
    empresa_ids: [],
    puede_crear_editar_emisores: false,
  };
  showFormModal.value = true;
};

const abrirEditar = (usuario: Usuario) => {
  usuarioEditando.value = usuario;
  formError.value = "";
  form.value = {
    nombre: usuario.nombre,
    email: usuario.email,
    password: "",
    es_admin: usuario.es_admin,
    activo: usuario.activo,
    empresa_ids: [...usuario.empresa_ids],
    puede_crear_editar_emisores: usuario.puede_crear_editar_emisores,
  };
  showFormModal.value = true;
};

const cerrarForm = () => {
  showFormModal.value = false;
  usuarioEditando.value = null;
  formError.value = "";
};

const validarFormulario = () => {
  formError.value = "";

  if (!form.value.nombre.trim() || !form.value.email.trim()) {
    formError.value = "Completá nombre y correo electrónico.";
    return false;
  }
  if (!usuarioEditando.value && form.value.password.length < 6) {
    formError.value = "La contraseña debe tener al menos 6 caracteres.";
    return false;
  }
  return true;
};

const solicitarGuardar = () => {
  if (!validarFormulario()) return;

  if (usuarioEditando.value) {
    const emisoresRevocados = usuarioEditando.value.empresa_ids.filter(
      (id) => !form.value.empresa_ids.includes(id),
    );
    if (usuarioEditando.value.es_admin && !form.value.es_admin) {
      confirmacionGuardado.value = `${usuarioEditando.value.nombre} pasará a ser operador con acceso a: ${nombresEmisores(form.value.empresa_ids)}. Los lotes ya confirmados o encolados podrán terminar, pero las acciones nuevas requerirán una asignación vigente.`;
      return;
    }
    if (emisoresRevocados.length > 0) {
      confirmacionGuardado.value = `Se revocará el acceso de ${usuarioEditando.value.nombre} a: ${nombresEmisores(emisoresRevocados)}. Los lotes ya confirmados o encolados podrán terminar; las acciones nuevas quedarán bloqueadas.`;
      return;
    }
  }

  void guardarUsuario();
};

const guardarUsuario = async () => {
  if (!validarFormulario()) return;
  confirmacionGuardado.value = null;

  saving.value = true;
  try {
    if (usuarioEditando.value) {
      const usuarioActualizado = await usuariosService.update(
        usuarioEditando.value.id,
        {
          nombre: form.value.nombre,
          email: form.value.email,
          es_admin: form.value.es_admin,
          activo: form.value.activo,
          empresa_ids: [...form.value.empresa_ids],
          puede_crear_editar_emisores: form.value.puede_crear_editar_emisores,
        },
      );
      actualizarUsuarioLocal(usuarioActualizado);
      showSuccess("Usuario actualizado");
    } else {
      const usuarioCreado = await usuariosService.create({
        nombre: form.value.nombre,
        email: form.value.email,
        password: form.value.password,
        es_admin: form.value.es_admin,
        activo: form.value.activo,
        empresa_ids: [...form.value.empresa_ids],
        puede_crear_editar_emisores: form.value.puede_crear_editar_emisores,
      });
      usuarios.value = [usuarioCreado, ...usuarios.value];
      showSuccess("Usuario creado");
    }
    cerrarForm();
  } catch (err: any) {
    formError.value =
      err.response?.data?.detail || "No se pudo guardar el usuario";
    showError("Error", formError.value);
  } finally {
    saving.value = false;
  }
};

const abrirReset = (usuario: Usuario) => {
  usuarioReset.value = usuario;
  resetError.value = "";
  resetForm.value = {
    password: "",
    passwordConfirm: "",
  };
};

const cerrarReset = () => {
  usuarioReset.value = null;
  resetError.value = "";
};

const resetPassword = async () => {
  if (!usuarioReset.value) return;
  resetError.value = "";

  if (resetForm.value.password.length < 6) {
    resetError.value = "La contraseña debe tener al menos 6 caracteres.";
    return;
  }
  if (resetForm.value.password !== resetForm.value.passwordConfirm) {
    resetError.value = "Las contraseñas no coinciden.";
    return;
  }

  resetting.value = true;
  try {
    await usuariosService.resetPassword(usuarioReset.value.id, {
      password: resetForm.value.password,
    });
    showSuccess("Contraseña actualizada");
    cerrarReset();
  } catch (err: any) {
    resetError.value =
      err.response?.data?.detail || "No se pudo restablecer la contraseña";
    showError("Error", resetError.value);
  } finally {
    resetting.value = false;
  }
};

const confirmarAccion = (
  usuario: Usuario,
  tipo: "desactivar" | "reactivar",
) => {
  accionPendiente.value = { usuario, tipo };
};

const ejecutarAccion = async () => {
  if (!accionPendiente.value) return;
  const { usuario, tipo } = accionPendiente.value;
  try {
    const usuarioActualizado =
      tipo === "desactivar"
        ? await usuariosService.desactivar(usuario.id)
        : await usuariosService.reactivar(usuario.id);
    actualizarUsuarioLocal(usuarioActualizado);
    showSuccess(
      tipo === "desactivar" ? "Usuario desactivado" : "Usuario reactivado",
    );
  } catch (err: any) {
    const mensaje =
      err.response?.data?.detail || "No se pudo actualizar el usuario";
    showError("Error", mensaje);
  } finally {
    accionPendiente.value = null;
  }
};

onMounted(() => {
  cargarDatos();
});
</script>

<template>
  <div>
    <div
      class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <h1 class="text-3xl font-bold text-brand-ink">Usuarios</h1>
        <p class="mt-2 text-brand-slate">
          Administrá altas, accesos y estado de inicio de sesión.
        </p>
      </div>
      <BaseButton @click="abrirCrear">
        <PlusIcon class="mr-2 h-5 w-5" />
        Crear usuario
      </BaseButton>
    </div>

    <BaseAlert
      v-if="error"
      type="error"
      title="Error"
      :message="error"
      class="mb-6"
      @dismiss="error = ''"
    />

    <BaseCard>
      <BaseTable
        :columns="columns"
        :data="usuariosOrdenados"
        :loading="loading"
        empty-text="No hay usuarios creados"
      >
        <template #cell-nombre="{ row }">
          <div>
            <p class="font-medium text-brand-ink">
              {{ row.nombre }}
            </p>
            <p class="text-sm text-brand-slate">
              {{ row.email }}
            </p>
          </div>
        </template>

        <template #cell-rol="{ row }">
          <BaseBadge :variant="row.es_admin ? 'primary' : 'default'">
            {{ row.es_admin ? "Administrador" : "Usuario operativo" }}
          </BaseBadge>
        </template>

        <template #cell-estado="{ row }">
          <BaseBadge :variant="row.activo ? 'success' : 'danger'">
            {{ row.activo ? "Activo" : "Inactivo" }}
          </BaseBadge>
        </template>

        <template #cell-empresa="{ row }">
          <span class="text-brand-slate">
            {{ nombresEmisores(row.empresa_ids) }}
          </span>
        </template>

        <template #cell-capacidad_emisores="{ row }">
          <BaseBadge
            :variant="row.puede_crear_editar_emisores ? 'success' : 'default'"
          >
            {{
              row.puede_crear_editar_emisores
                ? "Puede crear y editar"
                : "Solo operar"
            }}
          </BaseBadge>
        </template>

        <template #cell-ultimo_login="{ value }">
          <span class="text-brand-slate">
            {{ formatDateTime(value) }}
          </span>
        </template>

        <template #actions="{ row }">
          <div class="flex justify-end gap-2">
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-control text-brand-flow transition-colors hover:text-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
              @click="abrirEditar(row)"
            >
              <PencilSquareIcon class="h-4 w-4" />
              Editar
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-control text-brand-slate transition-colors hover:text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
              @click="abrirReset(row)"
            >
              <KeyIcon class="h-4 w-4" />
              Clave
            </button>
            <button
              v-if="row.activo"
              type="button"
              class="inline-flex items-center gap-1 rounded-control text-status-danger transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-status-danger focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="row.id === authStore.user?.id"
              @click="confirmarAccion(row, 'desactivar')"
            >
              <NoSymbolIcon class="h-4 w-4" />
              Desactivar
            </button>
            <button
              v-else
              type="button"
              class="inline-flex items-center gap-1 rounded-control text-status-success transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-status-success focus:ring-offset-2"
              @click="confirmarAccion(row, 'reactivar')"
            >
              <CheckCircleIcon class="h-4 w-4" />
              Reactivar
            </button>
          </div>
        </template>
      </BaseTable>
    </BaseCard>

    <BaseModal
      :show="showFormModal"
      :title="formTitle"
      size="lg"
      @close="cerrarForm"
    >
      <BaseAlert
        v-if="formError"
        type="error"
        title="Error"
        :message="formError"
        class="mb-4"
        @dismiss="formError = ''"
      />

      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <BaseInput v-model="form.nombre" label="Nombre completo" required />
        <BaseInput
          v-model="form.email"
          type="email"
          label="Correo electrónico"
          :disabled="usuarioEditando?.id === authStore.user?.id"
          required
        />
        <BaseInput
          v-if="!usuarioEditando"
          v-model="form.password"
          type="password"
          label="Contraseña inicial"
          hint="Mínimo 6 caracteres"
          required
        />
        <fieldset class="space-y-3 md:col-span-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <legend class="text-sm font-medium text-brand-ink">
              Emisores habilitados
            </legend>
            <button
              type="button"
              class="rounded-control text-sm font-medium text-brand-flow hover:text-brand-teal focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2"
              @click="seleccionarTodosLosEmisoresActuales"
            >
              Seleccionar todos los emisores actuales
            </button>
          </div>
          <p class="text-xs text-brand-slate">
            La selección total toma una copia de la lista actual. Los emisores
            que se creen después no se asignarán automáticamente.
          </p>
          <div
            v-if="empresaStore.empresas.length"
            class="grid max-h-48 gap-2 overflow-y-auto rounded-control border border-border-subtle p-3 sm:grid-cols-2"
          >
            <label
              v-for="empresa in empresaStore.empresas"
              :key="empresa.id"
              class="flex items-start gap-2 text-sm text-brand-slate"
            >
              <input
                type="checkbox"
                :checked="form.empresa_ids.includes(empresa.id)"
                class="mt-0.5 h-4 w-4 rounded border-border-subtle text-brand-flow accent-brand-flow focus:ring-brand-flow"
                @change="alternarEmisor(empresa.id)"
              />
              <span>
                <span class="block font-medium text-brand-ink">
                  {{ empresa.razon_social }}
                </span>
                <span class="text-xs">CUIT {{ empresa.cuit }}</span>
              </span>
            </label>
          </div>
          <BaseAlert
            v-if="form.empresa_ids.length === 0"
            type="warning"
            title="Operador sin emisores"
            message="Podrá iniciar sesión, pero no podrá operar hasta que le asignes al menos un emisor."
          />
          <p v-if="form.es_admin" class="text-xs text-brand-slate">
            Estas asignaciones se conservan mientras sea administrador y serán
            efectivas si vuelve a ser operador.
          </p>
        </fieldset>
        <label class="flex items-center gap-2 text-sm text-brand-slate">
          <input
            v-model="form.es_admin"
            type="checkbox"
            class="h-4 w-4 rounded border-border-subtle text-brand-flow accent-brand-flow focus:ring-brand-flow"
            :disabled="usuarioEditando?.id === authStore.user?.id"
          />
          Puede administrar usuarios
        </label>
        <label class="flex items-center gap-2 text-sm text-brand-slate">
          <input
            v-model="form.puede_crear_editar_emisores"
            type="checkbox"
            class="h-4 w-4 rounded border-border-subtle text-brand-flow accent-brand-flow focus:ring-brand-flow"
          />
          Puede crear y editar emisores
        </label>
        <label class="flex items-center gap-2 text-sm text-brand-slate">
          <input
            v-model="form.activo"
            type="checkbox"
            class="h-4 w-4 rounded border-border-subtle text-brand-flow accent-brand-flow focus:ring-brand-flow"
            :disabled="usuarioEditando?.id === authStore.user?.id"
          />
          Usuario activo
        </label>
      </div>

      <template #footer>
        <BaseButton variant="secondary" @click="cerrarForm">
          Cancelar
        </BaseButton>
        <BaseButton :loading="saving" @click="solicitarGuardar">
          Guardar
        </BaseButton>
      </template>
    </BaseModal>

    <BaseModal
      :show="!!usuarioReset"
      title="Restablecer contraseña"
      size="sm"
      @close="cerrarReset"
    >
      <BaseAlert
        v-if="resetError"
        type="error"
        title="Error"
        :message="resetError"
        class="mb-4"
        @dismiss="resetError = ''"
      />
      <div class="space-y-4">
        <p class="text-sm text-brand-slate">
          {{ usuarioReset?.nombre }}
        </p>
        <BaseInput
          v-model="resetForm.password"
          type="password"
          label="Nueva contraseña"
          hint="Mínimo 6 caracteres"
          required
        />
        <BaseInput
          v-model="resetForm.passwordConfirm"
          type="password"
          label="Confirmar contraseña"
          required
        />
      </div>

      <template #footer>
        <BaseButton variant="secondary" @click="cerrarReset">
          Cancelar
        </BaseButton>
        <BaseButton :loading="resetting" @click="resetPassword">
          Actualizar
        </BaseButton>
      </template>
    </BaseModal>

    <ConfirmDialog
      :show="!!confirmacionGuardado"
      title="Confirmar alcance del operador"
      :message="confirmacionGuardado || ''"
      confirm-text="Guardar cambios"
      variant="danger"
      @cancel="confirmacionGuardado = null"
      @confirm="guardarUsuario"
    />

    <ConfirmDialog
      :show="!!accionPendiente"
      :title="accionTitle"
      :message="accionMessage"
      :confirm-text="accionConfirmText"
      :variant="accionVariant"
      @cancel="accionPendiente = null"
      @confirm="ejecutarAccion"
    />
  </div>
</template>
