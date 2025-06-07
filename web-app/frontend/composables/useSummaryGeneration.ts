import { ref, computed } from 'vue'

export interface SummaryState {
  isGenerating: boolean
  lastSummary: string
  autoSummary: boolean
  error: string | null
}

export const useSummaryGeneration = () => {
  const state = ref<SummaryState>({
    isGenerating: false,
    lastSummary: '',
    autoSummary: false,
    error: null
  })

  const autoReport = ref(false)
  const autoReportInterval = ref(30) // minutes
  const nextReportCountdown = ref(0)
  let reportTimer: NodeJS.Timeout | null = null

  const generateSummary = async (transcriptionText: string, previousReport?: string) => {
    state.value.isGenerating = true
    state.value.error = null

    try {
      const { $api } = useNuxtApp()
      const response = await $api.post('/summary', {
        transcription: transcriptionText,
        previous_report: previousReport || '',
        summary_mode: 'atc' // default mode
      })

      if (response.data?.message?.content) {
        state.value.lastSummary = response.data.message.content
      }
    } catch (error) {
      state.value.error = 'Summary generation failed: ' + (error as Error).message
    } finally {
      state.value.isGenerating = false
    }
  }

  const toggleAutoSummary = () => {
    state.value.autoSummary = !state.value.autoSummary
  }

  const toggleAutoReport = () => {
    autoReport.value = !autoReport.value
    
    if (autoReport.value) {
      startReportTimer()
    } else {
      stopReportTimer()
    }
  }

  const setAutoReportInterval = (minutes: number) => {
    autoReportInterval.value = minutes
    if (autoReport.value) {
      stopReportTimer()
      startReportTimer()
    }
  }

  const startReportTimer = () => {
    if (reportTimer) clearInterval(reportTimer)
    
    nextReportCountdown.value = autoReportInterval.value * 60 // convert to seconds
    
    reportTimer = setInterval(() => {
      nextReportCountdown.value--
      
      if (nextReportCountdown.value <= 0) {
        // Trigger auto-report generation
        const transcriptionStore = useTranscriptionStore()
        const currentTranscription = transcriptionStore.getAllTranscriptionText()
        if (currentTranscription) {
          generateSummary(currentTranscription, state.value.lastSummary)
        }
        nextReportCountdown.value = autoReportInterval.value * 60
      }
    }, 1000)
  }

  const stopReportTimer = () => {
    if (reportTimer) {
      clearInterval(reportTimer)
      reportTimer = null
    }
    nextReportCountdown.value = 0
  }

  const formatSummaryContent = (content: string) => {
    // Basic formatting for display
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>')
  }

  return {
    state: computed(() => state.value),
    autoReport: computed(() => autoReport.value),
    autoReportInterval: computed(() => autoReportInterval.value),
    nextReportCountdown: computed(() => nextReportCountdown.value),
    generateSummary,
    toggleAutoSummary,
    toggleAutoReport,
    setAutoReportInterval,
    formatSummaryContent
  }
}