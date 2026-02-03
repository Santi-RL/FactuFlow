import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  duration?: number
}

export const useUIStore = defineStore('ui', () => {
  const loading = ref(false)
  const sidebarOpen = ref(true)
  const notifications = ref<Notification[]>([])

  const showNotification = (notification: Omit<Notification, 'id'>) => {
    const id = Date.now().toString()
    const newNotification: Notification = {
      id,
      duration: 5000,
      ...notification
    }
    
    notifications.value.push(newNotification)

    // Auto-remove después del duration
    if (newNotification.duration) {
      setTimeout(() => {
        hideNotification(id)
      }, newNotification.duration)
    }

    return id
  }

  const hideNotification = (id: string) => {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }

  const toggleSidebar = () => {
    sidebarOpen.value = !sidebarOpen.value
  }

  const setLoading = (value: boolean) => {
    loading.value = value
  }

  return {
    loading,
    sidebarOpen,
    notifications,
    showNotification,
    hideNotification,
    toggleSidebar,
    setLoading
  }
})
