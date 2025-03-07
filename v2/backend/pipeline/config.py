from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "FasterWhisperTranscribeConfig",
    "AudioPreprocessingConfig",
    "AudioPostprocessingConfig",
    "OnlinePipelineConfig",
    "DEFAULT_FASTER_WHISPER_TRANSCRIBE_CONFIG"
]

@dataclass
class FasterWhisperTranscribeConfig:
    beam_size: int = 10
    best_of: int = 10
    condition_on_previous_text: bool = False
    language: str = "en"

@dataclass
class AudioPreprocessingConfig:
    audio_gain: float = 10.0
    audio_gain_mode: str = "db" # one of ["amplitude", "db"]
    normalize_audio: bool = False  # Whether to normalize audio (center and scale)
    high_pass_filter: bool = True  # Whether to apply high-pass filter to remove low-frequency noise
    high_pass_cutoff: float = 80.0  # Cutoff frequency for high-pass filter in Hz

@dataclass
class AudioPostprocessingConfig:
    collar: float = 0.5
    min_transcription_duration: float = 1.0
    pre_detection_duration: float = 0.1

DEFAULT_FASTER_WHISPER_TRANSCRIBE_CONFIG = FasterWhisperTranscribeConfig()

@dataclass
class OnlinePipelineConfig:
    segmentation_model_name: str = "pyannote/segmentation-3.0"
    embedding_model_name: str = "speechbrain/spkrec-ecapa-voxceleb"
    whisper_type: str = "faster-whisper"  # one of ['faster-whisper']
    whisper_model: str = "large-v3" # "aether-raid/WLV3t-SG-LN-NoAugs-ct2" # "large-v3"  # Model size (tiny, base, small, medium, large, large-v3, distil-large-v3)
    hf_token: Optional[str] = None
    
    whisper: FasterWhisperTranscribeConfig = field(default_factory=lambda: FasterWhisperTranscribeConfig())
    audio_preprocess: AudioPreprocessingConfig = field(default_factory=lambda: AudioPreprocessingConfig())
    audio_postprocess: AudioPostprocessingConfig = field(default_factory=lambda: AudioPostprocessingConfig())