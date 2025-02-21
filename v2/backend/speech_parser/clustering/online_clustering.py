from typing import Tuple, Dict

import torch
from scipy.optimize import linear_sum_assignment

from nemo.collections.asr.parts.utils.offline_clustering import SpeakerClustering, getCosAffinityMatrix

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
        MAX_EMBEDDINGS = 2800
        self.device = device
        
        self.max_embs_clustered = MAX_EMBEDDINGS
        if max_buffer_size >= MAX_EMBEDDINGS:
            raise ValueError(
                f"Buffer size {max_buffer_size} exceeds maximum allowed size of {MAX_EMBEDDINGS}. "
                "This may cause errors with Torch's Intel MKL implementation."
            )
        
        self.max_buffer_size = max_buffer_size
        self.hist_buffer_size_per_spk = hist_buffer_size_per_spk
        self.hist_spk_buffer = {}  # Buffer storing historical embeddings for each speaker
        self.spk_avg_ms_emb_dict = {}  # Dictionary storing average embeddings for each speaker
        self.embs: torch.Tensor = torch.tensor([], device=self.device, dtype=torch.float32)
        self.emb_labels: torch.Tensor = torch.tensor([], device=self.device, dtype=int)
        
        # Initialize NME-SC clustering algorithm
        self.clustering = SpeakerClustering()
        self.clustering.device = device
        self.clustering.cuda = "cuda" in device
        
        # Initialize clustering parameters
        self.multiscale_weights = torch.tensor([1, 1, 1, 1, 1], dtype=torch.float32)  # Weights for different temporal scales
        self.oracle_num_speakers = -1  # Set to -1 for automatic speaker count detection
        self.max_num_speakers = 8  # Maximum number of speakers to detect
        self.max_rp_threshold = 0.3  # Maximum threshold for spectral clustering # was 0.15
        self.sparse_search_volume = 50  # Number of threshold values to search
        self.fixed_thres = -1.0  # Fixed threshold for clustering (-1.0 means adaptive)
        self.kmeans_random_trials = 3  # Number of k-means clustering attempts
        self.sim_threshold = 0.5  # Similarity threshold for speaker matching
        
        # Speaker tracking state
        self.next_speaker_id = 0  # Next available unique speaker ID
        self.num_speakers = 0  # Current number of detected speakers
        self.is_online = False  # Flag indicating if system is in online mode

    def __call__(
        self, 
        ms_emb_t: torch.Tensor = None
    ) -> Dict[int, torch.Tensor]:
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
        cluster_emb_labels = self.get_clusters(cluster_input_embs)
        
        # Update speaker identities and historical buffer
        speaker_remaps = self.get_speaker_label_remaps(
            cluster_emb_labels,
            existing_embs,
            existing_emb_labels
        )
        
        cluster_emb_labels_remap = torch.tensor([speaker_remaps[int(spk_idx)] for spk_idx in cluster_emb_labels], device=self.device, dtype=torch.int)
        
        spk_ms_emb = self._group_speaker_embeddings(cluster_input_embs, cluster_emb_labels_remap)
        self.update_buffer(spk_ms_emb)

        self.embs = torch.cat([self.embs, ms_emb_t])
        self.emb_labels = torch.cat([self.emb_labels, cluster_emb_labels_remap[num_existing:]])
        
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
                        temp_hist_spk_buffer[spk_idx] = self.random_resample(spk_embs, ref_hist_buffer_size)
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
            int(spk_idx): embeddings[torch.where(cluster_labels == spk_idx)[0]]
            for spk_idx in spk_indices
        }
        
    def get_centroids(self):
        return {spk_idx: spk_embs.mean(0) for spk_idx, spk_embs in self.hist_spk_buffer.items()}
    
    def get_affinity_matrix(self, ms_emb_t):
        """
        Compute weighted multi-scale affinity matrix from embeddings.
        
        Args:
            ms_emb_t: Multi-scale embedding tensor [n, s, e]
                n: number of time steps
                s: number of scales
                e: embedding dimension
                
        Returns:
            Square cosine similarity matrix [n, n]
        """
        # Compute affinity matrix for each temporal scale
        affinity_matrices = torch.stack([getCosAffinityMatrix(ms_emb_t[:, scale_idx]) for scale_idx in range(ms_emb_t.shape[1])])

        # Compute weighted sum across all scales
        weighted_affinity_matrices = affinity_matrices.permute(1, 2, 0) * self.multiscale_weights.to(device=affinity_matrices.device)
        affinity_matrix = weighted_affinity_matrices.sum(2)
        
        return affinity_matrix
    
    def get_clusters(self, ms_emb_t):
        """
        Perform speaker clustering on multi-scale embeddings.
        
        Args:
            ms_emb_t: Multi-scale embedding tensor [n, s, e]
                n: number of time steps
                s: number of scales
                e: embedding dimension
                
        Returns:
            Tensor [n] containing cluster assignments for each time step
        """
        
        if ms_emb_t.shape[0] > self.max_embs_clustered:
            raise ValueError(
                f"{ms_emb_t} exceeds maximum allowed size of {self.max_embs_clustered}. "
                "This may cause errors with Torch's Intel MKL implementation."
            )
            
        affinity_matrix = self.get_affinity_matrix(ms_emb_t)
        affinity_matrix = affinity_matrix.to(device=self.device)
        
        return self.clustering.forward_unit_infer(
            mat=affinity_matrix,
            oracle_num_speakers=self.oracle_num_speakers,
            max_num_speakers=self.max_num_speakers,
            max_rp_threshold=self.max_rp_threshold,
            sparse_search_volume=self.sparse_search_volume,
            fixed_thres=self.fixed_thres,
            kmeans_random_trials=self.kmeans_random_trials,
        )

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
    
    def compute_similarity(self, emb1: torch.Tensor, emb2: torch.Tensor) -> torch.Tensor:
        """
        Compute weighted cosine similarity between multi-scale speaker embeddings.
        
        Args:
            emb1, emb2: Multi-scale embedding tensors to compare
            
        Returns:
            Weighted similarity score
        """
        similarities = torch.tensor([
            torch.nn.functional.cosine_similarity(
                emb1[scale], emb2[scale], dim=0
            ) for scale in range(5)
        ])
        return (similarities * self.multiscale_weights).sum()
        
    def update_buffer(self, spk_ms_emb: Dict[int, torch.Tensor]):
        """
        Update historical buffer with new speaker embeddings.
        
        Args:
            spk_ms_emb: Dictionary mapping speaker IDs to their embeddings
        """
        for spk_idx, spk_embs in spk_ms_emb.items():
            self.hist_spk_buffer[spk_idx] = torch.cat([self.hist_spk_buffer.get(spk_idx, torch.tensor([], device=self.device)), spk_embs])
                
    def random_resample(self, input_tensor: torch.Tensor, target_count: int) -> torch.Tensor:
        """
        Randomly resample a tensor to reduce its size while maintaining distribution.
        
        Args:
            input_tensor: Tensor to resample
            target_count: Desired number of samples
            
        Returns:
            Randomly resampled tensor with target_count samples
        """
        num_samples = input_tensor.shape[0]
        sampled_indices = torch.randperm(num_samples)[:target_count]
        return input_tensor[sampled_indices]