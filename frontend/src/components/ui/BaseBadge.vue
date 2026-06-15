<script setup lang="ts">
import { computed } from "vue";

interface Props {
  variant?: "default" | "primary" | "success" | "warning" | "danger" | "info";
  size?: "sm" | "md" | "lg";
}

const props = withDefaults(defineProps<Props>(), {
  variant: "default",
  size: "md",
});

const classes = computed(() => {
  const baseClasses =
    "inline-flex items-center justify-center font-medium rounded-full";

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-0.5 text-sm",
    lg: "px-3 py-1 text-base",
  };

  const variantClasses = {
    default: "bg-surface-page text-brand-slate",
    primary: "bg-brand-mint text-brand-teal",
    success: "bg-emerald-100 text-status-success",
    warning: "bg-amber-100 text-amber-900",
    danger: "bg-red-100 text-status-danger",
    info: "bg-blue-100 text-status-info",
  };

  return `${baseClasses} ${sizeClasses[props.size]} ${variantClasses[props.variant]}`;
});
</script>

<template>
  <span :class="classes">
    <slot />
  </span>
</template>
