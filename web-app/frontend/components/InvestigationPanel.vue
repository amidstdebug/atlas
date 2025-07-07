<script setup lang="ts">
import { MessageSquare, Filter, CheckCircle, AlertTriangle, Clock, Users, RefreshCw } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Progress } from '@/components/ui/progress'
import { useInvestigation } from '@/composables/useInvestigation'

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
  transcriptionSegments: any[]
  aggregatedTranscription: string
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

// Investigation composable
const {
  state: investigationState,
  selectedTimeRange,
  messages,
  isInvestigating,
  askQuestion,
  setTimeRange,
  clearTimeRange,
  clearMessages,
  formatTimeRange
} = useInvestigation()

// Investigation form
const investigationQuestion = ref('')
const startTimeStr = ref('')
const endTimeStr = ref('')
const timeRangeSelectedForPreview = ref(false)

function timestampToSeconds(ts: string): number | null {
  if (!ts?.trim()) return null
  
  const parts = ts.split(':').map(Number)
  if (parts.length === 2 && !parts.some(isNaN) && parts[1] >= 0 && parts[1] < 60) {
    return parts[0] * 60 + parts[1]
  }

  const seconds = parseFloat(ts)
  if (!isNaN(seconds)) {
    return seconds
  }
  
  return null
}

function secondsToTimestamp(s: number | null): string {
  if (s === null || s < 0) return ''
  const totalSeconds = Math.round(s)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${minutes}:${pad(seconds)}`
}

async function handleInvestigationSubmit() {
  if (!investigationQuestion.value.trim()) return

  const timeRange = (selectedTimeRange.value.start !== null || selectedTimeRange.value.end !== null) 
    ? { start: selectedTimeRange.value.start, end: selectedTimeRange.value.end }
    : undefined

  await askQuestion(
    investigationQuestion.value,
    props.aggregatedTranscription,
    timeRange
  )

  investigationQuestion.value = ''
}

function handleSelectClick() {
  const startSec = timestampToSeconds(startTimeStr.value)
  const endSec = timestampToSeconds(endTimeStr.value)

  if (startSec !== null && endSec !== null && endSec < startSec) {
    console.error('End time must be after start time.')
    return
  }

  setTimeRange(startSec, endSec)
  timeRangeSelectedForPreview.value = true
}

function clearTimeRangeInput() {
  startTimeStr.value = ''
  endTimeStr.value = ''
  clearTimeRange()
  timeRangeSelectedForPreview.value = false
}

const previewedSegments = computed(() => {
  if (!timeRangeSelectedForPreview.value || (selectedTimeRange.value.start === null && selectedTimeRange.value.end === null)) {
    return []
  }
  const start = selectedTimeRange.value.start ?? 0
  const end = selectedTimeRange.value.end ?? Infinity

  return props.transcriptionSegments
    .filter((segment: any) => {
      const segmentStart = segment?.start ?? segment?.begin
      return segmentStart >= start && segmentStart <= end
    })
    .slice(0, 10)
})

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

const sortedActions = computed(() => {
  return props.actions
    .filter(action => !action.completed)
    .sort((a, b) => {
      if (a.priority !== b.priority) {
        return b.priority - a.priority
      }
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

function formatSummaryContent(content: string): string {
  return content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
}
</script>

<template>
  <Card class="h-full flex flex-col border-0 shadow-none bg-background">
    <CardHeader class="pb-2 border-b border-border">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30">
            <MessageSquare class="h-5 w-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <CardTitle class="text-lg">Investigation</CardTitle>
            <p class="text-sm text-muted-foreground">AI-powered investigation & suggested actions</p>
          </div>
        </div>
      </div>
    </CardHeader>
    
    <CardContent class="flex-1 flex flex-col p-4 space-y-4">
      <!-- Time Range Selection -->
      <Accordion type="single" collapsible class="w-full">
        <AccordionItem value="item-1">
          <AccordionTrigger>
            <div class="flex items-center space-x-2">
              <Filter class="h-4 w-4" />
              <span class="text-sm font-medium">Time Range Filter</span>
              <Badge v-if="selectedTimeRange.start !== null || selectedTimeRange.end !== null" variant="secondary" class="font-mono">
                {{ formatTimeRange(selectedTimeRange) }}
              </Badge>
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <div class="space-y-3 pt-1">
              <div class="grid grid-cols-2 gap-2">
                <Input
                  v-model="startTimeStr"
                  placeholder="Start (e.g., 1:23 or 83s)"
                  class="text-xs"
                />
                <Input
                  v-model="endTimeStr"
                  placeholder="End (e.g., 2:45 or 165s)"
                  class="text-xs"
                />
              </div>
              <div class="grid grid-cols-2 gap-2">
                <Button @click="handleSelectClick" size="sm" class="text-xs">
                  Select Range
                </Button>
                <Button @click="clearTimeRangeInput" variant="outline" size="sm" class="text-xs">
                  Clear Selection
                </Button>
              </div>
              
              <div v-if="previewedSegments.length > 0" class="pt-2">
                <p class="text-xs text-muted-foreground mb-1.5">Preview (up to 10 segments):</p>
                <div class="max-h-32 overflow-y-auto p-2 rounded-md bg-muted/40 border space-y-1.5">
                  <div
                    v-for="(segment, index) in previewedSegments"
                    :key="index"
                    class="text-xs"
                  >
                    <span class="font-mono text-muted-foreground/80 mr-2">[{{ secondsToTimestamp((segment as any).start ?? (segment as any).begin) }}]</span>
                    <span class="text-foreground/90">{{ (segment as any).text ?? (segment as any).content }}</span>
                  </div>
                </div>
              </div>
              <div v-else-if="timeRangeSelectedForPreview" class="pt-2 text-center">
                <p class="text-xs text-muted-foreground italic">No transcription available in the selected range.</p>
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <!-- Chat Messages -->
      <div class="flex-1 overflow-y-auto space-y-4">
        <div v-if="messages.length === 0" class="text-center text-muted-foreground text-sm py-8">
          Ask questions about the transcription data to investigate specific details.
        </div>
        
        <div
          v-for="(message, index) in messages"
          :key="index"
          :class="[
            'p-3 rounded-lg',
            message.role === 'user' 
              ? 'bg-purple-50 dark:bg-purple-900/30 ml-8' 
              : 'bg-muted/50 mr-8'
          ]"
        >
          <div class="flex items-start space-x-2">
            <div :class="[
              'w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium',
              message.role === 'user' 
                ? 'bg-purple-200 dark:bg-purple-800 text-purple-800 dark:text-purple-200' 
                : 'bg-muted text-muted-foreground'
            ]">
              {{ message.role === 'user' ? 'U' : 'AI' }}
            </div>
            <div class="flex-1">
              <div v-html="formatSummaryContent(message.content)" class="prose prose-sm max-w-none dark:prose-invert"></div>
              <div v-if="message.relevantSegments && message.relevantSegments.length > 0" class="mt-2">
                <p class="text-xs text-muted-foreground mb-1">Relevant segments:</p>
                <div class="space-y-1">
                  <div
                    v-for="segment in message.relevantSegments.slice(0, 3)"
                    :key="segment.line_number"
                    class="text-xs bg-background/50 p-2 rounded border"
                  >
                    {{ segment.content }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Question Input -->
      <div class="border-t pt-4">
        <div class="flex space-x-2">
          <Textarea
            v-model="investigationQuestion"
            placeholder="Ask a question about the transcription..."
            class="flex-1 min-h-[60px] resize-none"
            @keydown.enter.ctrl="handleInvestigationSubmit"
          />
          <Button
            @click="handleInvestigationSubmit"
            :disabled="!investigationQuestion.trim() || isInvestigating"
            class="self-end"
          >
            <MessageSquare class="h-4 w-4" />
          </Button>
        </div>
        <p class="text-xs text-muted-foreground mt-1">Press Ctrl+Enter to send</p>
      </div>

      <!-- Suggested Actions Section -->
      <div class="border-t pt-4 space-y-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <CheckCircle class="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <h3 class="text-sm font-medium">Suggested Actions</h3>
          </div>
          <div class="flex items-center space-x-2">
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
            <div v-if="autoActionsEnabled" class="flex items-center space-x-1 px-2 py-1 rounded-md bg-muted/20 border border-border/40">
              <div class="w-1 h-1 bg-emerald-500 rounded-full animate-pulse"></div>
              <span class="text-xs text-muted-foreground">Auto</span>
            </div>
          </div>
        </div>

        <!-- Critical Actions Alert -->
        <div v-if="criticalActions.length > 0" class="p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
          <div class="flex items-center space-x-2">
            <AlertTriangle class="h-3 w-3 text-red-600 dark:text-red-400" />
            <span class="text-xs font-medium text-red-900 dark:text-red-100">
              {{ criticalActions.length }} Critical Action{{ criticalActions.length > 1 ? 's' : '' }}
            </span>
          </div>
        </div>

        <!-- Actions List -->
        <div v-if="sortedActions.length === 0 && !isGenerating" class="text-center py-4">
          <p class="text-xs text-muted-foreground">No actions required at this time</p>
        </div>

        <div v-else-if="isGenerating" class="text-center py-4">
          <div class="flex items-center justify-center space-x-2">
            <RefreshCw class="h-4 w-4 animate-spin text-emerald-600" />
            <span class="text-xs text-muted-foreground">Analyzing...</span>
          </div>
        </div>

        <div v-else class="space-y-2 max-h-96 overflow-y-auto">
          <div
            v-for="action in sortedActions.slice(0, 5)"
            :key="action.id"
            :class="[
              'rounded-md p-3 border transition-all duration-200',
              actionTypeConfig[action.type].bgColor,
              actionTypeConfig[action.type].borderColor
            ]"
          >
            <div class="flex items-start space-x-2">
              <component 
                :is="actionTypeConfig[action.type].icon"
                :class="['h-4 w-4 mt-0.5', actionTypeConfig[action.type].color]"
              />
              
              <div class="flex-1 space-y-1">
                <div class="flex items-center justify-between">
                  <h4 class="font-medium text-xs">{{ action.title }}</h4>
                  <Badge 
                    variant="secondary"
                    :class="actionTypeConfig[action.type].badgeClass"
                    class="text-xs"
                  >
                    {{ action.type.charAt(0).toUpperCase() + action.type.slice(1) }}
                  </Badge>
                </div>
                
                <div 
                  v-html="formatActionContent(action.description)"
                  class="text-xs text-muted-foreground"
                ></div>
                
                <div class="flex items-center justify-between">
                  <span class="text-xs text-muted-foreground">
                    {{ formatActionTimestamp(action.timestamp) }}
                  </span>
                  
                  <Button
                    @click="handleCompleteAction(action.id)"
                    variant="outline"
                    size="sm"
                    class="text-xs h-6 px-2"
                  >
                    <CheckCircle class="h-3 w-3 mr-1" />
                    Complete
                  </Button>
                </div>
              </div>
            </div>
          </div>
          
          <div v-if="sortedActions.length > 5" class="text-center py-2">
            <p class="text-xs text-muted-foreground">+{{ sortedActions.length - 5 }} more actions</p>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>