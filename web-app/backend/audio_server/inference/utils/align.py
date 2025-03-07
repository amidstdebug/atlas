# align.py
import copy
import math
import os
from dataclasses import dataclass, field, is_dataclass
from pathlib import Path
from typing import List, Optional

import torch
from omegaconf import OmegaConf

from .data_prep import (
    add_t_start_end_to_utt_obj,
    get_batch_starts_ends,
    get_batch_variables,
    get_manifest_lines_batch,
    is_entry_in_all_lines,
    is_entry_in_any_lines,
)
from .make_ass_files import make_ass_files
from .make_ctm_files import make_ctm_files
from .make_output_manifest import write_manifest_out_line
from .viterbi_decoding import viterbi_decoding

from nemo.collections.asr.models.ctc_models import EncDecCTCModel
from nemo.collections.asr.models.hybrid_rnnt_ctc_models import EncDecHybridRNNTCTCModel
from nemo.collections.asr.parts.utils.streaming_utils import FrameBatchASR
from nemo.collections.asr.parts.utils.transcribe_utils import setup_model
from nemo.core.config import hydra_runner
from nemo.utils import logging

@dataclass
class CTMFileConfig:
    remove_blank_tokens: bool = False
    minimum_timestamp_duration: float = 0

@dataclass
class ASSFileConfig:
    fontsize: int = 20
    vertical_alignment: str = "center"
    resegment_text_to_fill_space: bool = False
    max_lines_per_segment: int = 2
    text_already_spoken_rgb: List[int] = field(default_factory=lambda: [49, 46, 61])
    text_being_spoken_rgb: List[int] = field(default_factory=lambda: [57, 171, 9])
    text_not_yet_spoken_rgb: List[int] = field(default_factory=lambda: [194, 193, 199])

@dataclass
class AlignmentConfig:
    pretrained_name: Optional[str] = None
    model_path: Optional[str] = None
    manifest_filepath: Optional[str] = None
    output_dir: Optional[str] = None
    align_using_pred_text: bool = False
    transcribe_device: Optional[str] = None
    viterbi_device: Optional[str] = None
    batch_size: int = 1
    use_local_attention: bool = True
    additional_segment_grouping_separator: Optional[str] = None
    audio_filepath_parts_in_utt_id: int = 1
    use_buffered_chunked_streaming: bool = False
    chunk_len_in_secs: float = 1.6
    total_buffer_in_secs: float = 4.0
    chunk_batch_size: int = 32
    simulate_cache_aware_streaming: Optional[bool] = False
    save_output_file_formats: List[str] = field(default_factory=lambda: ["ctm", "ass"])
    ctm_file_config: CTMFileConfig = CTMFileConfig()
    ass_file_config: ASSFileConfig = ASSFileConfig()

def load_alignment_model(cfg: AlignmentConfig) -> torch.nn.Module:
    """
    Loads and returns the ASR model based on the provided configuration.
    This should be called only once and the model instance reused.
    """
    transcribe_device = (
        torch.device(cfg.transcribe_device)
        if cfg.transcribe_device
        else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )
    model, _ = setup_model(cfg, transcribe_device)
    model.eval()
    if isinstance(model, EncDecHybridRNNTCTCModel):
        model.change_decoding_strategy(decoder_type="ctc")
    if cfg.use_local_attention:
        logging.info("Using local attention for model.")
        model.change_attention_model(self_attention_model="rel_pos_local_attn", att_context_size=[64, 64])
    if not (isinstance(model, EncDecCTCModel) or isinstance(model, EncDecHybridRNNTCTCModel)):
        raise NotImplementedError("Model must be an instance of EncDecCTCModel or EncDecHybridRNNTCTCModel.")
    return model

def _alignment_pipeline(cfg: AlignmentConfig, model: Optional[torch.nn.Module] = None) -> None:
    """
    Core alignment logic. If a model is provided, it is used;
    otherwise, a new model is loaded.
    """
    logging.info(f'Hydra config: {OmegaConf.to_yaml(cfg)}')
    if is_dataclass(cfg):
        cfg = OmegaConf.structured(cfg)

    # --- Validation code (unchanged semantics) ---
    if cfg.model_path is None and cfg.pretrained_name is None:
        raise ValueError("Both cfg.model_path and cfg.pretrained_name cannot be None")
    if cfg.model_path is not None and cfg.pretrained_name is not None:
        raise ValueError("One of cfg.model_path and cfg.pretrained_name must be None")
    if cfg.manifest_filepath is None:
        raise ValueError("cfg.manifest_filepath must be specified")
    if cfg.output_dir is None:
        raise ValueError("cfg.output_dir must be specified")
    if cfg.batch_size < 1:
        raise ValueError("cfg.batch_size cannot be zero or a negative number")
    if cfg.additional_segment_grouping_separator in ["", " "]:
        raise ValueError("cfg.additional_grouping_separator cannot be empty string or space character")
    if cfg.ctm_file_config.minimum_timestamp_duration < 0:
        raise ValueError("cfg.minimum_timestamp_duration cannot be a negative number")
    if cfg.ass_file_config.vertical_alignment not in ["top", "center", "bottom"]:
        raise ValueError("cfg.ass_file_config.vertical_alignment must be one of 'top', 'center' or 'bottom'")
    for rgb_list in [
        cfg.ass_file_config.text_already_spoken_rgb,
        cfg.ass_file_config.text_being_spoken_rgb,
        cfg.ass_file_config.text_not_yet_spoken_rgb,
    ]:
        if len(rgb_list) != 3:
            raise ValueError("RGB lists must contain exactly 3 elements.")

    if not is_entry_in_all_lines(cfg.manifest_filepath, "audio_filepath"):
        raise RuntimeError("Manifest missing 'audio_filepath' entry.")
    if cfg.align_using_pred_text:
        if is_entry_in_any_lines(cfg.manifest_filepath, "pred_text"):
            raise RuntimeError("Cannot use pred_text when align_using_pred_text is True.")
    else:
        if not is_entry_in_all_lines(cfg.manifest_filepath, "text"):
            raise RuntimeError("Manifest missing 'text' entry.")

    # --- Device initialization ---
    transcribe_device = (
        torch.device(cfg.transcribe_device)
        if cfg.transcribe_device
        else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )
    logging.info(f"Transcribe device: {transcribe_device}")
    viterbi_device = (
        torch.device(cfg.viterbi_device)
        if cfg.viterbi_device
        else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )
    logging.info(f"Viterbi device: {viterbi_device}")
    if transcribe_device.type == 'cuda' or viterbi_device.type == 'cuda':
        logging.warning("Using GPU(s); consider CPU if OOM errors occur.")

    # --- Load model only if not provided ---
    if model is None:
        model = load_alignment_model(cfg)

    # --- (Optionally, include buffered streaming logic here) ---
    buffered_chunk_params = {}
    starts, ends = get_batch_starts_ends(cfg.manifest_filepath, cfg.batch_size)
    output_timestep_duration = None
    os.makedirs(cfg.output_dir, exist_ok=True)
    tgt_manifest_name = str(Path(cfg.manifest_filepath).stem) + "_with_output_file_paths.json"
    tgt_manifest_filepath = str(Path(cfg.output_dir) / tgt_manifest_name)
    f_manifest_out = open(tgt_manifest_filepath, 'w')
    for start, end in zip(starts, ends):
        manifest_lines_batch = get_manifest_lines_batch(cfg.manifest_filepath, start, end)
        (log_probs_batch, y_batch, T_batch, U_batch, utt_obj_batch, output_timestep_duration) = get_batch_variables(
            manifest_lines_batch,
            model,
            cfg.additional_segment_grouping_separator,
            cfg.align_using_pred_text,
            cfg.audio_filepath_parts_in_utt_id,
            output_timestep_duration,
            cfg.simulate_cache_aware_streaming,
            cfg.use_buffered_chunked_streaming,
            buffered_chunk_params,
        )
        alignments_batch = viterbi_decoding(log_probs_batch, y_batch, T_batch, U_batch, viterbi_device)
        for utt_obj, alignment_utt in zip(utt_obj_batch, alignments_batch):
            utt_obj = add_t_start_end_to_utt_obj(utt_obj, alignment_utt, output_timestep_duration)
            if "ctm" in cfg.save_output_file_formats:
                utt_obj = make_ctm_files(utt_obj, cfg.output_dir, cfg.ctm_file_config)
            if "ass" in cfg.save_output_file_formats:
                utt_obj = make_ass_files(utt_obj, cfg.output_dir, cfg.ass_file_config)
            write_manifest_out_line(f_manifest_out, utt_obj)
    f_manifest_out.close()

@hydra_runner(config_name="AlignmentConfig", schema=AlignmentConfig)
def main(cfg: AlignmentConfig) -> None:
    _alignment_pipeline(cfg)
    return None

def run_alignment(cfg: AlignmentConfig, model: Optional[torch.nn.Module] = None) -> None:
    """
    A wrapper around the alignment pipeline. This function calls the pipeline
    with the provided configuration and an optional preloaded model.
    """
    _alignment_pipeline(cfg, model=model)
