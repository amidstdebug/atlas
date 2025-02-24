from pathlib import Path
import json
import asyncio
from typing import List, Dict
import base64
from fastapi import FastAPI, WebSocket, UploadFile, File
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
        
        # Constants for processing
        self.chunk_size = 500_000  # Size of audio chunks to process
        self.sample_rate = 16000   # Expected sample rate

    def process_chunk(self, waveform: np.ndarray) -> Dict:
        """Process a single chunk of audio and return diarization results."""
        try:
            waveform_torch = torch.from_numpy(waveform.copy())
            
            print('waveform loading ok')
            print(waveform_torch.shape)
            torchaudio.save('test.wav', self.audio_processor.waveform.unsqueeze(0).cpu(), 16_000)
            
            proba, labels = self.audio_processor(waveform_torch)
            print('num speakers', self.audio_processor.speaker_clustering.num_speakers)
    
            print('diarization ok')
            
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
            print(e)
            return {
                "segments": []
            }

speech_parser = SpeechManager()

@app.websocket("/ws/diarize")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            # Receive audio chunk as base64 string
            data = await websocket.receive_text()
            chunk_data = json.loads(data)
            
            # Decode base64 audio data
            audio_bytes = base64.b64decode(chunk_data['audio'])
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
            
            # Process the chunk
            results = speech_parser.process_chunk(audio_array)
            
            # Send results back to client
            await websocket.send_json(results)
            
    except Exception as e:
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)