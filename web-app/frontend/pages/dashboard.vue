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
import AudioSimulationPlayer from '@/components/AudioSimulationPlayer.vue'
import { watch, computed, ref, onMounted, onUnmounted } from 'vue'

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

// Simulate mode state
const isSimulateMode = ref(false)

// Watch simulate mode changes to automatically start/stop recording
watch(isSimulateMode, async (newValue) => {
  if (newValue) {
    // When simulate mode is turned on, clear existing transcriptions
    console.log('[Simulate] 🎬 Simulate mode activated - clearing transcriptions')
    clearTranscription()
  } else {
    // When simulate mode is turned off, simulation will stop automatically
    console.log('[Simulate] 🛑 Simulate mode deactivated')
  }
})

// Handle simulation segments
function handleSimulationSegmentsUpdated(segments: any[]) {
  // Replace the existing transcription segments with simulation segments
  transcriptionSegments.value.splice(0, transcriptionSegments.value.length, ...segments)
  console.log('[Simulate] 📝 Updated transcription segments from simulation:', segments.length)
}

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
onMounted(async () => {
  // First, validate the authentication token
  await validateAuthToken()

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
        transcriptionSegments.value
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

async function validateAuthToken() {
  // Check if we have a token
  const authCookie = useCookie('auth_token')
  if (!authCookie.value) {
    console.log('[Auth] No token found, redirecting to login')
    logout()
    return
  }

  // Validate token by making a request to a protected endpoint
  try {
    const { $api } = useNuxtApp()
    await $api.get('/summary/history')
    console.log('[Auth] Token validation successful')
  } catch (error: any) {
    if (error.response?.status === 401) {
      console.log('[Auth] Token expired or invalid, logging out')
      logout()
    } else {
      console.warn('[Auth] Token validation request failed:', error.message)
      // For network errors, don't logout - user might just be offline
    }
  }
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

async function uploadRecording() {
  // This will be handled by the simulate toggle now
  // The upload functionality is now part of the AudioUploadPlayer
  isSimulateMode.value = true
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
      @open-config="openConfigPanel"
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
            :is-simulate-mode="isSimulateMode"
            @update-segment="handleUpdateSegment"
            @update:is-simulate-mode="isSimulateMode = $event"
            @start-recording="handleToggleRecording"
            @stop-recording="handleToggleRecording"
            @toggle-recording="handleToggleRecording"
            @clear-transcription="handleClearTranscription"
            @segments-updated="handleSimulationSegmentsUpdated"
            class="h-full"
          />
        </div>

        <!-- Resize Handle -->
        <div
          class="w-1 bg-border hover:bg-border/80 cursor-col-resize transition-colors relative"
          @mousedown="handleResizeStart"
        >
          <div class="absolute inset-y-0 left-0 w-1 bg-transparent hover:bg-primary/20 transition-colors"></div>
        </div>

        <!-- Right Panel - Summary and Investigation -->
        <div class="flex-1 flex flex-col overflow-hidden">
          <LiveIncidentPanel
            :summaries="summaries"
            :is-generating="summaryState.isGenerating"
            :is-auto-summary-enabled="autoSummaryEnabled"
            :is-auto-report-enabled="autoReportEnabled"
            :auto-report-interval="autoReportIntervalValue"
            :transcription-segments="transcriptionSegments"
            :aggregated-transcription="aggregatedTranscription"
            :auto-actions-enabled="autoActionsEnabled"
            :pending-actions="pendingActions"
            :format-summary-content="formatSummaryContent"
            @force-analysis="handleForceAnalysis"
            @toggle-auto-mode="handleToggleAutoMode"
            class="h-full"
          />
        </div>
      </div>
    </div>

    <!-- Remove AudioUploadPlayer - it's now handled in TranscriptionPanel -->

    <!-- Floating Audio Simulation Player -->
    <AudioSimulationPlayer 
      v-if="isSimulateMode" 
      @close="isSimulateMode = false"
      @segments-updated="handleSimulationSegmentsUpdated"
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

