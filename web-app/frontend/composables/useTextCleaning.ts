import { ref, computed } from 'vue'

export interface CleanedSegment {
  index: number
  originalText: string
  cleanedText: string
  isProcessing: boolean
  error?: string
}

export const useTextCleaning = () => {
  const cleanedSegments = ref<Map<number, CleanedSegment>>(new Map())
  const isCleanMode = ref(false)

  const cleanTextBlock = async (text: string, segmentIndex: number): Promise<string> => {
    try {
      // Mark as processing
      cleanedSegments.value.set(segmentIndex, {
        index: segmentIndex,
        originalText: text,
        cleanedText: '',
        isProcessing: true
      })

      const { $api } = useNuxtApp()
      const response = await $api.post('/clean-text', {
        text: text
      })

      const cleanedText = response.data?.cleaned_text || text

      // Update with cleaned result
      cleanedSegments.value.set(segmentIndex, {
        index: segmentIndex,
        originalText: text,
        cleanedText,
        isProcessing: false
      })

      return cleanedText
    } catch (error: any) {
      console.error('Text cleaning failed:', error)
      
      // Update with error
      cleanedSegments.value.set(segmentIndex, {
        index: segmentIndex,
        originalText: text,
        cleanedText: text, // Fallback to original text
        isProcessing: false,
        error: error.response?.data?.detail || 'Cleaning failed'
      })

      return text // Return original text on error
    }
  }

  const getDisplayText = (segmentIndex: number, originalText: string): string => {
    if (!isCleanMode.value) {
      return originalText
    }

    const cleaned = cleanedSegments.value.get(segmentIndex)
    if (!cleaned) {
      return originalText
    }

    if (cleaned.isProcessing) {
      return originalText + ' [cleaning...]'
    }

    return cleaned.cleanedText || originalText
  }

  const isSegmentProcessing = (segmentIndex: number): boolean => {
    const cleaned = cleanedSegments.value.get(segmentIndex)
    return cleaned?.isProcessing || false
  }

  const toggleCleanMode = () => {
    isCleanMode.value = !isCleanMode.value
  }

  const clearCleanedSegments = () => {
    cleanedSegments.value.clear()
  }

  return {
    isCleanMode: computed(() => isCleanMode.value),
    cleanedSegments: computed(() => cleanedSegments.value),
    cleanTextBlock,
    getDisplayText,
    isSegmentProcessing,
    toggleCleanMode,
    clearCleanedSegments
  }
}