import os
import json
import asyncio
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional, AsyncGenerator
from pathlib import Path
import queue
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

from sse_starlette.sse import EventSourceResponse
import uvicorn

import tempfile

import numpy as np
import torch
import torchaudio

from pipeline import OnlinePipeline, OnlinePipelineConfig, LD_LIBRARY_PATH
from pipeline.utils import transcription_to_rttm
from ollama_pipeline import MinutesPipeline
from utils import EnhancedJSONEncoder

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

def serialize_section(section):
    """Convert a MinutesSection object to a serializable dictionary."""
    if hasattr(section, '__dict__'):
        return {
            "title": section.title,
            "description": section.description,
            "speakers": section.speakers,
            "start": section.start,
            "end": section.end,
            "segment_ids": section.segment_ids if hasattr(section, 'segment_ids') else []
        }
    return section  # Return as is if not a MinutesSection object

class SpeechManager:
    def __init__(self):
        logger.info("Initializing SpeechManager")
        start_time = time.time()
        
        # Initialize models
        logger.info("Loading models.")

        config = OnlinePipelineConfig()
        self.pipeline = OnlinePipeline(config)
        
        # Initialize MinutesPipeline for meeting minutes
        self.minutes_pipeline = MinutesPipeline("phi4:latest")
        # self.minutes_pipeline = MinutesPipeline("phi4:14b-q8_0")
        
        # Audio storage settings
        self.sample_rate = 44100  # Default sample rate
        
        self.transcribe_duration = 2
        self.time_since_transcribe = 0
        self.save_duration = 60
        self.time_since_save = 0
        
        self.output_dir = Path("recorded_audio")
        self.output_dir.mkdir(exist_ok=True)
        
        # Create test_output directory for segment saving
        self.segments_dir = Path("test_output")
        self.segments_dir.mkdir(exist_ok=True)
        
        # Counters for unique filenames
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chunk_counter = 0
        
        # Flags
        self.save_audio = True  # Whether to save audio chunks
        
        # Queue for progress updates
        self.progress_queue = queue.Queue()
        self.is_generating_minutes = False
        
        logger.info(f"SpeechManager initialized in {time.time() - start_time:.2f}s")

    def get_output_segments(self):
        transcripts = self.pipeline.get_transcription()
        if len(transcripts) > 0:
            output_segments = [
                {
                    'speaker': transcript.label, 
                    'start': transcript.segment.start, 
                    'end': transcript.segment.end, 
                    'duration': transcript.segment.end - transcript.segment.start,
                    'text': transcript.text,
                    'id': transcript.id
                } 
                for transcript in transcripts
            ]
        else:            
            # Format segments for JSON response
            annotation = self.pipeline.get_annotation()
            output_segments = [
                {
                    'speaker': label, 
                    'start': segment.start, 
                    'end': segment.end, 
                    'duration': segment.end - segment.start,
                    'text': f"[{label} audio]"
                } 
                for segment, _, label in annotation.itertracks(yield_label=True)
            ]

        return output_segments
    
    def process_chunk(self, waveform: np.ndarray) -> Dict:
        """Process a single chunk of audio and return diarization results."""
        chunk_start_time = time.time()
        logger.info(f"Processing chunk: {len(waveform)} samples")
        
        try:
            # waveform is processed as in the original code...
            increment_duration = waveform.shape[0]
            self.time_since_transcribe += increment_duration
            self.time_since_save += increment_duration
            
            waveform = np.expand_dims(waveform, 1)
            self.pipeline(waveform, self.sample_rate)
            
            if self.time_since_transcribe > self.transcribe_duration * self.sample_rate:
                self.pipeline.transcribe()
                self.time_since_transcribe = 0

            if self.time_since_save > self.save_duration * self.sample_rate:
                pipeline_sample_rate = self.pipeline.get_pipeline().config.sample_rate
                pipeline_waveform = torch.from_numpy(self.pipeline.waveform).permute(1, 0)
                torchaudio.save(f"recorded_audio/save_{time.time()}.wav", pipeline_waveform, pipeline_sample_rate)
                self.time_since_save = 0
                
            output_segments = self.get_output_segments()
            
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
    
    def progress_callback(self, update):
        """Callback to receive progress updates from minutes generation"""
        # Add to progress queue to be consumed by SSE
        self.progress_queue.put(update)
        logger.info(f"Minutes progress: {update.get('type', 'unknown')} - {update.get('message', '')}")
    
    def generate_minutes_thread(self, transcripts):
        """Generate minutes in a separate thread to avoid blocking"""
        try:
            self.is_generating_minutes = True
            self.minutes_pipeline.generate_minutes_with_progress(transcripts, self.progress_callback)
            self.is_generating_minutes = False
        except Exception as e:
            logger.error(f"Error in minutes generation thread: {e}", exc_info=True)
            self.progress_callback({"type": "error", "message": f"Error: {str(e)}"})
            self.is_generating_minutes = False
    
    def start_minutes_generation(self):
        """Start minutes generation in the background with progress updates"""
        transcripts = self.pipeline.get_transcription()
        if not transcripts:
            return False, "No transcription data available"
        
        # Clear the progress queue
        while not self.progress_queue.empty():
            self.progress_queue.get()
            
        # Start generation in a thread to avoid blocking
        threading.Thread(
            target=self.generate_minutes_thread,
            args=(transcripts,),
            daemon=True
        ).start()
        
        return True, "Minutes generation started"
    
    async def stream_minutes_progress(self) -> AsyncGenerator[str, None]:
        """Stream progress updates about minutes generation"""
        # Initial update
        yield json.dumps({
            "type": "status", 
            "message": "Starting minutes generation...",
            "timestamp": time.time()
        }, cls=EnhancedJSONEncoder)
        
        # Keep checking the progress queue for updates
        timeout_seconds = 180  # 3 minutes timeout
        start_time = time.time()
        
        while True:
            try:
                # Check if we've been running too long
                if time.time() - start_time > timeout_seconds:
                    yield json.dumps({
                        "type": "error", 
                        "message": "Minutes generation timed out",
                        "timestamp": time.time()
                    }, cls=EnhancedJSONEncoder)
                    break
                
                # Check if minutes generation is complete
                if not self.is_generating_minutes and self.progress_queue.empty():
                    # One final message if everything succeeded
                    yield json.dumps({
                        "type": "complete", 
                        "message": "Minutes generation complete",
                        "timestamp": time.time()
                    }, cls=EnhancedJSONEncoder)
                    break
                
                # Try to get an update from the queue with a timeout
                try:
                    update = self.progress_queue.get(timeout=0.5)
                    # Add timestamp to the update
                    update["timestamp"] = time.time()
                    yield json.dumps(update, cls=EnhancedJSONEncoder)
                except queue.Empty:
                    # No updates yet, yield a heartbeat message
                    yield json.dumps({
                        "type": "heartbeat", 
                        "timestamp": time.time()
                    }, cls=EnhancedJSONEncoder)
                    
                # Short sleep to avoid overwhelming the client
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in progress stream: {e}", exc_info=True)
                yield json.dumps({
                    "type": "error", 
                    "message": f"Error in progress stream: {str(e)}",
                    "timestamp": time.time()
                }, cls=EnhancedJSONEncoder)
                break

# Create a single instance of the speech manager
logger.info("Starting speech diarization server")
speech_parser = SpeechManager()

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
            
            # Handle configuration or JSON data
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    # Configuration message
                    if "type" in data and data["type"] == "config":
                        client_config = data
                        # Update sample rate from client config
                        speech_parser.sample_rate = data.get("sampleRate", 44100)
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

@app.get("/minutes/progress")
async def stream_minutes_progress(request: Request):
    """Stream progress updates during minutes generation using SSE."""
    # Start the minutes generation process
    success, message = speech_parser.start_minutes_generation()
    
    if not success:
        # If we can't start minutes generation, return an error event
        async def error_generator():
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "message": message
                })
            }
        return EventSourceResponse(error_generator())
    
    # Stream progress updates
    async def event_generator():
        async for update in speech_parser.stream_minutes_progress():
            if await request.is_disconnected():
                logger.info("Client disconnected from progress stream")
                break
            
            yield {
                "event": "update",
                "data": update
            }
    
    return EventSourceResponse(event_generator())

@app.get("/minutes")
async def get_minutes():
    """Get the current meeting minutes as a complete document."""
    try:
        # Check if minutes have already been generated
        if not speech_parser.minutes_pipeline.minutes:
            # If not, try to generate them - but don't wait for completion
            return JSONResponse(
                status_code=202,  # Accepted, but processing
                content={
                    "status": "processing", 
                    "message": "Minutes generation in progress. Use the /minutes/progress endpoint to track status."
                }
            )
        
        # Format the minutes if they're already available
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

@app.post("/reannotate")
async def redo_annotation():
    """Reset the diarization pipeline to its initial state."""
    try:
        speech_parser.pipeline.reannotate()
        
        logger.info(f"Transcript reannotated.")
        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Pipeline reannotated successfully"}
        )
    except Exception as e:
        logger.error(f"Error resetting pipeline: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to reset pipeline: {str(e)}"}
        )
        
@app.get("/download/rttm")
async def download_rttm():
    """Download the current transcription as an RTTM file."""
    try:
        # Get the current transcription
        transcripts = speech_parser.pipeline.get_transcription()
        
        if not transcripts:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "No transcription data available"}
            )
        
        # Generate RTTM content with current session ID as file_id
        rttm_content = transcription_to_rttm(transcripts, file_id=speech_parser.session_id)
        
        # Create filename with session ID and timestamp
        filename = f"transcript_{speech_parser.session_id}.rttm"
        
        # Return the RTTM content as a downloadable file
        from fastapi.responses import Response
        return Response(
            content=rttm_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Error generating RTTM file: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to generate RTTM file: {str(e)}"}
        )

@app.get("/segments")
async def get_segments():
    try:
        output_segments = speech_parser.get_output_segments()
        
        return JSONResponse(
            status_code=200,
            content={
                "segments": output_segments
            }
        )
    except Exception as e:
        logger.error(f"Error getting segments: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to get segments: {str(e)}"}
        )

@app.get("/segments/{segment_id}/audio")
async def get_segment_audio(segment_id: str, background_tasks: BackgroundTasks):
    """
    Return the audio waveform for a specific transcription segment by ID.
    
    Parameters:
    - segment_id: The unique identifier of the transcription segment
    - background_tasks: FastAPI background tasks handler (injected automatically)
    
    Returns:
    - Audio file in WAV format
    """
    temp_path = None
    try:
        # Find the segment with the matching ID
        transcripts = speech_parser.pipeline.get_transcription()
        
        # Find the target segment
        target_segment = None
        for transcript in transcripts:
            if transcript.id == segment_id:
                target_segment = transcript
                break
        
        if not target_segment:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": f"Segment with ID {segment_id} not found"}
            )
        
        # Extract timing information
        sample_rate = speech_parser.pipeline.get_pipeline().config.sample_rate
        start_idx = int(target_segment.segment.start * sample_rate)
        end_idx = int(target_segment.segment.end * sample_rate)
        
        # Ensure indices are within bounds
        start_idx = max(0, start_idx)
        end_idx = min(len(speech_parser.pipeline.waveform), end_idx)
        
        # Extract the segment waveform
        segment_waveform = speech_parser.pipeline.waveform[start_idx:end_idx]
        
        # Convert numpy array to torch tensor for torchaudio
        segment_tensor = torch.from_numpy(segment_waveform).permute(1, 0)  # Reshape to [channels, samples]
        
        # Create a temporary file with a more robust approach
        temp_dir = Path("temp_audio")
        temp_dir.mkdir(exist_ok=True)
        
        temp_filename = f"segment_{segment_id}_{int(time.time())}.wav"
        temp_path = temp_dir / temp_filename
        
        # Save the audio segment to the file
        torchaudio.save(str(temp_path), segment_tensor, sample_rate)
        
        # Ensure the file exists before returning
        if not temp_path.exists():
            raise FileNotFoundError(f"Failed to create audio file at {temp_path}")
            
        # Log file creation
        logger.info(f"Created audio file for segment {segment_id} at {temp_path}")
        
        # Define a proper cleanup function for the background task
        def cleanup_temp_file():
            try:
                # Add a slight delay to ensure the file is fully sent before deletion
                time.sleep(2)
                if temp_path.exists():
                    temp_path.unlink()
                    logger.info(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.error(f"Error cleaning up temp file {temp_path}: {e}")
        
        # Add the cleanup function to background tasks
        background_tasks.add_task(cleanup_temp_file)
        
        # Return the WAV file
        return FileResponse(
            path=str(temp_path),
            media_type="audio/wav",
            filename=f"segment_{segment_id}.wav"
        )
            
    except Exception as e:
        logger.error(f"Error extracting segment audio: {e}", exc_info=True)
        # Clean up temp file if it exists
        if temp_path and Path(temp_path).exists():
            try:
                Path(temp_path).unlink()
            except Exception:
                pass
                
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to extract segment audio: {str(e)}"}
        )

if __name__ == "__main__":
    logger.info("Server starting on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)