import os
import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import logging

logger = logging.getLogger(__name__)

def load_whisper_model(model_path):
    """
    Load Whisper model from the given path or HuggingFace model name.
    
    Args:
        model_path: Path to the model directory or HuggingFace model name
        
    Returns:
        tuple: (processor, model, device)
    """
    try:
        # Set up device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {device}")
        
        # Check if model_path exists
        if os.path.exists(model_path):
            logger.info(f"Loading model from local path: {model_path}")
        else:
            # If model_path doesn't exist locally, try to download from HuggingFace
            logger.info(f"Model not found locally. Trying to download from HuggingFace: {model_path}")
            
            # Fallback to a default model if neither exists
            if not os.path.exists(model_path):
                logger.warning(f"Local model not found. Using jlvdoorn/whisper-medium.en-atco2-asr as fallback")
                model_path = "jlvdoorn/whisper-medium.en-atco2-asr"
        
        # Load the processor and model
        processor = WhisperProcessor.from_pretrained(model_path)
        model = WhisperForConditionalGeneration.from_pretrained(model_path)
        
        # Move model to the appropriate device
        model = model.to(device)
        
        logger.info("Model loaded successfully")
        
        return processor, model, device
        
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        raise

# canary_transcriber.py
from nemo.collections.asr.models import EncDecMultiTaskModel

class CanaryTranscriber:
    def __init__(self, model_name: str = 'nvidia/canary-1b'):
        # Load the Canary ASR model from NeMo pretrained models.
        self.model = EncDecMultiTaskModel.from_pretrained(model_name)
        # Update the decoding configuration (beam size etc)
        decode_cfg = self.model.cfg.decoding
        decode_cfg.beam.beam_size = 1
        self.model.change_decoding_strategy(decode_cfg)
        self.model.eval()

    def transcribe(self, audio_filepath: str) -> str:
        """
        Transcribes the given audio file.
        Returns a single string (the transcription).
        """
        result = self.model.transcribe(audio_filepath)
        # In our example, the model returns a list of hypotheses.
        if isinstance(result, list):
            return result[0]
        return result