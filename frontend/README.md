# FactuFlow Frontend

Frontend moderno desarrollado con Vue.js 3, TypeScript y Tailwind CSS para el sistema de facturación electrónica FactuFlow.

## 🚀 Stack Tecnológico

- **Vue.js 3.4+** - Framework reactivo con Composition API
- **TypeScript 5.3+** - Tipado estático
- **Vite 5.x** - Build tool ultra-rápido
- **Tailwind CSS 3.4+** - Utility-first CSS
- **Vue Router 4.x** - Enrutamiento SPA
- **Pinia 2.x** - State management
- **Axios 1.x** - Cliente HTTP
- **Hero Icons 2.x** - Iconos SVG

## 📦 Instalación

```bash
# Instalar dependencias
npm install

# Copiar variables de entorno
cp .env.example .env

# Editar .env con la URL del backend
# VITE_API_URL=http://localhost:8000
```

## 🛠️ Desarrollo

```bash
# Iniciar servidor de desarrollo
npm run dev

# El frontend estará disponible en http://localhost:8080
```

## 🏗️ Build para Producción

```bash
# Compilar para producción
npm run build

# Los archivos compilados estarán en dist/

# Preview del build
npm run preview
```

## 🐳 Docker

```bash
# Build de la imagen
docker build -t factuflow-frontend .

# Ejecutar contenedor
docker run -p 80:80 factuflow-frontend

# Con docker-compose (desde la raíz del proyecto)
docker-compose up frontend
```

## 📁 Estructura del Proyecto

```
frontend/
├── src/
│   ├── assets/              # Assets estáticos (CSS, imágenes)
│   │   └── styles/
│   │       └── main.css     # Tailwind imports + utilities
│   ├── components/          # Componentes reutilizables
│   │   ├── common/          # Componentes comunes (Pagination, ConfirmDialog)
│   │   ├── layout/          # Layout principal (AppLayout, Sidebar, Header)
│   │   └── ui/              # Componentes UI base (Button, Input, Modal, etc.)
│   ├── composables/         # Composables de Vue (useAuth, useNotification)
│   ├── router/              # Configuración de rutas
│   ├── services/            # Servicios de API
│   ├── stores/              # Stores de Pinia
│   ├── types/               # Tipos TypeScript
│   ├── views/               # Páginas/Vistas
│   │   ├── auth/            # Login, Setup
│   │   ├── dashboard/       # Dashboard
│   │   ├── clientes/        # CRUD de clientes
│   │   ├── empresa/         # Configuración de empresa
│   │   └── comprobantes/    # Gestión de comprobantes
│   ├── App.vue              # Componente raíz
│   └── main.ts              # Entry point
├── index.html               # HTML base
├── vite.config.ts           # Configuración de Vite
├── tailwind.config.js       # Configuración de Tailwind
├── tsconfig.json            # Configuración de TypeScript
├── nginx.conf               # Configuración de Nginx (producción)
└── Dockerfile               # Multi-stage build
```

## 🎨 Componentes UI Base

### Botones
```vue
<BaseButton variant="primary" size="md" :loading="false">
  Guardar
</BaseButton>
```

Variantes: `primary`, `secondary`, `danger`, `ghost`
Tamaños: `sm`, `md`, `lg`

### Inputs
```vue
<BaseInput
  v-model="email"
  type="email"
  label="Correo electrónico"
  placeholder="usuario@ejemplo.com"
  :error="errorMessage"
  required
/>
```

### Select
```vue
<BaseSelect
  v-model="selected"
  label="Provincia"
  :options="provincias"
  required
/>
```

### Modal
```vue
<BaseModal :show="showModal" title="Título" size="md" @close="showModal = false">
  <p>Contenido del modal</p>
  
  <template #footer>
    <BaseButton @click="showModal = false">Cerrar</BaseButton>
  </template>
</BaseModal>
```

### Tabla
```vue
<BaseTable
  :columns="columns"
  :data="items"
  :loading="loading"
>
  <template #cell-nombre="{ value }">
    <strong>{{ value }}</strong>
  </template>
  
  <template #actions="{ row }">
    <button @click="edit(row)">Editar</button>
  </template>
</BaseTable>
```

### Alertas
```vue
<BaseAlert
  type="success"
  title="Éxito"
  message="Operación completada"
  @dismiss="closeAlert"
/>
```

Tipos: `success`, `error`, `warning`, `info`

## 🔌 Servicios de API

Todos los servicios están en `src/services/`:

```typescript
// Autenticación
import { authService } from '@/services/auth.service'

await authService.login({ email, password })
await authService.logout()
const user = await authService.me()

// Clientes
import { clientesService } from '@/services/clientes.service'

const clientes = await clientesService.getAll({ page: 1, per_page: 30 })
const cliente = await clientesService.getById(1)
await clientesService.create(data)
await clientesService.update(1, data)
await clientesService.delete(1)
```

## 🗃️ Stores (Pinia)

```vue
<script setup>
import { useAuthStore } from '@/stores/auth'
import { useClientesStore } from '@/stores/clientes'

const authStore = useAuthStore()
const clientesStore = useClientesStore()

// Usar el store
authStore.login({ email, password })
await clientesStore.fetchClientes()
</script>
```

## 🛣️ Rutas

### Rutas Públicas (Guest)
- `/login` - Iniciar sesión
- `/setup` - Configuración inicial

### Rutas Protegidas (Requieren autenticación)
- `/` - Dashboard
- `/clientes` - Listado de clientes
- `/clientes/nuevo` - Crear cliente
- `/clientes/:id` - Ver cliente
- `/clientes/:id/editar` - Editar cliente
- `/empresa` - Configuración de empresa
- `/comprobantes` - Gestión de comprobantes

## 🔐 Autenticación

El sistema usa JWT tokens almacenados en `localStorage`:

```typescript
// Login automático si hay token
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
authStore.init() // Carga token de localStorage

// El router redirige automáticamente según estado de auth
```

## 🎯 Composables

### useAuth
```vue
<script setup>
import { useAuth } from '@/composables/useAuth'

const { user, isAuthenticated, login, logout } = useAuth()
</script>
```

### useNotification
```vue
<script setup>
import { useNotification } from '@/composables/useNotification'

const { showSuccess, showError, showWarning, showInfo } = useNotification()

showSuccess('Cliente guardado', 'El cliente se guardó correctamente')
showError('Error', 'No se pudo guardar el cliente')
</script>
```

## 🌍 Idioma

**Todo el sistema está en español**:
- Labels y textos de UI
- Mensajes de error
- Placeholders
- Títulos y descripciones

Fechas visibles:
- Mostrar fechas para usuarios en formato argentino `DD/MM/AAAA`.
- Aceptar `DD/MM/AAAA` cuando una fecha llegue como texto visible o importado por usuario.
- Mantener `YYYY-MM-DD`, ISO datetime o `CbteFch` `YYYYMMDD` solo como formatos técnicos de API/backend/ARCA.
- No usar `new Date(string)` ni `Date.parse` como parser general de strings de usuario; validar formato y calendario explícitamente.

## 📱 Responsive

El diseño es responsive con breakpoints de Tailwind:
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

El sidebar se colapsa automáticamente en mobile.

## 🎨 Personalización de Colores

En `tailwind.config.js`:

```javascript
colors: {
  primary: { /* Azul */ },
  celeste: '#74acdf',  // Color ARCA
  sol: '#f6b40e'       // Color argentino
}
```

## 🧪 Testing

```bash
# Tests unitarios
npm run test:unit

# E2E local en Chromium desktop
npm run test:e2e

# Type checking
npm run type-check

# Lint no destructivo
npm run lint
npm run lint:check

# Autocorrección de lint
npm run lint:fix
```

`npm run test:e2e` usa un servidor Vite dedicado en `127.0.0.1:18080` y lo
cierra al terminar. Si el puerto está ocupado, detener ese proceso o configurar
`E2E_PORT`. Para ejecutar la matriz completa de navegadores y mobile, usar
`$env:E2E_FULL_BROWSER_MATRIX='1'; npm run test:e2e` en PowerShell o
`E2E_FULL_BROWSER_MATRIX=1 npm run test:e2e` en bash.

## 📝 Convenciones de Código

- Componentes en PascalCase: `BaseButton.vue`, `ClienteForm.vue`
- Props en camelCase: `modelValue`, `showModal`
- Events en kebab-case: `@update:modelValue`, `@cliente-guardado`
- Usar Composition API con `<script setup>`
- TypeScript para type safety
- Tailwind CSS para estilos (evitar CSS custom cuando sea posible)

## 🔧 Configuración del Backend

El frontend se conecta al backend mediante la variable de entorno:

```bash
VITE_API_URL=http://localhost:8000
```

En producción, nginx hace proxy reverso a `/api`.

## 📄 Licencia

Ver LICENSE en la raíz del proyecto.

## 👥 Contribuir

Ver CONTRIBUTING.md en la raíz del proyecto.
