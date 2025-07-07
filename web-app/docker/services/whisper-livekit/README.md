# WhisperLiveKit Service

This service uses WhisperLiveKit for real-time speech-to-text transcription, optimized for ATC (Air Traffic Control) communications.

## Model Storage

Models are stored in the mounted `/app/models` directory, which maps to the `whisper_models` Docker volume. This ensures:

- **Persistent Storage**: Models are downloaded once and reused across container restarts
- **Performance**: Faster startup times after initial model download
- **Shared Storage**: Multiple containers can share the same model cache

### Directory Structure

```
/app/models/
├── transformers/     # Transformers model cache
├── huggingface/     # Hugging Face Hub cache  
└── torch/           # PyTorch model cache
```

## Configuration

### Default Settings (Production)
- Model: `base.en` (English-optimized, faster)
- Language: `en`
- VAC: Enabled (Voice Activity Controller)
- Confidence Validation: Enabled
- Min Chunk Size: 1.0 seconds

### Development Settings
- Model: `base.en` 
- Language: `en`
- VAC: Enabled
- Debug: Enabled

## Endpoints

- **WebSocket**: `/asr` - Real-time transcription
- **Health Check**: `/` - Service status

## Environment Variables

- `TRANSFORMERS_CACHE=/app/models/transformers`
- `HF_HOME=/app/models/huggingface` 
- `TORCH_HOME=/app/models/torch`
- `PYTHONUNBUFFERED=1`
- `CUDA_VISIBLE_DEVICES=0`