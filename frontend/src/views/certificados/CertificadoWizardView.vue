<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { Certificado } from '@/types/certificado'
import WizardProgress from '@/components/certificados/WizardProgress.vue'
import WizardStep1Intro from '@/components/certificados/WizardStep1Intro.vue'
import WizardStep2GenerarCSR from '@/components/certificados/WizardStep2GenerarCSR.vue'
import WizardStep3PortalArca from '@/components/certificados/WizardStep3PortalArca.vue'
import WizardStep4SubirCert from '@/components/certificados/WizardStep4SubirCert.vue'
import WizardStep5Verificar from '@/components/certificados/WizardStep5Verificar.vue'

const router = useRouter()

const currentStep = ref(1)
const wizardData = ref({
  cuit: '',
  nombre: '',
  ambiente: '',
  keyFilename: ''
})
const certificadoCreado = ref<Certificado | null>(null)

const steps = [
  { number: 1, title: 'Introducción', shortTitle: 'Intro' },
  { number: 2, title: 'Generar CSR', shortTitle: 'CSR' },
  { number: 3, title: 'Portal ARCA', shortTitle: 'Portal' },
  { number: 4, title: 'Subir Cert', shortTitle: 'Subir' },
  { number: 5, title: 'Verificar', shortTitle: 'Verificar' }
]

const onStep2Next = (data: { keyFilename: string; cuit: string; nombre: string; ambiente: string }) => {
  wizardData.value = data
  currentStep.value = 3
}

const onStep4Next = (certificado: Certificado) => {
  certificadoCreado.value = certificado
  currentStep.value = 5
}

const onFinish = () => {
  // Redirigir a la página de éxito o listado
  router.push({
    name: 'certificado-exito',
    params: { id: certificadoCreado.value?.id }
  })
}

const goToPrevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

const goToNextStep = () => {
  if (currentStep.value < 5) {
    currentStep.value++
  }
}
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <div class="mb-8">
      <h1
        class="text-3xl font-bold text-gray-900 mb-2"
        data-testid="page-title"
      >
        Wizard de Certificados ARCA
      </h1>
      <p class="text-gray-600">
        Configurá tu certificado digital paso a paso
      </p>
    </div>
    
    <!-- Progress Bar -->
    <WizardProgress
      :current-step="currentStep"
      :steps="steps"
    />
    
    <!-- Steps Content -->
    <div class="mt-8">
      <WizardStep1Intro
        v-if="currentStep === 1"
        @next="goToNextStep"
      />
      
      <WizardStep2GenerarCSR
        v-else-if="currentStep === 2"
        @next="onStep2Next"
        @prev="goToPrevStep"
      />
      
      <WizardStep3PortalArca
        v-else-if="currentStep === 3"
        @next="goToNextStep"
        @prev="goToPrevStep"
      />
      
      <WizardStep4SubirCert
        v-else-if="currentStep === 4"
        :cuit="wizardData.cuit"
        :nombre="wizardData.nombre"
        :ambiente="wizardData.ambiente"
        :key-filename="wizardData.keyFilename"
        @next="onStep4Next"
        @prev="goToPrevStep"
      />
      
      <WizardStep5Verificar
        v-else-if="currentStep === 5 && certificadoCreado"
        :certificado="certificadoCreado"
        @finish="onFinish"
        @prev="goToPrevStep"
      />
    </div>
  </div>
</template>
