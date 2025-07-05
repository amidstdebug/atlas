from fastapi import (
	FastAPI,
	UploadFile,
	File,
	Depends,
	HTTPException,
	WebSocket,
	WebSocketDisconnect
)
from fastapi.responses import JSONResponse
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from services.whisper_service import WhisperService, get_whisper_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
	"""
	Lifespan manager for the FastAPI application.
	Handles startup and shutdown events, such as model loading.
	"""
	logger.info("Application startup: Initializing Whisper service...")
	try:
		get_whisper_service()
		logger.info("Whisper service initialized successfully.")
	except Exception as e:
		logger.error(f"Application startup failed: {e}")
		raise RuntimeError("Failed to initialize the Whisper model on startup.") from e
	yield
	logger.info("Application shutdown complete.")


app = FastAPI(
	title="Whisper ASR API",
	description="An API for transcribing audio files using the Whisper model via HTTP and WebSockets.",
	version="1.1.0",
	lifespan=lifespan
)

@app.get("/", tags=["General"])
def read_root():
	"""
	Root endpoint to check if the API is running.
	"""
	return {"message": "Whisper ASR API is running."}

@app.post("/transcribe", tags=["Speech-to-Text (HTTP)"])
async def transcribe_audio(
	file: UploadFile = File(...),
	whisper_service: WhisperService = Depends(get_whisper_service)
):
	"""
	Transcribes an entire audio file at once.
	This is suitable for pre-recorded audio files.
	"""
	if file.content_type is None or not file.content_type.startswith("audio/"):
		raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

	try:
		audio_data = await file.read()
		transcription_result = whisper_service.transcribe(audio_data)
		print("transcription_result", transcription_result)

		# Convert result to segments format
		segments = []
		if isinstance(transcription_result, dict) and "chunks" in transcription_result:
			for chunk in transcription_result["chunks"]:
				if "timestamp" in chunk and len(chunk["timestamp"]) >= 2:
					segments.append({
						"text": chunk["text"],
						"start": float(chunk["timestamp"][0]),
						"end": float(chunk["timestamp"][1])
					})
		elif isinstance(transcription_result, list):
			for item in transcription_result:
				if "timestamp" in item and len(item["timestamp"]) >= 2:
					segments.append({
						"text": item["text"],
						"start": float(item["timestamp"][0]),
						"end": float(item["timestamp"][1])
					})

		return JSONResponse(content={"segments": segments})
	except Exception as e:
		logger.error(f"Error processing transcription request: {e}")
		raise HTTPException(status_code=500, detail="An error occurred during transcription.")

@app.websocket("/ws/transcribe")
async def websocket_transcribe(
	websocket: WebSocket,
	whisper_service: WhisperService = Depends(get_whisper_service)
):
	"""
	Transcribes audio in real-time over a WebSocket connection.
	The client should stream audio bytes. The server will stream back transcription results.
	"""
	await websocket.accept()
	logger.info("WebSocket connection established.")

	async def audio_generator() -> AsyncGenerator[bytes, None]:
		"""A generator that yields audio chunks from the WebSocket."""
		try:
			while True:
				# Receive audio data in chunks from the client
				data = await websocket.receive_bytes()
				yield data
		except WebSocketDisconnect:
			logger.info("WebSocket client disconnected.")
		except Exception as e:
			logger.error(f"Error receiving data from WebSocket: {e}")

	try:
		# The service's stream method processes the audio generator
		results_generator = whisper_service.transcribe_stream(audio_generator())

		for result in results_generator:
			# Send the partial or final transcription result back to the client
			await websocket.send_json({
				"text": result,
				"chunks": result.get("chunks", []) # Timestamps per word/phrase
			})

	except Exception as e:
		logger.error(f"An error occurred during WebSocket transcription: {e}")
		# Optionally send an error message to the client before closing
		await websocket.close(code=1011, reason=f"An error occurred: {e}")
	finally:
		if websocket.client_state != "DISCONNECTED":
			await websocket.close()
			logger.info("WebSocket connection closed.")

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)