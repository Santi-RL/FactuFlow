import { useUIStore } from '@/stores/ui'
import type { Notification } from '@/stores/ui'

export function useNotification() {
  const uiStore = useUIStore()

  const showSuccess = (title: string, message?: string, duration?: number) => {
    return uiStore.showNotification({
      type: 'success',
      title,
      message,
      duration
    })
  }

  const showError = (title: string, message?: string, duration?: number) => {
    return uiStore.showNotification({
      type: 'error',
      title,
      message,
      duration
    })
  }

  const showWarning = (title: string, message?: string, duration?: number) => {
    return uiStore.showNotification({
      type: 'warning',
      title,
      message,
      duration
    })
  }

  const showInfo = (title: string, message?: string, duration?: number) => {
    return uiStore.showNotification({
      type: 'info',
      title,
      message,
      duration
    })
  }

  const show = (notification: Omit<Notification, 'id'>) => {
    return uiStore.showNotification(notification)
  }

  const hide = (id: string) => {
    uiStore.hideNotification(id)
  }

  return {
    showSuccess,
    showError,
    showWarning,
    showInfo,
    show,
    hide
  }
}
