import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from transformers import AutoProcessor, WhisperForConditionalGeneration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for model and processor
asr_model = None
asr_processor = None

def load_whisper_pipeline():
    """
    Load Whisper model and processor once.
    Uses openai/whisper-large-v3-turbo by default, controllable via WHISPER_MODEL_ID.
    This version is compatible with transformers < 4.37.0
    """
    global asr_model, asr_processor
    if asr_model is not None and asr_processor is not None:
        return asr_model

    try:
        if torch.cuda.is_available():
            device = "cuda"
            torch_dtype = torch.float16
            logger.info(f"CUDA is available. Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            device = "cpu"
            torch_dtype = torch.float32
            logger.info("CUDA is not available. Using CPU.")

        model_name = os.getenv("WHISPER_MODEL_ID", "openai/whisper-large-v3-turbo")
        logger.info(f"Loading Whisper model: {model_name}")

        # Load processor and model (without attn_implementation for older transformers)
        asr_processor = AutoProcessor.from_pretrained(model_name)
        asr_model = WhisperForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map="auto" if device == "cuda" else None,
        )
        if device == "cuda":
            asr_model.to(device)

        # Quick sanity check using 0.1 s of silence
        silence = np.zeros(int(16000 * 0.1), dtype=np.float32)
        feats = asr_processor(silence, sampling_rate=16000, return_tensors="pt").input_features
        feats = feats.to(device, dtype=torch_dtype)
        _ = asr_model.generate(feats, max_new_tokens=1)

        logger.info("Whisper model and processor loaded successfully")
        return asr_model

    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        asr_model = None
        asr_processor = None
        raise 