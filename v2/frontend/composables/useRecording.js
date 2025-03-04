import { ref } from "vue";

import { useAudioStream } from "./useAudioStream";
import { useConfig } from "./useConfig";

export const useRecording = () => {
    const error = ref(null);

    const { segments } = useAudioStream();
    const { baseUrl } = useConfig();

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

    return {
        error,
        resetRecording,
    };
};
