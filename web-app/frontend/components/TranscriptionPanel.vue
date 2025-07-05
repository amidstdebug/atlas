<script setup lang="ts">
import { Clock, FileAudio } from 'lucide-vue-next'
import { nextTick, ref } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'

interface TranscriptionSegment {
  text: string
  start: number
  end: number
}

interface Props {
  segments: TranscriptionSegment[]
  isTranscribing: boolean
  isRecording?: boolean
  audioLevel?: number
  isWaitingForTranscription?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  updateSegment: [index: number, text: string]
}>()

// Editing state
const editingSegment = ref<number | null>(null)
const editingText = ref('')

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
        textarea.style.height = 'auto'
        textarea.style.height = `${textarea.scrollHeight}px`
        textarea.focus()
        textarea.select()
      }
    }
  })
}

function saveEdit() {
  if (editingSegment.value !== null) {
    emit('updateSegment', editingSegment.value, editingText.value)
    editingSegment.value = null
    editingText.value = ''
  }
}

function cancelEdit() {
  editingSegment.value = null
  editingText.value = ''
}

function handleBlur() {
  saveEdit()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    saveEdit()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    cancelEdit()
  }
}
</script>

<template>
  <Card class="h-[700px] flex flex-col border-0 shadow-xl bg-card/50 backdrop-blur-sm overflow-hidden">
    <!-- Status Indicator -->
    <div v-if="props.isRecording || props.isWaitingForTranscription" class="absolute top-2 right-4 z-10">
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
        <!-- Waiting indicator -->
        <div v-if="props.isWaitingForTranscription" class="flex items-center space-x-2">
          <div class="w-2 h-2 rounded-full bg-blue-500 animate-spin border border-blue-300"></div>
          <span class="text-xs font-medium text-blue-600 dark:text-blue-400">Processing</span>
        </div>
      </div>
    </div>

    <CardHeader class="pb-4">
      <div class="flex items-center space-x-3">
        <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
          <FileAudio class="h-5 w-5 text-blue-600 dark:text-blue-400" />
        </div>
        <div>
          <CardTitle class="text-lg">Live Transcription</CardTitle>
          <p class="text-sm text-muted-foreground">Real-time audio analysis</p>
        </div>
      </div>
    </CardHeader>
    <CardContent class="flex-1 overflow-hidden">
      <div v-if="segments.length > 0" class="h-full">
        <!-- Transcription Timeline -->
        <div class="h-full overflow-y-auto pr-4 relative">
          <div class="absolute top-4 bottom-4 w-0.5 bg-blue-500/10" style="left: 40px;"></div>

          <div class="relative z-10">
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
                      @keydown="handleKeydown"
                      @input="handleTextareaInput"
                      @blur="handleBlur"
                      class="w-full text-sm leading-relaxed bg-transparent border-0 p-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:bg-muted/30 rounded-lg"
                      placeholder="Edit transcription..."
                      rows="1"
                    />
                  </template>
                  <template v-else>
                    <!-- Display mode -->
                    <div
                      class="text-sm leading-relaxed text-foreground/90 p-2 rounded-lg cursor-text hover:bg-muted/30 transition-colors border border-transparent hover:border-muted"
                      @click="startEditing(index, segment.text)"
                    >
                      <span v-if="segment.text">{{ segment.text }}</span>
                      <span v-else class="text-muted-foreground italic">Click to edit...</span>
                    </div>
                  </template>
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
          <p class="text-muted-foreground max-w-xs">
            Upload an audio recording (MP3, WAV, or other formats) or start live recording to begin transcription
          </p>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<style scoped>
/* Segment transition animations */
.segment-enter-active,
.segment-leave-active {
  transition: all 0.3s ease-out;
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

/* Recording activity animations - removed since we use reactive audio levels */
</style>