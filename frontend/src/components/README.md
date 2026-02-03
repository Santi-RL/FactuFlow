# Componentes Vue Reutilizables

Esta carpeta contiene todos los componentes reutilizables de la aplicación.

## Estructura

```
components/
├── layout/               # Componentes de layout
│   ├── Sidebar.vue
│   ├── Header.vue
│   └── Footer.vue
├── ui/                   # Componentes base de UI
│   ├── Button.vue
│   ├── Input.vue
│   ├── Select.vue
│   ├── Modal.vue
│   ├── Table.vue
│   ├── Card.vue
│   ├── Alert.vue
│   └── Badge.vue
└── facturacion/          # Componentes específicos del dominio
    ├── FormCliente.vue
    ├── FormFactura.vue
    ├── TablaComprobantes.vue
    └── VistaPrevia.vue
```

## Convenciones

### Nombrado
- Archivos en PascalCase: `BotonPrimario.vue`
- Props en camelCase: `nombreCliente`
- Events en kebab-case: `@cliente-guardado`

### Estructura de Componente

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'

// Props
interface Props {
  titulo: string
  mostrarIcono?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  mostrarIcono: true
})

// Emits
const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

// State local
const activo = ref(false)

// Computed
const clases = computed(() => ({
  'activo': activo.value
}))

// Methods
const handleClick = (event: MouseEvent) => {
  activo.value = !activo.value
  emit('click', event)
}
</script>

<template>
  <div :class="clases" @click="handleClick">
    {{ titulo }}
  </div>
</template>

<style scoped>
/* Preferir Tailwind, usar CSS solo si es necesario */
</style>
```

## Componentes Base (UI)

### Button
Variantes: primary, secondary, danger, ghost
Tamaños: sm, md, lg
Estados: loading, disabled

### Input
Tipos: text, number, email, password, textarea
Features: label, placeholder, error message, validación

### Modal
Tamaños: sm, md, lg, xl
Features: overlay, close button, footer actions

### Table
Features: sorting, paginación, acciones por fila, loading state
