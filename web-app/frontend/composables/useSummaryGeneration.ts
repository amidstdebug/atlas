import { ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useTranscriptionStore } from '@/stores/transcription'

interface SummaryState {
  isGenerating: boolean
  lastSummary: string
  error: string | null
}

interface AutoReportConfig {
  enabled: boolean
  customPrompt: string
  summaryMode: string
  formatTemplate?: string
}

export const useSummaryGeneration = (reactiveSegments: Ref<any[]>) => {
  const transcriptionStore = useTranscriptionStore()

  const state = ref<SummaryState>({
    isGenerating: false,
    lastSummary: '',
    error: null
  })

  const autoReportConfig = ref<AutoReportConfig>({
    enabled: false,
    customPrompt: '',
    summaryMode: 'atc',
    formatTemplate: ''
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
    formatTemplate?: string
  ) => {
    if (!transcriptionText.trim()) {
      state.value.error = 'No transcription text provided'
      return null
    }

    // Always ensure we have a prompt - use default if none provided
    const effectivePrompt = customPrompt?.trim() || 'Extract pending items and emergencies from transcription. Focus on safety issues and required actions.'

    state.value.isGenerating = true
    state.value.error = null

    try {
      // Get the Nuxt app instance
      const nuxtApp = (globalThis as any).$nuxt || (window as any).$nuxt
      if (!nuxtApp) {
        throw new Error('Nuxt app not available')
      }
      const { $api } = nuxtApp

      if (structured) {
        // Use the new structured summary endpoint
        const requestPayload = {
          transcription: transcriptionText,
          transcription_segments: transcriptionSegments?.map(seg => ({
            text: seg.text,
            start: seg.start,
            end: seg.end
          })) || [],
          custom_prompt: effectivePrompt,  // Always provided now
          format_template: formatTemplate || autoReportConfig.value.formatTemplate || undefined,
          previous_report: previousReport || undefined,
          summary_mode: summaryMode,
          structured: true
        }

        console.log('Structured summary request:', requestPayload)

        const response = await $api.post('/summary/structured', requestPayload)

        if (response.data?.structured_summary) {
          const summaryData = response.data.structured_summary
          
          // Convert structured data to a readable format for display
          const summaryText = formatStructuredSummary(summaryData)
          state.value.lastSummary = summaryText

          // Store in transcription store
          transcriptionStore.addSummary({
            id: Date.now().toString(),
            summary: summaryText,
            structured_summary: summaryData,
            timestamp: new Date().toISOString()
          })

          return response.data
        }
      } else {
        // Optimized settings for small model
        const messages = [
          { role: 'system', content: effectivePrompt },  // Always provided now
          { role: 'user', content: transcriptionText.slice(-2000) }  // Limit context for small model
        ]

        console.log('Traditional summary messages:', messages)

        const response = await $api.post('/v1/chat/completions', {
          messages,
          stream: false,
          temperature: 0.0,
          max_tokens: 256  // Smaller output for efficiency
        })

        if (response.data?.choices) {
          const summaryText = response.data.choices[0]?.message?.content || ''
          state.value.lastSummary = summaryText

          // Store in transcription store
          transcriptionStore.addSummary({
            id: Date.now().toString(),
            summary: summaryText,
            timestamp: new Date().toISOString()
          })

          return response.data
        }
      }
    } catch (error: any) {
      console.error('Summary generation error:', error)
      state.value.error = error.response?.data?.detail || 'Summary generation failed'
      throw error
    } finally {
      state.value.isGenerating = false
    }
  }

  const formatStructuredSummary = (structuredData: any): string => {
    let formatted = '**STRUCTURED INCIDENT ANALYSIS**\n\n'
    
    // Format pending information
    if (structuredData.pending_information && structuredData.pending_information.length > 0) {
      formatted += '**PENDING INFORMATION:**\n'
      structuredData.pending_information.forEach((item: any, index: number) => {
        formatted += `${index + 1}. **${item.description}**\n`
        if (item.eta_etr_info) formatted += `   ETA/ETR: ${item.eta_etr_info}\n`
        if (item.calculated_time) formatted += `   Calculated Time: ${item.calculated_time}\n`
        formatted += `   Priority: ${item.priority || 'medium'}\n`
        if (item.timestamps && item.timestamps.length > 0) {
          formatted += `   Timestamps: ${item.timestamps.map((t: any) => `${t.start}s-${t.end}s`).join(', ')}\n`
        }
        formatted += '\n'
      })
    }

    // Format emergency information
    if (structuredData.emergency_information && structuredData.emergency_information.length > 0) {
      formatted += '**EMERGENCY INFORMATION:**\n'
      structuredData.emergency_information.forEach((item: any, index: number) => {
        formatted += `${index + 1}. **${item.category}: ${item.description}**\n`
        formatted += `   Severity: ${item.severity || 'high'}\n`
        formatted += `   Immediate Action Required: ${item.immediate_action_required ? 'Yes' : 'No'}\n`
        if (item.timestamps && item.timestamps.length > 0) {
          formatted += `   Timestamps: ${item.timestamps.map((t: any) => `${t.start}s-${t.end}s`).join(', ')}\n`
        }
        formatted += '\n'
      })
    }

    if (structuredData.pending_information.length === 0 && structuredData.emergency_information.length === 0) {
      formatted += 'No significant incidents or pending items identified.\n'
    }

    return formatted
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

    console.log('[Auto-Report] Attempting to send API request for structured summary generation.')
    try {
      await generateSummary(
        currentTranscription,
        autoReportConfig.value.summaryMode,
        autoReportConfig.value.customPrompt,
        state.value.lastSummary,
        true, // structured
        segments, // use the determined segments
        autoReportConfig.value.formatTemplate // pass format template
      )
    } catch (error) {
      console.error('Auto-report generation failed:', error)
    }
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

  const setCustomPrompt = (prompt: string) => {
    autoReportConfig.value.customPrompt = prompt
  }

  const setFormatTemplate = (template: string) => {
    autoReportConfig.value.formatTemplate = template
  }

  const formatSummaryContent = (content: string): string => {
    return content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>')
  }

  const cleanup = () => {
    state.value.isGenerating = false
    state.value.error = null
  }

  return {
    state,
    autoReportConfig,
    generateSummary,
    generateAutoReport,
    toggleAutoReport,
    updateAutoReportConfig,
    setCustomPrompt,
    setFormatTemplate,
    formatSummaryContent,
    cleanup
  }
}