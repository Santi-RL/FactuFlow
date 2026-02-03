# Assets - Archivos Estáticos

Esta carpeta contiene assets estáticos como imágenes, fuentes e iconos.

## Estructura

```
assets/
├── styles/
│   ├── main.css         # Estilos globales y Tailwind
│   └── variables.css    # Variables CSS custom
├── images/
│   ├── logo.svg         # Logo de FactuFlow
│   ├── logo-white.svg   # Logo blanco (para fondos oscuros)
│   └── placeholder.png  # Placeholders
└── fonts/
    └── README.md        # Si se usan fuentes custom
```

## Estilos Globales

```css
/* assets/styles/main.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Estilos base */
@layer base {
  body {
    @apply bg-gray-50 text-gray-900;
  }
  
  h1 {
    @apply text-3xl font-bold mb-4;
  }
  
  h2 {
    @apply text-2xl font-semibold mb-3;
  }
}

/* Componentes reutilizables */
@layer components {
  .btn-primary {
    @apply px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition;
  }
  
  .btn-secondary {
    @apply px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition;
  }
  
  .card {
    @apply bg-white rounded-lg shadow-md p-6;
  }
  
  .input {
    @apply w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent;
  }
}
```

## Importar Assets

```vue
<script setup lang="ts">
import logoUrl from '@/assets/images/logo.svg'
</script>

<template>
  <img :src="logoUrl" alt="FactuFlow" />
</template>
```

O directamente en template:

```vue
<template>
  <img src="@/assets/images/logo.svg" alt="FactuFlow" />
</template>
```

## Iconos

Se recomienda usar **@heroicons/vue** en lugar de archivos SVG:

```bash
npm install @heroicons/vue
```

```vue
<script setup lang="ts">
import { UserIcon, DocumentTextIcon } from '@heroicons/vue/24/outline'
</script>

<template>
  <UserIcon class="w-6 h-6 text-gray-600" />
  <DocumentTextIcon class="w-5 h-5 text-blue-500" />
</template>
```
