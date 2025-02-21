from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Iterator

import torch
from nemo.collections.asr.models.label_models import EncDecSpeakerLabelModel

from .segment import Segment, BaseScaleSegment, ScaleSegment, SegmentBatch, SpeakerSegment, get_segments, get_segment_batches, merge_segments
from ..clustering.online_clustering import OnlineSpeakerClustering
from ..msdd import MSDD
from ..vad import SileroVAD

@dataclass
class Audio:
    base_scale: float
    scales: List[float]
    hops: List[float]
    sampling_rate: int = 16_000
    device: str = 'cuda'
    waveform: Optional[torch.Tensor] = None
    voice_activity_mask: Optional[torch.Tensor] = None # 1 for speech, 0 for non-speech
    segment_scales: Optional[Dict[float, ScaleSegment]] = None

    def __init__(
        self, 
        scales: List[float], 
        hops: List[float], 
        base_scale: float=0.5, 
        sampling_rate: int=16_000,
        batch_size: int=128,
        speech_embedding_model: EncDecSpeakerLabelModel=None,
        voice_activity_detection_model: SileroVAD=None,
        multi_scale_diarization_model: MSDD=None,
        speaker_clustering=None,
        waveform=None
    ):
        self.idle_device = 'cpu'
        
        # Initialize models and parameters for multi-scale diarization
        self.scales = scales
        self.hops = hops
        self.scale_hops = {scale: hop for scale, hop in zip(scales, hops)}
        self.base_scale = base_scale
        self.segment_scales = {}
        
        self.sampling_rate = sampling_rate
        self.batch_size = batch_size

        # Tunables
        self.min_segments_for_clustering: int = 100
        self.min_speaker_segment_duration: float = 1.0
        self.max_silence_per_segment_pct: float = 0.5

        # Merging segments
        self._active_speakers: Dict[Any, List[Segment]] = {}
        self.merged_segments: List[SpeakerSegment] = []
        self._merged_segments_idx: int = 0

        # Clustering state
        self._clustering_start = False

        # VAD state
        self._unprocessed_chunk: Optional[torch.Tensor] = None

        # Models
        self.speech_embedding_model = speech_embedding_model
        self.speech_embedding_model.freeze() # Freeze model weights for inference
        self.voice_activity_detection_model = voice_activity_detection_model
        self.multi_scale_diarization_model = multi_scale_diarization_model
        self.speaker_clustering = speaker_clustering

        # Track indices for processing segments at different scales
        self.base_scale_idx = 0
        self.other_scales = [s for s in self.scales if s != self.base_scale]
        self.other_scale_segment_idx = {scale: 0 for scale in self.other_scales}
        
        # Initialize waveform and process if provided
        self.waveform = torch.tensor([]) if waveform is None else waveform
        self.waveform = self.waveform.to(device=self.idle_device, dtype=torch.float32)
        if waveform is not None:
            self.voice_activity_mask = self.voice_activity_detection_model(self.waveform)
            self.populate_segment_scales()
            self.assign_segments()
        else:
            self.voice_activity_mask = torch.tensor([], device=self.idle_device, dtype=torch.float32)

    def __call__(self, waveform: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # Process new audio input and perform diarization
        new_segments = self.append_waveform(waveform)

        empty_returns = torch.tensor([], device=self.idle_device), torch.tensor([], device=self.idle_device)

        # Collect embeddings from new segments
        segments_to_update = []
        for segment in new_segments:
            if segment.has_tensor:
                segments_to_update.append(segment)
        if len(segments_to_update) == 0:
            return empty_returns

        # Hold a certain number of segments in buffer before starting to cluster to prevent inaccurate issues
        if not self._clustering_start:
            if len(self.base_scale_segments) > self.min_segments_for_clustering:
                self._clustering_start = True
                self.clear_merged_segments()
                segments_to_update = self.base_scale_segments.segments_with_tensors
                
        if self._clustering_start:
            new_ms_emb_seq = torch.stack([segment.tensor for segment in segments_to_update])
            
            # Perform speaker clustering and get updated centroids
            new_label_seq = self.speaker_clustering(new_ms_emb_seq)
            centroids = self.speaker_clustering.get_centroids()
    
            # Prepare inputs for multi-scale diarization model
            new_ms_emb_seq = new_ms_emb_seq.unsqueeze(0)
            new_label_seq = new_label_seq.unsqueeze(0)
            ms_avg_embs = torch.stack([centroids[spk_idx] for spk_idx in sorted(list(centroids.keys()))]).permute(1, 2, 0).unsqueeze(0)
            
            # Move tensors to appropriate device
            new_ms_emb_seq = new_ms_emb_seq.to(self.device)
            new_label_seq = new_label_seq.to(self.device)
            ms_avg_embs = ms_avg_embs.to(self.device)
            
            # Get diarization probabilities and logits
            proba, labels = self.multi_scale_diarization_model(new_ms_emb_seq, new_label_seq, ms_avg_embs)
            proba = proba.to(self.idle_device)
            labels = labels.to(self.idle_device)
    
            for spk_idx in range(labels.shape[0]):
                for i, segment in enumerate(segments_to_update):
                    if labels[spk_idx, i] == 1:
                        segment.add_speaker(spk_idx)
                        
            return proba, labels
        else:
            for segment in segments_to_update:
                segment.set_unk_speaker()
            return empty_returns

    @property
    def base_scale_segments(self) -> Optional[ScaleSegment]:
        return self.segment_scales.get(self.base_scale)
        
    def embed(self) -> None:
        # Generate speaker embeddings for all segments in batches
        for scale, segment_scale in self.segment_scales.items():        
            batch_loader = get_segment_batches(segment_scale, self.batch_size)
            for batch in batch_loader:
                with torch.no_grad():
                    audio_signal = batch.tensor.to(device=self.device, dtype=torch.float32)
                    audio_signal_lens = torch.tensor([audio_signal.shape[-1]] * audio_signal.shape[0], device=self.device)
                    _, embeds = self.speech_embedding_model.forward(input_signal=audio_signal, input_signal_length=audio_signal_lens)
                embeds = embeds.to(self.idle_device)
                batch.update_embeds(embeds)

    def assign_segments(self) -> None:
        # Link segments across different temporal scales
        # This allows the model to consider relationships between segments at different time resolutions
        for self.base_scale_idx, segment in enumerate(self.base_scale_segments.unassigned_segments):
            segment.other_scale_segments = {}
            for scale, other_segment_idx in self.other_scale_segment_idx.items():
                other_scale = self.segment_scales[scale]

                # Stop if we've processed all segments at this scale
                if other_segment_idx == len(other_scale):
                    segment.other_scale_segments = None
                    break

                other_scale_segment = other_scale[other_segment_idx]
                boundary_to_next = other_scale_segment.center + (self.scale_hops[scale] / 2)
                
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
        self._active_speakers = {}
        self.merged_segments = []
        self._merged_segments_idx = 0
        
    def get_merged_speaker_segments(self, use_cache: bool = False) -> List[SpeakerSegment]:  
        if not use_cache:
            self.clear_merged_segments()
        for curr_merged_idx, segment in enumerate(self.base_scale_segments[self._merged_segments_idx:]):
            curr_active_speakers = list(self._active_speakers.items())
            
            for speaker, active_segments in curr_active_speakers:
                
                # end the speaker segment if the start of the new segment is past the end of the old
                if (speaker in segment.speakers) and (segment.start <= active_segments[-1].end):
                    self._active_speakers[speaker].append(segment)
                elif segment.start > active_segments[-1].end:
                    # merge and end speakers
                    speaker_segment = merge_segments(
                        active_segments, 
                        speaker, 
                        sampling_rate=self.sampling_rate
                    )
                    self.merged_segments.append(speaker_segment)
                    self._active_speakers.pop(speaker)
                
            for speaker in segment.speakers:
                if speaker not in self._active_speakers:
                    # start speaker
                    self._active_speakers[speaker] = [segment]
                    
        self._merged_segments_idx += curr_merged_idx

        # filters
        filtered_segments = []
        for segment in self.merged_segments:
            if (segment.mask.sum()/segment.mask.shape[0]) < self.max_silence_per_segment_pct:
                continue
            if segment.duration <= self.min_speaker_segment_duration:
                continue
            filtered_segments.append(segment)

        return filtered_segments

    def get_all_embeds(self) -> torch.Tensor:
        # Collect all speaker embeddings from base scale segments
        out_arr = []
        for segment in self.base_scale_segments:
            if segment.has_tensor:
                out_arr.append(segment.tensor)
        return torch.stack(out_arr)

    def append_waveform(self, waveform) -> List[Segment]:
        # Add new audio data and update voice activity detection mask
        waveform = waveform.to(device=self.idle_device, dtype=torch.float32)
        if self._unprocessed_chunk is not None:
            waveform = torch.cat([self._unprocessed_chunk, waveform])
        vad_mask, self._unprocessed_chunk = self.voice_activity_detection_model(waveform)

        if self._unprocessed_chunk is not None:
            unprocessed_length = self._unprocessed_chunk.shape[0]
        else:
            unprocessed_length = 1
        self.waveform = torch.cat([self.waveform, waveform[:-unprocessed_length]])
        self.voice_activity_mask = torch.cat([self.voice_activity_mask, vad_mask])

        return self.populate_segment_scales()

    def populate_segment_scales(self) -> List[Segment]:
        # Create and process segments at all temporal scales for new audio data
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

        # Update segment relationships and generate embeddings
        self.assign_segments()
        self.embed()
        return self.base_scale_segments[orig_num_base_segments:]
