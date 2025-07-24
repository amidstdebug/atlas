<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { X, RefreshCw, Activity, AlertCircle } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import HealthStatus from './HealthStatus.vue'

interface Props {
  isOpen: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:isOpen': [value: boolean]
}>()

const healthStatusRef = ref<InstanceType<typeof HealthStatus> | null>(null)

function closeModal() {
  emit('update:isOpen', false)
}

function refreshHealth() {
  healthStatusRef.value?.checkHealth()
}
</script>

<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
    @click.self="closeModal"
  >
    <Card class="w-full max-w-2xl max-h-[80vh] overflow-hidden border-0 shadow-2xl bg-card/95 backdrop-blur-xl">
      <CardHeader class="pb-4 border-b border-border/50">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
              <Activity class="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <CardTitle class="text-lg">System Health Status</CardTitle>
              <p class="text-sm text-muted-foreground">Detailed system and service status information</p>
            </div>
          </div>
          <div class="flex items-center space-x-2">
            <Button variant="outline" size="sm" @click="refreshHealth">
              <RefreshCw class="h-3 w-3 mr-1" />
              Refresh
            </Button>
            <Button variant="ghost" size="icon" @click="closeModal">
              <X class="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent class="p-6 overflow-y-auto max-h-[calc(80vh-120px)]">
        <div class="space-y-6">
          <!-- Detailed Health Status -->
          <HealthStatus 
            ref="healthStatusRef"
            :show-details="true" 
            :auto-refresh="false"
          />

          <!-- Troubleshooting Info -->
          <Card class="border-border/50">
            <CardHeader class="pb-3">
              <CardTitle class="text-sm flex items-center space-x-2">
                <AlertCircle class="h-4 w-4" />
                <span>Troubleshooting</span>
              </CardTitle>
            </CardHeader>
            <CardContent class="pt-0 space-y-3">
              <div class="text-sm space-y-2">
                <div class="font-medium">If services are unhealthy:</div>
                <ul class="list-disc list-inside space-y-1 text-muted-foreground ml-2">
                  <li>Check if Docker containers are running</li>
                  <li>Verify service URLs in environment configuration</li>
                  <li>Check container logs for error messages</li>
                  <li>Ensure sufficient system resources (RAM, GPU)</li>
                </ul>
              </div>
              
              <div class="text-sm space-y-2">
                <div class="font-medium">Common issues:</div>
                <ul class="list-disc list-inside space-y-1 text-muted-foreground ml-2">
                  <li><strong>Whisper Service:</strong> Audio processing may be unavailable</li>
                  <li><strong>vLLM Service:</strong> AI analysis and summaries may not work</li>
                  <li><strong>High Response Times:</strong> System may be under heavy load</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </CardContent>
    </Card>
  </div>
</template> 