import os
from dotenv import load_dotenv
import hashlib
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, List, Union
import warnings

import torch
import numpy as np
import torchaudio.functional as F  # Added for resampling

from pyannote.core import SlidingWindow, SlidingWindowFeature, Annotation
from diart.models import EmbeddingModel, SegmentationModel
# from diart import SpeakerDiarization, SpeakerDiarizationConfig
from .diart_mod import SpeakerDiarization
from diart import SpeakerDiarizationConfig

from faster_whisper import WhisperModel

from .segments import TranscribedSegment
from .utils import initialize_whisper_model, transcribe_audio_segment
from .config import OnlinePipelineConfig

class OnlinePipeline:
    def __init__(self, config: OnlinePipelineConfig):
        self.config = config
        
        if self.config.hf_token is None:
            load_dotenv()
            hf_token = os.environ.get('HF_TOKEN')
        else:
            hf_token = config.hf_token
            
        segmentation = SegmentationModel.from_pretrained(self.config.segmentation_model_name, use_hf_token=hf_token)
        embedding = EmbeddingModel.from_pretrained(self.config.embedding_model_name, use_hf_token=hf_token)
        
        speaker_diarization_config = SpeakerDiarizationConfig(
            segmentation=segmentation,
            embedding=embedding,
            # latency=2,
            # tau_active=0.555,
            # rho_update=0.422,
            delta_new=1.2
        )
        
        self._pipeline = SpeakerDiarization(speaker_diarization_config)
        self.duration = int(self._pipeline.config.duration * self._pipeline.config.sample_rate)
        self.step = int(self._pipeline.config.step * self._pipeline.config.sample_rate)
        self.waveform: Optional[np.ndarray] = None
        self.last_processed_start_time: int = 0  # adjusted by sample_rate
        self._annotation = Annotation()
        self._transcription: Sequence[TranscribedSegment] = []
        
        if config.whisper_type == "faster-whisper":
            self.whisper: WhisperModel = initialize_whisper_model(config.whisper_model)
        else:
            # Default to faster-whisper as specified in config
            raise ValueError(f"Unsupported whisper type: {config.whisper_type}. Only 'faster-whisper' is implemented.")

    def get_pipeline(self):
        return self._pipeline
    
    def get_annotation(self):
        return self._annotation.support(self.config.audio_postprocess.collar)

    def preprocess(self, waveform: Union[torch.Tensor, np.ndarray], sample_rate: int) -> np.ndarray:
        if isinstance(waveform, np.ndarray):
            waveform = torch.from_numpy(waveform)
            waveform = waveform.permute(1, 0) # assume np arr format is (length, channel)

        # Apply resampling if needed
        if sample_rate != self._pipeline.config.sample_rate:
            # Apply resampling
            waveform = F.resample(
                waveform, 
                orig_freq=sample_rate, 
                new_freq=self._pipeline.config.sample_rate
            )
            
        # Apply high-pass filter if enabled
        if self.config.audio_preprocess.high_pass_filter:
            nyquist = self._pipeline.config.sample_rate / 2
            normalized_cutoff = self.config.audio_preprocess.high_pass_cutoff / nyquist
            
            # Apply high-pass filter using torchaudio
            # This is a simple first-order filter, can be replaced with more sophisticated ones if needed
            waveform = F.highpass_biquad(
                waveform,
                self._pipeline.config.sample_rate,
                self.config.audio_preprocess.high_pass_cutoff
            )
            
        # Apply gain adjustment
        if self.config.audio_preprocess.audio_gain_mode == "amplitude":
            if self.config.audio_preprocess.audio_gain != 1.0:
                waveform = waveform * self.config.audio_preprocess.audio_gain
        elif self.config.audio_preprocess.audio_gain_mode == "db":
            waveform = F.gain(waveform, self.config.audio_preprocess.audio_gain)
        else:
            warnings.warn(f"config.audio_gain_mode '{self.config.audio_preprocess.audio_gain_mode}' should instead be one of ['amplitude', 'db']")
            
        waveform = waveform.permute(1, 0) # channel, length -> length, channel
        waveform = waveform.numpy()

        return waveform

    def online_annotate(self, waveform: np.ndarray, audio_start_time: float):
        sliding_window = SlidingWindow(
            start=audio_start_time,
            duration=1.0 / self._pipeline.config.sample_rate,
            step=1.0 / self._pipeline.config.sample_rate,
        )
        
        waveform = SlidingWindowFeature(waveform, sliding_window)
        annotation, _ = self._pipeline([waveform])[0]
        self._annotation.update(annotation)
        
    def reannotate(self):
        self._annotation = Annotation()
        self._transcription = []
        
        outputs = self._pipeline.redo()

        for annotation, _ in outputs:
            self._annotation.update(annotation)

        self.transcribe()
            
    def __call__(self, waveform: Union[torch.Tensor, np.ndarray], sample_rate: int = 16_000):
        """
        Process an audio waveform for speaker diarization.
        
        Args:
            waveform: tensor of shape (channel, length) or np array of shape (length, channel)
            sample_rate: the sample rate of the input waveform
        
        Returns:
            Updated speaker annotation
        """
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
            audio_start_time = self.last_processed_start_time / self._pipeline.config.sample_rate
            
            self.online_annotate(audio, audio_start_time)
            
            self.last_processed_start_time += self.step
        return self.get_annotation()
    
    def reset(self):
        """Reset the pipeline state to its initial condition."""
        self.waveform = None
        self.last_processed_start_time = 0
        self._annotation = Annotation()
        self._transcription = []
        
    def transcribe(self):
        anno = self.get_annotation()
        for t_segment in self._transcription:
            t_segment.deprecated = True
            for segment, track, label in anno.itertracks(yield_label=True):
                if (t_segment.segment.start == segment.start and 
                    t_segment.segment.end == segment.end and 
                    t_segment.label == label):
                    t_segment.deprecated = False
                    break
                
        self._transcription = list(filter(lambda x: not x.deprecated, self._transcription))
        self._transcription.sort(key=lambda x: x.segment.start)
        
        for segment, track, label in anno.itertracks(yield_label=True):
            if (segment.end - segment.start) <= self.config.audio_postprocess.min_transcription_duration:
                continue
                
            track_exists = False
            for t_segment in self._transcription:
                if (t_segment.segment.start == segment.start and 
                    t_segment.segment.end == segment.end and 
                    t_segment.label == label):
                    track_exists = True
                    break
            
            if not track_exists:
                print('Transcribing:', segment, track, label)
                
                # Extract audio for this segment
                start_idx = int((segment.start - self.config.audio_postprocess.pre_detection_duration) * self._pipeline.config.sample_rate)
                end_idx = int(segment.end * self._pipeline.config.sample_rate)
                
                text = ""
                if end_idx <= self.waveform.shape[0] and (end_idx - start_idx) > 0:
                    # Extract audio segment
                    audio_segment = self.waveform[start_idx:end_idx]
                    
                    text = transcribe_audio_segment(
                        self.whisper,
                        audio_segment,
                        whisper_config=self.config.whisper
                    )
                
                new_segment = TranscribedSegment(
                    segment=segment,
                    label=label,
                    track=track,
                    text=text
                )
                self._transcription.append(new_segment)
    
    def get_transcription(self):
        return list(filter(lambda x: len(x.text.strip()) > 0, self._transcription))