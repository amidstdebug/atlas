<template>
  <!-- Use full browser height, no extra scroll outside. -->
  <div class="h-screen flex flex-col overflow-hidden">

    <!-- Header sits at the top -->
    <Header :activeMode="activeMode" @switch-mode="switchMode" />

    <!-- Main content:
         flex-1 => occupy remaining vertical space
         mt-[2vw] mb-[2vw] => top/bottom margin
         overflow-hidden => no scroll on this container
    -->
    <div class="flex-1 mt-[2vw] mb-[2vw] overflow-hidden">
      <!-- The row that holds the two boxes -->
      <div class="flex h-full mx-[5%] gap-[2%]">

        <!-- TranscriptionBox (35%) -->
        <TranscriptionBox
          class="h-full flex flex-col overflow-hidden p-4"
          style="width: 35%;"
          :transcriptions="transcriptions"
          :recording="recording"
          :speakerColors="speakerColors"
          @start-recording="startRecording"
          @stop-recording="stopRecording"
          @clear-transcripts="clearTranscripts"
        />

        <!-- SummaryBox (65%) -->
        <SummaryBox
          class="h-full flex flex-col overflow-hidden p-4"
          style="width: 65%;"
          :summary="summary"
          :updatingSummary="updatingSummary"
          @apply-changes="applyChanges"
          @update-summary="updateSummary"
        />
      </div>
    </div>
  </div>
</template>

<script>
import Header from './Header.vue'
import TranscriptionBox from './TranscriptionBox.vue'
import SummaryBox from './SummaryBox.vue'
import {Button} from '@/components/ui/button'
import {Separator} from '@/components/ui/separator'

export default {
  name: 'App',
  components: { Header, TranscriptionBox, SummaryBox, Button, Separator },
  data() {
    return {
      activeMode: 'ATC',
      recording: false,
      transcriptions: [],
      summary: '',
      updatingSummary: false,
      speakerColors: {
        'Speaker A': '#1CDC9A',
        'Speaker B': '#3B82F6',
        'Speaker C': '#FBBF24'
      },
      recordingInterval: null
    }
  },
  methods: {
    switchMode(mode) {
      this.activeMode = mode
    },
    startRecording() {
      this.recording = true
      this.recordingInterval = setInterval(() => {
        const newTranscript = this.generateFakeTranscript()
        this.transcriptions.push(newTranscript)
        // Example logic: every 3 lines, attempt a summary update
        if (this.transcriptions.length % 3 === 0 && !this.updatingSummary) {
          this.triggerSummaryUpdate()
        }
      }, 3000)
    },
    stopRecording() {
      this.recording = false
      clearInterval(this.recordingInterval)
      // Optionally do a final summary update
      this.triggerSummaryUpdate()
    },
    clearTranscripts() {
      this.transcriptions = []
      this.summary = ''
    },
    generateFakeTranscript() {
      const speakers = Object.keys(this.speakerColors)
      const speaker = speakers[Math.floor(Math.random() * speakers.length)]
      const timestamp = new Date().toLocaleTimeString()
      const texts = [
        'This is a sample transcription line.',
        'Air incident reported near runway 2.',
        'Meeting starting with introductions.',
        'Discussion about project milestones.'
      ]
      const text = texts[Math.floor(Math.random() * texts.length)]
      return { timestamp, speaker, text }
    },
    triggerSummaryUpdate() {
      if (this.updatingSummary) return
      this.updatingSummary = true
      setTimeout(() => {
        const lastTranscripts = this.transcriptions
          .slice(-3)
          .map(t => `${t.timestamp} - ${t.speaker}: ${t.text}`)
          .join('\n')
        this.summary = (this.summary + '\n' + lastTranscripts).trim()
        this.updatingSummary = false
      }, 2000)
    },
    applyChanges(newSummary) {
      this.summary = newSummary
      this.triggerSummaryUpdate()
    },
    updateSummary(newText) {
      this.summary = newText
    }
  }
}
</script>

<style>
/* Pastel color classes */
.bg-pastel-blue {
  background-color: #a8dadc;
}
.bg-pastel-pink {
  background-color: #f4acb7;
}
.bg-pastel-lavender {
  background-color: #8787ad;
}
.bg-pastel-green {
  background-color: #80af9e;
}
</style>