import os
import io
import base64
import json
from typing import Dict, List, Optional
import numpy as np
import requests
import logging
import jwt
import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Header, WebSocket, Depends, BackgroundTasks, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

from pydantic import BaseModel
from contextlib import asynccontextmanager

from server.funcs.transcription import apply_custom_fixes

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables
AUDIO_SERVER_URL = os.environ.get('AUDIO_SERVER_URL', 'http://audio_server:8000')
OLLAMA_SERVER_URL = os.environ.get('OLLAMA_SERVER_URL', 'http://ollama:11434')
LLM_URI = f"{OLLAMA_SERVER_URL}/api/chat"
JWT_SECRET = os.environ.get('JWT_SECRET', 'meeting_minutes_transcription_2024_secure_key')
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5')

# Define lifespan context manager using asynccontextmanager
import httpx

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting transcription server...")
    
    async with httpx.AsyncClient() as client:
        # Check audio server health asynchronously
        try:
            audio_response = await client.get(f"{AUDIO_SERVER_URL}/health", timeout=5)
            if audio_response.status_code == 200:
                logger.info("Audio server is available")
            else:
                logger.warning(f"Audio server may not be ready. Status: {audio_response.status_code}")
        except Exception as e:
            logger.warning(f"Could not connect to audio server: {str(e)}. Proceeding with startup.")
        
        # Check Ollama server health asynchronously
        try:
            payload = {
                "model": OLLAMA_MODEL,
                "messages": [{"role": "system", "content": "Test connection"}],
                "stream": False
            }
            ollama_response = await client.post(LLM_URI, json=payload, timeout=5)
            if ollama_response.status_code == 200:
                logger.info(f"Ollama server is available with model: {OLLAMA_MODEL}")
            else:
                logger.warning(f"Ollama server returned status {ollama_response.status_code}")
        except Exception as e:
            logger.warning(f"Could not connect to Ollama server: {str(e)}. Proceeding with startup.")
    
    yield  # Yield control back to FastAPI
    
    logger.info("Shutting down transcription server...")


# Create FastAPI application with lifespan
app = FastAPI(
	title="Meeting Minutes Transcription API", 
	version="1.0.0", 
	lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Store connected clients and their latest transcriptions
connected_clients = {}
transcription_history = {}
current_summary = {}

# Pydantic models for request/response validation
class LoginRequest(BaseModel):
	user_id: str
	password: str

class TokenResponse(BaseModel):
	token: str

class TokenData(BaseModel):
	user_id: str
	exp: datetime.datetime

class TranscriptionRequest(BaseModel):
	transcription: str
	previous_report: Optional[str] = None
	summary_mode: str = "atc"

# Function to generate JWT token
def generate_jwt_token(user_id: str) -> str:
	payload = {
		'user_id': user_id,
		'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
	}
	token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
	return token if isinstance(token, str) else token.decode('utf-8')

# Dependency for JWT token verification
async def get_token_data(authorization: str = Header(None)) -> TokenData:
	if not authorization:
		raise HTTPException(status_code=401, detail="Token is missing")
	
	try:
		token = authorization.split(" ")[1]
		payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
		
		return TokenData(
			user_id=payload.get('user_id'),
			exp=datetime.datetime.fromtimestamp(payload.get('exp'))
		)
	except jwt.ExpiredSignatureError:
		raise HTTPException(status_code=401, detail="Token has expired")
	except (jwt.InvalidTokenError, IndexError):
		raise HTTPException(status_code=401, detail="Invalid token")

# Function to summarize transcription text
async def summarize_text(transcription: str, previous_report: Optional[str] = None, summary_mode: str = 'atc') -> Dict:
	try:
		# Format content based on previous report
		if previous_report is not None and previous_report != '':
			content = f"This is the previous report:\n{previous_report}\n\nand these are new transcriptions that just came in:\n{transcription}"
		else:
			content = transcription
			
		# Get the system prompt from the appropriate file
		file_path = f"./server/models/prompt_{summary_mode}"
		absolute_path = os.path.abspath(file_path)
		
		try:
			with open(file_path, 'r') as file:
				system_prompt = file.read()
		except FileNotFoundError:
			logger.warning(f"System prompt file not found: {file_path}. Using default prompt.")
			system_prompt = "You will summarize the meeting transcription provided."
		
		# Define the payload to send to the LLM service
		payload = {
			"model": OLLAMA_MODEL,
			"options": {"temperature": 0.1},
			"messages": [
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": content}
			],
			"stream": False
		}
		
		# Make the request to the Ollama server
		response = await run_in_threadpool(
			lambda: requests.post(LLM_URI, json=payload)
		)
		
		# Check if the request was successful
		if response.status_code != 200:
			logger.error(f"Error from LLM server: {response.text}")
			return {"error": "Failed to generate summary", "details": response.text}
		
		# Return the response from the LLM service
		return response.json()
		
	except Exception as e:
		logger.error(f"Error in summarize_text: {str(e)}")
		raise

# API Routes
@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
	# Check if user_id and password are provided
	if not request.user_id or not request.password:
		raise HTTPException(status_code=400, detail="Missing user_id or password")

	# In a production environment, validate against a secure database
	if request.user_id == 'atlasuser' and request.password == 'passwordbearer2024':
		token = generate_jwt_token(request.user_id)
		return {"token": token}
	else:
		raise HTTPException(status_code=401, detail="Invalid user_id or password")

@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(authorization: str = Header(None)):
	if not authorization:
		raise HTTPException(status_code=401, detail="Token is missing")
		
	try:
		token = authorization.split(" ")[1]
		
		# Decode the token without verifying the expiration
		payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
		exp = datetime.datetime.utcfromtimestamp(payload['exp'])
		now = datetime.datetime.utcnow()

		# Check how long the token has been expired
		time_since_expiry = now - exp

		if time_since_expiry <= datetime.timedelta(hours=1):
			new_payload = {
				'user_id': payload['user_id'],
				'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
			}
			new_token = jwt.encode(new_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
			return {"token": new_token if isinstance(new_token, str) else new_token.decode('utf-8')}
		else:
			raise HTTPException(status_code=403, detail="Token is no longer secure")
			
	except jwt.ExpiredSignatureError:
		raise HTTPException(status_code=401, detail="Token has expired")
	except (jwt.InvalidTokenError, IndexError):
		raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...), token_data: TokenData = Depends(get_token_data)):
	try:
		# Read file content
		file_content = await file.read()
		
		print('received')
		# Forward the file to the audio_server
		files = {'file': (file.filename, file_content, file.content_type)}
		response = requests.post(f"{AUDIO_SERVER_URL}/transcribe/file", files=files)
		
		if response.status_code != 200:
			raise HTTPException(status_code=response.status_code, 
								detail=f"Audio server error: {response.text}")
			
		# Get the transcription from audio_server
		result = response.json()
		transcription = result.get('transcription', '')

		transcription = apply_custom_fixes(transcription)
		
		# Store the transcription in history for this user
		user_id = token_data.user_id
		if user_id not in transcription_history:
			transcription_history[user_id] = []
		
		transcription_history[user_id].append(transcription)
		
		return {"transcription": transcription}

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error transcribing audio: {str(e)}")
		raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/summary")
async def get_summary(request: TranscriptionRequest, token_data: TokenData = Depends(get_token_data)):
	try:
		# Call the internal summarize method
		summary_result = await summarize_text(
			request.transcription, 
			request.previous_report, 
			request.summary_mode
		)
		
		# Store the summary for this user
		user_id = token_data.user_id
		current_summary[user_id] = summary_result
		
		return summary_result

	except Exception as e:
		logger.error(f"Error generating summary: {str(e)}")
		raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/health")
async def health_check():
	health_status = {"status": "healthy", "services": {}}
	
	# Check audio server health
	try:
		audio_response = requests.get(f"{AUDIO_SERVER_URL}/health", timeout=5)
		health_status["services"]["audio_server"] = {
			"status": "healthy" if audio_response.status_code == 200 else "unhealthy",
			"details": audio_response.json() if audio_response.status_code == 200 else {"error": audio_response.text}
		}
	except Exception as e:
		health_status["services"]["audio_server"] = {"status": "unhealthy", "details": {"error": str(e)}}
	
	# Check Ollama server health
	try:
		ollama_response = requests.post(LLM_URI, json={
			"model": OLLAMA_MODEL,
			"messages": [{"role": "system", "content": "Health check"}],
			"stream": False
		}, timeout=5)
		health_status["services"]["ollama_server"] = {
			"status": "healthy" if ollama_response.status_code == 200 else "unhealthy"
		}
	except Exception as e:
		health_status["services"]["ollama_server"] = {"status": "unhealthy", "details": {"error": str(e)}}
	
	# Set overall status
	if any(service["status"] != "healthy" for service in health_status["services"].values()):
		health_status["status"] = "degraded"
	
	return health_status

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
	await websocket.accept()
	try:
		while True:
			data = await websocket.receive_json()
			
			# Get the base64 audio data from the client
			audio_base64 = data.get('audio')
			
			if not audio_base64:
				await websocket.send_json({'error': 'Missing required "audio" data'})
				continue

			# Prepare payload for the audio server
			payload = {'audio': audio_base64}
			
			# Make the request to the audio server
			response = requests.post(f"{AUDIO_SERVER_URL}/transcribe/base64", json=payload)
			print("RESPONSE:", response)
			
			if response.status_code != 200:
				await websocket.send_json({
					'error': 'Failed to transcribe audio',
					'status_code': response.status_code,
					'details': response.text
				})
				continue
			
			# Retrieve the transcription from the audio server response
			result = response.json()
			transcription_data = result.get('transcription', '')

			# Send the transcription back to the client
			await websocket.send_json({'transcription': json.dumps(transcription_data)})

	except WebSocketDisconnect:
		logger.info("WebSocket client disconnected")
	except Exception as e:
		logger.error(f"WebSocket error: {str(e)}")
		await websocket.close(code=1002, reason=str(e))

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=5002)
