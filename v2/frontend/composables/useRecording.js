import { ref } from "vue";

import { useAudioStream } from "./useAudioStream";
import { useConfig } from "./useConfig";

export const useRecording = () => {
    const error = ref(null);
    const isProcessingReannote = ref(false);

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

    return {
        error,
        resetRecording,

        redoAnnotation,
        isProcessingReannote,
    };
};
