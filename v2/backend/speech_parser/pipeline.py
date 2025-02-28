from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Iterator, Any

import torch
from nemo.collections.asr.models.label_models import EncDecSpeakerLabelModel

from .audio import Audio, Segment, BaseScaleSegment, ScaleSegment, SpeakerSegment, SegmentBatch, get_segments, get_segment_batches, merge_segments
from .clustering.online_clustering import OnlineSpeakerClustering
from .msdd import MSDD
from .vad import SileroVAD

class OnlineDiarizationPipeline:
    def __init__(
        self,
        speech_embedding_model: EncDecSpeakerLabelModel=None,
        voice_activity_detection_model: SileroVAD=None,
        multi_scale_diarization_model: MSDD=None,
        speaker_clustering: OnlineSpeakerClustering=None,
        scales: List[float]=[1.5, 1.25, 1.0, 0.75, 0.5], 
        hops: List[float]=[1.5/4, 1.25/4, 1.0/4, 0.75/4, 0.5/4], 
        base_scale: float=0.5, 
        sampling_rate: int=16_000,
        batch_size: int=128,
        waveform: Optional[torch.Tensor]=None
    ):
        self.device = 'cuda'
        self.idle_device = 'cpu'
        
        # Initialize models
        self.speech_embedding_model = speech_embedding_model
        if self.speech_embedding_model is not None:
            self.speech_embedding_model.freeze()  # Freeze model weights for inference
            
        self.voice_activity_detection_model = voice_activity_detection_model
        self.multi_scale_diarization_model = multi_scale_diarization_model
        self.speaker_clustering = speaker_clustering
        
        # Initialize Audio object with configuration
        self.audio = Audio(
            scales=scales,
            hops=hops,
            base_scale=base_scale,
            sampling_rate=sampling_rate,
            batch_size=batch_size
        )
        self.sampling_rate = sampling_rate
        
        # Tunables for filtering speaker segments
        self.min_speaker_segment_duration = 1.0
        self.max_silence_per_segment_pct = 0.5
        
        # Clustering state
        self._clustering_start = False
        
        # Initialize with waveform if provided
        if waveform is not None:
            self.init_with_waveform(waveform)
    
    def init_with_waveform(self, waveform: torch.Tensor) -> None:
        """
        Initialize the pipeline with an existing waveform.
        
        Args:
            waveform: Audio waveform to initialize with
        """
        self.audio.waveform = waveform.to(device=self.idle_device, dtype=torch.float32)
        self.audio.voice_activity_mask = self.voice_activity_detection_model(self.audio.waveform)
        
        # Create segments
        new_segments = self.audio.populate_segment_scales()
        
        # Generate embeddings
        self.embed_all_segments()
    
    def _diarize(self, segments_to_update: List[Segment]) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Run the multi-scale diarization model on provided segments.
        
        Args:
            segments_to_update: List of segments to process with MSDD
            
        Returns:
            Tuple[torch.Tensor, torch.Tensor]: (probabilities, labels) for speaker assignments
        """
        empty_returns = torch.tensor([], device=self.idle_device), torch.tensor([], device=self.idle_device)
        
        if not self._clustering_start or len(segments_to_update) == 0:
            return empty_returns
            
        new_ms_emb_seq = torch.stack([segment.tensor for segment in segments_to_update])
        
        # Get updated centroids
        centroids = self.speaker_clustering.get_centroids()

        # Prepare inputs for multi-scale diarization model
        new_ms_emb_seq = new_ms_emb_seq.unsqueeze(0).to(self.device)
        ms_avg_embs = torch.stack([centroids[spk_idx] for spk_idx in sorted(list(centroids.keys()))]).permute(1, 2, 0).unsqueeze(0).to(self.device)
        
        # Get diarization probabilities and logits
        proba, labels = self.multi_scale_diarization_model(new_ms_emb_seq, None, ms_avg_embs)
        proba = proba.to(self.idle_device)
        labels = labels.to(self.idle_device)

        # Assign speaker labels to segments
        self.assign_speaker(segments_to_update, labels)
                    
        return proba, labels
    
    def assign_speaker(self, segments: List[Segment], labels: torch.Tensor):
        """
        Assign speaker labels to segments based on diarization results.
        
        Args:
            segments: List of segments to assign speakers to
            labels: Speaker labels from diarization model
        """
        for spk_idx in range(labels.shape[0]):
            for i, segment in enumerate(segments):
                if labels[spk_idx, i] == 1:
                    segment.add_speaker(spk_idx)
    
    def online_cluster(self, segments: List[Segment]):
        """
        Perform online clustering of speech segments.
        
        Args:
            segments: List of segments to cluster
        
        Returns:
            torch.Tensor: Speaker labels for the segments
        """
        if len(segments) == 0:
            return torch.tensor([])
            
        # Stack embeddings for processing
        new_ms_emb_seq = torch.stack([segment.tensor for segment in segments])
        return self.speaker_clustering(new_ms_emb_seq)
    
    def embed_segments(self, batches: List[SegmentBatch]) -> None:
        """
        Generate speaker embeddings for segment batches.
        
        Args:
            batches: List of segment batches to embed
        """
        if not batches or not self.speech_embedding_model:
            return
            
        for batch in batches:
            with torch.no_grad():
                audio_signal = batch.tensor.to(device=self.device, dtype=torch.float32)
                audio_signal_lens = torch.tensor([audio_signal.shape[-1]] * audio_signal.shape[0], device=self.device)
                _, embeds = self.speech_embedding_model.forward(input_signal=audio_signal, input_signal_length=audio_signal_lens)
            embeds = embeds.to(self.idle_device)
            batch.update_embeds(embeds)
    
    def embed_all_segments(self) -> None:
        """
        Generate speaker embeddings for all segments across all scales.
        """
        for scale, segment_scale in self.audio.segment_scales.items():        
            batch_loader = get_segment_batches(segment_scale, self.audio.batch_size)
            self.embed_segments(list(batch_loader))
    
    def process_audio(self, waveform: torch.Tensor) -> Tuple[List[Segment], torch.Tensor]:
        """
        Process new audio input, detect voice activity, and create segments.
        
        Args:
            waveform: New audio waveform to process
            
        Returns:
            Tuple[List[Segment], torch.Tensor]: (new segments, voice activity mask)
        """
        # Add new audio data and update voice activity detection mask
        waveform = waveform.to(device=self.idle_device, dtype=torch.float32)
        
        if self.audio._unprocessed_chunk is not None:
            waveform = torch.cat([self.audio._unprocessed_chunk, waveform])
            
        vad_mask, self.audio._unprocessed_chunk = self.voice_activity_detection_model(waveform)

        if self.audio._unprocessed_chunk is not None:
            unprocessed_length = self.audio._unprocessed_chunk.shape[0]
        else:
            unprocessed_length = 1
            
        self.audio.waveform = torch.cat([self.audio.waveform, waveform[:-unprocessed_length]])
        self.audio.voice_activity_mask = torch.cat([self.audio.voice_activity_mask, vad_mask])

        # Create segments at different scales
        new_segments = self.audio.populate_segment_scales()
        
        return new_segments, vad_mask
    
    def get_merged_speaker_segments(self, use_cache: bool = False) -> List[SpeakerSegment]:  
        """
        Get merged and filtered speaker segments.
        
        Returns:
            List[SpeakerSegment]: Filtered speaker segments
        """
        if not use_cache:
            self.audio.clear_merged_segments()
            
        for curr_merged_idx, segment in enumerate(self.audio.base_scale_segments[self.audio._merged_segments_idx:]):
            curr_active_speakers = list(self.audio._active_speakers.items())
            
            for speaker, active_segments in curr_active_speakers:
                # End the speaker segment if the start of the new segment is past the end of the old
                if (speaker in segment.speakers) and (segment.start <= active_segments[-1].end):
                    self.audio._active_speakers[speaker].append(segment)
                elif segment.start > active_segments[-1].end:
                    # Merge and end speakers
                    speaker_segment = merge_segments(
                        active_segments, 
                        speaker, 
                        sampling_rate=self.audio.sampling_rate
                    )
                    self.audio.merged_segments.append(speaker_segment)
                    self.audio._active_speakers.pop(speaker)
                
            for speaker in segment.speakers:
                if speaker not in self.audio._active_speakers:
                    # Start speaker
                    self.audio._active_speakers[speaker] = [segment]
                    
        self.audio._merged_segments_idx += curr_merged_idx

        # Apply filters
        filtered_segments = []
        for segment in self.audio.merged_segments:
            if (segment.mask.sum()/segment.mask.shape[0]) < self.max_silence_per_segment_pct:
                continue
            if segment.duration <= self.min_speaker_segment_duration:
                continue
            filtered_segments.append(segment)

        return filtered_segments
    
    def rediarize(self) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Recluster segments and reassign speakers based on new clustering.
        
        Returns:
            Tuple[torch.Tensor, torch.Tensor]: (probabilities, labels) for speaker assignments
        """
        if not self._clustering_start:
            return torch.tensor([], device=self.idle_device), torch.tensor([], device=self.idle_device)
            
        # Get all segments with embeddings
        segments_to_update = self.audio.base_scale_segments.segments_with_tensors
        if len(segments_to_update) == 0:
            return torch.tensor([], device=self.idle_device), torch.tensor([], device=self.idle_device)
            
        # Recluster and clear existing speaker assignments
        self.speaker_clustering.recluster()
        for segment in segments_to_update:
            segment.speakers.clear()
        
        # Run diarization on the segments with reclustered data
        return self._diarize(segments_to_update)

    
    def __call__(self, waveform: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Process new audio input and perform diarization.
        
        Args:
            waveform: New audio waveform to process
            
        Returns:
            Tuple[torch.Tensor, torch.Tensor]: (probabilities, labels) for speaker assignments
        """
        # Process audio and get new segments
        new_segments, _ = self.process_audio(waveform)
        
        empty_returns = torch.tensor([], device=self.idle_device), torch.tensor([], device=self.idle_device)

        # Generate embeddings for new segments
        self.embed_all_segments()
        
        segments_to_update = []
        for segment in new_segments:
            if segment.has_tensor:
                segments_to_update.append(segment)
                
        if len(segments_to_update) == 0:
            return empty_returns
                
        # Perform online clustering
        new_label_seq = self.online_cluster(segments_to_update)
        
        if len(self.speaker_clustering.get_centroids()) > 0:
            if not self._clustering_start:
                self.audio.clear_merged_segments()
                segments_to_update = self.audio.base_scale_segments.segments_with_tensors
                self._clustering_start = True
                
            return self._diarize(segments_to_update)
        else:
            for segment in segments_to_update:
                segment.set_unk_speaker()
            return empty_returns