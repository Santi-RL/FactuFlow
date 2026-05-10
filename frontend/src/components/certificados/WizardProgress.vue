<script setup lang="ts">
import { computed } from "vue";
import { CheckIcon } from "@heroicons/vue/24/solid";

interface Step {
  number: number;
  title: string;
  shortTitle: string;
}

interface Props {
  currentStep: number;
  steps: Step[];
}

const props = defineProps<Props>();

const currentStepIndex = computed(() => {
  const index = props.steps.findIndex(
    (step) => step.number === props.currentStep,
  );
  return Math.max(index, 0);
});

const progressPercentage = computed(() => {
  if (props.steps.length <= 1) return 0;
  return (currentStepIndex.value / (props.steps.length - 1)) * 100;
});

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${props.steps.length}, minmax(0, 1fr))`,
}));

const lineInset = computed(() => `${100 / (props.steps.length * 2)}%`);

const lineStyle = computed(() => ({
  left: lineInset.value,
  right: lineInset.value,
}));

const progressStyle = computed(() => ({
  width: `${progressPercentage.value}%`,
}));

const getStepClasses = (stepNumber: number) => {
  const isActive = stepNumber === props.currentStep;
  const isCompleted = stepNumber < props.currentStep;

  return {
    "bg-blue-600 text-white border-blue-600 shadow-sm ring-4 ring-blue-100 scale-105":
      isActive,
    "bg-green-500 text-white border-green-500 shadow-sm": isCompleted,
    "bg-white text-gray-500 border-gray-300": !isActive && !isCompleted,
  };
};

const getLabelClasses = (stepNumber: number) => {
  const isActive = stepNumber === props.currentStep;
  const isCompleted = stepNumber < props.currentStep;

  return {
    "text-blue-700 font-semibold": isActive,
    "text-green-700 font-medium": isCompleted,
    "text-gray-500 font-medium": !isActive && !isCompleted,
  };
};
</script>

<template>
  <div class="w-full py-6">
    <div class="relative">
      <div
        class="absolute top-5 h-1 rounded-full bg-gray-200"
        :style="lineStyle"
      >
        <div
          class="h-full rounded-full bg-green-500 transition-all duration-500 ease-out"
          :style="progressStyle"
        />
      </div>

      <ol class="relative grid items-start" :style="gridStyle">
        <li
          v-for="step in steps"
          :key="step.number"
          class="flex min-w-0 flex-col items-center text-center"
          :aria-current="step.number === currentStep ? 'step' : undefined"
        >
          <div
            class="relative z-10 flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-bold transition-all duration-300"
            :class="getStepClasses(step.number)"
          >
            <CheckIcon
              v-if="step.number < currentStep"
              class="h-5 w-5"
              aria-hidden="true"
            />
            <span v-else>{{ step.number }}</span>
          </div>

          <div class="mt-3 min-w-0 px-1">
            <p
              class="truncate text-xs leading-4 transition-colors duration-300"
              :class="getLabelClasses(step.number)"
            >
              <span class="hidden md:inline">{{ step.title }}</span>
              <span class="inline md:hidden">{{ step.shortTitle }}</span>
            </p>
            <p
              v-if="step.number === currentStep"
              class="mt-1 hidden text-[11px] font-medium text-gray-500 sm:block"
            >
              Paso actual
            </p>
            <span class="sr-only" v-if="step.number < currentStep">
              Completado
            </span>
          </div>
        </li>
      </ol>
    </div>
  </div>
</template>
