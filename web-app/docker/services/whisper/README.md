# Whisper Transcription Service

A standalone FastAPI service for audio transcription using OpenAI Whisper.

## Features

- HTTP POST endpoint for audio transcription
- Supports various audio formats (WebM, MP3, WAV, etc.)
- GPU acceleration support (CUDA)
- Docker containerized
- Health check endpoint
- Configurable Whisper model size

## Endpoints

### Health Check
- **GET** `/health` - Returns service health status

### Transcription
- **POST** `/transcribe` - Transcribe audio file
  - **Form data**: `file` (audio file)
  - **Response**: JSON with transcription segments

## Configuration

Environment variables:
- `WHISPER_MODEL_SIZE`: Model size (tiny, base, small, medium, large, large-v2, large-v3)
- `CUDA_VISIBLE_DEVICES`: GPU device ID for CUDA acceleration

## Docker Usage

### Build the image:
```bash
docker build -t whisper-service .
```

### Run the container:
```bash
docker run -p 8000:8000 whisper-service
```

### With GPU support:
```bash
docker run --gpus all -p 8000:8000 whisper-service
```

## API Example

```bash
# Health check
curl http://localhost:8000/health

# Transcribe audio file
curl -X POST http://localhost:8000/transcribe \
  -F "file=@audio.webm" \
  -H "Content-Type: multipart/form-data"
```

## Response Format

```json
{
  "segments": [
    {
      "text": "Hello world",
      "start": 0.0,
      "end": 1.5
    }
  ],
  "language": "en",
  "duration": 1.5
}
```

## Development

Run locally:
```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Test the service:
```bash
python test_whisper.py
```