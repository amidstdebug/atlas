import json
import os
import io
import numpy as np
import torch
import soundfile as sf
import librosa
from scipy.signal import resample_poly
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
from typing import Dict, Any, Optional, List
from tempfile import NamedTemporaryFile
from contextlib import asynccontextmanager

from pydub import AudioSegment

import sys
import os
os.environ['HF_HOME'] = '/usr/src/app/audio_server/models'
os.environ["NEMO_CACHE_DIR"] = "/usr/src/app/audio_server/models"


# Import the model loading function from inference.utils module
from inference.models.chunked_canary_transcriber import ChunkedCanaryTranscriber

# Global variables for model
model = None

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
	# Startup: load model
	global model
	model = ChunkedCanaryTranscriber()
	print("Model loaded successfully")
	
	# Prepare a test file for the model
	test_file_path = '/usr/src/app/mono_output.wav'
	
	try:
		print("Running test transcription...")
		transcription = model.transcribe(test_file_path)
		print("Test transcription completed successfully")
	except Exception as e:
		print(f"Error during test transcription: {str(e)}")
	
	yield  # This yields control back to FastAPI
	
	# Shutdown: cleanup resources
	print("Shutting down and releasing resources")

# Create FastAPI app with lifespan
app = FastAPI(
	title="Audio Transcription Service",
	description="Service for transcribing audio",
	version="1.0.0",
	lifespan=lifespan
)

# Enable CORS
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],  # In production, replace with specific origins
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Define request and response models
class AudioRequest(BaseModel):
	audio: str  # Base64 encoded audio
	chunk_id: Optional[int] = None
	sample_rate: int = 16000

class TranscriptionResponse(BaseModel):
	transcription: str
	chunk_id: Optional[int] = None

@app.post("/transcribe/file", response_model=TranscriptionResponse)
async def transcribe_file(file: UploadFile = File(...)):
	"""
	Transcribe audio from an uploaded file.
	"""
	try:
		if not model:
			raise HTTPException(status_code=500, detail="Model not loaded")
		
		# Read the file
		contents = await file.read()
		wav_io = io.BytesIO(contents)
		
		# Check if the file is empty
		if wav_io.getbuffer().nbytes == 0:
			raise HTTPException(status_code=400, detail="No file data received")
		
		# Process the audio and transcribe
		transcription = await process_audio(wav_io)
		
		return {"transcription": json.dumps(transcription)}
	
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error during transcription: {str(e)}")

@app.post("/transcribe/base64", response_model=TranscriptionResponse)
async def transcribe_base64(request: AudioRequest):
	"""
	Transcribe audio from base64 encoded string.
	"""
	try:
		if not model:
			raise HTTPException(status_code=500, detail="Model not loaded")
		
		# Decode base64 string
		try:
			audio_bytes = base64.b64decode(request.audio)
		except Exception as e:
			raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {str(e)}")
		
		wav_io = io.BytesIO(audio_bytes)
		
		# Check if the data is empty
		if wav_io.getbuffer().nbytes == 0:
			raise HTTPException(status_code=400, detail="No audio data received")
		
		# Process the audio and transcribe
		transcription = await process_audio(wav_io, request.sample_rate)
		
		return {"transcription": transcription, "chunk_id": request.chunk_id}
	
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error during transcription: {str(e)}")

async def process_audio(wav_io=None, original_sample_rate=None):
	"""
	Process audio data for transcription by:
	1. Reading audio data
	2. Converting to mono
	3. Removing DC offset
	4. Normalizing
	5. (Optionally) Padding
	6. Resampling to 16kHz
	7. Writing to a temporary WAV file
	8. Passing that file path to model.transcribe
	"""
	temp_file_path = None
	
	try:
		# If no wav_io provided, this is probably a test call
		if wav_io is None:
			return "Test transcription"
			
		# Determine if we're dealing with Float32Array data or audio file
		try:
			# Try to interpret the data as Float32Array from frontend
			float32_data = np.frombuffer(wav_io.getvalue(), dtype=np.float32)
			
			# If successful, we have raw Float32Array data
			audio_mono = float32_data  # Already mono
			sr = original_sample_rate or 48000  # Frontend typically uses 48kHz
			
			print(f"Processing Float32Array data with {len(audio_mono)} samples at {sr}Hz")
			
		except Exception as float32_error:
			print(f"Not Float32Array data: {str(float32_error)}")
			
			# Try to read as regular audio file
			try:
				# Read the audio data
				if original_sample_rate:
					audio_data, sr = sf.read(wav_io)
					if sr != original_sample_rate:
						print(f"Warning: File sample rate {sr} differs from specified rate {original_sample_rate}")
				else:
					audio_data, sr = sf.read(wav_io)
				
				# Convert to mono if necessary
				if audio_data.ndim > 1:
					audio_mono = librosa.to_mono(audio_data.T)
				else:
					audio_mono = audio_data
				
				print(f"Processing audio file with {len(audio_mono)} samples at {sr}Hz")
				
			except Exception as audio_error:
				raise Exception(f"Failed to interpret audio data: {str(audio_error)}")

		# Remove DC offset
		audio_mono = audio_mono - np.mean(audio_mono)
		
		# Normalize the audio to prevent clipping
		max_val = np.max(np.abs(audio_mono))
		if max_val > 0:
			audio_mono = audio_mono / max_val * 0.99
		
		# Resample to 16kHz if needed
		target_sample_rate = 16000
		if sr != target_sample_rate:
			print(f"Resampling from {sr}Hz to {target_sample_rate}Hz")
			audio_resampled = resample_poly(audio_mono, up=target_sample_rate, down=sr)
		else:
			audio_resampled = audio_mono
		
		# Write processed data to a temporary file
		with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
			print(f"Writing temporary file: {tmp.name}")
			sf.write(tmp.name, audio_resampled, target_sample_rate, subtype='PCM_16')
			temp_file_path = tmp.name
		
		# ChunkedCanaryTranscriber expects a mono file
		print(f"Transcribing file: {temp_file_path}")
		transcription = model.transcribe(temp_file_path, chunk_duration_sec = 10)
		
		# Clean up temporary file
		if temp_file_path:
			try:
				os.remove(temp_file_path)
			except OSError as e:
				print(f"Warning: Could not remove temp file: {str(e)}")
		
		return transcription
	
	except Exception as e:
		print(f"Error processing audio: {str(e)}")
		if temp_file_path and os.path.exists(temp_file_path):
			try:
				os.remove(temp_file_path)
			except:
				pass
		raise

@app.get("/health")
async def health_check():
	"""
	Health check endpoint to verify service is running.
	"""
	if not model:
		return {"status": "model not loaded"}
	return {"status": "healthy"}

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)
