import { defineStore } from "pinia";
import { ref } from "vue";

export interface Notification {
  id: string;
  type: "success" | "error" | "warning" | "info";
  title: string;
  message?: string;
  duration?: number;
}

const DEFAULT_NOTIFICATION_DURATION = 5000;

export const useUIStore = defineStore("ui", () => {
  const loading = ref(false);
  const sidebarOpen = ref(true);
  const notifications = ref<Notification[]>([]);

  const showNotification = (notification: Omit<Notification, "id">) => {
    const id = Date.now().toString();
    const duration =
      notification.duration ?? DEFAULT_NOTIFICATION_DURATION;
    const newNotification: Notification = {
      id,
      ...notification,
      duration,
    };

    notifications.value.push(newNotification);

    // `duration: 0` deja el aviso visible hasta que el usuario lo cierre.
    if (duration > 0) {
      setTimeout(() => {
        hideNotification(id);
      }, duration);
    }

    return id;
  };

  const hideNotification = (id: string) => {
    notifications.value = notifications.value.filter((n) => n.id !== id);
  };

  const toggleSidebar = () => {
    sidebarOpen.value = !sidebarOpen.value;
  };

  const setLoading = (value: boolean) => {
    loading.value = value;
  };

  return {
    loading,
    sidebarOpen,
    notifications,
    showNotification,
    hideNotification,
    toggleSidebar,
    setLoading,
  };
});
