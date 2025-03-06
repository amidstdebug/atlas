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
                        <!-- Redo Annotation button - with disabled state -->
                        <button
                            @click="redoAnnotation"
                            class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center"
                            :class="isProcessingReannote ? 'animate-spin bg-white/5 cursor-not-allowed': 'bg-white/10 hover:bg-white/20'"
                            :disabled="isProcessingReannote"
                        >
                            <Icon name="tabler:reload" class="h-4 w-4" />
                        </button>
                        <!-- Minutes button -->
                        <!-- <button
                            @click="toggleMinutesPanel"
                            class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center"
                            :class="showMinutes ? 'bg-blue-500 hover:bg-blue-600' : 'bg-white/10 hover:bg-white/20'"
                        >
                            <Icon name="tabler:pencil-bolt" class="h-4 w-4" />
                        </button> -->
                    </div>
                </div>
                <!-- Transcription/Diarization Area -->
                <div class="border-2 border-stone-800 bg-black p-6 rounded-2xl" v-if="segments.length > 0">
                    <TranscriptBox :segments="segments" class="max-h-60 min-w-64 max-w-2xl pe-4" />
                </div>
            </div>

            <!-- Minutes Area -->
            <div v-if="showMinutes" class="border-2 border-stone-800 bg-black p-6 rounded-2xl min-w-64 max-w-xl">
                <MinutesBox />
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
const { resetRecording, redoAnnotation, isProcessingReannote } = useRecording();

const { 
  isLoading: isMinutesLoading, 
  error: minutesError, 
  minutesSections, 
  currentStatus,
  showMinutes,
  progressPercentage,
  generateMinutes: startMinutesGeneration,
  fetchCompleteMinutes,
  formatTime,
  toggleMinutesPanel,
  cleanup: cleanupMinutes
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
  } else {
      console.log("Stopping recording flow...");
      stopRecording();
      disconnect();
  }
};

// Generate minutes only when not recording
const generateMinutes = async () => {
  if (!isRecording.value) {
    if (!showMinutes.value) {
      toggleMinutesPanel();
    } else if (segments.length > 0) {
      // If minutes panel is already visible, start generation
      await startMinutesGeneration();
    }
  }
};

// Regenerate minutes
const regenerateMinutes = async () => {
  if (!isRecording.value && segments.length > 0) {
    await startMinutesGeneration();
  }
};

// Clean up
onUnmounted(() => {
  console.log("Component unmounting...");
  stopRecording();
  disconnect();
  cleanupMinutes();
});
</script>