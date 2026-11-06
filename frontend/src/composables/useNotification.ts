import { useUIStore } from "@/stores/ui";

export function useNotification() {
  const uiStore = useUIStore();

  const showSuccess = (title: string, message?: string, duration?: number) => {
    return uiStore.showNotification({
      type: "success",
      title,
      message,
      duration,
    });
  };

  const showError = (title: string, message?: string, duration?: number) => {
    return uiStore.showNotification({
      type: "error",
      title,
      message,
      duration,
    });
  };

  const showWarning = (title: string, message?: string, duration?: number) => {
    return uiStore.showNotification({
      type: "warning",
      title,
      message,
      duration,
    });
  };

  const showInfo = (title: string, message?: string, duration?: number) => {
    return uiStore.showNotification({
      type: "info",
      title,
      message,
      duration,
    });
  };

  return {
    showSuccess,
    showError,
    showWarning,
    showInfo,
  };
}
