<script setup lang="ts">
import { Clock, FileAudio, Edit3, Check, X } from 'lucide-vue-next'
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
}

const props = defineProps<Props>()

const emit = defineEmits<{
  updateSegment: [index: number, text: string]
}>()

// Editing state
const editingSegment = ref<number | null>(null)
const editingText = ref('')

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function startEditing(index: number, currentText: string) {
  editingSegment.value = index
  editingText.value = currentText
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
    <!-- Recording Activity Indicator -->
    <div v-if="props.isRecording" class="absolute top-0 left-0 right-0 z-10">
      <!-- Gray baseline -->
      <div class="h-1 bg-gradient-to-r from-transparent via-gray-300 dark:via-gray-600 to-transparent">
        <!-- Audio level indicator -->
        <div 
          class="h-full bg-gradient-to-r from-red-400 via-red-600 to-red-400 transition-all duration-150 ease-out"
          :style="{ 
            transform: `scaleX(${Math.max(0.1, (props.audioLevel || 0) * 1.5)})`,
            opacity: Math.max(0.3, (props.audioLevel || 0))
          }"
        ></div>
      </div>
      <div class="absolute top-1 left-4 flex items-center space-x-2 bg-gray-500/20 backdrop-blur-sm rounded-full px-3 py-1">
        <div 
          class="w-2 h-2 rounded-full transition-colors duration-150"
          :class="(props.audioLevel || 0) > 0.1 ? 'bg-red-500' : 'bg-gray-400'"
        ></div>
        <span class="text-xs font-medium"
              :class="(props.audioLevel || 0) > 0.1 ? 'text-red-600 dark:text-red-400' : 'text-gray-600 dark:text-gray-400'">
          RECORDING
        </span>
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
        <div class="h-full overflow-y-auto pr-2 space-y-3">
          <TransitionGroup
            name="segment"
            tag="div"
            class="space-y-3"
          >
            <div
              v-for="(segment, index) in segments"
              :key="`segment-${index}`"
              class="group relative bg-gradient-to-r from-background via-background to-background/50
                     border border-border/40 rounded-xl p-4
                     hover:border-blue-200 dark:hover:border-blue-800
                     hover:shadow-md hover:shadow-blue-500/5
                     transition-all duration-200 ease-out"
            >
              <!-- Timeline marker -->
              <div class="absolute -left-1 top-6 w-2 h-2 bg-blue-500 rounded-full opacity-60"></div>
              <div class="absolute -left-0.5 top-6 w-3 h-3 bg-blue-500/20 rounded-full animate-pulse"></div>

              <!-- Header with timestamp and actions -->
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center space-x-3">
                  <Badge variant="outline" class="text-xs font-mono bg-muted/30 border-border/40 px-2 py-1">
                    <Clock class="h-3 w-3 mr-1.5" />
                    {{ formatTimestamp(segment.start) }}
                  </Badge>
                  <div class="text-xs text-muted-foreground">
                    {{ Math.ceil((segment.end - segment.start) * 1000) / 1000 }}s
                  </div>
                </div>

                <!-- Edit controls -->
                <div class="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    v-if="editingSegment !== index"
                    @click="startEditing(index, segment.text)"
                    class="p-1.5 rounded-lg hover:bg-muted/40 transition-colors"
                  >
                    <Edit3 class="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                  </button>
                  <template v-else>
                    <button
                      @click="saveEdit"
                      class="p-1.5 rounded-lg hover:bg-green-500/10 transition-colors"
                    >
                      <Check class="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                    </button>
                    <button
                      @click="cancelEdit"
                      class="p-1.5 rounded-lg hover:bg-red-500/10 transition-colors"
                    >
                      <X class="h-3.5 w-3.5 text-red-600 dark:text-red-400" />
                    </button>
                  </template>
                </div>
              </div>

              <!-- Content -->
              <div class="relative">
                <template v-if="editingSegment === index">
                  <!-- Edit mode -->
                  <Textarea
                    v-model="editingText"
                    @keydown="handleKeydown"
                    class="min-h-[80px] text-sm leading-relaxed resize-none
                           border-blue-200 dark:border-blue-800
                           focus:border-blue-400 dark:focus:border-blue-600
                           focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Edit transcription..."
                    :autofocus="true"
                  />
                  <div class="mt-2 text-xs text-muted-foreground">
                    Press Enter to save • Escape to cancel • Shift+Enter for new line
                  </div>
                </template>
                <template v-else>
                  <!-- Display mode -->
                  <div
                    class="text-sm leading-relaxed text-foreground/90
                           cursor-pointer rounded-lg p-2 -m-2
                           hover:bg-muted/20 transition-colors"
                    @click="startEditing(index, segment.text)"
                  >
                    {{ segment.text }}
                  </div>
                </template>
              </div>

              <!-- Subtle progress bar -->
              <div class="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500/0 via-blue-500/20 to-blue-500/0 rounded-b-xl"></div>
            </div>
          </TransitionGroup>
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