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
    "inline-flex items-center justify-center rounded-full border font-medium";

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-0.5 text-sm",
    lg: "px-3 py-1 text-base",
  };

  const variantClasses = {
    default: "border-border-subtle bg-surface-page text-brand-slate",
    primary: "border-border-subtle bg-brand-mint text-brand-teal",
    success: "border-status-success bg-status-success-soft text-status-success",
    warning: "border-status-warning bg-status-warning-soft text-status-warning",
    danger: "border-status-danger bg-status-danger-soft text-status-danger",
    info: "border-status-info bg-status-info-soft text-status-info",
  };

  return `${baseClasses} ${sizeClasses[props.size]} ${variantClasses[props.variant]}`;
});
</script>

<template>
  <span :class="classes">
    <slot />
  </span>
</template>
