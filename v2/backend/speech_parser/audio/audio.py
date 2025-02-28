from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Iterator, Any

import torch

from .segment import Segment, BaseScaleSegment, ScaleSegment, SegmentBatch, SpeakerSegment, get_segments, merge_segments

class Audio:
    def __init__(
        self, 
        scales: List[float]=[1.5, 1.25, 1.0, 0.75, 0.5], 
        hops: List[float]=[1.5/4, 1.25/4, 1.0/4, 0.75/4, 0.5/4], 
        base_scale: float=0.5, 
        sampling_rate: int=16_000,
        batch_size: int=128,
        waveform: Optional[torch.Tensor]=None
    ):
        self.device = 'cpu'  # Default device, will be overridden by pipeline
        self.idle_device = 'cpu'
        
        # Initialize parameters for multi-scale segmentation
        self.scales = scales
        self.hops = hops
        self._scale_hops = {scale: hop for scale, hop in zip(scales, hops)}
        self.base_scale = base_scale
        self.segment_scales: Dict[float, ScaleSegment] = {}
        
        self.sampling_rate = sampling_rate
        self.batch_size = batch_size

        # Merging segments state
        self._active_speakers: Dict[Any, List[Segment]] = {}
        self.merged_segments: List[SpeakerSegment] = []
        self._merged_segments_idx: int = 0

        # VAD state
        self._unprocessed_chunk: Optional[torch.Tensor] = None
        self.voice_activity_mask: Optional[torch.Tensor] = None  # 1 for speech, 0 for non-speech

        # Track indices for processing segments at different scales
        self.base_scale_idx = 0
        self.other_scales = [s for s in self.scales if s != self.base_scale]
        self.other_scale_segment_idx = {scale: 0 for scale in self.other_scales}
        
        # Initialize waveform
        self.waveform = torch.tensor([]) if waveform is None else waveform
        self.waveform = self.waveform.to(device=self.idle_device, dtype=torch.float32)
        self.voice_activity_mask = torch.tensor([], device=self.idle_device, dtype=torch.float32)

    @property
    def base_scale_segments(self) -> Optional[ScaleSegment]:
        """Get segments at the base scale."""
        return self.segment_scales.get(self.base_scale)
        
    def assign_segments(self) -> None:
        """Link segments across different temporal scales."""
        for self.base_scale_idx, segment in enumerate(self.base_scale_segments.unassigned_segments):
            segment.other_scale_segments = {}
            for scale, other_segment_idx in self.other_scale_segment_idx.items():
                other_scale = self.segment_scales[scale]

                # Stop if we've processed all segments at this scale
                if other_segment_idx == len(other_scale):
                    segment.other_scale_segments = None
                    break

                other_scale_segment = other_scale[other_segment_idx]
                boundary_to_next = other_scale_segment.center + (self._scale_hops[scale] / 2)
                
                if segment.center < boundary_to_next:
                    # Current segment falls within the other scale segment
                    segment.other_scale_segments[scale] = other_scale_segment
                else:
                    # Move to next segment at other scale
                    next_other_segment_idx = other_segment_idx + 1
                    if next_other_segment_idx == len(other_scale):
                        segment.other_scale_segments = None
                        break
                        
                    segment.other_scale_segments[scale] = self.segment_scales[scale][next_other_segment_idx]
                    self.other_scale_segment_idx[scale] = next_other_segment_idx

    def clear_merged_segments(self) -> None:
        """Reset all merged segment data."""
        self._active_speakers = {}
        self.merged_segments = []
        self._merged_segments_idx = 0

    def get_all_embeds(self) -> torch.Tensor:
        """Collect all speaker embeddings from base scale segments."""
        out_arr = []
        for segment in self.base_scale_segments:
            if segment.has_tensor:
                out_arr.append(segment.tensor)
        return torch.stack(out_arr)

    def populate_segment_scales(self) -> List[Segment]:
        """
        Create segments at all temporal scales for new audio data.
        
        Returns:
            List[Segment]: New segments at the base scale
        """
        orig_num_base_segments = len(self.segment_scales.get(self.base_scale, []))
        for scale, hop in zip(self.scales, self.hops):
            if self.segment_scales.get(scale) is None:
                self.segment_scales[scale] = ScaleSegment(scale, [])
                
            last_segment_time = self.segment_scales[scale].last_segment_time
            # Use different segment class for base scale vs other scales
            segment_class = BaseScaleSegment if scale == self.base_scale else Segment
            
            segments = get_segments(
                self.waveform,
                self.voice_activity_mask,
                self.sampling_rate, 
                scale, 
                hop, 
                segment_class=segment_class, 
                start_time=last_segment_time
            )
        
            self.segment_scales[scale].extend(segments)

        # Update segment relationships
        self.assign_segments()
        return self.base_scale_segments[orig_num_base_segments:]