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
    <Card class="w-full max-w-2xl overflow-hidden border-0 shadow-2xl bg-card/95 backdrop-blur-xl">
      <CardHeader class="border-b border-border/50">
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

      <CardContent class="overflow-y-auto max-h-[calc(80vh-120px)]">
        <div class="space-y-6">
          <!-- Detailed Health Status -->
          <HealthStatus 
            ref="healthStatusRef"
            :show-details="true" 
            :auto-refresh="false"
          />
        </div>
      </CardContent>
    </Card>
  </div>
</template> 