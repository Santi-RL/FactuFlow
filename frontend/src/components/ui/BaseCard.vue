<script setup lang="ts">
interface Props {
  title?: string;
  padding?: boolean;
}

withDefaults(defineProps<Props>(), {
  title: "",
  padding: true,
});
</script>

<template>
  <div class="rounded-panel border border-border-subtle bg-surface-card shadow-panel">
    <div
      v-if="title || $slots.header"
      class="border-b border-border-subtle px-6 py-4"
    >
      <h3 class="text-lg font-semibold text-brand-ink">
        <slot name="header">
          {{ title }}
        </slot>
      </h3>
    </div>

    <div :class="padding ? 'p-6' : ''">
      <slot />
    </div>

    <div
      v-if="$slots.footer"
      class="rounded-b-panel border-t border-border-subtle bg-surface-page px-6 py-4"
    >
      <slot name="footer" />
    </div>
  </div>
</template>
