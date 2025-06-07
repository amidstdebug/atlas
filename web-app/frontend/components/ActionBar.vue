<script setup lang="ts">
import { Mic, Upload, Square, Sparkles, RotateCcw, Settings } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

interface RecordingState {
  isRecording: boolean
  isTranscribing: boolean
}

interface SummaryState {
  isGenerating: boolean
}

interface Props {
  recordingState: RecordingState
  summaryState: SummaryState
  aggregatedTranscription: string
  autoReportEnabled: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  uploadRecording: []
  startRecording: []
  stopRecording: []
  generateSummary: []
  clearTranscription: []
  openConfig: []
}>()

function handleUploadRecording() {
  emit('uploadRecording')
}

function handleRecordingToggle() {
  if (props.recordingState.isRecording) {
    emit('stopRecording')
  } else {
    emit('startRecording')
  }
}

function handleGenerateSummary() {
  emit('generateSummary')
}

function handleClearTranscription() {
  emit('clearTranscription')
}

function handleOpenConfig() {
  emit('openConfig')
}
</script>

<template>
  <!-- Floating Action Bar -->
  <div class="fixed inset-x-0 bottom-4 flex justify-center z-40 pointer-events-none">
    <!-- inner wrapper gets the events; outer keeps clicks below reachable -->
    <div class="pointer-events-auto flex flex-wrap items-center justify-center gap-3
              bg-background/90 border border-border/50 shadow-xl backdrop-blur-xl
              rounded-full px-6 py-3">

      <Button
        :disabled="recordingState.isTranscribing || recordingState.isRecording"
        variant="outline"
        size="lg"
        class="rounded-full shadow-sm hover:shadow-md transition-all duration-200 hover:cursor-pointer"
        @click="handleUploadRecording"
      >
        <Upload class="h-4 w-4 mr-2" />
        {{ recordingState.isTranscribing ? 'Processing...' : 'Upload Audio (MP3, WAV)' }}
      </Button>

      <Button
        :disabled="recordingState.isTranscribing"
        :variant="recordingState.isRecording ? 'destructive' : 'default'"
        size="lg"
        class="rounded-full shadow-sm hover:shadow-md transition-all duration-200 min-w-[140px] hover:cursor-pointer"
        :class="{ 'animate-pulse': recordingState.isRecording }"
        @click="handleRecordingToggle"
      >
        <Mic v-if="!recordingState.isRecording" class="h-4 w-4 mr-2" />
        <Square v-else class="h-4 w-4 mr-2" />
        {{ recordingState.isRecording ? 'Stop Recording' : 'Start Recording' }}
      </Button>

      <Button
        :disabled="!aggregatedTranscription || summaryState.isGenerating || autoReportEnabled || recordingState.isRecording"
        variant="secondary"
        size="lg"
        class="rounded-full shadow-sm hover:shadow-md transition-all duration-200 hover:cursor-pointer"
        @click="handleGenerateSummary"
      >
        <Sparkles class="h-4 w-4 mr-2" />
        {{ autoReportEnabled ? 'Auto Report Active' : summaryState.isGenerating ? 'Analyzing...' : 'Generate Report' }}
      </Button>

      <Button
        :disabled="recordingState.isRecording || recordingState.isTranscribing"
        variant="outline"
        size="lg"
        class="rounded-full shadow-sm hover:shadow-md transition-all duration-200 hover:cursor-pointer"
        @click="handleClearTranscription"
      >
        <RotateCcw class="h-4 w-4 mr-2" />
        Clear All
      </Button>

      <Button
        :disabled="recordingState.isRecording"
        variant="outline"
        size="lg"
        class="rounded-full shadow-sm hover:shadow-md transition-all duration-200 hover:cursor-pointer"
        @click="handleOpenConfig"
      >
        <Settings class="h-4 w-4 mr-2" />
        Config
      </Button>
    </div>
  </div>
</template>
