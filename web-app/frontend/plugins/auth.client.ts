export default defineNuxtPlugin(async () => {
  const authStore = useAuthStore()
  
  // Check authentication status on app startup
  await authStore.checkAuth()
})