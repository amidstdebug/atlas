<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface Summary {
  id: string
  summary: string
  timestamp: string
}

interface Props {
  summaries: Summary[]
  isGenerating: boolean
  autoReportEnabled: boolean
  nextReportCountdown: number
  formatSummaryContent: (content: string) => string
}

const props = defineProps<Props>()

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
    <CardHeader class="pb-4">
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
          <div v-if="summaries.length > 0" class="flex items-center space-x-2">
            <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span class="text-xs text-muted-foreground">Live</span>
          </div>
          <div v-if="autoReportEnabled" class="flex items-center space-x-1.5 px-2 py-1 rounded-md bg-muted/20 border border-border/40">
            <div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></div>
            <span class="text-xs text-muted-foreground">Auto</span>
            <span v-if="nextReportCountdown > 0" class="text-xs text-muted-foreground/60">{{ nextReportCountdown }}s</span>
            <span v-else class="text-xs text-muted-foreground/60">Ready</span>
          </div>
        </div>
      </div>
    </CardHeader>
    <CardContent class="flex-1 overflow-hidden">
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
      <div v-else class="h-full flex flex-col">
        <!-- Incident Analysis Carousel -->
        <div class="flex-1 relative overflow-hidden">
          <!-- Carousel content -->
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
                <!-- Report header -->
                <div class="flex items-center justify-between mb-4 pb-2 border-b">
                  <div class="flex items-center space-x-3">
                    <Badge variant="outline" class="text-xs" :class="[
                      index === 0 ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800' :
                      'bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800'
                    ]">
                      {{ index === 0 ? 'Initial Report' : `Update ${index}` }}
                    </Badge>
                    <span class="text-xs text-muted-foreground">{{ formatSummaryTimestamp(summary.timestamp) }}</span>
                  </div>

                  <span class="text-xs text-muted-foreground">
                    {{ currentReportIndex + 1 }} of {{ summaries.length }}
                  </span>
                </div>

                <!-- Report content -->
                <div
                  v-html="formatSummaryContent(summary.summary)"
                  class="prose prose-sm max-w-none dark:prose-invert"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Navigation controls -->
        <div class="flex items-center justify-between p-4 border-t bg-muted/20">
          <button
            @click="previousReport"
            :disabled="currentReportIndex === 0"
            class="flex items-center space-x-2 px-3 py-2 text-sm rounded-lg border transition-colors"
            :class="[
              currentReportIndex === 0
                ? 'text-muted-foreground border-border cursor-not-allowed'
                : 'text-foreground border-border hover:bg-muted hover:border-muted-foreground'
            ]"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
            </svg>
            <span>Previous</span>
          </button>

          <!-- Timeline slider -->
          <div class="flex-1 mx-6">
            <div class="relative">
              <div class="w-full h-2 bg-muted rounded-full">
                <div
                  class="h-2 bg-indigo-500 rounded-full transition-all duration-300"
                  :style="{ width: `${((currentReportIndex + 1) / summaries.length) * 100}%` }"
                ></div>
              </div>
              <div class="absolute -top-1 w-4 h-4 bg-indigo-500 rounded-full border-2 border-background transition-all duration-300"
                   :style="{ left: `calc(${(currentReportIndex / Math.max(summaries.length - 1, 1)) * 100}% - 8px)` }">
              </div>
            </div>
          </div>

          <button
            @click="nextReport"
            :disabled="currentReportIndex === summaries.length - 1"
            class="flex items-center space-x-2 px-3 py-2 text-sm rounded-lg border transition-colors"
            :class="[
              currentReportIndex === summaries.length - 1
                ? 'text-muted-foreground border-border cursor-not-allowed'
                : 'text-foreground border-border hover:bg-muted hover:border-muted-foreground'
            ]"
          >
            <span>Next</span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
            </svg>
          </button>
        </div>
      </div>
    </CardContent>
  </Card>
</template>