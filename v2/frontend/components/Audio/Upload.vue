<template>
    <div class="flex flex-col items-center justify-center mt-4">
        <input type="file" ref="fileInput" accept="audio/*" class="hidden" @change="handleFileSelected" />

        <!-- Upload progress indicator -->
        <div v-if="isUploading" class="w-full max-w-xs mb-4">
            <div v-if="uploadProgress < 100">
                <div class="text-xs text-center mb-1">Uploading: {{ uploadProgress }}%</div>
                <div class="w-full bg-white/10 rounded-full h-1">
                    <div class="bg-white h-1 rounded-full" :style="{ width: `${uploadProgress}%` }"></div>
                </div>
            </div>
            <div v-else-if="uploadProgress == 100">
                <div class="text-xs text-center">Annotating...</div>
            </div>
        </div>

        <!-- Error message -->
        <div v-if="error" class="text-xs text-red-400 mb-4">
            {{ error }}
        </div>

        <button
            class="p-3 rounded-full transition-all duration-300 aspect-square flex items-center justify-center bg-white/10 hover:bg-white/20"
            title="Upload recording"
            :disabled="isUploading"
            @click="triggerFileDialog"
        >
            <Icon v-if="!isUploading" name="tabler:upload" class="h-4 w-4" />
            <Icon v-else name="tabler:loader" class="h-4 w-4 animate-spin" />
        </button>
    </div>
</template>

<script setup>
import { ref } from "vue";
import { useRecording } from "~/composables/useRecording";
import { useAudioStream } from "~/composables/useAudioStream";

const fileInput = ref(null);
const { uploadRecording, isUploading, uploadProgress, error } = useRecording();
const { segments } = useAudioStream();

const triggerFileDialog = () => {
    if (!isUploading.value) {
        fileInput.value.click();
    }
};

const handleFileSelected = async (event) => {
    const file = event.target.files[0];
    if (file) {
        try {
            segments.value = [];
            await uploadRecording(file);
        } catch (err) {
            // Error is already handled in the composable
            console.error("Upload failed:", err);
        } finally {
            // Reset the file input to allow selecting the same file again
            event.target.value = "";
        }
    }
};
</script>
