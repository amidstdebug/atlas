import os
import torch
import logging

from nemo.collections.asr.models import ClusteringDiarizer
# Import your long-form clustering logic
from nemo.collections.asr.parts.utils.longform_clustering import LongFormSpeakerClustering

logger = logging.getLogger(__name__)

class LongFormClusteringDiarizer(ClusteringDiarizer):
	"""
	A drop-in replacement for NeMo's ClusteringDiarizer that uses the
	long_form_speaker_clustering approach for large recordings to avoid OOM.
	"""

	def __init__(
		self,
		chunk_cluster_count: int = 50,
		embeddings_per_chunk: int = 10000,
		max_num_speakers: int = 8,
		# any other relevant arguments you'd like to pass
		**kwargs
	):
		"""
		Args:
			chunk_cluster_count (int): Over-clustering target for each chunk
			embeddings_per_chunk (int): Maximum # of embeddings to handle in each chunk
			max_num_speakers (int): The upper bound on the speaker count for the final stage
			**kwargs: Passed along to the parent ClusteringDiarizer
		"""
		super().__init__(**kwargs)
		self.chunk_cluster_count = chunk_cluster_count
		self.embeddings_per_chunk = embeddings_per_chunk
		self.max_num_speakers = max_num_speakers

		self.config = self._load_config(config_path)
		self.__update_config()

		# We create one instance of the long-form clustering engine
		self.long_form_clustering = LongFormSpeakerClustering(cuda=self._is_cuda_available())

		# We’ll store the final cluster labels in memory
		self._final_cluster_labels = None

	def _load_config(self, config_path):
		# If no config is provided, download the default meeting config (suitable for long recordings)
		if not config_path:
			config_url = ("https://raw.githubusercontent.com/NVIDIA/NeMo/main/"
						  "examples/speaker_tasks/diarization/conf/inference/diar_infer_meeting.yaml")
			config_path = os.path.join(self.out_dir, "diar_infer_meeting.yaml")
			if not os.path.exists(config_path):
				print("Downloading default diarization config...")
				wget.download(config_url, config_path)
				print(f"\nDownloaded config to: {config_path}")
		return OmegaConf.load(config_path)

	def _update_config(self):
		# Update configuration settings common to all inferences.
		self.config.diarizer.out_dir = self.out_dir
		self.config.diarizer.oracle_vad = self.use_oracle_vad
		if self.num_speakers is not None:
			self.config.diarizer.num_speakers = self.num_speakers

		# For system VAD (when oracle_vad is False), set the VAD model and its parameters.
		if not self.use_oracle_vad:
			self.config.diarizer.vad.model_path = "vad_multilingual_marblenet"
			self.config.diarizer.vad.parameters.onset = 0.8
			self.config.diarizer.vad.parameters.offset = 0.6
			self.config.diarizer.vad.parameters.pad_offset = -0.05

		# Set speaker embedding extraction parameters.
		self.config.diarizer.speaker_embeddings.model_path = "titanet_large"
		self.config.diarizer.speaker_embeddings.parameters.window_length_in_sec = [1.5, 1.25, 1.0, 0.75, 0.5]
		self.config.diarizer.speaker_embeddings.parameters.shift_length_in_sec = [0.75, 0.625, 0.5, 0.375, 0.1]
		self.config.diarizer.speaker_embeddings.parameters.multiscale_weights = [1, 1, 1, 1, 1]

		# Clustering settings: do not use oracle number of speakers.
		self.config.diarizer.clustering.parameters.oracle_num_speakers = False


	def _is_cuda_available(self):
		# Basic helper - you might want something more robust
		return torch.cuda.is_available()

	def _perform_offline_clustering(self):
		"""
		Overrides the base method that normally calls `spectral` or `agglomerative` clustering.
		Instead, we handle it with the LongFormSpeakerClustering approach if the audio has too many segments.
		"""
		logger.info("Starting offline clustering (Long-Form).")

		# 1. Grab the multi-scale embeddings + timestamps from the aggregator
		#    The parent class typically sets them in self._embeddings_in_scales, self._timestamps_in_scales
		#    and self._multiscale_segment_counts, self._multiscale_weights
		embeddings_in_scales = self._embeddings_in_scales
		timestamps_in_scales = self._timestamps_in_scales
		multiscale_segment_counts = self._multiscale_segment_counts
		multiscale_weights = self._multiscale_weights

		# 2. Prepare the inputs for the long-form clustering
		#    We must pack them into a dictionary matching the `forward_infer` signature from
		#    LongFormSpeakerClustering
		param_dict = {
			"embeddings": embeddings_in_scales,          # shape: [sum-of-segments, emb_dim]
			"timestamps": timestamps_in_scales,          # shape: [sum-of-segments, 2]
			"multiscale_segment_counts": multiscale_segment_counts,
			"multiscale_weights": multiscale_weights,
			"oracle_num_speakers": torch.tensor(self._diarizer_params.oracle_num_speakers, dtype=torch.long),
			"max_rp_threshold": torch.tensor(self._max_rp_threshold, dtype=torch.float),
			"max_num_speakers": torch.tensor(self.max_num_speakers, dtype=torch.long),
			"enhanced_count_thres": torch.tensor(self._enhanced_count_thres, dtype=torch.long),
			"sparse_search_volume": torch.tensor(self._sparse_search_volume, dtype=torch.long),
			"fixed_thres": torch.tensor(self._fixed_thres, dtype=torch.float),
		}

		# 3. If the total # of segments is large or if the total audio duration is large,
		#    we do the chunk-based approach. This is handled internally by `forward_infer`.
		#    We pass chunk_cluster_count / embeddings_per_chunk as well.
		#    The logic in `forward_infer` decides if it must do chunk-based approach or not.
		param_dict["chunk_cluster_count"] = torch.tensor(self.chunk_cluster_count, dtype=torch.long)
		param_dict["embeddings_per_chunk"] = torch.tensor(self.embeddings_per_chunk, dtype=torch.long)

		# 4. Actually run the long-form clustering
		cluster_labels = self.long_form_clustering.forward_infer(**param_dict)

		# 5. Now `cluster_labels` is a 1D tensor with length = # base-scale segments
		#    We'll store them for use in `_create_rttm_from_clusters()`.
		self._final_cluster_labels = cluster_labels

	def _create_rttm_from_clusters(self):
		"""
		Replaces the base method. We have the final cluster labels in self._final_cluster_labels.
		Next, we create the final RTTM with each base-scale segment assigned a speaker label.
		"""
		logger.info("Creating final RTTM from clusters (Long-Form).")

		# The parent class method is typically:
		#   1. map cluster labels back to each sub-segment
		#   2. create start/end times
		#   3. write out the RTTM lines

		# We'll do something similar, but rely on the internal logic from `ClusteringDiarizer._write_rttm(...)`
		# or we can replicate it. For brevity:
		if self._final_cluster_labels is None:
			raise ValueError("No cluster labels found. Please call _perform_offline_clustering() first.")

		base_scale_count = self._multiscale_segment_counts[-1].item()
		if base_scale_count != len(self._final_cluster_labels):
			raise ValueError(
				f"Mismatch: base scale count = {base_scale_count}, but we have {len(self._final_cluster_labels)} labels."
			)

		# The parent code normally uses self._timestamp_list (or self._diar_timestamp) for the base scale
		# and merges them with the cluster labels. Something like:
		speaker_labels = self._final_cluster_labels.cpu().numpy().tolist()
		base_timestamps = self._timestamps_in_scales[-1].cpu().numpy()

		# Each row of base_timestamps is [start_time, end_time].
		# We'll create a list of RTTM lines:
		rttm_lines = []
		for i, label in enumerate(speaker_labels):
			start_time = base_timestamps[i][0]
			end_time = base_timestamps[i][1]
			duration = end_time - start_time
			spk_label = f"speaker_{label}"
			# `file_id` is usually the reference from self.AUDIO_RTTM_MAP or self._current_file_id
			file_id = self._current_file_id
			line = f"SPEAKER {file_id} 1 {start_time:.3f} {duration:.3f} <NA> <NA> {spk_label} <NA> <NA>\n"
			rttm_lines.append(line)

		# 6. Write out the RTTM file
		audio_rttm = self.AUDIO_RTTM_MAP[self._current_file_id]
		out_rttm_dir = os.path.join(self._out_dir, "pred_rttms")
		os.makedirs(out_rttm_dir, exist_ok=True)
		out_rttm_path = os.path.join(out_rttm_dir, f"{audio_rttm['uniq_id']}.rttm")
		with open(out_rttm_path, "w") as f:
			f.writelines(rttm_lines)

		logger.info(f"Final RTTM saved to: {out_rttm_path}")


	def _diarize_single_file(self, uniq_id):
		"""
		Example override of the single-file diarization logic. This is called by diarize().
		The flow is typically:
		  1. VAD
		  2. subseg + multi-scale embeddings
		  3. offline clustering
		  4. create RTTM
		We override the "3" + "4" steps to do our long-form approach.
		"""
		super()._perform_speech_activity_detection()  # normal VAD
		super()._perform_segmentation()               # normal sub-seg
		super()._perform_embedding_extract()          # normal embedding extraction

		# Instead of the base `super()._perform_clustering()`, do our own:
		self._perform_offline_clustering()
		self._create_rttm_from_clusters()

	# End of LongFormClusteringDiarizer
