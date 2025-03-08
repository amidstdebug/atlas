<template>
    <div class="font-[Inter] text-white bg-stone-950 h-screen w-screen flex flex-row items-center justify-center gap-4">
        <div class="flex flex-row gap-4 relative">
            <div class="flex flex-col gap-4">
                <div class="flex flex-col items-center justify-center border-2 border-stone-800 bg-black p-6 rounded-2xl">
                    <AudioLiveRecorder />
                </div>
                <!-- Transcription/Diarization Area -->
                <div class="border-2 border-stone-800 bg-black px-6 pt-6 pb-2 rounded-2xl" v-if="segments.length > 0">
                    <TranscriptBox :segments="segments" class="max-h-60 min-w-64 max-w-2xl pe-4" />
                    <div class="flex flex-row items-center justify-center mt-2">
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
import { onMounted, onUnmounted } from "vue";
import { useConfig } from "~/composables/useConfig";
import { useAudioStream } from "~/composables/useAudioStream";

const { baseUrl } = useConfig();

const { segments } = useAudioStream();

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
