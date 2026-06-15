<script setup lang="ts">
import { XMarkIcon } from "@heroicons/vue/24/outline";

interface Props {
  show: boolean;
  title?: string;
  size?: "sm" | "md" | "lg" | "xl" | "2xl" | "full";
}

withDefaults(defineProps<Props>(), {
  title: "",
  size: "md",
});

const emit = defineEmits<{
  close: [];
}>();

const sizeClasses = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
  "2xl": "max-w-6xl",
  full: "max-w-[min(98vw,1440px)]",
};

const handleClose = () => {
  emit("close");
};

const handleOverlayClick = (event: MouseEvent) => {
  if (event.target === event.currentTarget) {
    handleClose();
  }
};
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="show"
        class="fixed inset-0 z-40 bg-[rgba(16,20,24,0.72)] transition-opacity"
        @click="handleOverlayClick"
      />
    </Transition>

    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
      enter-to-class="opacity-100 translate-y-0 sm:scale-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100 translate-y-0 sm:scale-100"
      leave-to-class="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
    >
      <div
        v-if="show"
        class="fixed inset-0 z-50 overflow-y-auto"
        @click="handleOverlayClick"
      >
        <div class="flex min-h-full items-center justify-center p-3 sm:p-4">
          <div
            :class="[
              'relative flex max-h-[calc(100vh-2rem)] w-full flex-col overflow-hidden rounded-modal bg-surface-card shadow-overlay',
              sizeClasses[size],
            ]"
            @click.stop
          >
            <!-- Header -->
            <div
              v-if="title || $slots.header"
              class="flex items-center justify-between border-b border-border-subtle p-4 sm:p-6"
            >
              <h3 class="text-lg font-semibold text-brand-ink">
                <slot name="header">
                  {{ title }}
                </slot>
              </h3>
              <button
                type="button"
                class="text-brand-slate transition-colors hover:text-brand-ink"
                @click="handleClose"
              >
                <XMarkIcon class="h-6 w-6" />
              </button>
            </div>

            <!-- Content -->
            <div class="min-h-0 overflow-y-auto p-4 sm:p-6">
              <slot />
            </div>

            <!-- Footer -->
            <div
              v-if="$slots.footer"
              class="flex items-center justify-end gap-3 rounded-b-modal border-t border-border-subtle bg-surface-page p-4 sm:p-6"
            >
              <slot name="footer" />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
