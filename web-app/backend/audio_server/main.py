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
from inference.models.chunked_whisper_transcriber import ChunkedWhisperTranscriber

# Global variables for model
model = None

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
	# Startup: load model
	global model
	# Use HuggingFace Whisper model instead of Canary
	model = ChunkedWhisperTranscriber(model_name='jlvdoorn/whisper-medium.en-atco2-asr')
	print("Whisper model loaded successfully")
	
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
		transcription = model.transcribe(temp_file_path, chunk_duration_sec = 30)


		transcription_str = json.dumps(transcription)  # returns a JSON string

		""""
		transcription_str
		{\"text\": \"Ah, now, Rich, would you like some pussy? Well, it wasn't on my mind right now. It is now. Pussy energy drink. I see. What flavour is it? Flavour. Leave it. Leave it. Yeah, moving on. I'd like to introduce something for which, at first, I thought I'm going to struggle to find a motoring application, because what it is is this. This machine is controlled by your iPhone, right? With an app, and it flies up in the air, and there's a camera on it.\", \"words\": [{\"start\": 0.4, \"duration\": 0.4, \"end\": 0.8, \"text\": \"Ah,\"}, {\"start\": 0.88, \"duration\": 0.32, \"end\": 1.2, \"text\": \"now,\"}, {\"start\": 1.28, \"duration\": 0.56, \"end\": 1.84, \"text\": \"Rich,\"}, {\"start\": 1.92, \"duration\": 0.08, \"end\": 2.0, \"text\": \"would\"}, {\"start\": 2.32, \"duration\": 0.08, \"end\": 2.4, \"text\": \"you\"}, {\"start\": 2.56, \"duration\": 0.08, \"end\": 2.64, \"text\": \"like\"}, {\"start\": 2.8, \"duration\": 0.08, \"end\": 2.88, \"text\": \"some\"}, {\"start\": 3.04, \"duration\": 2.24, \"end\": 5.28, \"text\": \"pussy?\"}, {\"start\": 5.92, \"duration\": 0.32, \"end\": 6.24, \"text\": \"Well,\"}, {\"start\": 6.24, \"duration\": 0.08, \"end\": 6.32, \"text\": \"it\"}, {\"start\": 6.4, \"duration\": 0.32, \"end\": 6.72, \"text\": \"wasn't\"}, {\"start\": 6.72, \"duration\": 0.16, \"end\": 6.88, \"text\": \"on\"}, {\"start\": 6.88, \"duration\": 0.08, \"end\": 6.96, \"text\": \"my\"}, {\"start\": 7.04, \"duration\": 0.08, \"end\": 7.12, \"text\": \"mind\"}, {\"start\": 7.44, \"duration\": 0.08, \"end\": 7.52, \"text\": \"right\"}, {\"start\": 7.68, \"duration\": 0.24, \"end\": 7.92, \"text\": \"now.\"}, {\"start\": 8.0, \"duration\": 0.08, \"end\": 8.08, \"text\": \"It\"}, {\"start\": 8.24, \"duration\": 0.08, \"end\": 8.32, \"text\": \"is\"}, {\"start\": 8.48, \"duration\": 0.32, \"end\": 8.8, \"text\": \"now.\"}, {\"start\": 9.84, \"duration\": 0.56, \"end\": 10.4, \"text\": \"Pussy\"}, {\"start\": 10.56, \"duration\": 0.4, \"end\": 10.96, \"text\": \"energy\"}, {\"start\": 11.04, \"duration\": 1.52, \"end\": 12.56, \"text\": \"drink.\"}, {\"start\": 12.96, \"duration\": 0.08, \"end\": 13.04, \"text\": \"I\"}, {\"start\": 13.36, \"duration\": 0.48, \"end\": 13.84, \"text\": \"see.\"}, {\"start\": 14.32, \"duration\": 0.08, \"end\": 14.4, \"text\": \"What\"}, {\"start\": 14.56, \"duration\": 0.4, \"end\": 14.96, \"text\": \"flavour\"}, {\"start\": 15.04, \"duration\": 0.08, \"end\": 15.12, \"text\": \"is\"}, {\"start\": 15.2, \"duration\": 0.32, \"end\": 15.52, \"text\": \"it?\"}, {\"start\": 15.68, \"duration\": 2.4, \"end\": 18.08, \"text\": \"Flavour.\"}, {\"start\": 18.48, \"duration\": 0.32, \"end\": 18.8, \"text\": \"Leave\"}, {\"start\": 18.88, \"duration\": 0.4, \"end\": 19.28, \"text\": \"it.\"}, {\"start\": 19.6, \"duration\": 1.76, \"end\": 21.36, \"text\": \"Leave\"}, {\"start\": 21.36, \"duration\": 0.32, \"end\": 21.68, \"text\": \"it.\"}, {\"start\": 21.68, \"duration\": 0.32, \"end\": 22.0, \"text\": \"Yeah,\"}, {\"start\": 22.08, \"duration\": 0.32, \"end\": 22.4, \"text\": \"moving\"}, {\"start\": 22.4, \"duration\": 0.32, \"end\": 22.72, \"text\": \"on.\"}, {\"start\": 22.88, \"duration\": 0.32, \"end\": 23.2, \"text\": \"I'd\"}, {\"start\": 23.2, \"duration\": 0.08, \"end\": 23.28, \"text\": \"like\"}, {\"start\": 23.28, \"duration\": 0.08, \"end\": 23.36, \"text\": \"to\"}, {\"start\": 23.36, \"duration\": 0.48, \"end\": 23.84, \"text\": \"introduce\"}, {\"start\": 23.84, \"duration\": 0.08, \"end\": 23.92, \"text\": \"something\"}, {\"start\": 24.08, \"duration\": 0.08, \"end\": 24.16, \"text\": \"for\"}, {\"start\": 24.24, \"duration\": 0.16, \"end\": 24.4, \"text\": \"which,\"}, {\"start\": 24.4, \"duration\": 0.16, \"end\": 24.56, \"text\": \"at\"}, {\"start\": 24.56, \"duration\": 0.24, \"end\": 24.8, \"text\": \"first,\"}, {\"start\": 24.8, \"duration\": 0.08, \"end\": 24.88, \"text\": \"I\"}, {\"start\": 24.88, \"duration\": 0.08, \"end\": 24.96, \"text\": \"thought\"}, {\"start\": 24.96, \"duration\": 0.32, \"end\": 25.28, \"text\": \"I'm\"}, {\"start\": 25.28, \"duration\": 0.08, \"end\": 25.36, \"text\": \"going\"}, {\"start\": 25.36, \"duration\": 0.08, \"end\": 25.44, \"text\": \"to\"}, {\"start\": 25.44, \"duration\": 0.4, \"end\": 25.84, \"text\": \"struggle\"}, {\"start\": 25.84, \"duration\": 0.08, \"end\": 25.92, \"text\": \"to\"}, {\"start\": 25.92, \"duration\": 0.08, \"end\": 26.0, \"text\": \"find\"}, {\"start\": 26.0, \"duration\": 0.08, \"end\": 26.08, \"text\": \"a\"}, {\"start\": 26.08, \"duration\": 0.32, \"end\": 26.4, \"text\": \"motoring\"}, {\"start\": 26.48, \"duration\": 0.56, \"end\": 27.04, \"text\": \"application,\"}, {\"start\": 27.04, \"duration\": 0.08, \"end\": 27.12, \"text\": \"because\"}, {\"start\": 27.76, \"duration\": 0.08, \"end\": 27.84, \"text\": \"what\"}, {\"start\": 27.92, \"duration\": 0.08, \"end\": 28.0, \"text\": \"it\"}, {\"start\": 28.16, \"duration\": 0.08, \"end\": 28.24, \"text\": \"is\"}, {\"start\": 28.64, \"duration\": 0.08, \"end\": 28.72, \"text\": \"is\"}, {\"start\": 29.76, \"duration\": 0.24, \"end\": 30.0, \"text\": \"this.\"}, {\"start\": 30.0, \"duration\": 0.08, \"end\": 30.08, \"text\": \"This\"}, {\"start\": 30.32, \"duration\": 0.24, \"end\": 30.56, \"text\": \"machine\"}, {\"start\": 30.56, \"duration\": 0.16, \"end\": 30.72, \"text\": \"is\"}, {\"start\": 30.72, \"duration\": 0.32, \"end\": 31.04, \"text\": \"controlled\"}, {\"start\": 31.04, \"duration\": 0.08, \"end\": 31.12, \"text\": \"by\"}, {\"start\": 31.12, \"duration\": 0.08, \"end\": 31.2, \"text\": \"your\"}, {\"start\": 31.2, \"duration\": 0.56, \"end\": 31.76, \"text\": \"iPhone,\"}, {\"start\": 31.76, \"duration\": 0.16, \"end\": 31.92, \"text\": \"right?\"}, {\"start\": 31.92, \"duration\": 0.08, \"end\": 32.0, \"text\": \"With\"}, {\"start\": 32.0, \"duration\": 0.08, \"end\": 32.08, \"text\": \"an\"}, {\"start\": 32.16, \"duration\": 0.4, \"end\": 32.56, \"text\": \"app,\"}, {\"start\": 32.56, \"duration\": 0.08, \"end\": 32.64, \"text\": \"and\"}, {\"start\": 32.8, \"duration\": 0.08, \"end\": 32.88, \"text\": \"it\"}, {\"start\": 32.96, \"duration\": 0.32, \"end\": 33.28, \"text\": \"flies\"}, {\"start\": 33.44, \"duration\": 0.08, \"end\": 33.52, \"text\": \"up\"}, {\"start\": 33.6, \"duration\": 0.08, \"end\": 33.68, \"text\": \"in\"}, {\"start\": 33.68, \"duration\": 0.08, \"end\": 33.76, \"text\": \"the\"}, {\"start\": 33.76, \"duration\": 0.24, \"end\": 34.0, \"text\": \"air,\"}, {\"start\": 34.0, \"duration\": 0.08, \"end\": 34.08, \"text\": \"and\"}, {\"start\": 34.08, \"duration\": 0.32, \"end\": 34.4, \"text\": \"there's\"}, {\"start\": 34.4, \"duration\": 0.08, \"end\": 34.480000000000004, \"text\": \"a\"}, {\"start\": 34.480000000000004, \"duration\": 0.32, \"end\": 34.8, \"text\": \"camera\"}, {\"start\": 34.8, \"duration\": 0.08, \"end\": 34.88, \"text\": \"on\"}, {\"start\": 34.88, \"duration\": 0.32, \"end\": 35.2, \"text\": \"it.\"}], \"tokens\": [{\"start\": 0.0, \"duration\": 0.4, \"end\": 0.4, \"text\": \"<b>\"}, {\"start\": 0.4, \"duration\": 0.08, \"end\": 0.48, \"text\": \"\▁A\"}, {\"start\": 0.48, \"duration\": 0.08, \"end\": 0.56, \"text\": \"<b>\"}, {\"start\": 0.56, \"duration\": 0.08, \"end\": 0.64, \"text\": \"h\"}, {\"start\": 0.64, \"duration\": 0.08, \"end\": 0.72, \"text\": \"<b>\"}, {\"start\": 0.72, \"duration\": 0.08, \"end\": 0.8, \"text\": \",\"}, {\"start\": 0.8, \"duration\": 0.08, \"end\": 0.88, \"text\": \"<b>\"}, {\"start\": 0.88, \"duration\": 0.08, \"end\": 0.96, \"text\": \"\▁now\"}, {\"start\": 0.96, \"duration\": 0.16, \"end\": 1.12, \"text\": \"<b>\"}, {\"start\": 1.12, \"duration\": 0.08, \"end\": 1.2, \"text\": \",\"}, {\"start\": 1.2, \"duration\": 0.08, \"end\": 1.28, \"text\": \"<b>\"}, {\"start\": 1.28, \"duration\": 0.08, \"end\": 1.36, \"text\": \"\▁Ri\"}, {\"start\": 1.36, \"duration\": 0.16, \"end\": 1.52, \"text\": \"<b>\"}, {\"start\": 1.52, \"duration\": 0.08, \"end\": 1.6, \"text\": \"ch\"}, {\"start\": 1.6, \"duration\": 0.16, \"end\": 1.76, \"text\": \"<b>\"}, {\"start\": 1.76, \"duration\": 0.08, \"end\": 1.84, \"text\": \",\"}, {\"start\": 1.84, \"duration\": 0.08, \"end\": 1.92, \"text\": \"<b>\"}, {\"start\": 1.92, \"duration\": 0.08, \"end\": 2.0, \"text\": \"\▁would\"}, {\"start\": 2.0, \"duration\": 0.32, \"end\": 2.32, \"text\": \"<b>\"}, {\"start\": 2.32, \"duration\": 0.08, \"end\": 2.4, \"text\": \"\▁you\"}, {\"start\": 2.4, \"duration\": 0.16, \"end\": 2.56, \"text\": \"<b>\"}, {\"start\": 2.56, \"duration\": 0.08, \"end\": 2.64, \"text\": \"\▁like\"}, {\"start\": 2.64, \"duration\": 0.16, \"end\": 2.8, \"text\": \"<b>\"}, {\"start\": 2.8, \"duration\": 0.08, \"end\": 2.88, \"text\": \"\▁some\"}, {\"start\": 2.88, \"duration\": 0.16, \"end\": 3.04, \"text\": \"<b>\"}, {\"start\": 3.04, \"duration\": 0.08, \"end\": 3.12, \"text\": \"\▁pu\"}, {\"start\": 3.12, \"duration\": 0.08, \"end\": 3.2, \"text\": \"s\"}, {\"start\": 3.2, \"duration\": 0.16, \"end\": 3.36, \"text\": \"<b>\"}, {\"start\": 3.36, \"duration\": 0.08, \"end\": 3.44, \"text\": \"s\"}, {\"start\": 3.44, \"duration\": 0.08, \"end\": 3.52, \"text\": \"y\"}, {\"start\": 3.52, \"duration\": 1.68, \"end\": 5.2, \"text\": \"<b>\"}, {\"start\": 5.2, \"duration\": 0.08, \"end\": 5.28, \"text\": \"?\"}, {\"start\": 5.28, \"duration\": 0.64, \"end\": 5.92, \"text\": \"<b>\"}, {\"start\": 5.92, \"duration\": 0.08, \"end\": 6.0, \"text\": \"\▁Well\"}, {\"start\": 6.0, \"duration\": 0.16, \"end\": 6.16, \"text\": \"<b>\"}, {\"start\": 6.16, \"duration\": 0.08, \"end\": 6.24, \"text\": \",\"}, {\"start\": 6.24, \"duration\": 0.08, \"end\": 6.32, \"text\": \"\▁it\"}, {\"start\": 6.32, \"duration\": 0.08, \"end\": 6.4, \"text\": \"<b>\"}, {\"start\": 6.4, \"duration\": 0.08, \"end\": 6.48, \"text\": \"\▁was\"}, {\"start\": 6.48, \"duration\": 0.08, \"end\": 6.56, \"text\": \"n\"}, {\"start\": 6.56, \"duration\": 0.08, \"end\": 6.64, \"text\": \"'\"}, {\"start\": 6.64, \"duration\": 0.08, \"end\": 6.72, \"text\": \"t\"}, {\"start\": 6.72, \"duration\": 0.16, \"end\": 6.88, \"text\": \"\▁on\"}, {\"start\": 6.88, \"duration\": 0.08, \"end\": 6.96, \"text\": \"\▁my\"}, {\"start\": 6.96, \"duration\": 0.08, \"end\": 7.04, \"text\": \"<b>\"}, {\"start\": 7.04, \"duration\": 0.08, \"end\": 7.12, \"text\": \"\▁mind\"}, {\"start\": 7.12, \"duration\": 0.32, \"end\": 7.44, \"text\": \"<b>\"}, {\"start\": 7.44, \"duration\": 0.08, \"end\": 7.52, \"text\": \"\▁right\"}, {\"start\": 7.52, \"duration\": 0.16, \"end\": 7.68, \"text\": \"<b>\"}, {\"start\": 7.68, \"duration\": 0.08, \"end\": 7.76, \"text\": \"\▁now\"}, {\"start\": 7.76, \"duration\": 0.08, \"end\": 7.84, \"text\": \"<b>\"}, {\"start\": 7.84, \"duration\": 0.08, \"end\": 7.92, \"text\": \".\"}, {\"start\": 7.92, \"duration\": 0.08, \"end\": 8.0, \"text\": \"<b>\"}, {\"start\": 8.0, \"duration\": 0.08, \"end\": 8.08, \"text\": \"\▁It\"}, {\"start\": 8.08, \"duration\": 0.16, \"end\": 8.24, \"text\": \"<b>\"}, {\"start\": 8.24, \"duration\": 0.08, \"end\": 8.32, \"text\": \"\▁is\"}, {\"start\": 8.32, \"duration\": 0.16, \"end\": 8.48, \"text\": \"<b>\"}, {\"start\": 8.48, \"duration\": 0.08, \"end\": 8.56, \"text\": \"\▁now\"}, {\"start\": 8.56, \"duration\": 0.16, \"end\": 8.72, \"text\": \"<b>\"}, {\"start\": 8.72, \"duration\": 0.08, \"end\": 8.8, \"text\": \".\"}, {\"start\": 8.8, \"duration\": 1.04, \"end\": 9.84, \"text\": \"<b>\"}, {\"start\": 9.84, \"duration\": 0.08, \"end\": 9.92, \"text\": \"\▁P\"}, {\"start\": 9.92, \"duration\": 0.08, \"end\": 10.0, \"text\": \"<b>\"}, {\"start\": 10.0, \"duration\": 0.08, \"end\": 10.08, \"text\": \"us\"}, {\"start\": 10.08, \"duration\": 0.16, \"end\": 10.24, \"text\": \"<b>\"}, {\"start\": 10.24, \"duration\": 0.08, \"end\": 10.32, \"text\": \"s\"}, {\"start\": 10.32, \"duration\": 0.08, \"end\": 10.4, \"text\": \"y\"}, {\"start\": 10.4, \"duration\": 0.16, \"end\": 10.56, \"text\": \"<b>\"}, {\"start\": 10.56, \"duration\": 0.08, \"end\": 10.64, \"text\": \"\▁en\"}, {\"start\": 10.64, \"duration\": 0.08, \"end\": 10.72, \"text\": \"<b>\"}, {\"start\": 10.72, \"duration\": 0.08, \"end\": 10.8, \"text\": \"er\"}, {\"start\": 10.8, \"duration\": 0.08, \"end\": 10.88, \"text\": \"g\"}, {\"start\": 10.88, \"duration\": 0.08, \"end\": 10.96, \"text\": \"y\"}, {\"start\": 10.96, \"duration\": 0.08, \"end\": 11.04, \"text\": \"<b>\"}, {\"start\": 11.04, \"duration\": 0.08, \"end\": 11.12, \"text\": \"\▁dr\"}, {\"start\": 11.12, \"duration\": 0.08, \"end\": 11.2, \"text\": \"<b>\"}, {\"start\": 11.2, \"duration\": 0.08, \"end\": 11.28, \"text\": \"in\"}, {\"start\": 11.28, \"duration\": 0.08, \"end\": 11.36, \"text\": \"k\"}, {\"start\": 11.36, \"duration\": 1.12, \"end\": 12.48, \"text\": \"<b>\"}, {\"start\": 12.48, \"duration\": 0.08, \"end\": 12.56, \"text\": \".\"}, {\"start\": 12.56, \"duration\": 0.4, \"end\": 12.96, \"text\": \"<b>\"}, {\"start\": 12.96, \"duration\": 0.08, \"end\": 13.04, \"text\": \"\▁I\"}, {\"start\": 13.04, \"duration\": 0.32, \"end\": 13.36, \"text\": \"<b>\"}, {\"start\": 13.36, \"duration\": 0.08, \"end\": 13.44, \"text\": \"\▁see\"}, {\"start\": 13.44, \"duration\": 0.32, \"end\": 13.76, \"text\": \"<b>\"}, {\"start\": 13.76, \"duration\": 0.08, \"end\": 13.84, \"text\": \".\"}, {\"start\": 13.84, \"duration\": 0.48, \"end\": 14.32, \"text\": \"<b>\"}, {\"start\": 14.32, \"duration\": 0.08, \"end\": 14.4, \"text\": \"\▁What\"}, {\"start\": 14.4, \"duration\": 0.16, \"end\": 14.56, \"text\": \"<b>\"}, {\"start\": 14.56, \"duration\": 0.08, \"end\": 14.64, \"text\": \"\▁fl\"}, {\"start\": 14.64, \"duration\": 0.08, \"end\": 14.72, \"text\": \"a\"}, {\"start\": 14.72, \"duration\": 0.08, \"end\": 14.8, \"text\": \"<b>\"}, {\"start\": 14.8, \"duration\": 0.08, \"end\": 14.88, \"text\": \"vo\"}, {\"start\": 14.88, \"duration\": 0.08, \"end\": 14.96, \"text\": \"ur\"}, {\"start\": 14.96, \"duration\": 0.08, \"end\": 15.04, \"text\": \"<b>\"}, {\"start\": 15.04, \"duration\": 0.08, \"end\": 15.12, \"text\": \"\▁is\"}, {\"start\": 15.12, \"duration\": 0.08, \"end\": 15.2, \"text\": \"<b>\"}, {\"start\": 15.2, \"duration\": 0.08, \"end\": 15.28, \"text\": \"\▁it\"}, {\"start\": 15.28, \"duration\": 0.16, \"end\": 15.44, \"text\": \"<b>\"}, {\"start\": 15.44, \"duration\": 0.08, \"end\": 15.52, \"text\": \"?\"}, {\"start\": 15.52, \"duration\": 0.16, \"end\": 15.68, \"text\": \"<b>\"}, {\"start\": 15.68, \"duration\": 0.08, \"end\": 15.76, \"text\": \"\▁F\"}, {\"start\": 15.76, \"duration\": 0.08, \"end\": 15.84, \"text\": \"<b>\"}, {\"start\": 15.84, \"duration\": 0.08, \"end\": 15.92, \"text\": \"la\"}, {\"start\": 15.92, \"duration\": 0.16, \"end\": 16.08, \"text\": \"<b>\"}, {\"start\": 16.08, \"duration\": 0.08, \"end\": 16.16, \"text\": \"vo\"}, {\"start\": 16.16, \"duration\": 0.08, \"end\": 16.24, \"text\": \"<b>\"}, {\"start\": 16.24, \"duration\": 0.08, \"end\": 16.32, \"text\": \"ur\"}, {\"start\": 16.32, \"duration\": 1.68, \"end\": 18.0, \"text\": \"<b>\"}, {\"start\": 18.0, \"duration\": 0.08, \"end\": 18.08, \"text\": \".\"}, {\"start\": 18.08, \"duration\": 0.4, \"end\": 18.48, \"text\": \"<b>\"}, {\"start\": 18.48, \"duration\": 0.08, \"end\": 18.56, \"text\": \"\▁Le\"}, {\"start\": 18.56, \"duration\": 0.08, \"end\": 18.64, \"text\": \"<b>\"}, {\"start\": 18.64, \"duration\": 0.08, \"end\": 18.72, \"text\": \"a\"}, {\"start\": 18.72, \"duration\": 0.08, \"end\": 18.8, \"text\": \"ve\"}, {\"start\": 18.8, \"duration\": 0.08, \"end\": 18.88, \"text\": \"<b>\"}, {\"start\": 18.88, \"duration\": 0.08, \"end\": 18.96, \"text\": \"\▁it\"}, {\"start\": 18.96, \"duration\": 0.24, \"end\": 19.2, \"text\": \"<b>\"}, {\"start\": 19.2, \"duration\": 0.08, \"end\": 19.28, \"text\": \".\"}, {\"start\": 19.28, \"duration\": 0.32, \"end\": 19.6, \"text\": \"<b>\"}, {\"start\": 19.6, \"duration\": 0.08, \"end\": 19.68, \"text\": \"\▁Le\"}, {\"start\": 19.68, \"duration\": 1.44, \"end\": 21.12, \"text\": \"<b>\"}, {\"start\": 21.12, \"duration\": 0.08, \"end\": 21.2, \"text\": \"a\"}, {\"start\": 21.2, \"duration\": 0.16, \"end\": 21.36, \"text\": \"ve\"}, {\"start\": 21.36, \"duration\": 0.08, \"end\": 21.44, \"text\": \"\▁it\"}, {\"start\": 21.44, \"duration\": 0.16, \"end\": 21.6, \"text\": \"<b>\"}, {\"start\": 21.6, \"duration\": 0.08, \"end\": 21.68, \"text\": \".\"}, {\"start\": 21.68, \"duration\": 0.08, \"end\": 21.76, \"text\": \"\▁Yeah\"}, {\"start\": 21.76, \"duration\": 0.16, \"end\": 21.92, \"text\": \"<b>\"}, {\"start\": 21.92, \"duration\": 0.08, \"end\": 22.0, \"text\": \",\"}, {\"start\": 22.0, \"duration\": 0.08, \"end\": 22.08, \"text\": \"<b>\"}, {\"start\": 22.08, \"duration\": 0.08, \"end\": 22.16, \"text\": \"\▁mo\"}, {\"start\": 22.16, \"duration\": 0.16, \"end\": 22.32, \"text\": \"<b>\"}, {\"start\": 22.32, \"duration\": 0.08, \"end\": 22.4, \"text\": \"ving\"}, {\"start\": 22.4, \"duration\": 0.08, \"end\": 22.48, \"text\": \"\▁on\"}, {\"start\": 22.48, \"duration\": 0.16, \"end\": 22.64, \"text\": \"<b>\"}, {\"start\": 22.64, \"duration\": 0.08, \"end\": 22.72, \"text\": \".\"}, {\"start\": 22.72, \"duration\": 0.16, \"end\": 22.88, \"text\": \"<b>\"}, {\"start\": 22.88, \"duration\": 0.08, \"end\": 22.96, \"text\": \"\▁I\"}, {\"start\": 22.96, \"duration\": 0.08, \"end\": 23.04, \"text\": \"'\"}, {\"start\": 23.04, \"duration\": 0.16, \"end\": 23.2, \"text\": \"d\"}, {\"start\": 23.2, \"duration\": 0.08, \"end\": 23.28, \"text\": \"\▁like\"}, {\"start\": 23.28, \"duration\": 0.08, \"end\": 23.36, \"text\": \"\▁to\"}, {\"start\": 23.36, \"duration\": 0.08, \"end\": 23.44, \"text\": \"\▁in\"}, {\"start\": 23.44, \"duration\": 0.08, \"end\": 23.52, \"text\": \"t\"}, {\"start\": 23.52, \"duration\": 0.16, \"end\": 23.68, \"text\": \"ro\"}, {\"start\": 23.68, \"duration\": 0.08, \"end\": 23.76, \"text\": \"duc\"}, {\"start\": 23.76, \"duration\": 0.08, \"end\": 23.84, \"text\": \"e\"}, {\"start\": 23.84, \"duration\": 0.08, \"end\": 23.92, \"text\": \"\▁something\"}, {\"start\": 23.92, \"duration\": 0.16, \"end\": 24.08, \"text\": \"<b>\"}, {\"start\": 24.08, \"duration\": 0.08, \"end\": 24.16, \"text\": \"\▁for\"}, {\"start\": 24.16, \"duration\": 0.08, \"end\": 24.24, \"text\": \"<b>\"}, {\"start\": 24.24, \"duration\": 0.08, \"end\": 24.32, \"text\": \"\▁which\"}, {\"start\": 24.32, \"duration\": 0.08, \"end\": 24.4, \"text\": \",\"}, {\"start\": 24.4, \"duration\": 0.16, \"end\": 24.56, \"text\": \"\▁at\"}, {\"start\": 24.56, \"duration\": 0.08, \"end\": 24.64, \"text\": \"\▁first\"}, {\"start\": 24.64, \"duration\": 0.08, \"end\": 24.72, \"text\": \"<b>\"}, {\"start\": 24.72, \"duration\": 0.08, \"end\": 24.8, \"text\": \",\"}, {\"start\": 24.8, \"duration\": 0.08, \"end\": 24.88, \"text\": \"\▁I\"}, {\"start\": 24.88, \"duration\": 0.08, \"end\": 24.96, \"text\": \"\▁thought\"}, {\"start\": 24.96, \"duration\": 0.16, \"end\": 25.12, \"text\": \"\▁I\"}, {\"start\": 25.12, \"duration\": 0.08, \"end\": 25.2, \"text\": \"'\"}, {\"start\": 25.2, \"duration\": 0.08, \"end\": 25.28, \"text\": \"m\"}, {\"start\": 25.28, \"duration\": 0.08, \"end\": 25.36, \"text\": \"\▁going\"}, {\"start\": 25.36, \"duration\": 0.08, \"end\": 25.44, \"text\": \"\▁to\"}, {\"start\": 25.44, \"duration\": 0.08, \"end\": 25.52, \"text\": \"\▁str\"}, {\"start\": 25.52, \"duration\": 0.08, \"end\": 25.6, \"text\": \"u\"}, {\"start\": 25.6, \"duration\": 0.16, \"end\": 25.76, \"text\": \"gg\"}, {\"start\": 25.76, \"duration\": 0.08, \"end\": 25.84, \"text\": \"le\"}, {\"start\": 25.84, \"duration\": 0.08, \"end\": 25.92, \"text\": \"\▁to\"}, {\"start\": 25.92, \"duration\": 0.08, \"end\": 26.0, \"text\": \"\▁find\"}, {\"start\": 26.0, \"duration\": 0.08, \"end\": 26.08, \"text\": \"\▁a\"}, {\"start\": 26.08, \"duration\": 0.08, \"end\": 26.16, \"text\": \"\▁mo\"}, {\"start\": 26.16, \"duration\": 0.08, \"end\": 26.24, \"text\": \"t\"}, {\"start\": 26.24, \"duration\": 0.08, \"end\": 26.32, \"text\": \"or\"}, {\"start\": 26.32, \"duration\": 0.08, \"end\": 26.4, \"text\": \"ing\"}, {\"start\": 26.4, \"duration\": 0.08, \"end\": 26.48, \"text\": \"<b>\"}, {\"start\": 26.48, \"duration\": 0.08, \"end\": 26.56, \"text\": \"\▁app\"}, {\"start\": 26.56, \"duration\": 0.08, \"end\": 26.64, \"text\": \"li\"}, {\"start\": 26.64, \"duration\": 0.16, \"end\": 26.8, \"text\": \"c\"}, {\"start\": 26.8, \"duration\": 0.08, \"end\": 26.88, \"text\": \"ation\"}, {\"start\": 26.88, \"duration\": 0.08, \"end\": 26.96, \"text\": \"<b>\"}, {\"start\": 26.96, \"duration\": 0.08, \"end\": 27.04, \"text\": \",\"}, {\"start\": 27.04, \"duration\": 0.08, \"end\": 27.12, \"text\": \"\▁because\"}, {\"start\": 27.12, \"duration\": 0.64, \"end\": 27.76, \"text\": \"<b>\"}, {\"start\": 27.76, \"duration\": 0.08, \"end\": 27.84, \"text\": \"\▁what\"}, {\"start\": 27.84, \"duration\": 0.08, \"end\": 27.92, \"text\": \"<b>\"}, {\"start\": 27.92, \"duration\": 0.08, \"end\": 28.0, \"text\": \"\▁it\"}, {\"start\": 28.0, \"duration\": 0.16, \"end\": 28.16, \"text\": \"<b>\"}, {\"start\": 28.16, \"duration\": 0.08, \"end\": 28.24, \"text\": \"\▁is\"}, {\"start\": 28.24, \"duration\": 0.4, \"end\": 28.64, \"text\": \"<b>\"}, {\"start\": 28.64, \"duration\": 0.08, \"end\": 28.72, \"text\": \"\▁is\"}, {\"start\": 28.72, \"duration\": 1.04, \"end\": 29.76, \"text\": \"<b>\"}, {\"start\": 29.76, \"duration\": 0.08, \"end\": 29.84, \"text\": \"\▁this\"}, {\"start\": 29.84, \"duration\": 0.08, \"end\": 29.92, \"text\": \"<b>\"}, {\"start\": 29.92, \"duration\": 0.08, \"end\": 30.0, \"text\": \".\"}, {\"start\": 30.0, \"duration\": 0.08, \"end\": 30.08, \"text\": \"<b>\"}, {\"start\": 30.0, \"duration\": 0.08, \"end\": 30.08, \"text\": \"\▁This\"}, {\"start\": 30.08, \"duration\": 0.24, \"end\": 30.32, \"text\": \"<b>\"}, {\"start\": 30.32, \"duration\": 0.08, \"end\": 30.4, \"text\": \"\▁ma\"}, {\"start\": 30.4, \"duration\": 0.08, \"end\": 30.48, \"text\": \"ch\"}, {\"start\": 30.48, \"duration\": 0.08, \"end\": 30.56, \"text\": \"ine\"}, {\"start\": 30.56, \"duration\": 0.16, \"end\": 30.72, \"text\": \"\▁is\"}, {\"start\": 30.72, \"duration\": 0.08, \"end\": 30.8, \"text\": \"\▁control\"}, {\"start\": 30.8, \"duration\": 0.16, \"end\": 30.96, \"text\": \"le\"}, {\"start\": 30.96, \"duration\": 0.08, \"end\": 31.04, \"text\": \"d\"}, {\"start\": 31.04, \"duration\": 0.08, \"end\": 31.12, \"text\": \"\▁by\"}, {\"start\": 31.12, \"duration\": 0.08, \"end\": 31.2, \"text\": \"\▁your\"}, {\"start\": 31.2, \"duration\": 0.08, \"end\": 31.28, \"text\": \"\▁\"}, {\"start\": 31.28, \"duration\": 0.08, \"end\": 31.36, \"text\": \"i\"}, {\"start\": 31.36, \"duration\": 0.16, \"end\": 31.52, \"text\": \"P\"}, {\"start\": 31.52, \"duration\": 0.08, \"end\": 31.6, \"text\": \"h\"}, {\"start\": 31.6, \"duration\": 0.08, \"end\": 31.68, \"text\": \"one\"}, {\"start\": 31.68, \"duration\": 0.08, \"end\": 31.76, \"text\": \",\"}, {\"start\": 31.76, \"duration\": 0.08, \"end\": 31.84, \"text\": \"\▁right\"}, {\"start\": 31.84, \"duration\": 0.08, \"end\": 31.92, \"text\": \"?\"}, {\"start\": 31.92, \"duration\": 0.08, \"end\": 32.0, \"text\": \"\▁With\"}, {\"start\": 32.0, \"duration\": 0.08, \"end\": 32.08, \"text\": \"\▁an\"}, {\"start\": 32.08, \"duration\": 0.08, \"end\": 32.16, \"text\": \"<b>\"}, {\"start\": 32.16, \"duration\": 0.08, \"end\": 32.24, \"text\": \"\▁app\"}, {\"start\": 32.24, \"duration\": 0.24, \"end\": 32.48, \"text\": \"<b>\"}, {\"start\": 32.48, \"duration\": 0.08, \"end\": 32.56, \"text\": \",\"}, {\"start\": 32.56, \"duration\": 0.08, \"end\": 32.64, \"text\": \"\▁and\"}, {\"start\": 32.64, \"duration\": 0.16, \"end\": 32.8, \"text\": \"<b>\"}, {\"start\": 32.8, \"duration\": 0.08, \"end\": 32.88, \"text\": \"\▁it\"}, {\"start\": 32.88, \"duration\": 0.08, \"end\": 32.96, \"text\": \"<b>\"}, {\"start\": 32.96, \"duration\": 0.08, \"end\": 33.04, \"text\": \"\▁fl\"}, {\"start\": 33.04, \"duration\": 0.16, \"end\": 33.2, \"text\": \"<b>\"}, {\"start\": 33.2, \"duration\": 0.08, \"end\": 33.28, \"text\": \"ies\"}, {\"start\": 33.28, \"duration\": 0.16, \"end\": 33.44, \"text\": \"<b>\"}, {\"start\": 33.44, \"duration\": 0.08, \"end\": 33.52, \"text\": \"\▁up\"}, {\"start\": 33.52, \"duration\": 0.08, \"end\": 33.6, \"text\": \"<b>\"}, {\"start\": 33.6, \"duration\": 0.08, \"end\": 33.68, \"text\": \"\▁in\"}, {\"start\": 33.68, \"duration\": 0.08, \"end\": 33.76, \"text\": \"\▁the\"}, {\"start\": 33.76, \"duration\": 0.08, \"end\": 33.84, \"text\": \"\▁a\"}, {\"start\": 33.84, \"duration\": 0.08, \"end\": 33.92, \"text\": \"ir\"}, {\"start\": 33.92, \"duration\": 0.08, \"end\": 34.0, \"text\": \",\"}, {\"start\": 34.0, \"duration\": 0.08, \"end\": 34.08, \"text\": \"\▁and\"}, {\"start\": 34.08, \"duration\": 0.08, \"end\": 34.16, \"text\": \"\▁there\"}, {\"start\": 34.16, \"duration\": 0.16, \"end\": 34.32, \"text\": \"'\"}, {\"start\": 34.32, \"duration\": 0.08, \"end\": 34.4, \"text\": \"s\"}, {\"start\": 34.4, \"duration\": 0.08, \"end\": 34.480000000000004, \"text\": \"\▁a\"}, {\"start\": 34.480000000000004, \"duration\": 0.08, \"end\": 34.56, \"text\": \"\▁came\"}, {\"start\": 34.56, \"duration\": 0.08, \"end\": 34.64, \"text\": \"<b>\"}, {\"start\": 34.64, \"duration\": 0.16, \"end\": 34.8, \"text\": \"ra\"}, {\"start\": 34.8, \"duration\": 0.08, \"end\": 34.88, \"text\": \"\▁on\"}, {\"start\": 34.88, \"duration\": 0.08, \"end\": 34.96, \"text\": \"\▁it\"}, {\"start\": 34.96, \"duration\": 0.16, \"end\": 35.12, \"text\": \"<b>\"}, {\"start\": 35.12, \"duration\": 0.08, \"end\": 35.2, \"text\": \".\"}], \"segments\": [{\"start\": 0.4, \"duration\": 29.6, \"end\": 30.0, \"text\": \"Ah, now, Rich, would you like some pussy? Well, it wasn't on my mind right now. It is now. Pussy energy drink. I see. What flavour is it? Flavour. Leave it. Leave it. Yeah, moving on. I'd like to introduce something for which, at first, I thought I'm going to struggle to find a motoring application, because what it is is this.\"}, {\"start\": 30.0, \"duration\": 5.2, \"end\": 35.2, \"text\": \"This machine is controlled by your iPhone, right? With an app, and it flies up in the air, and there's a camera on it.\"}]}
		"""

		transcription_str = transcription_str.replace('<space>', ' ')

		# If you want a Python dictionary again, parse it back:
		transcription = json.loads(transcription_str)

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
