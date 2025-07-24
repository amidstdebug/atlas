import { ref, computed, onMounted, readonly } from 'vue'

// Note: useNuxtApp is globally available in Nuxt 3 composables

export interface BackendHealthState {
  isChecking: boolean
  isHealthy: boolean
  error: string | null
  isDashboardDisabled: boolean
}

export function useBackendHealth() {
  // Reactive state
  const isCheckingBackendHealth = ref(true)
  const backendHealthy = ref(false)
  const backendError = ref<string | null>(null)

  // Computed properties
  const isDashboardDisabled = computed(() => !backendHealthy.value)

  // Health check function
  async function checkBackendHealth() {
    isCheckingBackendHealth.value = true
    backendError.value = null

    try {
      const { $api } = useNuxtApp()
      const response = await $api.get('/health')
      
      // Backend is healthy if overall status is healthy or degraded (degraded still allows basic functionality)
      backendHealthy.value = response.data.status === 'healthy' || response.data.status === 'degraded'
      
      if (!backendHealthy.value) {
        backendError.value = `System status: ${response.data.status}`
      }
    } catch (err: any) {
      console.error('Backend health check failed:', err)
      backendHealthy.value = false
      
      if (err.response?.status === 503) {
        // Service degraded but backend is responding - allow limited functionality
        backendHealthy.value = true
        backendError.value = 'Some services are degraded'
      } else {
        backendError.value = err.response?.data?.detail || err.message || 'Backend connection failed'
      }
    } finally {
      isCheckingBackendHealth.value = false
    }
  }

  // Retry connection function
  async function retryBackendConnection() {
    await checkBackendHealth()
  }

  // Auto-check health on mount
  onMounted(async () => {
    await checkBackendHealth()
  })

  // Return reactive state and methods
  return {
    // State
    isCheckingBackendHealth: readonly(isCheckingBackendHealth),
    backendHealthy: readonly(backendHealthy),
    backendError: readonly(backendError),
    isDashboardDisabled,
    
    // Methods
    checkBackendHealth,
    retryBackendConnection
  }
} 