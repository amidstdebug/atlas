export interface TranscriptionSegment {
  text: string;
  start: number;
  end: number;
  isLive?: boolean;
  // Processing states
  isProcessing?: boolean;
  isCleaningText?: boolean;
  isExtractingNER?: boolean;
  // Enhanced content
  cleanedText?: string;
  nerText?: string;
  entities?: NEREntity[];
  processingError?: string;
}

export interface NEREntity {
  text: string;
  category: 'IMPORTANT_INFO' | 'WEATHER' | 'TIMES';
  start_pos: number;
  end_pos: number;
}

export interface TranscriptionResponse {
  segments: TranscriptionSegment[];
  chunk_id?: string | null;
  processing_applied?: {
    numbers_replaced: boolean;
    icao_callsigns_applied: boolean;
  };
}

export interface CleanTextResponse {
  cleaned_text: string;
}

export interface ProcessBlockResponse {
  cleaned_text: string;
  ner_text: string;
  entities: NEREntity[];
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

export interface AudioRecordingVariables {
  chunkDuration: number;
  userClosing: boolean;
  lastReceivedData: any;
  startTime: number | null;
  timerInterval: NodeJS.Timeout | null;
  lastProcessedText: string;
  currentSessionStartTime: number;
  lastAudioTime: number;
  silenceBreakPoints: number[];
  currentSegmentStartChar: number;
  mediaRecorder: MediaRecorder | null;
  audioStream: MediaStream | null;
  audioContext: AudioContext | null;
  analyser: AnalyserNode | null;
  dataArray: Uint8Array | null;
  animationFrame: number | null;
  destinationNode: MediaStreamAudioDestinationNode | null;
  websocket: WebSocket | null;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
} 