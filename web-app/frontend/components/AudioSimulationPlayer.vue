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

const authStore = useAuthStore()


const audioRef = ref<HTMLAudioElement>()
const fileInput = ref<HTMLInputElement>()
const file = ref<File | null>(null)
const audioUrl = ref('')
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const isMinimized = ref(false)

// Simulation state
const isSimulating = ref(false)
const isTranscribing = ref(false)
const simulationSegments = ref<any[]>([])
const currentChunkIndex = ref(0)
const chunkSize = ref(AUDIO_CONFIG.CHUNK_DURATION_SECONDS || 10) // 10 seconds
const audioChunks = ref<{ blob: Blob; startTime: number; endTime: number; sent: boolean }[]>([])
const isPreparingChunks = ref(false)
let playbackTimer: ReturnType<typeof setTimeout> | null = null

function openFileDialog() {
  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const f = target.files?.[0]
  if (f) {
    file.value = f
    audioUrl.value = URL.createObjectURL(f)
    // Clear any existing chunks
    clearAudioChunks()
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
      // Prepare chunks before playing if not already done
      if (audioChunks.value.length === 0 && !isPreparingChunks.value) {
        await prepareAudioChunks()
      }
      
      await audioRef.value.play()
      if (!isSimulating.value) {
        startSimulation()
      }
    } catch (error) {
      console.error('Error playing audio:', error)
    }
  }
  isPlaying.value = !isPlaying.value
}

async function prepareAudioChunks() {
  if (!file.value || !duration.value || isPreparingChunks.value) return
  
  console.log('[Simulation] 🔧 Preparing audio chunks...')
  isPreparingChunks.value = true
  
  try {
    const totalChunks = Math.ceil(duration.value / chunkSize.value)
    const chunks: { blob: Blob; startTime: number; endTime: number; sent: boolean }[] = []
    
    // Pre-slice all audio chunks
    for (let i = 0; i < totalChunks; i++) {
      const startTime = i * chunkSize.value
      const endTime = Math.min(startTime + chunkSize.value, duration.value)
      
      console.log(`[Simulation] ✂️ Slicing chunk ${i}: ${startTime}s - ${endTime}s`)
      const blob = await sliceAudioFile(file.value, startTime, endTime)
      
      chunks.push({
        blob,
        startTime,
        endTime,
        sent: false
      })
    }
    
    audioChunks.value = chunks
    console.log(`[Simulation] ✅ Prepared ${chunks.length} audio chunks`)
  } catch (error) {
    console.error('[Simulation] ❌ Error preparing chunks:', error)
  } finally {
    isPreparingChunks.value = false
  }
}

async function startSimulation() {
  if (!audioRef.value || audioChunks.value.length === 0) return
  
  console.log('[Simulation] 🎬 Starting audio simulation')
  isSimulating.value = true
  simulationSegments.value = []
  currentChunkIndex.value = 0
  
  // Reset all chunks to unsent
  audioChunks.value.forEach(chunk => chunk.sent = false)
  
  // Start monitoring playback
  monitorPlayback()
}

function monitorPlayback() {
  if (!isSimulating.value || !audioRef.value) return
  
  const currentTime = audioRef.value.currentTime
  
  // Check if we need to send any chunks
  for (let i = 0; i < audioChunks.value.length; i++) {
    const chunk = audioChunks.value[i]
    
    // Send chunk when playback reaches the END of its time range (after N seconds)
    if (!chunk.sent && currentTime >= chunk.endTime) {
      console.log(`[Simulation] 📤 Sending chunk ${i} at playback time ${currentTime.toFixed(1)}s (chunk completed)`)
      sendChunkToBackend(chunk, i)
      chunk.sent = true
      currentChunkIndex.value = i + 1
      
      // Clean up previous chunk to prevent memory leak
      if (i > 0) {
        const prevChunk = audioChunks.value[i - 1]
        // Create a new object without the blob to allow garbage collection
        audioChunks.value[i - 1] = {
          blob: null as any, // Release blob reference
          startTime: prevChunk.startTime,
          endTime: prevChunk.endTime,
          sent: prevChunk.sent
        }
        console.log(`[Simulation] 🗑️ Released memory for chunk ${i - 1}`)
      }
    }
  }
  
  // Continue monitoring
  if (isSimulating.value) {
    playbackTimer = setTimeout(monitorPlayback, 100) // Check every 100ms
  }
}

async function sendChunkToBackend(chunk: { blob: Blob; startTime: number; endTime: number }, chunkIndex: number) {
  try {
    isTranscribing.value = true
    
    const formData = new FormData()
    formData.append('file', chunk.blob, `simulation_chunk_${chunkIndex}.wav`)
    formData.append('replace_numbers', 'true')
    formData.append('use_icao_callsigns', 'true')
    
    const baseUrl = process.env.NODE_ENV === 'development' ? 'http://localhost:5002' : ''
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
    
    // Process the transcription response similar to the recording system
    if (data.segments && data.segments.length > 0) {
      const allText = data.segments.map((seg: any) => seg.text.trim()).join(' ').trim()
      
      if (allText) {
        const chunkSegment = {
          text: allText,
          start: chunk.startTime,
          end: chunk.endTime,
        }
        
        const segmentIndex = simulationSegments.value.length
        simulationSegments.value.push(chunkSegment)
        
        // Emit the updated segments to parent
        emit('segments-updated', simulationSegments.value)
        
        // Note: Process-block will be automatically triggered by TranscriptionPanel watching segments
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
  if (playbackTimer) {
    clearTimeout(playbackTimer)
    playbackTimer = null
  }
}

function clearAudioChunks() {
  console.log('[Simulation] 🧹 Clearing audio chunks')
  audioChunks.value = []
  currentChunkIndex.value = 0
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
  let offset = 44
  for (let i = 0; i < length; i++) {
    for (let channel = 0; channel < numberOfChannels; channel++) {
      const sample = Math.max(-1, Math.min(1, buffer.getChannelData(channel)[i]))
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true)
      offset += 2
    }
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
        
        <!-- Chunk preparation status -->
        <div v-if="isPreparingChunks" class="flex items-center justify-center space-x-2 text-xs text-orange-600 bg-orange-50 dark:bg-orange-950/20 rounded-md p-1">
          <div class="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse"></div>
          <span class="font-medium">Preparing chunks...</span>
        </div>
        
        <!-- Simulation status -->
        <div v-else-if="isSimulating" class="flex items-center justify-center space-x-2 text-xs text-blue-600 bg-blue-50 dark:bg-blue-950/20 rounded-md p-1">
          <div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></div>
          <span class="font-medium">Simulating ({{ currentChunkIndex }}/{{ audioChunks.length }})</span>
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