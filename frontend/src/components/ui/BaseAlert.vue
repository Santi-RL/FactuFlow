<script setup lang="ts">
import { computed } from "vue";
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from "@heroicons/vue/24/outline";

interface Props {
  type: "success" | "error" | "warning" | "info";
  title?: string;
  message?: string;
  dismissible?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  title: "",
  message: "",
  dismissible: true,
});

const emit = defineEmits<{
  dismiss: [];
}>();

const iconComponent = computed(() => {
  const icons = {
    success: CheckCircleIcon,
    error: XCircleIcon,
    warning: ExclamationTriangleIcon,
    info: InformationCircleIcon,
  };
  return icons[props.type];
});

const colorClasses = computed(() => {
  const colors = {
    success: "bg-emerald-50 border-emerald-200 text-status-success",
    error: "bg-red-50 border-red-200 text-status-danger",
    warning: "bg-amber-50 border-amber-200 text-amber-900",
    info: "bg-brand-mint border-border-subtle text-brand-ink",
  };
  return colors[props.type];
});

const iconColorClasses = computed(() => {
  const colors = {
    success: "text-status-success",
    error: "text-status-danger",
    warning: "text-amber-700",
    info: "text-brand-flow",
  };
  return colors[props.type];
});
</script>

<template>
  <div :class="['flex items-start gap-3 rounded-panel border p-4', colorClasses]">
    <component
      :is="iconComponent"
      :class="['h-5 w-5 flex-shrink-0 mt-0.5', iconColorClasses]"
    />

    <div class="flex-1">
      <h3
        v-if="title"
        class="text-sm font-medium"
      >
        {{ title }}
      </h3>
      <div
        v-if="$slots.default"
        :class="[title ? 'mt-1 text-sm opacity-90' : 'text-sm opacity-90']"
      >
        <slot />
      </div>
      <p
        v-else-if="message"
        :class="[title ? 'mt-1 text-sm opacity-90' : 'text-sm opacity-90']"
      >
        {{ message }}
      </p>
    </div>

    <button
      v-if="dismissible"
      type="button"
      class="flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity"
      @click="emit('dismiss')"
    >
      <XMarkIcon class="h-5 w-5" />
    </button>
  </div>
</template>
