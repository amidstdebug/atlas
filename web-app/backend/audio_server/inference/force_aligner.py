# force_aligner.py
import os
import tempfile
import json
import uuid
from pathlib import Path
from nemo.utils import logging

# Import the AlignmentConfig and the main() function from your (modified) align module.
# (The align module code is adapted from your provided snippet.)
from align import AlignmentConfig, ASSFileConfig, main  as align_main

def run_alignment(alignment_config):
    """
    A thin wrapper to call the alignment pipeline.
    In our example, we simply call the provided `align_main` function.
    """
    align_main(alignment_config)

class ForceAligner:
    def __init__(self, model_name: str = None):
        # model_name can be used to override the default ASR model used for forced alignment.
        self.model_name = model_name

    def align(self, audio_filepath: str, text: str) -> dict:
        """
        Runs Nemo Forced Alignment (NFA) on the audio file using the given text.
        Internally, it writes a manifest JSON line, builds an AlignmentConfig,
        runs the alignment, and then reads back the output manifest.
        Returns a dict with alignment details (e.g. word/token timings).
        """
        # Create a temporary working directory.
        tmpdir = tempfile.mkdtemp(prefix="nfa_")
        utt_id = str(uuid.uuid4())

        # Write a one‐line manifest file with the audio filepath and reference text.
        manifest_data = {
            "audio_filepath": audio_filepath,
            "text": text
        }
        manifest_path = os.path.join(tmpdir, f"{utt_id}_manifest.json")
        with open(manifest_path, 'w') as f:
            f.write(json.dumps(manifest_data) + "\n")
        
        # Create an output directory for alignment results.
        output_dir = os.path.join(tmpdir, "nfa_output")
        os.makedirs(output_dir, exist_ok=True)

        # Build the alignment configuration.
        alignment_config = AlignmentConfig(
            pretrained_name=self.model_name if self.model_name else "stt_en_fastconformer_hybrid_large_pc",
            manifest_filepath=manifest_path,
            output_dir=output_dir,
            audio_filepath_parts_in_utt_id=1,
            batch_size=1,
            use_local_attention=True,
            additional_segment_grouping_separator="|",
            save_output_file_formats=["ctm"],  # we choose CTM output for word/timing info
            ass_file_config=ASSFileConfig(),
        )

        # Run the alignment.
        run_alignment(alignment_config)

        # By default the alignment pipeline writes a new manifest file with output file paths.
        # For example, if the input manifest was "xxx_manifest.json" then the output
        # manifest is "xxx_manifest_with_output_file_paths.json" in the output_dir.
        manifest_stem = Path(manifest_path).stem
        output_manifest = os.path.join(output_dir, manifest_stem + "_with_output_file_paths.json")
        alignment_result = {}
        if os.path.exists(output_manifest):
            with open(output_manifest, 'r') as f:
                # For simplicity, assume one line in the manifest.
                alignment_result = json.loads(f.readline())
        else:
            logging.error("Alignment output manifest not found.")
        
        # (Optionally, you can clean up tmpdir after processing.)
        return alignment_result
