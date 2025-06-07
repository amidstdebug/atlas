import { ref, computed } from 'vue';
// If you are using Nuxt, you might need to import useNuxtApp from '#app'
// import { useNuxtApp } from '#app';

export interface TranscriptionSegment {
  id: string;
  text: string;
  timestamp: number;
  confidence?: number;
}

export interface RecordingState {
  isRecording: boolean;
  isProcessing: boolean;
  duration: number;
  error: string | null;
  audioLevel: number;
}

export const useAudioRecording = () => {
  const state = ref<RecordingState>({
    isRecording: false,
    isProcessing: false,
    duration: 0,
    error: null,
    audioLevel: 0,
  });

  const transcriptionSegments = ref<TranscriptionSegment[]>([]);

  // --- Audio graph variables ---
  let mediaRecorder: MediaRecorder | null = null;
  let audioStream: MediaStream | null = null;
  let audioContext: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  let dataArray: Uint8Array | null = null;
  let animationFrame: number | null = null;
  // This destination node is the key to fixing the recording issue.
  let destinationNode: MediaStreamAudioDestinationNode | null = null;

  /**
   * Continuously samples the audio frequency to update the visual audio level.
   */
  const updateAudioLevel = () => {
    if (analyser && dataArray && state.value.isRecording) {
      analyser.getByteFrequencyData(dataArray);

      // Calculate the average volume
      const sum = dataArray.reduce((acc, val) => acc + val, 0);
      const average = sum / dataArray.length;

      // Normalize the average to a 0-1 range for the UI
      state.value.audioLevel = Math.min(average / 128, 1);

      // Log the current audio level to the console for debugging
      console.log(`Current Audio Level: ${state.value.audioLevel}`);

      // Request the next frame to continue the animation loop
      animationFrame = requestAnimationFrame(updateAudioLevel);
    }
  };

  /**
   * Sets up the Web Audio API graph to process audio for visualization
   * and recording.
   * @param stream The raw audio stream from the microphone.
   * @returns The destination node which provides the final, processable audio stream.
   */
  const setupAudioAnalysis = (stream: MediaStream): MediaStreamAudioDestinationNode | null => {
    try {
      audioContext = new AudioContext();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;

      const bufferLength = analyser.frequencyBinCount;
      dataArray = new Uint8Array(bufferLength);

      const source = audioContext.createMediaStreamSource(stream);
      // Create a destination to capture the audio from the graph
      destinationNode = audioContext.createMediaStreamDestination();

      // --- This is the corrected audio routing ---
      // 1. Connect the microphone source to the analyser
      source.connect(analyser);
      // 2. Connect the analyser to the final destination
      analyser.connect(destinationNode);

      return destinationNode;
    } catch (error) {
      console.warn('Audio analysis setup failed:', error);
      state.value.error = 'Audio analysis setup failed. Your browser might not support it.';
      return null;
    }
  };

  /**
   * Starts the recording process. It requests microphone access, sets up the
   * audio graph, and initializes the MediaRecorder.
   */
  const startRecording = async () => {
    try {
      state.value.error = null;
      state.value.isRecording = true;

      // 1. Get user's microphone
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // 2. Set up the audio graph for analysis and get the destination stream
      const destination = setupAudioAnalysis(audioStream);

      // --- FIX: Resume AudioContext if it's suspended ---
      // This is crucial for browsers that auto-suspend audio until user interaction.
      if (audioContext && audioContext.state === 'suspended') {
        await audioContext.resume();
        console.log("AudioContext was suspended and has been resumed.");
      }

      if (!destination) {
        throw new Error('Failed to initialize the audio processing pipeline.');
      }

      // 3. IMPORTANT: Record from the destination's stream, not the original audioStream.
      // This stream contains the audio that has passed through the analyser.
      mediaRecorder = new MediaRecorder(destination.stream);
      const chunks: Blob[] = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
            chunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Use a more common and compatible mimetype like 'audio/webm'
        const audioBlob = new Blob(chunks, { type: 'audio/webm' });
        await processAudioBlob(audioBlob);
      };

      // Start recording and begin the audio level visualization loop
      mediaRecorder.start();
      updateAudioLevel();

    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.value.error = 'Failed to start recording: ' + message;
      state.value.isRecording = false; // Reset state on failure
    }
  };

  /**
   * Stops the recording, tears down the audio graph, and releases microphone access.
   */
  const stopRecording = () => {
    if (mediaRecorder && state.value.isRecording) {
      mediaRecorder.stop();
      state.value.isRecording = false;
      state.value.audioLevel = 0;

      // Clean up the animation frame
      if (animationFrame) {
        cancelAnimationFrame(animationFrame);
        animationFrame = null;
      }

      // Close the audio context to release resources
      if (audioContext) {
        audioContext.close();
        audioContext = null;
      }

      // Stop all tracks on the original microphone stream to turn off the mic indicator
      if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
      }

      // Clear variables
      analyser = null;
      dataArray = null;
      destinationNode = null;
    }
  };

  /**
   * Sends a file to the transcription API.
   * @param file The audio file to transcribe.
   */
  const transcribeFile = async (file: File) => {
    state.value.isProcessing = true;
    state.value.error = null;

    try {
      const formData = new FormData();
      formData.append('file', file);

      // This is a placeholder for your Nuxt API call.
      // const { $api } = useNuxtApp();
      // const response = await $api.post('/transcribe', formData, { ... });

      // --- Mock API Response for demonstration ---
      console.log("Transcribing file:", file.name, "size:", file.size);
      await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate network delay
      const mockResponse = {
          data: {
              transcription: "This is a simulated transcription of your recording."
          }
      };
      // --- End Mock API Response ---

      if (mockResponse.data?.transcription) {
        const newSegment: TranscriptionSegment = {
          id: Date.now().toString(),
          text: mockResponse.data.transcription,
          timestamp: Date.now(),
        };
        transcriptionSegments.value.push(newSegment);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.value.error = 'Transcription failed: ' + message;
    } finally {
      state.value.isProcessing = false;
    }
  };

  /**
   * Wraps the recorded audio blob in a File object and sends it for transcription.
   * @param blob The recorded audio data.
   */
  const processAudioBlob = async (blob: Blob) => {
    // Note: Most browsers record in webm or ogg format. Naming it .wav doesn't convert it.
    // Your server-side transcription service needs to handle the actual format (e.g., audio/webm).
    const file = new File([blob], 'recording.webm', { type: 'audio/webm' });
    await transcribeFile(file);
  };

  const clearTranscription = () => {
    transcriptionSegments.value = [];
  };

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return {
    state: computed(() => state.value),
    transcriptionSegments: computed(() => transcriptionSegments.value),
    startRecording,
    stopRecording,
    transcribeFile,
    clearTranscription,
    formatTimestamp,
  };
};
