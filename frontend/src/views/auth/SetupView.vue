<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useEmpresaStore } from '@/stores/empresa'
import { useNotification } from '@/composables/useNotification'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import BaseAlert from '@/components/ui/BaseAlert.vue'

const router = useRouter()
const authStore = useAuthStore()
const empresaStore = useEmpresaStore()
const { showSuccess, showError } = useNotification()

const loading = ref(false)
const error = ref('')
const step = ref(1)

// Usuario admin
const usuario = ref({
  nombre: '',
  email: '',
  password: '',
  passwordConfirm: ''
})

// Datos de empresa
const empresa = ref({
  razon_social: '',
  cuit: '',
  condicion_iva: 'RI' as 'RI' | 'Monotributo' | 'Exento',
  domicilio: '',
  localidad: '',
  provincia: '',
  codigo_postal: '',
  email: '',
  telefono: '',
  inicio_actividades: ''
})

const condicionIvaOptions = [
  { value: 'RI', label: 'Responsable Inscripto' },
  { value: 'Monotributo', label: 'Monotributo' },
  { value: 'Exento', label: 'Exento' }
]

const provinciasOptions = [
  { value: 'Buenos Aires', label: 'Buenos Aires' },
  { value: 'CABA', label: 'Ciudad Autónoma de Buenos Aires' },
  { value: 'Catamarca', label: 'Catamarca' },
  { value: 'Chaco', label: 'Chaco' },
  { value: 'Chubut', label: 'Chubut' },
  { value: 'Córdoba', label: 'Córdoba' },
  { value: 'Corrientes', label: 'Corrientes' },
  { value: 'Entre Ríos', label: 'Entre Ríos' },
  { value: 'Formosa', label: 'Formosa' },
  { value: 'Jujuy', label: 'Jujuy' },
  { value: 'La Pampa', label: 'La Pampa' },
  { value: 'La Rioja', label: 'La Rioja' },
  { value: 'Mendoza', label: 'Mendoza' },
  { value: 'Misiones', label: 'Misiones' },
  { value: 'Neuquén', label: 'Neuquén' },
  { value: 'Río Negro', label: 'Río Negro' },
  { value: 'Salta', label: 'Salta' },
  { value: 'San Juan', label: 'San Juan' },
  { value: 'San Luis', label: 'San Luis' },
  { value: 'Santa Cruz', label: 'Santa Cruz' },
  { value: 'Santa Fe', label: 'Santa Fe' },
  { value: 'Santiago del Estero', label: 'Santiago del Estero' },
  { value: 'Tierra del Fuego', label: 'Tierra del Fuego' },
  { value: 'Tucumán', label: 'Tucumán' }
]

const nextStep = () => {
  error.value = ''
  
  if (step.value === 1) {
    if (!usuario.value.nombre || !usuario.value.email || !usuario.value.password) {
      error.value = 'Por favor complete todos los campos'
      return
    }
    
    if (usuario.value.password !== usuario.value.passwordConfirm) {
      error.value = 'Las contraseñas no coinciden'
      return
    }
    
    if (usuario.value.password.length < 6) {
      error.value = 'La contraseña debe tener al menos 6 caracteres'
      return
    }
  }
  
  step.value++
}

const previousStep = () => {
  step.value--
}

const handleSubmit = async () => {
  error.value = ''
  loading.value = true

  try {
    // Crear empresa primero
    const nuevaEmpresa = await empresaStore.createEmpresa(empresa.value)
    
    // Crear usuario admin
    await authStore.setup({
      nombre: usuario.value.nombre,
      email: usuario.value.email,
      password: usuario.value.password,
      empresa_id: nuevaEmpresa.id
    })

    showSuccess('Sistema configurado', 'Ya puede iniciar sesión')
    router.push('/login')
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Error al configurar el sistema'
    showError('Error', error.value)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 py-12 px-4">
    <div class="max-w-2xl mx-auto">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold text-primary-600 mb-2">
          FactuFlow
        </h1>
        <p class="text-gray-600">
          Configuración Inicial del Sistema
        </p>
      </div>

      <BaseCard>
        <!-- Progress indicator -->
        <div class="mb-8">
          <div class="flex items-center justify-between mb-2">
            <span :class="['text-sm font-medium', step >= 1 ? 'text-primary-600' : 'text-gray-500']">
              1. Usuario Admin
            </span>
            <span :class="['text-sm font-medium', step >= 2 ? 'text-primary-600' : 'text-gray-500']">
              2. Datos de Empresa
            </span>
          </div>
          <div class="flex gap-2">
            <div :class="['flex-1 h-2 rounded', step >= 1 ? 'bg-primary-600' : 'bg-gray-200']" />
            <div :class="['flex-1 h-2 rounded', step >= 2 ? 'bg-primary-600' : 'bg-gray-200']" />
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
          v-if="step === 1"
          class="space-y-4"
        >
          <h2 class="text-xl font-bold text-gray-900 mb-4">
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
            <BaseButton @click="nextStep">
              Continuar
            </BaseButton>
          </div>
        </div>

        <!-- Step 2: Empresa -->
        <div
          v-if="step === 2"
          class="space-y-4"
        >
          <h2 class="text-xl font-bold text-gray-900 mb-4">
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
            v-model="empresa.domicilio"
            label="Domicilio"
            placeholder="Av. Siempre Viva 123"
            required
          />

          <div class="grid grid-cols-2 gap-4">
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

          <div class="flex justify-between pt-4">
            <BaseButton
              variant="secondary"
              @click="previousStep"
            >
              Volver
            </BaseButton>
            <BaseButton
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
