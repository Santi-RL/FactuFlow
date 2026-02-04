<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/vue/24/outline'

interface Props {
  currentPage: number
  totalPages: number
  perPage?: number
  total?: number
}

const props = withDefaults(defineProps<Props>(), {
  perPage: 30
})

const emit = defineEmits<{
  'update:currentPage': [page: number]
}>()

const pages = computed(() => {
  const result = []
  const maxPages = 7
  
  if (props.totalPages <= maxPages) {
    for (let i = 1; i <= props.totalPages; i++) {
      result.push(i)
    }
  } else {
    if (props.currentPage <= 4) {
      for (let i = 1; i <= 5; i++) result.push(i)
      result.push('...')
      result.push(props.totalPages)
    } else if (props.currentPage >= props.totalPages - 3) {
      result.push(1)
      result.push('...')
      for (let i = props.totalPages - 4; i <= props.totalPages; i++) result.push(i)
    } else {
      result.push(1)
      result.push('...')
      for (let i = props.currentPage - 1; i <= props.currentPage + 1; i++) result.push(i)
      result.push('...')
      result.push(props.totalPages)
    }
  }
  
  return result
})

const goToPage = (page: number | string) => {
  if (typeof page === 'number' && page !== props.currentPage) {
    emit('update:currentPage', page)
  }
}

const previousPage = () => {
  if (props.currentPage > 1) {
    emit('update:currentPage', props.currentPage - 1)
  }
}

const nextPage = () => {
  if (props.currentPage < props.totalPages) {
    emit('update:currentPage', props.currentPage + 1)
  }
}

const startItem = computed(() => (props.currentPage - 1) * props.perPage + 1)
const endItem = computed(() => Math.min(props.currentPage * props.perPage, props.total || 0))
</script>

<template>
  <div class="flex items-center justify-between border-t border-gray-200 bg-white px-4 py-3 sm:px-6">
    <div class="flex flex-1 justify-between sm:hidden">
      <button
        :disabled="currentPage === 1"
        class="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        @click="previousPage"
      >
        Anterior
      </button>
      <button
        :disabled="currentPage === totalPages"
        class="relative ml-3 inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        @click="nextPage"
      >
        Siguiente
      </button>
    </div>
    
    <div class="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
      <div>
        <p class="text-sm text-gray-700">
          Mostrando
          <span class="font-medium">{{ startItem }}</span>
          a
          <span class="font-medium">{{ endItem }}</span>
          de
          <span class="font-medium">{{ total }}</span>
          resultados
        </p>
      </div>
      
      <div>
        <nav
          class="isolate inline-flex -space-x-px rounded-md shadow-sm"
          aria-label="Pagination"
        >
          <button
            :disabled="currentPage === 1"
            class="relative inline-flex items-center rounded-l-md px-2 py-2 text-gray-400 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0 disabled:opacity-50 disabled:cursor-not-allowed"
            @click="previousPage"
          >
            <span class="sr-only">Anterior</span>
            <ChevronLeftIcon class="h-5 w-5" />
          </button>
          
          <button
            v-for="(page, index) in pages"
            :key="index"
            :class="[
              'relative inline-flex items-center px-4 py-2 text-sm font-semibold ring-1 ring-inset ring-gray-300 focus:z-20 focus:outline-offset-0',
              page === currentPage
                ? 'z-10 bg-primary-600 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600'
                : page === '...'
                  ? 'text-gray-700 cursor-default'
                  : 'text-gray-900 hover:bg-gray-50 cursor-pointer'
            ]"
            :disabled="page === '...'"
            @click="goToPage(page)"
          >
            {{ page }}
          </button>
          
          <button
            :disabled="currentPage === totalPages"
            class="relative inline-flex items-center rounded-r-md px-2 py-2 text-gray-400 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0 disabled:opacity-50 disabled:cursor-not-allowed"
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
