import apiClient from './api'
import type { LoginCredentials, LoginResponse, Usuario, SetupData } from '@/types/auth'

export const authService = {
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>('/api/auth/login', credentials)
    return response.data
  },

  async logout(): Promise<void> {
    // Limpiar el storage local
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  },

  async me(): Promise<Usuario> {
    const response = await apiClient.get<Usuario>('/api/auth/me')
    return response.data
  },

  async setup(data: SetupData): Promise<Usuario> {
    const response = await apiClient.post<Usuario>('/api/auth/setup', data)
    return response.data
  },

  async checkSetupRequired(): Promise<boolean> {
    try {
      // Intentar hacer una petición al endpoint de setup
      // Si devuelve error 400, significa que ya hay usuarios
      await apiClient.post('/api/auth/setup', {
        email: 'test@test.com',
        password: 'test',
        nombre: 'test'
      })
      return true
    } catch (error: any) {
      // Si el error es 400 y el mensaje indica que ya existe un usuario, no se requiere setup
      if (error.response?.status === 400) {
        return false
      }
      // Para cualquier otro error, asumir que no se requiere setup
      return false
    }
  }
}
