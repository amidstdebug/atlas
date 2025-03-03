from typing import Tuple, Dict, Optional

import torch
from scipy.optimize import linear_sum_assignment

from .utils import NMESCConfig, MAX_SPECTRAL_CLUSTERING_SAMPLES, get_clusters, random_resample, window_overcluster_resample

class OnlineSpeakerClustering:
    """
    A class for performing online speaker clustering on audio embeddings.
    Uses a historical buffer to maintain speaker identities across multiple audio segments
    and implements a weighted multi-scale clustering approach.
    """
    
    def __init__(
        self,
        hist_buffer_size_per_spk: int = 400,
        max_buffer_size: int = 1500,
        device: str = 'cpu'
    ):
        """
        Initialize the online speaker clustering system.

        Args:
            hist_buffer_size_per_spk: number of randomly sampled embedding entries to store in buffer per speaker
                                     set to -1 to dynamically allocate size based on number of speakers and max buffer size
            max_buffer_size: maximum number of embeddings to be retained in buffer
                           exceeding 2900~ will possibly result in errors with Torch (related to Intel MKL)
            device: computation device ('cuda' or 'cpu')
        """
        MAX_SPECTRAL_CLUSTERING_SAMPLES = 2800
        self.device = device
        
        self.max_embs_clustered = MAX_SPECTRAL_CLUSTERING_SAMPLES
        if max_buffer_size >= MAX_SPECTRAL_CLUSTERING_SAMPLES:
            raise ValueError(
                f"Buffer size {max_buffer_size} exceeds maximum allowed size of {MAX_SPECTRAL_CLUSTERING_SAMPLES}. "
                "This may cause errors with Torch's Intel MKL implementation."
            )
        
        self.max_buffer_size = max_buffer_size
        self.hist_buffer_size_per_spk = hist_buffer_size_per_spk
        self.all_embs: List[torch.Tensor] = []
        self.buffer: List[torch.Tensor] = []
        self.hist_spk_buffer = {}  # Buffer storing historical embeddings for each speaker
        self.spk_avg_ms_emb_dict = {}  # Dictionary storing average embeddings for each speaker
        self.embs: torch.Tensor = torch.tensor([], device=self.device, dtype=torch.float32)
        self.emb_labels: torch.Tensor = torch.tensor([], device=self.device, dtype=int)
        
        # Initialize clustering parameters
        self.cluster_config = NMESCConfig(
            multiscale_weights = torch.tensor([1, 1, 1, 1, 1], dtype=torch.float32),
            oracle_num_speakers = -1,
            max_num_speakers = 8,
            max_rp_threshold = 0.15,
            sparse_search_volume = 20,
            fixed_thres = -1.0,
            kmeans_random_trials = 5,
            device = self.device
        )

        self.min_new_samples = 250
        
        # Speaker tracking state
        self.next_speaker_id = 0  # Next available unique speaker ID
        self.num_speakers = 0  # Current number of detected speakers
        self.is_online = False  # Flag indicating if system is in online mode

    def __call__(
        self, 
        ms_emb_t: torch.Tensor = None
    ) -> Optional[torch.Tensor]:
        self.buffer.append(ms_emb_t)
        self.all_embs.append(ms_emb_t)
        
        curr_buffer_len = sum([embs.shape[0] for embs in self.buffer])

        if curr_buffer_len > self.min_new_samples:
            buffer_tensor = torch.concat(self.buffer)
            self.buffer.clear()
            
            return self._forward(buffer_tensor)
        else:
            return None

    def _forward(
        self, 
        ms_emb_t: torch.Tensor = None
    ) -> torch.Tensor:
        """
        Process new embeddings and return speaker mappings.
        Main entry point for clustering new audio segments.
        
        Args:
            ms_emb_t: Multi-scale embedding tensor of shape [n, s, e] where:
                n is the number of time steps
                s is the number of scales
                e is the embedding dimension
                
        Returns:
            Dictionary mapping cluster indices to persistent speaker IDs
        """
        ms_emb_t = ms_emb_t.to(device=self.device, dtype=torch.float32)
        
        # Prepare data by combining historical and new embeddings
        cluster_input_embs, existing_embs, existing_emb_labels, num_existing = self._prepare_clustering_data(ms_emb_t)
        
        # Perform clustering and group speaker embeddings
        cluster_emb_labels = get_clusters(cluster_input_embs, self.cluster_config)
        
        # Update speaker identities and historical buffer
        speaker_remaps = self.get_speaker_label_remaps(
            cluster_emb_labels,
            existing_embs,
            existing_emb_labels
        )
        
        cluster_emb_labels_remap = torch.tensor([speaker_remaps[int(spk_idx)] for spk_idx in cluster_emb_labels], device=self.device, dtype=torch.int)
        
        spk_ms_emb = self._group_speaker_embeddings(cluster_input_embs, cluster_emb_labels_remap)
        self.update_buffer(spk_ms_emb)

        # self.embs = torch.cat([self.embs, ms_emb_t])
        # self.emb_labels = torch.cat([self.emb_labels, cluster_emb_labels_remap[num_existing:]])
        
        return cluster_emb_labels[num_existing:]

    def _prepare_clustering_data(
        self,
        ms_emb_t: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, int]:
        """
        Prepare input data for clustering by combining historical and new embeddings.
        Handles buffer size management and random resampling if needed.
        
        Args:
            ms_emb_t: New multi-scale embeddings tensor
            
        Returns:
            Tuple containing:
            - Combined embeddings for clustering
            - Historical embeddings
            - Historical embedding labels
            - Number of historical embeddings
        """
        num_existing = 0
        existing_embs = torch.tensor([], device=self.device)
        existing_emb_labels = torch.tensor([], device=self.device)
        
        # If we have historical data, combine it with new embeddings
        if len(self.hist_spk_buffer) > 0:
            existing_embs = torch.cat(list(self.hist_spk_buffer.values()))
            existing_emb_labels = torch.cat([
                torch.full([spk_embs.shape[0]], spk_idx) 
                for spk_idx, spk_embs in self.hist_spk_buffer.items()
            ])
            num_existing = existing_embs.shape[0]
            
            # Handle buffer size limits by resampling if needed
            if (num_existing + ms_emb_t.shape[0]) > self.max_embs_clustered:
                if self.hist_buffer_size_per_spk == -1:
                    ref_hist_buffer_size = (self.max_buffer_size - ms_emb_t.shape[0]) // len(self.hist_spk_buffer)
                else:
                    ref_hist_buffer_size = self.hist_buffer_size_per_spk

                temp_hist_spk_buffer = self.hist_spk_buffer.copy()
                for spk_idx, spk_embs in self.hist_spk_buffer.items():
                    if spk_embs.shape[0] > ref_hist_buffer_size:
                        temp_hist_spk_buffer[spk_idx] = random_resample(spk_embs, ref_hist_buffer_size)
                    else:
                        temp_hist_spk_buffer[spk_idx] = spk_embs
                        
                existing_embs = torch.cat(list(temp_hist_spk_buffer.values()))
                existing_emb_labels = torch.cat([
                    torch.full([spk_embs.shape[0]], spk_idx) 
                    for spk_idx, spk_embs in temp_hist_spk_buffer.items()
                ])
                num_existing = existing_embs.shape[0]
            
            cluster_input_embs = torch.cat([existing_embs, ms_emb_t])
        else:
            cluster_input_embs = ms_emb_t
            
        return cluster_input_embs, existing_embs, existing_emb_labels, num_existing

    def _group_speaker_embeddings(
        self,
        embeddings: torch.Tensor,
        cluster_labels: torch.Tensor
    ) -> Dict[int, torch.Tensor]:
        """
        Compute per-speaker embeddings by grouping embeddings according to cluster assignments.
        
        Args:
            embeddings: Input embedding tensor
            cluster_labels: Tensor of cluster assignments
            
        Returns:
            Dictionary mapping speaker indices to their corresponding embeddings
        """
        spk_indices = cluster_labels.unique()
        return {
            int(spk_idx): embeddings[cluster_labels == spk_idx]
            for spk_idx in spk_indices
        }
        
    def recluster(self, downsample_method: str = "window_overcluster"):
        """
        Recluster all embeddings in the historical buffer and overwrite past history.
        Handles resampling to maximum allowed embeddings if necessary.
        
        This method:
        1. Combines all embeddings from the historical buffer
        2. Resamples if total embeddings exceed maximum limit
        3. Performs fresh clustering on all embeddings
        4. Updates the historical buffer with new cluster assignments
        """

        ALLOWED_DOWNSAMPLE_METHODS = ["random", "window_overcluster"] # incl later window_random?
        if downsample_method not in ALLOWED_DOWNSAMPLE_METHODS:
            raise ValueError(f"downsample_method must be one of {','.join(ALLOWED_DOWNSAMPLE_METHODS)} instead of {downsample_method}")
            
        # If buffer is empty, nothing to do
        if not self.hist_spk_buffer:
            return
            
        # Combine all embeddings from historical buffer
        all_embeddings = torch.cat(list(self.hist_spk_buffer.values()))
        total_samples = all_embeddings.shape[0]
        
        # Resample if exceeding maximum limit
        if total_samples > self.max_embs_clustered:
            if downsample_method == "random":
                all_embeddings = random_resample(all_embeddings, self.max_embs_clustered)
            elif downsample_method == "window_overcluster":
                all_embeddings = window_overcluster_resample(
                    input_tensor=all_embeddings, 
                    target_count=self.max_embs_clustered
                )
        
        # Perform fresh clustering
        cluster_labels = get_clusters(all_embeddings, self.cluster_config)
        
        # Create new speaker mappings starting from 0
        unique_clusters = cluster_labels.unique().tolist()
        new_speaker_mapping = {k: i for i, k in enumerate(unique_clusters)}
        remapped_labels = torch.tensor([new_speaker_mapping[int(label)] for label in cluster_labels], 
                                     device=self.device, 
                                     dtype=torch.int)
        
        # Group embeddings by new cluster assignments
        new_speaker_embeddings = self._group_speaker_embeddings(all_embeddings, remapped_labels)
        
        # Clear existing buffer and update with new clusters
        self.hist_spk_buffer.clear()
        self.update_buffer(new_speaker_embeddings)
        
        # Reset speaker tracking state
        self.next_speaker_id = len(unique_clusters)
        self.num_speakers = len(unique_clusters)
        
    def get_centroids(self):
        return {spk_idx: spk_embs.mean(0) for spk_idx, spk_embs in self.hist_spk_buffer.items()}

    def get_speaker_label_remaps(
        self, 
        cluster_labels: torch.Tensor,
        existing_embs: torch.Tensor,
        existing_emb_labels: torch.Tensor,
    ) -> Dict[int, int]:
        """
        Match new speaker labels to existing speakers by maximizing agreement with historical labels.
        Uses the Hungarian algorithm for optimal matching and handles creation of new speaker IDs.
        
        Args:
            cluster_labels: Cluster assignments for all embeddings (historical + new)
            existing_embs: Historical embeddings
            existing_emb_labels: Historical speaker labels
            
        Returns:
            Dictionary mapping new cluster indices to persistent speaker IDs
        """
        # Handle first batch case
        if len(existing_embs) == 0:
            unique_clusters = cluster_labels.unique().tolist()
            mapping = {k: i for i, k in enumerate(unique_clusters)}
            self.next_speaker_id = len(unique_clusters)
            return mapping
    
        # Get unique speaker IDs and determine if we need to check for new speakers
        new_indices = cluster_labels.unique().tolist()
        existing_indices = existing_emb_labels.unique().tolist()
        check_new_speakers = len(new_indices) > len(existing_indices)
        
        # Build cost matrix for Hungarian algorithm
        n_new = len(new_indices)
        n_existing = len(existing_indices)
        cost_matrix = torch.zeros((n_new, n_existing))
        
        # Count label agreements between old and new assignments
        num_historical = len(existing_embs)
        for i in range(num_historical):
            old_label = existing_emb_labels[i]
            new_label = cluster_labels[i]
            new_idx = new_indices.index(new_label)
            old_idx = existing_indices.index(old_label)
            cost_matrix[new_idx, old_idx] += 1
        
        # Run Hungarian algorithm for optimal matching
        cost_matrix = -cost_matrix  # Negative for minimization
        row_ind, col_ind = linear_sum_assignment(cost_matrix.cpu().numpy())
        
        # Process matches and create new speakers if needed
        remapping = {}
        for i, j in zip(row_ind, col_ind):
            new_idx = new_indices[i]
            existing_idx = existing_indices[j]
            count = -cost_matrix[i, j]
            
            # Check if match has enough agreement
            expected_count = num_historical / len(existing_indices)
            if check_new_speakers and count < (expected_count / 2):
                new_speaker_id = self.next_speaker_id
                self.next_speaker_id += 1
                remapping[new_idx] = new_speaker_id
            else:
                remapping[new_idx] = existing_idx
        
        # Handle any remaining unmatched speakers
        if check_new_speakers:
            for new_idx in new_indices:
                if new_idx not in remapping:
                    new_speaker_id = self.next_speaker_id
                    self.next_speaker_id += 1
                    remapping[new_idx] = new_speaker_id
        
        return remapping
        
    def update_buffer(self, spk_ms_emb: Dict[int, torch.Tensor]):
        """
        Update historical buffer with new speaker embeddings.
        
        Args:
            spk_ms_emb: Dictionary mapping speaker IDs to their embeddings
        """
        for spk_idx, spk_embs in spk_ms_emb.items():
            self.hist_spk_buffer[spk_idx] = torch.cat([self.hist_spk_buffer.get(spk_idx, torch.tensor([], device=self.device)), spk_embs])