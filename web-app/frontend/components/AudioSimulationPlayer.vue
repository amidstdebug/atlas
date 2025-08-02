<script setup lang="ts">
import { ref, onBeforeUnmount, nextTick } from 'vue'
import { Play, Pause, Upload, X, Volume2, Minus } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { useAuthStore } from '@/stores/auth'

import { AUDIO_CONFIG } from '@/constants/audio'

const emit = defineEmits<{
  'close': []
  'segments-updated': [segments: any[]]
}>()

const props = defineProps<{
  customWhisperPrompt?: string
}>()

const authStore = useAuthStore()

const audioRef = ref<HTMLAudioElement>()
const fileInput = ref<HTMLInputElement>()
const file = ref<File | null>(null)
const audioUrl = ref('')
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const isMinimized = ref(false)

// Streaming simulation state
const isSimulating = ref(false)
const isTranscribing = ref(false)
const simulationSegments = ref<any[]>([])
const currentChunkIndex = ref(0)
const chunkSize = ref(AUDIO_CONFIG.CHUNK_DURATION_SECONDS || 10) // 10 seconds
let mediaRecorder: MediaRecorder | null = null
let streamingSupported = false
let audioContext: AudioContext | null = null
let mediaStreamSource: MediaStreamAudioSourceNode | null = null
let scriptProcessor: ScriptProcessorNode | null = null
let recordingBuffer: Float32Array[] = []
let recordingLength = 0
let sampleRate = 44100

// Check if streaming is supported on component mount
if (typeof window !== 'undefined') {
  streamingSupported = 'captureStream' in HTMLMediaElement.prototype && 
                      'MediaRecorder' in window &&
                      'AudioContext' in window
}

function openFileDialog() {
  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const f = target.files?.[0]
  if (f) {
    file.value = f
    audioUrl.value = URL.createObjectURL(f)
    nextTick(() => {
      if (audioRef.value) {
        audioRef.value.load()
      }
    })
  }
}

async function togglePlay() {
  if (!audioRef.value) return

  if (isPlaying.value) {
    audioRef.value.pause()
    stopSimulation()
  } else {
    try {
      await audioRef.value.play()
      startSimulation()
    } catch (error) {
      console.error('Error playing audio:', error)
    }
  }
  isPlaying.value = !isPlaying.value
}

function startSimulation() {
  if (!audioRef.value) return
  
  console.log('[Simulation] 🎬 Starting audio simulation')
  isSimulating.value = true
  simulationSegments.value = []
  currentChunkIndex.value = 0
  
  if (streamingSupported) {
    startStreamingCapture()
  } else {
    console.warn('[Simulation] ⚠️ Streaming not supported, falling back to chunk-on-demand')
    startFallbackSimulation()
  }
}

function startStreamingCapture() {
  try {
    // Capture the audio stream from the playing element
    const stream = (audioRef.value as any).captureStream()
    
    // Instead of using MediaRecorder with WebM fragments, 
    // we'll use Web Audio API to capture PCM data and convert to WAV
    audioContext = new AudioContext({ sampleRate: 44100 })
    sampleRate = audioContext.sampleRate
    mediaStreamSource = audioContext.createMediaStreamSource(stream)
    
    // Use ScriptProcessorNode for older browser support, or AudioWorkletNode for modern browsers
    const bufferSize = 4096
    scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1)
    
    recordingBuffer = []
    recordingLength = 0
    let chunkStartTime = performance.now()
    
    scriptProcessor.onaudioprocess = (event) => {
      if (!isSimulating.value) return
      
      const inputBuffer = event.inputBuffer
      const inputData = inputBuffer.getChannelData(0)
      
      // Copy the data to our recording buffer
      const bufferCopy = new Float32Array(inputData.length)
      bufferCopy.set(inputData)
      recordingBuffer.push(bufferCopy)
      recordingLength += inputData.length
      
      // Check if we've recorded enough for a chunk (based on sample rate and time)
      const recordedDuration = recordingLength / sampleRate
      if (recordedDuration >= chunkSize.value) {
        // Create WAV blob from the recorded data
        const wavBlob = createWavBlob(recordingBuffer, recordingLength, sampleRate)
        
        const chunkStartTimeSeconds = currentChunkIndex.value * chunkSize.value
        const chunkEndTimeSeconds = Math.min(chunkStartTimeSeconds + chunkSize.value, duration.value)
        
        console.log(`[Simulation] 📤 Streaming chunk ${currentChunkIndex.value}: ${chunkStartTimeSeconds}s - ${chunkEndTimeSeconds}s`)
        
        // Send the chunk
        sendChunkToBackend({
          blob: wavBlob,
          startTime: chunkStartTimeSeconds,
          endTime: chunkEndTimeSeconds
        }, currentChunkIndex.value)
        
        // Reset buffer for next chunk
        recordingBuffer = []
        recordingLength = 0
        currentChunkIndex.value++
        chunkStartTime = performance.now()
      }
    }
    
    // Connect the audio processing chain
    mediaStreamSource.connect(scriptProcessor)
    scriptProcessor.connect(audioContext.destination)
    
    console.log('[Simulation] 🎙️ Started streaming capture with WAV conversion')
    
  } catch (error) {
    console.error('[Simulation] ❌ Failed to start streaming:', error)
    // Fall back to chunk-on-demand if streaming fails
    startFallbackSimulation()
  }
}

let fallbackTimer: ReturnType<typeof setTimeout> | null = null

function startFallbackSimulation() {
  if (!file.value || !audioRef.value) return
  
  console.log('[Simulation] 🔄 Using fallback chunk-on-demand method')
  monitorPlaybackFallback()
}

function monitorPlaybackFallback() {
  if (!isSimulating.value || !audioRef.value || !file.value) return
  
  const currentTime = audioRef.value.currentTime
  const expectedChunkEndTime = currentChunkIndex.value * chunkSize.value + chunkSize.value
  
  // Check if we've crossed into the next chunk
  if (currentTime >= expectedChunkEndTime && currentTime <= duration.value) {
    const chunkStartTime = currentChunkIndex.value * chunkSize.value
    const chunkEndTime = Math.min(expectedChunkEndTime, duration.value)
    
    console.log(`[Simulation] ✂️ Creating chunk ${currentChunkIndex.value} on-demand: ${chunkStartTime}s - ${chunkEndTime}s`)
    
    // Create chunk on-demand and send immediately
    sliceAndSendChunk(file.value, chunkStartTime, chunkEndTime, currentChunkIndex.value)
    currentChunkIndex.value++
  }
  
  // Continue monitoring
  if (isSimulating.value && currentTime < duration.value) {
    fallbackTimer = setTimeout(monitorPlaybackFallback, 100)
  }
}

async function sliceAndSendChunk(file: File, startTime: number, endTime: number, chunkIndex: number) {
  try {
    const blob = await sliceAudioFile(file, startTime, endTime)
    await sendChunkToBackend({
      blob,
      startTime,
      endTime
    }, chunkIndex)
  } catch (error) {
    console.error(`[Simulation] ❌ Failed to slice and send chunk ${chunkIndex}:`, error)
  }
}

async function sendChunkToBackend(chunk: { blob: Blob; startTime: number; endTime: number }, chunkIndex: number) {
  try {
    isTranscribing.value = true
    
    const formData = new FormData()
    formData.append('file', chunk.blob, `simulation_chunk_${chunkIndex}.wav`)
    if (props.customWhisperPrompt) {
      formData.append('prompt', props.customWhisperPrompt)
    }
    
    const baseUrl = import.meta.env.DEV ? 'http://localhost:5002' : ''
    const response = await fetch(`${baseUrl}/transcribe`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
      },
      body: formData,
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    
    // Process the transcription response
    if (data.segments && data.segments.length > 0) {
      const allText = data.segments.map((seg: any) => seg.text.trim()).join(' ').trim()
      
      if (allText) {
        const chunkSegment = {
          text: allText,
          start: chunk.startTime,
          end: chunk.endTime,
        }
        
        simulationSegments.value.push(chunkSegment)
        
        // Emit the updated segments to parent
        emit('segments-updated', simulationSegments.value)
      }
    }
    
    console.log(`[Simulation] ✅ Chunk ${chunkIndex} transcription completed`)
  } catch (error) {
    console.error(`[Simulation] ❌ Chunk ${chunkIndex} transcription failed:`, error)
  } finally {
    isTranscribing.value = false
  }
}

function stopSimulation() {
  console.log('[Simulation] 🛑 Stopping simulation')
  isSimulating.value = false
  
  // Stop MediaRecorder if it's running
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
    mediaRecorder = null
  }
  
  // Clean up Web Audio API resources
  if (scriptProcessor) {
    scriptProcessor.disconnect()
    scriptProcessor = null
  }
  if (mediaStreamSource) {
    mediaStreamSource.disconnect()
    mediaStreamSource = null
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close()
    audioContext = null
  }
  
  // Clear fallback timer
  if (fallbackTimer) {
    clearTimeout(fallbackTimer)
    fallbackTimer = null
  }
  
  // Reset recording state
  recordingBuffer = []
  recordingLength = 0
}

async function sliceAudioFile(file: File, startTime: number, endTime: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const audioContext = new AudioContext()
    const fileReader = new FileReader()
    
    fileReader.onload = async (e) => {
      try {
        const arrayBuffer = e.target?.result as ArrayBuffer
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
        
        const sampleRate = audioBuffer.sampleRate
        const startSample = Math.floor(startTime * sampleRate)
        const endSample = Math.floor(endTime * sampleRate)
        const chunkLength = endSample - startSample
        
        // Create new audio buffer for the chunk
        const chunkBuffer = audioContext.createBuffer(
          audioBuffer.numberOfChannels,
          chunkLength,
          sampleRate
        )
        
        // Copy the audio data for the specified time range
        for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
          const originalData = audioBuffer.getChannelData(channel)
          const chunkData = chunkBuffer.getChannelData(channel)
          
          for (let i = 0; i < chunkLength; i++) {
            chunkData[i] = originalData[startSample + i] || 0
          }
        }
        
        // Convert to WAV blob
        const wavBlob = audioBufferToWav(chunkBuffer)
        resolve(wavBlob)
      } catch (error) {
        reject(error)
      } finally {
        audioContext.close()
      }
    }
    
    fileReader.onerror = () => reject(new Error('Failed to read file'))
    fileReader.readAsArrayBuffer(file)
  })
}

function audioBufferToWav(buffer: AudioBuffer): Blob {
  const length = buffer.length
  const numberOfChannels = buffer.numberOfChannels
  const sampleRate = buffer.sampleRate
  const arrayBuffer = new ArrayBuffer(44 + length * numberOfChannels * 2)
  const view = new DataView(arrayBuffer)
  
  // WAV header
  const writeString = (offset: number, string: string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i))
    }
  }
  
  writeString(0, 'RIFF')
  view.setUint32(4, 36 + length * numberOfChannels * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, numberOfChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * numberOfChannels * 2, true)
  view.setUint16(32, numberOfChannels * 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, length * numberOfChannels * 2, true)
  
  // Convert audio data
  let audioOffset = 44
  for (let i = 0; i < length; i++) {
    for (let channel = 0; channel < numberOfChannels; channel++) {
      const sample = Math.max(-1, Math.min(1, buffer.getChannelData(channel)[i]))
      view.setInt16(audioOffset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true)
      audioOffset += 2
    }
  }
  
  return new Blob([arrayBuffer], { type: 'audio/wav' })
}

function createWavBlob(buffers: Float32Array[], length: number, sampleRate: number): Blob {
  // Create a single buffer with all the data
  const result = new Float32Array(length)
  let offset = 0
  for (const buffer of buffers) {
    result.set(buffer, offset)
    offset += buffer.length
  }
  
  // Convert to 16-bit PCM
  const arrayBuffer = new ArrayBuffer(44 + length * 2)
  const view = new DataView(arrayBuffer)
  
  // WAV header
  const writeString = (offset: number, string: string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i))
    }
  }
  
  writeString(0, 'RIFF')
  view.setUint32(4, 36 + length * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM format
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, length * 2, true)
  
  // Convert float samples to 16-bit PCM
  let dataOffset = 44
  for (let i = 0; i < length; i++) {
    const sample = Math.max(-1, Math.min(1, result[i]))
    view.setInt16(dataOffset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true)
    dataOffset += 2
  }
  
  return new Blob([arrayBuffer], { type: 'audio/wav' })
}

function updateTime() {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
    duration.value = audioRef.value.duration || 0
  }
}

function handleEnded() {
  isPlaying.value = false
  stopSimulation()
}

function handleClose() {
  cleanup()
  emit('close')
}

function toggleMinimize() {
  isMinimized.value = !isMinimized.value
}

function cleanup() {
  if (audioRef.value && !audioRef.value.paused) {
    audioRef.value.pause()
  }
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value)
  }
  stopSimulation()
  isPlaying.value = false
}

onBeforeUnmount(cleanup)
</script>

<template>
  <div
    class="fixed bottom-4 right-4 z-50 transition-all duration-300 ease-in-out bg-background/95 backdrop-blur-xl border border-border/50 rounded-lg shadow-2xl overflow-hidden"
    :style="{
      width: isMinimized ? '48px' : '280px',
      height: isMinimized ? '48px' : 'auto'
    }"
  >
    <!-- Header -->
    <div class="flex items-center justify-between p-2 bg-muted/30 border-b border-border/30">
      <div class="flex items-center space-x-2">
        <Volume2 class="h-3 w-3 text-muted-foreground" />
        <span v-if="!isMinimized" class="text-xs font-medium">Audio Simulation</span>
      </div>
      <div class="flex items-center space-x-1">
        <Button 
          variant="ghost" 
          size="icon" 
          class="h-5 w-5 hover:bg-muted/50"
          @click="toggleMinimize"
        >
          <Minus class="h-3 w-3" />
        </Button>
        <Button 
          variant="ghost" 
          size="icon" 
          class="h-5 w-5 hover:bg-destructive/20 hover:text-destructive"
          @click="handleClose"
        >
          <X class="h-3 w-3" />
        </Button>
      </div>
    </div>
    
    <!-- Main content (hidden when minimized) -->
    <div 
      v-if="!isMinimized"
      class="p-3 space-y-3 transition-all duration-300"
    >
      <input ref="fileInput" type="file" accept="audio/*" class="hidden" @change="handleFileChange" />

      <!-- Upload section -->
      <div v-if="!file" class="flex justify-center">
        <Button 
          @click="openFileDialog" 
          class="w-full bg-primary/10 hover:bg-primary/20 border-primary/20 text-primary"
          variant="outline"
          size="sm"
        >
          <Upload class="h-3 w-3 mr-2" />
          Upload Audio
        </Button>
      </div>

      <!-- Player section -->
      <div v-else class="space-y-3">
        <!-- File info -->
        <div class="bg-muted/30 rounded-md p-2">
          <div class="text-xs text-muted-foreground break-all truncate" :title="file.name">
            {{ file.name }}
          </div>
          <div class="text-xs text-muted-foreground mt-1">
            {{ (file.size / 1024 / 1024).toFixed(1) }} MB
            <span v-if="!streamingSupported" class="text-orange-500 ml-1">(Fallback mode)</span>
          </div>
        </div>
        
        <audio
          ref="audioRef"
          :src="audioUrl"
          class="hidden"
          @timeupdate="updateTime"
          @loadedmetadata="updateTime"
          @ended="handleEnded"
          crossorigin="anonymous"
        />
        
        <!-- Player controls -->
        <div class="flex items-center space-x-2">
          <Button 
            @click="togglePlay" 
            size="icon" 
            class="h-8 w-8 rounded-full transition-all duration-200 flex-shrink-0"
            :class="{
              'bg-primary text-primary-foreground hover:bg-primary/90': !isPlaying,
              'bg-destructive text-destructive-foreground hover:bg-destructive/90': isPlaying
            }"
          >
            <Play v-if="!isPlaying" class="h-3 w-3 ml-0.5" />
            <Pause v-else class="h-3 w-3" />
          </Button>
          
          <div class="flex-1 space-y-1">
            <Progress 
              :model-value="duration ? (currentTime / duration) * 100 : 0" 
              class="w-full h-1"
            />
            <div class="flex justify-between text-xs font-mono text-muted-foreground">
              <span>{{ Math.floor(currentTime / 60) }}:{{ Math.floor(currentTime % 60).toString().padStart(2, '0') }}</span>
              <span>{{ Math.floor(duration / 60) }}:{{ Math.floor(duration % 60).toString().padStart(2, '0') }}</span>
            </div>
          </div>
        </div>
        
        <!-- Simulation status -->
        <div v-if="isSimulating" class="flex items-center justify-center space-x-2 text-xs text-blue-600 bg-blue-50 dark:bg-blue-950/20 rounded-md p-1">
          <div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></div>
          <span class="font-medium">
            {{ streamingSupported ? 'Streaming' : 'Simulating' }} 
            ({{ currentChunkIndex }}/{{ Math.ceil(duration / chunkSize) }})
          </span>
        </div>
        
        <!-- Transcription status -->
        <div v-else-if="isTranscribing" class="flex items-center justify-center space-x-2 text-xs text-green-600 bg-green-50 dark:bg-green-950/20 rounded-md p-1">
          <div class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
          <span class="font-medium">Transcribing</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Smooth transitions for all interactive elements */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}

/* Custom scrollbar for any overflow content */
::-webkit-scrollbar {
  width: 4px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(156, 163, 175, 0.5);
  border-radius: 2px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(156, 163, 175, 0.7);
}
</style>