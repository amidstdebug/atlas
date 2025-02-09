import os
import json
import wget
from omegaconf import OmegaConf

class Diarizer:
    def __init__(self, config_path=None, out_dir="diarizer_output",
                 num_speakers=None, use_oracle_vad=False):
        """
        Initialize the diarizer by loading the config and model weights.
        This implementation supports only the clustering-based diarization method.
        
        Parameters:
            config_path (str): Optional path to a diarization YAML config.
            out_dir (str): Directory where outputs and intermediate files are stored.
            num_speakers (int or None): Number of speakers (if known).
            use_oracle_vad (bool): Whether to use ground-truth RTTM for VAD.
        """
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)
        self.num_speakers = num_speakers
        self.use_oracle_vad = use_oracle_vad

        self.config = self._load_config(config_path)
        self._update_config()

        # Only clustering diarizer is supported.
        from nemo.collections.asr.models import ClusteringDiarizer
        self.model = ClusteringDiarizer(cfg=self.config)

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

    def _create_manifest(self, alignment_result, rttm_filepath=None):
        """
        Create a manifest for a given alignment result.
        
        The manifest is a JSON-lines file containing keys that NeMo's diarization
        pipeline expects:
            - audio_filepath
            - offset
            - duration
            - label
            - text
            - num_speakers
            - rttm_filepath
            - uem_filepath
        """
        manifest = {
            "audio_filepath": alignment_result["audio_filepath"],
            "offset": 0,
            "duration": None,
            "label": "infer",
            "text": alignment_result.get("text", "-"),
            "num_speakers": self.num_speakers,
            "rttm_filepath": rttm_filepath if rttm_filepath else "",
            "uem_filepath": None
        }
        manifest_path = os.path.join(self.out_dir, "input_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
            f.write("\n")
        return manifest_path

    def diarize(self, alignment_result, rttm_filepath=None):
        """
        Perform speaker diarization using the clustering method.
        
        Parameters:
            alignment_result (dict): Contains keys such as "audio_filepath" and "text".
            rttm_filepath (str or None): Optional RTTM file path for Oracle VAD.
        
        Returns:
            pred_rttm (str): Path to the predicted RTTM file.
        """
        manifest_path = self._create_manifest(alignment_result, rttm_filepath)
        # Update the config with the current manifest path.
        self.config.diarizer.manifest_filepath = manifest_path
        if hasattr(self.model, "_diarizer_params"):
            self.model._diarizer_params.manifest_filepath = manifest_path

        print("Running diarization inference...")
        self.model.diarize()

        base_audio = os.path.splitext(os.path.basename(alignment_result["audio_filepath"]))[0]
        pred_rttm = os.path.join(self.out_dir, "pred_rttms", f"{base_audio}.rttm")
        if os.path.exists(pred_rttm):
            print(f"Diarization complete. Predicted RTTM at: {pred_rttm}")
        else:
            print("Diarization complete but RTTM file not found. Check logs.")
        return pred_rttm