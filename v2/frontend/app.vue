<template>
  <div class="font-[Inter] text-white bg-stone-950 h-screen w-screen flex flex-row items-center justify-center gap-4">
      <div class="flex flex-row gap-4 relative">
          <div class="flex flex-col gap-4">
              <div class="flex flex-col items-center justify-center border-2 border-stone-800 bg-black p-6 rounded-2xl">
                  <!-- Connection status -->
                  <div v-if="error" class="text-red-500 text-xs">{{ error }}</div>
                  <!-- Debug status -->
                  <div class="text-xs text-gray-400">WebSocket: {{ isConnected ? "Connected" : "Disconnected" }}</div>
                  <!-- Waveform container -->
                  <div class="h-24 flex items-center justify-center gap-1">
                      <div
                          v-for="(bar, index) in waveformBars"
                          :key="index"
                          class="w-1 bg-white rounded-full transition-all duration-150"
                          :style="{ height: `${bar}px` }"
                      ></div>
                  </div>
                  <div class="flex flex-row justify-center items-center gap-2">
                      <!-- Reset button -->
                      <button
                          @click="resetRecording"
                          class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center bg-white/10 hover:bg-white/20"
                      >
                          <Icon name="tabler:trash-x-filled" class="h-4 w-4" />
                      </button>
                      <!-- Microphone button -->
                      <button
                          @click="toggleRecording"
                          class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center"
                          :class="isRecording ? 'bg-red-500 hover:bg-red-600' : 'bg-white/10 hover:bg-white/20'"
                      >
                          <Icon name="tabler:microphone-filled" class="h-4 w-4" />
                      </button>
                      <!-- Minutes button -->
                      <button
                          @click="toggleMinutesPanel"
                          class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center"
                          :class="showMinutes ? 'bg-blue-500 hover:bg-blue-600' : 'bg-white/10 hover:bg-white/20'"
                      >
                          <Icon name="tabler:pencil-bolt" class="h-4 w-4" />
                      </button>
                  </div>
              </div>
              <!-- Transcription/Diarization Area -->
              <div class="border-2 border-stone-800 bg-black p-6 rounded-2xl" v-if="segments.length > 0">
                  <TranscriptBox :segments="segments" class="max-h-60 min-w-64 max-w-2xl pe-4" />
              </div>
          </div>
          
          <!-- Minutes Area -->
          <div 
              v-if="showMinutes" 
              class="border-2 border-stone-800 bg-black p-6 rounded-2xl min-w-64 max-w-xl"
          >
              <div class="flex flex-col h-full">
                  <div class="flex justify-between items-center mb-4">
                      <h2 class="text-lg font-semibold">Meeting Minutes</h2>
                      <div class="text-xs text-gray-400">{{ currentStatus }}</div>
                  </div>
                  
                  <div v-if="minutesError" class="text-red-500 text-sm mb-2">{{ minutesError }}</div>
                  
                  <!-- Loading state -->
                  <div v-if="isMinutesLoading && minutesSections.length === 0" class="flex flex-col items-center justify-center py-8">
                      <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mb-2"></div>
                      <div class="text-sm text-gray-400">Generating minutes...</div>
                  </div>
                  
                  <!-- Minutes sections -->
                  <div v-else class="overflow-y-auto max-h-96 pr-2 space-y-4">
                      <div v-if="minutesSections.length === 0" class="text-center text-gray-400 py-8">
                          No minutes available yet. Keep talking to generate content.
                      </div>
                      
                      <div 
                          v-for="section in minutesSections" 
                          :key="section.id"
                          class="border border-stone-800 rounded-lg p-4 bg-stone-900"
                      >
                          <div class="flex justify-between items-start mb-2">
                              <h3 class="font-medium">{{ section.title }}</h3>
                              <span class="text-xs text-gray-400">
                                  {{ formatTime(section.start) }} - {{ formatTime(section.end) }}
                              </span>
                          </div>
                          
                          <div class="text-xs text-gray-400 mb-2">
                              <span class="font-medium">Participants:</span> {{ section.speakers.join(', ') }}
                          </div>
                          
                          <p class="text-sm text-gray-300 whitespace-pre-wrap">{{ section.description }}</p>
                      </div>
                  </div>
              </div>
          </div>
      </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from "vue";
import { useAudioStream } from "~/composables/useAudioStream";
import { useAudioProcessor } from "~/composables/useAudioProcessor";
import { useRecording } from "~/composables/useRecording";
import { useMinutes } from "~/composables/useMinutes";

const { isConnected, segments, error, connect, sendAudioChunk, disconnect } = useAudioStream();
const { resetRecording } = useRecording();

const { 
  isStreaming, 
  isLoading: isMinutesLoading, 
  error: minutesError, 
  minutesSections, 
  currentStatus,
  showMinutes,
  startMinutesStream, 
  stopMinutesStream,
  formatTime,
  toggleMinutesPanel
} = useMinutes();

const { isRecording, waveformBars, startRecording, stopRecording } = useAudioProcessor((chunk) => {
  if (isConnected.value) {
      sendAudioChunk(chunk);
  }
});

const toggleRecording = async () => {
  console.log("Toggle recording, current state:", isRecording.value);

  if (!isRecording.value) {
      console.log("Starting recording flow...");
      connect();
      await startRecording();
      
      // Automatically start minutes streaming when recording begins
      if (showMinutes.value && !isStreaming.value) {
          startMinutesStream();
      }
  } else {
      console.log("Stopping recording flow...");
      stopRecording();
      disconnect();
  }
};

// Clean up
onUnmounted(() => {
  console.log("Component unmounting...");
  stopRecording();
  disconnect();
  stopMinutesStream();
});
</script>