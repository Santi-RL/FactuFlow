import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Usuario, LoginCredentials, SetupData } from '@/types/auth'
import { authService } from '@/services/auth.service'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<Usuario | null>(null)
  const token = ref<string | null>(null)
  const isAuthenticated = ref(false)
  const loading = ref(false)

  // Inicializar desde localStorage
  const init = () => {
    const storedToken = localStorage.getItem('token')
    const storedUser = localStorage.getItem('user')

    if (storedToken && storedUser) {
      token.value = storedToken
      user.value = JSON.parse(storedUser)
      isAuthenticated.value = true
    }
  }

  const login = async (credentials: LoginCredentials) => {
    loading.value = true
    try {
      const response = await authService.login(credentials)
      
      token.value = response.access_token
      user.value = response.user
      isAuthenticated.value = true

      // Guardar en localStorage
      localStorage.setItem('token', response.access_token)
      localStorage.setItem('user', JSON.stringify(response.user))

      return response
    } finally {
      loading.value = false
    }
  }

  const logout = async () => {
    await authService.logout()
    
    token.value = null
    user.value = null
    isAuthenticated.value = false
  }

  const checkAuth = async () => {
    if (!token.value) return false

    try {
      const userData = await authService.me()
      user.value = userData
      isAuthenticated.value = true
      
      // Actualizar en localStorage
      localStorage.setItem('user', JSON.stringify(userData))
      
      return true
    } catch (error) {
      await logout()
      return false
    }
  }

  const setup = async (data: SetupData) => {
    loading.value = true
    try {
      const newUser = await authService.setup(data)
      return newUser
    } finally {
      loading.value = false
    }
  }

  return {
    user,
    token,
    isAuthenticated,
    loading,
    init,
    login,
    logout,
    checkAuth,
    setup
  }
})
