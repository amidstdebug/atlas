import type { RecordingState, TranscriptionSegment } from './types';

export interface RecordingHandlers {
  onStateUpdate: (updates: Partial<RecordingState>) => void;
}

export interface RecordingVariables {
  chunkDuration: number;
  currentSessionStartTime: number;
  lastProcessedText: string;
  lastAudioTime: number;
  silenceBreakPoints: number[];
  breakPoints: number[];
  currentSegmentStartChar: number;
  mediaRecorder: MediaRecorder | null;
  audioStream: MediaStream | null;
  audioContext: AudioContext | null;
  analyser: AnalyserNode | null;
  dataArray: Uint8Array | null;
  animationFrame: number | null;
  startTime: number | null;
  timerInterval: NodeJS.Timeout | null;
  websocket: WebSocket | null;
  userClosing: boolean;
  cumulativeSegmentEndTime: number;
}

/**
 * Starts the recording process using chunked audio approach
 */
export const startRecording = async (
  variables: RecordingVariables,
  handlers: RecordingHandlers,
  transcriptionSegments: { value: TranscriptionSegment[] },
  updateAudioLevel: () => void
) => {
  try {
    handlers.onStateUpdate({
      error: null,
      isRecording: true,
      isTranscribing: true
    });

    // Initialize session tracking
    variables.currentSessionStartTime = transcriptionSegments.value.length > 0 ? 
      Math.max(...transcriptionSegments.value.map(seg => seg.end)) : 0;
    variables.lastProcessedText = '';
    
    // Reset silence tracking for new session
    variables.lastAudioTime = 0;
    variables.silenceBreakPoints = [];
    variables.breakPoints = [];
    variables.currentSegmentStartChar = 0;
    
    console.log('[Recording] 🎬 Starting new session at time offset:', variables.currentSessionStartTime);

    // Get user's microphone
    variables.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Set up audio analysis for visualization
    variables.audioContext = new AudioContext();
    variables.analyser = variables.audioContext.createAnalyser();
    variables.analyser.fftSize = 256;
    const bufferLength = variables.analyser.frequencyBinCount;
    variables.dataArray = new Uint8Array(bufferLength);

    const microphone = variables.audioContext.createMediaStreamSource(variables.audioStream);
    microphone.connect(variables.analyser);

    // Set up MediaRecorder for chunked audio sending
    variables.mediaRecorder = new MediaRecorder(variables.audioStream, { mimeType: 'audio/webm' });
    variables.mediaRecorder.ondataavailable = (event) => {
      if (variables.websocket && variables.websocket.readyState === WebSocket.OPEN) {
        console.log('[Audio] 🎤 Sending audio chunk, size:', event.data.size, 'bytes');
        variables.websocket.send(event.data);
      } else {
        console.warn('[Audio] ⚠️ WebSocket not ready, dropping audio chunk');
      }
    };

    // Start recording with chunked intervals
    console.log('[Audio] ▶️ Starting MediaRecorder with', variables.chunkDuration, 'ms chunks');
    variables.mediaRecorder.start(variables.chunkDuration);

    // Start timer and audio level monitoring
    variables.startTime = Date.now();
    variables.timerInterval = setInterval(() => {
      if (variables.startTime) {
        const elapsed = Math.floor((Date.now() - variables.startTime) / 1000);
        handlers.onStateUpdate({ duration: elapsed });
      }
    }, 1000);

    // Start audio level monitoring
    updateAudioLevel();

  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    handlers.onStateUpdate({
      error: 'Failed to start recording: ' + message,
      isRecording: false,
      isTranscribing: false
    });
  }
};

/**
 * Stops the recording and sends stop signal to WebSocket
 */
export const stopRecording = (
  variables: RecordingVariables,
  handlers: RecordingHandlers
) => {
  if (handlers.onStateUpdate) {
    variables.userClosing = true;
    handlers.onStateUpdate({
      waitingForStop: true,
      isRecording: false
    });

    // Send empty audio buffer as stop signal
    if (variables.websocket && variables.websocket.readyState === WebSocket.OPEN) {
      console.log('[Audio] ⏹️ Sending stop signal (empty blob)');
      const emptyBlob = new Blob([], { type: 'audio/webm' });
      variables.websocket.send(emptyBlob);
      handlers.onStateUpdate({ error: 'Recording stopped. Processing final audio...' });
      console.log('[Audio] ⏳ Waiting for final processing...');
      
      // Close WebSocket connection after sending stop signal
      setTimeout(() => {
        if (variables.websocket && variables.websocket.readyState === WebSocket.OPEN) {
          console.log('[WebSocket] 🔌 Closing WebSocket connection after processing');
          variables.websocket.close();
          variables.websocket = null;
        }
      }, 2000); // Give 2 seconds for final processing
    } else {
      console.warn('[Audio] ⚠️ WebSocket not available to send stop signal');
      // Clean up WebSocket if it exists but is not open
      if (variables.websocket) {
        variables.websocket.close();
        variables.websocket = null;
      }
    }

    // Stop media recorder
    if (variables.mediaRecorder && variables.mediaRecorder.state === 'recording') {
      variables.mediaRecorder.stop();
      variables.mediaRecorder = null;
    }

    // Clean up audio resources
    if (variables.audioContext && variables.audioContext.state !== 'closed') {
      try {
        variables.audioContext.close();
      } catch (e) {
        console.warn('Could not close audio context:', e);
      }
      variables.audioContext = null;
    }

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
    handlers.onStateUpdate({
      audioLevel: 0,
      duration: 0
    });

    // Reset session tracking
    console.log('[Recording] 🎬 Session ended, resetting tracking variables');
    variables.startTime = null;
    variables.analyser = null;
    variables.dataArray = null;
  }
}; 