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

from diarizer import Audio, SileroVAD, OnlineSpeakerClustering, MSDD
from utils import load_audio

app = FastAPI()

class DiarizationManager:
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
                timeline = [segment.speakers for segment in self.audio_processor.base_scale_segments]
                print('got all timeline')
                timeline = self._process_timeline(timeline)
                print('process timeline ok')
                merged_segments = self._merge_segments(timeline)
                print('merge segments ok')
                
                return {
                    "segments": merged_segments,
                    "total_duration": len(timeline) * 0.25
                }
            else:
                return {
                    "segments": [],
                    "total_duration": 0
                }
        except Exception as e:
            print(e)
            return {
                "segments": [],
                "total_duration": 0
            }

    def _process_timeline(self, data: List) -> List:
        """Convert None to empty list for consistency."""
        return [[] if x is None else sorted(x) for x in data]

    def _merge_segments(self, timeline: List) -> List:
        """Merge consecutive segments for each speaker."""
        merged_segments = []
        
        for speaker in set([spk for t in timeline for spk in t]):
            start_idx = None
            
            for t, speakers in enumerate(timeline):
                if speaker in speakers:
                    if start_idx is None:
                        start_idx = t
                elif start_idx is not None:
                    merged_segments.append({
                        'speaker': speaker,
                        'start': start_idx * 0.25,
                        'end': t * 0.25,
                        'duration': (t - start_idx) * 0.25
                    })
                    start_idx = None
            
            if start_idx is not None:
                merged_segments.append({
                    'speaker': speaker,
                    'start': start_idx * 0.25,
                    'end': len(timeline) * 0.25,
                    'duration': (len(timeline) - start_idx) * 0.25
                })
        
        return sorted(merged_segments, key=lambda x: (x['start'], x['speaker']))

diarizer = DiarizationManager()

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
            results = diarizer.process_chunk(audio_array)
            
            # Send results back to client
            await websocket.send_json(results)
            
    except Exception as e:
        await websocket.close(code=1001, reason=str(e))

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Endpoint for processing complete audio files."""
    try:
        # Save uploaded file temporarily
        temp_path = Path("temp_audio.wav")
        with temp_path.open("wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Load and process audio
        waveform, sr = load_audio(str(temp_path))
        waveform = waveform[0]
        
        # Process in chunks
        results = []
        for i in range(0, len(waveform), diarizer.chunk_size):
            chunk = waveform[i:i + diarizer.chunk_size]
            chunk_results = diarizer.process_chunk(chunk)
            results.append(chunk_results)
        
        # Combine results
        all_segments = []
        for r in results:
            all_segments.extend(r['segments'])
        
        final_results = {
            "segments": sorted(all_segments, key=lambda x: (x['start'], x['speaker'])),
            "total_duration": sum(r['total_duration'] for r in results)
        }
        
        # Clean up
        temp_path.unlink()
        
        return JSONResponse(content=final_results)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)