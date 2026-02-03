import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

export function useAuth() {
  const authStore = useAuthStore()
  const router = useRouter()

  const user = computed(() => authStore.user)
  const isAuthenticated = computed(() => authStore.isAuthenticated)
  const loading = computed(() => authStore.loading)

  const login = async (email: string, password: string) => {
    try {
      await authStore.login({ email, password })
      router.push('/')
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Error al iniciar sesión')
    }
  }

  const logout = async () => {
    await authStore.logout()
    router.push('/login')
  }

  return {
    user,
    isAuthenticated,
    loading,
    login,
    logout
  }
}
