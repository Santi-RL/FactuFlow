# Stores - State Management con Pinia

Esta carpeta contiene los stores de Pinia para el manejo de estado global.

## Estructura

```
stores/
├── auth.ts          # Autenticación y usuario actual
├── empresa.ts       # Datos de la empresa activa
├── clientes.ts      # Lista de clientes
├── comprobantes.ts  # Comprobantes emitidos
└── certificados.ts  # Certificados ARCA
```

## Ejemplo de Store

```typescript
// stores/clientes.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Cliente } from '@/types'
import { clientesApi } from '@/services/clientes'

export const useClientesStore = defineStore('clientes', () => {
  // State
  const clientes = ref<Cliente[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const clientesActivos = computed(() => 
    clientes.value.filter(c => c.activo)
  )

  const totalClientes = computed(() => clientes.value.length)

  // Actions
  const fetchClientes = async () => {
    loading.value = true
    error.value = null
    try {
      clientes.value = await clientesApi.getAll()
    } catch (e) {
      error.value = 'Error al cargar clientes'
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  const crearCliente = async (data: ClienteCreate) => {
    const cliente = await clientesApi.create(data)
    clientes.value.push(cliente)
    return cliente
  }

  const actualizarCliente = async (id: number, data: ClienteUpdate) => {
    const cliente = await clientesApi.update(id, data)
    const index = clientes.value.findIndex(c => c.id === id)
    if (index !== -1) {
      clientes.value[index] = cliente
    }
    return cliente
  }

  const eliminarCliente = async (id: number) => {
    await clientesApi.delete(id)
    clientes.value = clientes.value.filter(c => c.id !== id)
  }

  return {
    // State
    clientes,
    loading,
    error,
    // Getters
    clientesActivos,
    totalClientes,
    // Actions
    fetchClientes,
    crearCliente,
    actualizarCliente,
    eliminarCliente,
  }
})
```

## Store de Autenticación

```typescript
// stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/services/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref(null)

  const isAuthenticated = computed(() => !!token.value)

  const login = async (username: string, password: string) => {
    const response = await authApi.login(username, password)
    token.value = response.token
    user.value = response.user
    localStorage.setItem('token', response.token)
  }

  const logout = () => {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  const checkAuth = async () => {
    if (!token.value) return false
    try {
      user.value = await authApi.me()
      return true
    } catch {
      logout()
      return false
    }
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    logout,
    checkAuth,
  }
})
```

## Persistencia

Para persistir state en localStorage:

```typescript
import { defineStore } from 'pinia'

export const useStore = defineStore('store', {
  state: () => ({
    data: []
  }),
  persist: true  // Requiere pinia-plugin-persistedstate
})
```
