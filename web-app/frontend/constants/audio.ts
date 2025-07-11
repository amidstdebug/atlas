// Audio recording configuration constants
export const AUDIO_CONFIG = {
  // Duration in seconds for each audio chunk
  CHUNK_DURATION_SECONDS: 10,
  
  // Audio recording format
  MIME_TYPE: 'audio/webm;codecs=opus',
  
  // Audio analysis settings
  FFT_SIZE: 256,
  
  // Recording intervals
  TIMER_UPDATE_INTERVAL: 1000, // 1 second
  CHUNK_RESTART_DELAY: 100, // 100ms delay between chunks
  
  // Audio processing settings
  AUDIO_LEVEL_NORMALIZE_THRESHOLD: 128,
  
  // HTTP request settings
  TRANSCRIPTION_TIMEOUT: 30000, // 30 seconds
} as const