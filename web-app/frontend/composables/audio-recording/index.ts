import { ref, computed } from 'vue';
import type { RecordingState, TranscriptionSegment, TranscriptionResponse } from './types';
import { useAuthStore } from '@/stores/auth';
import { useAdvancedTextProcessing } from '@/composables/useAdvancedTextProcessing';
import { AUDIO_CONFIG } from '@/constants/audio';

export * from './types';

interface RecordingVariables {
  mediaRecorder: MediaRecorder | null;
  audioStream: MediaStream | null;
  audioContext: AudioContext | null;
  analyser: AnalyserNode | null;
  dataArray: Uint8Array | null;
  animationFrame: number | null;
  startTime: number | null;
  timerInterval: NodeJS.Timeout | null;
  recordingTimeout: NodeJS.Timeout | null;
  chunkCount: number;
}

export const useAudioRecording = () => {
  const state = ref<RecordingState>({
    isRecording: false,
    isProcessing: false,
    isTranscribing: false,
    duration: 0,
    error: null,
    audioLevel: 0,
    isWaitingForTranscription: false,
    waitingForStop: false,
  });

  const transcriptionSegments = ref<TranscriptionSegment[]>([]);
  const authStore = useAuthStore();
  const { processTranscriptionBlock: processAdvancedBlock } = useAdvancedTextProcessing();

  // Recording variables
  const variables: RecordingVariables = {
    mediaRecorder: null,
    audioStream: null,
    audioContext: null,
    analyser: null,
    dataArray: null,
    animationFrame: null,
    startTime: null,
    timerInterval: null,
    recordingTimeout: null,
    chunkCount: 0,
  };

  // Create update audio level function
  const updateAudioLevel = () => {
    if (variables.analyser && variables.dataArray && state.value.isRecording) {
      variables.analyser.getByteFrequencyData(variables.dataArray);

      // Calculate the average volume
      const sum = variables.dataArray.reduce((acc, val) => acc + val, 0);
      const average = sum / variables.dataArray.length;

      // Normalize the average to a 0-1 range for the UI
      state.value.audioLevel = Math.min(average / AUDIO_CONFIG.AUDIO_LEVEL_NORMALIZE_THRESHOLD, 1);

      // Request the next frame to continue the animation loop
      variables.animationFrame = requestAnimationFrame(updateAudioLevel);
    }
  };

  // Auto-process new transcription blocks using the advanced text processing
  const autoProcessNewBlock = async (segmentIndex: number) => {
    const segment = transcriptionSegments.value[segmentIndex];
    if (!segment || !segment.text.trim()) return;

    try {
      console.log(`[Auto-Processing] 🚀 Starting processing for block ${segmentIndex}`);
      await processAdvancedBlock(segment.text, segmentIndex);
      console.log(`[Auto-Processing] ✅ Block ${segmentIndex} processed successfully`);
    } catch (error) {
      console.error(`[Auto-Processing] ❌ Block ${segmentIndex} processing failed:`, error);
    }
  };

  // Send audio chunk to backend via HTTP POST
  const sendAudioChunk = async (audioBlob: Blob) => {
    try {
      state.value.isTranscribing = true;

      const formData = new FormData();
      formData.append('file', audioBlob, 'audio.webm');
      formData.append('replace_numbers', 'true');
      formData.append('use_icao_callsigns', 'true');

      const baseUrl = process.env.NODE_ENV === 'development' ? 'http://localhost:5002' : '';
      const response = await fetch(`${baseUrl}/transcribe`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authStore.token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: TranscriptionResponse = await response.json();

      // Process the transcription response - treat each 10-second chunk as one block
      if (data.segments && data.segments.length > 0) {
        // Combine all text from the chunk into a single segment
        const allText = data.segments.map(seg => seg.text.trim()).join(' ').trim();
        
        if (allText) {
          // Each chunk is exactly CHUNK_DURATION_SECONDS, starting at chunkCount * CHUNK_DURATION_SECONDS
          const chunkSegment: TranscriptionSegment = {
            text: allText,
            start: variables.chunkCount * AUDIO_CONFIG.CHUNK_DURATION_SECONDS,
            end: (variables.chunkCount + 1) * AUDIO_CONFIG.CHUNK_DURATION_SECONDS,
          };
          
          const segmentIndex = transcriptionSegments.value.length;
          transcriptionSegments.value.push(chunkSegment);

          // Immediately start processing the block for clean-text and NER
          autoProcessNewBlock(segmentIndex);
        }
      }

      console.log('[Transcription] ✅ HTTP transcription completed, total segments:', transcriptionSegments.value.length);
    } catch (error) {
      console.error('[Transcription] ❌ HTTP transcription failed:', error);
      state.value.error = `Transcription failed: ${error instanceof Error ? error.message : String(error)}`;
    } finally {
      state.value.isTranscribing = false;
    }
  };

  // Start recording with 10-second chunks
  const startRecording = async () => {
    try {
      state.value.error = null;
      state.value.isRecording = true;
      state.value.isTranscribing = false;

      // Initialize chunk counter - continue from where we left off
      variables.chunkCount = transcriptionSegments.value.length;

      console.log('[Recording] 🎬 Starting recording session, chunk count:', variables.chunkCount);

      // Get user's microphone
      variables.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Set up audio analysis for visualization
      variables.audioContext = new AudioContext();
      variables.analyser = variables.audioContext.createAnalyser();
      variables.analyser.fftSize = AUDIO_CONFIG.FFT_SIZE;
      const bufferLength = variables.analyser.frequencyBinCount;
      variables.dataArray = new Uint8Array(bufferLength);

      const microphone = variables.audioContext.createMediaStreamSource(variables.audioStream);
      microphone.connect(variables.analyser);

      // Set up MediaRecorder for configurable duration chunks
      variables.mediaRecorder = new MediaRecorder(variables.audioStream, {
        mimeType: AUDIO_CONFIG.MIME_TYPE
      });

      const audioChunks: Blob[] = [];

      variables.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      variables.mediaRecorder.onstop = async () => {
        if (audioChunks.length > 0) {
          const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
          await sendAudioChunk(audioBlob);
          variables.chunkCount++; // Increment chunk counter after sending
        }
        audioChunks.length = 0;
      };

      // Start recording and schedule 10-second chunks
      variables.mediaRecorder.start();

      const recordChunk = () => {
        if (variables.mediaRecorder && variables.mediaRecorder.state === 'recording') {
          variables.mediaRecorder.stop();

          // Start next chunk if still recording
          if (state.value.isRecording) {
            setTimeout(() => {
              if (variables.mediaRecorder && state.value.isRecording) {
                variables.mediaRecorder.start();
                variables.recordingTimeout = setTimeout(recordChunk, AUDIO_CONFIG.CHUNK_DURATION_SECONDS * 1000);
              }
            }, AUDIO_CONFIG.CHUNK_RESTART_DELAY);
          }
        }
      };

      // Schedule first chunk completion after configured duration
      variables.recordingTimeout = setTimeout(recordChunk, AUDIO_CONFIG.CHUNK_DURATION_SECONDS * 1000);

      // Start timer and audio level monitoring
      variables.startTime = Date.now();
      variables.timerInterval = setInterval(() => {
        if (variables.startTime) {
          const elapsed = Math.floor((Date.now() - variables.startTime) / 1000);
          state.value.duration = elapsed;
        }
      }, AUDIO_CONFIG.TIMER_UPDATE_INTERVAL);

      // Start audio level monitoring
      updateAudioLevel();

    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.value.error = 'Failed to start recording: ' + message;
      state.value.isRecording = false;
      state.value.isTranscribing = false;
    }
  };

  // Stop recording
  const stopRecording = () => {
    state.value.isRecording = false;
    state.value.waitingForStop = false;

    // Clear recording timeout
    if (variables.recordingTimeout) {
      clearTimeout(variables.recordingTimeout);
      variables.recordingTimeout = null;
    }

    // Stop media recorder and send final chunk
    if (variables.mediaRecorder && variables.mediaRecorder.state === 'recording') {
      variables.mediaRecorder.stop();
    }
    variables.mediaRecorder = null;

    // Clean up audio resources
    if (variables.audioContext && variables.audioContext.state !== 'closed') {
      try {
        variables.audioContext.close();
      } catch (e) {
        console.warn('Could not close audio context:', e);
      }
    }
    variables.audioContext = null;

    // Stop audio stream
    if (variables.audioStream) {
      variables.audioStream.getTracks().forEach(track => track.stop());
      variables.audioStream = null;
    }

    // Clean up animation frame
    if (variables.animationFrame) {
      cancelAnimationFrame(variables.animationFrame);
      variables.animationFrame = null;
    }

    // Clear timer
    if (variables.timerInterval) {
      clearInterval(variables.timerInterval);
      variables.timerInterval = null;
    }

    // Reset audio level and timer
    state.value.audioLevel = 0;
    state.value.duration = 0;
    variables.startTime = null;
    variables.analyser = null;
    variables.dataArray = null;

    console.log('[Recording] 🎬 Recording session ended');
  };

  // Toggle recording function
  const toggleRecording = async () => {
    if (!state.value.isRecording) {
      if (state.value.waitingForStop) {
        console.log('Waiting for stop, early return');
        return;
      }
      await startRecording();
    } else {
      stopRecording();
    }
  };

  // Transcribe file (for file uploads) - use existing HTTP endpoint
  const transcribeFile = async (file: File) => {
    state.value.isProcessing = true;
    state.value.isTranscribing = true;
    state.value.error = null;
    clearTranscription();

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('replace_numbers', 'true');
      formData.append('use_icao_callsigns', 'true');

      const baseUrl = process.env.NODE_ENV === 'development' ? 'http://localhost:5002' : '';
      const response = await fetch(`${baseUrl}/transcribe`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authStore.token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: TranscriptionResponse = await response.json();

      if (data.segments && data.segments.length > 0) {
        transcriptionSegments.value.push(...data.segments);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.value.error = 'Transcription failed: ' + message;
      console.error('Transcription error:', error);
    } finally {
      state.value.isProcessing = false;
      state.value.isTranscribing = false;
    }
  };

  // Clear transcription
  const clearTranscription = () => {
    transcriptionSegments.value = [];
    variables.chunkCount = 0;
  };

  // Update segment
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
    toggleRecording,
    transcribeFile,
    clearTranscription,
    updateSegment,
    autoProcessNewBlock, // Expose for manual processing
  };
};