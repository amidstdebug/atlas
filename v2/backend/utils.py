from typing import Tuple

import torch
import torchaudio

def load_audio(
    file_path: str,
    target_sample_rate: int = 16000,
    normalize: bool = True
) -> Tuple[torch.Tensor, int]:
    """Load and preprocess audio file"""
    waveform, sr = torchaudio.load(file_path)
    
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
        
    if sr != target_sample_rate:
        resampler = torchaudio.transforms.Resample(sr, target_sample_rate)
        waveform = resampler(waveform)
        
    if normalize:
        waveform = waveform / (torch.max(torch.abs(waveform)) + 1e-8)
        
    return waveform, target_sample_rate