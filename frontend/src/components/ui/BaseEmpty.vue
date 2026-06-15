<script setup lang="ts">
import { FolderOpenIcon } from "@heroicons/vue/24/outline";

interface Props {
  title?: string;
  message?: string;
  icon?: any;
}

withDefaults(defineProps<Props>(), {
  title: "No hay datos",
  message: "No se encontraron resultados",
  icon: FolderOpenIcon,
});
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 text-center">
    <component
      :is="icon"
      class="mb-4 h-16 w-16 text-brand-slate"
    />
    <h3 class="mb-1 text-lg font-medium text-brand-ink">
      {{ title }}
    </h3>
    <p class="text-brand-slate">
      {{ message }}
    </p>
    <div
      v-if="$slots.default || $slots.actions || $slots.action"
      class="mt-6"
    >
      <slot />
      <slot name="actions" />
      <slot name="action" />
    </div>
  </div>
</template>
