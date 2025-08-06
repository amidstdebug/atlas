<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useHealthCheck } from '~/composables/useHealthCheck'

interface ServiceHealth {
  status: 'healthy' | 'unhealthy' | 'degraded'
  name: string
  url: string
  response_time_ms?: number
  error?: string
  endpoint?: string
  status_code?: number
}

interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: string
  version?: string
  services: {
    whisper: ServiceHealth
    vllm: ServiceHealth
  }
}

interface Props {
  showDetails?: boolean
  autoRefresh?: boolean
  refreshInterval?: number
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showDetails: false,
  autoRefresh: false,
  refreshInterval: 30000, // 30 seconds
  compact: false
})

const {
  isChecking,
  healthStatus,
  error,
  lastChecked,
  isHealthy,
  isDegraded,
  isUnhealthy,
  checkHealth,
  getStatusColor,
  getStatusIcon,
  getBadgeVariant,
  getServiceStatusText,
  formatTimestamp
} = useHealthCheck()

let refreshInterval: any = null

onMounted(async () => {
  await checkHealth()
  
  if (props.autoRefresh) {
    refreshInterval = setInterval(checkHealth, props.refreshInterval)
  }
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

defineExpose({
  checkHealth,
  isHealthy,
  isDegraded,
  isUnhealthy
})
</script>

<template>
  <!-- Compact Mode -->
  <div v-if="compact" class="flex items-center space-x-2 px-3 py-2 rounded-lg bg-background border border-border/50 hover:bg-muted/50 transition-colors">
    <svg 
      class="h-4 w-4 flex-shrink-0"
      :class="getStatusColor(error ? 'unhealthy' : healthStatus?.status || 'unhealthy').split(' ')[0]"
      fill="none" 
      stroke="currentColor" 
      viewBox="0 0 24 24"
    >
      <path 
        stroke-linecap="round" 
        stroke-linejoin="round" 
        stroke-width="2" 
        :d="getStatusIcon(error ? 'unhealthy' : healthStatus?.status || 'unhealthy')"
      />
    </svg>
    <div class="flex items-center space-x-2 min-w-0">
      <span class="text-sm font-medium text-foreground truncate">
        {{ error ? 'Error' : 
           healthStatus?.status === 'healthy' ? 'All Systems' :
           healthStatus?.status === 'degraded' ? 'Degraded' :
           healthStatus?.status === 'unhealthy' ? 'Issues' : 'Unknown' }}
      </span>
      <Badge 
        :variant="getBadgeVariant(error ? 'unhealthy' : healthStatus?.status || 'unhealthy')"
        class="text-xs flex-shrink-0"
      >
        {{ error ? 'ERR' : 
           healthStatus?.status === 'healthy' ? 'OK' :
           healthStatus?.status === 'degraded' ? 'DEG' :
           healthStatus?.status === 'unhealthy' ? 'DOWN' : '?' }}
      </Badge>
    </div>
  </div>

  <!-- Full Mode -->
  <Card v-else class="border-0 shadow-sm">
    <CardHeader>
      <div class="flex items-center justify-between">
        <CardTitle class="text-sm font-medium flex items-center space-x-2">
          <svg 
            class="h-4 w-4"
            :class="getStatusColor(error ? 'unhealthy' : healthStatus?.status || 'unhealthy').split(' ')[0]"
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              stroke-linecap="round" 
              stroke-linejoin="round" 
              stroke-width="2" 
              :d="getStatusIcon(error ? 'unhealthy' : healthStatus?.status || 'unhealthy')"
            />
          </svg>
          <span>System Status</span>
        </CardTitle>
        <div class="flex items-center space-x-2">
          <Badge 
            :variant="getBadgeVariant(error ? 'unhealthy' : healthStatus?.status || 'unhealthy')"
            class="text-xs"
          >
            {{ error ? 'Error' : healthStatus?.status?.toUpperCase() || 'UNKNOWN' }}
          </Badge>
          <Button 
            variant="ghost" 
            size="sm" 
            @click="checkHealth"
            :disabled="isChecking"
            class="h-7 w-7 p-0"
          >
            <RefreshCw :class="['h-3 w-3', { 'animate-spin': isChecking }]" />
          </Button>
        </div>
      </div>
    </CardHeader>

    <CardContent class="pt-0">
      <!-- Error State -->
      <div v-if="error" class="p-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800">
        <div class="flex items-start space-x-2">
          <XCircle class="h-4 w-4 text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
          <div class="text-sm text-red-800 dark:text-red-200">
            <div class="font-medium">Connection Failed</div>
            <div class="text-xs mt-1 opacity-75">{{ error }}</div>
          </div>
        </div>
      </div>

      <!-- Success State -->
      <div v-else-if="healthStatus" class="space-y-3">
        <!-- Overall Status -->
        <div 
          class="p-3 rounded-lg border"
          :class="getStatusColor(healthStatus.status)"
        >
          <div class="flex items-center justify-between">
            <div class="text-sm font-medium">
              {{ healthStatus.status === 'healthy' ? 'All Systems Operational' : 
                 healthStatus.status === 'degraded' ? 'Some Services Degraded' : 
                 'System Issues Detected' }}
            </div>
            <div class="text-xs opacity-75 flex items-center space-x-1">
              <Clock class="h-3 w-3" />
              <span>{{ lastChecked ? lastChecked.toLocaleTimeString() : 'Never' }}</span>
            </div>
          </div>
        </div>

        <!-- Service Details -->
        <div v-if="showDetails" class="grid grid-cols-1 gap-3">
          <div 
            v-for="[key, service] in Object.entries(healthStatus.services)" 
            :key="key"
            class="p-3 rounded-lg border border-border/50 bg-muted/20"
          >
            <div class="flex items-center justify-between mb-1">
              <div class="text-sm font-medium">{{ service.name }}</div>
              <Badge 
                :variant="getBadgeVariant(service.status)"
                class="text-xs"
              >
                {{ service.status.toUpperCase() }}
              </Badge>
            </div>
            <div class="text-xs text-muted-foreground">
              {{ getServiceStatusText(service) }}
            </div>
            <div v-if="service.url" class="text-xs text-muted-foreground mt-1 opacity-60">
              {{ service.url }}{{ service.endpoint || '' }}
            </div>
          </div>
        </div>

        <!-- Version Info -->
        <div v-if="healthStatus.version && showDetails" class="text-xs text-muted-foreground text-center">
          API Version {{ healthStatus.version }}
        </div>
      </div>

      <!-- Loading State -->
      <div v-else-if="isChecking" class="flex items-center justify-center py-4">
        <RefreshCw class="h-4 w-4 animate-spin text-muted-foreground" />
        <span class="ml-2 text-sm text-muted-foreground">Checking system status...</span>
      </div>
    </CardContent>
  </Card>
</template> 