<script setup lang="ts">
import { computed } from "vue";

interface Props {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}

const props = withDefaults(defineProps<Props>(), {
  variant: "primary",
  size: "md",
  loading: false,
  disabled: false,
  type: "button",
});

const classes = computed(() => {
  const baseClasses =
    "inline-flex items-center justify-center rounded-control font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60";

  const sizeClasses = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2 text-base",
    lg: "px-6 py-3 text-lg",
  };

  const variantClasses = {
    primary:
      "border border-transparent bg-brand-teal text-white hover:bg-brand-flow",
    secondary:
      "border border-border-subtle bg-surface-card text-brand-ink hover:bg-brand-mint",
    danger:
      "border border-transparent bg-status-danger text-white hover:bg-red-700 focus:ring-status-danger",
    ghost:
      "border border-transparent bg-transparent text-brand-slate hover:bg-brand-mint hover:text-brand-ink",
  };

  return `${baseClasses} ${sizeClasses[props.size]} ${variantClasses[props.variant]}`;
});
</script>

<template>
  <button
    :type="type"
    :class="classes"
    :disabled="disabled || loading"
  >
    <svg
      v-if="loading"
      class="animate-spin -ml-1 mr-2 h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        class="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        stroke-width="4"
      />
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
    <slot />
  </button>
</template>
