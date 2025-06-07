<script setup lang="ts">
import { Progress } from '@/components/ui/progress'
import { useAudioRecording } from '@/composables/useAudioRecording'
import { useSummaryGeneration } from '@/composables/useSummaryGeneration'
import { useSuggestedActions } from '@/composables/useSuggestedActions'
import { useTranscriptionStore } from '@/stores/transcription'
import { useAuthStore } from '@/stores/auth'
import ConfigPanel from '@/components/ConfigPanel.vue'
import HeaderBar from '@/components/HeaderBar.vue'
import TranscriptionPanel from '@/components/TranscriptionPanel.vue'
import AnalysisPanel from '@/components/AnalysisPanel.vue'
import SuggestedActionsPanel from '@/components/SuggestedActionsPanel.vue'
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
  updateSegment
} = useAudioRecording()

const {
  state: summaryState,
  generateSummary,
  generateAutoReport,
  toggleAutoSummary,
  toggleAutoReport,
  updateAutoReportConfig,
  setAutoReportInterval,
  setCustomPrompt,
  formatSummaryContent,
  autoReport,
  autoReportInterval,
  nextReportCountdown,
  cleanup
} = useSummaryGeneration()

const {
  state: actionsState,
  autoActionsEnabled,
  nextActionsCountdown,
  actions,
  pendingActions,
  criticalActions,
  generateActions,
  completeAction,
  toggleAutoActions,
  formatActionContent,
  shouldTriggerActions,
  cleanup: cleanupActions
} = useSuggestedActions()

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

    // Update composable config
    updateAutoReportConfig({
      enabled: autoReportEnabled.value,
      interval: autoReportIntervalValue.value,
      customPrompt: customPrompt.value
    })
  }
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
    setAutoReportInterval(newValue)
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

// ------------------------------------------------------
// 3. Coordinate between panels (async coordination)
// ------------------------------------------------------
// Watch for new transcription segments and check if actions should be triggered
watch(transcriptionSegments, async (newSegments, oldSegments) => {
  if (!newSegments || newSegments.length === 0) return

  // Only check if we have new segments
  if (!oldSegments || newSegments.length > oldSegments.length) {
    const recentSegments = newSegments.slice(oldSegments?.length || 0)
    const recentText = recentSegments.map(seg => seg.text).join(' ')

    // Check if the new transcription should trigger actions
    if (shouldTriggerActions(recentText, recentSegments)) {
      console.log('Trigger conditions detected, generating suggested actions...')

      // Automatically generate actions when trigger conditions are met
      try {
        await generateActions(
          aggregatedTranscription.value,
          transcriptionSegments.value,
          pendingActions.value
        )
      } catch (error) {
        console.error('Auto-triggered actions generation failed:', error)
      }
    }
  }
}, { deep: true })

// Watch for critical actions and provide user notifications
watch(criticalActions, (newCriticalActions) => {
  if (newCriticalActions && newCriticalActions.length > 0) {
    // Could add toast notifications or other alerts for critical actions
    console.log(`${newCriticalActions.length} critical actions requiring attention`)
  }
}, { deep: true })

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

async function handleGenerateSummary() {
  if (aggregatedTranscription.value) {
    try {
      // Get the latest summary for previous report context
      const latestSummary = summaries.value.length > 0 ? summaries.value[summaries.value.length - 1].summary : undefined

      await generateSummary(
        aggregatedTranscription.value,
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
    interval: 30,
    customPrompt: ''
  })
}

function handleApplySettings() {
  // Update all auto-report configuration
  updateAutoReportConfig({
    enabled: autoReportEnabled.value,
    interval: autoReportIntervalValue.value,
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

// Cleanup on unmount
onUnmounted(() => {
  cleanup()
  cleanupActions()
})

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
    <main class="max-w-screen-2xl mx-auto px-6 py-8">
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
      <div class="grid grid-cols-1 xl:grid-cols-8 gap-8">
        <!-- Transcription Panel -->
        <div class="xl:col-span-2">
          <TranscriptionPanel
            :segments="transcriptionSegments"
            :is-transcribing="recordingState.isTranscribing"
            :is-recording="recordingState.isRecording"
            :audio-level="recordingState.audioLevel"
            :is-waiting-for-transcription="recordingState.isWaitingForTranscription"
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
            :transcription-segments="transcriptionSegments"
            :aggregated-transcription="aggregatedTranscription"
          />
        </div>

        <!-- Suggested Actions Panel -->
        <div class="xl:col-span-3">
          <SuggestedActionsPanel
            :is-generating="actionsState.isGenerating"
            :actions="actions"
            :auto-actions-enabled="autoActionsEnabled"
            :next-actions-countdown="nextActionsCountdown"
            :format-action-content="formatActionContent"
            @complete-action="handleCompleteAction"
            @refresh-actions="handleRefreshActions"
            @toggle-auto-actions="handleToggleAutoActions"
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

