<script setup lang="ts">
import { computed } from "vue";
import { ChevronLeftIcon, ChevronRightIcon } from "@heroicons/vue/24/outline";

interface Props {
  currentPage: number;
  totalPages: number;
  perPage?: number;
  total?: number;
}

const props = withDefaults(defineProps<Props>(), {
  perPage: 30,
  total: 0,
});

const emit = defineEmits<{
  "update:currentPage": [page: number];
}>();

const pages = computed(() => {
  const result = [];
  const maxPages = 7;

  if (props.totalPages <= maxPages) {
    for (let i = 1; i <= props.totalPages; i++) {
      result.push(i);
    }
  } else {
    if (props.currentPage <= 4) {
      for (let i = 1; i <= 5; i++) result.push(i);
      result.push("...");
      result.push(props.totalPages);
    } else if (props.currentPage >= props.totalPages - 3) {
      result.push(1);
      result.push("...");
      for (let i = props.totalPages - 4; i <= props.totalPages; i++)
        result.push(i);
    } else {
      result.push(1);
      result.push("...");
      for (let i = props.currentPage - 1; i <= props.currentPage + 1; i++)
        result.push(i);
      result.push("...");
      result.push(props.totalPages);
    }
  }

  return result;
});

const goToPage = (page: number | string) => {
  if (typeof page === "number" && page !== props.currentPage) {
    emit("update:currentPage", page);
  }
};

const previousPage = () => {
  if (props.currentPage > 1) {
    emit("update:currentPage", props.currentPage - 1);
  }
};

const nextPage = () => {
  if (props.currentPage < props.totalPages) {
    emit("update:currentPage", props.currentPage + 1);
  }
};

const startItem = computed(() => (props.currentPage - 1) * props.perPage + 1);
const endItem = computed(() =>
  Math.min(props.currentPage * props.perPage, props.total || 0),
);
</script>

<template>
  <div
    class="flex items-center justify-between border-t border-border-subtle bg-surface-card px-4 py-3 sm:px-6"
  >
    <div class="flex flex-1 justify-between sm:hidden">
      <button
        :disabled="currentPage === 1"
        class="relative inline-flex items-center rounded-control border border-border-subtle bg-surface-card px-4 py-2 text-sm font-medium text-brand-ink transition-colors hover:bg-brand-mint focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        @click="previousPage"
      >
        Anterior
      </button>
      <button
        :disabled="currentPage === totalPages"
        class="relative ml-3 inline-flex items-center rounded-control border border-border-subtle bg-surface-card px-4 py-2 text-sm font-medium text-brand-ink transition-colors hover:bg-brand-mint focus:outline-none focus:ring-2 focus:ring-brand-flow focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        @click="nextPage"
      >
        Siguiente
      </button>
    </div>

    <div class="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
      <div>
        <p class="text-sm text-brand-slate">
          Mostrando
          <span class="font-medium text-brand-ink">{{ startItem }}</span>
          a
          <span class="font-medium text-brand-ink">{{ endItem }}</span>
          de
          <span class="font-medium text-brand-ink">{{ total }}</span>
          resultados
        </p>
      </div>

      <div>
        <nav
          class="isolate inline-flex -space-x-px rounded-control shadow-panel"
          aria-label="Paginación"
        >
          <button
            :disabled="currentPage === 1"
            class="relative inline-flex items-center rounded-l-control px-2 py-2 text-brand-slate ring-1 ring-inset ring-border-subtle transition-colors hover:bg-brand-mint hover:text-brand-teal focus:z-20 focus:outline-none focus:ring-2 focus:ring-brand-flow disabled:cursor-not-allowed disabled:opacity-50"
            @click="previousPage"
          >
            <span class="sr-only">Anterior</span>
            <ChevronLeftIcon class="h-5 w-5" />
          </button>

          <button
            v-for="(page, index) in pages"
            :key="index"
            :class="[
              'relative inline-flex items-center px-4 py-2 text-sm font-semibold ring-1 ring-inset ring-border-subtle transition-colors focus:z-20 focus:outline-none focus:ring-2 focus:ring-brand-flow',
              page === currentPage
                ? 'z-10 bg-brand-teal text-white'
                : page === '...'
                  ? 'cursor-default text-brand-slate'
                  : 'cursor-pointer text-brand-ink hover:bg-brand-mint hover:text-brand-teal',
            ]"
            :disabled="page === '...'"
            @click="goToPage(page)"
          >
            {{ page }}
          </button>

          <button
            :disabled="currentPage === totalPages"
            class="relative inline-flex items-center rounded-r-control px-2 py-2 text-brand-slate ring-1 ring-inset ring-border-subtle transition-colors hover:bg-brand-mint hover:text-brand-teal focus:z-20 focus:outline-none focus:ring-2 focus:ring-brand-flow disabled:cursor-not-allowed disabled:opacity-50"
            @click="nextPage"
          >
            <span class="sr-only">Siguiente</span>
            <ChevronRightIcon class="h-5 w-5" />
          </button>
        </nav>
      </div>
    </div>
  </div>
</template>
