import { ref, computed } from 'vue';
// If you are using Nuxt, you might need to import useNuxtApp from '#app'
// import { useNuxtApp } from '#app';

export interface TranscriptionSegment {
  text: string;
  start: number;
  end: number;
}

export interface TranscriptionResponse {
  segments: TranscriptionSegment[];
  chunk_id: string | null;
  processing_applied: {
    numbers_replaced: boolean;
    icao_callsigns_applied: boolean;
  };
}

export interface RecordingState {
  isRecording: boolean;
  isProcessing: boolean;
  duration: number;
  error: string | null;
  audioLevel: number;
  isWaitingForTranscription: boolean;
}

export const useAudioRecording = () => {
  const state = ref<RecordingState>({
    isRecording: false,
    isProcessing: false,
    duration: 0,
    error: null,
    audioLevel: 0,
    isWaitingForTranscription: false,
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

  // --- Chunking variables ---
  let chunkInterval: NodeJS.Timeout | null = null;
  const CHUNK_DURATION = 30000; // 30 seconds in milliseconds

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
   * Starts the recording process with 30-second chunking.
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
      if (audioContext && audioContext.state === 'suspended') {
        await audioContext.resume();
        console.log("AudioContext was suspended and has been resumed.");
      }

      if (!destination) {
        throw new Error('Failed to initialize the audio processing pipeline.');
      }

      // 3. Initialize MediaRecorder for chunked recording
      mediaRecorder = new MediaRecorder(destination.stream);

      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0) {
          const audioBlob = new Blob([event.data], { type: 'audio/webm' });
          await transcribeAudioChunk(audioBlob);
        }
      };

      mediaRecorder.onstop = async () => {
        // This handles the final chunk when recording is manually stopped
        // ondataavailable will be called before onstop, so no need to process here
      };

      // Start recording with timeslice for 30-second chunks
      mediaRecorder.start(CHUNK_DURATION);
      updateAudioLevel();

      // Set up interval to restart recording every 30 seconds for continuous chunking
      chunkInterval = setInterval(() => {
        if (mediaRecorder && state.value.isRecording && mediaRecorder.state === 'recording') {
          // Stop current recording (triggers ondataavailable) and start a new one
          mediaRecorder.stop();
          setTimeout(() => {
            if (state.value.isRecording && destination) {
              mediaRecorder = new MediaRecorder(destination.stream);

              mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                  const audioBlob = new Blob([event.data], { type: 'audio/webm' });
                  await transcribeAudioChunk(audioBlob);
                }
              };

              mediaRecorder.start(CHUNK_DURATION);
            }
          }, 100); // Small delay to ensure clean stop/start
        }
      }, CHUNK_DURATION);

    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.value.error = 'Failed to start recording: ' + message;
      state.value.isRecording = false;
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

      // Clear the chunk interval
      if (chunkInterval) {
        clearInterval(chunkInterval);
        chunkInterval = null;
      }

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
   * Sends a blob to the transcription API.
   * @param blob The audio blob to transcribe.
   */
  const transcribeAudioChunk = async (blob: Blob) => {
    state.value.isWaitingForTranscription = true;
    state.value.error = null;

    try {
      const { $transcribeAudio } = useNuxtApp();
      const response: TranscriptionResponse = await $transcribeAudio(blob);

      if (response?.segments && response.segments.length > 0) {
        const lastEndTime =
          transcriptionSegments.value.length > 0
            ? transcriptionSegments.value[transcriptionSegments.value.length - 1].end
            : 0

        const adjustedSegments = response.segments.map((segment) => ({
          ...segment,
          start: segment.start + lastEndTime,
          end: segment.end + lastEndTime,
        }))

        transcriptionSegments.value.push(...adjustedSegments)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.value.error = 'Transcription failed: ' + message;
      console.error('Transcription error:', error);
    } finally {
      state.value.isWaitingForTranscription = false;
    }
  };

  /**
   * Sends a file to the transcription API (for file uploads).
   * @param file The audio file to transcribe.
   */
  const transcribeFile = async (file: File) => {
    state.value.isProcessing = true;
    state.value.error = null;
    clearTranscription();

    try {
      const { $transcribeAudio } = useNuxtApp();
      const response: TranscriptionResponse = await $transcribeAudio(file);

      if (response?.segments && response.segments.length > 0) {
        transcriptionSegments.value.push(...response.segments);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.value.error = 'Transcription failed: ' + message;
      console.error('Transcription error:', error);
    } finally {
      state.value.isProcessing = false;
    }
  };


  const clearTranscription = () => {
    transcriptionSegments.value = [];
  };

  const updateSegment = (index: number, newText: string) => {
    if (transcriptionSegments.value[index]) {
      transcriptionSegments.value[index].text = newText;
    }
  };

  return {
    state: computed(() => state.value),
    transcriptionSegments: computed(() => transcriptionSegments.value),
    startRecording,
    stopRecording,
    transcribeFile,
    clearTranscription,
    updateSegment,
  };
};
