"""
Whisper Transcription Service
A standalone FastAPI service for audio transcription using a Hugging Face
Transformers Whisper model.
"""

import tempfile
import os
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse

import torch
import numpy as np

# Optional import of torchaudio for audio loading and resampling
try:
	import torchaudio
	_HAVE_TORCHAUDIO = True
except Exception:
	_HAVE_TORCHAUDIO = False

from transformers import AutoProcessor, WhisperForConditionalGeneration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables to store the loaded model and processor
asr_model = None
asr_processor = None

def load_whisper_pipeline():
	"""
	Load Whisper model and processor once.
	Uses openai/whisper-large-v3-turbo by default, controllable via WHISPER_MODEL_ID.
	"""
	global asr_model, asr_processor
	if asr_model is not None and asr_processor is not None:
		return asr_model

	try:
		if torch.cuda.is_available():
			device = "cuda"
			torch_dtype = torch.float16
			logger.info(f"CUDA is available. Using GPU: {torch.cuda.get_device_name(0)}")
		else:
			device = "cpu"
			torch_dtype = torch.float32
			logger.info("CUDA is not available. Using CPU.")

		model_name = os.getenv("WHISPER_MODEL_ID", "openai/whisper-large-v3-turbo")
		logger.info(f"Loading Whisper model: {model_name}")

		# Load processor and model
		asr_processor = AutoProcessor.from_pretrained(model_name)
		asr_model = WhisperForConditionalGeneration.from_pretrained(
			model_name,
			torch_dtype=torch_dtype,
			device_map="auto" if device == "cuda" else None,
			attn_implementation="sdpa",
		)
		if device == "cuda":
			asr_model.to(device)

		# Quick sanity check using 0.1 s of silence
		silence = np.zeros(int(16000 * 0.1), dtype=np.float32)
		feats = asr_processor(silence, sampling_rate=16000, return_tensors="pt").input_features
		feats = feats.to(device, dtype=torch_dtype)
		_ = asr_model.generate(feats, max_new_tokens=1)

		logger.info("Whisper model and processor loaded successfully")
		return asr_model

	except Exception as e:
		logger.error(f"Failed to load Whisper model: {e}")
		asr_model = None
		asr_processor = None
		raise

@asynccontextmanager
async def lifespan(app: FastAPI):
	# startup
	load_whisper_pipeline()
	yield
	# shutdown
	try:
		global asr_model, asr_processor
		asr_model = None
		asr_processor = None
		if torch.cuda.is_available():
			torch.cuda.empty_cache()
	except Exception as e:
		logger.warning(f"Shutdown cleanup warning: {e}")

app = FastAPI(
	title="Whisper Transcription Service",
	description="Standalone audio transcription service using Hugging Face Whisper",
	version="1.0.0",
	lifespan=lifespan,
)

@app.get("/health")
async def health_check():
	"""Health check endpoint"""
	return {"status": "healthy", "service": "whisper-transcription"}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...), prompt: Optional[str] = Form(None)):
	"""
	Transcribe audio file using Whisper large v3 turbo
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
			# Ensure model is loaded
			model = load_whisper_pipeline()
			if model is None or asr_processor is None:
				raise HTTPException(status_code=500, detail="Failed to load ASR model")

			# Load audio to numpy array at 16 kHz
			if not _HAVE_TORCHAUDIO:
				raise HTTPException(
					status_code=415,
					detail="torchaudio is required for audio decoding. Please install torchaudio.",
				)

			waveform, sr = torchaudio.load(temp_file_path)
			if sr != 16000:
				waveform = torchaudio.functional.resample(waveform, sr, 16000)
				sr = 16000
			audio_array = waveform.squeeze().numpy()

			# Tokenize features
			inputs = asr_processor(
				audio_array,
				sampling_rate=sr,
				return_tensors="pt"
			).input_features

			device = "cuda" if torch.cuda.is_available() else "cpu"
			dtype = torch.float16 if device == "cuda" else torch.float32
			inputs = inputs.to(device, dtype=dtype)

			# Generation
			predicted_ids = model.generate(inputs, cache_implementation="static")
			transcription = asr_processor.batch_decode(
				predicted_ids, skip_special_tokens=True
			)[0].strip()

			# Build response
			segments = [{"text": transcription, "start": 0.0, "end": 0.0}]
			logger.info("Transcription completed")
			return {"segments": segments, "language": "unknown", "duration": 0.0}

		finally:
			# Clean up temporary file
			if os.path.exists(temp_file_path):
				os.unlink(temp_file_path)

	except HTTPException:
		# Re-raise HTTP exceptions as-is
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
