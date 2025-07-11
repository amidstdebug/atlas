import { ref, computed } from 'vue'

export interface NEREntity {
  text: string
  category: 'IMPORTANT_INFO' | 'WEATHER' | 'TIMES'
  start_pos: number
  end_pos: number
}

export interface ProcessedBlock {
  index: number
  rawText: string
  cleanedText: string
  nerText: string
  entities: NEREntity[]
  isProcessing: boolean
  isProcessed: boolean
  error?: string
}

export const useAdvancedTextProcessing = () => {
  const processedBlocks = ref<Map<number, ProcessedBlock>>(new Map())

  const processTranscriptionBlock = async (text: string, segmentIndex: number): Promise<ProcessedBlock> => {
    try {
      // Mark as processing
      const processingBlock: ProcessedBlock = {
        index: segmentIndex,
        rawText: text,
        cleanedText: '',
        nerText: '',
        entities: [],
        isProcessing: true,
        isProcessed: false
      }
      processedBlocks.value.set(segmentIndex, processingBlock)

      const { $api } = useNuxtApp()
      const response = await $api.post('/process-block', {
        text: text
      })

      const processedBlock: ProcessedBlock = {
        index: segmentIndex,
        rawText: text,
        cleanedText: response.data?.cleaned_text || text,
        nerText: response.data?.ner_text || response.data?.cleaned_text || text,
        entities: response.data?.entities || [],
        isProcessing: false,
        isProcessed: true
      }

      processedBlocks.value.set(segmentIndex, processedBlock)
      return processedBlock

    } catch (error: any) {
      console.error('Block processing failed:', error)
      
      const errorBlock: ProcessedBlock = {
        index: segmentIndex,
        rawText: text,
        cleanedText: text, // Fallback to original text
        nerText: text,
        entities: [],
        isProcessing: false,
        isProcessed: false,
        error: error.response?.data?.detail || 'Processing failed'
      }

      processedBlocks.value.set(segmentIndex, errorBlock)
      return errorBlock
    }
  }

  const getDisplayText = (segmentIndex: number, originalText: string): string => {
    const processed = processedBlocks.value.get(segmentIndex)
    
    if (!processed) {
      return originalText
    }

    if (processed.isProcessing) {
      return processed.cleanedText || originalText
    }

    if (processed.isProcessed && processed.nerText) {
      return processed.nerText
    }

    return processed.cleanedText || originalText
  }

  const getRawText = (segmentIndex: number): string => {
    const processed = processedBlocks.value.get(segmentIndex)
    return processed?.rawText || ''
  }

  const isBlockProcessing = (segmentIndex: number): boolean => {
    const processed = processedBlocks.value.get(segmentIndex)
    return processed?.isProcessing || false
  }

  const isBlockProcessed = (segmentIndex: number): boolean => {
    const processed = processedBlocks.value.get(segmentIndex)
    return processed?.isProcessed || false
  }

  const hasNERHighlights = (segmentIndex: number): boolean => {
    const processed = processedBlocks.value.get(segmentIndex)
    return processed?.entities.length > 0 || false
  }

  const getProcessingStatus = (segmentIndex: number): 'raw' | 'processing' | 'processed' => {
    const processed = processedBlocks.value.get(segmentIndex)
    
    if (!processed) return 'raw'
    if (processed.isProcessing) return 'processing'
    if (processed.isProcessed) return 'processed'
    return 'raw'
  }

  const clearProcessedBlocks = () => {
    processedBlocks.value.clear()
  }

  // Get aggregated text for LLM calls (prefer NER text, fallback to cleaned, then raw)
  const getAggregatedProcessedText = (segments: any[]): string => {
    return segments.map((segment, index) => {
      const processed = processedBlocks.value.get(index)
      if (processed?.nerText) return processed.nerText.replace(/<[^>]*>/g, '') // Strip HTML for LLM
      if (processed?.cleanedText) return processed.cleanedText
      return segment.text
    }).join(' ')
  }

  return {
    processedBlocks: computed(() => processedBlocks.value),
    processTranscriptionBlock,
    getDisplayText,
    getRawText,
    isBlockProcessing,
    isBlockProcessed,
    hasNERHighlights,
    getProcessingStatus,
    getAggregatedProcessedText,
    clearProcessedBlocks
  }
}