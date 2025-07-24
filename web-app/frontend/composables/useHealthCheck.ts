import { ref, computed } from 'vue'

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
  const isChecking = ref(false)
  const healthStatus = ref<HealthStatus | null>(null)
  const error = ref<string | null>(null)

  const isHealthy = computed(() => healthStatus.value?.status === 'healthy')
  const isDegraded = computed(() => healthStatus.value?.status === 'degraded')
  const isUnhealthy = computed(() => healthStatus.value?.status === 'unhealthy' || !!error.value)

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
    switch (status) {
      case 'healthy':
        return '✅'
      case 'degraded':
        return '⚠️'
      case 'unhealthy':
        return '❌'
      default:
        return '❓'
    }
  }

  const checkHealth = async () => {
    isChecking.value = true
    error.value = null

    try {
      const { $api } = useNuxtApp()
      const response = await $api.get('/health')
      healthStatus.value = response.data
    } catch (err: any) {
      console.error('Health check failed:', err)
      
      if (err.response?.status === 503) {
        // Service degraded but backend is responding
        healthStatus.value = err.response.data
      } else {
        // Complete failure
        error.value = err.response?.data?.detail || err.message || 'Health check failed'
        healthStatus.value = null
      }
    } finally {
      isChecking.value = false
    }
  }

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

  return {
    isChecking,
    healthStatus,
    error,
    isHealthy,
    isDegraded,
    isUnhealthy,
    checkHealth,
    getStatusColor,
    getStatusIcon,
    getServiceStatusText,
    formatTimestamp
  }
} 