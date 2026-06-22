<script setup lang="ts">
import {
  ArrowRightIcon,
  CheckCircleIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
  KeyIcon,
} from "@heroicons/vue/24/outline";
import BaseButton from "@/components/ui/BaseButton.vue";
import BaseCard from "@/components/ui/BaseCard.vue";

interface Emits {
  (e: "next"): void;
}

const emit = defineEmits<Emits>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <div class="mb-8 text-center">
      <div
        class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-panel bg-brand-mint text-brand-teal"
      >
        <KeyIcon class="h-9 w-9" />
      </div>
      <h2 class="mb-2 text-3xl font-bold text-brand-ink">
        ¡Configuremos tu certificado ARCA!
      </h2>
    </div>

    <BaseCard class="mb-8">
      <div class="space-y-6 text-lg text-brand-slate">
        <p>
          Para poder emitir facturas electrónicas, necesitás un certificado
          digital que te identifica ante ARCA.
        </p>

        <p>
          Este asistente te guiará paso a paso por todo el proceso.
          <strong class="font-semibold text-brand-ink">
            ¡No te preocupes, es más fácil de lo que parece!
          </strong>
        </p>

        <div class="border-l-4 border-brand-teal bg-brand-mint p-6">
          <h3
            class="mb-4 flex items-center gap-2 text-lg font-semibold text-brand-ink"
          >
            <ClipboardDocumentListIcon class="h-5 w-5 text-brand-teal" />
            <span>Vas a necesitar:</span>
          </h3>

          <ul class="space-y-2">
            <li class="flex items-start gap-2">
              <CheckCircleIcon
                class="mt-1 h-5 w-5 flex-shrink-0 text-status-success"
              />
              <span>Tu CUIT</span>
            </li>
            <li class="flex items-start gap-2">
              <CheckCircleIcon
                class="mt-1 h-5 w-5 flex-shrink-0 text-status-success"
              />
              <span>Tu clave fiscal (nivel 3 o superior)</span>
            </li>
            <li class="flex items-start gap-2">
              <CheckCircleIcon
                class="mt-1 h-5 w-5 flex-shrink-0 text-status-success"
              />
              <span>Acceso al portal de ARCA</span>
            </li>
          </ul>
        </div>

        <div class="border-t border-border-subtle pt-6">
          <div class="mb-2 flex items-center gap-3">
            <ClockIcon class="h-6 w-6 text-brand-teal" />
            <span class="text-lg font-semibold text-brand-ink">
              Tiempo estimado:
            </span>
          </div>
          <p>
            10-15 minutos
          </p>
        </div>
      </div>
    </BaseCard>

    <div class="flex justify-center">
      <BaseButton
        size="lg"
        class="gap-2"
        @click="emit('next')"
      >
        <span>Comenzar</span>
        <ArrowRightIcon class="h-5 w-5" />
      </BaseButton>
    </div>
  </div>
</template>
