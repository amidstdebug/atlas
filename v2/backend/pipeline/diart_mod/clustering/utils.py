import math
from dataclasses import dataclass

import torch
from .offline_clustering import SpeakerClustering, getCosAffinityMatrix

MAX_SPECTRAL_CLUSTERING_SAMPLES = 2800

DEVICE = 'cpu'

MULTISCALE_WEIGHTS = torch.tensor([1, 1, 1, 1, 1], dtype=torch.float32)

# Initialize NME-SC clustering algorithm
nemo_speaker_clustering = SpeakerClustering()
nemo_speaker_clustering.device = DEVICE
nemo_speaker_clustering.cuda = "cuda"

def get_affinity_matrix(
    ms_emb_t: torch.Tensor,
    multiscale_weights: torch.Tensor = MULTISCALE_WEIGHTS
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

@dataclass
class NMESCConfig:
    multiscale_weights: torch.Tensor = MULTISCALE_WEIGHTS
    oracle_num_speakers: int = -1
    max_num_speakers: int = 8
    max_rp_threshold: float = 0.15
    sparse_search_volume: int = 20
    fixed_thres: float = -1.0
    kmeans_random_trials: float = 5
    device: str = DEVICE 

def get_clusters(
    ms_emb_t: torch.Tensor,
    config: NMESCConfig,
):
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
    
    if ms_emb_t.shape[0] > MAX_SPECTRAL_CLUSTERING_SAMPLES:
        raise ValueError(
            f"{ms_emb_t} of shape {ms_emb_t.shape} exceeds maximum allowed size of {MAX_SPECTRAL_CLUSTERING_SAMPLES}. "
            "This may cause errors with Torch's Intel MKL implementation."
        )
    print(ms_emb_t.shape)
        
    affinity_matrix = get_affinity_matrix(ms_emb_t, config.multiscale_weights)
    affinity_matrix = affinity_matrix.to(device=config.device)
    
    return nemo_speaker_clustering.forward_unit_infer(
        mat=affinity_matrix,
        oracle_num_speakers=config.oracle_num_speakers,
        max_num_speakers=config.max_num_speakers,
        max_rp_threshold=config.max_rp_threshold,
        sparse_search_volume=config.sparse_search_volume,
        fixed_thres=config.fixed_thres,
        kmeans_random_trials=config.kmeans_random_trials,
    )

def random_resample(
    input_tensor: torch.Tensor, 
    target_count: int
) -> torch.Tensor:
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

def window_overcluster_resample(
    input_tensor: torch.Tensor, 
    target_count: int, 
    clusters_per_window: int = 10,
) -> torch.Tensor:
    """
    Args:
        input_tensor: Tensor to resample
        target_count: Desired number of samples
        clusters_per_window: Number of samples per window
        
    Returns:
        Randomly resampled tensor with target_count samples
    """
    input_len = input_tensor.shape[0]
    
    if target_count > input_len:
        return input_tensor

    window_count = math.ceil(target_count / clusters_per_window)
    window_size = math.ceil(input_len / window_count)
        
    start_idx = 0
    end_idx = window_size

    cluster_config = NMESCConfig(
        oracle_num_speakers=clusters_per_window, 
        max_num_speakers=clusters_per_window,
        device='cuda'
    )

    samples = []
    while end_idx < (input_len + window_size):
        curr_window = input_tensor[start_idx:end_idx]

        labels = get_clusters(curr_window, cluster_config)
        unique_labels = labels.unique()

        samples.extend([curr_window[labels == label].mean(0) for label in unique_labels])

        start_idx = end_idx
        end_idx += window_size

    return torch.stack(samples)
    