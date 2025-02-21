from itertools import combinations

import torch

from nemo.collections.asr.models.msdd_models import EncDecDiarLabelModel

@torch.no_grad()
def get_speaker_predictions(
    ms_emb_seq: torch.Tensor, 
    ms_emb_seq_labels: torch.Tensor, 
    ms_avg_embs: torch.Tensor, 
    msdd_model: EncDecDiarLabelModel, 
    threshold=0.7, 
    batch_size=256
):
    """
    Process embeddings through MSDD model and return speaker probabilities.
    Processes sequence in batches to handle long sequences efficiently.
    
    Args:
        ms_emb_seq: Embedding sequence tensor [batch_size, length, scale_n, emb_dim]
        ms_emb_seq_labels: Initial clustering labels [batch_size, sequence_length]
        ms_avg_embs: Average embeddings tensor [batch_size, scale_n, emb_dim, num_speakers] (centroids)
        msdd_model: MSDD model instance
        threshold: Threshold value for final speaker label output (default: 0.7)
        batch_size: Number of sequence steps to process at once (default: 256)
    
    Returns:
        tuple: (probabilities, labels)
            - probabilities: tensor of shape [num_speakers, sequence_length]
            - labels: binary tensor of shape [num_speakers, sequence_length]
    """
    if ms_emb_seq.shape[1] != ms_emb_seq_labels.shape[1]:
        raise ValueError(f"ms_emb_seq sequence length {ms_emb_seq.shape[1]} does not match ms_emb_seq_labels sequence length {ms_emb_seq_labels.shape[1]}")
        
    device = ms_emb_seq.device
    num_speakers = ms_avg_embs.shape[-1]
    speaker_indices = list(range(num_speakers))
    sequence_length = ms_emb_seq.shape[1]
    if batch_size == -1:
        batch_size = sequence_length
    
    if len(speaker_indices) == 1:
        all_probs = torch.ones((1, sequence_length), device=device)
        labels = torch.ones((1, sequence_length), device=device)
        return all_probs, labels
    else:
        # Initialize output tensors for full sequence
        all_probs = torch.zeros((num_speakers, sequence_length), device=device)
        labels = torch.zeros((num_speakers, sequence_length), device=device)

    
    # Generate all possible speaker pairs
    speaker_pairs = list(combinations(speaker_indices, 2))
    
    # Process sequence in batches
    for start_idx in range(0, sequence_length, batch_size):
        end_idx = min(start_idx + batch_size, sequence_length)
        batch_slice = slice(start_idx, end_idx)
        
        # Get batch of embeddings
        batch_emb_seq = ms_emb_seq[:, batch_slice]
        
        # Store results for this batch
        batch_results = {}
        
        # Process each speaker pair for this batch
        for spk1_idx, spk2_idx in speaker_pairs:
            # Select centroids for this pair
            pair_centroids = ms_avg_embs[:, :, :, [spk1_idx, spk2_idx]]
            
            # Run the model on the batch
            preds, scale_weights = msdd_model.core_model(
                batch_emb_seq,  # [batch_size, batch_length, scale_n, emb_dim]
                None,
                pair_centroids, # [batch_size, scale_n, emb_dim, 2]
                None
            )
            
            batch_results[(spk1_idx, spk2_idx)] = (preds, scale_weights)
        
        # Calculate probabilities for each speaker in this batch
        batch_probs = torch.zeros((num_speakers, end_idx - start_idx), device=device)
        
        # For each speaker
        for s in speaker_indices:
            # Find all pairs containing speaker s
            relevant_pairs = [(s1, s2) for s1, s2 in batch_results.keys() if s in (s1, s2)]
            
            # Accumulate probabilities
            for pair in relevant_pairs:
                preds, _ = batch_results[pair]
                # If s is the first speaker in the pair
                if pair[0] == s:
                    batch_probs[s] += preds[0, :, 0]
                # If s is the second speaker in the pair
                else:
                    batch_probs[s] += preds[0, :, 1]
            
            # Average by (S-1) as per equation (5)
            batch_probs[s] = batch_probs[s] / (num_speakers - 1)
        
        # Store probabilities for this batch
        all_probs[:, batch_slice] = batch_probs
        
        # For each time step in the batch
        for i in range(end_idx - start_idx):
            # If max probability at this time step is below threshold
            if torch.max(batch_probs[:, i]) < threshold:
                # Use the initial clustering label
                initial_label = ms_emb_seq_labels[0, start_idx + i]
                labels[initial_label, start_idx + i] = 1
            else:
                # Use the model predictions
                labels[:, start_idx + i] = (batch_probs[:, i] > threshold).float()
    
    return all_probs, labels

class MSDD:
    device: str = 'cuda'
    
    def __init__(
        self,
        threshold: float = 0.8,
        batch_size: int = 256
    ):
        self.overall_msdd = EncDecDiarLabelModel.from_pretrained(model_name='diar_msdd_telephonic').eval()
        self.overall_msdd = self.overall_msdd.to(device=self.device)
        self.msdd = self.overall_msdd

        self.speech_embedding_model = self.overall_msdd.msdd._speaker_model

        self.threshold: float = threshold
        self.batch_size: int = batch_size

    def __call__(
        self,
        ms_emb_seq: torch.Tensor, 
        ms_emb_seq_labels: torch.Tensor, 
        ms_avg_embs: torch.Tensor
    ):
        return get_speaker_predictions(
            ms_emb_seq, 
            ms_emb_seq_labels, 
            ms_avg_embs, 
            msdd_model=self.overall_msdd.msdd, 
            threshold=self.threshold, 
            batch_size=self.batch_size
        )