<script setup lang="ts">
import { CheckCircle, AlertTriangle, Clock, Users, Radio, Settings, RefreshCw } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'

interface ActionItem {
  id: string
  type: 'critical' | 'warning' | 'advisory' | 'routine'
  title: string
  description: string
  priority: number
  timestamp: string
  context?: string
  completed?: boolean
}

interface Props {
  isGenerating: boolean
  actions: ActionItem[]
  autoActionsEnabled: boolean
  nextActionsCountdown: number
  formatActionContent: (content: string) => string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'completeAction', actionId: string): void
  (e: 'refreshActions'): void
  (e: 'toggleAutoActions'): void
}>()

// Action type configuration
const actionTypeConfig = {
  critical: {
    icon: AlertTriangle,
    color: 'text-red-600 dark:text-red-400',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    borderColor: 'border-red-200 dark:border-red-800',
    badgeClass: 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300'
  },
  warning: {
    icon: AlertTriangle,
    color: 'text-orange-600 dark:text-orange-400',
    bgColor: 'bg-orange-50 dark:bg-orange-900/20',
    borderColor: 'border-orange-200 dark:border-orange-800',
    badgeClass: 'bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300'
  },
  advisory: {
    icon: Clock,
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    borderColor: 'border-blue-200 dark:border-blue-800',
    badgeClass: 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
  },
  routine: {
    icon: Users,
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-900/20',
    borderColor: 'border-green-200 dark:border-green-800',
    badgeClass: 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
  }
}

// Computed properties
const sortedActions = computed(() => {
  return props.actions
    .filter(action => !action.completed)
    .sort((a, b) => {
      // Sort by priority (higher number = higher priority)
      if (a.priority !== b.priority) {
        return b.priority - a.priority
      }
      // Then by timestamp (newer first)
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    })
})

const completedActions = computed(() => {
  return props.actions.filter(action => action.completed)
})

const criticalActions = computed(() => {
  return sortedActions.value.filter(action => action.type === 'critical')
})

function formatActionTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (error) {
    return 'Invalid time'
  }
}

function formatCountdown(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

function handleCompleteAction(actionId: string) {
  emit('completeAction', actionId)
}

function handleRefreshActions() {
  emit('refreshActions')
}

function handleToggleAutoActions() {
  emit('toggleAutoActions')
}
</script>

<template>
  <Card class="h-[700px] flex flex-col border-0 shadow-xl bg-card/50 backdrop-blur-sm overflow-hidden">
    <CardHeader class="pb-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
            <CheckCircle class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <CardTitle class="text-lg">Suggested Actions</CardTitle>
            <p class="text-sm text-muted-foreground">AI-recommended operational actions</p>
          </div>
        </div>
        
        <div class="flex items-center space-x-3">
          <Button
            @click="handleRefreshActions"
            variant="ghost"
            size="sm"
            :disabled="isGenerating"
            class="text-xs"
          >
            <RefreshCw class="h-3 w-3 mr-1" :class="{ 'animate-spin': isGenerating }" />
            Refresh
          </Button>
          
          <div v-if="autoActionsEnabled" class="flex items-center space-x-1.5 px-2 py-1 rounded-md bg-muted/20 border border-border/40">
            <div class="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></div>
            <span class="text-xs text-muted-foreground">Auto</span>
            <span v-if="nextActionsCountdown > 0" class="text-xs text-muted-foreground/60">
              {{ formatCountdown(nextActionsCountdown) }}
            </span>
            <span v-else class="text-xs text-muted-foreground/60">Ready</span>
          </div>
        </div>
      </div>

      <!-- Critical Actions Alert -->
      <div v-if="criticalActions.length > 0" class="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
        <div class="flex items-center space-x-2">
          <AlertTriangle class="h-4 w-4 text-red-600 dark:text-red-400" />
          <span class="text-sm font-medium text-red-900 dark:text-red-100">
            {{ criticalActions.length }} Critical Action{{ criticalActions.length > 1 ? 's' : '' }} Required
          </span>
        </div>
      </div>
    </CardHeader>

    <CardContent class="flex-1 overflow-hidden">
      <div v-if="sortedActions.length === 0 && !isGenerating" class="h-full flex items-center justify-center">
        <div class="text-center space-y-4">
          <div class="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-emerald-100 to-green-100 dark:from-emerald-900/30 dark:to-green-900/30 flex items-center justify-center">
            <CheckCircle class="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div class="space-y-2">
            <p class="text-muted-foreground max-w-sm">
              No actions required at this time
            </p>
            <div v-if="autoActionsEnabled" class="flex items-center justify-center space-x-2 px-3 py-2 rounded-md bg-muted/30 border border-border/50">
              <div class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
              <span class="text-sm text-muted-foreground">
                <template v-if="nextActionsCountdown > 0">
                  Next check in {{ formatCountdown(nextActionsCountdown) }}
                </template>
                <template v-else>
                  Auto actions ready - monitoring for triggers
                </template>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading State -->
      <div v-else-if="isGenerating" class="h-full flex items-center justify-center">
        <div class="text-center space-y-4">
          <div class="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-emerald-100 to-green-100 dark:from-emerald-900/30 dark:to-green-900/30 flex items-center justify-center">
            <RefreshCw class="h-8 w-8 text-emerald-600 dark:text-emerald-400 animate-spin" />
          </div>
          <div class="space-y-2">
            <p class="text-muted-foreground">Analyzing situation for recommended actions...</p>
            <Progress class="h-2 rounded-full max-w-xs mx-auto" />
          </div>
        </div>
      </div>

      <!-- Actions List -->
      <div v-else class="h-full overflow-y-auto space-y-3">
        <div
          v-for="action in sortedActions"
          :key="action.id"
          :class="[
            'rounded-lg p-4 border transition-all duration-200 hover:shadow-md',
            actionTypeConfig[action.type].bgColor,
            actionTypeConfig[action.type].borderColor
          ]"
        >
          <div class="flex items-start justify-between">
            <div class="flex items-start space-x-3 flex-1">
              <component 
                :is="actionTypeConfig[action.type].icon"
                :class="['h-5 w-5 mt-0.5', actionTypeConfig[action.type].color]"
              />
              
              <div class="flex-1 space-y-2">
                <div class="flex items-center space-x-2">
                  <h4 class="font-medium text-sm">{{ action.title }}</h4>
                  <Badge 
                    variant="secondary"
                    :class="actionTypeConfig[action.type].badgeClass"
                    class="text-xs font-medium"
                  >
                    {{ action.type.toUpperCase() }}
                  </Badge>
                  <Badge variant="outline" class="text-xs font-mono">
                    P{{ action.priority }}
                  </Badge>
                </div>
                
                <div 
                  v-html="formatActionContent(action.description)"
                  class="text-sm text-muted-foreground prose prose-sm max-w-none dark:prose-invert"
                ></div>
                
                <div v-if="action.context" class="text-xs text-muted-foreground/80 italic">
                  Context: {{ action.context }}
                </div>
                
                <div class="flex items-center justify-between">
                  <span class="text-xs text-muted-foreground">
                    {{ formatActionTimestamp(action.timestamp) }}
                  </span>
                  
                  <Button
                    @click="handleCompleteAction(action.id)"
                    variant="outline"
                    size="sm"
                    class="text-xs"
                  >
                    <CheckCircle class="h-3 w-3 mr-1" />
                    Mark Complete
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Completed Actions Summary -->
        <div v-if="completedActions.length > 0" class="mt-6 pt-4 border-t border-border/50">
          <div class="flex items-center space-x-2 mb-3">
            <CheckCircle class="h-4 w-4 text-green-600 dark:text-green-400" />
            <span class="text-sm font-medium text-muted-foreground">
              {{ completedActions.length }} Completed Action{{ completedActions.length > 1 ? 's' : '' }}
            </span>
          </div>
          
          <div class="space-y-2">
            <div
              v-for="action in completedActions.slice(0, 3)"
              :key="action.id"
              class="flex items-center space-x-3 text-sm text-muted-foreground/70 bg-muted/20 rounded-md p-2"
            >
              <CheckCircle class="h-3 w-3 text-green-500" />
              <span class="flex-1">{{ action.title }}</span>
              <span class="text-xs">{{ formatActionTimestamp(action.timestamp) }}</span>
            </div>
            
            <div v-if="completedActions.length > 3" class="text-xs text-muted-foreground text-center py-1">
              +{{ completedActions.length - 3 }} more completed
            </div>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>