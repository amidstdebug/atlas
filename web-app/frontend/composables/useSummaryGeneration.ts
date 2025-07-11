import { ref, computed, watch } from 'vue'
import { useTranscriptionStore } from '@/stores/transcription'

export interface SummaryState {
  isGenerating: boolean
  lastSummary: string
  autoSummary: boolean
  error: string | null
}

export interface AutoReportConfig {
  enabled: boolean
  // interval: number // No longer needed
  customPrompt?: string
  summaryMode: string
}

export const useSummaryGeneration = (reactiveSegments: Ref<any[]>) => {
  const transcriptionStore = useTranscriptionStore()

  const state = ref<SummaryState>({
    isGenerating: false,
    lastSummary: '',
    autoSummary: false,
    error: null
  })

  const autoReportConfig = ref<AutoReportConfig>({
    enabled: false,
    // interval: 30, // No longer needed
    customPrompt: '',
    summaryMode: 'atc',
  })

  // Watch for changes in the segments array to detect when a segment is finalized.
  watch(
    () => [...reactiveSegments.value], // Watch a shallow copy to get different old/new values
    (newSegments, oldSegments) => {
      if (!autoReportConfig.value.enabled || !newSegments || newSegments.length === 0) {
        return
      }

      console.log(`[Auto-Report Watcher] Segments changed. New length: ${newSegments.length}, Old length: ${oldSegments?.length ?? 0}`);

      // A segment is considered "finalized" if a new segment has been added.
      if (oldSegments && newSegments.length > oldSegments.length) {
        const finalizedSegment = newSegments[newSegments.length - 2];
        console.log(`%c[Auto-Report] Triggered by new finalized segment: "${finalizedSegment.text}"`, 'color: #4CAF50; font-weight: bold;');
        generateAutoReport(newSegments);
      }
    },
    { deep: true }
  )

  const generateSummary = async (
    transcriptionText: string,
    summaryMode: string = 'atc',
    customPrompt?: string,
    previousReport?: string,
    structured: boolean = true,
    transcriptionSegments?: any[],
  ) => {
    if (!transcriptionText.trim()) {
      state.value.error = 'No transcription text provided'
      return null
    }

    state.value.isGenerating = true
    state.value.error = null

    try {
      const { $api } = useNuxtApp()

      // Convert transcription segments to the format expected by the backend
      const segments = transcriptionSegments?.map(seg => ({
        text: seg.text,
        start: seg.start,
        end: seg.end
      }))

      const response = await $api.post('/summary', {
        transcription: transcriptionText,
        transcription_segments: segments || undefined,
        previous_report: previousReport || '',
        summary_mode: summaryMode,
        custom_prompt: customPrompt || undefined,
        structured: structured && summaryMode === 'atc',
      })

      if (response.data?.summary) {
        state.value.lastSummary = response.data.summary

        // Store in transcription store
        const transcriptionStore = useTranscriptionStore()

        transcriptionStore.addSummary({
          id: Date.now().toString(),
          summary: response.data.summary,
          structured_summary: response.data.structured_summary || undefined,
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

  const generateAutoReport = async (segmentsToProcess?: any[]) => {
    const transcriptionStore = useTranscriptionStore()
    // Prioritize segments passed from the watcher, fall back to store for manual triggers.
    const segments = segmentsToProcess || transcriptionStore.getSegments
    const currentTranscription = segments.map((s: any) => s.text).join(' ')

    if (!currentTranscription) {
      console.warn('No transcription available for auto-report')
      return
    }

    console.log('[Auto-Report] Attempting to send API request for summary generation.')
    try {
      await generateSummary(
        currentTranscription,
        autoReportConfig.value.summaryMode,
        autoReportConfig.value.customPrompt,
        state.value.lastSummary,
        true, // structured
        segments, // use the determined segments
        false
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
    console.log(`Auto-report mode ${autoReportConfig.value.enabled ? 'enabled' : 'disabled'}.`);

    // If we just enabled it and there's already transcription, trigger an initial report.
    if (autoReportConfig.value.enabled && transcriptionStore.getTranscription) {
       generateAutoReport()
    }
  }

  const updateAutoReportConfig = (config: Partial<AutoReportConfig>) => {
    autoReportConfig.value = {
      ...autoReportConfig.value,
      ...config
    }
  }

  const setAutoReportInterval = (minutes: number) => {
    // This function is now obsolete but kept to avoid breaking other parts if they reference it.
    // It can be removed in a future cleanup.
    console.warn("setAutoReportInterval is deprecated. Auto-reporting is now segment-driven.")
  }

  const setCustomPrompt = (prompt: string) => {
    updateAutoReportConfig({ customPrompt: prompt })
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
    // No longer anything to clean up
  }

  return {
    state: computed(() => state.value),
    autoReportConfig: computed(() => autoReportConfig.value),
    autoReport: computed(() => autoReportConfig.value.enabled),
    autoReportInterval: computed(() => 0), // Obsolete
    nextReportCountdown: computed(() => 0), // Obsolete
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