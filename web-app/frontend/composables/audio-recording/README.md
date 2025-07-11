# Audio Recording Composable

This directory contains the modular audio recording composable, broken down into logical components for better maintainability.

## File Structure

```
audio-recording/
├── index.ts           # Main composable that ties everything together
├── types.ts           # TypeScript interfaces and types
├── utils.ts           # Utility functions (timestamp parsing)
├── segmentation.ts    # Audio segmentation logic
├── websocket.ts       # WebSocket connection management
├── recording.ts       # Audio recording start/stop logic
└── README.md         # This file
```

## Key Features

### Silence & Time-Based Segmentation
The composable automatically segments transcription based on **either** of the following conditions:
1. A silence marker – lines with `speaker === -2`
2. The running segment exceeds **10 seconds** in duration

Whichever happens first closes the current segment and starts a new one, giving concise, meaningful timestamps while avoiding segments that are too long.

### Modular Architecture
- **types.ts**: All TypeScript interfaces centralized
- **utils.ts**: Pure utility functions (timestamp parsing)
- **segmentation.ts**: Contains `buildSegmentsFromLines()` and legacy segmentation functions
- **websocket.ts**: WebSocket connection setup and message handling
- **recording.ts**: Audio capture, MediaRecorder setup, and cleanup
- **index.ts**: Main composable that coordinates all modules

### Audio Processing
- 2-second audio chunks sent to WebSocket
- Real-time audio level visualization
- Session-based timestamps (multiple recordings continue from previous end time)

## Usage

```typescript
import { useAudioRecording } from '@/composables/useAudioRecording'

const {
  state,                    // Recording state (isRecording, audioLevel, etc.)
  transcriptionSegments,    // Array of timestamped segments
  toggleRecording,          // Start/stop recording
  transcribeFile,          // Upload file for transcription
  clearTranscription,      // Clear all segments
  updateSegment            // Edit a specific segment
} = useAudioRecording()
```

## Data Flow

1. **Recording Start**: `toggleRecording()` → WebSocket connection → audio capture setup
2. **Audio Chunks**: MediaRecorder sends 2s chunks to WebSocket
3. **Transcription**: Server responds with `lines` containing speaker info and text
4. **Segmentation**: `buildSegmentsFromLines()` processes silence markers and creates segments
5. **UI Update**: Reactive `transcriptionSegments` updates the TranscriptionPanel

## Backward Compatibility

The main `useAudioRecording.ts` file now simply re-exports from this modular structure, so existing imports continue to work without changes.

## Legacy Functions

Some functions are kept for compatibility but not currently used:
- `breakTextIntoSegments()` - Natural language segmentation
- `detectSilenceBreaks()` - Time-based silence detection
- `createSegmentsFromBreaks()` - Character-position-based segmentation

These can be removed in future versions once the silence-marker approach is fully validated.