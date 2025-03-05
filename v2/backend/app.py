import os
import json
import asyncio
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
import uvicorn
import numpy as np
import torch
import torchaudio

from diart_pipeline import OnlinePipeline, OnlinePipelineConfig, LD_LIBRARY_PATH, transcription_to_rttm
from minutes_pipeline import MinutesPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("diarization_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("diarization_server")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL instead of "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SpeechManager:
    def __init__(self):
        logger.info("Initializing SpeechManager")
        start_time = time.time()
        
        # Initialize models
        logger.info("Loading models.")

        config = OnlinePipelineConfig()
        self.pipeline = OnlinePipeline(config)
        
        # Initialize MinutesPipeline for meeting minutes
        self.minutes_pipeline = MinutesPipeline("llama3")
        
        # Audio storage settings
        self.sample_rate = 44100  # Default sample rate
        self.transcribe_duration = 2
        self.time_since_transcribe = 0
        self.output_dir = Path("recorded_audio")
        self.output_dir.mkdir(exist_ok=True)
        
        self.transform = torchaudio.transforms.Resample(
            orig_freq = self.sample_rate,
            new_freq = self.pipeline.pipeline.config.sample_rate
        )
        
        # Create test_output directory for segment saving
        self.segments_dir = Path("test_output")
        self.segments_dir.mkdir(exist_ok=True)
        
        # Counters for unique filenames
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chunk_counter = 0
        
        # Flags
        self.save_audio = True  # Whether to save audio chunks
        
        # Track the last minute update time to avoid excessive updates
        self.last_minutes_update = 0
        self.minutes_update_interval = 5  # Only update minutes every 5 seconds
        
        logger.info(f"SpeechManager initialized in {time.time() - start_time:.2f}s")
    
    def process_chunk(self, waveform: np.ndarray) -> Dict:
        """Process a single chunk of audio and return diarization results."""
        chunk_start_time = time.time()
        logger.info(f"Processing chunk: {len(waveform)} samples")
        
        try:
            # waveform is processed as in the original code...
            increment_duration = waveform.shape[0]
            self.time_since_transcribe += increment_duration
            
            waveform = np.expand_dims(waveform, 1)
            anno = self.pipeline(waveform, self.sample_rate)
            
            if self.time_since_transcribe > self.transcribe_duration * self.sample_rate:
                self.pipeline.transcribe()
                self.time_since_transcribe = 0
                torchaudio.save(f"recorded_audio/save_{time.time()}.wav", torch.from_numpy(self.pipeline.waveform).permute(1, 0), self.pipeline.pipeline.config.sample_rate)
                
                print(transcription_to_rttm(self.pipeline.get_transcription()))
                
                # Update minutes when new transcription is available
                current_time = time.time()
                if current_time - self.last_minutes_update > self.minutes_update_interval:
                    self.minutes_pipeline(self.pipeline.get_transcription())
                    self.last_minutes_update = current_time

            transcripts = self.pipeline.get_transcription()
            if len(transcripts) > 0:
                output_segments = [
                    {
                        'speaker': transcript.label, 
                        'start': transcript.segment.start, 
                        'end': transcript.segment.end, 
                        'duration': transcript.segment.end - transcript.segment.start,
                        'text': transcript.text
                    } 
                    for transcript in transcripts
                ]
            else:            
                # Format segments for JSON response
                output_segments = [
                    {
                        'speaker': label, 
                        'start': segment.start, 
                        'end': segment.end, 
                        'duration': segment.end - segment.start,
                        'text': f"[{label} audio]"
                    } 
                    for segment, _, label in anno.itertracks(yield_label=True)
                ]
            
            total_time = time.time() - chunk_start_time
            logger.info(f"Processing complete: {len(output_segments)} segments in {total_time:.2f}s")
            
            return {
                "segments": output_segments
            }
        except Exception as e:
            logger.error(f"Chunk processing error: {e}", exc_info=True)
            return {
                "segments": []
            }
    
    async def stream_minutes_updates(self) -> AsyncGenerator[str, None]:
        """Stream meeting minutes updates as they're generated."""
        if not self.pipeline.get_transcription():
            # No transcription available yet
            yield json.dumps({"event": "info", "data": "Waiting for transcription data..."})
            return
        
        # Get current transcription data
        transcripts = self.pipeline.get_transcription()
        
        # Use the streaming minutes pipeline
        for update in self.minutes_pipeline.stream_minutes(transcripts):
            # Convert the update to a JSON string
            yield json.dumps(update)
            
            # Brief pause to avoid overwhelming the client
            await asyncio.sleep(0.05)
            

# Create a single instance of the speech manager
logger.info("Starting speech diarization server")
speech_parser = SpeechManager()

# @app.on_event("startup")
# async def startup_event():
#     os.environ["LD_LIBRARY_PATH"] = LD_LIBRARY_PATH
    # logger.info(os.environ.get("LD_LIBRARY_PATH", "Not set"))

@app.websocket("/ws/call")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = id(websocket)
    logger.info(f"Client connected: {client_id}")
    
    # Client audio configuration
    client_config = None
    
    try:
        # Generate a new session ID for each connection
        speech_parser.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        speech_parser.chunk_counter = 0
        logger.info(f"New session: {speech_parser.session_id}")
        
        message_count = 0
        chunk_count = 0
        session_start_time = time.time()
        
        while True:
            # Receive message
            message = await websocket.receive()
            message_count += 1
            
            # logger.info(os.environ.get("LD_LIBRARY_PATH", "Not set"))
            
            # Handle configuration or JSON data
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    # Configuration message
                    if "type" in data and data["type"] == "config":
                        client_config = data
                        # Update sample rate from client config
                        speech_parser.sample_rate = data.get("sampleRate", 44100)
                        # speech_parser.transform = torchaudio.transforms.Resample(
                        #     orig_freq = speech_parser.sample_rate,
                        #     new_freq = speech_parser.pipeline.pipeline.config.sample_rate
                        # )
                        logger.info(f"Config received: sample rate={speech_parser.sample_rate}Hz")
                        await websocket.send_json({"status": "config_received"})
                        continue
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received")
                    pass
            
            # Handle binary audio data
            if "bytes" in message:
                # Get the binary data and convert to float32 array
                audio_bytes = message["bytes"]
                audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
                
                chunk_count += 1
                chunk_size_seconds = len(audio_array) / speech_parser.sample_rate
                logger.info(f"Chunk #{chunk_count}: {chunk_size_seconds:.2f}s audio")
                
                # Process audio chunk
                chunk_start = time.time()
                results = speech_parser.process_chunk(audio_array)
                chunk_process_time = time.time() - chunk_start
                
                # Send results if there are segments
                if "segments" in results:
                    num_segments = len(results["segments"])
                    logger.info(f"Sending {num_segments} segments to client ({chunk_process_time:.2f}s)")
                    await websocket.send_json(results)
                else:                
                    raise RuntimeError('Response from speech_parser does not have key "segments".')
        
    except WebSocketDisconnect:
        session_duration = time.time() - session_start_time
        logger.info(f"Client {client_id} disconnected. Stats: {session_duration:.2f}s, {chunk_count} chunks")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await websocket.close(code=1001, reason=str(e))

@app.get("/minutes/stream")
async def stream_minutes(request: Request):
    """Stream meeting minutes updates to the client using SSE."""
    async def event_generator():
        try:
            # Send initial message
            yield {
                "event": "start",
                "data": json.dumps({
                    "message": "Starting minutes stream",
                    "session_id": speech_parser.session_id
                })
            }
            
            # Stream minutes updates
            async for update in speech_parser.stream_minutes_updates():
                if await request.is_disconnected():
                    logger.info("Client disconnected from minutes stream")
                    break
                
                yield {
                    "event": "update",
                    "data": update
                }
                
                # Small delay to control flow rate
                await asyncio.sleep(0.1)
                
            # Send completion message
            yield {
                "event": "complete",
                "data": json.dumps({
                    "message": "Minutes generation complete"
                })
            }
            
        except Exception as e:
            logger.error(f"Error in minutes stream: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({
                    "message": f"Error: {str(e)}"
                })
            }
    
    return EventSourceResponse(event_generator())

@app.get("/minutes")
async def get_minutes():
    """Get the current meeting minutes as a complete document."""
    try:
        # Format the current minutes
        minutes_text = speech_parser.minutes_pipeline.format_minutes()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success", 
                "minutes": minutes_text,
                "sections": [
                    {
                        "title": section.title,
                        "description": section.description,
                        "speakers": section.speakers,
                        "start": section.start,
                        "end": section.end
                    }
                    for section in speech_parser.minutes_pipeline.minutes
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error getting minutes: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to get minutes: {str(e)}"}
        )

@app.post("/reset")
async def reset_pipeline():
    """Reset the diarization pipeline to its initial state."""
    try:
        speech_parser.pipeline.reset()
        speech_parser.minutes_pipeline.reset()
        
        # Also reset session-specific information
        speech_parser.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        speech_parser.chunk_counter = 0
        speech_parser.time_since_transcribe = 0
        speech_parser.last_minutes_update = 0
        
        logger.info(f"Pipeline reset. New session: {speech_parser.session_id}")
        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Pipeline reset successfully", "new_session_id": speech_parser.session_id}
        )
    except Exception as e:
        logger.error(f"Error resetting pipeline: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to reset pipeline: {str(e)}"}
        )

if __name__ == "__main__":
    logger.info("Server starting on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)