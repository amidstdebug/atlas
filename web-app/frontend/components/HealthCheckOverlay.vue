<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-vue-next'
import HealthStatus from '@/components/HealthStatus.vue'

interface Props {
  isChecking: boolean
  isHealthy: boolean
  error: string | null
}

defineProps<Props>()

const emit = defineEmits<{
  retry: []
}>()

function handleRetry() {
  emit('retry')
}
</script>

<template>
  <div 
    v-if="isChecking || !isHealthy" 
    class="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center"
  >
    <div class="text-center space-y-6 max-w-lg min-w-sm mx-auto p-6">
      <!-- Loading State -->
      <div v-if="isChecking" class="space-y-4">
        <div class="w-16 h-16 mx-auto rounded-full border-4 border-blue-500 border-t-transparent animate-spin"></div>
        <div>
          <h2 class="text-xl font-semibold text-foreground">Checking System Status</h2>
          <p class="text-muted-foreground mt-2">Verifying backend services availability...</p>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="!isHealthy" class="space-y-4">
        <div class="w-16 h-16 mx-auto rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
          <svg class="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 14.5c-.77.833.192 2.5 1.732 2.5z"></path>
          </svg>
        </div>
        <div>
          <h2 class="text-xl font-semibold text-foreground">System Unavailable</h2>
        </div>
        
        <!-- Detailed Health Status -->
        <div class="mt-6">
          <HealthStatus :show-details="true" :auto-refresh="false" />
        </div>

        <!-- Retry Button -->
        <div class="flex flex-col space-y-3 mt-6">
          <Button @click="handleRetry" :disabled="isChecking" class="w-full">
            <RefreshCw :class="['w-4 h-4 mr-2', { 'animate-spin': isChecking }]" />
            {{ isChecking ? 'Checking...' : 'Retry Connection' }}
          </Button>
        </div>
        
        <!-- Troubleshooting Info -->
        <div class="mt-8 p-4 rounded-lg bg-muted/50 text-left">
          <h3 class="text-sm font-medium text-foreground mb-2">Troubleshooting</h3>
          <ul class="text-xs text-muted-foreground space-y-1">
            <li>• Check if Docker containers are running</li>
            <li>• Verify backend service is accessible</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template> 