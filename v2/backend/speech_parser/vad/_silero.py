import torch

from silero_vad import load_silero_vad

class SileroVAD:
    sr: int = 16_000
    device: str = 'cpu'
    
    def __init__(self):
        self.model = load_silero_vad()
        # speech mask params
        self.threshold: float = 0.5
        self.min_speech_duration_ms: int = 100
        self.max_speech_duration_s: float = float('inf')
        self.min_silence_duration_ms: int = 50
        self.speech_pad_ms: int = 15
        self.neg_threshold: float = None
        
        # State tracking
        self.prev_end_was_speech: bool = False
        self.speech_start_samples: int = 0
        self.last_speech_end_samples: int = 0
        self.cumulative_samples: int = 0
        
    def __call__(self, waveform: torch.Tensor) -> torch.Tensor:
        orig_device = waveform.device

        waveform = waveform.to(self.device)
        
        mask = get_speech_mask(
            waveform,
            self.model,
            threshold=self.threshold,
            sampling_rate=self.sr,
            min_speech_duration_ms=self.min_speech_duration_ms,
            max_speech_duration_s=self.max_speech_duration_s,
            min_silence_duration_ms=self.min_silence_duration_ms,
            speech_pad_ms=self.speech_pad_ms,
            neg_threshold=self.neg_threshold,
            prev_end_was_speech=self.prev_end_was_speech,
            speech_start_samples=self.speech_start_samples,
            last_speech_end_samples=self.last_speech_end_samples,
            cumulative_samples=self.cumulative_samples
        )
        
        # Update state for next call
        self.prev_end_was_speech = mask[-1].item() == 1
        self.cumulative_samples += len(waveform)
        
        if self.prev_end_was_speech:
            # If we're in speech, keep track of when this speech segment started
            if not mask[0].item() == 1:  # Speech started in this segment
                self.speech_start_samples = self.cumulative_samples - len(waveform) + torch.where(mask == 1)[0][0].item()
        else:
            # If we ended in silence, record where the last speech ended
            speech_indices = torch.where(mask == 1)[0]
            if len(speech_indices) > 0:
                self.last_speech_end_samples = self.cumulative_samples - len(waveform) + speech_indices[-1].item()

        mask = mask.to(orig_device)
        return mask

@torch.no_grad()
def get_speech_mask(
    audio: torch.Tensor,
    model,
    threshold: float = 0.5,
    sampling_rate: int = 16000,
    min_speech_duration_ms: int = 250,
    max_speech_duration_s: float = float('inf'),
    min_silence_duration_ms: int = 100,
    speech_pad_ms: int = 30,
    neg_threshold: float = None,
    prev_end_was_speech: bool = False,
    speech_start_samples: int = 0,
    last_speech_end_samples: int = 0,
    cumulative_samples: int = 0
) -> torch.Tensor:
    """
    Generate a binary mask indicating speech segments in audio using silero VAD

    Parameters
    ----------
    audio: torch.Tensor, one dimensional
        One dimensional float torch.Tensor
    model: preloaded .jit/.onnx silero VAD model
    threshold: float (default - 0.5)
        Speech threshold. Probabilities above this value are considered speech.
    sampling_rate: int (default - 16000)
        Supports 8000 and 16000 (or multiply of 16000) sample rates
    min_speech_duration_ms: int (default - 250 milliseconds)
        Speech segments shorter than this are removed
    max_speech_duration_s: float (default - inf)
        Maximum duration of speech segments in seconds
    min_silence_duration_ms: int (default - 100 milliseconds)
        Required silence duration to end a speech segment
    speech_pad_ms: int (default - 30 milliseconds)
        Padding added to each side of speech segments
    neg_threshold: float (default = threshold - 0.15)
        Values below this are considered non-speech when in speech state
    prev_end_was_speech: bool
        Whether the previous segment ended in speech
    speech_start_samples: int
        Sample position where current speech segment started
    last_speech_end_samples: int
        Sample position where last speech segment ended
    cumulative_samples: int
        Total number of samples processed so far
        
    Returns
    -------
    mask: torch.Tensor
        Binary mask of same shape as input where 1 indicates speech, 0 indicates silence
    """
    
    if not torch.is_tensor(audio):
        try:
            audio = torch.Tensor(audio)
        except:
            raise TypeError("Audio cannot be cast to tensor")
    
    audio = audio.squeeze()
    if len(audio.shape) > 1:
        raise ValueError("Audio must be single-channel")
    
    # Handle sampling rate
    if sampling_rate > 16000 and (sampling_rate % 16000 == 0):
        step = sampling_rate // 16000
        sampling_rate = 16000
        audio = audio[::step]
    else:
        step = 1

    if sampling_rate not in [8000, 16000]:
        raise ValueError("Sampling rate must be 8000 or 16000")

    # Initialize parameters
    window_size_samples = 512 if sampling_rate == 16000 else 256
    neg_threshold = neg_threshold or max(threshold - 0.15, 0.01)
    
    min_speech_samples = int(sampling_rate * min_speech_duration_ms / 1000)
    min_silence_samples = int(sampling_rate * min_silence_duration_ms / 1000)
    speech_pad_samples = int(sampling_rate * speech_pad_ms / 1000)
    
    # Handle infinite max_speech_duration
    if max_speech_duration_s == float('inf'):
        max_speech_samples = len(audio)
    else:
        max_speech_samples = int(sampling_rate * max_speech_duration_s)
    
    # Generate initial probabilities
    mask = torch.zeros_like(audio)
    
    # Get speech probabilities for each window
    for i in range(0, len(audio), window_size_samples):
        chunk = audio[i:i + window_size_samples]
        if len(chunk) < window_size_samples:
            chunk = torch.nn.functional.pad(chunk, (0, window_size_samples - len(chunk)))
        speech_prob = model(chunk, sampling_rate).item()
        
        # Consider prev_end_was_speech for the first window
        if i == 0 and prev_end_was_speech and speech_prob >= neg_threshold:
            mask[i:i + window_size_samples] = 1
        elif speech_prob >= threshold:
            mask[i:i + window_size_samples] = 1
    
    # Apply minimum speech duration, considering previous state
    if prev_end_was_speech:
        current_speech_duration = cumulative_samples - speech_start_samples
        # Only apply min_speech if we're transitioning to silence
        if mask[0].item() == 0 and current_speech_duration < min_speech_samples:
            # Force beginning to be speech until we meet minimum duration
            samples_needed = min_speech_samples - current_speech_duration
            mask[:min(samples_needed, len(mask))] = 1
    
    mask = remove_short_segments(mask, min_speech_samples, value=1)
    
    # Apply minimum silence duration, considering previous state
    if not prev_end_was_speech and mask[0].item() == 1:
        silence_duration = cumulative_samples - last_speech_end_samples
        if silence_duration < min_silence_samples:
            # Continue silence until minimum is met
            samples_needed = min_silence_samples - silence_duration
            mask[:min(samples_needed, len(mask))] = 0
    
    mask = remove_short_segments(mask, min_silence_samples, value=0)
    
    # Apply maximum speech duration
    if max_speech_duration_s < float('inf'):
        if prev_end_was_speech:
            current_speech_duration = cumulative_samples - speech_start_samples
            if current_speech_duration > max_speech_samples:
                mask = split_long_segments(mask, max_speech_samples, min_silence_samples)
        else:
            mask = split_long_segments(mask, max_speech_samples, min_silence_samples)
    
    # Add padding to speech segments, being careful at boundaries
    mask = pad_speech_segments(mask, speech_pad_samples)
    
    # Restore original sampling rate if needed
    if step > 1:
        mask = mask.repeat_interleave(step)
        mask = mask[:len(audio)]
    
    return mask

def remove_short_segments(mask: torch.Tensor, min_length: int, value: int) -> torch.Tensor:
    """Remove segments shorter than min_length samples"""
    mask = mask.clone()
    segments = torch.where(mask[1:] != mask[:-1])[0] + 1
    segments = torch.cat([torch.tensor([0]), segments, torch.tensor([len(mask)])])

    for i in range(len(segments) - 1):
        if mask[segments[i]] == value and (segments[i+1] - segments[i]) < min_length:
            mask[segments[i]:segments[i+1]] = 1 - value

    return mask
def split_long_segments(mask: torch.Tensor, max_length: int, min_silence: int) -> torch.Tensor:
    """Split segments longer than max_length samples"""
    mask = mask.clone()
    segments = torch.where(mask[1:] != mask[:-1])[0] + 1
    segments = torch.cat([torch.tensor([0]), segments, torch.tensor([len(mask)])])

    for i in range(len(segments) - 1):
        if mask[segments[i]] == 1 and (segments[i+1] - segments[i]) > max_length:
            # Try to find a natural silence point
            segment = mask[segments[i]:segments[i+1]]
            potential_splits = torch.where(segment == 0)[0]

            if len(potential_splits) > 0 and potential_splits[-1] > min_silence:
                split_point = segments[i] + potential_splits[-1]
            else:
                split_point = segments[i] + max_length

            mask[split_point:segments[i+1]] = 0

    return mask
def pad_speech_segments(mask: torch.Tensor, pad_samples: int) -> torch.Tensor:
    """Add padding to speech segments"""
    mask = mask.clone()
    segments = torch.where(mask[1:] != mask[:-1])[0] + 1
    segments = torch.cat([torch.tensor([0]), segments, torch.tensor([len(mask)])])

    for i in range(len(segments) - 1):
        if mask[segments[i]] == 1:
            start = max(0, segments[i] - pad_samples)
            end = min(len(mask), segments[i+1] + pad_samples)
            mask[start:end] = 1

    return mask