import { ref, computed, onMounted, readonly } from 'vue'

export interface ServiceHealth {
  status: 'healthy' | 'unhealthy' | 'degraded'
  name: string
  url: string
  response_time_ms?: number
  error?: string
  endpoint?: string
  status_code?: number
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: string
  version?: string
  services: {
    whisper: ServiceHealth
    vllm: ServiceHealth
  }
}

export const useHealthCheck = () => {
  // State
  const isChecking = ref(false)
  const healthStatus = ref<HealthStatus | null>(null)
  const error = ref<string | null>(null)
  const lastChecked = ref<Date | null>(null)

  // Computed properties
  const isHealthy = computed(() => healthStatus.value?.status === 'healthy')
  const isDegraded = computed(() => healthStatus.value?.status === 'degraded')
  const isUnhealthy = computed(() => healthStatus.value?.status === 'unhealthy' || !!error.value)
  
  // For backward compatibility with useBackendHealth
  const backendHealthy = computed(() => isHealthy.value || isDegraded.value)
  const isDashboardDisabled = computed(() => !backendHealthy.value)

  // UI Utilities
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 dark:text-green-400'
      case 'degraded':
        return 'text-yellow-600 dark:text-yellow-400'
      case 'unhealthy':
        return 'text-red-600 dark:text-red-400'
      default:
        return 'text-gray-600 dark:text-gray-400'
    }
  }

  const getStatusIcon = (status: string) => {
    // Return SVG path data instead of emojis
    switch (status) {
      case 'healthy':
        return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' // Check circle
      case 'degraded':
        return 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z' // Warning triangle
      case 'unhealthy':
        return 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z' // X circle
      default:
        return 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' // Question circle
    }
  }

  const getBadgeVariant = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'default'
      case 'degraded':
        return 'secondary'
      case 'unhealthy':
        return 'destructive'
      default:
        return 'outline'
    }
  }

  // Main health check function
  const checkHealth = async () => {
    isChecking.value = true
    error.value = null

    try {
      const { $api } = useNuxtApp()
      const response = await $api.get('/health')
      healthStatus.value = response.data
      lastChecked.value = new Date()
    } catch (err: any) {
      console.error('Health check failed:', err)
      
      if (err.response?.status === 503) {
        // Service degraded but backend is responding
        healthStatus.value = err.response.data
        lastChecked.value = new Date()
      } else {
        // Complete failure
        error.value = err.response?.data?.detail || err.message || 'Health check failed'
        healthStatus.value = null
      }
    } finally {
      isChecking.value = false
    }
  }

  // Utility functions
  const getServiceStatusText = (service: ServiceHealth) => {
    if (service.status === 'healthy') {
      const responseTime = service.response_time_ms ? Math.round(service.response_time_ms) : 0
      return `Online (${responseTime}ms)`
    } else if (service.error) {
      return service.error
    } else {
      return 'Offline'
    }
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString()
    } catch {
      return timestamp
    }
  }

  // Retry function (for backward compatibility)
  const retryConnection = async () => {
    await checkHealth()
  }

  return {
    // State
    isChecking: readonly(isChecking),
    healthStatus: readonly(healthStatus),
    error: readonly(error),
    lastChecked: readonly(lastChecked),
    
    // Computed
    isHealthy,
    isDegraded,
    isUnhealthy,
    backendHealthy,
    isDashboardDisabled,
    
    // Methods
    checkHealth,
    retryConnection,
    
    // UI Utilities
    getStatusColor,
    getStatusIcon,
    getBadgeVariant,
    getServiceStatusText,
    formatTimestamp
  }
}

// Backward compatibility export
export const useBackendHealth = useHealthCheck 