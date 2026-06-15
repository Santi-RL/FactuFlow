<script setup lang="ts">
import BaseSpinner from "./BaseSpinner.vue";

interface Column {
  key: string;
  label: string;
  sortable?: boolean;
}

interface Props {
  columns: Column[];
  data: any[];
  loading?: boolean;
  emptyText?: string;
}

withDefaults(defineProps<Props>(), {
  loading: false,
  emptyText: "No hay datos para mostrar",
});

const emit = defineEmits<{
  sort: [key: string];
}>();

const handleSort = (column: Column) => {
  if (column.sortable) {
    emit("sort", column.key);
  }
};
</script>

<template>
  <div class="overflow-x-auto">
    <table class="min-w-full divide-y divide-border-subtle">
      <thead class="bg-surface-page">
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            scope="col"
            :class="[
              'px-6 py-3 text-left text-xs font-medium uppercase text-brand-slate',
              column.sortable ? 'cursor-pointer hover:bg-brand-mint' : '',
            ]"
            @click="handleSort(column)"
          >
            {{ column.label }}
          </th>
          <th
            v-if="$slots.actions"
            scope="col"
            class="px-6 py-3 text-right text-xs font-medium uppercase text-brand-slate"
          >
            Acciones
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border-subtle bg-surface-card">
        <tr v-if="loading">
          <td
            :colspan="columns.length + ($slots.actions ? 1 : 0)"
            class="px-6 py-12"
          >
            <BaseSpinner />
          </td>
        </tr>
        <tr v-else-if="data.length === 0">
          <td
            :colspan="columns.length + ($slots.actions ? 1 : 0)"
            class="px-6 py-12 text-center text-brand-slate"
          >
            {{ emptyText }}
          </td>
        </tr>
        <tr
          v-for="(row, index) in data"
          v-else
          :key="index"
          class="hover:bg-surface-page"
        >
          <td
            v-for="column in columns"
            :key="column.key"
            class="whitespace-nowrap px-6 py-4 text-sm text-brand-ink"
          >
            <slot
              :name="`cell-${column.key}`"
              :row="row"
              :value="row[column.key]"
            >
              {{ row[column.key] }}
            </slot>
          </td>
          <td
            v-if="$slots.actions"
            class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium"
          >
            <slot
              name="actions"
              :row="row"
            />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
