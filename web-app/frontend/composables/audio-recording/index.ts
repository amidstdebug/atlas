import { ref, computed } from 'vue';
import type { RecordingState, TranscriptionSegment, TranscriptionResponse } from './types';
import { parseTimestamp } from './utils';
import { buildSegmentsFromLines } from './segmentation';
import { setupWebSocket, type WebSocketHandlers } from './websocket';
import { startRecording as startRecordingInternal, stopRecording as stopRecordingInternal, type RecordingHandlers, type RecordingVariables } from './recording';

export * from './types';

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

  // Recording variables
  const variables: RecordingVariables = {
    chunkDuration: 2000, // 2 second chunks
    currentSessionStartTime: 0,
    lastProcessedText: '',
    lastAudioTime: 0,
    silenceBreakPoints: [], // Legacy, can be removed later
    breakPoints: [], // The character indices where splits occur
    currentSegmentStartChar: 0,
    mediaRecorder: null,
    audioStream: null,
    audioContext: null,
    analyser: null,
    dataArray: null,
    animationFrame: null,
    startTime: null,
    timerInterval: null,
    websocket: null,
    userClosing: false,
    cumulativeSegmentEndTime: 0,
  };

  const animationFrameRef = { current: null as number | null };

  // Create update audio level function
  const updateAudioLevel = () => {
    if (variables.analyser && variables.dataArray && state.value.isRecording) {
      variables.analyser.getByteFrequencyData(variables.dataArray);

      // Calculate the average volume
      const sum = variables.dataArray.reduce((acc, val) => acc + val, 0);
      const average = sum / variables.dataArray.length;

      // Normalize the average to a 0-1 range for the UI
      state.value.audioLevel = Math.min(average / 128, 1);

      // Request the next frame to continue the animation loop
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
    }
  };

  // Recording handlers
  const recordingHandlers: RecordingHandlers = {
    onStateUpdate: (updates) => {
      Object.assign(state.value, updates);
    }
  };

  // Process transcription data from WebSocket
  const processTranscriptionData = (data: any, isFinalizing: boolean) => {
    console.log('[Transcription] 🔄 Processing data. IsFinalizing:', isFinalizing, 'Data:', data);

    // Handle lines format - this is the cumulative text case (like reference code)
    if (data.lines && Array.isArray(data.lines) && data.lines.length > 0) {
      console.log('[Transcription] 📄 Processing lines format:', data.lines.length, 'lines');

      const fullLine = data.lines[0];
      const fullText = (fullLine.text || '').trim();
      
      const lastBreakPoint = variables.breakPoints.length > 0 ? variables.breakPoints[variables.breakPoints.length - 1] : 0;
      const liveText = fullText.substring(lastBreakPoint);
      
      const sessionDuration = (parseTimestamp(fullLine.end) - parseTimestamp(fullLine.beg));
      // Handle potential division by zero if fullText is empty.
      const durationOfLiveText = fullText.length > 0 
        ? (liveText.length / fullText.length) * sessionDuration
        : 0;

      // If live text is over 10s, add a new breakpoint, preferably at a sentence end.
      if (durationOfLiveText > 10 && !isFinalizing) {
        const lastDotIndex = fullText.lastIndexOf('.');
        
        // Ensure the dot is within the current "live" segment to be a valid split point.
        if (lastDotIndex > lastBreakPoint) {
            const newBreakPoint = lastDotIndex + 1; // Break after the full stop.
            if (!variables.breakPoints.includes(newBreakPoint)) {
                console.log(`[Segmentation] Smart break at sentence end: index ${newBreakPoint}`);
                variables.breakPoints.push(newBreakPoint);
            }
        } else {
            // Fallback: No sentence end found. Break at the end of the current text.
            const newBreakPoint = fullText.length;
            if (newBreakPoint > lastBreakPoint && !variables.breakPoints.includes(newBreakPoint)) {
                console.log(`[Segmentation] Timed break (10s) without sentence end: index ${newBreakPoint}`);
                variables.breakPoints.push(newBreakPoint);
            }
        }
      }

      const bufferText = (data.buffer_transcription || '').trim();
      const { segments: newSegments, newCumulativeEndTime } = buildSegmentsFromLines(
        data.lines,
        variables.currentSessionStartTime,
        bufferText,
        isFinalizing,
        variables.breakPoints
      );

      // After building segments, update the cumulative end time
      variables.cumulativeSegmentEndTime = newCumulativeEndTime;

      // Replace the segments for the current session
      const sessionStartIndex = transcriptionSegments.value.findIndex(seg => seg.start >= variables.currentSessionStartTime);
      if (sessionStartIndex >= 0) {
        transcriptionSegments.value.splice(sessionStartIndex);
      }
      transcriptionSegments.value.push(...newSegments);

      state.value.isTranscribing = false;
      console.log('[Transcription] ✅ Lines processing completed, total segments:', transcriptionSegments.value.length);
    }
    // Handle segments format (keep existing logic for compatibility)
    else if (data.segments && Array.isArray(data.segments)) {
      console.log('[Transcription] 📝 Processing segments format:', data.segments.length, 'segments');

      const newSegments = data.segments.map((seg: any) => ({
        text: seg.text || '',
        start: parseTimestamp(seg.start),
        end: parseTimestamp(seg.end)
      }));

      if (isFinalizing) {
        transcriptionSegments.value.push(...newSegments);
      } else {
        const sessionStartIndex = transcriptionSegments.value.findIndex(seg => seg.start >= variables.currentSessionStartTime);
        if (sessionStartIndex >= 0) {
          transcriptionSegments.value.splice(sessionStartIndex);
        }
        transcriptionSegments.value.push(...newSegments);
      }

      state.value.isTranscribing = false;
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

  // WebSocket handlers
  const websocketHandlers: WebSocketHandlers = {
    onProcessTranscriptionData: processTranscriptionData,
    onStateUpdate: (updates) => {
      Object.assign(state.value, updates);
    },
    onStopRecording: () => stopRecording()
  };

  // Toggle recording function
  const toggleRecording = async () => {
    if (!state.value.isRecording) {
      if (state.value.waitingForStop) {
        console.log('Waiting for stop, early return');
        return;
      }

      console.log('Connecting to WebSocket');
      try {
        // Reset error state
        state.value.error = null;
        state.value.isTranscribing = true;
        
        // Always create a new WebSocket connection for each recording session
        variables.websocket = await setupWebSocket(websocketHandlers, {
          userClosing: variables.userClosing,
          lastReceivedData: null,
          websocket: variables.websocket
        });
        await startRecordingInternal(variables, recordingHandlers, transcriptionSegments, updateAudioLevel);
      } catch (err) {
        console.error('[Recording] Failed to start recording:', err);
        const errorMessage = err instanceof Error ? err.message : 'Could not connect to transcription service or access microphone.';
        state.value.error = errorMessage;
        state.value.isRecording = false;
        state.value.isTranscribing = false;
        state.value.waitingForStop = false;
      }
    } else {
      console.log('Stopping recording');
      stopRecording();
    }
  };

  // Start recording
  const startRecording = async () => {
    await startRecordingInternal(variables, recordingHandlers, transcriptionSegments, updateAudioLevel);
  };

  // Stop recording
  const stopRecording = () => {
    stopRecordingInternal(variables, recordingHandlers);
  };

  // Transcribe file (for file uploads)
  const transcribeFile = async (file: File) => {
    state.value.isProcessing = true;
    state.value.isTranscribing = true;
    state.value.error = null;
    clearTranscription();

    try {
      // Note: This would need to be implemented with your transcription service
      // const { $transcribeAudio } = useNuxtApp();
      // const response: TranscriptionResponse = await $transcribeAudio(file);

      // if (response?.segments && response.segments.length > 0) {
      //   transcriptionSegments.value.push(...response.segments);
      // }

      console.warn('File transcription not implemented - add your transcription service here');
      throw new Error('File transcription not implemented');
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
    variables.lastProcessedText = '';
    variables.lastAudioTime = 0;
    variables.silenceBreakPoints = [];
    variables.breakPoints = [];
    variables.currentSegmentStartChar = 0;
    variables.currentSessionStartTime = 0;
    variables.cumulativeSegmentEndTime = 0;
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
  };
};