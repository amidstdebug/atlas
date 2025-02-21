import torch
from silero_vad import load_silero_vad

class SileroVAD:
    sr: int = 16_000
    device: str = 'cpu'
    
    def __init__(
        self,
        threshold: float = 0.5
    ):
        self.model = load_silero_vad()
        self.model = self.model.eval()
        self.threshold: float = threshold
        
    def __call__(self, waveform: torch.Tensor) -> torch.Tensor:
        orig_device = waveform.device
        waveform = waveform.to(self.device)
        
        mask, chunk = get_speech_mask(
            waveform,
            self.model,
            threshold=self.threshold
        )
        
        mask = mask.to(orig_device)
        return mask, chunk

@torch.no_grad()
def get_speech_mask(
    audio: torch.Tensor,
    model,
    threshold: float = 0.5,
    pad: bool = False
) -> torch.Tensor:
    """
    Generate a binary mask indicating speech segments in audio using silero VAD
    with simplified parameters.

    Parameters
    ----------
    audio: torch.Tensor, one dimensional
        One dimensional float torch.Tensor
    model: preloaded .jit/.onnx silero VAD model
    threshold: float (default - 0.5)
        Speech threshold. Probabilities above this value are considered speech.
        
    Returns
    -------
    mask: torch.Tensor
        Binary mask of same shape as input where 1 indicates speech, 0 indicates silence
    chunk: torch.Tensor
        Last chunk
    """
    
    if not torch.is_tensor(audio):
        try:
            audio = torch.Tensor(audio)
        except:
            raise TypeError("Audio cannot be cast to tensor")
    
    audio = audio.squeeze()
    if len(audio.shape) > 1:
        raise ValueError("Audio must be single-channel")
    
    # Fixed sampling rate at 16000
    sampling_rate = 16000
    window_size_samples = 512
    
    # Generate initial probabilities
    mask = torch.zeros_like(audio)
    
    # Get speech probabilities for each window
    for i in range(0, len(audio), window_size_samples):
        chunk = audio[i:i + window_size_samples]
        if len(chunk) < window_size_samples:
            if pad:
                chunk = torch.nn.functional.pad(chunk, (0, window_size_samples - len(chunk)))
            else:
                break
        speech_prob = model(chunk, sampling_rate).item()
        
        if speech_prob >= threshold:
            mask[i:i + window_size_samples] = 1
    
    return mask, chunk