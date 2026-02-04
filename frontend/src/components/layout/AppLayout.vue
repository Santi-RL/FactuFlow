<script setup lang="ts">
import { useUIStore } from '@/stores/ui'
import Sidebar from './Sidebar.vue'
import Header from './Header.vue'
import Footer from './Footer.vue'

const uiStore = useUIStore()
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex">
    <!-- Sidebar -->
    <Sidebar />
    
    <!-- Main content area -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Header -->
      <Header />
      
      <!-- Page content -->
      <main class="flex-1 p-6 overflow-auto">
        <router-view />
      </main>
      
      <!-- Footer -->
      <Footer />
    </div>

    <!-- Notifications -->
    <div class="fixed top-4 right-4 z-50 space-y-2">
      <BaseAlert
        v-for="notification in uiStore.notifications"
        :key="notification.id"
        :type="notification.type"
        :title="notification.title"
        :message="notification.message"
        @dismiss="uiStore.hideNotification(notification.id)"
      />
    </div>
  </div>
</template>

<script lang="ts">
import BaseAlert from '@/components/ui/BaseAlert.vue'
export default {
  components: {
    BaseAlert
  }
}
</script>
