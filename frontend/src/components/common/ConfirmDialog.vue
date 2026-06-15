<script setup lang="ts">
import { computed } from "vue";
import BaseModal from "../ui/BaseModal.vue";
import BaseButton from "../ui/BaseButton.vue";
import { ExclamationTriangleIcon } from "@heroicons/vue/24/outline";

interface Props {
  show: boolean;
  title?: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "danger" | "primary";
}

withDefaults(defineProps<Props>(), {
  title: "¿Está seguro?",
  message: "Esta acción no se puede deshacer",
  confirmText: "Confirmar",
  cancelText: "Cancelar",
  variant: "danger",
});

const emit = defineEmits<{
  confirm: [];
  cancel: [];
}>();

const iconShellClasses = computed(() => ({
  danger: "bg-[rgba(180,35,24,0.10)]",
  primary: "bg-brand-mint",
}));

const iconClasses = computed(() => ({
  danger: "text-status-danger",
  primary: "text-brand-teal",
}));
</script>

<template>
  <BaseModal
    :show="show"
    size="sm"
    @close="emit('cancel')"
  >
    <div class="text-center">
      <div
        :class="[
          'mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full',
          iconShellClasses[variant],
        ]"
      >
        <ExclamationTriangleIcon
          :class="['h-6 w-6', iconClasses[variant]]"
        />
      </div>

      <h3 class="mb-2 text-lg font-semibold text-brand-ink">
        {{ title }}
      </h3>
      <p class="mb-6 text-sm leading-6 text-brand-slate">
        {{ message }}
      </p>

      <div class="flex flex-col-reverse justify-center gap-3 sm:flex-row">
        <BaseButton
          variant="secondary"
          @click="emit('cancel')"
        >
          {{ cancelText }}
        </BaseButton>
        <BaseButton
          :variant="variant"
          @click="emit('confirm')"
        >
          {{ confirmText }}
        </BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
