"""
Whisper Transcription Service
A standalone FastAPI service for audio transcription using a Hugging Face
Transformers Whisper model.
"""

import tempfile
import os
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from transformers import pipeline
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whisper Transcription Service",
    description="Standalone audio transcription service using Hugging Face Whisper",
    version="1.0.0"
)

# Global variable to store the loaded pipeline
asr_pipeline = None

def load_whisper_pipeline():
    """Load the Whisper pipeline on startup"""
    global asr_pipeline
    if asr_pipeline is None:
        try:
            # Check if CUDA is available and print GPU info
            if torch.cuda.is_available():
                device = 0
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"CUDA is available. Using GPU: {gpu_name} ({gpu_memory:.1f} GB)")
            else:
                device = "cpu"
                logger.info("CUDA is not available. Using CPU.")

            model_name = os.getenv(
                "WHISPER_MODEL_ID", "jlvdoorn/whisper-large-v3-atco2-asr"
            )
            asr_pipeline = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                chunk_length_s=30,
                device=device,
            )

            logger.info(f"Whisper model '{model_name}' loaded successfully on {device}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {str(e)}")
            raise
    return asr_pipeline

@app.on_event("startup")
async def startup_event():
    """Load the Whisper model on startup"""
    load_whisper_pipeline()

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
            # Get the pipeline
            asr = load_whisper_pipeline()

            # Transcribe the audio
            result = asr(temp_file_path, return_timestamps=True)

            # Extract segments
            segments = []
            for chunk in result.get("chunks", []):
                start, end = chunk.get("timestamp", (0.0, 0.0))
                segments.append(
                    {
                        "text": chunk.get("text", "").strip(),
                        "start": float(start),
                        "end": float(end),
                    }
                )
            if not segments:
                segments.append({"text": result.get("text", "").strip(), "start": 0.0, "end": 0.0})

            logger.info(f"Transcription completed: {len(segments)} segments")

            duration = segments[-1]["end"] if segments else 0.0
            return {
                "segments": segments,
                "language": result.get("language", "unknown"),
                "duration": duration,
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
