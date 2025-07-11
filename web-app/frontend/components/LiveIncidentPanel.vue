<script setup lang="ts">
import { Sparkles, Clock, AlertTriangle, Users, AlertOctagon, Activity, Eye } from 'lucide-vue-next'
import { ref, computed, watch } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'

interface Summary {
  id: string
  summary: string
  timestamp: string
  structured_summary?: {
    [key: string]: {
      content: string,
      latest_timestamp: number
    }
  }
}

interface KanbanColumn {
  title: string;
  icon: any;
  color: string;
  items: any[];
}

interface KanbanColumns {
  [key: string]: KanbanColumn;
}

interface Props {
  summaries: Summary[]
  isGenerating: boolean
  autoReportEnabled: boolean
  formatSummaryContent: (content: string) => string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'forceAnalysis'): void
  (e: 'toggleAutoMode'): void
}>()

// --- Alert Management ---

// --- Kanban Data Transformation ---
const kanbanColumns = computed(() => {
  const columns: KanbanColumns = {
    pending_information: { title: 'Pending Information', icon: Clock, color: 'blue', items: [] },
    emergency_information: { title: 'Emergency', icon: AlertOctagon, color: 'red', items: [] },
  }

  props.summaries.forEach(summary => {
    if (summary.structured_summary) {
      // Handle pending information
      if (summary.structured_summary.pending_information) {
        summary.structured_summary.pending_information.forEach((item: any, index: number) => {
          columns.pending_information.items.push({
            id: `${summary.id}-pending-${index}`,
            content: item.description,
            eta_etr_info: item.eta_etr_info,
            calculated_time: item.calculated_time,
            priority: item.priority,
            timestamps: item.timestamps,
            latest_timestamp: item.timestamps?.[0]?.end || 0
          })
        })
      }

      // Handle emergency information
      if (summary.structured_summary.emergency_information) {
        summary.structured_summary.emergency_information.forEach((item: any, index: number) => {
          columns.emergency_information.items.push({
            id: `${summary.id}-emergency-${index}`,
            content: item.description,
            category: item.category,
            severity: item.severity,
            immediate_action_required: item.immediate_action_required,
            timestamps: item.timestamps,
            latest_timestamp: item.timestamps?.[0]?.end || 0
          })
        })
      }
    }
  })

  // Sort items by latest timestamp (newest first)
  for (const key in columns) {
    columns[key].items.sort((a, b) => (b.latest_timestamp || 0) - (a.latest_timestamp || 0))
  }

  return Object.values(columns)
})

// --- Component Logic ---
const isAutoMode = ref(props.autoReportEnabled)
watch(() => props.autoReportEnabled, (newVal) => {
  isAutoMode.value = newVal
})


function formatTimestampBadge(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

function getPriorityColor(priority: string): string {
  switch (priority) {
    case 'high': return 'text-red-600 bg-red-50 border-red-200'
    case 'medium': return 'text-orange-600 bg-orange-50 border-orange-200'
    case 'low': return 'text-blue-600 bg-blue-50 border-blue-200'
    default: return 'text-gray-600 bg-gray-50 border-gray-200'
  }
}

function getCategoryColor(category: string): string {
  switch (category) {
    case 'MAYDAY_PAN': return 'text-red-700 bg-red-100 border-red-300'
    case 'CASEVAC': return 'text-purple-700 bg-purple-100 border-purple-300'
    case 'AIRCRAFT_DIVERSION': return 'text-orange-700 bg-orange-100 border-orange-300'
    case 'OTHERS': return 'text-gray-700 bg-gray-100 border-gray-300'
    default: return 'text-red-700 bg-red-100 border-red-300'
  }
}

function handleToggleAutoMode() {
  isAutoMode.value = !isAutoMode.value
  emit('toggleAutoMode')
}


</script>

<template>
  <Card class="h-full flex flex-col border-0 shadow-none bg-background">
    <CardHeader class="space-y-4">
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-3">
          <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
            <Sparkles class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <CardTitle class="text-lg">Live Situation Report</CardTitle>
            <p class="text-sm text-muted-foreground">Real-time AI-powered analysis</p>
          </div>
        </div>
        <div class="flex items-center space-x-3">
          <Button
            v-if="!isAutoMode"
            @click="emit('forceAnalysis')"
            :disabled="isGenerating"
            variant="outline"
            size="sm"
            class="text-xs"
          >
            <Sparkles class="h-3 w-3 mr-1" />
            {{ isGenerating ? 'Analyzing...' : 'Generate Analysis' }}
          </Button>
          <div v-else class="flex items-center space-x-2 px-2 py-1.5 rounded-md bg-muted/20 border border-border/40">
            <div class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
            <span class="text-xs text-muted-foreground">Auto-Analyzing</span>
          </div>
        </div>
      </div>
       <div class="flex items-center justify-between border-t border-border pt-3">
         <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <Eye class="h-4 w-4 text-muted-foreground" />
            <span class="text-xs font-medium text-muted-foreground">Auto-Report</span>
            <Switch
              id="auto-mode-switch"
              :checked="isAutoMode"
              @update:checked="handleToggleAutoMode"
            />
          </div>
         </div>
       </div>
    </CardHeader>

    <CardContent class="flex-1 overflow-hidden p-0 border-t">
       <div v-if="summaries.length === 0" class="h-full flex items-center justify-center p-8">
        <div class="text-center space-y-4">
          <div class="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900/30 dark:to-purple-900/30 flex items-center justify-center">
            <Sparkles class="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div class="space-y-2">
            <p class="text-muted-foreground max-w-sm">
              AI analysis will appear here as audio is processed.
            </p>
            <div v-if="isAutoMode" class="flex items-center justify-center space-x-2 px-3 py-2 rounded-md bg-muted/30 border border-border/50">
              <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span class="text-sm text-muted-foreground">
                Auto-report enabled. Waiting for finalized segment.
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Kanban-style columns -->
      <div v-else class="h-full grid grid-cols-2 gap-0">
        <div v-for="column in kanbanColumns" :key="column.title" class="border-r border-border h-full flex flex-col bg-muted/20">
          <div :class="`p-3 bg-${column.color}-50 dark:bg-${column.color}-900/20 border-b border-${column.color}-200 dark:border-${column.color}-800`">
            <div class="flex items-center space-x-2">
              <component :is="column.icon" :class="`h-4 w-4 text-${column.color}-600 dark:text-${column.color}-400`" />
              <h3 :class="`text-sm font-semibold text-${column.color}-900 dark:text-${column.color}-100`">{{ column.title }}</h3>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-2 space-y-2">
            <TransitionGroup name="kanban-item">
              <div v-for="item in column.items" :key="item.id" class="p-2 rounded-md bg-background shadow-sm border border-border/50">
                <div class="flex items-center justify-between mb-2">
                  <Badge variant="outline" class="text-xs font-mono">
                    {{ formatTimestampBadge(item.latest_timestamp) }}
                  </Badge>
                  <!-- Priority badge for pending items -->
                  <Badge v-if="item.priority" variant="secondary" :class="getPriorityColor(item.priority)" class="text-xs">
                    {{ item.priority.toUpperCase() }}
                  </Badge>
                  <!-- Category badge for emergency items -->
                  <Badge v-if="item.category" variant="destructive" :class="getCategoryColor(item.category)" class="text-xs">
                    {{ item.category.replace('_', '/') }}
                  </Badge>
                </div>
                
                <div v-html="formatSummaryContent(item.content)" class="prose prose-sm max-w-none dark:prose-invert text-foreground/80 text-xs mb-2"></div>
                
                <!-- ETA/ETR information for pending items -->
                <div v-if="item.eta_etr_info || item.calculated_time" class="text-xs text-muted-foreground border-t pt-1 mt-1">
                  <div v-if="item.eta_etr_info" class="mb-1">
                    <strong>Original:</strong> {{ item.eta_etr_info }}
                  </div>
                  <div v-if="item.calculated_time" class="text-blue-600 dark:text-blue-400 font-medium">
                    <strong>Calculated:</strong> {{ item.calculated_time }}H
                  </div>
                </div>
                
                <!-- Immediate action indicator for emergencies -->
                <div v-if="item.immediate_action_required" class="text-xs text-red-600 dark:text-red-400 font-semibold border-t pt-1 mt-1">
                  ⚠️ IMMEDIATE ACTION REQUIRED
                </div>
              </div>
            </TransitionGroup>
          </div>
        </div>
      </div>
    </CardContent>

  </Card>
</template>

<style scoped>
.prose {
  line-height: 1.4;
}
.kanban-item-enter-active,
.kanban-item-leave-active {
  transition: all 0.5s cubic-bezier(0.55, 0, 0.1, 1);
}
.kanban-item-enter-from,
.kanban-item-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-10px);
}
</style>