<template>
    <div class="font-[Inter] text-white bg-stone-950 h-screen w-screen flex flex-row items-center justify-center gap-4">
        <div class="flex flex-row gap-4 relative">
            <div class="flex flex-col gap-4">
                <div class="flex flex-col items-center justify-center border-2 border-stone-800 bg-black p-4 rounded-2xl min-w-80">
                    <!-- iOS Style Toggle -->
                    <div class="relative h-10 w-40 bg-stone-900 rounded-full p-1">
                        <!-- Moving Pill -->
                        <div
                            class="absolute top-1 h-8 bg-stone-800 rounded-full transition-all duration-300 ease-in-out"
                            :style="{
                                left: selectedComponent === 'recorder' ? '4px' : '50%',
                                width: 'calc(50% - 4px)',
                            }"
                        ></div>
                        <!-- Option Buttons -->
                        <div class="relative flex h-full">
                            <button
                                @click="selectedComponent = 'recorder'"
                                class="flex-1 z-10 text-sm font-medium rounded-full flex items-center justify-center transition-colors duration-300"
                                :class="selectedComponent === 'recorder' ? 'text-white' : 'text-stone-400'"
                            >
                                Live
                            </button>
                            <button
                                @click="selectedComponent = 'upload'"
                                class="flex-1 z-10 text-sm font-medium rounded-full flex items-center justify-center transition-colors duration-300"
                                :class="selectedComponent === 'upload' ? 'text-white' : 'text-stone-400'"
                            >
                                Upload
                            </button>
                        </div>
                    </div>
                    <!-- Render component based on selection -->
                    <AudioLiveRecorder v-if="selectedComponent === 'recorder'" />
                    <AudioUpload v-if="selectedComponent === 'upload'" />
                </div>
                <!-- Transcription/Diarization Area -->
                <div class="border-2 border-stone-800 bg-black p-4 rounded-2xl" v-if="segments.length > 0">
                    <TranscriptBox :segments="segments" class="max-h-60 min-w-64 max-w-2xl pe-4" />
                    <div class="flex flex-row items-center justify-center mt-4">
                        <button
                            v-if="segments.length > 5"
                            @click="downloadRTTM"
                            class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center bg-white/10 hover:bg-white/20"
                        >
                            <Icon name="tabler:download" class="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useConfig } from "~/composables/useConfig";
import { useAudioStream } from "~/composables/useAudioStream";

const { baseUrl } = useConfig();
const { segments } = useAudioStream();

// State for selected component
const selectedComponent = ref("upload"); // Default to upload

// Function to download RTTM file
const downloadRTTM = () => {
    const downloadUrl = `http://${baseUrl.value}/download/rttm`;

    // Create a temporary anchor element
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = "diarization.rttm"; // Suggested filename for the download

    // Append to body, click, and remove
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    console.log("Downloading RTTM file from:", downloadUrl);
};
</script>
