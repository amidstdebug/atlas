import { ref } from "vue";

import { useAudioStream } from "./useAudioStream";
import { useConfig } from "./useConfig";

export const useRecording = () => {
    const error = ref(null);
    const isProcessingReannote = ref(false);
    const isUploading = ref(false);
    const uploadProgress = ref(0);

    const { segments, getSegments } = useAudioStream();
    const { baseUrl } = useConfig();

    const redoAnnotation = async () => {
        try {
            isProcessingReannote.value = true;
            // Post to the reset endpoint
            const response = await fetch(`http://${baseUrl.value}/reannotate`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
            });

            if (!response.ok) {
                throw new Error(`Failed to redo annotation: ${response.status}`);
            }
        } catch (e) {
            error.value = e.message;
            console.error("Error redoing annotation:", e);
        }

        getSegments();

        isProcessingReannote.value = false;
    };

    const resetRecording = async () => {
        try {
            // Post to the reset endpoint
            const response = await fetch(`http://${baseUrl.value}/reset`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
            });

            if (!response.ok) {
                throw new Error(`Failed to reset recording: ${response.status}`);
            }

            // Clear the segments array
            segments.value = [];
        } catch (e) {
            error.value = e.message;
            console.error("Error resetting recording:", e);
        }
    };

    const uploadRecording = async (file) => {
        if (!file) {
            error.value = "No file selected";
            return;
        }

        try {
            isUploading.value = true;
            uploadProgress.value = 0;
            error.value = null;

            // Create FormData to send the file
            const formData = new FormData();
            formData.append("file", file);

            // Use fetch with upload progress tracking
            const xhr = new XMLHttpRequest();

            // Set up the progress event handler
            xhr.upload.addEventListener("progress", (event) => {
                if (event.lengthComputable) {
                    uploadProgress.value = Math.round((event.loaded / event.total) * 100);
                }
            });

            // Create a promise to handle the upload
            const uploadPromise = new Promise((resolve, reject) => {
                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve(JSON.parse(xhr.responseText));
                    } else {
                        reject(new Error(`Upload failed with status: ${xhr.status}`));
                    }
                };

                xhr.onerror = () => {
                    reject(new Error("Network error during upload"));
                };
            });

            // Send the request
            xhr.open("POST", `http://${baseUrl.value}/upload/audio`);
            xhr.send(formData);

            // Wait for upload to complete
            const result = await uploadPromise;

            // Get updated segments after successful upload
            await getSegments();

            return result;
        } catch (e) {
            error.value = e.message;
            console.error("Error uploading file:", e);
            throw e;
        } finally {
            isUploading.value = false;
        }
    };

    return {
        error,
        resetRecording,

        redoAnnotation,
        isProcessingReannote,

        uploadRecording,
        isUploading,
        uploadProgress,
    };
};
