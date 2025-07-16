"""
Whisper Transcription Service
A standalone FastAPI service for audio transcription using OpenAI Whisper
"""

import tempfile
import os
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import whisper
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whisper Transcription Service",
    description="Standalone audio transcription service using OpenAI Whisper",
    version="1.0.0"
)

# Global variable to store the loaded model
whisper_model = None

def load_whisper_model():
    """Load the Whisper model on startup"""
    global whisper_model
    if whisper_model is None:
        try:
            # Check if CUDA is available and print GPU info
            if torch.cuda.is_available():
                device = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"CUDA is available. Using GPU: {gpu_name} ({gpu_memory:.1f} GB)")
            else:
                device = "cpu"
                logger.info("CUDA is not available. Using CPU.")

            # Load model - use 'base' for faster processing, 'large' for better accuracy
            model_size = os.getenv("WHISPER_MODEL_SIZE", "large-v3-turbo")
            whisper_model = whisper.load_model(model_size, device=device)

            logger.info(f"Whisper model '{model_size}' loaded successfully on {device}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {str(e)}")
            raise
    return whisper_model

@app.on_event("startup")
async def startup_event():
    """Load the Whisper model on startup"""
    load_whisper_model()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "whisper-transcription"}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio file using Whisper
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Read file content
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file provided")

        logger.info(f"Transcribing file: {file.filename} ({len(file_content)} bytes)")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            # Get the model
            model = load_whisper_model()

            # Transcribe the audio
            result = model.transcribe(temp_file_path, word_timestamps=True)

            # Extract segments
            segments = []
            if 'segments' in result:
                for seg in result['segments']:
                    segments.append({
                        'text': seg['text'].strip(),
                        'start': float(seg['start']),
                        'end': float(seg['end'])
                    })
            else:
                # Fallback: create a single segment
                segments.append({
                    'text': result['text'].strip(),
                    'start': 0.0,
                    'end': 10.0  # Default duration for chunk
                })

            logger.info(f"Transcription completed: {len(segments)} segments")

            return {
                "segments": segments,
                "language": result.get('language', 'unknown'),
                "duration": result.get('duration', 0.0)
            }

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Whisper Transcription Service", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)