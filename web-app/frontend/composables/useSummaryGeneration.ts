import { ref, computed } from 'vue'
import { useTranscriptionStore } from '@/stores/transcription'

export interface SummaryState {
  isGenerating: boolean
  lastSummary: string
  autoSummary: boolean
  error: string | null
}

export interface AutoReportConfig {
  enabled: boolean
  interval: number // minutes
  customPrompt?: string
  summaryMode: string
}

export const useSummaryGeneration = () => {
  const state = ref<SummaryState>({
    isGenerating: false,
    lastSummary: '',
    autoSummary: false,
    error: null
  })

  const autoReportConfig = ref<AutoReportConfig>({
    enabled: false,
    interval: 30,
    customPrompt: '',
    summaryMode: 'atc'
  })

  const nextReportCountdown = ref(0)
  let reportTimer: NodeJS.Timeout | null = null

  const generateSummary = async (
    transcriptionText: string,
    summaryMode: string = 'atc',
    customPrompt?: string,
    previousReport?: string
  ) => {
    if (!transcriptionText.trim()) {
      state.value.error = 'No transcription text provided'
      return null
    }

    state.value.isGenerating = true
    state.value.error = null

    try {
      const { $api } = useNuxtApp()
      const response = await $api.post('/summary', {
        transcription: transcriptionText,
        previous_report: previousReport || '',
        summary_mode: summaryMode,
        custom_prompt: customPrompt || undefined
      })

      if (response.data?.summary) {
        state.value.lastSummary = response.data.summary

        // Store in transcription store
        const transcriptionStore = useTranscriptionStore()
        transcriptionStore.addSummary({
          id: Date.now().toString(),
          summary: response.data.summary,
          timestamp: new Date().toISOString()
        })

        return response.data
      }
    } catch (error: any) {
      console.error('Summary generation error:', error)
      state.value.error = error.response?.data?.detail || 'Summary generation failed'
      throw error
    } finally {
      state.value.isGenerating = false
    }
  }

  const generateAutoReport = async () => {
    const transcriptionStore = useTranscriptionStore()
    const currentTranscription = transcriptionStore.getTranscription

    if (!currentTranscription) {
      console.warn('No transcription available for auto-report')
      return
    }

    try {
      await generateSummary(
        currentTranscription,
        autoReportConfig.value.summaryMode,
        autoReportConfig.value.customPrompt,
        state.value.lastSummary
      )
    } catch (error) {
      console.error('Auto-report generation failed:', error)
    }
  }

  const toggleAutoSummary = () => {
    state.value.autoSummary = !state.value.autoSummary
  }

  const toggleAutoReport = () => {
    autoReportConfig.value.enabled = !autoReportConfig.value.enabled

    if (autoReportConfig.value.enabled) {
      startReportTimer()
    } else {
      stopReportTimer()
    }
  }

  const updateAutoReportConfig = (config: Partial<AutoReportConfig>) => {
    const wasEnabled = autoReportConfig.value.enabled

    autoReportConfig.value = {
      ...autoReportConfig.value,
      ...config
    }

    // Restart timer if enabled and interval changed
    if (autoReportConfig.value.enabled) {
      if (!wasEnabled || config.interval) {
        stopReportTimer()
        startReportTimer()
      }
    }
  }

  const setAutoReportInterval = (minutes: number) => {
    updateAutoReportConfig({ interval: minutes })
  }

  const setCustomPrompt = (prompt: string) => {
    updateAutoReportConfig({ customPrompt: prompt })
  }

  const startReportTimer = () => {
    if (reportTimer) clearInterval(reportTimer)

    nextReportCountdown.value = autoReportConfig.value.interval * 60 // convert to seconds

    reportTimer = setInterval(() => {
      nextReportCountdown.value--

      if (nextReportCountdown.value <= 0) {
        // Trigger auto-report generation
        generateAutoReport()
        nextReportCountdown.value = autoReportConfig.value.interval * 60
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
    if (!content) return ''
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>')
  }

  // Cleanup on unmount
  const cleanup = () => {
    stopReportTimer()
  }

  return {
    state: computed(() => state.value),
    autoReportConfig: computed(() => autoReportConfig.value),
    autoReport: computed(() => autoReportConfig.value.enabled),
    autoReportInterval: computed(() => autoReportConfig.value.interval),
    nextReportCountdown: computed(() => nextReportCountdown.value),
    generateSummary,
    generateAutoReport,
    toggleAutoSummary,
    toggleAutoReport,
    updateAutoReportConfig,
    setAutoReportInterval,
    setCustomPrompt,
    formatSummaryContent,
    cleanup
  }
}