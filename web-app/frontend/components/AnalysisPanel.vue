<script setup lang="ts">
import { Sparkles, MessageSquare, Clock, Users, AlertTriangle, TrendingUp, Filter } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { useInvestigation } from '@/composables/useInvestigation'

interface Summary {
  id: string
  summary: string
  timestamp: string
  structured_summary?: {
    situation_update: string
    current_situation_details: string
    recent_actions_taken: string
    overall_status: string
  }
}

interface Props {
  summaries: Summary[]
  isGenerating: boolean
  autoReportEnabled: boolean
  nextReportCountdown: number
  formatSummaryContent: (content: string) => string
  transcriptionSegments: any[]
  aggregatedTranscription: string
}

const props = defineProps<Props>()

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

// Tab state
const activeTab = ref<'overview' | 'investigate'>('overview')

// Investigation form
const investigationQuestion = ref('')
const startTimeStr = ref('')
const endTimeStr = ref('')
const timeRangeSelectedForPreview = ref(false)

function timestampToSeconds(ts: string): number | null {
  if (!ts?.trim()) return null
  
  // Try parsing as MM:SS
  const parts = ts.split(':').map(Number)
  if (parts.length === 2 && !parts.some(isNaN) && parts[1] >= 0 && parts[1] < 60) {
    return parts[0] * 60 + parts[1]
  }

  // Try parsing as raw seconds
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

// Carousel state
const currentReportIndex = ref(0)

function formatSummaryTimestamp(timestamp: string): string {
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

function previousReport() {
  if (currentReportIndex.value > 0) {
    currentReportIndex.value--
  }
}

function nextReport() {
  if (currentReportIndex.value < props.summaries.length - 1) {
    currentReportIndex.value++
  }
}

// Investigation methods
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
    // TODO: Show user-facing error
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

function switchTab(tab: 'overview' | 'investigate') {
  activeTab.value = tab
}

// Get latest structured summary
const latestStructuredSummary = computed(() => {
  const latest = props.summaries[props.summaries.length - 1]
  return latest?.structured_summary
})

function formatTimestampBadge(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

function getSectionTimestamps(section: any) {
  if (!section?.timestamps || !Array.isArray(section.timestamps)) {
    return []
  }
  return section.timestamps.slice(0, 5) // Show up to 5 timestamps per section
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
    .slice(0, 10) // Limit preview to 10 segments
})

// Auto-navigate to latest report when new summary is added
watch(() => props.summaries, (newSummaries, oldSummaries) => {
  if (newSummaries.length > (oldSummaries?.length || 0)) {
    // New summary added, navigate to the latest
    currentReportIndex.value = newSummaries.length - 1
  }
}, { deep: true })

// Keyboard navigation for carousel
if (process.client) {
  const handleCarouselKeydown = (event: KeyboardEvent) => {
    if (event.target && (event.target as HTMLElement).tagName === 'INPUT') return

    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      previousReport()
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      nextReport()
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleCarouselKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleCarouselKeydown)
  })
}
</script>

<template>
  <Card class="h-[700px] flex flex-col border-0 shadow-xl bg-card/50 backdrop-blur-sm overflow-hidden">
    <CardHeader class="pb-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/30">
            <Sparkles class="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <CardTitle class="text-lg">Live Incident Analysis</CardTitle>
            <p class="text-sm text-muted-foreground">Real-time AI-powered investigation</p>
          </div>
        </div>
        <div class="flex items-center space-x-3">
          <div v-if="autoReportEnabled" class="flex items-center space-x-1.5 px-2 py-1 rounded-md bg-muted/20 border border-border/40">
            <div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></div>
            <span class="text-xs text-muted-foreground">Auto</span>
            <span v-if="nextReportCountdown > 0" class="text-xs text-muted-foreground/60">{{ nextReportCountdown }}s</span>
            <span v-else class="text-xs text-muted-foreground/60">Ready</span>
          </div>
        </div>
      </div>
      
      <!-- Tab Navigation -->
      <div class="flex space-x-1 mt-4 p-1 bg-muted/30 rounded-lg">
        <button
          @click="switchTab('overview')"
          :class="[
            'flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === 'overview' 
              ? 'bg-background text-foreground shadow-sm' 
              : 'text-muted-foreground hover:text-foreground'
          ]"
        >
          <TrendingUp class="h-4 w-4" />
          <span>Overview</span>
        </button>
        <button
          @click="switchTab('investigate')"
          :class="[
            'flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === 'investigate' 
              ? 'bg-background text-foreground shadow-sm' 
              : 'text-muted-foreground hover:text-foreground'
          ]"
        >
          <MessageSquare class="h-4 w-4" />
          <span>Investigate</span>
        </button>
      </div>
    </CardHeader>
    
    <CardContent class="flex-1 overflow-hidden">
      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'" class="h-full">
        <div v-if="summaries.length === 0" class="h-full flex items-center justify-center">
          <div class="text-center space-y-4">
            <div class="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900/30 dark:to-purple-900/30 flex items-center justify-center">
              <Sparkles class="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div class="space-y-2">
              <p class="text-muted-foreground max-w-sm">
                AI analysis will appear here as audio is processed
              </p>
              <div v-if="autoReportEnabled" class="flex items-center justify-center space-x-2 px-3 py-2 rounded-md bg-muted/30 border border-border/50">
                <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                <span class="text-sm text-muted-foreground">
                  <template v-if="nextReportCountdown > 0">
                    Next auto report in {{ nextReportCountdown }}s
                  </template>
                  <template v-else>
                    Auto reports ready - waiting for transcription updates
                  </template>
                </span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Structured Summary Sections -->
        <div v-else-if="latestStructuredSummary" class="h-full overflow-y-auto space-y-4">
          <!-- Situation Update -->
          <div class="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-2">
                <AlertTriangle class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                <h3 class="font-semibold text-blue-900 dark:text-blue-100">Situation Update</h3>
              </div>
              <div v-if="latestStructuredSummary.situation_update?.latest_timestamp" class="flex items-center space-x-1">
                <Clock class="h-3 w-3 text-blue-500 dark:text-blue-400" />
                <Badge variant="outline" class="text-xs font-mono border-blue-300 text-blue-700 dark:border-blue-700 dark:text-blue-300">
                  {{ formatTimestampBadge(latestStructuredSummary.situation_update.latest_timestamp) }}
                </Badge>
              </div>
            </div>
            <div v-html="formatSummaryContent(latestStructuredSummary.situation_update?.content || latestStructuredSummary.situation_update)" class="prose prose-sm max-w-none dark:prose-invert text-blue-800 dark:text-blue-200"></div>
            <div v-if="getSectionTimestamps(latestStructuredSummary.situation_update).length > 0" class="mt-3 pt-3 border-t border-blue-200 dark:border-blue-700">
              <p class="text-xs text-blue-600 dark:text-blue-400 mb-2 font-medium">Referenced Timestamps:</p>
              <div class="flex flex-wrap gap-1.5">
                <Badge 
                  v-for="(timestamp, index) in getSectionTimestamps(latestStructuredSummary.situation_update)"
                  :key="index"
                  variant="secondary"
                  class="text-xs font-mono bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/70 cursor-help"
                  :title="timestamp.text"
                >
                  {{ formatTimestampBadge(timestamp.start) }}-{{ formatTimestampBadge(timestamp.end) }}
                </Badge>
              </div>
            </div>
          </div>

          <!-- Current Situation Details -->
          <div class="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-lg p-4 border border-green-200 dark:border-green-800">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-2">
                <Users class="h-5 w-5 text-green-600 dark:text-green-400" />
                <h3 class="font-semibold text-green-900 dark:text-green-100">Current Situation Details</h3>
              </div>
              <div v-if="latestStructuredSummary.current_situation_details?.latest_timestamp" class="flex items-center space-x-1">
                <Clock class="h-3 w-3 text-green-500 dark:text-green-400" />
                <Badge variant="outline" class="text-xs font-mono border-green-300 text-green-700 dark:border-green-700 dark:text-green-300">
                  {{ formatTimestampBadge(latestStructuredSummary.current_situation_details.latest_timestamp) }}
                </Badge>
              </div>
            </div>
            <div v-html="formatSummaryContent(latestStructuredSummary.current_situation_details?.content || latestStructuredSummary.current_situation_details)" class="prose prose-sm max-w-none dark:prose-invert text-green-800 dark:text-green-200"></div>
            <div v-if="getSectionTimestamps(latestStructuredSummary.current_situation_details).length > 0" class="mt-3 pt-3 border-t border-green-200 dark:border-green-700">
              <p class="text-xs text-green-600 dark:text-green-400 mb-2 font-medium">Referenced Timestamps:</p>
              <div class="flex flex-wrap gap-1.5">
                <Badge 
                  v-for="(timestamp, index) in getSectionTimestamps(latestStructuredSummary.current_situation_details)"
                  :key="index"
                  variant="secondary"
                  class="text-xs font-mono bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/70 cursor-help"
                  :title="timestamp.text"
                >
                  {{ formatTimestampBadge(timestamp.start) }}-{{ formatTimestampBadge(timestamp.end) }}
                </Badge>
              </div>
            </div>
          </div>

          <!-- Recent Actions Taken -->
          <div class="bg-gradient-to-r from-orange-50 to-amber-50 dark:from-orange-900/20 dark:to-amber-900/20 rounded-lg p-4 border border-orange-200 dark:border-orange-800">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-2">
                <Clock class="h-5 w-5 text-orange-600 dark:text-orange-400" />
                <h3 class="font-semibold text-orange-900 dark:text-orange-100">Recent Actions Taken</h3>
              </div>
              <div v-if="latestStructuredSummary.recent_actions_taken?.latest_timestamp" class="flex items-center space-x-1">
                <Clock class="h-3 w-3 text-orange-500 dark:text-orange-400" />
                <Badge variant="outline" class="text-xs font-mono border-orange-300 text-orange-700 dark:border-orange-700 dark:text-orange-300">
                  {{ formatTimestampBadge(latestStructuredSummary.recent_actions_taken.latest_timestamp) }}
                </Badge>
              </div>
            </div>
            <div v-html="formatSummaryContent(latestStructuredSummary.recent_actions_taken?.content || latestStructuredSummary.recent_actions_taken)" class="prose prose-sm max-w-none dark:prose-invert text-orange-800 dark:text-orange-200"></div>
            <div v-if="getSectionTimestamps(latestStructuredSummary.recent_actions_taken).length > 0" class="mt-3 pt-3 border-t border-orange-200 dark:border-orange-700">
              <p class="text-xs text-orange-600 dark:text-orange-400 mb-2 font-medium">Referenced Timestamps:</p>
              <div class="flex flex-wrap gap-1.5">
                <Badge 
                  v-for="(timestamp, index) in getSectionTimestamps(latestStructuredSummary.recent_actions_taken)"
                  :key="index"
                  variant="secondary"
                  class="text-xs font-mono bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 hover:bg-orange-200 dark:hover:bg-orange-900/70 cursor-help"
                  :title="timestamp.text"
                >
                  {{ formatTimestampBadge(timestamp.start) }}-{{ formatTimestampBadge(timestamp.end) }}
                </Badge>
              </div>
            </div>
          </div>

          <!-- Overall Status -->
          <div class="bg-gradient-to-r from-purple-50 to-violet-50 dark:from-purple-900/20 dark:to-violet-900/20 rounded-lg p-4 border border-purple-200 dark:border-purple-800">
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-2">
                <TrendingUp class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                <h3 class="font-semibold text-purple-900 dark:text-purple-100">Overall Status</h3>
              </div>
              <div v-if="latestStructuredSummary.overall_status?.latest_timestamp" class="flex items-center space-x-1">
                <Clock class="h-3 w-3 text-purple-500 dark:text-purple-400" />
                <Badge variant="outline" class="text-xs font-mono border-purple-300 text-purple-700 dark:border-purple-700 dark:text-purple-300">
                  {{ formatTimestampBadge(latestStructuredSummary.overall_status.latest_timestamp) }}
                </Badge>
              </div>
            </div>
            <div v-html="formatSummaryContent(latestStructuredSummary.overall_status?.content || latestStructuredSummary.overall_status)" class="prose prose-sm max-w-none dark:prose-invert text-purple-800 dark:text-purple-200"></div>
            <div v-if="getSectionTimestamps(latestStructuredSummary.overall_status).length > 0" class="mt-3 pt-3 border-t border-purple-200 dark:border-purple-700">
              <p class="text-xs text-purple-600 dark:text-purple-400 mb-2 font-medium">Referenced Timestamps:</p>
              <div class="flex flex-wrap gap-1.5">
                <Badge 
                  v-for="(timestamp, index) in getSectionTimestamps(latestStructuredSummary.overall_status)"
                  :key="index"
                  variant="secondary"
                  class="text-xs font-mono bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 hover:bg-purple-200 dark:hover:bg-purple-900/70 cursor-help"
                  :title="timestamp.text"
                >
                  {{ formatTimestampBadge(timestamp.start) }}-{{ formatTimestampBadge(timestamp.end) }}
                </Badge>
              </div>
            </div>
          </div>
        </div>

        <!-- Fallback to original carousel for non-structured summaries -->
        <div v-else class="h-full flex flex-col">
          <div class="flex-1 relative overflow-hidden">
            <div
              class="h-full transition-transform duration-300 ease-in-out"
              :style="{ transform: `translateX(-${currentReportIndex * 100}%)` }"
            >
              <div class="flex h-full">
                <div
                  v-for="(summary, index) in summaries"
                  :key="summary.id"
                  class="w-full flex-shrink-0 p-4 overflow-y-auto"
                >
                  <div class="flex items-center justify-between mb-4 pb-2 border-b">
                    <div class="flex items-center space-x-3">
                      <Badge variant="outline" class="text-xs">
                        {{ index === 0 ? 'Initial Report' : `Update ${index}` }}
                      </Badge>
                      <span class="text-xs text-muted-foreground">{{ formatSummaryTimestamp(summary.timestamp) }}</span>
                    </div>
                    <span class="text-xs text-muted-foreground">
                      {{ currentReportIndex + 1 }} of {{ summaries.length }}
                    </span>
                  </div>
                  <div
                    v-html="formatSummaryContent(summary.summary)"
                    class="prose prose-sm max-w-none dark:prose-invert"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Investigation Tab -->
      <div v-else class="h-full flex flex-col">
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
        <div class="flex-1 overflow-y-auto space-y-4 pt-4">
          <div v-if="messages.length === 0" class="text-center text-muted-foreground text-sm py-8">
            Ask questions about the transcription data to investigate specific details.
          </div>
          
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="[
              'p-3 rounded-lg',
              message.role === 'user' 
                ? 'bg-indigo-50 dark:bg-indigo-900/30 ml-8' 
                : 'bg-muted/50 mr-8'
            ]"
          >
            <div class="flex items-start space-x-2">
              <div :class="[
                'w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium',
                message.role === 'user' 
                  ? 'bg-indigo-200 dark:bg-indigo-800 text-indigo-800 dark:text-indigo-200' 
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
              class="flex-1 min-h-[80px] resize-none"
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
      </div>
    </CardContent>
  </Card>
</template>