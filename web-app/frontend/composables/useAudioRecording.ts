import { ref, computed } from 'vue';
// If you are using Nuxt, you might need to import useNuxtApp from '#app'
// import { useNuxtApp } from '#app';
import { useAuthStore } from '@/stores/auth';

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
  isTranscribing: boolean;
  duration: number;
  error: string | null;
  audioLevel: number;
  isWaitingForTranscription: boolean;
  waitingForStop: boolean;
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


  // --- Reference code variables ---
  let chunkDuration = 1000; // 1 second chunks
  let userClosing = false;
  let lastReceivedData: any = null;
  let startTime: number | null = null;
  let timerInterval: NodeJS.Timeout | null = null;
  let lastProcessedText = ''; // Track the last processed text to detect changes
  let currentSessionStartTime = 0; // Track when current recording session started

  // --- Audio graph variables ---
  let mediaRecorder: MediaRecorder | null = null;
  let audioStream: MediaStream | null = null;
  let audioContext: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  let dataArray: Uint8Array | null = null;
  let animationFrame: number | null = null;
  let destinationNode: MediaStreamAudioDestinationNode | null = null;

  // --- WebSocket variables ---
  let websocket: WebSocket | null = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;


  /**
   * Continuously samples the audio frequency for visual indication.
   */
  const updateAudioLevel = () => {
    if (analyser && dataArray && state.value.isRecording) {
      analyser.getByteFrequencyData(dataArray);

      // Calculate the average volume
      const sum = dataArray.reduce((acc, val) => acc + val, 0);
      const average = sum / dataArray.length;

      // Normalize the average to a 0-1 range for the UI
      state.value.audioLevel = Math.min(average / 128, 1);

      // Request the next frame to continue the animation loop
      animationFrame = requestAnimationFrame(updateAudioLevel);
    }
  };

  /**
   * Initialize WebSocket connection for live transcription using reference code approach
   */
  const setupWebSocket = (): Promise<void> => {
    return new Promise((resolve, reject) => {
      try {
        const baseUrl = process.env.NODE_ENV === 'development' ? 'ws://localhost:5002' : 'wss://your-domain.com';

        // Get JWT token from auth store
        const authStore = useAuthStore();
        const token = authStore.token;
        const url = token ?
          `${baseUrl}/ws/live-transcribe?token=${encodeURIComponent(token)}` :
          `${baseUrl}/ws/live-transcribe`;

        console.log('[WebSocket] Attempting to connect to:', url);
        websocket = new WebSocket(url);
      } catch (error) {
        console.error('[WebSocket] Failed to create WebSocket:', error);
        state.value.error = 'Invalid WebSocket URL. Please check and try again.';
        reject(error);
        return;
      }

      websocket.onopen = () => {
        console.log('[WebSocket] ✅ Connected to server successfully');
        state.value.error = null;
        resolve();
      };

      websocket.onclose = (event) => {
        console.log('[WebSocket] Connection closed. Code:', event.code, 'Reason:', event.reason, 'UserClosing:', userClosing);
        if (userClosing) {
          if (state.value.waitingForStop) {
            console.log('[WebSocket] Processing finalized or connection closed');
            state.value.error = 'Processing finalized or connection closed.';
            if (lastReceivedData) {
              console.log('[WebSocket] Processing final transcription data:', lastReceivedData);
              processTranscriptionData(lastReceivedData, true);
            }
          }
        } else {
          console.error('[WebSocket] ❌ Disconnected from the WebSocket server unexpectedly');
          state.value.error = 'Disconnected from the WebSocket server.';
          if (state.value.isRecording) {
            stopRecording();
          }
        }
        state.value.isRecording = false;
        state.value.waitingForStop = false;
        userClosing = false;
        lastReceivedData = null;
        websocket = null;

        // Re-enable recording after processing is complete
        if (state.value.error === 'Finished processing audio! Ready to record again.') {
          state.value.error = null;
        }
      };

      websocket.onerror = (error) => {
        console.error('[WebSocket] ❌ Error connecting to WebSocket:', error);
        state.value.error = 'Error connecting to WebSocket.';
        reject(new Error('Error connecting to WebSocket'));
      };

      // Handle messages from server
      websocket.onmessage = (event) => {
        console.log('[WebSocket] 📥 Received message, size:', event.data.length);
        let data;
        try {
          data = JSON.parse(event.data);
          console.log('[WebSocket] 📄 Parsed message data:', data);
        } catch (parseError) {
          console.error('[WebSocket] ❌ Failed to parse message:', parseError, 'Raw data:', event.data);
          return;
        }

        // Check for status messages
        if (data.type === 'ready_to_stop') {
          console.log('[WebSocket] 🏁 Ready to stop received, finalizing display and closing WebSocket');
          state.value.waitingForStop = false;

          if (lastReceivedData) {
            console.log('[WebSocket] Processing final data before close:', lastReceivedData);
            processTranscriptionData(lastReceivedData, true);
          }
          state.value.error = 'Finished processing audio! Ready to record again.';
          console.log('[WebSocket] ✅ Transcription complete, ready for next recording');

          if (websocket) {
            websocket.close();
          }
          return;
        }

        lastReceivedData = data;
        processTranscriptionData(data, false);
      };
    });
  };

  /**
   * Parse timestamp string like "0:00:02" to seconds
   */
  const parseTimestamp = (timestamp: string | number): number => {
    if (typeof timestamp === 'number') return timestamp;
    if (!timestamp || typeof timestamp !== 'string') return 0;
    
    const parts = timestamp.split(':');
    if (parts.length === 3) {
      const hours = parseInt(parts[0]) || 0;
      const minutes = parseInt(parts[1]) || 0;
      const seconds = parseInt(parts[2]) || 0;
      return hours * 3600 + minutes * 60 + seconds;
    } else if (parts.length === 2) {
      const minutes = parseInt(parts[0]) || 0;
      const seconds = parseInt(parts[1]) || 0;
      return minutes * 60 + seconds;
    }
    return parseFloat(timestamp) || 0;
  };

  /**
   * Break up cumulative text into smaller, natural segments
   */
  const breakTextIntoSegments = (text: string, startTime: number, endTime: number): TranscriptionSegment[] => {
    if (!text || !text.trim()) return [];
    
    // Split on sentence endings and natural pauses
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
    if (sentences.length <= 1) {
      // If no natural breaks, split on commas or long phrases
      const phrases = text.split(/[,;]+|(?<=\w)\s+(?=\w{4,})/).filter(s => s.trim().length > 0);
      if (phrases.length <= 1) {
        return [{ text: text.trim(), start: startTime, end: endTime }];
      }
      sentences.splice(0, sentences.length, ...phrases);
    }
    
    const segments: TranscriptionSegment[] = [];
    const duration = endTime - startTime;
    const avgSegmentDuration = duration / sentences.length;
    
    sentences.forEach((sentence, index) => {
      const segmentStart = startTime + (index * avgSegmentDuration);
      const segmentEnd = index === sentences.length - 1 ? endTime : startTime + ((index + 1) * avgSegmentDuration);
      
      segments.push({
        text: sentence.trim(),
        start: Math.round(segmentStart * 100) / 100,
        end: Math.round(segmentEnd * 100) / 100
      });
    });
    
    return segments;
  };

  /**
   * Process transcription data from WebSocket - handles cumulative text properly
   */
  const processTranscriptionData = (data: any, isFinalizing: boolean) => {
    console.log('[Transcription] 🔄 Processing data. IsFinalizing:', isFinalizing, 'Data:', data);
    
    // Handle different data formats from backend
    if (data.segments && Array.isArray(data.segments)) {
      console.log('[Transcription] 📝 Processing segments:', data.segments.length, 'segments');
      
      // Process segments with individual timestamps (not merged like reference code)
      const newSegments = data.segments.map((seg: any, index: number) => {
        const segment = {
          text: seg.text || '',
          start: parseTimestamp(seg.start),
          end: parseTimestamp(seg.end)
        };
        console.log(`[Transcription] Segment ${index}:`, segment);
        return segment;
      });

      if (isFinalizing) {
        console.log('[Transcription] 🏁 Finalizing - adding', newSegments.length, 'segments to existing', transcriptionSegments.value.length);
        transcriptionSegments.value.push(...newSegments);
        console.log('[Transcription] ✅ Total segments after finalization:', transcriptionSegments.value.length);
      } else {
        console.log('[Transcription] 🔄 Live update - processing', newSegments.length, 'new segments');
        // For live updates, add segments without clearing previous sessions
        newSegments.forEach(newSeg => {
          const existingIndex = transcriptionSegments.value.findIndex(seg => 
            Math.abs(seg.start - newSeg.start) < 0.1
          );
          
          if (existingIndex >= 0) {
            console.log('[Transcription] 📝 Updating existing segment at index', existingIndex);
            transcriptionSegments.value[existingIndex] = newSeg;
          } else {
            console.log('[Transcription] ➕ Adding new segment at time', newSeg.start);
            const insertIndex = transcriptionSegments.value.findIndex(seg => seg.start > newSeg.start);
            if (insertIndex >= 0) {
              transcriptionSegments.value.splice(insertIndex, 0, newSeg);
            } else {
              transcriptionSegments.value.push(newSeg);
            }
          }
        });
        console.log('[Transcription] 📊 Current total segments:', transcriptionSegments.value.length);
      }

      state.value.isTranscribing = false;
      console.log('[Transcription] ✅ Transcription processing completed');
    } 
    // Handle lines format - this is the cumulative text case
    else if (data.lines && Array.isArray(data.lines)) {
      console.log('[Transcription] 📄 Processing lines format:', data.lines.length, 'lines');
      
      data.lines.forEach((line: any, lineIndex: number) => {
        if (!line.text || !line.text.trim()) return;
        
        const startTime = parseTimestamp(line.beg) + currentSessionStartTime;
        const endTime = parseTimestamp(line.end) + currentSessionStartTime;
        const fullText = line.text.trim();
        
        console.log(`[Transcription] Processing line ${lineIndex}: "${fullText}" (${startTime}s - ${endTime}s)`);
        
        if (isFinalizing) {
          // For finalizing, break the cumulative text into natural segments
          console.log('[Transcription] 🏁 Finalizing line - breaking into segments');
          const brokenSegments = breakTextIntoSegments(fullText, startTime, endTime);
          console.log('[Transcription] Created', brokenSegments.length, 'segments from final text');
          transcriptionSegments.value.push(...brokenSegments);
        } else {
          // For live updates, check if this is new text
          if (fullText !== lastProcessedText) {
            console.log('[Transcription] 🔄 New text detected, processing incremental update');
            
            // Find what's new compared to last processed text
            let newText = '';
            if (fullText.startsWith(lastProcessedText)) {
              newText = fullText.substring(lastProcessedText.length).trim();
              console.log('[Transcription] New text portion:', `"${newText}"`);
            } else {
              // Text changed completely, replace the last segment
              newText = fullText;
              console.log('[Transcription] Complete text replacement:', `"${newText}"`);
              
              // Remove segments from current session
              const sessionStartIndex = transcriptionSegments.value.findIndex(seg => seg.start >= currentSessionStartTime);
              if (sessionStartIndex >= 0) {
                transcriptionSegments.value.splice(sessionStartIndex);
                console.log('[Transcription] Cleared current session segments');
              }
            }
            
            if (newText) {
              // Calculate timing for new text portion
              const textRatio = newText.length / fullText.length;
              const duration = endTime - startTime;
              const newTextStart = endTime - (duration * textRatio);
              
              console.log('[Transcription] Adding new segment:', `"${newText}" (${newTextStart}s - ${endTime}s)`);
              
              // Create segments for the new text
              const newSegments = breakTextIntoSegments(newText, newTextStart, endTime);
              transcriptionSegments.value.push(...newSegments);
            }
            
            lastProcessedText = fullText;
          } else {
            console.log('[Transcription] 📄 No new text, skipping update');
          }
        }
      });
      
      // Handle buffer text if present
      if (data.buffer_transcription && data.buffer_transcription.trim()) {
        console.log('[Transcription] 📝 Processing buffer text:', `"${data.buffer_transcription}"`);
        // Add buffer as a temporary segment
        const bufferSegment = {
          text: data.buffer_transcription.trim(),
          start: parseTimestamp(data.lines[0]?.end || 0) + currentSessionStartTime,
          end: parseTimestamp(data.lines[0]?.end || 0) + currentSessionStartTime + 1
        };
        
        // Remove any existing buffer segments and add new one
        const lastSegment = transcriptionSegments.value[transcriptionSegments.value.length - 1];
        if (lastSegment && lastSegment.text.includes(data.buffer_transcription.trim())) {
          // Buffer is already incorporated
        } else {
          transcriptionSegments.value.push(bufferSegment);
        }
      }
      
      state.value.isTranscribing = false;
      console.log('[Transcription] ✅ Lines processing completed, total segments:', transcriptionSegments.value.length);
    }
    else if (data.type === 'processing') {
      console.log('[Transcription] ⏳ Processing status received');
      state.value.isTranscribing = true;
    } else if (data.type === 'error') {
      console.error('[Transcription] ❌ Error received:', data.message);
      state.value.error = data.message;
      state.value.isTranscribing = false;
    } else {
      console.warn('[Transcription] ⚠️ Unknown data format received:', data);
    }
  };

  /**
   * Toggle recording function using reference code approach
   */
  const toggleRecording = async () => {
    if (!state.value.isRecording) {
      if (state.value.waitingForStop) {
        console.log('Waiting for stop, early return');
        return;
      }

      console.log('Connecting to WebSocket');
      try {
        // Always create a new WebSocket connection for each recording session
        await setupWebSocket();
        await startRecording();
      } catch (err) {
        state.value.error = 'Could not connect to WebSocket or access mic. Aborted.';
        console.error(err);
      }
    } else {
      console.log('Stopping recording');
      stopRecording();
    }
  };

  /**
   * Starts the recording process using reference code approach with chunked audio.
   */
  const startRecording = async () => {
    try {
      state.value.error = null;
      state.value.isRecording = true;

      // Initialize session tracking
      currentSessionStartTime = transcriptionSegments.value.length > 0 ? 
        Math.max(...transcriptionSegments.value.map(seg => seg.end)) : 0;
      lastProcessedText = '';
      console.log('[Recording] 🎬 Starting new session at time offset:', currentSessionStartTime);

      // Get user's microphone
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Set up audio analysis for visualization
      audioContext = new AudioContext();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      const bufferLength = analyser.frequencyBinCount;
      dataArray = new Uint8Array(bufferLength);

      const microphone = audioContext.createMediaStreamSource(audioStream);
      microphone.connect(analyser);

      // Set up MediaRecorder for chunked audio sending
      mediaRecorder = new MediaRecorder(audioStream, { mimeType: 'audio/webm' });
      mediaRecorder.ondataavailable = (event) => {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          console.log('[Audio] 🎤 Sending audio chunk, size:', event.data.size, 'bytes');
          websocket.send(event.data);
        } else {
          console.warn('[Audio] ⚠️ WebSocket not ready, dropping audio chunk');
        }
      };

      // Start recording with chunked intervals
      console.log('[Audio] ▶️ Starting MediaRecorder with', chunkDuration, 'ms chunks');
      mediaRecorder.start(chunkDuration);

      // Start timer and audio level monitoring
      startTime = Date.now();
      timerInterval = setInterval(() => {
        if (startTime) {
          const elapsed = Math.floor((Date.now() - startTime) / 1000);
          state.value.duration = elapsed;
        }
      }, 1000);

      // Start audio level monitoring
      updateAudioLevel();

      state.value.isTranscribing = true;

    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      state.value.error = 'Failed to start recording: ' + message;
      state.value.isRecording = false;
      state.value.isTranscribing = false;
    }
  };

  /**
   * Stops the recording using reference code approach - preserves audio.
   */
  const stopRecording = () => {
    if (state.value.isRecording) {
      userClosing = true;
      state.value.waitingForStop = true;
      state.value.isRecording = false;

      // Send empty audio buffer as stop signal (reference code approach)
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        console.log('[Audio] ⏹️ Sending stop signal (empty blob)');
        const emptyBlob = new Blob([], { type: 'audio/webm' });
        websocket.send(emptyBlob);
        state.value.error = 'Recording stopped. Processing final audio...';
        console.log('[Audio] ⏳ Waiting for final processing...');
      } else {
        console.warn('[Audio] ⚠️ WebSocket not available to send stop signal');
      }

      // Stop media recorder
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        mediaRecorder = null;
      }

      // Clean up audio resources
      if (audioContext && audioContext.state !== 'closed') {
        try {
          audioContext.close();
        } catch (e) {
          console.warn('Could not close audio context:', e);
        }
        audioContext = null;
      }

      // Stop audio stream
      if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
      }

      // Clean up animation frame
      if (animationFrame) {
        cancelAnimationFrame(animationFrame);
        animationFrame = null;
      }

      // Clear timer
      if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
      }

      // Reset audio level
      state.value.audioLevel = 0;

      // Reset timer
      startTime = null;
      state.value.duration = 0;

      // Reset session tracking
      console.log('[Recording] 🎬 Session ended, resetting tracking variables');

      // Clear analysis variables
      analyser = null;
      dataArray = null;
    }
  };


  /**
   * Sends a file to the transcription API (for file uploads).
   * @param file The audio file to transcribe.
   */
  const transcribeFile = async (file: File) => {
    state.value.isProcessing = true;
    state.value.isTranscribing = true;
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
      state.value.isTranscribing = false;
    }
  };


  const clearTranscription = () => {
    transcriptionSegments.value = [];
    lastReceivedData = null;
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
    toggleRecording,
    transcribeFile,
    clearTranscription,
    updateSegment,
  };
};
