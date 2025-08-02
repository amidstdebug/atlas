"""
Whisper Transcription Service
A standalone FastAPI service for audio transcription using a Hugging Face
Transformers Whisper model.
"""

import tempfile
import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from transformers import pipeline, WhisperProcessor
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Whisper Transcription Service",
    description="Standalone audio transcription service using Hugging Face Whisper",
    version="1.0.0"
)

# Global variables to store the loaded pipeline and processor
asr_pipeline = None
asr_processor = None

def load_whisper_pipeline():
    """Load the Whisper pipeline on startup"""
    global asr_pipeline, asr_processor
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

            logger.info(f"Loading Whisper model: {model_name}")

            # Load the pipeline with error handling
            asr_pipeline = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                chunk_length_s=30,
                device=device,
                return_timestamps=True,  # Ensure timestamps are always returned
            )

            if asr_pipeline is None:
                raise Exception("Pipeline initialization returned None")

            # Disable forced decoder ids so custom prompts are respected
            if hasattr(asr_pipeline, 'model') and hasattr(asr_pipeline.model, 'generation_config'):
                asr_pipeline.model.generation_config.forced_decoder_ids = []

            # Load processor for prompt tokenization with error handling
            try:
                asr_processor = WhisperProcessor.from_pretrained(model_name)
                logger.info("Whisper processor loaded successfully")
            except Exception as processor_error:
                logger.warning(f"Failed to load processor (prompts will be disabled): {processor_error}")
                asr_processor = None

            logger.info(f"Whisper model '{model_name}' loaded successfully on {device}")

            # Test the pipeline with a small sample to ensure it works
            try:
                # Create a small test audio file (silence)
                import numpy as np
                sample_rate = 16000
                duration = 0.1  # 0.1 seconds
                silence = np.zeros(int(sample_rate * duration), dtype=np.float32)

                # Test transcription (this should not fail)
                test_result = asr_pipeline(silence)
                logger.info("Pipeline test successful")

            except Exception as test_error:
                logger.warning(f"Pipeline test failed, but continuing: {test_error}")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {str(e)}")
            # Reset global variables on failure
            asr_pipeline = None
            asr_processor = None
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
async def transcribe_audio(file: UploadFile = File(...), prompt: Optional[str] = Form(None)):
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

        # Determine file extension from filename or content type
        file_extension = ".wav"
        filename_lower = file.filename.lower()
        if filename_lower.endswith((".mp3", ".wav", ".flac", ".m4a", ".ogg", ".webm", ".mp4")):
            file_extension = "." + filename_lower.split(".")[-1]
        elif file.content_type:
            content_type_map = {
                "audio/wav": ".wav",
                "audio/wave": ".wav",
                "audio/x-wav": ".wav",
                "audio/mpeg": ".mp3",
                "audio/mp3": ".mp3",
                "audio/flac": ".flac",
                "audio/x-flac": ".flac",
                "audio/ogg": ".ogg",
                "audio/webm": ".webm",
                "video/mp4": ".mp4",
                "audio/mp4": ".m4a",
                "audio/x-m4a": ".m4a",
            }
            file_extension = content_type_map.get(file.content_type, ".wav")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            # Load pipeline
            asr = load_whisper_pipeline()
            if asr is None:
                raise HTTPException(status_code=500, detail="Failed to load ASR pipeline")

            # Prepare kwargs
            kwargs: Dict[str, Any] = {"return_timestamps": True}
            if prompt and asr_processor:
                try:
                    prompt_ids = asr_processor.tokenizer.get_prompt_ids(
                        prompt, return_tensors="pt"
                    ).to(asr.model.device)
                    kwargs["generate_kwargs"] = {
                        "prompt_ids": prompt_ids,
                        "prompt_condition_type": "first-segment",
                    }
                except Exception as prompt_error:
                    logger.warning(f"Failed to process prompt, continuing without it: {prompt_error}")

            # Transcribe, retrying without timestamps on IndexError
            try:
                result = asr(temp_file_path, **kwargs)
            except IndexError as ie:
                logger.warning(f"IndexError in ASR pipeline: {ie}. Retrying without timestamps.")
                fallback_kwargs = {k: v for k, v in kwargs.items() if k != "return_timestamps"}
                result = asr(temp_file_path, **fallback_kwargs, return_timestamps=False)

            # Validate result
            if result is None:
                raise HTTPException(status_code=500, detail="ASR pipeline returned None result")

            # Extract segments
            segments = []
            chunks = result.get("chunks", []) if isinstance(result, dict) else []
            if chunks:
                for chunk in chunks:
                    if not chunk:
                        continue
                    timestamp = chunk.get("timestamp") if isinstance(chunk, dict) else None
                    if timestamp and len(timestamp) >= 2:
                        start, end = float(timestamp[0]), float(timestamp[1])
                    else:
                        start, end = 0.0, 0.0
                    text = chunk.get("text", "").strip() if isinstance(chunk, dict) else ""
                    segments.append({"text": text, "start": start, "end": end})
            if not segments:
                text = result.get("text", "").strip() if isinstance(result, dict) and result.get("text") else ""
                segments.append({"text": text, "start": 0.0, "end": 0.0})

            logger.info(f"Transcription completed: {len(segments)} segments")
            duration = segments[-1]["end"] if segments else 0.0
            return {
                "segments": segments,
                "language": result.get("language", "unknown") if isinstance(result, dict) else "unknown",
                "duration": duration,
            }

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Whisper Transcription Service", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
