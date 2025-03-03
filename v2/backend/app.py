from pathlib import Path
import json
import asyncio
import time
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
import torch
import torchaudio

from diart_pipeline import OnlinePipeline, OnlinePipelineConfig

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

class SpeechManager:
    def __init__(self):
        logger.info("Initializing SpeechManager")
        start_time = time.time()
        
        # Initialize models
        logger.info("Loading models.")

        config = OnlinePipelineConfig()
        self.pipeline = OnlinePipeline(config)
        
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
        
        logger.info(f"SpeechManager initialized in {time.time() - start_time:.2f}s")
    
    def process_chunk(self, waveform: np.ndarray) -> Dict:
        """Process a single chunk of audio and return diarization results."""
        chunk_start_time = time.time()
        logger.info(f"Processing chunk: {len(waveform)} samples")
        
        try:
            waveform_torch = torch.from_numpy(waveform)
            increment_duration = waveform_torch.shape[0]
            self.time_since_transcribe += increment_duration
            waveform_torch = waveform_torch.unsqueeze(0)
            
            if self.sample_rate != self.pipeline.pipeline.config.sample_rate:
                waveform_torch = self.transform(waveform_torch)
            waveform_torch = waveform_torch.permute(1, 0)
            anno = self.pipeline(waveform_torch)
            
            if self.time_since_transcribe > self.transcribe_duration * self.sample_rate:
                self.pipeline.transcribe()

            transcripts = self.pipeline.get_transcription()
            if len(transcripts) > 0:
                output_segments = [
                    {
                        'speaker': transcript.label, 
                        'start': transcript.segment.start, 
                        'end': transcript.segment.end, 
                        'duration': transcript.segment.end - transcript.segment.start,
                        'text': transcript.transcription
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
    
    def save_audio_chunk(self, data, prefix, sample_rate=None):
        """Save an audio chunk to disk"""
        if sample_rate is None:
            sample_rate = self.sample_rate
            
        self.chunk_counter += 1
        filename = self.output_dir / f"{prefix}_{self.session_id}_{self.chunk_counter:04d}.wav"
        
        # Convert to torch tensor for saving
        tensor_data = torch.from_numpy(data).float()
        if tensor_data.ndim == 1:
            tensor_data = tensor_data.unsqueeze(0)  # Add channel dimension
            
        # Save the audio
        torchaudio.save(str(filename), tensor_data, sample_rate)
        
    def save_current_audio(self, prefix):
        """Save the current audio from audio_pipeline"""
        try:
            self.chunk_counter += 1
            filename = self.output_dir / f"{prefix}_{self.session_id}_{self.chunk_counter:04d}.wav"
            
            # Get the current waveform from audio_pipeline's audio object
            waveform = self.audio_pipeline.audio.waveform
            
            # Save the audio
            torchaudio.save(str(filename), waveform.unsqueeze(0).cpu(), self.audio_pipeline.audio.sample_rate)
        except Exception as e:
            logger.error(f"Error saving current audio: {e}")

# Create a single instance of the speech manager
logger.info("Starting speech diarization server")
speech_parser = SpeechManager()

@app.websocket("/ws/diarize")
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
                        speech_parser.transform = torchaudio.transforms.Resample(
                            orig_freq = speech_parser.sample_rate,
                            new_freq = speech_parser.pipeline.pipeline.config.sample_rate
                        )
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

@app.put("/redo")
async def redo_diarization():
    """
    Endpoint to trigger rediarization of existing audio segments.
    Returns 200 on success, 500 on error.
    """
    logger.info("Rediarization requested")
    try:
        start_time = time.time()
        
        # Use the pipeline's rediarize method
        proba, labels = speech_parser.audio_pipeline.rediarize()
        
        # Get the updated segments
        updated_segments = speech_parser.audio_pipeline.get_merged_speaker_segments()
        
        # Save rediarized segments
        if updated_segments:
            logger.info(f"Saving {len(updated_segments)} rediarized segments")
            for i, segment in enumerate(updated_segments):
                segment_filename = speech_parser.segments_dir / f"rediarized_{speech_parser.session_id}_{i+1}_{segment.speaker}_{segment.start:.2f}.wav"
                torchaudio.save(str(segment_filename), segment.data.unsqueeze(0).cpu(), speech_parser.audio_pipeline.audio.sample_rate)
        
        total_time = time.time() - start_time
        logger.info(f"Rediarization complete: {len(updated_segments)} segments in {total_time:.2f}s")
        
        return JSONResponse(
            status_code=200, 
            content={
                "message": "Rediarization completed", 
                "segments_count": len(updated_segments),
                "processing_time": total_time
            }
        )
    except Exception as e:
        logger.error(f"Rediarization failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, 
            content={"error": f"Failed to perform rediarization: {str(e)}"}
        )

@app.put("/toggle-save-audio")
async def toggle_save_audio():
    """
    Endpoint to toggle audio saving.
    """
    speech_parser.save_audio = not speech_parser.save_audio
    logger.info(f"Audio saving: {speech_parser.save_audio}")
    return JSONResponse(
        status_code=200, 
        content={"save_audio": speech_parser.save_audio}
    )

@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok", 
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    logger.info("Server starting on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)