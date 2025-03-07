from typing import Sequence

import numpy as np
import torch

from faster_whisper import WhisperModel

from .config import FasterWhisperTranscribeConfig, DEFAULT_FASTER_WHISPER_TRANSCRIBE_CONFIG
from .segments import TranscribedSegment

def initialize_whisper_model(model_name: str = "small") -> WhisperModel:
    """
    Initialize a faster-whisper model with appropriate settings.
    
    Args:
        model_name: Size of the Whisper model (tiny, base, small, medium, large)
        
    Returns:
        WhisperModel instance
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "float32"
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def transcribe_audio_segment(
    whisper_model: WhisperModel,
    audio: np.ndarray,
    whisper_config: FasterWhisperTranscribeConfig = DEFAULT_FASTER_WHISPER_TRANSCRIBE_CONFIG
) -> str:
    """
    Transcribe an audio segment using faster-whisper.
    
    Args:
        whisper_model: Initialized WhisperModel
        audio: Audio data as numpy array
        sample_rate: Sample rate of the audio
        
    Returns:
        Transcribed text
    """
    try:
        # Convert to mono if needed (faster-whisper expects mono audio)
        if len(audio.shape) == 2:
            if audio.shape[1] > 1:  # Multi-channel
                audio = audio.mean(axis=1)
            else:  # Single channel in 2D format
                audio = audio.flatten()
        
        # Transcribe using faster-whisper
        segments, _ = whisper_model.transcribe(
            audio,
            beam_size=whisper_config.beam_size,
            best_of=whisper_config.best_of,
            condition_on_previous_text=whisper_config.condition_on_previous_text,
            language=whisper_config.language
        )
        
        # Collect all segments' text
        texts = [seg.text for seg in segments]
        transcription = " ".join(texts) if texts else ""
        
        # Clean up transcription
        return transcription.strip()
    
    except Exception as e:
        print(f"Error transcribing audio segment: {e}")
        return ""

def transcription_to_rttm(
    transcription: Sequence[TranscribedSegment], 
    file_id='file_0'
):
    lines = []
    for seg in transcription:
        # RTTM format:
        # Type file_id channel_id start_time duration ortho speaker_type speaker_name conf
        # SPEAKER file_0 1 0.01 1.09 <NA> <NA> speaker_0 <NA>
        
        start = seg.segment.start
        duration = seg.segment.end - seg.segment.start
        speaker = seg.label
        
        line = f'SPEAKER {file_id} 1 {start:.3f} {duration:.3f} "{seg.text}" <NA> {speaker} <NA>'
        lines.append(line)
    
    return "\n".join(lines)
