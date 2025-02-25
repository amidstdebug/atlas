from pathlib import Path
import json
import asyncio
import time
import os
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
import torch
import torchaudio
from speech_parser import Audio, SileroVAD, OnlineSpeakerClustering, MSDD
from utils import load_audio

app = FastAPI()

class SpeechManager:
    def __init__(self):
        # Initialize models
        self.msdd = MSDD(threshold=0.8)
        self.titanet_l = self.msdd.speech_embedding_model
        self.vad = SileroVAD(threshold=0.7)
        self.osc = OnlineSpeakerClustering()
        
        # Configure audio processing parameters
        self.scales = [1.5, 1.25, 1.0, 0.75, 0.5]
        self.hops = [0.75, 0.625, 0.5, 0.375, 0.25]
        
        # Initialize audio processor
        self.audio_processor = Audio(
            self.scales,
            self.hops,
            speech_embedding_model=self.titanet_l,
            voice_activity_detection_model=self.vad,
            multi_scale_diarization_model=self.msdd,
            speaker_clustering=self.osc
        )
        
        # Audio storage settings
        self.sample_rate = 44100  # Default sample rate
        self.audio_buffer = np.array([], dtype=np.float32)
        self.output_dir = Path("recorded_audio")
        self.output_dir.mkdir(exist_ok=True)
        
        # Counters for unique filenames
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chunk_counter = 0
        
        # Processing settings
        self.process_threshold = 4096 * 4  # Process when buffer exceeds this size
        self.max_buffer_size = 44100 * 60  # 60 seconds max buffer
        
        # Flags
        self.save_audio = True  # Whether to save audio chunks

    def process_chunk(self, waveform: np.ndarray) -> Dict:
        """Process a single chunk of audio and return diarization results."""
        try:
            # Add to buffer
            self.audio_buffer = np.append(self.audio_buffer, waveform)
            
            # Cap buffer size to avoid memory issues
            if len(self.audio_buffer) > self.max_buffer_size:
                # Remove oldest samples, keeping the most recent
                excess = len(self.audio_buffer) - self.max_buffer_size
                self.audio_buffer = self.audio_buffer[excess:]
            
            # Skip processing if buffer is too small
            if len(self.audio_buffer) < self.process_threshold:
                return {"segments": []}
            
            # Process a copy of the buffer to avoid modifying the original
            process_data = self.audio_buffer.copy()
            self.audio_buffer = np.array([], dtype=np.float32)
            
            # Resample to 16kHz if needed (for model compatibility)
            if self.sample_rate != 16000:
                # Convert to torch tensor
                tensor_data = torch.from_numpy(process_data)
                tensor_data = tensor_data.view(1, -1)  # [1, length]
                
                # Resample
                resampled_tensor = torchaudio.functional.resample(
                    tensor_data,
                    orig_freq=self.sample_rate, 
                    new_freq=16000
                )
                process_data = resampled_tensor.squeeze().numpy()
                
                # Save resampled audio if enabled
                if self.save_audio:
                    self.save_audio_chunk(process_data, "resampled", sample_rate=16000)
            
            # Convert to torch tensor for processing
            waveform_torch = torch.from_numpy(process_data)
            
            # Save the pre-processing audio
            # if self.save_audio and hasattr(self.audio_processor, 'waveform') and self.audio_processor.waveform is not None:
            #     self.save_current_audio("before_processing")
            
            # Run diarization
            proba, labels = self.audio_processor(waveform_torch)
            
            # Save the post-processing audio
            if self.save_audio and hasattr(self.audio_processor, 'waveform') and self.audio_processor.waveform is not None:
                self.save_current_audio("after_processing")
            
            # Get timeline from base scale segments
            if self.audio_processor.base_scale_segments is not None:
                merged_segments = self.audio_processor.get_merged_speaker_segments(use_cache=False)
                output_segments = [
                    {
                        'speaker': segment.speaker, 
                        'start': segment.start, 
                        'end': segment.end, 
                        'duration': segment.duration
                    } 
                    for segment in merged_segments
                ]
                
                return {
                    "segments": output_segments
                }
            else:
                return {
                    "segments": []
                }
        except Exception as e:
            print(f"Error processing audio: {e}")
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
        print(f"Saved audio chunk to {filename}")
        
    def save_current_audio(self, prefix):
        """Save the current audio from audio_processor"""
        try:
            self.chunk_counter += 1
            filename = self.output_dir / f"{prefix}_{self.session_id}_{self.chunk_counter:04d}.wav"
            
            # Get the current waveform from audio_processor
            waveform = self.audio_processor.waveform
            
            # Save the audio
            torchaudio.save(str(filename), waveform.unsqueeze(0).cpu(), 16000)
            print(f"Saved current audio state to {filename}")
        except Exception as e:
            print(f"Error saving current audio: {e}")

# Create a single instance of the speech manager
speech_parser = SpeechManager()

@app.websocket("/ws/diarize")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Client audio configuration
    client_config = None
    
    try:
        # Generate a new session ID for each connection
        speech_parser.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        speech_parser.chunk_counter = 0
        
        while True:
            # Receive message
            message = await websocket.receive()
            
            # Handle configuration or JSON data
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    # Configuration message
                    if "type" in data and data["type"] == "config":
                        client_config = data
                        # Update sample rate from client config
                        speech_parser.sample_rate = data.get("sampleRate", 44100)
                        print(f"Audio configuration received: {client_config}")
                        await websocket.send_json({"status": "config_received"})
                        continue
                    # Legacy format with base64 encoding
                    elif "audio" in data:
                        print("Received legacy base64 format - not recommended for high fidelity")
                        continue
                except json.JSONDecodeError:
                    pass
            
            # Handle binary audio data
            if "bytes" in message:
                # Get the binary data and convert to float32 array
                audio_bytes = message["bytes"]
                audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
                
                # Process audio chunk
                results = speech_parser.process_chunk(audio_array)
                
                # Send results if there are segments
                if results["segments"]:
                    await websocket.send_json(results)
    
    except WebSocketDisconnect:
        print(f"Client disconnected: {speech_parser.session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=1001, reason=str(e))

@app.put("/redo")
async def redo_diarization():
    """
    Endpoint to trigger rediarization of existing audio segments.
    Returns 200 on success, 500 on error.
    """
    try:
        speech_parser.audio_processor.rediarize()
        return JSONResponse(status_code=200, content={"message": "Rediarization completed"})
    except Exception as e:
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
    return JSONResponse(
        status_code=200, 
        content={"save_audio": speech_parser.save_audio}
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)