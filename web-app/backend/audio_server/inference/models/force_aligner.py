# force_aligner.py
import os
import tempfile
import json
import uuid
from pathlib import Path
from nemo.utils import logging
from ..utils.align import AlignmentConfig, ASSFileConfig, load_alignment_model, run_alignment

class ForceAligner:
    def __init__(self, model_name: str = None):
        # model_name can override the default ASR model used for forced alignment.
        self.model_name = model_name
        # Create a base configuration for model loading.
        # Dummy manifest_filepath and output_dir values are used here because they are not needed for model instantiation.
        base_cfg = AlignmentConfig(
            pretrained_name=self.model_name if self.model_name else "stt_en_fastconformer_hybrid_large_pc",
            manifest_filepath="dummy_manifest.json",
            output_dir="dummy_output",
            batch_size=1,
            use_local_attention=True,
            additional_segment_grouping_separator="|",
            save_output_file_formats=["ctm"],
            ass_file_config=ASSFileConfig(),
        )
        # Load and cache the model once.
        self.model = load_alignment_model(base_cfg)

    def align(self, audio_filepath: str, text: str) -> dict:
        """
        Runs Nemo Forced Alignment on the audio file using the given text.
        Internally, it writes a manifest JSON line, builds an AlignmentConfig,
        runs the alignment using the preloaded model, and then reads back the output manifest.
        Returns a dict with alignment details (e.g. word/token timings).
        """
        tmpdir = tempfile.mkdtemp(prefix="nfa_")
        utt_id = str(uuid.uuid4())
        manifest_data = {
            "audio_filepath": audio_filepath,
            "text": text
        }
        manifest_path = os.path.join(tmpdir, f"{utt_id}_manifest.json")
        with open(manifest_path, 'w') as f:
            f.write(json.dumps(manifest_data) + "\n")
        output_dir = os.path.join(tmpdir, "nfa_output")
        os.makedirs(output_dir, exist_ok=True)
        alignment_config = AlignmentConfig(
            pretrained_name=self.model_name if self.model_name else "stt_en_fastconformer_hybrid_large_pc",
            manifest_filepath=manifest_path,
            output_dir=output_dir,
            audio_filepath_parts_in_utt_id=1,
            batch_size=1,
            use_local_attention=True,
            additional_segment_grouping_separator="|",
            save_output_file_formats=["ctm"],
            ass_file_config=ASSFileConfig(),
        )
        # Run the alignment using the cached model.
        run_alignment(alignment_config, model=self.model)
        manifest_stem = Path(manifest_path).stem
        output_manifest = os.path.join(output_dir, manifest_stem + "_with_output_file_paths.json")
        alignment_result = {}
        if os.path.exists(output_manifest):
            with open(output_manifest, 'r') as f:
                alignment_result = json.loads(f.readline())
        else:
            logging.error("Alignment output manifest not found.")
        return alignment_result
