import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, List
import torch
import numpy as np
from pyannote.core import SlidingWindow, SlidingWindowFeature, Annotation, Timeline, Segment
from diart.models import EmbeddingModel, SegmentationModel
from diart import SpeakerDiarization, SpeakerDiarizationConfig
from faster_whisper import WhisperModel


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
    audio: np.ndarray
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
            beam_size=5,
            language="en"
        )
        
        # Collect all segments' text
        texts = [seg.text for seg in segments]
        transcription = " ".join(texts) if texts else ""
        
        # Clean up transcription
        return transcription.strip()
    
    except Exception as e:
        print(f"Error transcribing audio segment: {e}")
        return ""


@dataclass
class TranscribedSegment:
    segment: Segment
    label: str
    track: str
    transcription: str
    deprecated: bool = False


@dataclass
class OnlinePipelineConfig:
    segmentation_model_name: str = "pyannote/segmentation-3.0"
    embedding_model_name: str = "nvidia/speakerverification_en_titanet_large"
    whisper_type: str = "faster-whisper"  # one of ['whisper', 'faster-whisper']
    whisper_model: str = "small"  # Model size (tiny, base, small, medium, large)
    collar: float = 0.25
    hf_token: Optional[str] = None


class OnlinePipeline:
    def __init__(self, config: OnlinePipelineConfig):
        self.config = config
        
        if config.hf_token is None:
            load_dotenv()
            hf_token = os.environ.get('HF_TOKEN')
        else:
            hf_token = config.hf_token
            
        segmentation = SegmentationModel.from_pretrained(config.segmentation_model_name, use_hf_token=hf_token)
        embedding = EmbeddingModel.from_pretrained(config.embedding_model_name, use_hf_token=hf_token)
        
        speaker_diarization_config = SpeakerDiarizationConfig(
            segmentation=segmentation,
            embedding=embedding
        )
        
        self.pipeline = SpeakerDiarization(speaker_diarization_config)
        self.duration = int(self.pipeline.config.duration * self.pipeline.config.sample_rate)
        self.step = int(self.pipeline.config.step * self.pipeline.config.sample_rate)
        self.waveform: Optional[np.ndarray] = None
        self.last_processed_start_time: int = 0  # adjusted by sample_rate
        self._annotation = Annotation()
        self._transcriptions: Sequence[TranscribedSegment] = []
        
        # Initialize Whisper model
        if config.whisper_type == "faster-whisper":
            self.whisper = initialize_whisper_model(config.whisper_model)
        else:
            # Default to faster-whisper as specified in config
            raise ValueError(f"Unsupported whisper type: {config.whisper_type}. Only 'faster-whisper' is implemented.")
    
    def get_annotation(self):
        return self._annotation.support(self.config.collar)
        
    def __call__(self, waveform, sample_rate: int = 16_000):
        """
        Inputs:
            waveform: numpy array of shape (length, channel)
        """
        if sample_rate != self.pipeline.config.sample_rate:
            # write resampling logic
            pass
        if isinstance(waveform, torch.Tensor):
            # if 'cuda' in waveform.device:
            waveform = waveform.detach().cpu()            
            waveform = waveform.numpy()
        if len(waveform.shape) != 2:
            raise ValueError(f'input waveform of shape {waveform.shape} should be of shape (length, channel)')
        if self.waveform is not None:
            self.waveform = np.concatenate((self.waveform, waveform))
        else:
            self.waveform = waveform
        while self.waveform.shape[0] > (self.last_processed_start_time + self.duration):
            audio = self.waveform[self.last_processed_start_time:self.last_processed_start_time+self.duration]
            
            sliding_window = SlidingWindow(
                start=self.last_processed_start_time/self.pipeline.config.sample_rate,
                duration=1.0 / self.pipeline.config.sample_rate,
                step=1.0 / self.pipeline.config.sample_rate,
            )
            
            audio = SlidingWindowFeature(audio, sliding_window)
            annotation, _ = self.pipeline([audio])[0]
            self._annotation.update(annotation)
            
            self.last_processed_start_time += self.step
        return self.get_annotation()
        
    def transcribe(self):
        anno = self.get_annotation()
        for t_segment in self._transcriptions:
            if not anno.has_track(t_segment.segment, t_segment.track):
                t_segment.deprecated = True
        self._transcriptions = list(filter(lambda x: not x.deprecated, self._transcriptions))
        self._transcriptions.sort(key=lambda x: x.segment.start)
        
        for segment, track, label in anno.itertracks(yield_label=True):
            print(segment, track, label)
            
            track_exists = False
            for t_segment in self._transcriptions:
                if t_segment.segment == segment and t_segment.label == label:
                    track_exists = True
                    break
            
            if not track_exists:
                # Extract audio for this segment
                start_sample = int(segment.start * self.pipeline.config.sample_rate)
                end_sample = int(segment.end * self.pipeline.config.sample_rate)
                
                transcription = ""
                if end_sample <= self.waveform.shape[0] and (end_sample - start_sample) > 0:
                    # Extract audio segment
                    audio_segment = self.waveform[start_sample:end_sample]
                    
                    # Transcribe using the external function
                    transcription = transcribe_audio_segment(
                        self.whisper,
                        audio_segment
                    )
                
                new_segment = TranscribedSegment(
                    segment=segment,
                    label=label,
                    track=track,
                    transcription=transcription
                )
                self._transcriptions.append(new_segment)
    
    def get_transcription(self):
        return self._transcriptions