import os
import json
import wget
import tempfile
import wave
import struct
from omegaconf import OmegaConf
from nemo.collections.asr.parts.utils.decoder_timestamps_utils import ASRDecoderTimeStamps
from nemo.collections.asr.parts.utils.diarization_utils import OfflineDiarWithASR

def load_config(config_dir, domain_type="meeting"):
	"""
	Load (or download if not present) the diarization inference configuration file.
	The configuration file is expected to reside in config_dir. If not present, it is downloaded.
	"""
	config_filename = f"diar_infer_{domain_type}.yaml"
	config_path = os.path.join(config_dir, config_filename)
	config_url = (
		f"https://raw.githubusercontent.com/NVIDIA/NeMo/main/examples/speaker_tasks/diarization/conf/inference/{config_filename}"
	)
	
	if not os.path.exists(config_path):
		print(f"Downloading config from {config_url}...")
		wget.download(config_url, out=config_dir)
	
	cfg = OmegaConf.load(config_path)
	return cfg

def create_manifest(audio_file_path, out_dir):
	"""
	Create a manifest file as required by the diarization pipeline.
	"""
	manifest_data = {
		'audio_filepath': audio_file_path,
		'offset': 0,
		'duration': None,
		'label': 'infer',
		'text': '-',
		'num_speakers': None,
		'rttm_filepath': None,
		'uem_filepath': None
	}
	manifest_path = os.path.join(out_dir, 'input_manifest.json')
	with open(manifest_path, 'w') as fp:
		json.dump(manifest_data, fp)
		fp.write('\n')
	return manifest_path

class ASRDiarizationInference:
	"""
	A class-based wrapper that loads and caches the ASR model once, but otherwise uses
	a fresh temporary directory for each inference call. This mirrors your "stateless" 
	script's approach for ephemeral files, while reusing the heavy model in memory.
	"""

	def __init__(self, config_dir, domain_type="meeting"):
		"""
		1) Pre-download/load the diarization config (so we don't do it repeatedly)
		2) Create a persistent directory that won't be auto-deleted
		3) Create a valid dummy WAV + manifest in that directory so we can load the heavy ASR model once
		"""
		self.config_dir = config_dir
		self.domain_type = domain_type

		# 1) Load base config once
		self.base_cfg = load_config(config_dir, domain_type=self.domain_type)
		# Standard config updates
		self.base_cfg.diarizer.speaker_embeddings.model_path = 'titanet_large'
		self.base_cfg.diarizer.clustering.parameters.oracle_num_speakers = False
		self.base_cfg.diarizer.vad.model_path = 'vad_multilingual_marblenet'
		self.base_cfg.diarizer.asr.model_path = 'stt_en_fastconformer_ctc_large'
		self.base_cfg.diarizer.oracle_vad = False
		self.base_cfg.diarizer.asr.parameters.asr_based_vad = False

		# 2) Create a persistent model cache directory
		self.model_cache_dir = os.path.join(self.config_dir, "model_cache")
		os.makedirs(self.model_cache_dir, exist_ok=True)

		# 3) Use a dummy WAV and a dummy manifest in the persistent directory
		dummy_wav = os.path.join(self.model_cache_dir, "dummy.wav")
		self._create_dummy_wav(dummy_wav)
		dummy_manifest = create_manifest(dummy_wav, self.model_cache_dir)

		# Build a dummy config that references this persistent directory
		cfg_dummy = OmegaConf.create(OmegaConf.to_container(self.base_cfg))
		cfg_dummy.diarizer.manifest_filepath = dummy_manifest
		cfg_dummy.diarizer.out_dir = self.model_cache_dir

		# Instantiate a temporary decoder purely to load & cache the heavy model
		decoder = ASRDecoderTimeStamps(cfg_dummy.diarizer)
		self.asr_model = decoder.set_asr_model()

		if self.asr_model is None:
			raise RuntimeError("Failed to load the heavy ASR model.")

	def _create_dummy_wav(self, filepath):
		"""
		Create a minimal valid WAV file (e.g., 1 second of silence), so we can load the model.
		"""
		framerate = 16000
		duration_seconds = 1
		n_samples = framerate * duration_seconds
		amplitude = 0  # Silence

		with wave.open(filepath, 'wb') as wf:
			wf.setnchannels(1)       # Mono
			wf.setsampwidth(2)       # 2 bytes per sample
			wf.setframerate(framerate)
			for _ in range(n_samples):
				wf.writeframes(struct.pack('<h', amplitude))

	def infer(self, audio_file_path: str) -> dict:
		"""
		This method replicates your stateless logic:
		  - create a fresh tempfile.TemporaryDirectory()
		  - inside it, create pred_rttms dir & manifest
		  - copy the base_cfg, point diarizer.manifest_filepath and out_dir to the ephemeral folder
		  - create fresh decoder & diarization wrappers, re-using self.asr_model
		"""
		# 1) Create a fresh ephemeral directory for this single inference
		with tempfile.TemporaryDirectory() as temp_out_dir:
			pred_rttms_dir = os.path.join(temp_out_dir, 'pred_rttms')
			os.makedirs(pred_rttms_dir, exist_ok=True)

			# 2) Create the per-run manifest in the ephemeral directory
			manifest_path = create_manifest(audio_file_path, temp_out_dir)

			# 3) Create a copy of the base config, update ephemeral-specific fields
			cfg = OmegaConf.create(OmegaConf.to_container(self.base_cfg))
			cfg.diarizer.manifest_filepath = manifest_path
			cfg.diarizer.out_dir = temp_out_dir

			# 4) Fresh ASR decoder & diarizer wrappers; reuse the heavy asr_model
			asr_decoder = ASRDecoderTimeStamps(cfg.diarizer)
			asr_decoder.set_asr_model()
			word_hyp, word_ts_hyp = asr_decoder.run_ASR(self.asr_model)

			asr_diar = OfflineDiarWithASR(cfg.diarizer)
			asr_diar.word_ts_anchor_offset = asr_decoder.word_ts_anchor_offset
			diar_hyp, _ = asr_diar.run_diarization(cfg, word_ts_hyp)

			# 5) Merge the ASR & diarization results
			transcript_info = asr_diar.get_transcript_with_speaker_labels(diar_hyp, word_hyp, word_ts_hyp)

			# 6) Attempt to read the transcript & RTTM from ephemeral dir
			base_name = os.path.basename(audio_file_path).replace('.wav', '')
			transcript_file = os.path.join(pred_rttms_dir, f"{base_name}.txt")
			rttm_file = os.path.join(pred_rttms_dir, f"{base_name}.rttm")

			transcript = ""
			if os.path.exists(transcript_file):
				with open(transcript_file, "r") as f:
					transcript = f.read()

			rttm = ""
			if os.path.exists(rttm_file):
				with open(rttm_file, "r") as f:
					rttm = f.read()

			# Return exactly as in the stateless script
			return {
				"transcript": transcript,
				"rttm": rttm,
				"transcript_info": transcript_info
			}
