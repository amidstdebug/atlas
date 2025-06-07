<script setup lang="ts">
import { Progress } from '@/components/ui/progress'
import { useAudioRecording } from '@/composables/useAudioRecording'
import { useSummaryGeneration } from '@/composables/useSummaryGeneration'
import { useTranscriptionStore } from '@/stores/transcription'
import { useAuthStore } from '@/stores/auth'
import ConfigPanel from '@/components/ConfigPanel.vue'
import HeaderBar from '@/components/HeaderBar.vue'
import TranscriptionPanel from '@/components/TranscriptionPanel.vue'
import AnalysisPanel from '@/components/AnalysisPanel.vue'
import ActionBar from '@/components/ActionBar.vue'
import { watch } from 'vue'

definePageMeta({
  middleware: 'auth'
})

const authStore = useAuthStore()

// Stores and composables
const transcriptionStore = useTranscriptionStore()
const {
  state: recordingState,
  transcriptionSegments,
  startRecording,
  stopRecording,
  transcribeFile,
  clearTranscription,
  formatTimestamp
} = useAudioRecording()

const {
  state: summaryState,
  generateSummary,
  toggleAutoSummary,
  toggleAutoReport,
  setAutoReportInterval,
  formatSummaryContent,
  autoReport,
  autoReportInterval,
  nextReportCountdown
} = useSummaryGeneration()

// File upload
const audioFileInput = ref<HTMLInputElement>()

// Configuration state
const isConfigPanelOpen = ref(false)
const customPrompt = ref('')
const replaceNumbers = ref(true)
const useIcaoCallsigns = ref(true)
const autoReportEnabled = ref(false) // UI state only, copies from composable
const autoReportIntervalValue = ref(30)


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

    // Set interval in composable
    setAutoReportInterval(autoReportIntervalValue.value)
    if (autoReportEnabled.value !== autoReport) {
      toggleAutoReport()
    }
  }
})

// Watch for changes and save to localStorage
watch(customPrompt, (newValue) => {
  if (process.client) {
    localStorage.setItem('atlas-custom-prompt', newValue)
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
  if (enabled !== autoReport) {
    toggleAutoReport()
  }
})

// Computed
const aggregatedTranscription = computed(() => {
  return transcriptionSegments.value.map(segment => segment.text).join(' ')
})

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
      await transcribeFile(file, replaceNumbers.value, useIcaoCallsigns.value)
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

async function handleGenerateSummary() {
  if (aggregatedTranscription.value) {
    try {
      await generateSummary(
        aggregatedTranscription.value,
        'atc',
        customPrompt.value || undefined
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
  setAutoReportInterval(30)
  if (autoReport) {
    toggleAutoReport()
  }
}

function handleApplySettings() {
  // Update interval setting
  setAutoReportInterval(autoReportIntervalValue.value)

  // Update auto-report state if changed
  if (autoReportEnabled.value !== autoReport) {
    toggleAutoReport()
  }
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
  transcriptionStore.updateSegment(index, text)
}


useHead({
  title: 'ATLAS - Air Incident Investigation'
})
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950 tech-grid-bg">
    <!-- Header -->
    <HeaderBar
      :username="authStore.user?.username"
      @logout="logout"
    />

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-6 py-8">
      <!-- Progress Indicators -->
      <div v-if="recordingState.isTranscribing || summaryState.isGenerating" class="mb-8">
        <div class="max-w-md mx-auto space-y-4">
          <div v-if="recordingState.isTranscribing" class="text-center">
            <p class="text-sm text-muted-foreground mb-3">Processing audio transcription...</p>
            <Progress class="h-2 rounded-full" />
          </div>
          <div v-if="summaryState.isGenerating" class="text-center">
            <p class="text-sm text-muted-foreground mb-3">Generating incident analysis...</p>
            <Progress class="h-2 rounded-full" />
          </div>
        </div>
      </div>

      <!-- Content Grid -->
      <div class="grid grid-cols-1 xl:grid-cols-5 gap-8">
        <!-- Transcription Panel -->
        <div class="xl:col-span-2">
          <TranscriptionPanel
            :segments="transcriptionSegments"
            :is-transcribing="recordingState.isTranscribing"
            :is-recording="recordingState.isRecording"
            :audio-level="recordingState.audioLevel"
            @update-segment="handleUpdateSegment"
          />
        </div>

        <!-- Analysis Panel -->
        <div class="xl:col-span-3">
          <AnalysisPanel
            :summaries="summaries"
            :is-generating="summaryState.isGenerating"
            :auto-report-enabled="autoReportEnabled"
            :next-report-countdown="nextReportCountdown"
            :format-summary-content="formatSummaryContent"
          />
        </div>
      </div>
    </main>

    <!-- Action Bar -->
    <ActionBar
      :recording-state="recordingState"
      :summary-state="summaryState"
      :aggregated-transcription="aggregatedTranscription"
      :auto-report-enabled="autoReportEnabled"
      @upload-recording="uploadRecording"
      @start-recording="handleStartRecording"
      @stop-recording="handleStopRecording"
      @generate-summary="handleGenerateSummary"
      @clear-transcription="handleClearTranscription"
      @open-config="openConfigPanel"
    />

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

