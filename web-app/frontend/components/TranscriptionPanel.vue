<script setup lang="ts">
import { Clock, FileAudio, Mic, Upload, Square, RotateCcw, AlertTriangle } from 'lucide-vue-next'
import { nextTick, ref, watch } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { useAdvancedTextProcessing } from '@/composables/useAdvancedTextProcessing'
import NERLegend from './NERLegend.vue'

interface TranscriptionSegment {
  text: string
  start: number
  end: number
  isLive?: boolean
}

interface RecordingState {
  isRecording: boolean
  isTranscribing: boolean
  audioLevel?: number
  isWaitingForTranscription?: boolean
  waitingForStop?: boolean
  error?: string
}

interface Props {
  segments: TranscriptionSegment[]
  isTranscribing: boolean
  isRecording?: boolean
  audioLevel?: number
  isWaitingForTranscription?: boolean
  recordingState: RecordingState
  sidebarWidth?: number
  isSimulateMode?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'updateSegment': [index: number, text: string]
  'uploadRecording': []
  'startRecording': []
  'stopRecording': []
  'toggleRecording': []
  'clearTranscription': []
  'update:isSimulateMode': [value: boolean]
  'open-ner-legend': []
}>()

// Editing state
const editingSegment = ref<number | null>(null)
const editingText = ref('')

// Hover state for raw text tooltip
const showRawTooltip = ref<number | null>(null)

// Advanced text processing functionality
const {
  processTranscriptionBlock,
  getDisplayText,
  getRawText,
  isBlockProcessing,
  isBlockProcessed,
  hasNERHighlights,
  getProcessingStatus,
  clearProcessedBlocks
} = useAdvancedTextProcessing()

// Watch for finalized segments to process them
watch(
  () => props.segments,
  (newSegments, oldSegments) => {
    if (!newSegments || newSegments.length === 0) return

    // Process all finalized segments that haven't been processed yet
    newSegments.forEach((segment, index) => {
      // Only process non-live segments that haven't been processed
      if (!segment.isLive && segment.text.trim() && getProcessingStatus(index) === 'raw') {
        console.log(`[TranscriptionPanel] Processing finalized segment ${index}:`, segment.text.substring(0, 50) + '...')
        processTranscriptionBlock(segment.text, index)
      }
    })
  },
  { deep: true, immediate: true }
)

function handleTextareaInput(event: Event) {
  const textarea = event.target as HTMLTextAreaElement
  textarea.style.height = 'auto'
  textarea.style.height = `${textarea.scrollHeight}px`
}

function formatTimestamp(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) seconds = 0
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function startEditing(index: number, currentText: string) {
  editingSegment.value = index
  editingText.value = currentText
  nextTick(() => {
    const container = document.querySelector(`[data-segment-index="${index}"]`)
    if (container) {
      const textarea = container.querySelector<HTMLTextAreaElement>('textarea')
      if (textarea) {
        textarea.focus()
        textarea.setSelectionRange(textarea.value.length, textarea.value.length)
      }
    }
  })
}

function saveEdit(index: number) {
  if (editingText.value.trim()) {
    emit('updateSegment', index, editingText.value.trim())
  }
  editingSegment.value = null
  editingText.value = ''
}

function cancelEdit() {
  editingSegment.value = null
  editingText.value = ''
}

function handleKeydown(event: KeyboardEvent, index: number) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    saveEdit(index)
  } else if (event.key === 'Escape') {
    event.preventDefault()
    cancelEdit()
  }
}

function handleRecordingToggle() {
  emit('toggleRecording')
}

function handleClearTranscription() {
  clearProcessedBlocks()
  emit('clearTranscription')
}

function handleSimulateModeToggle(value: boolean) {
  emit('update:isSimulateMode', value)
}
</script>

<template>
  <div class="h-[700px] border-0 shadow-xl bg-card/50 backdrop-blur-sm overflow-hidden rounded-lg">
    <!-- Main Transcription Panel -->
    <div class="h-full flex flex-col bg-card relative">
      <!-- Status Indicator -->
      <div v-if="props.isRecording || props.isWaitingForTranscription || props.recordingState.waitingForStop" class="absolute top-2 right-4 z-10">
        <div class="flex items-center space-x-2 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-full px-3 py-1.5 shadow-sm">
          <!-- Recording indicator -->
          <div v-if="props.isRecording" class="flex items-center space-x-2">
            <div
              class="w-2 h-2 rounded-full transition-all duration-150"
              :class="{
                'bg-red-500 animate-pulse': (props.audioLevel || 0) <= 0.1,
                'bg-red-400 scale-125': (props.audioLevel || 0) > 0.1 && (props.audioLevel || 0) <= 0.3,
                'bg-red-500 scale-150': (props.audioLevel || 0) > 0.3 && (props.audioLevel || 0) <= 0.6,
                'bg-red-600 scale-175': (props.audioLevel || 0) > 0.6
              }"
            ></div>
            <span
              class="text-xs font-medium transition-colors duration-150"
              :class="{
                'text-red-600 dark:text-red-400': (props.audioLevel || 0) <= 0.1,
                'text-red-700 dark:text-red-300': (props.audioLevel || 0) > 0.1
              }"
            >
              REC
            </span>
          </div>
          <!-- Waiting for stop indicator -->
          <div v-if="props.recordingState.waitingForStop" class="flex items-center space-x-2">
            <div class="w-2 h-2 rounded-full bg-yellow-500 animate-spin border border-yellow-300"></div>
            <span class="text-xs font-medium text-yellow-600 dark:text-yellow-400">Finalizing</span>
          </div>
          <!-- Waiting indicator -->
          <div v-if="props.isWaitingForTranscription && !props.recordingState.waitingForStop" class="flex items-center space-x-2">
            <div class="w-2 h-2 rounded-full bg-blue-500 animate-spin border border-blue-300"></div>
            <span class="text-xs font-medium text-blue-600 dark:text-blue-400">Processing</span>
          </div>
        </div>
      </div>

      <!-- Sidebar Header -->
      <div class="pb-2 p-4 border-b border-border">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
              <FileAudio class="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h3 class="text-lg font-semibold">Live Transcription</h3>
              <p class="text-sm text-muted-foreground">Real-time audio analysis</p>
            </div>
          </div>
          <!-- NER Legend Button -->
          <NERLegend @open-ner-legend="$emit('open-ner-legend')" />
        </div>

        <!-- Error Display -->
        <div v-if="recordingState.error" class="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
          <div class="flex items-start space-x-2">
            <AlertTriangle class="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <p class="text-sm font-medium text-red-900 dark:text-red-100">Connection Error</p>
              <p class="text-xs text-red-700 dark:text-red-300 mt-1">{{ recordingState.error }}</p>
            </div>
          </div>
        </div>

        <!-- Recording Controls -->
        <div class="flex items-center justify-between mt-3 pt-3 border-t border-border/50">
          <div class="flex items-center space-x-2">
            <!-- Simulate toggle (replaces Upload button) -->
            <div class="flex items-center space-x-2">
              <Switch 
                id="simulate-mode" 
                :checked="props.isSimulateMode" 
                @update:checked="handleSimulateModeToggle"
                :disabled="recordingState.isRecording || recordingState.isTranscribing || recordingState.waitingForStop"
              />
              <Label for="simulate-mode" class="text-sm">Simulate</Label>
            </div>

            <Button
              :disabled="recordingState.waitingForStop || props.isSimulateMode"
              :variant="recordingState.isRecording ? 'destructive' : 'default'"
              size="sm"
              :class="{ 'animate-pulse': recordingState.isRecording || recordingState.waitingForStop }"
              @click="handleRecordingToggle"
            >
              <Mic v-if="!recordingState.isRecording" class="h-3 w-3 mr-2" />
              <Square v-else class="h-3 w-3 mr-2" />
              {{ recordingState.waitingForStop ? 'Finalizing...' : recordingState.isRecording ? 'Stop' : 'Record' }}
            </Button>
          </div>

          <div class="flex items-center space-x-2">
            <Button
              :disabled="recordingState.isRecording || recordingState.isTranscribing || recordingState.waitingForStop"
              variant="ghost"
              size="sm"
              @click="handleClearTranscription"
            >
              <RotateCcw class="h-3 w-3 mr-2" />
              Clear
            </Button>
          </div>
        </div>
      </div>

	  

      <!-- Sidebar Content -->
      <div class="flex-1 overflow-hidden p-4">
        <div v-if="segments.length > 0" class="h-full">
          <!-- Transcription Timeline -->
          <div class="h-full overflow-y-auto pr-4">
            <div class="relative z-10">
              <div class="absolute top-4 bottom-4 w-0.5 bg-blue-500/10" style="left: 40px;"></div>
              <TransitionGroup
                name="segment"
                tag="div"
                class="space-y-4 py-4"
              >
                <div
                  v-for="(segment, index) in segments"
                  :key="`segment-${index}`"
                  :data-segment-index="index"
                  class="grid grid-cols-[80px_1fr] items-start gap-x-4 group"
                >
                  <!-- Timestamp -->
                  <div class="flex justify-center pt-[0.6rem] z-10">
                    <Badge variant="secondary" class="font-mono text-xs">
                      {{ formatTimestamp(segment.start) }}
                    </Badge>
                  </div>

                  <!-- Content -->
                  <div class="w-full relative">
                    <template v-if="editingSegment === index">
                      <!-- Edit mode -->
                      <Textarea
                        v-model="editingText"
                        @keydown="handleKeydown($event, index)"
                        @input="handleTextareaInput"
                        @blur="saveEdit(index)"
                        class="w-full text-sm leading-relaxed bg-transparent border-0 p-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:bg-muted/30 rounded-lg"
                        placeholder="Edit transcription..."
                        rows="1"
                      />
                    </template>
                    <template v-else>
                      <!-- Display mode -->
                      <div
                        class="text-sm leading-relaxed text-foreground/90 p-2 rounded-lg cursor-text hover:bg-muted/30 transition-colors border"
                        :class="{
                          'border-transparent hover:border-muted': !segment.isLive && getProcessingStatus(index) === 'raw',
                          'border-blue-500/50 ring-2 ring-blue-500/20 animate-pulse':
                            segment.isLive && !recordingState.waitingForStop,
                          'border-green-500/50 ring-2 ring-green-500/20 animate-pulse bg-green-50/30 dark:bg-green-900/10':
                            isBlockProcessing(index),
                          'border-purple-400/50 bg-purple-50/30 dark:bg-purple-900/20 cursor-pointer hover:border-purple-400/70 hover:bg-purple-50/50':
                            isBlockProcessed(index) && hasNERHighlights(index),
                          'border-gray-300/50 bg-gray-50/30 dark:bg-gray-800/30':
                            isBlockProcessed(index) && !hasNERHighlights(index)
                        }"
                        @click="startEditing(index, segment.text)"
                      >
                        <!-- Debug info for processed blocks -->
                        <div v-if="isBlockProcessed(index)" class="text-xs text-muted-foreground mb-1 opacity-60">
                          Status: Processed | Has NER: {{ hasNERHighlights(index) ? 'Yes' : 'No' }}
                        </div>

                        <span v-if="segment.text">
                          <!-- Show NER highlighted text if processed, otherwise show original -->
                          <template v-if="isBlockProcessed(index) && hasNERHighlights(index)">
                            <div
                              v-html="getDisplayText(index, segment.text)"
                              class="ner-highlighted-content"
                              @mouseenter="showRawTooltip = index"
                              @mouseleave="showRawTooltip = null"
                            ></div>
                          </template>
                          <template v-else>
                            {{ getDisplayText(index, segment.text) }}
                          </template>
                        </span>
                        <span v-else class="text-muted-foreground italic">Click to edit...</span>
                        <span v-if="segment.isLive && isTranscribing" class="text-muted-foreground">...</span>
                      </div>
                    </template>

                    <!-- Raw Text Tooltip -->
                    <Transition
                      enter-active-class="transition-all duration-200 ease-out"
                      enter-from-class="opacity-0 scale-95"
                      enter-to-class="opacity-100 scale-100"
                      leave-active-class="transition-all duration-150 ease-in"
                      leave-from-class="opacity-100 scale-100"
                      leave-to-class="opacity-0 scale-95"
                    >
                      <div
                        v-if="showRawTooltip === index && getRawText(index)"
                        class="absolute z-50 max-w-sm p-3 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-xs rounded-lg shadow-lg border border-gray-700 dark:border-gray-300 pointer-events-none"
                        style="top: -10px; left: 50%; transform: translateX(-50%) translateY(-100%);"
                      >
                        <div class="font-medium mb-1 text-yellow-300 dark:text-yellow-600">Original Transcription:</div>
                        <div class="leading-relaxed">{{ getRawText(index) }}</div>
                        <!-- Tooltip arrow -->
                        <div class="absolute top-full left-1/2 transform -translate-x-1/2 w-2 h-2 bg-gray-900 dark:bg-gray-100 rotate-45"></div>
                      </div>
                    </Transition>
                  </div>
                </div>
              </TransitionGroup>
            </div>
          </div>
        </div>
        <div v-else class="h-full flex items-center justify-center">
          <div class="text-center space-y-3">
            <div class="w-16 h-16 mx-auto rounded-full bg-muted/50 flex items-center justify-center">
              <FileAudio class="h-8 w-8 text-muted-foreground" />
            </div>
            <p class="text-muted-foreground max-w-xs text-sm">
              Upload an audio recording (MP3, WAV, or other formats) or start live recording to begin transcription
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Floating Audio Simulation Player -->
  </div>
</template>

<style scoped>
/* Segment transition animations */
.segment-enter-active,
.segment-leave-active {
  transition: all 0.3s ease-out;
}

/* NER Entity Highlighting */
.ner-highlighted-content :deep(.ner-identifier) {
  background-color: rgba(250, 204, 21, 0.2); /* Softer yellow */
  color: #a16207; /* Darker, readable text */
  padding: 1px 5px;
  border-radius: 6px;
  font-weight: 500;
  border: 1px solid rgba(250, 204, 21, 0.4);
  box-shadow: none;
}

.ner-highlighted-content :deep(.ner-weather) {
  background-color: rgba(59, 130, 246, 0.15); /* Softer blue */
  color: #1d4ed8;
  padding: 1px 5px;
  border-radius: 6px;
  font-weight: 500;
  border: 1px solid rgba(59, 130, 246, 0.3);
  box-shadow: none;
}

.ner-highlighted-content :deep(.ner-times) {
  background-color: rgba(168, 85, 247, 0.15); /* Softer purple */
  color: #7e22ce;
  padding: 1px 5px;
  border-radius: 6px;
  font-weight: 500;
  border: 1px solid rgba(168, 85, 247, 0.3);
  box-shadow: none;
}

.ner-highlighted-content :deep(.ner-location) {
  background-color: rgba(34, 197, 94, 0.15); /* Softer green */
  color: #15803d;
  padding: 1px 5px;
  border-radius: 6px;
  font-weight: 500;
  border: 1px solid rgba(34, 197, 94, 0.3);
  box-shadow: none;
}

.ner-highlighted-content :deep(.ner-impact) {
  background-color: rgba(239, 68, 68, 0.15); /* Softer red */
  color: #dc2626;
  padding: 1px 5px;
  border-radius: 6px;
  font-weight: 500;
  border: 1px solid rgba(239, 68, 68, 0.3);
  box-shadow: none;
}

/* Dark mode variants */
.dark .ner-highlighted-content :deep(.ner-identifier) {
  background-color: rgba(250, 204, 21, 0.15);
  color: #facc15; /* Brighter yellow for dark mode */
  border-color: rgba(250, 204, 21, 0.3);
}

.dark .ner-highlighted-content :deep(.ner-weather) {
  background-color: rgba(59, 130, 246, 0.15);
  color: #93c5fd; /* Brighter blue for dark mode */
  border-color: rgba(59, 130, 246, 0.3);
}

.dark .ner-highlighted-content :deep(.ner-times) {
  background-color: rgba(168, 85, 247, 0.15);
  color: #c084fc; /* Brighter purple for dark mode */
  border-color: rgba(168, 85, 247, 0.3);
}

.dark .ner-highlighted-content :deep(.ner-location) {
  background-color: rgba(34, 197, 94, 0.15);
  color: #4ade80; /* Brighter green for dark mode */
  border-color: rgba(34, 197, 94, 0.3);
}

.dark .ner-highlighted-content :deep(.ner-impact) {
  background-color: rgba(239, 68, 68, 0.15);
  color: #f87171; /* Brighter red for dark mode */
  border-color: rgba(239, 68, 68, 0.3);
}

.segment-enter-from {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

.segment-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.95);
}

.segment-move {
  transition: transform 0.3s ease-out;
}
</style>