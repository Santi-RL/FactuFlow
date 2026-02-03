# Views - Páginas de la Aplicación

Esta carpeta contiene todas las páginas/vistas principales de la aplicación.

## Estructura

```
views/
├── Login.vue                # Página de login
├── Dashboard.vue            # Dashboard principal
├── Clientes.vue             # Listado de clientes
├── ClienteForm.vue          # Crear/editar cliente
├── Comprobantes.vue         # Listado de comprobantes
├── NuevaFactura.vue         # Emisión de factura
├── DetalleComprobante.vue   # Detalle de un comprobante
├── Configuracion.vue        # Configuración de empresa
├── Certificados.vue         # Gestión de certificados
└── WizardCertificados.vue   # Wizard guiado de certificados
```

## Convenciones

- Una vista por archivo
- Nombres en PascalCase
- Usar Composition API con `<script setup>`
- TypeScript preferido
- Documentar props y emits complejos

## Rutas

Las rutas se definen en `router/index.ts` y apuntan a estas vistas:

```typescript
{
  path: '/dashboard',
  name: 'Dashboard',
  component: () => import('@/views/Dashboard.vue'),
  meta: { requiresAuth: true }
}
```

## Vista Típica

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useClientesStore } from '@/stores/clientes'
import TablaClientes from '@/components/facturacion/TablaClientes.vue'

const router = useRouter()
const clientesStore = useClientesStore()

const loading = ref(true)

onMounted(async () => {
  await clientesStore.fetchClientes()
  loading.value = false
})

const irANuevoCliente = () => {
  router.push({ name: 'ClienteForm' })
}
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">Clientes</h1>
      <button @click="irANuevoCliente" class="btn-primary">
        Nuevo Cliente
      </button>
    </div>

    <TablaClientes v-if="!loading" :clientes="clientesStore.clientes" />
    <div v-else>Cargando...</div>
  </div>
</template>
```
