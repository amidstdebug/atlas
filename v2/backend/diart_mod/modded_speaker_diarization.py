from typing import Sequence, Optional, List, Iterable, Tuple

import numpy as np
import torch

from pyannote.core import Annotation, SlidingWindowFeature, SlidingWindow, Segment

from diart import SpeakerDiarization, SpeakerDiarizationConfig
from diart.mapping import SpeakerMap, SpeakerMapBuilder
from diart.blocks.clustering import OnlineSpeakerClustering

from .clustering import NMESCConfig, MAX_SPECTRAL_CLUSTERING_SAMPLES, get_clusters, random_resample, window_overcluster_resample

class ModOnlineSpeakerClustering:
    """Implements constrained incremental online clustering of speakers and manages cluster centers.

    Parameters
    ----------
    tau_active:float
        Threshold for detecting active speakers. This threshold is applied on the maximum value of per-speaker output
        activation of the local segmentation model.
    rho_update: float
        Threshold for considering the extracted embedding when updating the centroid of the local speaker.
        The centroid to which a local speaker is mapped is only updated if the ratio of speech/chunk duration
        of a given local speaker is greater than this threshold.
    delta_new: float
        Threshold on the distance between a speaker embedding and a centroid. If the distance between a local speaker and all
        centroids is larger than delta_new, then a new centroid is created for the current speaker.
    metric: str. Defaults to "cosine".
        The distance metric to use.
    max_speakers: int
        Maximum number of global speakers to track through a conversation. Defaults to 20.
    """

    def __init__(
        self,
        tau_active: float,
        rho_update: float,
        delta_new: float,
        metric: Optional[str] = "cosine",
        max_speakers: int = 20,
        max_cluster_embs: int = MAX_SPECTRAL_CLUSTERING_SAMPLES,
        downsample_method: str = "random"
    ):
        self.tau_active = tau_active
        self.rho_update = rho_update
        self.delta_new = delta_new
        self.metric = metric
        self.max_speakers = max_speakers
        # self.centers: Optional[np.ndarray] = None
        self.embeddings: Sequence[np.ndarray] = []
        self.clusters: Optional[Dict[int, Sequence[np.ndarray]]] = None 
        self.dimension: Optional[int] = None
        self.active_centers = set()
        self.blocked_centers = set()

        self.max_cluster_embs = max_cluster_embs
        self.downsample_method = downsample_method 
        
        self.cluster_config = NMESCConfig(
            multiscale_weights = torch.tensor([1], dtype=torch.float32),
            oracle_num_speakers = -1,
            max_num_speakers = max_speakers,
            max_rp_threshold = 0.15,
            sparse_search_volume = 20,
            fixed_thres = -1.0,
            kmeans_random_trials = 5,
            device = "cpu"
        )

        self.online = True

    @property
    def num_free_centers(self) -> int:
        return self.max_speakers - self.num_known_speakers - self.num_blocked_speakers

    @property
    def num_known_speakers(self) -> int:
        return len(self.active_centers)

    @property
    def num_blocked_speakers(self) -> int:
        return len(self.blocked_centers)

    @property
    def inactive_centers(self) -> List[int]:
        return [
            c
            for c in range(self.max_speakers)
            if c not in self.active_centers or c in self.blocked_centers
        ]

    def get_next_center_position(self) -> Optional[int]:
        for center in range(self.max_speakers):
            if center not in self.active_centers and center not in self.blocked_centers:
                return center

    def init_clusters(self, dimension: int):
        """Initializes the speaker centroid matrix

        Parameters
        ----------
        dimension: int
            Dimension of embeddings used for representing a speaker.
        """
        self.clusters = {}
        self.dimension = dimension
        # self.centers = np.zeros((self.max_speakers, dimension))
        self.active_centers = set()
        self.blocked_centers = set()

    def update(self, assignments: Iterable[Tuple[int, int]], embeddings: np.ndarray):
        """Updates the speaker centroids given a list of assignments and local speaker embeddings

        Parameters
        ----------
        assignments: Iterable[Tuple[int, int]])
            An iterable of tuples with two elements having the first element as the source speaker
            and the second element as the target speaker.
        embeddings: np.ndarray, shape (local_speakers, embedding_dim)
            Matrix containing embeddings for all local speakers.
        """
        if self.clusters is not None:
            for l_spk, g_spk in assignments:
                assert g_spk in self.active_centers, "Cannot update unknown centers"
                self.clusters[g_spk].append(embeddings[l_spk])
                self.embeddings.append(embeddings[l_spk])

    def add_cluster(self, embedding: np.ndarray) -> int:
        """Add a new speaker centroid initialized to a given embedding

        Parameters
        ----------
        embedding: np.ndarray
            Embedding vector of some local speaker

        Returns
        -------
            center_index: int
                Index of the created center
        """
        center = self.get_next_center_position()
        self.clusters[center] = [embedding]
        self.embeddings.append(embedding)
        self.active_centers.add(center)
        return center

    def get_centers(self) -> np.ndarray:
        centers = np.zeros((self.max_speakers, self.dimension))
        for spk_idx, embeddings in self.clusters.items():
            centers[spk_idx] = np.mean(embeddings, axis=0)
        return centers
        
    def identify(
        self, segmentation: SlidingWindowFeature, embeddings: torch.Tensor
    ) -> SpeakerMap:
        """Identify the centroids to which the input speaker embeddings belong.

        Parameters
        ----------
        segmentation: np.ndarray, shape (frames, local_speakers)
            Matrix of segmentation outputs
        embeddings: np.ndarray, shape (local_speakers, embedding_dim)
            Matrix of embeddings

        Returns
        -------
            speaker_map: SpeakerMap
                A mapping from local speakers to global speakers.
        """
        embeddings = embeddings.detach().cpu().numpy()
        active_speakers = np.where(
            np.max(segmentation.data, axis=0) >= self.tau_active
        )[0]
        long_speakers = np.where(np.mean(segmentation.data, axis=0) >= self.rho_update)[
            0
        ]
        # Remove speakers that have NaN embeddings
        no_nan_embeddings = np.where(~np.isnan(embeddings).any(axis=1))[0]
        active_speakers = np.intersect1d(active_speakers, no_nan_embeddings)

        num_local_speakers = segmentation.data.shape[1]

        if self.clusters is None:
            self.init_clusters(embeddings.shape[1])
            assignments = [
                (spk, self.add_cluster(embeddings[spk])) for spk in active_speakers
            ]
            return SpeakerMapBuilder.hard_map(
                shape=(num_local_speakers, self.max_speakers),
                assignments=assignments,
                maximize=False,
            )

        # Obtain a mapping based on distances between embeddings and centers
        dist_map = SpeakerMapBuilder.dist(embeddings, self.get_centers(), self.metric)
        # Remove any assignments containing invalid speakers
        inactive_speakers = np.array(
            [spk for spk in range(num_local_speakers) if spk not in active_speakers]
        )
        dist_map = dist_map.unmap_speakers(inactive_speakers, self.inactive_centers)
        # Keep assignments under the distance threshold
        valid_map = dist_map.unmap_threshold(self.delta_new)

        # Some speakers might be unidentified
        missed_speakers = [
            s for s in active_speakers if not valid_map.is_source_speaker_mapped(s)
        ]

        # Add assignments to new centers if possible
        new_center_speakers = []
        for spk in missed_speakers:
            has_space = len(new_center_speakers) < self.num_free_centers
            if has_space and spk in long_speakers:
                # Flag as a new center
                new_center_speakers.append(spk)
            else:
                # Cannot create a new center
                # Get global speakers in order of preference
                preferences = np.argsort(dist_map.mapping_matrix[spk, :])
                preferences = [
                    g_spk for g_spk in preferences if g_spk in self.active_centers
                ]
                # Get the free global speakers among the preferences
                _, g_assigned = valid_map.valid_assignments()
                free = [g_spk for g_spk in preferences if g_spk not in g_assigned]
                if free:
                    # The best global speaker is the closest free one
                    valid_map = valid_map.set_source_speaker(spk, free[0])

        if self.online:
            # Update known centers
            to_update = [
                (ls, gs)
                for ls, gs in zip(*valid_map.valid_assignments())
                if ls not in missed_speakers and ls in long_speakers
            ]
            self.update(to_update, embeddings)

        # Add new centers
        for spk in new_center_speakers:
            valid_map = valid_map.set_source_speaker(
                spk, self.add_cluster(embeddings[spk])
            )

        return valid_map

    def redo(self):
        # Combine all embeddings from historical buffer
        embeddings = torch.from_numpy(np.stack(self.embeddings))
        embeddings = embeddings.unsqueeze(1)
        total_samples = embeddings.shape[0]
        
        # Resample if exceeding maximum limit
        if total_samples > self.max_cluster_embs:
            if downsample_method == "random":
                embeddings = random_resample(embeddings, self.max_cluster_embs)
            elif downsample_method == "window_overcluster":
                embeddings = window_overcluster_resample(
                    input_tensor=embeddings, 
                    target_count=self.max_cluster_embs
                )
        
        # Perform fresh clustering
        labels = get_clusters(embeddings, self.cluster_config)

        self.clusters.clear()

        embeddings = embeddings.squeeze(1)

        for label in labels.unique():
            self.clusters[int(label)] = list(np.unstack(embeddings[labels == label].detach().cpu().numpy(), axis=0))
        
    def __call__(
        self, segmentation: SlidingWindowFeature, embeddings: torch.Tensor
    ) -> SlidingWindowFeature:
        return SlidingWindowFeature(
            self.identify(segmentation, embeddings).apply(segmentation.data),
            segmentation.sliding_window,
        )

class ModSpeakerDiarization(SpeakerDiarization):
    def __init__(self, config: SpeakerDiarizationConfig | None = None):
        super().__init__(config)

        self.windows = []
        self.batch_size = 32
        
    def reset(self):
        self.set_timestamp_shift(0)
        self.clustering = ModOnlineSpeakerClustering(
            self.config.tau_active,
            self.config.rho_update,
            self.config.delta_new,
            "cosine",
            self.config.max_speakers,
        )
        self.chunk_buffer, self.pred_buffer = [], []

    def __call__(
        self, waveforms: Sequence[SlidingWindowFeature]
    ) -> Sequence[tuple[Annotation, SlidingWindowFeature]]:
        self.windows.extend(waveforms)

        return super().__call__(waveforms)
        
    def redo(self) -> Sequence[tuple[Annotation, SlidingWindowFeature]]:
        self.clustering.redo()
        self.online = False
        
        start_idx = 0

        outputs = []
        while start_idx < len(self.windows):
            end_idx = start_idx + self.batch_size

            batch = self.windows[start_idx:end_idx]
            start_idx = end_idx
            
            if len(batch) >= 1:
                outputs.extend(super().__call__(batch))
            
        self.online = True

        return outputs