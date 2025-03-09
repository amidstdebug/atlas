<template>
    <div class="flex flex-col items-center justify-center">
        <!-- Debug status -->
        <div v-if="error" class="text-red-500 text-xs">{{ error }}</div>

        <!-- Connection status -->
        <!-- <div class="text-xs text-gray-400">WebSocket: {{ isConnected ? "Connected" : "Disconnected" }}</div> -->

        <!-- Waveform container -->
        <div class="h-24 flex items-center justify-center gap-1">
            <div
                v-for="(bar, index) in waveformBars"
                :key="index"
                class="w-1 bg-white rounded-full transition-all duration-150"
                :style="{ height: `${bar}px` }"
            ></div>
        </div>

        <div class="grid grid-cols-5 h-10 gap-2">
            <div></div>
            <!-- Reset button -->
            <button
                @click="resetRecording"
                class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center bg-white/10 hover:bg-white/20"
                title="Clear recording and transcript"
            >
                <Icon name="tabler:trash-x-filled" class="h-4 w-4" />
            </button>

            <!-- Microphone button -->
            <button
                @click="toggleRecording"
                class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center"
                :class="{
                    'bg-emerald-600 hover:bg-green-700': isRecording && isConnected,
                    'bg-red-500 hover:bg-red-600': isRecording && !isConnected,
                    'bg-white/5 cursor-not-allowed': isProcessingReannote,
                    'bg-white/10 hover:bg-white/20': !isRecording && !isProcessingReannote,
                }"
                :disabled="isProcessingReannote"
                title="Start/stop recording"
            >
                <Icon name="tabler:microphone-filled" class="h-4 w-4" />
            </button>

            <!-- Redo Annotation button -->
            <button
                @click="redoAnnotation"
                class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center"
                :class="{
                    'animate-spin': isProcessingReannote,
                    'bg-white/5 cursor-not-allowed': isRecording || isProcessingReannote,
                    'bg-white/10 hover:bg-white/20': !isRecording && !isProcessingReannote,
                }"
                :disabled="isProcessingReannote || isRecording"
                title="Reannotate & transcribe"
            >
                <Icon name="tabler:reload" class="h-4 w-4" />
            </button>

            <!-- Download recording button -->
            <button
                v-if="segments.length > 0"
                @click="downloadAudio"
                class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center bg-white/10 hover:bg-white/20"
                title="Download recording"
            >
                <Icon name="tabler:download" class="h-4 w-4" />
            </button>
        </div>
    </div>
</template>

<script setup>
import { useConfig } from "~/composables/useConfig";
import { useAudioStream } from "~/composables/useAudioStream";
import { useAudioProcessor } from "~/composables/useAudioProcessor";
import { useRecording } from "~/composables/useRecording";

const { baseUrl } = useConfig();
const { isConnected, segments, error, connect, sendAudioChunk, disconnect } = useAudioStream();
const { resetRecording, redoAnnotation, isProcessingReannote } = useRecording();
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

const downloadAudio = () => {
    const downloadUrl = `http://${baseUrl.value}/download/audio`;

    // Create a temporary anchor element
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = "audio.wav"; // Suggested filename for the download

    // Append to body, click, and remove
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    console.log("Downloading Audio file from:", downloadUrl);
};

// Clean up
onUnmounted(() => {
    console.log("Component unmounting...");
    stopRecording();
    disconnect();
});
</script>
