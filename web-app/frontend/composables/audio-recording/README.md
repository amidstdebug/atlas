# Audio Recording Composable

This directory contains the simplified audio recording composable for HTTP-based transcription with 10-second chunks.

## File Structure

```
audio-recording/
├── index.ts           # Main composable with HTTP-based transcription
├── types.ts           # TypeScript interfaces and types
└── README.md         # This file
```

## Key Features

### 10-Second Chunk Processing
The composable now uses a simplified approach:
1. Records audio in **10-second chunks**
2. Each chunk is sent via **HTTP POST** to the transcription service
3. Each chunk becomes **one transcription segment** (no complex segmentation)
4. Simple sequential timing: chunk 0 = 0-10s, chunk 1 = 10-20s, etc.

### Simplified Architecture
- **types.ts**: All TypeScript interfaces centralized
- **index.ts**: Main composable with HTTP-based transcription, audio capture, and chunk management

### Audio Processing
- 10-second audio chunks sent via HTTP POST
- Real-time audio level visualization
- Sequential chunk-based timestamps
- No complex segmentation or WebSocket handling

## Usage

```typescript
import { useAudioRecording } from '@/composables/useAudioRecording'

const {
  state,                    // Recording state (isRecording, audioLevel, etc.)
  transcriptionSegments,    // Array of 10-second timestamped segments
  toggleRecording,          // Start/stop recording
  transcribeFile,          // Upload file for transcription
  clearTranscription,      // Clear all segments
  updateSegment            // Edit a specific segment
} = useAudioRecording()
```

## Data Flow

1. **Recording Start**: `toggleRecording()` → microphone access → MediaRecorder setup
2. **Audio Chunks**: MediaRecorder creates 10-second audio blobs
3. **HTTP Transcription**: Each chunk sent to `/api/transcribe` endpoint
4. **Simple Segmentation**: Each chunk becomes one segment with 10-second duration
5. **UI Update**: Reactive `transcriptionSegments` updates the UI

## Benefits

- **Simpler**: No WebSocket complexity or smart segmentation logic
- **More Reliable**: HTTP requests are easier to debug and handle errors
- **Predictable**: Each 10-second chunk = one segment with fixed timing
- **Scalable**: Can easily adjust chunk duration if needed
- **Container-Based**: Whisper service runs in separate Docker container