<script setup lang="ts">
import { ref } from "vue";
import { useAuth } from "@/composables/useAuth";
import { authService } from "@/services/auth.service";
import BaseInput from "@/components/ui/BaseInput.vue";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";
import BaseAlert from "@/components/ui/BaseAlert.vue";

const { login, loading } = useAuth();

const email = ref("");
const password = ref("");
const error = ref("");
const serverUnavailable = ref(false);
const checkingServer = ref(false);

const serverUnavailableMessage =
  'No se pudo conectar con el servidor local. Hacé click derecho en el ícono de FactuFlow junto al reloj de Windows y elegí "Reiniciar servicios". Cuando el ícono quede verde, presioná "Reintentar". Si no ves el ícono, abrí nuevamente FactuFlow Local.vbs.';

const checkServerAvailability = async (): Promise<boolean> => {
  checkingServer.value = true;
  try {
    const available = await authService.checkBackendAvailable();
    serverUnavailable.value = !available;
    return available;
  } finally {
    checkingServer.value = false;
  }
};

const retryServerConnection = async () => {
  error.value = "";
  await checkServerAvailability();
};

const handleSubmit = async () => {
  error.value = "";
  serverUnavailable.value = false;

  if (!email.value || !password.value) {
    error.value = "Por favor complete todos los campos";
    return;
  }

  const serverAvailable = await checkServerAvailability();
  if (!serverAvailable) {
    return;
  }

  try {
    await login(email.value, password.value);
  } catch (err: any) {
    if (err.message === serverUnavailableMessage) {
      serverUnavailable.value = true;
      return;
    }
    error.value = err.message || "Error al iniciar sesión";
  }
};
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-primary-600 mb-2">
          FactuFlow
        </h1>
        <p class="text-gray-600">
          Sistema de Facturación Electrónica ARCA
        </p>
      </div>

      <BaseCard>
        <h2 class="text-2xl font-bold text-gray-900 mb-6">
          Iniciar Sesión
        </h2>

        <BaseAlert
          v-if="serverUnavailable"
          type="warning"
          title="FactuFlow no está listo para iniciar sesión"
          class="mb-4"
          @dismiss="serverUnavailable = false"
        >
          <p>{{ serverUnavailableMessage }}</p>
          <BaseButton
            type="button"
            variant="secondary"
            size="sm"
            class="mt-3"
            :loading="checkingServer"
            @click="retryServerConnection"
          >
            Reintentar
          </BaseButton>
        </BaseAlert>

        <BaseAlert
          v-if="error"
          type="error"
          title="Error"
          :message="error"
          class="mb-4"
          @dismiss="error = ''"
        />

        <form
          class="space-y-4"
          @submit.prevent="handleSubmit"
        >
          <BaseInput
            v-model="email"
            type="email"
            label="Correo electrónico"
            placeholder="usuario@ejemplo.com"
            required
          />

          <BaseInput
            v-model="password"
            type="password"
            label="Contraseña"
            placeholder="••••••••"
            required
          />

          <BaseButton
            type="submit"
            variant="primary"
            class="w-full"
            :loading="loading || checkingServer"
          >
            Ingresar
          </BaseButton>
        </form>

        <div class="mt-4 text-center text-sm text-gray-600">
          ¿Primera vez?
          <router-link
            to="/setup"
            class="text-primary-600 hover:text-primary-700 font-medium"
          >
            Configurar sistema
          </router-link>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
