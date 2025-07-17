import { ref, computed } from 'vue'
import { NEREntity } from './audio-recording/types'
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

const processedBlocks = ref<Record<number, ProcessedBlock>>({})

export const useAdvancedTextProcessing = () => {

  const processTranscriptionBlock = async (text: string, segmentIndex: number): Promise<ProcessedBlock> => {
    try {
      console.log(`[AdvancedTextProcessing] 🚀 Starting processing for block ${segmentIndex}:`, text.substring(0, 50) + '...')

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
      processedBlocks.value[segmentIndex] = processingBlock
      console.log(`[AdvancedTextProcessing] 📝 Marked block ${segmentIndex} as processing`)

      const { $api } = useNuxtApp()
      console.log(`[AdvancedTextProcessing] 📡 Making API call to /process-block for block ${segmentIndex}`)

      const response = await $api.post('/process-block', {
        text: text
      })

      console.log(`[AdvancedTextProcessing] ✅ API response for block ${segmentIndex}:`, response.data)

      const processedBlock: ProcessedBlock = {
        index: segmentIndex,
        rawText: text,
        cleanedText: response.data?.cleaned_text || text,
        nerText: response.data?.ner_text || response.data?.cleaned_text || text,
        entities: response.data?.entities || [],
        isProcessing: false,
        isProcessed: true
      }

      processedBlocks.value[segmentIndex] = processedBlock
      console.log(`[AdvancedTextProcessing] 🎯 Updated block ${segmentIndex} with processed data:`, {
        hasCleanedText: !!processedBlock.cleanedText,
        hasNerText: !!processedBlock.nerText,
        entitiesCount: processedBlock.entities.length
      })

      return processedBlock

    } catch (error: any) {
      console.error(`[AdvancedTextProcessing] ❌ Block ${segmentIndex} processing failed:`, error)

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

      processedBlocks.value[segmentIndex] = errorBlock
      console.log(`[AdvancedTextProcessing] 🚨 Set error block ${segmentIndex}:`, errorBlock.error)
      return errorBlock
    }
  }

  const getDisplayText = (segmentIndex: number, originalText: string): string => {
    const processed = processedBlocks.value[segmentIndex]

    if (!processed) {
      console.log(`[getDisplayText] Block ${segmentIndex}: No processed data, returning original`)
      return originalText
    }

    if (processed.isProcessing) {
      console.log(`[getDisplayText] Block ${segmentIndex}: Processing, returning cleaned or original`)
      return processed.cleanedText || originalText
    }

    if (processed.isProcessed && processed.nerText) {
      console.log(`[getDisplayText] Block ${segmentIndex}: Processed with NER, returning nerText`)
      console.log(`[getDisplayText] Block ${segmentIndex}: NER Text content:`, processed.nerText)
      console.log(`[getDisplayText] Block ${segmentIndex}: Entities:`, processed.entities)
      console.log(`[getDisplayText] Block ${segmentIndex}: Has NER highlights:`, processed.entities.length > 0)
      return processed.nerText
    }

    console.log(`[getDisplayText] Block ${segmentIndex}: Processed without NER, returning cleanedText`)
    return processed.cleanedText || originalText
  }

  const getRawText = (segmentIndex: number): string => {
    const processed = processedBlocks.value[segmentIndex]
    return processed?.rawText || ''
  }

  const isBlockProcessing = (segmentIndex: number): boolean => {
    const processed = processedBlocks.value[segmentIndex]
    return processed?.isProcessing || false
  }

  const isBlockProcessed = (segmentIndex: number): boolean => {
    const processed = processedBlocks.value[segmentIndex]
    return processed?.isProcessed || false
  }

  const hasNERHighlights = (segmentIndex: number): boolean => {
    const processed = processedBlocks.value[segmentIndex]
    // Check both entities array and if ner_text contains HTML spans
    return (processed?.entities.length > 0) || 
           (processed?.nerText && processed.nerText.includes('<span')) || false
  }

  const getProcessingStatus = (segmentIndex: number): 'raw' | 'processing' | 'processed' => {
    const processed = processedBlocks.value[segmentIndex]

    if (!processed) return 'raw'
    if (processed.isProcessing) return 'processing'
    if (processed.isProcessed) return 'processed'
    return 'raw'
  }

  const clearProcessedBlocks = () => {
    processedBlocks.value = {}
  }

  // Get aggregated text for LLM calls (prefer NER text, fallback to cleaned, then raw)
  const getAggregatedProcessedText = (segments: any[]): string => {
    return segments.map((segment, index) => {
      const processed = processedBlocks.value[index]
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