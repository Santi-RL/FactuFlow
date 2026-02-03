# Services - Llamadas a API

Esta carpeta contiene los servicios para comunicarse con el backend.

## Estructura

```
services/
├── api.ts           # Cliente Axios configurado
├── auth.ts          # Servicio de autenticación
├── clientes.ts      # Servicio de clientes
├── empresas.ts      # Servicio de empresas
├── comprobantes.ts  # Servicio de comprobantes
├── certificados.ts  # Servicio de certificados
└── afip.ts          # Servicio de integración AFIP
```

## Cliente API Base

```typescript
// services/api.ts
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor (agregar token)
api.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor (manejar errores)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore()
      authStore.logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
```

## Servicio Típico

```typescript
// services/clientes.ts
import api from './api'
import type { Cliente, ClienteCreate, ClienteUpdate } from '@/types'

export const clientesApi = {
  async getAll(): Promise<Cliente[]> {
    const response = await api.get('/api/v1/clientes')
    return response.data
  },

  async getById(id: number): Promise<Cliente> {
    const response = await api.get(`/api/v1/clientes/${id}`)
    return response.data
  },

  async create(data: ClienteCreate): Promise<Cliente> {
    const response = await api.post('/api/v1/clientes', data)
    return response.data
  },

  async update(id: number, data: ClienteUpdate): Promise<Cliente> {
    const response = await api.put(`/api/v1/clientes/${id}`, data)
    return response.data
  },

  async delete(id: number): Promise<void> {
    await api.delete(`/api/v1/clientes/${id}`)
  },

  async search(query: string): Promise<Cliente[]> {
    const response = await api.get(`/api/v1/clientes/search`, {
      params: { q: query }
    })
    return response.data
  },
}
```

## Manejo de Errores

```typescript
// En componente o store
try {
  await clientesApi.create(data)
} catch (error: any) {
  if (error.response) {
    // Error de la API
    const message = error.response.data.message || 'Error del servidor'
    console.error(message)
  } else if (error.request) {
    // No hubo respuesta
    console.error('Sin conexión al servidor')
  } else {
    // Error al configurar la request
    console.error('Error:', error.message)
  }
}
```

## Tipos TypeScript

```typescript
// types/index.ts
export interface Cliente {
  id: number
  nombre: string
  cuit: string
  email?: string
  condicion_iva: string
  activo: boolean
  created_at: string
}

export interface ClienteCreate {
  nombre: string
  cuit: string
  email?: string
  condicion_iva: string
}

export interface ClienteUpdate {
  nombre?: string
  email?: string
  condicion_iva?: string
  activo?: boolean
}
```
