import os
from dotenv import load_dotenv

from dataclasses import dataclass
from typing import Optional

import numpy as np
from pyannote.core import SlidingWindow, SlidingWindowFeature, Annotation, Timeline, Segment

from diart.models import EmbeddingModel, SegmentationModel
from diart import SpeakerDiarization, SpeakerDiarizationConfig

@dataclass
class OnlinePipelineConfig:
    segmentation_model_name: str = "pyannote/segmentation-3.0"
    embedding_model_name: str = "nvidia/speakerverification_en_titanet_large"
    collar: float = 0.25
    hf_token: Optional[str] = None

class OnlinePipeline:
    def __init__(self, config: PipelineConfig):
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
        self.duration = self.pipeline.config.duration * self.pipeline.config.sample_rate
        self.step = self.pipeline.config.step * self.pipeline.config.sample_rate

        self.waveform: Optional[np.ndarray] = None
        self.last_processed_start_time: int = 0 # adjusted by sample_rate
        self._annotation = Annotation()

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
            if 'cuda' in waveform.device:
                waveform = waveform.detach().cpu()            
            waveform = waveform.numpy()

        if len(waveform.shape) != 2:
            raise ValueError(f'input waveform of shape {waveform.shape} should be of shape (length, channel)')
            
        self.waveform = np.concatenate((self.waveform, waveform))

        while self.waveform.shape[0] > (self.last_processed_start_time + self.duration):
            audio = self.waveform[self.last_processed_start_time:self.last_processed_start_time+self.duration]
            
            sliding_window = SlidingWindow(
                start=self.last_processed_start_time/self.config.sample_rate,
                duration=1.0 / self.config.sample_rate,
                step=1.0 / self.config.sample_rate,
            )
            
            audio = SlidingWindowFeature(audio, sliding_window)
            annotation, _ = self.pipeline([audio])[0]
            self._annotation.update(annotation)
            
            self.last_processed_start_time += self.duration

        return self.get_annotation()