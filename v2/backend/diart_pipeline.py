import os
from dotenv import load_dotenv

import nvidia.cublas.lib
import nvidia.cudnn.lib

LD_LIBRARY_PATH = f'{os.path.dirname(nvidia.cublas.lib.__file__)}:{os.path.dirname(nvidia.cudnn.lib.__file__)}'
# LD_LIBRARY_PATH = f'{os.path.dirname(nvidia.cudnn.lib.__file__

os.environ["LD_LIBRARY_PATH"] = LD_LIBRARY_PATH

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, List, Union
import warnings

import torch
import numpy as np
import torchaudio.functional as F  # Added for resampling

from pyannote.core import SlidingWindow, SlidingWindowFeature, Annotation, Timeline, Segment
from diart.models import EmbeddingModel, SegmentationModel
# from diart import SpeakerDiarization, SpeakerDiarizationConfig
from diart_mod import SpeakerDiarization
from diart import SpeakerDiarizationConfig

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
            beam_size=3,
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
    text: str
    deprecated: bool = False


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


@dataclass
class OnlinePipelineConfig:
    segmentation_model_name: str = "pyannote/segmentation-3.0"
    embedding_model_name: str = "speechbrain/spkrec-ecapa-voxceleb" # "pyannote/embedding" "hbredin/wespeaker-voxceleb-resnet34-LM" "nvidia/speakerverification_en_titanet_large"
    whisper_type: str = "faster-whisper"  # one of ['whisper', 'faster-whisper']
    whisper_model: str = "large-v3"  # Model size (tiny, base, small, medium, large, large-v3, distil-large-v3)
    hf_token: Optional[str] = None
    
    # Audio preprocessing settings
    audio_gain: float = 10.0
    audio_gain_mode: str = "db" # one of ["amplitude", "db"]
    normalize_audio: bool = False  # Whether to normalize audio (center and scale)
    high_pass_filter: bool = True  # Whether to apply high-pass filter to remove low-frequency noise
    high_pass_cutoff: float = 80.0  # Cutoff frequency for high-pass filter in Hz
    
    collar: float = 0.5
    min_transcription_duration: float = 1.0
    pre_detection_duration: float = 0.1


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
            embedding=embedding,
            latency=2,
            # tau_active=0.555,
            # rho_update=0.422,
            # delta_new=1.517
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

    def preprocess(self, waveform: Union[torch.Tensor, np.ndarray], sample_rate: int) -> np.ndarray:
        if isinstance(waveform, np.ndarray):
            waveform = torch.from_numpy(waveform)
            waveform = waveform.permute(1, 0) # assume np arr format is (length, channel)

        # Apply resampling if needed
        if sample_rate != self.pipeline.config.sample_rate:
            # Apply resampling
            waveform = F.resample(
                waveform, 
                orig_freq=sample_rate, 
                new_freq=self.pipeline.config.sample_rate
            )
            
        # Apply high-pass filter if enabled
        if self.config.high_pass_filter:
            nyquist = self.pipeline.config.sample_rate / 2
            normalized_cutoff = self.config.high_pass_cutoff / nyquist
            
            # Apply high-pass filter using torchaudio
            # This is a simple first-order filter, can be replaced with more sophisticated ones if needed
            waveform = F.highpass_biquad(
                waveform,
                self.pipeline.config.sample_rate,
                self.config.high_pass_cutoff
            )
            
        # Apply gain adjustment
        if self.config.audio_gain_mode == "amplitude":
            if self.config.audio_gain != 1.0:
                waveform = waveform * self.config.audio_gain
        elif self.config.audio_gain_mode == "db":
            waveform = F.gain(waveform, self.config.audio_gain)
        else:
            warnings.warn(f"config.audio_gain_mode '{self.config.audio_gain_mode}' should instead be one of ['amplitude', 'db']")
            
        waveform = waveform.permute(1, 0) # channel, length -> length, channel
        waveform = waveform.numpy()

        return waveform

    def online_annotate(self, waveform: np.ndarray, audio_start_time: float):
        sliding_window = SlidingWindow(
            start=audio_start_time,
            duration=1.0 / self.pipeline.config.sample_rate,
            step=1.0 / self.pipeline.config.sample_rate,
        )
        
        waveform = SlidingWindowFeature(waveform, sliding_window)
        annotation, _ = self.pipeline([waveform])[0]
        self._annotation.update(annotation)
        
    def reannotate(self):
        self._annotation = Annotation()
        
        outputs = self.pipeline.redo()

        for annotation, _ in outputs:
            self._annotation.update(annotation)
            
    def __call__(self, waveform: Union[torch.Tensor, np.ndarray], sample_rate: int = 16_000):
        """
        Process an audio waveform for speaker diarization.
        
        Args:
            waveform: tensor of shape (channel, length) or np array of shape (length, channel)
            sample_rate: the sample rate of the input waveform
        
        Returns:
            Updated speaker annotation
        """
        # if isinstance(waveform, torch.Tensor):
        #     # if 'cuda' in waveform.device:
        #     waveform = waveform.detach().cpu()            
        #     waveform = waveform.numpy()
            
        if len(waveform.shape) != 2:
            raise ValueError(f'input waveform of shape {waveform.shape} should be of shape (channel, length)')

        waveform = self.preprocess(waveform, sample_rate)
        
        # Continue with existing logic for processing
        if self.waveform is not None:
            self.waveform = np.concatenate((self.waveform, waveform))
        else:
            self.waveform = waveform
            
        while self.waveform.shape[0] > (self.last_processed_start_time + self.duration):
            audio = self.waveform[self.last_processed_start_time:self.last_processed_start_time+self.duration]
            audio_start_time = self.last_processed_start_time / self.pipeline.config.sample_rate
            
            self.online_annotate(audio, audio_start_time)
            
            self.last_processed_start_time += self.step
        return self.get_annotation()
    
    def reset(self):
        """Reset the pipeline state to its initial condition."""
        self.waveform = None
        self.last_processed_start_time = 0
        self._annotation = Annotation()
        self._transcriptions = []
        
    def transcribe(self):
        anno = self.get_annotation()
        for t_segment in self._transcriptions:
            t_segment.deprecated = True
            for segment, track, label in anno.itertracks(yield_label=True):
                if (t_segment.segment.start == segment.start and 
                    t_segment.segment.end == segment.end and 
                    t_segment.label == label):
                    t_segment.deprecated = False
                    break
                
        self._transcriptions = list(filter(lambda x: not x.deprecated, self._transcriptions))
        self._transcriptions.sort(key=lambda x: x.segment.start)
        
        for segment, track, label in anno.itertracks(yield_label=True):
            if (segment.end - segment.start) <= self.config.min_transcription_duration:
                continue
                
            track_exists = False
            for t_segment in self._transcriptions:
                if (t_segment.segment.start == segment.start and 
                    t_segment.segment.end == segment.end and 
                    t_segment.label == label):
                    track_exists = True
                    break
            
            if not track_exists:
                print('Transcribing:', segment, track, label)
                
                # Extract audio for this segment
                start_idx = int((segment.start - self.config.pre_detection_duration) * self.pipeline.config.sample_rate)
                end_idx = int(segment.end * self.pipeline.config.sample_rate)
                
                text = ""
                if end_idx <= self.waveform.shape[0] and (end_idx - start_idx) > 0:
                    # Extract audio segment
                    audio_segment = self.waveform[start_idx:end_idx]
                    
                    text = transcribe_audio_segment(
                        self.whisper,
                        audio_segment
                    )
                
                new_segment = TranscribedSegment(
                    segment=segment,
                    label=label,
                    track=track,
                    text=text
                )
                self._transcriptions.append(new_segment)
    
    def get_transcription(self):
        return self._transcriptions