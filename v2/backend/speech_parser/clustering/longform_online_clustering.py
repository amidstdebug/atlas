from typing import Tuple, Dict, Optional

import torch
from scipy.optimize import linear_sum_assignment

from nemo.collections.asr.parts.utils.offline_clustering import SpeakerClustering, getCosAffinityMatrix

clustering_utils = SpeakerClustering()
MAX_EMBEDDINGS = 2800

def get_affinity_matrix(
    ms_emb_t,
    multiscale_weights = torch.tensor([1, 1, 1, 1, 1])
):
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
    weighted_affinity_matrices = affinity_matrices.permute(1, 2, 0) * multiscale_weights.to(device=affinity_matrices.device)
    affinity_matrix = weighted_affinity_matrices.sum(2)
    
    return affinity_matrix

class OverclusteringWindow:
    def __init__(
        self,
        embeds: torch.Tensor,
        clusters: int,
        device: str = 'cpu',
    ):
        self.clusters: int = clusters

        self.is_clustered: bool = False

        self.embeds: torch.Tensor = embeds
        self.labels: torch.Tensor = torch.zeros(self.embeds.shape[0], dtype=int)
        self.remapping: Optional[Dict[int, int]] = None
        # self.remapped_labels: torch.Tensor = torch.zeros(self.embeds.shape, dtype=int)

        # Initialize clustering parameters
        self.multiscale_weights = torch.tensor([1, 1, 1, 1, 1], dtype=torch.float32)  # Weights for different temporal scales
        self.max_rp_threshold = 0.3  # Maximum threshold for spectral clustering # was 0.15
        self.sparse_search_volume = 50  # Number of threshold values to search
        self.fixed_thres = -1.0  # Fixed threshold for clustering (-1.0 means adaptive)
        self.kmeans_random_trials = 3  # Number of k-means clustering attempts
        self.sim_threshold = 0.5  # Similarity threshold for speaker matching

        self.device: str = device

    def cluster(self):
        if self.embeds.shape[0] > MAX_EMBEDDINGS:
            raise ValueError(
                f"{ms_emb_t} exceeds maximum allowed size of {self.max_embs_clustered}. "
                "This may cause errors with Torch's Intel MKL implementation."
            )
            
        affinity_matrix = get_affinity_matrix(self.embeds)
        affinity_matrix = affinity_matrix.to(device=self.device)
        
        self.labels = clustering_utils.forward_unit_infer(
            mat=affinity_matrix,
            oracle_num_speakers=self.clusters,
            max_num_speakers=self.clusters,
            max_rp_threshold=self.max_rp_threshold,
            sparse_search_volume=self.sparse_search_volume,
            fixed_thres=self.fixed_thres,
            kmeans_random_trials=self.kmeans_random_trials,
        )

        self.is_clustered = True

        return self.labels

    def set_remapping(self, mapping: Dict[int, int]):
        self.remapping = mapping

    def get_labels(self, with_remapping=False) -> torch.Tensor:
        if not with_remapping or self.remapping is None:
            return self.labels
        
        remapped_labels = torch.zeros(self.embeds.shape[0], dtype=int)
        for i, old_label in enumerate(self.labels):
            new_label = mapping.get(int(old_label), 0)
            remapped_labels[i] = new_label
        return remapped_labels

    @property
    def grouped_embeds(self) -> Dict[int, torch.Tensor]:
        labels = self.get_labels()
        return {
            int(label): self.embeds[torch.where(labels == label)[0]].mean(0) # tweak here for aggregation method
            for label in labels.unique() 
        }

class OverclusteringWindowArray:
    def __init__(
        self,
        window_size: int,
        clusters_per_window: int,
        device: str = 'cpu',
    ):
        self.window_size: int = window_size
        self.clusters_per_window: int = clusters_per_window

        self.device: str = device

        self.windows: List[OverclusteringWindow] = []

        self.leftover_chunk: torch.Tensor = torch.tensor([], device=self.device)

    def extend(
        self,
        embeds: torch.Tensor
    ):
        leftover_len = self.leftover_chunk.shape[0]
        new_len = embeds.shape[0]

        if (new_len + leftover_len) > self.window_size:
            new_chunk = torch.concat([self.leftover_chunk, embeds])
            self.leftover_chunk = new_chunk[self.window_size:]
            self.windows.append(
                OverclusteringWindow(
                    new_chunk[:self.window_size],
                    self.clusters_per_window
                )
            )
        else:
            self.leftover_chunk = torch.concat([self.leftover_chunk, embeds])
            
    def cluster(self):
        for window in self.windows:
            if not window.is_clustered:
                window.cluster()
                
    @property
    def grouped_embeds(self):
        grouped_label_list = []
        grouped_embeds_list = []
        for window in self.windows:
            if window.is_clustered:
                labels = list(window.grouped_embeds.keys())
                embeds = list(window.grouped_embeds.values())
                
                grouped_label_list.extend(labels)
                grouped_embeds_list.extend(embeds)
        return torch.tensor(grouped_label_list, device=self.device), torch.stack(grouped_embeds_list)

class LongformOnlineClustering:
    def __init__(
        self,
        device: str = 'cpu',
        max_buffer_size: int = 2800
    ):
        self.window_size = 200
        self.clusters_per_window = 10 # over clustering
        
        self.device = device
        
        self.max_embs_clustered = MAX_EMBEDDINGS
        if max_buffer_size >= MAX_EMBEDDINGS:
            raise ValueError(
                f"Buffer size {max_buffer_size} exceeds maximum allowed size of {MAX_EMBEDDINGS}. "
                "This may cause errors with Torch's Intel MKL implementation."
            )
        
        self.max_buffer_size = max_buffer_size

        # Initialize NME-SC clustering algorithm
        self.clustering = SpeakerClustering()
        self.clustering.device = device
        self.clustering.cuda = "cuda" in device

        self.windows = []

    def __call__(
        self,
        embeds
    ):
        pass