import { defineStore } from 'pinia'

export interface SummaryEntry {
  id: string
  summary: string
  timestamp: string
  structured_summary?: Record<string, any>
  previous_report?: string
}

export interface TranscriptionState {
  transcription: string
  summaries: SummaryEntry[]
  recording: boolean
  loading: boolean
  currentSummary: SummaryEntry | null
  segments: Segment[]
}

export interface Segment {
  start: number
  end: number
  text: string
}

export const useTranscriptionStore = defineStore('transcription', {
  state: (): TranscriptionState => ({
    transcription: '',
    summaries: [],
    recording: false,
    loading: false,
    currentSummary: null,
    segments: []
  }),

  getters: {
    getTranscription: (state) => state.transcription,
    getSummaries: (state) => state.summaries,
    getIsRecording: (state) => state.recording,
    getLoading: (state) => state.loading,
    getCurrentSummary: (state) => state.currentSummary,
    getLatestSummary: (state) => state.summaries[state.summaries.length - 1] || null,
    getSegments: (state) => state.segments
  },

  actions: {
    setTranscription(transcription: string) {
      this.transcription = transcription
    },

    appendTranscription(text: string) {
      this.transcription += (this.transcription ? ' ' : '') + text
    },

    clearTranscription() {
      this.transcription = ''
    },

    addSummary(summary: SummaryEntry) {
      this.summaries.push(summary)
      this.currentSummary = summary
    },

    setSummaries(summaries: SummaryEntry[]) {
      this.summaries = summaries
    },

    clearSummaries() {
      this.summaries = []
      this.currentSummary = null
    },

    setRecording(isRecording: boolean) {
      this.recording = isRecording
    },

    toggleRecording() {
      this.recording = !this.recording
    },

    setLoading(loading: boolean) {
      this.loading = loading
    },

    reset() {
      this.transcription = ''
      this.summaries = []
      this.recording = false
      this.loading = false
      this.currentSummary = null
    },

    setSegments(list: Segment[]) {
      this.segments = list
      this.persist()
    },

    updateSegment(index: number, newText: string) {
      if (this.segments[index]) {
        this.segments[index].text = newText
        this.persist()
      }
    },

    persist() {
      if (process.client) {
        localStorage.setItem('atlas-segments',   JSON.stringify(this.segments))
        localStorage.setItem('atlas-summaries', JSON.stringify(this.summaries))
      }
    },

    hydrate() {
      if (process.client) {
        const seg = localStorage.getItem('atlas-segments')
        const sum = localStorage.getItem('atlas-summaries')
        if (seg) this.segments  = JSON.parse(seg)
        if (sum) this.summaries = JSON.parse(sum)
      }
    }
  }
})