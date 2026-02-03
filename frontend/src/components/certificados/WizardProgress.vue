<script setup lang="ts">
import { computed } from 'vue'

interface Step {
  number: number
  title: string
  shortTitle: string
}

interface Props {
  currentStep: number
  steps: Step[]
}

const props = defineProps<Props>()

const getStepClasses = (stepNumber: number) => {
  const isActive = stepNumber === props.currentStep
  const isCompleted = stepNumber < props.currentStep
  
  return {
    'bg-blue-600 text-white': isActive,
    'bg-green-500 text-white': isCompleted,
    'bg-gray-200 text-gray-500': !isActive && !isCompleted
  }
}

const getLineClasses = (stepNumber: number) => {
  const isCompleted = stepNumber < props.currentStep
  
  return {
    'bg-green-500': isCompleted,
    'bg-gray-300': !isCompleted
  }
}
</script>

<template>
  <div class="w-full py-6">
    <div class="flex items-center justify-between relative">
      <!-- Steps -->
      <div
        v-for="(step, index) in steps"
        :key="step.number"
        class="flex flex-col items-center relative z-10"
        :class="{ 'flex-1': index < steps.length - 1 }"
      >
        <!-- Circle -->
        <div
          class="w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all duration-300"
          :class="getStepClasses(step.number)"
        >
          <span v-if="step.number < currentStep">✓</span>
          <span v-else>{{ step.number }}</span>
        </div>
        
        <!-- Title -->
        <div class="mt-2 text-center">
          <p
            class="text-xs font-medium transition-colors duration-300"
            :class="{
              'text-blue-600': step.number === currentStep,
              'text-green-600': step.number < currentStep,
              'text-gray-500': step.number > currentStep
            }"
          >
            <span class="hidden sm:inline">{{ step.title }}</span>
            <span class="inline sm:hidden">{{ step.shortTitle }}</span>
          </p>
        </div>
        
        <!-- Connecting Line -->
        <div
          v-if="index < steps.length - 1"
          class="absolute top-5 h-0.5 transition-all duration-300"
          :class="getLineClasses(step.number)"
          :style="{
            left: '50%',
            right: index === steps.length - 2 ? '-50%' : `calc(-100% + 2.5rem)`,
            width: index === steps.length - 2 ? '50%' : 'calc(100% - 2.5rem)'
          }"
        />
      </div>
    </div>
  </div>
</template>
