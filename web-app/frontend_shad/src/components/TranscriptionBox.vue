<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!--
      Scrollable container:
      flex-1 grows to fill available space
      overflow-auto ensures scrolling when content overflows
    -->
    <ScrollArea
      ref="transcriptionBox"
      class="flex-1 border p-4 rounded-lg relative overflow-auto"
      :class="recording ? 'animate-glow' : ''"
      style="background-color: #f9f9f9;"
    >
      <div v-for="(item, index) in transcriptions" :key="index" class="mb-2">
        <div>
          <span class="font-mono text-sm text-gray-500">{{ item.timestamp }}</span>
          <span class="font-bold ml-2" :style="{ color: getSpeakerColor(item.speaker) }">
            {{ item.speaker }}
          </span>:
        </div>
        <div class="ml-4">{{ item.text }}</div>
      </div>
    </ScrollArea>

    <!-- Bottom control buttons, horizontally centered, with separators -->
    <div class="mt-4 flex items-center justify-center space-x-4">
      <Button class="bg-pastel-blue text-white px-4 py-2 rounded" @click="uploadRecording">
        Upload Recording
      </Button>

      <Separator orientation="vertical" class="h-8" />

      <Button v-if="!recording" class="bg-pastel-pink text-white px-4 py-2 rounded" @click="startRecording">
        Start Recording
      </Button>
      <Button v-else class="bg-pastel-lavender text-white px-4 py-2 rounded" @click="stopRecording">
        Stop Recording
      </Button>

      <Separator orientation="vertical" class="h-8" />

      <Button class="bg-pastel-green text-white px-4 py-2 rounded" @click="clearTranscripts">
        Clear Transcript
      </Button>
    </div>
  </div>
</template>

<script>
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

export default {
  name: 'TranscriptionBox',
  components: { ScrollArea, Button, Separator },
  props: {
    transcriptions: {
      type: Array,
      default: () => []
    },
    recording: {
      type: Boolean,
      default: false
    },
    speakerColors: {
      type: Object,
      default: () => ({})
    }
  },
  methods: {
    getSpeakerColor(speaker) {
      return this.speakerColors[speaker] || '#000000';
    },
    uploadRecording() {
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = 'audio/*'
      input.onchange = (e) => {
        const file = e.target.files[0]
        if (file) {
          this.simulateFileProcessing(file)
        }
      }
      input.click()
    },
    startRecording() {
      this.$emit('start-recording')
    },
    stopRecording() {
      this.$emit('stop-recording')
    },
    clearTranscripts() {
      this.$emit('clear-transcripts')
    },
    simulateFileProcessing(file) {
      this.$emit('upload-recording', file)
    }
  },
  updated() {
    if (this.$refs.transcriptionBox) {
      this.$nextTick(() => {
        const el = this.$refs.transcriptionBox.$el || this.$refs.transcriptionBox;
        el.scrollTop = el.scrollHeight; // Auto-scroll to bottom
      });
    }
  }
}
</script>

<style scoped>
/* Use Tailwind CSS animations if necessary */
</style>