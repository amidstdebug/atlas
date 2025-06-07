import { ref, computed } from 'vue'

export interface InvestigationState {
  isInvestigating: boolean
  messages: ChatMessage[]
  error: string | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  relevantSegments?: any[]
}

export interface TimeRange {
  start: number | null
  end: number | null
}

export interface InvestigationRequest {
  transcription: string
  question: string
  startTime?: number
  endTime?: number
  context?: string
}

export const useInvestigation = () => {
  const state = ref<InvestigationState>({
    isInvestigating: false,
    messages: [],
    error: null
  })

  const selectedTimeRange = ref<TimeRange>({
    start: null,
    end: null
  })

  const askQuestion = async (
    question: string,
    transcription: string,
    timeRange?: TimeRange,
    context?: string
  ) => {
    if (!question.trim()) {
      state.value.error = 'Please enter a question'
      return
    }

    state.value.isInvestigating = true
    state.value.error = null

    // Add user message
    const userMessage: ChatMessage = {
      role: 'user',
      content: question,
      timestamp: new Date().toISOString()
    }
    state.value.messages.push(userMessage)

    try {
      const { $api } = useNuxtApp()
      const response = await $api.post('/investigate', {
        transcription,
        question,
        start_time: timeRange?.start || undefined,
        end_time: timeRange?.end || undefined,
        context: context || undefined
      })

      if (response.data?.answer) {
        // Add assistant response
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: response.data.answer,
          timestamp: new Date().toISOString(),
          relevantSegments: response.data.relevant_segments || []
        }
        state.value.messages.push(assistantMessage)

        return response.data
      }
    } catch (error: any) {
      console.error('Investigation error:', error)
      state.value.error = error.response?.data?.detail || 'Investigation failed'
      
      // Add error message
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'I apologize, but I encountered an error while processing your question. Please try again.',
        timestamp: new Date().toISOString()
      }
      state.value.messages.push(errorMessage)
      
      throw error
    } finally {
      state.value.isInvestigating = false
    }
  }

  const setTimeRange = (start: number | null, end: number | null) => {
    selectedTimeRange.value = { start, end }
  }

  const clearTimeRange = () => {
    selectedTimeRange.value = { start: null, end: null }
  }

  const clearMessages = () => {
    state.value.messages = []
    state.value.error = null
  }

  const formatTimeRange = (timeRange: TimeRange): string => {
    if (!timeRange.start && !timeRange.end) {
      return 'All time'
    }
    
    const formatTime = (seconds: number) => {
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = Math.floor(seconds % 60)
      return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
    }

    if (timeRange.start && timeRange.end) {
      return `${formatTime(timeRange.start)} - ${formatTime(timeRange.end)}`
    } else if (timeRange.start) {
      return `From ${formatTime(timeRange.start)}`
    } else if (timeRange.end) {
      return `Until ${formatTime(timeRange.end)}`
    }
    
    return 'All time'
  }

  const getFilteredTranscription = (transcription: string, segments: any[], timeRange: TimeRange): string => {
    if (!timeRange.start && !timeRange.end) {
      return transcription
    }

    const filtered = segments.filter(segment => {
      if (timeRange.start && segment.start < timeRange.start) return false
      if (timeRange.end && segment.end > timeRange.end) return false
      return true
    })

    return filtered.map(segment => segment.text).join(' ')
  }

  return {
    state: computed(() => state.value),
    selectedTimeRange: computed(() => selectedTimeRange.value),
    messages: computed(() => state.value.messages),
    isInvestigating: computed(() => state.value.isInvestigating),
    error: computed(() => state.value.error),
    askQuestion,
    setTimeRange,
    clearTimeRange,
    clearMessages,
    formatTimeRange,
    getFilteredTranscription
  }
}