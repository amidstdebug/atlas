<template>
    <div class="font-[Inter] text-white bg-stone-950 h-screen w-screen flex flex-row items-center justify-center gap-4">
        <div class="flex flex-row gap-4 relative">
            <div class="flex flex-col gap-4">
                <div class="flex flex-col items-center justify-center border-2 border-stone-800 bg-black p-6 rounded-2xl">
                    <!-- Connection status -->
                    <div v-if="error" class="text-red-500">{{ error }}</div>
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
                    <!-- Microphone button -->
                    <button
                        @click="toggleRecording"
                        class="p-4 rounded-full transition-all duration-300 aspect-square flex items-center justify-center"
                        :class="isRecording ? 'bg-red-500 hover:bg-red-600' : 'bg-white/10 hover:bg-white/20'"
                    >
                        <Icon name="tabler:microphone-filled" class="h-6 w-6" />
                    </button>
                </div>
                <!-- Transcription/Diarization Area -->
                <div class="border-2 border-stone-800 bg-black p-6 rounded-2xl" v-if="segments.length > 0">
                    <TranscriptBox :segments="segments" class="max-h-60 min-w-64 max-w-2xl pe-4" />
                </div>
            </div>
            <!-- Summarize Area -->
            <!-- <div class="border-2 border-stone-800 bg-black p-6 rounded-2xl"></div> -->
        </div>
    </div>
</template>

<script setup>
import { onMounted, onUnmounted } from "vue";
import { useWebSocket } from "~/composables/useWebSocket";
import { useAudioProcessor } from "~/composables/useAudioProcessor";

const { isConnected, segments, error, connect, sendAudioChunk, disconnect } = useWebSocket();

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

// Clean up
onUnmounted(() => {
    console.log("Component unmounting...");
    stopRecording();
    disconnect();
});
</script>
