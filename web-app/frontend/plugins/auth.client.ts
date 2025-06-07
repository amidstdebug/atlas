export default defineNuxtPlugin(() => {
  const authStore = useAuthStore()
  
  // Check authentication status on app startup
  authStore.checkAuth()
})