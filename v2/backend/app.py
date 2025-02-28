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
from speech_parser import OnlineDiarizationPipeline, Audio, SileroVAD, OnlineSpeakerClustering, MSDD
from utils import load_audio

# Configure logging with simpler format
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
        logger.info("Loading models (MSDD, VAD, clustering)")
        self.msdd = MSDD(threshold=0.8)
        self.speech_model = self.msdd.speech_embedding_model
        self.vad = SileroVAD(threshold=0.7)
        self.clustering = OnlineSpeakerClustering()
        
        # Configure audio processing parameters
        self.scales = [1.5, 1.25, 1.0, 0.75, 0.5]
        self.hops = [scale / 4 for scale in self.scales]
        
        # Initialize diarization pipeline
        self.audio_pipeline = OnlineDiarizationPipeline(
            speech_embedding_model=self.speech_model,
            voice_activity_detection_model=self.vad,
            multi_scale_diarization_model=self.msdd,
            speaker_clustering=self.clustering,
            scales=self.scales,
            hops=self.hops
        )
        
        # Audio storage settings
        self.sampling_rate = 44100  # Default sample rate
        self.audio_buffer = np.array([], dtype=np.float32)
        self.output_dir = Path("recorded_audio")
        self.output_dir.mkdir(exist_ok=True)
        
        # Create test_output directory for segment saving
        self.segments_dir = Path("test_output")
        self.segments_dir.mkdir(exist_ok=True)
        
        # Counters for unique filenames
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chunk_counter = 0
        
        # Processing settings
        self.process_threshold = 4096 * 4  # Process when buffer exceeds this size
        self.max_buffer_size = 44100 * 60  # 60 seconds max buffer
        
        # Flags
        self.save_audio = True  # Whether to save audio chunks
        
        logger.info(f"SpeechManager initialized in {time.time() - start_time:.2f}s")
    
    def process_chunk(self, waveform: np.ndarray) -> Dict:
        """Process a single chunk of audio and return diarization results."""
        chunk_start_time = time.time()
        logger.info(f"Processing chunk: {len(waveform)} samples")
        
        try:
            # Add to buffer
            self.audio_buffer = np.append(self.audio_buffer, waveform)
            
            # Cap buffer size to avoid memory issues
            if len(self.audio_buffer) > self.max_buffer_size:
                excess = len(self.audio_buffer) - self.max_buffer_size
                self.audio_buffer = self.audio_buffer[excess:]
                logger.info(f"Buffer trimmed: removed {excess} oldest samples")
            
            # Skip processing if buffer is too small
            if len(self.audio_buffer) < self.process_threshold:
                return {"segments": []}
            
            # Process a copy of the buffer
            process_data = self.audio_buffer.copy()
            process_data_size = len(process_data)
            self.audio_buffer = np.array([], dtype=np.float32)
            
            # Resample if needed
            if self.sampling_rate != self.audio_pipeline.audio.sampling_rate:
                # Convert to torch tensor
                tensor_data = torch.from_numpy(process_data)
                tensor_data = tensor_data.view(1, -1)
                
                # Resample
                resampled_tensor = torchaudio.functional.resample(
                    tensor_data,
                    orig_freq=self.sampling_rate, 
                    new_freq=self.audio_pipeline.audio.sampling_rate
                )
                process_data = resampled_tensor.squeeze().numpy()
                process_data = torchaudio.functional.gain(process_data, 10)
                
                # Save resampled audio if enabled
                if self.save_audio:
                    self.save_audio_chunk(process_data, "resampled", sampling_rate=self.audio_pipeline.audio.sampling_rate)
            
            # Convert to torch tensor for processing
            waveform_torch = torch.from_numpy(process_data)
            
            try:
                # Process using the diarization pipeline
                diarize_start = time.time()
                proba, labels = self.audio_pipeline(waveform_torch)
                diarize_time = time.time() - diarize_start
                
                if labels.numel() > 0:
                    logger.info(f"Diarization: {labels.shape[0]} speakers detected in {diarize_time:.2f}s")
                else:
                    logger.info(f"Diarization: no speakers detected ({diarize_time:.2f}s)")
            except Exception as e:
                logger.error(f"Diarization error: {e}", exc_info=True)
                raise e
                
            # Save the post-processing audio
            if self.save_audio and hasattr(self.audio_pipeline.audio, 'waveform') and self.audio_pipeline.audio.waveform is not None:
                self.save_current_audio("after_processing")
            
            # Get merged speaker segments
            merge_start = time.time()
            merged_segments = self.audio_pipeline.get_merged_speaker_segments(use_cache=False)
            merge_time = time.time() - merge_start
            
            # Save segments if enabled
            if self.save_audio and merged_segments:
                logger.info(f"Saving {len(merged_segments)} segments to {self.segments_dir}")
                for i, segment in enumerate(merged_segments):
                    try:
                        segment_filename = self.segments_dir / f"segment_{self.session_id}_{i+1}_{segment.speaker}_{segment.start:.2f}.wav"
                        torchaudio.save(str(segment_filename), segment.data.unsqueeze(0).cpu(), self.audio_pipeline.audio.sampling_rate)
                    except Exception as e:
                        logger.error(f"Failed to save segment {i}: {e}")
            
            # Format segments for JSON response
            output_segments = [
                {
                    'speaker': segment.speaker, 
                    'start': segment.start, 
                    'end': segment.start + segment.duration, 
                    'duration': segment.duration
                } 
                for segment in merged_segments
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
    
    def save_audio_chunk(self, data, prefix, sampling_rate=None):
        """Save an audio chunk to disk"""
        if sampling_rate is None:
            sampling_rate = self.sampling_rate
            
        self.chunk_counter += 1
        filename = self.output_dir / f"{prefix}_{self.session_id}_{self.chunk_counter:04d}.wav"
        
        # Convert to torch tensor for saving
        tensor_data = torch.from_numpy(data).float()
        if tensor_data.ndim == 1:
            tensor_data = tensor_data.unsqueeze(0)  # Add channel dimension
            
        # Save the audio
        torchaudio.save(str(filename), tensor_data, sampling_rate)
        
    def save_current_audio(self, prefix):
        """Save the current audio from audio_pipeline"""
        try:
            self.chunk_counter += 1
            filename = self.output_dir / f"{prefix}_{self.session_id}_{self.chunk_counter:04d}.wav"
            
            # Get the current waveform from audio_pipeline's audio object
            waveform = self.audio_pipeline.audio.waveform
            
            # Save the audio
            torchaudio.save(str(filename), waveform.unsqueeze(0).cpu(), self.audio_pipeline.audio.sampling_rate)
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
                        speech_parser.sampling_rate = data.get("sampleRate", 44100)
                        logger.info(f"Config received: sample rate={speech_parser.sampling_rate}Hz")
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
                chunk_size_seconds = len(audio_array) / speech_parser.sampling_rate
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
                torchaudio.save(str(segment_filename), segment.data.unsqueeze(0).cpu(), speech_parser.audio_pipeline.audio.sampling_rate)
        
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