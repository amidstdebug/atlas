from typing import Sequence, Optional
import re
import logging

import numpy as np
import torch

from faster_whisper import WhisperModel
# from faster_whisper.utils import _MODELS

import huggingface_hub

from .config import FasterWhisperTranscribeConfig, DEFAULT_FASTER_WHISPER_TRANSCRIBE_CONFIG
from .segments import TranscribedSegment

_MODELS = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "tiny": "Systran/faster-whisper-tiny",
    "base.en": "Systran/faster-whisper-base.en",
    "base": "Systran/faster-whisper-base",
    "small.en": "Systran/faster-whisper-small.en",
    "small": "Systran/faster-whisper-small",
    "medium.en": "Systran/faster-whisper-medium.en",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

def download_model(
    size_or_id: str,
    output_dir: Optional[str] = None,
    local_files_only: bool = False,
    cache_dir: Optional[str] = None,
    token: Optional[str] = None,
):
    """Downloads a CTranslate2 Whisper model from the Hugging Face Hub.
    Args:
      size_or_id: Size of the model to download from https://huggingface.co/Systran
        (tiny, tiny.en, base, base.en, small, small.en, distil-small.en, medium, medium.en,
        distil-medium.en, large-v1, large-v2, large-v3, large, distil-large-v2,
        distil-large-v3), or a CTranslate2-converted model ID from the Hugging Face Hub
        (e.g. Systran/faster-whisper-large-v3).
      output_dir: Directory where the model should be saved. If not set, the model is saved in
        the cache directory.
      local_files_only: If True, avoid downloading the file and return the path to the local
        cached file if it exists.
      cache_dir: Path to the folder where cached files are stored.
      token: Hugging Face token to use for authentication when downloading from private repositories.
    Returns:
      The path to the downloaded model.
    Raises:
      ValueError: if the model size is invalid or if local_files_only=True and model isn't in cache.
    """
    # Setup logger
    logger = logging.getLogger(__name__)

    # Define disabled_tqdm for progress display
    try:
        from tqdm.auto import tqdm as disabled_tqdm
    except ImportError:
        class disabled_tqdm:
            def __init__(self, iterable=None, **kwargs):
                self.iterable = iterable
            def __iter__(self):
                return iter(self.iterable)
            def __enter__(self):
                return self
            def __exit__(self, *args, **kwargs):
                pass

    # Determine repo ID from model size or direct input
    if re.match(r".*/.*", size_or_id):
        repo_id = size_or_id
    else:
        repo_id = _MODELS.get(size_or_id)
        if repo_id is None:
            raise ValueError(
                "Invalid model size '%s', expected one of: %s"
                % (size_or_id, ", ".join(_MODELS.keys()))
            )

    # Files to look for
    allow_patterns = [
        "config.json",
        "preprocessor_config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.*",
    ]

    # Prepare download arguments
    kwargs = {
        "allow_patterns": allow_patterns,
        "tqdm_class": disabled_tqdm,
    }

    if output_dir is not None:
        kwargs["local_dir"] = output_dir
        kwargs["local_dir_use_symlinks"] = False
    if cache_dir is not None:
        kwargs["cache_dir"] = cache_dir
    if token is not None:
        kwargs["token"] = token

    # First check if model is in cache
    try:
        # Try to load the model with local_files_only=True
        logger.info(f"Checking if model {repo_id} is in cache")
        model_path = huggingface_hub.snapshot_download(
            repo_id,
            local_files_only=True,
            **kwargs
        )
        logger.info(f"Model {repo_id} found in cache at {model_path}")
        return model_path
    except Exception as e:
        # Model not in cache
        logger.info(f"Model {repo_id} not found in cache: {e}")

        if local_files_only:
            # If local_files_only is True, we raise an error
            err_msg = f"Model {repo_id} not found in cache and local_files_only=True"
            logger.error(err_msg)
            raise ValueError(err_msg)
        else:
            # Otherwise, download the model
            logger.info(f"Downloading model {repo_id}")
            try:
                model_path = huggingface_hub.snapshot_download(
                    repo_id,
                    local_files_only=False,
                    **kwargs
                )
                logger.info(f"Model {repo_id} downloaded to {model_path}")
                return model_path
            except Exception as download_error:
                err_msg = f"Failed to download model {repo_id}: {download_error}"
                logger.error(err_msg)
                raise ValueError(err_msg)

def initialize_whisper_model(
    model_name: str = "small",
    cache_dir: Optional[str] = None,
    token: Optional[str] = None,
    output_dir: Optional[str] = None,
    local_files_only: bool = False,
) -> WhisperModel:
    """
    Initialize a faster-whisper model with appropriate settings.

    Args:
        model_name: Size of the Whisper model (tiny, base, small, medium, large)
        cache_dir: Path to the folder where cached models are stored
        token: Hugging Face token for downloading models
        output_dir: Directory where the model should be saved
        local_files_only: If True, only use local files

    Returns:
        WhisperModel instance
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "float32"

    # Get model path (from cache or download)
    try:
        model_path = download_model(
            model_name,
            output_dir=output_dir,
            local_files_only=local_files_only,
            cache_dir=cache_dir,
            token=token
        )

        # Initialize and return the model
        return WhisperModel(
            model_path,
            device=device,
            compute_type=compute_type,
        )
    except ValueError as e:
        # If model not found in cache with local_files_only=True, but it's a standard model,
        # let WhisperModel handle it (which will fail if it's not already downloaded)
        if "not found in cache and local_files_only=True" in str(e):
            logging.warning(f"Model {model_name} not found in cache, using model name directly")
            return WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                local_files_only=local_files_only,
                download_root=cache_dir,
            )
        else:
            # Re-raise other errors
            raise

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
