<script setup lang="ts">
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { Settings } from 'lucide-vue-next'
import { useAudioRecording } from '@/composables/useAudioRecording'
import { useSummaryGeneration } from '@/composables/useSummaryGeneration'
import { useAdvancedTextProcessing } from '@/composables/useAdvancedTextProcessing'
import { useTranscriptionStore } from '@/stores/transcription'
import { useAuthStore } from '@/stores/auth'
import ConfigPanel from '@/components/ConfigPanel.vue'
import HeaderBar from '@/components/HeaderBar.vue'
import TranscriptionPanel from '@/components/TranscriptionPanel.vue'
import LiveIncidentPanel from '@/components/LiveIncidentPanel.vue'
import { watch, computed } from 'vue'

definePageMeta({
  middleware: 'auth'
})

let pollingLogInterval: NodeJS.Timeout | null = null

const authStore = useAuthStore()

// Stores and composables
const transcriptionStore = useTranscriptionStore()
const {
  state: recordingState,
  transcriptionSegments,
  startRecording,
  stopRecording,
  toggleRecording,
  transcribeFile,
  clearTranscription,
  updateSegment
} = useAudioRecording()

const {
  state: summaryState,
  autoReportConfig,
  generateSummary,
  generateAutoReport,
  toggleAutoSummary,
  toggleAutoReport,
  updateAutoReportConfig,
  setCustomPrompt,
  formatSummaryContent,
  cleanup
} = useSummaryGeneration(transcriptionSegments)


// File upload
const audioFileInput = ref<HTMLInputElement>()

// Configuration state
const isConfigPanelOpen = ref(false)
const customPrompt = ref('')
const replaceNumbers = ref(true)
const useIcaoCallsigns = ref(true)
const autoReportEnabled = ref(false) // UI state only, copies from composable
const autoReportIntervalValue = ref(30)

// Sidebar resizing state
const sidebarWidth = ref(320)
const isResizing = ref(false)
const minWidth = 250
const maxWidth = 600



// -------------------------------
// 1.  Restore & sync on mount
// -------------------------------
onMounted(() => {
  if (process.client) {
    const savedPrompt             = localStorage.getItem('atlas-custom-prompt')
    const savedReplaceNumbers     = localStorage.getItem('atlas-replace-numbers')
    const savedUseIcaoCallsigns   = localStorage.getItem('atlas-use-icao-callsigns')
    const savedAutoReportEnabled  = localStorage.getItem('atlas-auto-report-enabled')
    const savedAutoReportInterval = localStorage.getItem('atlas-auto-report-interval')

    if (savedPrompt) {
      customPrompt.value = savedPrompt
    }
    if (savedReplaceNumbers !== null) {
      replaceNumbers.value = savedReplaceNumbers === 'true'
    }
    if (savedUseIcaoCallsigns !== null) {
      useIcaoCallsigns.value = savedUseIcaoCallsigns === 'true'
    }
    if (savedAutoReportEnabled !== null) {
      autoReportEnabled.value = savedAutoReportEnabled === 'true'
    }
    if (savedAutoReportInterval) {
      autoReportIntervalValue.value = parseInt(savedAutoReportInterval) || 30
    }

    // Update composable config
    updateAutoReportConfig({
      enabled: autoReportEnabled.value,
      customPrompt: customPrompt.value
    })
  }

  // Polling logger for segment length
  pollingLogInterval = setInterval(() => {
    console.log(`[Segment Polling] Total segments: ${transcriptionSegments.value.length}`)
  }, 1000)
})

// Watch for changes and save to localStorage
watch(customPrompt, (newValue) => {
  if (process.client) {
    localStorage.setItem('atlas-custom-prompt', newValue)
    setCustomPrompt(newValue)
  }
})

watch(replaceNumbers, (newValue) => {
  if (process.client) {
    localStorage.setItem('atlas-replace-numbers', newValue.toString())
  }
})

watch(useIcaoCallsigns, (newValue) => {
  if (process.client) {
    localStorage.setItem('atlas-use-icao-callsigns', newValue.toString())
  }
})

watch(autoReportIntervalValue, (newValue) => {
  if (process.client) {
    localStorage.setItem('atlas-auto-report-interval', newValue.toString())
    // Note: setAutoReportInterval is now deprecated, this watcher can be removed.
  }
})

// ------------------------------------------------------
// 2.  Reactively keep both sources of truth in-sync
// ------------------------------------------------------
watch(autoReportEnabled, (enabled) => {
  // persist to localStorage (existing behaviour)
  if (process.client) {
    localStorage.setItem('atlas-auto-report-enabled', enabled.toString())
  }

  // keep composable flag in-sync
  if (enabled !== autoReportConfig.value.enabled) {
    toggleAutoReport()
  }
})

// ------------------------------------------------------
// 3. Coordinate between panels (async coordination)
// ------------------------------------------------------
// This watcher is being removed as the logic is moving into the composables themselves.


// Advanced text processing functionality
const { getAggregatedProcessedText } = useAdvancedTextProcessing()

// Computed
const aggregatedTranscription = computed(() => {
  return transcriptionSegments.value.map(segment => segment.text).join(' ')
})

// Get processed transcription for LLM calls (uses NER processed text, cleaned text, or raw as fallback)
const getProcessedTranscription = () => {
  return getAggregatedProcessedText(transcriptionSegments.value)
}

const summaries = computed(() => transcriptionStore.getSummaries)

// Methods
async function uploadRecording() {
  audioFileInput.value?.click()
}

async function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (file) {
    try {
      await transcribeFile(file)
    } catch (error) {
      console.error('File upload failed:', error)
    }

    // Reset file input
    target.value = ''
  }
}

async function handleStartRecording() {
  try {
    await startRecording()
  } catch (error) {
    console.error('Recording failed:', error)
  }
}

async function handleStopRecording() {
  try {
    await stopRecording()
  } catch (error) {
    console.error('Stop recording failed:', error)
  }
}

async function handleToggleRecording() {
  try {
    await toggleRecording()
  } catch (error) {
    console.error('Toggle recording failed:', error)
  }
}

async function handleGenerateSummary() {
  if (aggregatedTranscription.value) {
    try {
      // Get the latest summary for previous report context
      const latestSummary = summaries.value.length > 0 ? summaries.value[summaries.value.length - 1].summary : undefined

      // Use processed transcription (NER/cleaned) by default, fallback to raw if not available
      const transcriptionToUse = getProcessedTranscription() || aggregatedTranscription.value

      await generateSummary(
        transcriptionToUse,
        'atc',
        customPrompt.value || undefined,
        latestSummary, // pass previous report for context
        true, // structured
        transcriptionSegments.value,
        false
      )
    } catch (error) {
      console.error('Summary generation failed:', error)
    }
  }
}

function openConfigPanel() {
  isConfigPanelOpen.value = true
}

function resetConfig() {
  customPrompt.value = ''
  replaceNumbers.value = true
  useIcaoCallsigns.value = true
  autoReportEnabled.value = false
  autoReportIntervalValue.value = 30

  // Reset composable state
  updateAutoReportConfig({
    enabled: false,
    customPrompt: ''
  })
}

function handleApplySettings() {
  // Update all auto-report configuration
  updateAutoReportConfig({
    enabled: autoReportEnabled.value,
    customPrompt: customPrompt.value
  })
}

function handleClearTranscription() {
  clearTranscription()
  transcriptionStore.clearSummaries()
}

function logout() {
  authStore.logout()
  navigateTo('/login')
}

function handleUpdateSegment(index: number, text: string) {
  updateSegment(index, text)
}

// Resize handlers
function handleResizeStart() {
  isResizing.value = true
  document.addEventListener('mousemove', handleResizeMove)
  document.addEventListener('mouseup', handleResizeEnd)
}

function handleResizeMove(event: MouseEvent) {
  if (!isResizing.value) return

  const newWidth = Math.max(minWidth, Math.min(maxWidth, event.clientX))
  sidebarWidth.value = newWidth
}

function handleResizeEnd() {
  isResizing.value = false
  document.removeEventListener('mousemove', handleResizeMove)
  document.removeEventListener('mouseup', handleResizeEnd)
}

// Right panel resize handlers



// Action handlers for suggested actions
async function handleRefreshActions() {
  if (aggregatedTranscription.value) {
    try {
      await generateActions(
        aggregatedTranscription.value,
        transcriptionSegments.value,
        pendingActions.value
      )
    } catch (error) {
      console.error('Actions generation failed:', error)
    }
  }
}

function handleCompleteAction(actionId: string) {
  completeAction(actionId)
}

function handleToggleAutoActions() {
  toggleAutoActions()
}

function handleForceAnalysis() {
  if (aggregatedTranscription.value) {
    handleGenerateSummary()
  }
}

function handleToggleAutoMode() {
  autoReportEnabled.value = !autoReportEnabled.value
}


// Cleanup on unmount
onUnmounted(() => {
  cleanup()

  // Clear polling logger
  if (pollingLogInterval) {
    clearInterval(pollingLogInterval)
  }
})

useHead({
  title: 'ATLAS - Air Incident Investigation'
})
</script>

<template>
  <div class="h-screen bg-background flex flex-col">
    <!-- Header -->
    <HeaderBar
      :username="authStore.user?.username"
      @logout="logout"
      class="shrink-0"
    />

    <!-- Progress Indicators -->
    <div v-if="recordingState.isTranscribing || summaryState.isGenerating" class="shrink-0 border-b border-border">
      <div class="px-4 py-2 space-y-2">
        <div v-if="recordingState.isTranscribing" class="flex items-center space-x-2">
          <div class="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"></div>
          <span class="text-sm text-muted-foreground">Processing audio transcription...</span>
        </div>
        <div v-if="summaryState.isGenerating" class="flex items-center space-x-2">
          <div class="w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin"></div>
          <span class="text-sm text-muted-foreground">Generating situation report...</span>
        </div>
      </div>
    </div>

    <!-- Main IDE-style Layout -->
    <div class="flex-1 flex overflow-hidden p-6 pt-0">
      <div class="flex-1 flex overflow-hidden border border-border rounded-lg">
        <!-- Left Panel - Transcription -->
        <div class="flex border-r border-border flex flex-col" :style="{ width: sidebarWidth + 'px' }">
        <TranscriptionPanel
          :segments="transcriptionSegments"
          :is-transcribing="recordingState.isTranscribing"
          :is-recording="recordingState.isRecording"
          :audio-level="recordingState.audioLevel"
          :is-waiting-for-transcription="recordingState.isWaitingForTranscription"
          :recording-state="recordingState"
          :sidebar-width="sidebarWidth"
          @update-segment="handleUpdateSegment"
          @upload-recording="uploadRecording"
          @start-recording="handleToggleRecording"
          @stop-recording="handleToggleRecording"
          @toggle-recording="handleToggleRecording"
          @clear-transcription="handleClearTranscription"
          class="h-full"
        />
      </div>

        <!-- Resize Handle -->
        <div
          class="w-1 bg-border hover:bg-border/80 cursor-col-resize transition-colors relative"
          @mousedown="handleResizeStart"
        >
          <div class="absolute inset-y-0 -left-1 -right-1 cursor-col-resize"></div>
        </div>

        <!-- Center Panel - Live Situation Report -->
        <div class="flex-1 flex flex-col">
        <LiveIncidentPanel
          :summaries="summaries"
          :is-generating="summaryState.isGenerating"
          :auto-report-enabled="autoReportEnabled"
          :format-summary-content="formatSummaryContent"
          @force-analysis="handleForceAnalysis"
          @toggle-auto-mode="handleToggleAutoMode"
          class="h-full"
        />
        </div>
      </div>
    </div>

    <!-- Bottom Panel - Configuration Button -->
    <div class="shrink-0 border-t border-border px-6 py-2 flex justify-end">
      <Button
        @click="openConfigPanel"
        variant="ghost"
        size="sm"
        class="text-xs"
      >
        <Settings class="h-3 w-3 mr-1" />
        Configuration
      </Button>
    </div>

    <!-- Hidden file input -->
    <input
      ref="audioFileInput"
      type="file"
      accept="audio/*"
      class="hidden"
      @change="handleFileUpload"
    />

    <!-- Prompt Configuration Panel -->
    <ConfigPanel
      v-model:is-open="isConfigPanelOpen"
      v-model:custom-prompt="customPrompt"
      v-model:replace-numbers="replaceNumbers"
      v-model:use-icao-callsigns="useIcaoCallsigns"
      v-model:auto-report-enabled="autoReportEnabled"
      v-model:auto-report-interval="autoReportIntervalValue"
      @apply="handleApplySettings"
      @reset="resetConfig"
    />
  </div>
</template>

