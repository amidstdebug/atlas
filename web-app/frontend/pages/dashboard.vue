<script setup lang="ts">
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
import HealthStatusModal from '@/components/HealthStatusModal.vue'
import NERLegendModal from '@/components/NERLegendModal.vue'
import HealthCheckOverlay from '@/components/HealthCheckOverlay.vue'
import { useBackendHealth } from '@/composables/useBackendHealth'
import { watch, computed, ref, onMounted, onUnmounted } from 'vue'

// definePageMeta({
//   middleware: 'auth'
// })

let pollingLogInterval: any = null

// Authentication store
const authStore = useAuthStore()

// Backend health state
const {
  isCheckingBackendHealth,
  backendHealthy,
  backendError,
  isDashboardDisabled,
  retryBackendConnection
} = useBackendHealth()

// Stores and composables
const transcriptionStore = useTranscriptionStore()

// Simulate mode state
const isSimulateMode = ref(false)

// Watch simulate mode changes to automatically start/stop recording
watch(isSimulateMode, (newValue) => {
  console.log(`[Simulate] Mode changed to: ${newValue}`)
  if (!newValue) {
    // Stopped simulating - could clear transcription or leave it
    console.log('[Simulate] 🛑 Simulation mode stopped')
  } else {
    console.log('[Simulate] ▶️ Simulation mode started')
    // Clear existing transcription when simulation starts
    clearTranscription()
    console.log('[Simulate] 🧹 Cleared existing transcription for simulation')
  }
})

const handleSimulationSegmentsUpdated = (segments: any[]) => {
  console.log('[Simulate] 📝 Updated transcription segments from simulation:', segments.length)
  
  // Replace the existing transcription segments with simulation segments
  transcriptionSegments.value.splice(0, transcriptionSegments.value.length, ...segments)
  
  console.log('[Simulate] ✅ Transcription segments updated in UI:', transcriptionSegments.value.length)
}

// Configuration state
const isConfigPanelOpen = ref(false)
const isHealthModalOpen = ref(false)
const isNerLegendModalOpen = ref(false)
const customPrompt = ref('Extract pending items and emergencies from transcription. Focus on safety issues and required actions.')
const customWhisperPrompt = ref('')
const customFormatTemplate = ref('')
const autoReportEnabled = ref(false) // UI state only, copies from composable
const autoReportIntervalValue = ref(30)

// Audio recording setup (after configuration variables are declared)
const {
  state: recordingState,
  transcriptionSegments,
  startRecording,
  stopRecording,
  toggleRecording,
  transcribeFile,
  clearTranscription,
  updateSegment
} = useAudioRecording(customWhisperPrompt)

const {
  state: summaryState,
  autoReportConfig,
  generateSummary,
  generateAutoReport,
  toggleAutoReport,
  updateAutoReportConfig,
  setCustomPrompt,
  setFormatTemplate,
  formatSummaryContent,
  cleanup
} = useSummaryGeneration(transcriptionSegments)

// Sidebar resizing state
const sidebarWidth = ref(320)
const isResizing = ref(false)
const minWidth = 250
const maxWidth = 600



// -------------------------------
// 1.  Restore & sync on mount
// -------------------------------
onMounted(async () => {
  // Validate the authentication token
  await validateAuthToken()

  if (process.client) {
    const savedPrompt             = localStorage.getItem('atlas-custom-prompt')
    const savedWhisperPrompt      = localStorage.getItem('atlas-custom-whisper-prompt')
    const savedFormatTemplate     = localStorage.getItem('atlas-custom-format-template')
    const savedAutoReportEnabled  = localStorage.getItem('atlas-auto-report-enabled')
    const savedAutoReportInterval = localStorage.getItem('atlas-auto-report-interval')

    if (savedPrompt) {
      customPrompt.value = savedPrompt
    }
    if (savedWhisperPrompt) {
      customWhisperPrompt.value = savedWhisperPrompt
    }
    if (savedFormatTemplate) {
      customFormatTemplate.value = savedFormatTemplate
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
      customPrompt: customPrompt.value,
      formatTemplate: customFormatTemplate.value
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

watch(customWhisperPrompt, (newValue) => {
  if (process.client) {
    localStorage.setItem('atlas-custom-whisper-prompt', newValue)
  }
})

watch(customFormatTemplate, (newValue) => {
  if (process.client) {
    localStorage.setItem('atlas-custom-format-template', newValue)
    setFormatTemplate(newValue)
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

// Get auto report enabled state - single source of truth
const autoSummaryEnabled = computed(() => autoReportConfig.value.enabled)

// Mock investigation composable for now
const actionsState = ref({ isGenerating: false })
const pendingActions = ref([])
const autoActionsEnabled = ref(false)
const generateActions = () => {
  console.log('Generate actions called')
}
const completeAction = () => {
  console.log('Complete action called')
}
const toggleAutoActions = () => {}

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

function openHealthModal() {
  isHealthModalOpen.value = true
}

function openNerLegendModal() {
  isNerLegendModalOpen.value = true
}

function resetConfig() {
  customPrompt.value = 'Extract pending items and emergencies from transcription. Focus on safety issues and required actions.'
  customWhisperPrompt.value = ''
  customFormatTemplate.value = ''
  autoReportEnabled.value = false
  autoReportIntervalValue.value = 30

  // Reset composable state
  updateAutoReportConfig({
    enabled: false,
    customPrompt: customPrompt.value,
    formatTemplate: ''
  })
}

function handleApplySettings() {
  // Update all auto-report configuration
  updateAutoReportConfig({
    enabled: autoReportEnabled.value,
    customPrompt: customPrompt.value,
    formatTemplate: customFormatTemplate.value
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

  // Validate token by attempting to refresh it
  const refreshSuccessful = await authStore.refreshToken()
  if (!refreshSuccessful) {
    console.log('[Auth] Token refresh failed, user will be redirected to login')
    // The refreshToken method already handles logout and redirect on failure
  } else {
    console.log('[Auth] Token validation/refresh successful')
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


function handleForceAnalysis() {
  if (aggregatedTranscription.value) {
    handleGenerateSummary()
  }
}

function handleToggleAutoMode() {
  autoReportEnabled.value = !autoReportEnabled.value
}

// Create computed property to convert recordingState for TranscriptionPanel
const transcriptionPanelRecordingState = computed(() => ({
  isRecording: recordingState.value.isRecording,
  isTranscribing: recordingState.value.isTranscribing,
  audioLevel: recordingState.value.audioLevel,
  isWaitingForTranscription: recordingState.value.isWaitingForTranscription,
  waitingForStop: recordingState.value.waitingForStop,
  error: recordingState.value.error || undefined // Convert null to undefined
}))

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
    <!-- Backend Health Check Overlay -->
    <HealthCheckOverlay
      :is-checking="isCheckingBackendHealth"
      :is-healthy="backendHealthy"
      :error="backendError"
      @retry="retryBackendConnection"
    />

    <!-- Main Dashboard Content (disabled when backend unhealthy) -->
    <div class="flex-1 flex flex-col" :class="{ 'pointer-events-none opacity-50': isDashboardDisabled }">
      <!-- Header -->
      <HeaderBar
        :username="authStore.user?.username"
        @logout="logout"
        @open-config="openConfigPanel"
        @open-health-modal="openHealthModal"
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
            <div class="w-4 h-4 rounded-full border-2 border-green-500 border-t-transparent animate-spin"></div>
            <span class="text-sm text-muted-foreground">Generating incident analysis...</span>
          </div>
        </div>
      </div>

      <!-- Main Content -->
      <div class="flex-1 flex overflow-hidden m-3 border border-gray-100 rounded-lg">
        <!-- Left Panel - Transcription -->
        <div 
          class="flex-shrink-0 flex flex-col overflow-hidden"
          :style="{ width: `${sidebarWidth}px` }"
        >
          <TranscriptionPanel
            :segments="transcriptionSegments"
            :is-transcribing="recordingState.isTranscribing"
            :is-recording="recordingState.isRecording"
            :audio-level="recordingState.audioLevel"
            :is-waiting-for-transcription="recordingState.isWaitingForTranscription"
            :recording-state="transcriptionPanelRecordingState"
            :sidebar-width="sidebarWidth"
            :is-simulate-mode="isSimulateMode"
            @update-segment="handleUpdateSegment"
            @update:is-simulate-mode="isSimulateMode = $event"
            @start-recording="handleToggleRecording"
            @stop-recording="handleToggleRecording"
            @toggle-recording="handleToggleRecording"
            @clear-transcription="handleClearTranscription"
            @open-ner-legend="openNerLegendModal"
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
            :auto-report-enabled="autoReportEnabled"
            :format-summary-content="formatSummaryContent"
            @force-analysis="handleForceAnalysis"
            @toggle-auto-mode="handleToggleAutoMode"
            class="h-full"
          />
        </div>
      </div>
    </div>

    <!-- Floating Audio Simulation Player -->
    <AudioSimulationPlayer
      v-if="isSimulateMode && backendHealthy"
      @close="isSimulateMode = false"
      @segments-updated="handleSimulationSegmentsUpdated"
      :custom-whisper-prompt="customWhisperPrompt"
    />

    <!-- Health Status Modal -->
    <HealthStatusModal
      v-model:is-open="isHealthModalOpen"
    />

    <!-- NER Legend Modal -->
    <NERLegendModal
      v-model:is-open="isNerLegendModalOpen"
    />

    <!-- Prompt Configuration Panel -->
    <ConfigPanel
      v-model:is-open="isConfigPanelOpen"
      v-model:custom-summary-prompt="customPrompt"
      v-model:custom-whisper-prompt="customWhisperPrompt"
      v-model:custom-format-template="customFormatTemplate"
      @apply="handleApplySettings"
      @reset="resetConfig"
    />
  </div>
</template>

