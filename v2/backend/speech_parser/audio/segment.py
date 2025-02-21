from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Iterator, Any

import torch

@dataclass
class Segment:
    """Represents a segment with its temporal boundaries and center"""
    start: float  # Start time in seconds
    end: float    # End time in seconds
    data: torch.Tensor # waveform data
    mask: torch.Tensor # VAD mask
    scale: int
    embed: Optional[torch.Tensor] = None
    is_base_scale: bool = False

    def __init__(
        self,
        start: float,
        end: float,
        data: torch.Tensor,
        mask: torch.Tensor,
        scale: int,
        embed: Optional[torch.Tensor] = None,
    ): 
        self.start = start
        self.end = end
        self.data = data
        self.mask = mask
        self.scale = scale
        self.embed = embed

        self.unk_speaker = True
        
        self.speakers: List[Any] = []
    
    @property
    def center(self) -> float:
        """Get center point of segment in seconds"""
        return (self.start + self.end) / 2

    @property
    def timestamp(self) -> Tuple[float, float]:
        return self.start, self.end

    @property
    def has_embed(self) -> bool:
        return self.embed is not None

    def add_speaker(self, speaker: Any) -> None:
        if self.speakers is None or self.unk_speaker:
            self.unk_speaker = False
            self.speakers = []
        self.speakers.append(speaker)

    def set_unk_speaker(self) -> None:
        self.unk_speaker = True
        self.speakers = ['?']
        
    def __hash__(self):
        return hash(f'{self.start}-{self.end}')
    
    def __eq__(self, other):
        # Two items are equal if they have the same id
        if not isinstance(other, Segment):
            return False
        return hash(self) == hash(other)

@dataclass
class BaseScaleSegment(Segment):
    is_base_scale: bool = True
    other_scale_segments: Optional[Dict[float, Segment]] = None # Only used in base scale

    def __init__(
        self,
        start: float,
        end: float,
        data: torch.Tensor,
        mask: torch.Tensor,
        scale: int,
        embed: Optional[torch.Tensor] = None
    ):
        super().__init__(
            start=start,
            end=end,
            data=data,
            mask=mask,
            scale=scale,
            embed=embed,
        )

    @property
    def tensor(self) -> torch.Tensor:
        scales = list(self.other_scale_segments.keys())
        # scales.sort(reverse=True)
        ordered_segments = [self.other_scale_segments[scale].embed for scale in scales] + [self.embed]
        if None in ordered_segments:
            print(ordered_segments)
        return torch.stack(ordered_segments)

    @property
    def has_tensor(self) -> bool:
        return self.other_scale_segments is not None and len(self.other_scale_segments) != 0 and self.embed is not None
        
    @property
    def has_speech(self) -> bool:
        return bool(torch.any(self.mask != 0).cpu().detach())
    
@dataclass
class ScaleSegment:
    scale: float
    segments: List[Segment]
    device: str

    @property
    def last_segment_time(self) -> float:
        if len(self.segments) == 0:
            return 0
        return self.segments[-1].end

    @property
    def tensor(self) -> torch.Tensor:
        return torch.stack([segment.embed for segment in self.segments if segment.has_embed])

    @property
    def timestamps(self) -> List[Tuple[float, float]]:
        return [segment.timestamp for segment in self.segments if segment.has_embed]

    def extend(self, segments):
        self.segments.extend(segments)

    @property
    def unassigned_segments(self):
        return [segment for segment in self.segments if segment.other_scale_segments is None]
        
    def __getitem__(self, idx: int) -> torch.Tensor:
        return self.segments[idx]

    def __len__(self) -> int:
        return len(self.segments)

def get_segments(
    waveform: torch.Tensor,
    voice_activity_mask: torch.Tensor,
    sample_rate: int,
    scale: float,
    hop_length: float,
    start_time: float = 0.0,
    segment_class = Segment 
) -> List[Segment]:
    """
    Generate segments for a specific scale
    
    Args:
        waveform: Input audio tensor [T * 16000]
        sample_rate: Audio sample rate
        scale: Scale factor in seconds * sample rate (e.g., 16000, 8000)
        hop_length: Hop length in seconds * sample rate
        
    Returns:
        List of Segment objects for this scale
    """
    duration = waveform.shape[-1] / sample_rate
    segment_samples = int(scale * sample_rate)
    hop_samples = int(hop_length * sample_rate)
    
    segments = []
    current_time = start_time
    
    while current_time < duration:
        start_time = current_time
        end_time = start_time + scale
        
        # Convert time to samples for extraction
        start_idx = int(start_time * sample_rate)
        end_idx = start_idx + segment_samples
        
        if end_idx > waveform.shape[0]:
            break
            
        segment_data = waveform[start_idx:end_idx]
        segment_vad_data = voice_activity_mask[start_idx:end_idx]
        
        segment = segment_class(start_time, end_time, segment_data, segment_vad_data, scale)
        segments.append(segment)
        
        current_time += hop_length
        
    return segments

@dataclass 
class SegmentBatch:
    segments: List[Segment]
    
    @property
    def tensor(self) -> torch.Tensor:
        return torch.stack([a.data for a in self.segments])

    def update_embeds(self, embeds: torch.Tensor):
        for i, s in enumerate(self.segments):
            # store on cpu
            s.embed = embeds[i].to('cpu')

def get_segment_batches(segment_scale: ScaleSegment, batch_size: int) -> Iterator[List[Segment]]:
    """
    Generate batches of segments where embed is None from a ScaleSegment object.
    
    Args:
        segment_scale: ScaleSegment object containing segments to process
        batch_size: Number of segments to include in each batch
        
    Yields:
        List[Segment]: Batch of segments with None embeds, up to batch_size in length
    """
    current_batch = []
    
    for segment in segment_scale.segments:
        # Skip segments that are base scale but don't have speech
        if segment.is_base_scale and not segment.has_speech:
            continue
            
        if segment.embed is None:
            segment.data = segment.data.to(segment_scale.device)
            current_batch.append(segment)
            
            if len(current_batch) >= batch_size:
                yield SegmentBatch(current_batch)
                current_batch = []
    
    # Only yield the final batch if it's not empty
    if current_batch:
        yield SegmentBatch(current_batch)

@dataclass
class SpeakerSegment:
    """Represents a continuous segment of speech for a single speaker"""
    start: float  # Start time in seconds
    end: float    # End time in seconds
    data: torch.Tensor # waveform data
    mask: torch.Tensor # VAD mask
    speaker: Any
    transcription: str = None

    def __init__(
        self,
        start: float,
        end: float,
        data: torch.Tensor,
        mask: torch.Tensor,
        speaker: int
    ): 
        self.start = start
        self.end = end
        self.data = data
        self.mask = mask
        self.speaker = speaker

    @property
    def duration(self) -> float:
        return self.end-self.start

    @property
    def center(self) -> float:
        """Get center point of segment in seconds"""
        return (self.start + self.end) / 2
        
    def __hash__(self):
        return hash(f'{self.start}-{self.end}, {self.speaker}')
    
    def __eq__(self, other):
        # Two items are equal if they have the same id
        if not isinstance(other, Segment):
            return False
        return hash(self) == hash(other)
    
def merge_segments(segments, speaker, sampling_rate=16000):
    
    first_segment = segments[0]
    start = first_segment.start
    end = first_segment.start
    normal_segment_duration = first_segment.end - first_segment.start
    waveforms = []
    vad_masks = []
    
    for segment in segments:
        increment = segment.end - end
        assert increment <= normal_segment_duration, f"Issue in the matching section of get_merged_speaker_segments(), {increment} > {normal_segment_duration}"

        concat_length = int(increment*sampling_rate)
        waveforms.append(segment.data[-concat_length:])
        vad_masks.append(segment.mask[-concat_length:])
        
        end = segment.end
        
    waveform = torch.cat(waveforms)
    vad_mask = torch.cat(vad_masks)

    return SpeakerSegment(start, end, waveform, vad_mask, speaker)