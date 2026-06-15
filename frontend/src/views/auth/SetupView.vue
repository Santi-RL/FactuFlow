<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useEmpresaStore } from "@/stores/empresa";
import { useNotification } from "@/composables/useNotification";
import { authService } from "@/services/auth.service";
import { provinciasOptions } from "@/constants/provincias";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseSelect from "@/components/ui/BaseSelect.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";
import wordmarkUrl from "@/assets/brand/factuflow-wordmark.svg";

const router = useRouter();
const authStore = useAuthStore();
const empresaStore = useEmpresaStore();
const { showSuccess, showError } = useNotification();

const loading = ref(false);
const checkingSetup = ref(true);
const error = ref("");
const step = ref(1);

// Usuario admin
const usuario = ref({
  nombre: "",
  email: "",
  password: "",
  passwordConfirm: "",
});

// Datos de empresa
const empresa = ref({
  razon_social: "",
  cuit: "",
  condicion_iva: "RI" as "RI" | "Monotributo" | "Exento",
  ingresos_brutos: "",
  domicilio: "",
  localidad: "",
  provincia: "",
  codigo_postal: "",
  email: "",
  telefono: "",
  inicio_actividades: "",
});

const condicionIvaOptions = [
  { value: "RI", label: "Responsable Inscripto" },
  { value: "Monotributo", label: "Monotributo" },
  { value: "Exento", label: "Exento" },
];

const nextStep = () => {
  error.value = "";

  if (step.value === 1) {
    if (
      !usuario.value.nombre ||
      !usuario.value.email ||
      !usuario.value.password
    ) {
      error.value = "Por favor complete todos los campos";
      return;
    }

    if (usuario.value.password !== usuario.value.passwordConfirm) {
      error.value = "Las contraseñas no coinciden";
      return;
    }

    if (usuario.value.password.length < 6) {
      error.value = "La contraseña debe tener al menos 6 caracteres";
      return;
    }
  }

  step.value++;
};

const previousStep = () => {
  step.value--;
};

const handleSubmit = async () => {
  error.value = "";
  loading.value = true;

  try {
    // Crear empresa primero
    const nuevaEmpresa = await empresaStore.createEmpresa(empresa.value);

    // Crear usuario admin
    await authStore.setup({
      nombre: usuario.value.nombre,
      email: usuario.value.email,
      password: usuario.value.password,
      empresa_id: nuevaEmpresa.id,
    });

    showSuccess("Sistema configurado", "Ya puede iniciar sesión");
    router.push("/login");
  } catch (err: any) {
    error.value =
      err.response?.data?.detail || "Error al configurar el sistema";
    showError("Error", error.value);
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  try {
    const setupRequired = await authService.checkSetupRequired();
    if (!setupRequired) {
      showError(
        "Configuración inicial ya realizada",
        "Iniciá sesión con un usuario existente.",
      );
      router.replace("/login");
      return;
    }
  } catch (err: any) {
    error.value =
      err.response?.data?.detail ||
      "No se pudo verificar el estado de instalación";
  } finally {
    checkingSetup.value = false;
  }
});
</script>

<template>
  <div class="min-h-screen bg-surface-page px-4 py-12">
    <div class="mx-auto max-w-2xl">
      <div class="mb-8 text-center">
        <img
          :src="wordmarkUrl"
          alt="FactuFlow"
          class="mx-auto h-12 w-auto"
        >
        <h1 class="sr-only">
          Configuración Inicial del Sistema
        </h1>
        <p class="mt-3 text-brand-slate">
          Configuración Inicial del Sistema
        </p>
      </div>

      <BaseCard>
        <div
          v-if="checkingSetup"
          class="py-12 text-center text-sm text-brand-slate"
        >
          Verificando estado de instalación...
        </div>

        <!-- Progress indicator -->
        <div
          v-if="!checkingSetup"
          class="mb-8"
        >
          <div class="flex items-center justify-between mb-2">
            <span
              :class="[
                'text-sm font-medium',
                step >= 1 ? 'text-brand-teal' : 'text-brand-slate',
              ]"
            >
              1. Usuario Admin
            </span>
            <span
              :class="[
                'text-sm font-medium',
                step >= 2 ? 'text-brand-teal' : 'text-brand-slate',
              ]"
            >
              2. Datos de Empresa
            </span>
          </div>
          <div class="flex gap-2">
            <div
              :class="[
                'flex-1 h-2 rounded',
                step >= 1 ? 'bg-brand-flow' : 'bg-border-subtle',
              ]"
            />
            <div
              :class="[
                'flex-1 h-2 rounded',
                step >= 2 ? 'bg-brand-flow' : 'bg-border-subtle',
              ]"
            />
          </div>
        </div>

        <BaseAlert
          v-if="error"
          type="error"
          title="Error"
          :message="error"
          class="mb-6"
          @dismiss="error = ''"
        />

        <!-- Step 1: Usuario -->
        <div
          v-if="!checkingSetup && step === 1"
          class="space-y-4"
        >
          <h2 class="mb-4 text-xl font-bold text-brand-ink">
            Crear Usuario Administrador
          </h2>

          <BaseInput
            v-model="usuario.nombre"
            label="Nombre completo"
            placeholder="Juan Pérez"
            required
          />

          <BaseInput
            v-model="usuario.email"
            type="email"
            label="Correo electrónico"
            placeholder="admin@empresa.com"
            required
          />

          <BaseInput
            v-model="usuario.password"
            type="password"
            label="Contraseña"
            placeholder="••••••••"
            hint="Mínimo 6 caracteres"
            required
          />

          <BaseInput
            v-model="usuario.passwordConfirm"
            type="password"
            label="Confirmar contraseña"
            placeholder="••••••••"
            required
          />

          <div class="flex justify-end">
            <BaseButton
              class="w-full sm:w-auto"
              @click="nextStep"
            >
              Continuar
            </BaseButton>
          </div>
        </div>

        <!-- Step 2: Empresa -->
        <div
          v-if="!checkingSetup && step === 2"
          class="space-y-4"
        >
          <h2 class="mb-4 text-xl font-bold text-brand-ink">
            Datos de la Empresa
          </h2>

          <BaseInput
            v-model="empresa.razon_social"
            label="Razón Social"
            placeholder="Mi Empresa S.A."
            required
          />

          <BaseInput
            v-model="empresa.cuit"
            label="CUIT"
            placeholder="20123456789"
            hint="11 dígitos sin guiones"
            maxlength="11"
            required
          />

          <BaseSelect
            v-model="empresa.condicion_iva"
            label="Condición IVA"
            :options="condicionIvaOptions"
            required
          />

          <BaseInput
            v-model="empresa.ingresos_brutos"
            label="Ingresos Brutos"
            placeholder="Ej.: CM 12345678 o Exento"
          />

          <BaseInput
            v-model="empresa.domicilio"
            label="Domicilio"
            placeholder="Av. Siempre Viva 123"
            required
          />

          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <BaseInput
              v-model="empresa.localidad"
              label="Localidad"
              placeholder="Buenos Aires"
              required
            />

            <BaseSelect
              v-model="empresa.provincia"
              label="Provincia"
              :options="provinciasOptions"
              required
            />
          </div>

          <BaseInput
            v-model="empresa.codigo_postal"
            label="Código Postal"
            placeholder="1234"
            required
          />

          <BaseInput
            v-model="empresa.email"
            type="email"
            label="Email"
            placeholder="contacto@empresa.com"
          />

          <BaseInput
            v-model="empresa.telefono"
            type="tel"
            label="Teléfono"
            placeholder="011-1234-5678"
          />

          <BaseInput
            v-model="empresa.inicio_actividades"
            type="date"
            label="Inicio de Actividades"
            required
          />

          <div class="flex flex-col-reverse gap-3 pt-4 sm:flex-row sm:justify-between">
            <BaseButton
              class="w-full sm:w-auto"
              variant="secondary"
              @click="previousStep"
            >
              Volver
            </BaseButton>
            <BaseButton
              class="w-full sm:w-auto"
              :loading="loading"
              @click="handleSubmit"
            >
              Finalizar Configuración
            </BaseButton>
          </div>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
