<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '@/composables/useAuth'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseAlert from '@/components/ui/BaseAlert.vue'

const { login, loading } = useAuth()

const email = ref('')
const password = ref('')
const error = ref('')

const handleSubmit = async () => {
  error.value = ''
  
  if (!email.value || !password.value) {
    error.value = 'Por favor complete todos los campos'
    return
  }

  try {
    await login(email.value, password.value)
  } catch (err: any) {
    error.value = err.message || 'Error al iniciar sesión'
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-primary-600 mb-2">FactuFlow</h1>
        <p class="text-gray-600">Sistema de Facturación Electrónica ARCA</p>
      </div>

      <BaseCard>
        <h2 class="text-2xl font-bold text-gray-900 mb-6">Iniciar Sesión</h2>

        <BaseAlert
          v-if="error"
          type="error"
          title="Error"
          :message="error"
          class="mb-4"
          @dismiss="error = ''"
        />

        <form @submit.prevent="handleSubmit" class="space-y-4">
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
            :loading="loading"
          >
            Ingresar
          </BaseButton>
        </form>

        <div class="mt-4 text-center text-sm text-gray-600">
          ¿Primera vez?
          <router-link to="/setup" class="text-primary-600 hover:text-primary-700 font-medium">
            Configurar sistema
          </router-link>
        </div>
      </BaseCard>
    </div>
  </div>
</template>
