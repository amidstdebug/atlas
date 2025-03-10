# whisper_transcriber.py
import os
import torch
import soundfile as sf
import numpy as np
from ..utils.model_loader import load_whisper_model

class WhisperTranscriber:
    def __init__(self, model_name: str = 'jlvdoorn/whisper-medium.en-atco2-asr'):
        """
        Initialize a Whisper-based transcriber.
        
        Args:
            model_name: Path to model or HuggingFace model name
        """
        self.model_name = model_name
        self.processor, self.model, self.device = load_whisper_model(model_name)
        print(f"WhisperTranscriber initialized with model: {model_name}")
        
    def transcribe(self, audio_filepath: str) -> str:
        """
        Transcribes the given audio file using Whisper model.
        Returns a single string (the transcription).
        
        Args:
            audio_filepath: Path to the audio file
            
        Returns:
            str: Transcription text
        """
        try:
            # Read the audio file
            audio_data, sample_rate = sf.read(audio_filepath)
            
            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            
            # Normalize the audio
            audio_data = audio_data / np.max(np.abs(audio_data))
            
            # Convert to float32
            audio_data = audio_data.astype(np.float32)
            
            # Convert to tensor and move to device
            input_features = self.processor(
                audio_data, 
                sampling_rate=sample_rate, 
                return_tensors="pt"
            ).input_features.to(self.device)
            
            # Generate token ids
            with torch.no_grad():
                predicted_ids = self.model.generate(input_features)
                
            # Decode token ids to text
            transcription = self.processor.batch_decode(
                predicted_ids, 
                skip_special_tokens=True
            )[0]
            
            return transcription
            
        except Exception as e:
            print(f"Error transcribing audio: {str(e)}")
            raise